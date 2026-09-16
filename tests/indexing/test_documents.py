from search_engine.indexing.documents import SearchDocument


def test_multiple_legal_codes_are_indexed_separately():
    source = SearchDocument(
        id="notice-1", title="고시 개정", code="제18조의3 제20조 1A001.",
    ).index_source()
    assert source["codes_exact"] == ["제18조의3", "제20조", "1a001"]
