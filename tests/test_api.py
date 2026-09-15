from unittest.mock import Mock

from fastapi.testclient import TestClient

from search_engine.api import app
from search_engine.config import Settings


def test_search_requires_api_key_and_rejects_blank_query(monkeypatch):
    monkeypatch.setattr("search_engine.api.get_settings", lambda: Settings(search_api_key="secret"))
    client = TestClient(app)
    assert client.post("/v1/search", json={"query": "허가"}).status_code == 401
    assert client.post("/v1/search", headers={"X-API-Key": "wrong"},
                       json={"query": "허가"}).status_code == 401
    assert client.post("/v1/search", headers={"X-API-Key": "secret"},
                       json={"query": " "}).status_code == 422


def test_search_returns_hits_from_alias(monkeypatch):
    monkeypatch.setattr("search_engine.api.get_settings", lambda: Settings(search_api_key="secret"))
    os_client = Mock()
    os_client.search.return_value = {"hits": {"hits": [
        {"_id": "faq-1", "_score": 3.0, "_source": {"title": "허가", "body": "본문"}},
    ]}}
    monkeypatch.setattr("search_engine.api.create_client", lambda: os_client)
    response = TestClient(app).post("/v1/search", headers={"X-API-Key": "secret"},
                                    json={"query": "허가"})
    assert response.status_code == 200
    assert response.json()["hits"][0]["id"] == "faq-1"
    assert os_client.search.call_args.kwargs["index"] == "search-documents"


def test_hsk_api_rejects_non_numeric_code_and_blank_control(monkeypatch):
    monkeypatch.setattr("search_engine.api.get_settings", lambda: Settings(search_api_key="secret"))
    client = TestClient(app)
    headers = {"X-API-Key": "secret"}
    assert client.post("/v1/hsk/search", headers=headers,
                       json={"hsk_code": "123"}).status_code == 422
    assert client.post("/v1/hsk/search", headers=headers,
                       json={"control_number": " . "}).status_code == 422
