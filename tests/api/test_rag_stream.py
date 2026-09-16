from unittest.mock import AsyncMock

import httpx
from fastapi.testclient import TestClient
from opensearchpy import ConnectionError

from search_engine.api import app
from search_engine.rag import llm, pipeline, retriever
from search_engine.rag.models import Message


def test_rag_accepts_requests_without_an_api_key(monkeypatch):
    monkeypatch.setattr(pipeline, "prepare_turn", AsyncMock(return_value=pipeline.Turn("허가", "s", None)))
    client = TestClient(app)
    assert client.post("/v1/rag/stream", json={"query": "허가"}).status_code == 200


def test_rag_frames_chunks_and_finishes(monkeypatch):
    monkeypatch.setattr(pipeline, "prepare_turn", AsyncMock(return_value=pipeline.Turn("허가", "s", "prompt")))

    async def chunks(prompt):
        yield "첫 줄\n둘째 줄"

    monkeypatch.setattr(llm, "stream_chat", chunks)
    response = TestClient(app).post("/v1/rag/stream", json={"query": "허가"})
    assert response.status_code == 200
    assert "data: 첫 줄\ndata: 둘째 줄" in response.text
    assert "event: done" in response.text


def test_rag_reports_search_failure_before_stream_headers(monkeypatch):
    monkeypatch.setattr(retriever, "retrieve", AsyncMock(side_effect=ConnectionError("down")))
    response = TestClient(app).post("/v1/rag/stream", json={"query": "허가"})
    assert response.status_code == 503


def test_rag_reports_ollama_failure_as_sse_error(monkeypatch):
    monkeypatch.setattr(pipeline, "prepare_turn", AsyncMock(return_value=pipeline.Turn("허가", "s", "prompt")))

    async def broken(prompt):
        raise httpx.ConnectError("down")
        yield "unreachable"

    monkeypatch.setattr(llm, "stream_chat", broken)
    response = TestClient(app).post("/v1/rag/stream", json={"query": "허가"})
    assert response.status_code == 200
    assert "event: error" in response.text
    assert "event: done" not in response.text
