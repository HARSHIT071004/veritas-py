import json
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger("clearlens.llm")


async def call_llm(prompt: str, max_tokens: int = 1000, temperature: float = 0.1, response_json: bool = True) -> Optional[str]:
    if settings.openrouter_api_key:
        return await _call_openrouter(prompt, max_tokens, temperature)
    if settings.openai_api_key:
        return await _call_openai(prompt, max_tokens, temperature)
    return None


async def _call_openrouter(prompt: str, max_tokens: int, temperature: float) -> Optional[str]:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/clearlens",
                    "X-Title": "ClearLens",
                },
                json={
                    "model": settings.openrouter_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            logger.error(f"OpenRouter {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"OpenRouter call failed: {e}")
    return None


async def _call_openai(prompt: str, max_tokens: int, temperature: float) -> Optional[str]:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
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
