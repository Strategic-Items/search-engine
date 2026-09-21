from search_engine.rag import guardrail
from search_engine.search.results import Passage, SearchHit


def test_empty_context_skips_model_prompt():
    assert guardrail.build_prompt("자가판정", []) is None
    assert "yesTrade" in guardrail.EMPTY_CONTEXT_ANSWER


def test_context_preserves_search_metadata_instead_of_generic_label():
    prompt = guardrail.build_prompt("서식", [SearchHit(
        id="form-1", parent_id="form-1", source_type="민원서식", title="신청서",
        body="본문", effective_from="2025-01-01", source_url="https://example.test/form",
        superseded_by="form-2",
    )])

    assert "민원서식" in prompt
    assert "검색 자료" not in prompt
    assert "시행일 2025-01-01" in prompt
    assert "대체됨: form-2" in prompt


def test_passages_of_one_document_are_kept_apart():
    """문서의 두 조각은 인접한 텍스트가 아니므로, 함께 연결되지 않는다."""
    hit = SearchHit(
        id="c1", parent_id="doc-1", title="공고", body="첫 부분", source_type="공고",
        passages=[Passage(id="c2", body="뒷 부분")],
    )
    context = guardrail.format_documents([hit])
    assert context.count("[공고 · 공고 · 시행일 확인 필요]") == 1
    assert "첫 부분" in context and "뒷 부분" in context
    assert guardrail.PASSAGE_SEPARATOR in context
