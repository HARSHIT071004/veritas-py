import time
import asyncio
from typing import Optional
from app.mcp.server import MCPServer
from app.data.database import Database
from app.data.models import AnalysisResult
from app.pipeline.trust import TrustEngine


class Analyzer:
    def __init__(self, mcp: MCPServer, db: Database):
        self.mcp = mcp
        self.db = db
        self.trust = TrustEngine()

    # ─── Public ────────────────────────────────────────────────

    async def analyze(self, video_id: str, metadata: dict, user_id: str) -> dict:
        cached = self.db.get_cached(video_id)
        if cached:
            return cached

        start = time.time()

        # ── Phase 1: Parallel ──────────────────────────────────
        # STT and OCR are independent — run them concurrently
        transcript_task = self._extract_transcript(video_id)
        vision_task = self._extract_vision(video_id, metadata.get("title", ""))
        transcript_res, vision_res = await asyncio.gather(transcript_task, vision_task)

        transcript = transcript_res.get("transcript")
        transcript_source = transcript_res.get("source")
        ocr_text = vision_res.get("ocr_text")
        ocr_used = vision_res.get("used", False)

        # ── Phase 2: Context Builder ───────────────────────────
        # Merge all sources into a single structured context
        context = {
            "transcript": transcript or "",
            "ocr_text": ocr_text or "",
            "title": metadata.get("title", ""),
            "description": metadata.get("description", ""),
            "channel": metadata.get("channel", ""),
        }

        # ── Phase 3: LLM Pipeline (sequential) ─────────────────
        # 3a — Extract factual claims from context
        claims_res = await self._extract_claims(**context)
        claims_list = claims_res.get("claims", [])
        video_summary = claims_res.get("video_summary", "")

        # 3b — Build query string for RAG from extracted claims
        if claims_list:
            claim_text = claims_list[0].get("claim", "")
            full_claims_text = " | ".join(c.get("claim", "") for c in claims_list)
        else:
            claim_text = metadata.get("title", "") or transcript[:200] if transcript else video_id
            full_claims_text = claim_text

        # 3c — Retrieve evidence from knowledge base
        evidence_res = await self._retrieve_evidence(full_claims_text)
        evidence_docs = evidence_res.get("results", [])

        # 3d — LLM reasons about claims + evidence and returns verdict
        reason_res = await self._reason_verdict(
            claim=full_claims_text,
            transcript=transcript or "",
            ocr_text=ocr_text or "",
            evidence=[d.get("content", "") for d in evidence_docs]
        )

        # ── Phase 4: Trust Score ───────────────────────────────
        trust = self.trust.score(
            verdict=reason_res.get("verdict", "unverifiable"),
            llm_confidence=reason_res.get("confidence", 0.0),
            evidence_sources=[d.get("metadata", {}) for d in evidence_docs],
            evidence_count=len(evidence_docs)
        )

        elapsed = int((time.time() - start) * 1000)

        result = AnalysisResult(
            video_id=video_id,
            user_id=user_id,
            claim=reason_res.get("claim", claim_text[:200]),
            verdict=reason_res.get("verdict", "unverifiable"),
            confidence=trust.score,
            explanation=reason_res.get("explanation", ""),
            sources=reason_res.get("sources", []),
            transcript_used=transcript_source is not None,
            ocr_used=ocr_used,
            processing_time_ms=elapsed
        )

        result_dict = result.to_dict()
        result_dict["trust_label"] = trust.label
        result_dict["transcript_source"] = transcript_source
        result_dict["claims_list"] = claims_list
        result_dict["video_summary"] = video_summary

        self.db.set_cache(video_id, result_dict)
        self.db.save_history(result)

        return result_dict

    # ─── Private helpers ───────────────────────────────────────

    async def _extract_claims(self, transcript: str, ocr_text: str, title: str, description: str, channel: str) -> dict:
        tool = self.mcp.get_tool("extract_claims")
        if not tool:
            return {"claims": [], "video_summary": ""}
        return await tool.execute(transcript=transcript, ocr_text=ocr_text, title=title, description=description, channel=channel)

    async def _extract_transcript(self, video_id: str) -> dict:
        tool = self.mcp.get_tool("extract_transcript")
        if not tool:
            return {"transcript": None, "source": None}
        return await tool.execute(video_id=video_id)

    async def _extract_vision(self, video_id: str, claim: str) -> dict:
        tool = self.mcp.get_tool("extract_vision_text")
        if not tool:
            return {"ocr_text": None, "used": False}
        return await tool.execute(video_id=video_id, claim_text=claim)

    async def _retrieve_evidence(self, query: str) -> dict:
        tool = self.mcp.get_tool("retrieve_evidence")
        if not tool:
            return {"results": [], "total": 0}
        return await tool.execute(query=query, top_k=5)

    async def _reason_verdict(self, claim: str, transcript: str, ocr_text: str, evidence: list[str]) -> dict:
        tool = self.mcp.get_tool("reason_verdict")
        if not tool:
            return {"claim": claim, "verdict": "unverifiable", "confidence": 0.0, "explanation": "", "sources": []}
        return await tool.execute(claim=claim, transcript=transcript, ocr_text=ocr_text, evidence=evidence)
