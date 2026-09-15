from datetime import date
from unittest.mock import Mock

from search_engine.search import (
    GUIDE_TYPES,
    SOURCE_TYPE_WEIGHT,
    build_query,
    retrieve,
    search_all,
)


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
    query = build_query("2026년 9월 개정 고시", date(2026, 9, 15))
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


def test_a_query_that_asks_for_a_procedure_lifts_the_guides():
    query = build_query("전문판정 신청은 어떤 절차로 진행되나요", date(2026, 9, 15))
    functions = query["function_score"]["functions"]
    assert functions[0]["filter"]["terms"]["source_type"] == list(GUIDE_TYPES)
    assert functions[0]["weight"] == SOURCE_TYPE_WEIGHT


def test_a_query_that_names_a_form_lifts_the_forms():
    query = build_query("최종사용자 서약서 양식 내려받기", date(2026, 9, 15))
    assert query["function_score"]["functions"][0]["filter"]["terms"]["source_type"] == ["민원서식"]


def test_the_word_in_a_notice_title_does_not_lift_the_guides():
    """`안내` is how notices title themselves, so it must not read as a guide."""
    query = build_query("제38차 전략물자 수출입고시 9월 1일 시행 안내", date(2026, 9, 15))
    boosted = [f["filter"] for f in query.get("function_score", {}).get("functions", [])]
    assert not any("source_type" in str(f) for f in boosted)


def test_a_plain_query_is_not_wrapped_in_a_score_function():
    assert "function_score" not in build_query("수출허가", date(2026, 9, 15))


def test_document_kind_and_period_boosts_apply_together():
    query = build_query("2026년 9월 개정 전문판정 신청서 양식", date(2026, 9, 15))
    functions = query["function_score"]["functions"]
    assert functions[0]["filter"]["terms"]["source_type"] == ["민원서식"]
    assert [f["filter"]["range"] for f in functions[1:]] == [
        {"published_at": {"gte": "2026-09-01", "lt": "2026-10-01"}},
        {"effective_from": {"gte": "2026-09-01", "lt": "2026-10-01"}},
    ]


def test_boosting_never_removes_a_document_from_the_result_set():
    """Boosts reorder what matched; they must not become filters."""
    query = build_query("전문판정 절차", date(2026, 9, 15))
    scored = query["function_score"]
    assert scored["boost_mode"] == "sum"
    assert scored["query"]["bool"]["minimum_should_match"] == 1
    assert "source_type" not in str(scored["query"]["bool"]["filter"])
