"""Ollama chat client. Swap the base URL/model in .env, not here."""

import json
from collections.abc import AsyncIterator

import httpx

from search_engine.config import get_settings


async def stream_chat(prompt: str, temperature: float | None = None) -> AsyncIterator[str]:
    settings = get_settings()
    payload = {
        "model": settings.ollama_chat_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "options": {
            # `or` would swallow an explicit 0.0, which is what compression asks for.
            "temperature": settings.ollama_temperature if temperature is None else temperature,
        },
    }
    async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
        async with client.stream(
            "POST", f"{settings.ollama_base_url}/api/chat", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
                if chunk.get("done"):
                    break


async def complete(prompt: str, temperature: float = 0.0) -> str:
    """Non-streaming call, used for query compression."""
    parts = [chunk async for chunk in stream_chat(prompt, temperature=temperature)]
    return "".join(parts)
