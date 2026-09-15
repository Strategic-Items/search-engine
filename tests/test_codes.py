from datetime import date

from search_engine.documents import SearchDocument
from search_engine.search import build_query


def test_multiple_legal_codes_are_indexed_separately_and_exactly_queryable():
    source = SearchDocument(
        id="notice-1", title="고시 개정", code="제18조의3 제20조 1A001.",
    ).index_source()
    assert source["codes_exact"] == ["제18조의3", "제20조", "1a001"]
    query = build_query("", "제18조의3", date(2026, 9, 15), [])
    assert query["bool"]["should"] == [
        {"term": {"codes_exact": {"value": "제18조의3", "boost": 6}}},
    ]
