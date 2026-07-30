import json
import re
import asyncio
import time
import hashlib
import logging
from typing import Optional
import httpx
from app.config import settings

logger = logging.getLogger("clearlens.llm")

_llm_cache: dict[str, tuple[str, float]] = {}
_http_client: Optional[httpx.AsyncClient] = None
_MAX_CACHE_SIZE = 256
_CACHE_TTL = 3600

_circuit_breakers: dict[str, dict] = {}


def _get_circuit_state(provider: str) -> dict:
    if provider not in _circuit_breakers:
        _circuit_breakers[provider] = {
            "state": "closed",
            "failures": 0,
            "failure_threshold": 5,
            "cooldown_ms": 30000,
            "last_failure_time": 0,
        }
    return _circuit_breakers[provider]


def _is_circuit_open(provider: str) -> bool:
    state = _get_circuit_state(provider)
    if state["state"] == "closed":
        return False
    if state["state"] == "open":
        elapsed = time.time() - state["last_failure_time"]
        if elapsed * 1000 >= state["cooldown_ms"]:
            state["state"] = "half-open"
            logger.info(f"Circuit breaker for {provider} transitioning to half-open")
            return False
        return True
    if state["state"] == "half-open":
        return False
    return False


def _record_success(provider: str):
    state = _get_circuit_state(provider)
    if state["state"] == "half-open":
        logger.info(f"Circuit breaker for {provider} recovered, closing")
    state["state"] = "closed"
    state["failures"] = 0


def _record_failure(provider: str):
    state = _get_circuit_state(provider)
    state["failures"] += 1
    state["last_failure_time"] = time.time()
    if state["failures"] >= state["failure_threshold"]:
        state["state"] = "open"
        logger.warning(f"Circuit breaker for {provider} opened after {state['failures']} failures")


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=60, limits=httpx.Limits(max_keepalive_connections=10, max_connections=20))
    return _http_client


def _normalize_prompt(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _cache_key(prompt: str, model: str, temperature: float, max_tokens: int) -> str:
    raw = f"{prompt}|{model}|{temperature}|{max_tokens}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(key: str) -> Optional[str]:
    if key in _llm_cache:
        resp, ts = _llm_cache[key]
        if time.time() - ts < _CACHE_TTL:
            return resp
        del _llm_cache[key]
    return None


def _set_cache(key: str, response: str):
    if len(_llm_cache) >= _MAX_CACHE_SIZE:
        oldest = min(_llm_cache.keys(), key=lambda k: _llm_cache[k][1])
        del _llm_cache[oldest]
    _llm_cache[key] = (response, time.time())


async def call_llm(prompt: str, max_tokens: int = 1000, temperature: float = 0.1, response_json: bool = True, model_override: Optional[str] = None) -> Optional[str]:
    providers = []

    if settings.groq_api_key:
        providers.append(("groq", lambda p, mt, t, to: _call_groq(p, mt, t, to, model_override)))
    if settings.openrouter_api_key:
        providers.append(("openrouter", lambda p, mt, t, to: _call_openrouter(p, mt, t, to, model_override)))
    if settings.openai_api_key:
        providers.append(("openai", lambda p, mt, t, to: _call_openai(p, mt, t, to, model_override)))

    if not providers:
        return None

    prompt = _normalize_prompt(prompt)

    cache_key = _cache_key(prompt, str(model_override), temperature, max_tokens)
    cached = _get_cached(cache_key)
    if cached:
        return cached

    for name, func in providers:
        if _is_circuit_open(name):
            logger.warning(f"Circuit breaker open for {name}, skipping")
            continue
        for attempt in range(3):
            try:
                timeout = min(30 + attempt * 30, 120)
                content = await func(prompt, max_tokens, temperature, timeout)
                if content:
                    _record_success(name)
                    _set_cache(cache_key, content)
                    return content
                logger.warning(f"{name} returned empty on attempt {attempt+1}")
            except Exception as e:
                logger.warning(f"{name} failed on attempt {attempt+1}: {e}")
                if attempt == 2:
                    _record_failure(name)
            if attempt < 2:
                await asyncio.sleep(1 + attempt * 3)
    return None


async def _call_groq(prompt: str, max_tokens: int, temperature: float, timeout: int, model_override: Optional[str] = None) -> Optional[str]:
    client = _get_client()
    model = model_override or "llama-3.3-70b-versatile"
    try:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"Groq {resp.status_code}: {resp.text[:200]}")
    except Exception:
        pass
    return None


async def _call_openrouter(prompt: str, max_tokens: int, temperature: float, timeout: int, model_override: Optional[str] = None) -> Optional[str]:
    client = _get_client()
    model = model_override or settings.openrouter_model
    try:
        resp = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/clearlens",
                "X-Title": "ClearLens",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"OpenRouter {resp.status_code}: {resp.text[:200]}")
    except Exception:
        pass
    return None


async def _call_openai(prompt: str, max_tokens: int, temperature: float, timeout: int, model_override: Optional[str] = None) -> Optional[str]:
    client = _get_client()
    model = model_override or "gpt-4o-mini"
    try:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"OpenAI {resp.status_code}: {resp.text[:200]}")
    except Exception:
        pass
    return None


def parse_json_response(content: str) -> Optional[dict]:
    if not content:
        return None
    try:
        cleaned = content.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(cleaned)
    except Exception:
        return None
