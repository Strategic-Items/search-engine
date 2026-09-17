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


OPENAI = dict(chat_provider="openai", chat_base_url_override="http://spark.test/v1",
              chat_model_override="qwen3-vl-30b-a3b")


def serving(monkeypatch, handler):
    """Point both the async and the sync client at a mock transport."""
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(llm.httpx, "AsyncClient",
                        lambda **kwargs: original(transport=transport, **kwargs))
    monkeypatch.setattr(llm.httpx, "post",
                        lambda url, **kwargs: httpx.Client(transport=transport).post(url, **kwargs))


async def test_stream_chat_reads_openai_server_sent_events(monkeypatch):
    body = (
        'data: {"choices":[{"delta":{"content":"안녕"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"하세요"}}]}\n\n'
        "data: [DONE]\n\n"
    ).encode()
    serving(monkeypatch, lambda request: httpx.Response(200, content=body))
    monkeypatch.setattr(llm, "get_settings", lambda: Settings(**OPENAI))

    assert [chunk async for chunk in llm.stream_chat("prompt")] == ["안녕", "하세요"]


async def test_the_openai_path_posts_to_chat_completions_without_doubling_v1(monkeypatch):
    seen = {}

    def record(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, content=b"data: [DONE]\n\n")

    serving(monkeypatch, record)
    monkeypatch.setattr(llm, "get_settings", lambda: Settings(**OPENAI, chat_api_key="none"))

    assert [chunk async for chunk in llm.stream_chat("prompt", temperature=0.0)] == []
    assert seen["url"] == "http://spark.test/v1/chat/completions"
    assert seen["body"]["model"] == "qwen3-vl-30b-a3b"
    assert seen["body"]["temperature"] == 0.0
    # num_ctx has no OpenAI equivalent; the server fixes the window at startup.
    assert "options" not in seen["body"]
    assert seen["auth"] == "Bearer none"


def test_generate_reads_a_non_streamed_openai_reply(monkeypatch):
    serving(monkeypatch, lambda request: httpx.Response(
        200, json={"choices": [{"message": {"content": "수출자 서약서"}}]}))

    assert llm.generate("prompt", settings=Settings(**OPENAI)) == "수출자 서약서"


def test_generate_reads_a_non_streamed_ollama_reply(monkeypatch):
    seen = {}

    def record(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"message": {"content": "수출자 서약서"}})

    serving(monkeypatch, record)
    settings = Settings(ollama_base_url="http://ollama.test")

    assert llm.generate("prompt", max_tokens=64, settings=settings) == "수출자 서약서"
    assert seen["url"] == "http://ollama.test/api/chat"
    assert seen["options"]["num_predict"] == 64
    assert seen["stream"] is False


def test_the_provider_defaults_to_the_ollama_settings(monkeypatch):
    settings = Settings(ollama_base_url="http://ollama.test", ollama_chat_model="qwen2.5:3b")
    assert settings.chat_base_url == "http://ollama.test"
    assert settings.chat_model == "qwen2.5:3b"
