import asyncio
import logging
from urllib.parse import urlparse

from app.config import settings
from app.llm.client import call_llm, parse_json_response
from app.llm.prompt_loader import format_prompt

logger = logging.getLogger("clearlens.services.web_evidence")

TIER_1_DOMAINS = {
    "reuters.com", "apnews.com", "afp.com", "bbc.com", "bbc.co.uk", "bloomberg.com",
    "ft.com", "aljazeera.com", "theguardian.com", "dw.com",
    "politifact.com", "snopes.com", "fullfact.org", "factcheck.org", "boomlive.in",
    "factly.in", "newschecker.in", "who.int", "un.org", "unicef.org", "unesco.org", "unep.org",
    "unodc.org", "ohchr.org", "unhcr.org", "imf.org", "worldbank.org", "oecd.org",
    "nato.int", "europol.europa.eu", "interpol.int", "sipri.org", "iiss.org",
    "nasa.gov", "esa.int", "isro.gov.in", "usgs.gov", "ipcc.ch", "wmo.int",
    "iea.org", "fao.org", "ilo.org", "cdc.gov", "epa.gov", "noaa.gov",
    "nature.com", "science.org", "pnas.org", "pubmed.ncbi.nlm.nih.gov",
    "thelancet.com", "mayoclinic.org", "hopkinsmedicine.org", "harvard.edu",
    "stanford.edu", "mit.edu", "ieee.org", "acm.org", "cisa.gov", "nist.gov",
    "mitre.org", "enisa.europa.eu", "pewresearch.org", "rand.org",
    "brookings.edu", "cfr.org", "chathamhouse.org", "carnegieendowment.org",
    "crisisgroup.org", "freedomhouse.org", "amnesty.org", "hrw.org", "icrc.org",
    "eci.gov.in", "loc.gov", "si.edu", "nationalgeographic.com",
    "ourworldindata.org", "reliefweb.int", "emdat.be", "gdacs.org",
    "iucnredlist.org", "panda.org", "krebsonsecurity.com", "thehackernews.com",
}

TIER_2_DOMAINS = {
    "nytimes.com", "washingtonpost.com", "wsj.com", "cnn.com", "nbcnews.com",
    "abcnews.go.com", "cbsnews.com", "usatoday.com", "times.co.uk",
    "telegraph.co.uk", "economist.com", "independent.co.uk", "time.com",
    "newsweek.com", "forbes.com", "fortune.com", "businessinsider.com", "vox.com",
    "npr.org", "politico.com", "axios.com", "theverge.com", "wired.com",
    "arstechnica.com", "techcrunch.com", "cnbc.com", "hindustantimes.com",
    "indiatimes.com", "ndtv.com", "indianexpress.com", "thehindu.com",
    "livemint.com", "firstpost.com", "news18.com", "scroll.in", "thewire.in",
    "theprint.in", "deccanherald.com", "timesnownews.com", "moneycontrol.com",
    "business-standard.com", "thequint.com", "espn.com", "skysports.com", "billboard.com",
    "variety.com", "imdb.com", "ew.com",
}

TRUSTED_DOMAINS = TIER_1_DOMAINS | TIER_2_DOMAINS
SEARCH_STATUSES = ("supported", "contradicted", "mixed", "insufficient")


def domain_of(url: str) -> str:
    try:
        host = urlparse(url if "://" in url else "https://" + url).netloc.lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def source_tier_for(url: str) -> int:
    domain = domain_of(url)
    for trusted in TIER_1_DOMAINS:
        if domain == trusted or domain.endswith("." + trusted):
            return 1
    for trusted in TIER_2_DOMAINS:
        if domain == trusted or domain.endswith("." + trusted):
            return 2
    return 3


def _search(claim: str, max_results: int) -> list[dict]:
    try:
        from ddgs import DDGS
        return list(DDGS().text(claim[:200], max_results=max_results))
    except Exception as exc:
        logger.warning("web search failed: %s", exc)
        return []


