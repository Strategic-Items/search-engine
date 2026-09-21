from collections import Counter
from unittest.mock import Mock

from fastapi.testclient import TestClient
from opensearchpy import ConnectionError

from search_engine.api import app


def test_search_rejects_blank_query():
    client = TestClient(app)
    assert client.post("/v1/search", json={"query": " "}).status_code == 422


def test_evaluation_questions_include_answerable_and_abstention_cases():
    body = TestClient(app).get("/v1/evaluation/questions").json()

    groups = Counter(row["group"] for row in body["questions"])
    assert body["total"] == sum(groups.values())
    assert sum(row["answerable"] for row in body["questions"]) == groups["answerable"] == 135
    assert groups["unanswerable"] >= 8
    assert {row["group"] for row in body["questions"]} == {
        "answerable", "unanswerable", "out_of_domain",
    }


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


def test_callcenter_search_uses_only_its_dedicated_alias(monkeypatch):
    os_client = Mock()
    os_client.search.return_value = {"hits": {"hits": [
        {"_id": "sg01#c0", "_score": 3.0, "_source": {
            "parent_id": "sg01", "title": "콜센터 상담 사례 · 판정", "body": "상담 내용",
            "call_id": "sg01", "categories": ["판정"],
        }},
    ]}}
    monkeypatch.setattr("search_engine.api.routes.create_client", lambda: os_client)

    response = TestClient(app).post("/v1/callcenter/search", json={"query": "공작기계 판정"})

    assert response.status_code == 200
    assert response.json()["hits"][0]["call_id"] == "sg01"
    assert os_client.search.call_args.kwargs["index"] == "search-callcenter"


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


def test_document_returns_every_chunk_in_order(monkeypatch):
    os_client = Mock()
    os_client.search.return_value = {"hits": {"hits": [
        {"_id": "gong-1#0001", "_source": {
            "parent_id": "gong-1", "title": "공고문", "source_type": "공고문", "body": "가. 목적",
        }},
        {"_id": "gong-1#0002", "_source": {"parent_id": "gong-1", "body": "나. 지원내용"}},
    ]}}
    monkeypatch.setattr("search_engine.api.routes.create_client", lambda: os_client)

    response = TestClient(app).get("/v1/documents/gong-1")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "공고문"
    assert [chunk["id"] for chunk in body["chunks"]] == ["gong-1#0001", "gong-1#0002"]
    assert os_client.search.call_args.kwargs["body"]["sort"] == [{"id": "asc"}]


def test_document_reports_a_parent_that_is_not_indexed(monkeypatch):
    os_client = Mock()
    os_client.search.return_value = {"hits": {"hits": []}}
    monkeypatch.setattr("search_engine.api.routes.create_client", lambda: os_client)

    assert TestClient(app).get("/v1/documents/absent").status_code == 404


def test_document_reads_an_id_that_contains_a_slash(monkeypatch):
    """Parent ids are built from source paths, so some carry a separator."""
    os_client = Mock()
    os_client.search.return_value = {"hits": {"hits": [
        {"_id": "hwpx/공고.hwpx#0001", "_source": {"parent_id": "hwpx/공고.hwpx", "body": "본문"}},
    ]}}
    monkeypatch.setattr("search_engine.api.routes.create_client", lambda: os_client)

    response = TestClient(app).get("/v1/documents/hwpx/공고.hwpx")

    assert response.status_code == 200
    assert response.json()["parent_id"] == "hwpx/공고.hwpx"
