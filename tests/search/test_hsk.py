from unittest.mock import Mock

from search_engine.search.hsk import build_hsk_query, extract_hsk_code, retrieve_hsk


def test_extract_hsk_code_accepts_compact_and_separated_codes():
    assert extract_hsk_code("2826902000") == "2826902000"
    assert extract_hsk_code("HSK 2826-9020-00 확인") == "2826902000"
    assert extract_hsk_code("통제번호 1A001") is None


def test_hsk_query_preserves_leading_zero_and_normalizes_control():
    query = build_hsk_query("0123456789", "1A001.")
    assert query["bool"]["filter"] == [
        {"term": {"hsk_code": "0123456789"}},
        {"term": {"control_no_norm": "1a001"}},
    ]


def test_hsk_search_returns_linkage_notice():
    client = Mock()
    client.search.return_value = {"hits": {"total": {"value": 1}, "hits": [
        {"_id": "hsk-1", "_source": {
            "hsk_code": "0123456789", "control_number": "1A001.",
            "linkage_notice": "possible linkage",
        }},
    ]}}
    result = retrieve_hsk(client, "search-hsk", "0123456789", None, 50)
    assert result.total == 1
    assert result.hits[0].linkage_notice == "possible linkage"
    assert client.search.call_args.kwargs["index"] == "search-hsk"
