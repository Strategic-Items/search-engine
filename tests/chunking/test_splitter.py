"""`unstructured-doc-parser_ver2`의 `tests/test_chunker.py`를 그대로 옮겼다 -- 이식한 `splitter.py`가
파서의 `chunker.py`와 같은 동작을 내는지 확인한다([설계](../../docs/design/chunking_ownership_move.md))."""

from search_engine.chunking.splitter import chunk_markdown

_SAMPLE_MD = """## 전략물자 판정기준 해석 세부지침

**제1조(목적)** 이 지침은 「대외무역법」에서 위임된 사항을 정함을 목적으로 한다.

**제2조(정의)** 본 지침에서 판정기준 해석이란 """ + ("다음과 같다. " * 40) + """

1. 첫 번째 항목에 대한 설명이다.
2. 두 번째 항목에 대한 설명이다.

| 통제번호 | 개정 전 | 개정 후 |
| --- | --- | --- |
| 3A001 | <신규> | 신경회로망 집적회로 |
"""


def test_chunks_stay_within_size_budget():
    chunks = chunk_markdown(_SAMPLE_MD, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 1
    # overlap 때문에 청크가 chunk_size를 다소 넘을 수 있지만 무한정 커지면 안 된다.
    assert all(len(c.text) <= 400 for c in chunks)


def test_no_tiny_orphan_chunks():
    chunks = chunk_markdown(_SAMPLE_MD, chunk_size=200, chunk_overlap=20, min_chunk_chars=30)
    assert all(len(c.text) >= 30 for c in chunks)


def test_heading_metadata_captured():
    chunks = chunk_markdown(_SAMPLE_MD, chunk_size=200, chunk_overlap=20)
    headings = [c.metadata.get("heading") for c in chunks if c.metadata.get("heading")]
    assert any("제1조" in h or "제2조" in h for h in headings)


def test_table_not_split_mid_row():
    chunks = chunk_markdown(_SAMPLE_MD, chunk_size=800, chunk_overlap=100)
    table_chunk = next(c for c in chunks if "3A001" in c.text)
    assert "| --- | --- | --- |" in table_chunk.text