class WebEvidenceService:
    def __init__(self):
        self._search_lock = asyncio.Lock()

    async def collect(self, claims: list[dict], video_summary: str = "") -> dict:
        if not settings.web_evidence_enabled:
            return self._empty("disabled")
        if not claims:
            return self._empty("no_claims")

        selected = claims[: settings.web_evidence_max_claims]
        search_results = list(await asyncio.gather(
            *(asyncio.to_thread(_search, c.get("claim", ""), settings.web_search_max_results) for c in selected)
        ))

        if not any(search_results):
            return self._empty("search_failed")

        agents = [
            self._analyze(c, r, video_summary)
            for c, r in zip(selected, search_results) if r
        ]
        outcomes = await asyncio.gather(*agents, return_exceptions=True)

        docs = []
        for outcome in outcomes:
            if isinstance(outcome, Exception):
                logger.warning("evidence agent failed: %s", outcome)
                continue
            docs.extend(outcome)

        return {
            "web_evidence": docs,
            "web_evidence_count": len(docs),
            "status": "ok" if docs else "empty",
        }

    async def _analyze(self, claim: dict, search_results: list[dict], video_summary: str) -> list[dict]:
        prompt = format_prompt(
            "evidence_search",
            claim=claim.get("claim", ""),
            category_block=(
                f"CLAIM CATEGORY: {claim.get('category', '')}"
                if claim.get("category")
                else "CLAIM CATEGORY: (not classified)"
            ),
            video_summary=video_summary[:1500],
            search_results=self._format_results(search_results),
        )

        parsed = None
        try:
            content = await call_llm(prompt, max_tokens=1500, temperature=0.1)
            if content:
                parsed = parse_json_response(content)
        except Exception as exc:
            logger.warning("evidence agent LLM call failed: %s", exc)

        if not self._valid(parsed):
            logger.warning("evidence agent returned invalid output, using raw search fallback")
            return self._fallback_docs(claim, search_results)

        status = parsed["status"]
        docs = []
        for item in parsed.get("evidence", [])[:5]:
            url = str(item.get("url", "")).strip()
            if not url.startswith("http"):
                continue
            docs.append(self._to_doc(item, claim, status))
        return docs or self._fallback_docs(claim, search_results)

    def _to_doc(self, item: dict, claim: dict, status: str) -> dict:
        url = str(item.get("url", "")).strip()
        title = str(item.get("title", "")).strip()
        website = str(item.get("website", "")).strip()
        published = str(item.get("published", "")).strip()
        summary = str(item.get("summary", "")).strip()
        parts = [x for x in (
            f"Title: {title}",
            f"Website: {website}",
            f"URL: {url}",
            f"Published: {published}",
            f"Summary: {summary}",
        ) if x]
        return {
            "content": " | ".join(parts)[:1500],
            "metadata": {
                "source_tier": source_tier_for(url),
                "url": url,
                "website": website,
                "title": title,
                "published": published,
                "source": website,
                "contradicts": status == "contradicted",
                "origin": "web",
                "claim": claim.get("claim", "")[:200],
            },
        }

    def _fallback_docs(self, claim: dict, search_results: list[dict]) -> list[dict]:
        docs = []
        for result in search_results:
            url = str(result.get("href", "") or result.get("url", "")).strip()
            if not url.startswith("http"):
                continue
            if source_tier_for(url) not in (1, 2):
                continue
            title = str(result.get("title", "")).strip()
            body = str(result.get("body", "")).strip()[:500]
            parts = [x for x in (f"Title: {title}", f"URL: {url}", f"Summary: {body}") if x]
            docs.append({
                "content": " | ".join(parts)[:1500],
                "metadata": {
                    "source_tier": source_tier_for(url),
                    "url": url,
                    "website": domain_of(url),
                    "title": title,
                    "published": "",
                    "source": domain_of(url),
                    "contradicts": False,
                    "origin": "web",
                    "claim": claim.get("claim", "")[:200],
                },
            })
            if len(docs) >= 5:
                break
        return docs

    def _format_results(self, results: list[dict]) -> str:
        lines = []
        for i, r in enumerate(results[:8], 1):
            title = str(r.get("title", ""))
            href = str(r.get("href", "") or r.get("url", ""))
            body = str(r.get("body", ""))[:400]
            lines.append(f"{i}. {title}\n   URL: {href}\n   {body}")
        return "\n\n".join(lines) or "No results."

    def _valid(self, parsed) -> bool:
        if not isinstance(parsed, dict):
            return False
        if parsed.get("status") not in SEARCH_STATUSES:
            return False
        confidence = parsed.get("confidence")
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            return False
        evidence = parsed.get("evidence")
        if not isinstance(evidence, list):
            return False
        return all(isinstance(e, dict) and e.get("url") for e in evidence)

    def _empty(self, reason: str) -> dict:
        return {"web_evidence": [], "web_evidence_count": 0, "status": reason}
