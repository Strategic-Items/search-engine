from search_engine.rag import guardrail
from search_engine.search.results import SearchHit


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
