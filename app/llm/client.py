import json
import asyncio
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger("clearlens.llm")


async def call_llm(prompt: str, max_tokens: int = 1000, temperature: float = 0.1, response_json: bool = True) -> Optional[str]:
    providers = []

    if settings.groq_api_key:
        providers.append(("groq", _call_groq))
    if settings.openrouter_api_key:
        providers.append(("openrouter", _call_openrouter))
    if settings.openai_api_key:
        providers.append(("openai", _call_openai))

    if not providers:
        return None

    for name, func in providers:
        for attempt in range(3):
            try:
                timeout = min(30 + attempt * 30, 120)
                content = await func(prompt, max_tokens, temperature, timeout)
                if content:
                    return content
                logger.warning(f"{name} returned empty on attempt {attempt+1}")
            except Exception as e:
                logger.warning(f"{name} failed on attempt {attempt+1}: {e}")
            if attempt < 2:
                await asyncio.sleep(1 + attempt * 3)
    return None


async def _call_groq(prompt: str, max_tokens: int, temperature: float, timeout: int) -> Optional[str]:
    import httpx
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        logger.error(f"Groq {resp.status_code}: {resp.text[:200]}")
    return None


async def _call_openrouter(prompt: str, max_tokens: int, temperature: float, timeout: int) -> Optional[str]:
    import httpx
    async with httpx.AsyncClient(timeout=timeout) as client:
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
    return None


async def _call_openai(prompt: str, max_tokens: int, temperature: float, timeout: int) -> Optional[str]:
    import httpx
    async with httpx.AsyncClient(timeout=timeout) as client:
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
        logger.error(f"OpenAI {resp.status_code}: {resp.text[:200]}")
    return None


def parse_json_response(content: str) -> Optional[dict]:
    if not content:
        return None
    try:
        cleaned = content.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(cleaned)
    except Exception:
        return None
