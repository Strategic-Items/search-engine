from unittest.mock import Mock

from fastapi.testclient import TestClient
from opensearchpy import ConnectionError

from search_engine.api import app


def test_search_rejects_blank_query():
    client = TestClient(app)
    assert client.post("/v1/search", json={"query": " "}).status_code == 422


def test_search_returns_hits_from_alias(monkeypatch):
    os_client = Mock()
    os_client.search.return_value = {"hits": {"hits": [
        {"_id": "faq-1", "_score": 3.0, "_source": {"title": "허가", "body": "본문"}},
    ]}}
    monkeypatch.setattr("search_engine.api.routes.create_client", lambda: os_client)

    response = TestClient(app).post("/v1/search", json={"query": "허가"})

    assert response.status_code == 200
    assert response.json()["hits"][0]["id"] == "faq-1"
    assert os_client.search.call_args.kwargs["index"] == "search-documents,search-docs"


def test_search_includes_hsk_linkage_for_an_hsk_code_query(monkeypatch):
    os_client = Mock()
    os_client.search.side_effect = [
        {"hits": {"hits": []}},
        {"hits": {"total": {"value": 1}, "hits": [{
            "_id": "hsk-1", "_source": {"hsk_code": "2826902000", "control_number": "1A001"},
        }]}},
    ]
    monkeypatch.setattr("search_engine.api.routes.create_client", lambda: os_client)

    response = TestClient(app).post(
        "/v1/search", json={"query": "HSK 2826-9020-00"},
    )

    assert response.status_code == 200
    assert response.json()["hsk"]["hits"][0]["control_number"] == "1A001"
    assert [call.kwargs["index"] for call in os_client.search.call_args_list] == [
        "search-documents,search-docs", "search-hsk",
    ]


def test_search_tolerates_a_corpus_that_has_never_been_indexed(monkeypatch):
    """A document index only exists once something has been indexed into it."""
    os_client = Mock()
    os_client.search.return_value = {"hits": {"hits": []}}
    monkeypatch.setattr("search_engine.api.routes.create_client", lambda: os_client)

    response = TestClient(app).post("/v1/search", json={"query": "허가"})

    assert response.status_code == 200
    assert os_client.search.call_args.kwargs["ignore_unavailable"] is True


def test_a_cluster_failure_is_reported_as_a_temporary_failure(monkeypatch):
    os_client = Mock()
    os_client.search.side_effect = ConnectionError("no route to cluster")
    monkeypatch.setattr("search_engine.api.routes.create_client", lambda: os_client)

    response = TestClient(app).post("/v1/search", json={"query": "허가"})

    assert response.status_code == 503


def test_readiness_follows_the_cluster(monkeypatch):
    os_client = Mock()
    monkeypatch.setattr("search_engine.api.routes.create_client", lambda: os_client)

    os_client.ping.return_value = True
    assert TestClient(app).get("/health/ready").status_code == 200

    os_client.ping.return_value = False
    assert TestClient(app).get("/health/ready").status_code == 503
