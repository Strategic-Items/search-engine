"""채팅 클라이언트. 하나의 인터페이스 뒤에 두 가지 와이어 프로토콜.

CHAT_PROVIDER는 Ollama의 네이티브 API와 OpenAI와 호환되는 서버(vLLM, SGLang, llama.cpp, LM Studio) 사이에서 선택한다. 여기가 아닌 .env에서 프로바이더, 기본 URL, 모델을 변경하라.

임베딩 모델은 선택된 프로바이더에 관계없이 의도적으로 Ollama에 남아 있다: 인덱스 매핑은 벡터의 너비를 고정하므로 임베딩을 이동하면 모든 데이터셋을 다시 인덱싱해야 하며, 일반적으로 채팅 서버는 bge-m3을 제공하지 않는다.
"""

import json
from collections.abc import AsyncIterator

import httpx

from search_engine.config import Settings, get_settings


def _messages(prompt: str, system: str | None) -> list[dict]:
    """주어진 경우 시스템 턴. 모델들이 이를 다르게 따르기 때문이다.

규칙을 사용자 턴에 접목하는 것은 동등하지 않다: 응답 가능성 판별기는 규칙을 별도의 턴에 둘 때 14.8%에 비해 20.7%의 응답 가능한 질문을 거부했다.
"""
    messages = [{"role": "user", "content": prompt}]
    if system:
        messages.insert(0, {"role": "system", "content": system})
    return messages


def _ollama_payload(settings: Settings, prompt: str, temperature: float,
                    max_tokens: int | None, stream: bool,
                    system: str | None = None, json_object: bool = False) -> dict:
    options = {
        "temperature": temperature,
        # Ollama는 이 값을 낮게 설정하고 긴 프롬프트의 앞부분을 조용히 잘라낸다.
        # 지지 규칙에 따라, 실패하는 대신 조용히 잘라낸다.
        "num_ctx": settings.ollama_num_ctx,
    }
    if max_tokens is not None:
        options["num_predict"] = max_tokens
    payload = {
        "model": settings.chat_model,
        "messages": _messages(prompt, system),
        "stream": stream,
        "options": options,
    }
    if json_object:
        payload["format"] = "json"
    return payload


def _openai_payload(settings: Settings, prompt: str, temperature: float,
                    max_tokens: int | None, stream: bool,
                    system: str | None = None, json_object: bool = False) -> dict:
# num_ctx와 같은 것 없음: 서버 시작 시 컨텍스트 창이 고정됨
# (vLLM의 --max-model-len), 따라서 긴 프롬프트는 조용히 잘리기보다 오류를 발생시킨다.
# OLLAMA_NUM_CTX 또는 그 이상과 일치하도록 창 크기를 설정하라.
    payload = {
        "model": settings.chat_model,
        "messages": _messages(prompt, system),
        "stream": stream,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if json_object:
        payload["response_format"] = {"type": "json_object"}
    return payload


def _request(settings: Settings, prompt: str, temperature: float,
             max_tokens: int | None, stream: bool,
             system: str | None = None, json_object: bool = False) -> tuple[str, dict, dict]:
    """설정된 제공자에 대한 하나의 호출에 대한 URL, JSON 본문 및 헤더."""
    base = settings.chat_base_url.rstrip("/")
    if settings.chat_provider == "openai":
        headers = {"Authorization": f"Bearer {settings.chat_api_key}"}
        url = f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
        return url, _openai_payload(settings, prompt, temperature, max_tokens, stream,
                                    system, json_object), headers
    return (f"{base}/api/chat",
            _ollama_payload(settings, prompt, temperature, max_tokens, stream,
                            system, json_object), {})


def _content(settings: Settings, line: str) -> tuple[str, bool]:
    """스트리밍된 한 줄을 (텍스트, 완료 여부)로 반환. 텍스트가 없는 경우 빈 문자열."""
    if settings.chat_provider == "openai":
        # 서버 전송 이벤트: `data: {...}`, `data: [DONE]`로 종료.
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
    """비스트리밍 응답의 텍스트."""
    if settings.chat_provider == "openai":
        choices = body.get("choices") or [{}]
        return choices[0].get("message", {}).get("content") or ""
    return body.get("message", {}).get("content") or ""


async def stream_chat(prompt: str, temperature: float | None = None) -> AsyncIterator[str]:
    settings = get_settings()
# `or`는 명시적인 0.0을 흡수할 수 있는데, 이는 압축이 요구하는 것이다.
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
    """쿼리 압축을 위해 사용하는 비스트리밍 호출."""
    parts = [chunk async for chunk in stream_chat(prompt, temperature=temperature)]
    return "".join(parts)


def generate(prompt: str, temperature: float = 0.0, max_tokens: int | None = None,
             settings: Settings | None = None, *, system: str | None = None,
             json_object: bool = False) -> str:
    """블로킹 단일샷 완성, 동기 검색 경로를 위한.

    모델에 접근할 수 없을 경우 httpx.HTTPError를 발생시킨다; 호출자는
    이 상황이 작업을 저하시켜야 하는지 아니면 실패해야 하는지를 결정한다.
    """
    settings = settings or get_settings()
    url, payload, headers = _request(settings, prompt, temperature, max_tokens,
                                     stream=False, system=system, json_object=json_object)
    response = httpx.post(url, json=payload, headers=headers,
                          timeout=settings.ollama_timeout_seconds)
    response.raise_for_status()
    return _answer(settings, response.json())
