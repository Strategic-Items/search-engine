import json

import httpx

from search_engine.config import Settings
from search_engine.rag import llm


async def test_stream_chat_reads_ollama_ndjson(monkeypatch):
    body = (
        '{"message":{"content":"안녕"},"done":false}\n'
        '{"message":{"content":"하세요"},"done":true}\n'
    ).encode()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kwargs: original_client(
        transport=transport, **kwargs
    ))
    monkeypatch.setattr(llm, "get_settings", lambda: Settings(ollama_base_url="http://ollama.test"))

    assert [chunk async for chunk in llm.stream_chat("prompt")] == ["안녕", "하세요"]


async def test_an_explicit_zero_temperature_survives_instead_of_falling_back(monkeypatch):
    sent = {}

    def record(request: httpx.Request) -> httpx.Response:
        sent.update(json.loads(request.content))
        return httpx.Response(200, content=b'{"message":{"content":"x"},"done":true}\n')

    transport = httpx.MockTransport(record)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda **kwargs: original_client(
        transport=transport, **kwargs
    ))
    monkeypatch.setattr(llm, "get_settings",
                        lambda: Settings(ollama_base_url="http://ollama.test",
                                         ollama_temperature=0.4))

    await llm.complete("prompt", temperature=0.0)

    assert sent["options"]["temperature"] == 0.0
