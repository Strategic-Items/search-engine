"""Chat client. Two wire protocols behind one interface.

CHAT_PROVIDER picks between Ollama's native API and any OpenAI-compatible
server (vLLM, SGLang, llama.cpp, LM Studio). Swap provider, base URL and model
in .env, not here.

The embedding model deliberately stays on Ollama whichever provider is chosen:
the index mapping fixes the vector width, so moving embeddings means a reindex
of every dataset, and a chat server generally does not serve bge-m3 anyway.
"""

import json
from collections.abc import AsyncIterator

import httpx

from search_engine.config import Settings, get_settings


def _ollama_payload(settings: Settings, prompt: str, temperature: float,
                    max_tokens: int | None, stream: bool) -> dict:
    options = {
        "temperature": temperature,
        # Ollama defaults this low and then silently truncates the front of an
        # over-long prompt -- the grounding rules -- rather than failing.
        "num_ctx": settings.ollama_num_ctx,
    }
    if max_tokens is not None:
        options["num_predict"] = max_tokens
    return {
        "model": settings.chat_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": stream,
        "options": options,
    }


def _openai_payload(settings: Settings, prompt: str, temperature: float,
                    max_tokens: int | None, stream: bool) -> dict:
    # No num_ctx equivalent: the context window is fixed when the server starts
    # (vLLM's --max-model-len), so an over-long prompt errors instead of being
    # silently cut. Size the window there to match OLLAMA_NUM_CTX or above.
    payload = {
        "model": settings.chat_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": stream,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    return payload


def _request(settings: Settings, prompt: str, temperature: float,
             max_tokens: int | None, stream: bool) -> tuple[str, dict, dict]:
    """URL, JSON body and headers for one call to the configured provider."""
    base = settings.chat_base_url.rstrip("/")
    if settings.chat_provider == "openai":
        headers = {"Authorization": f"Bearer {settings.chat_api_key}"}
        url = f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
        return url, _openai_payload(settings, prompt, temperature, max_tokens, stream), headers
    return (f"{base}/api/chat",
            _ollama_payload(settings, prompt, temperature, max_tokens, stream), {})


def _content(settings: Settings, line: str) -> tuple[str, bool]:
    """One streamed line as (text, done). Empty text for a line carrying none."""
    if settings.chat_provider == "openai":
        # Server-sent events: `data: {...}`, terminated by `data: [DONE]`.
        if not line.startswith("data:"):
            return "", False
        data = line[len("data:"):].strip()
        if data == "[DONE]":
            return "", True
        chunk = json.loads(data)
        choices = chunk.get("choices") or [{}]
        return (choices[0].get("delta", {}).get("content") or ""), False
    chunk = json.loads(line)
    return (chunk.get("message", {}).get("content") or ""), bool(chunk.get("done"))


def _answer(settings: Settings, body: dict) -> str:
    """The text of a non-streamed reply."""
    if settings.chat_provider == "openai":
        choices = body.get("choices") or [{}]
        return choices[0].get("message", {}).get("content") or ""
    return body.get("message", {}).get("content") or ""


async def stream_chat(prompt: str, temperature: float | None = None) -> AsyncIterator[str]:
    settings = get_settings()
    # `or` would swallow an explicit 0.0, which is what compression asks for.
    temp = settings.ollama_temperature if temperature is None else temperature
    url, payload, headers = _request(settings, prompt, temp, None, stream=True)
    async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                content, done = _content(settings, line)
                if content:
                    yield content
                if done:
                    break


async def complete(prompt: str, temperature: float = 0.0) -> str:
    """Non-streaming call, used for query compression."""
    parts = [chunk async for chunk in stream_chat(prompt, temperature=temperature)]
    return "".join(parts)


def generate(prompt: str, temperature: float = 0.0, max_tokens: int | None = None,
             settings: Settings | None = None) -> str:
    """Blocking single-shot completion, for the synchronous search path.

    Raises httpx.HTTPError if the model is unreachable; the caller decides
    whether that should degrade its work or fail it.
    """
    settings = settings or get_settings()
    url, payload, headers = _request(settings, prompt, temperature, max_tokens, stream=False)
    response = httpx.post(url, json=payload, headers=headers,
                          timeout=settings.ollama_timeout_seconds)
    response.raise_for_status()
    return _answer(settings, response.json())
