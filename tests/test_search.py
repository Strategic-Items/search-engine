from datetime import date
from unittest.mock import Mock

from search_engine.search import build_query, retrieve, search_all


def test_query_keeps_unknown_dates_and_filters_expired_documents():
    query = build_query("수출허가", date(2026, 9, 15))
    filters = query["bool"]["filter"]
    assert filters[0]["bool"]["should"][0]["range"]["effective_from"]["lte"] == "2026-09-15"
    assert filters[1]["bool"]["should"][0]["range"]["effective_to"]["gt"] == "2026-09-15"
    assert filters[0]["bool"]["should"][1]["bool"]["must_not"]["exists"]["field"] == "effective_from"


def test_retrieve_returns_unique_parent_documents():
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "chunk-1", "_score": 8.0, "_source": {"parent_id": "doc-1", "title": "A"}},
        {"_id": "chunk-2", "_score": 7.0, "_source": {"parent_id": "doc-1", "title": "A"}},
        {"_id": "doc-2", "_score": 6.0, "_source": {"title": "B"}},
    ]}}
    hits = retrieve(client, "search-documents", "수출허가", date.today(), 2)
    assert [hit.parent_id for hit in hits] == ["doc-1", "doc-2"]
    assert client.search.call_args.kwargs["size"] == 10


def test_explicit_year_month_boosts_matching_publication_and_effective_dates():
    query = build_query("2026년 9월 개정 전문판정 신청서", date(2026, 9, 15))
    scored = query["function_score"]
    assert scored["query"]["bool"]["minimum_should_match"] == 1
    assert scored["functions"][0]["filter"]["range"]["published_at"] == {
        "gte": "2026-09-01", "lt": "2026-10-01",
    }


def test_a_whole_year_and_an_impossible_month_are_read_correctly():
    whole_year = build_query("2026년 개정", date(2026, 9, 15))
    assert whole_year["function_score"]["functions"][0]["filter"]["range"]["published_at"] == {
        "gte": "2026-01-01", "lt": "2027-01-01",
    }
    assert "function_score" not in build_query("2026년 13월 개정", date(2026, 9, 15))


def test_search_all_adds_hsk_linkage_only_when_the_query_names_a_code():
    client = Mock()
    client.search.return_value = {"hits": {"hits": []}}
    assert search_all(client, "search-documents", "search-hsk", "허가", date.today()).hsk is None

    client.search.side_effect = [
        {"hits": {"hits": []}},
        {"hits": {"total": {"value": 1}, "hits": [
            {"_id": "hsk-1", "_source": {"hsk_code": "2826902000"}},
        ]}},
    ]
    result = search_all(client, "search-documents", "search-hsk", "HSK 2826-9020-00", date.today())
    assert result.hsk.hits[0].hsk_code == "2826902000"
    assert [call.kwargs["index"] for call in client.search.call_args_list[-2:]] == [
        "search-documents", "search-hsk",
    ]
