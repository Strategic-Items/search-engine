from datetime import date
from unittest.mock import Mock

from search_engine.search import build_query, retrieve


def test_query_keeps_unknown_dates_and_filters_expired_documents():
    query = build_query("수출허가", "5d002", date(2026, 9, 15), ["notice"])
    filters = query["bool"]["filter"]
    assert filters[0]["bool"]["should"][0]["range"]["effective_from"]["lte"] == "2026-09-15"
    assert filters[1]["bool"]["should"][0]["range"]["effective_to"]["gt"] == "2026-09-15"
    assert filters[0]["bool"]["should"][1]["bool"]["must_not"]["exists"]["field"] == "effective_from"
    assert filters[2] == {"terms": {"source_type": ["notice"]}}
    assert query["bool"]["should"][1]["term"]["code_norm"]["value"] == "5D002"


def test_retrieve_returns_unique_parent_documents():
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "chunk-1", "_score": 8.0, "_source": {"parent_id": "doc-1", "title": "A"}},
        {"_id": "chunk-2", "_score": 7.0, "_source": {"parent_id": "doc-1", "title": "A"}},
        {"_id": "doc-2", "_score": 6.0, "_source": {"title": "B"}},
    ]}}
    hits = retrieve(client, "search-documents", "수출허가", None, date.today(), [], 2)
    assert [hit["parent_id"] for hit in hits] == ["doc-1", "doc-2"]
    assert client.search.call_args.kwargs["size"] == 10
