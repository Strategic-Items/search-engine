import httpx
import pytest

from search_engine.config import Settings
from search_engine.search import rewrite as rewrite_module
from search_engine.search.rewrite import rewrite_query


def answering(monkeypatch, text: str) -> None:
    monkeypatch.setattr(rewrite_module, "generate", lambda *a, **k: text)


def test_a_rewrite_that_reaches_the_document_wording_is_kept(monkeypatch):
    answering(monkeypatch, "  수출자 서약서 폐지 개정안\n")
    assert rewrite_query("업체의 약속 문서를 없애려는 변경안", Settings()) == "수출자 서약서 폐지 개정안"


@pytest.mark.parametrize("reply", [
    "",
    "   ",
    "<think>고민</think>",
    "```python\nprint()\n```",
    "설명 " * 100,
])
def test_the_ways_a_small_model_fails_are_discarded(monkeypatch, reply):
    """A rejected rewrite leaves the original question, which already searches."""
    answering(monkeypatch, reply)
    assert rewrite_query("수출허가 신청 서류", Settings()) is None


def test_thinking_tags_are_stripped_before_the_answer_is_judged(monkeypatch):
    answering(monkeypatch, "<think>어떤 말이 좋을까</think>\n전략물자 수출허가 신청서류")
    assert rewrite_query("수출허가 서류", Settings()) == "전략물자 수출허가 신청서류"


def test_a_rewrite_identical_to_the_question_is_not_worth_a_second_search(monkeypatch):
    answering(monkeypatch, "수출허가 신청 서류")
    assert rewrite_query("수출허가 신청 서류", Settings()) is None


def test_an_empty_query_is_never_sent_to_the_model(monkeypatch):
    called = []
    monkeypatch.setattr(rewrite_module, "generate", lambda *a, **k: called.append(1))
    assert rewrite_query("   ", Settings()) is None
    assert not called


def test_the_model_being_unreachable_is_raised_for_the_caller_to_decide(monkeypatch):
    def refuse(*a, **k):
        raise httpx.ConnectError("no chat server")
    monkeypatch.setattr(rewrite_module, "generate", refuse)
    with pytest.raises(httpx.HTTPError):
        rewrite_query("수출허가 신청 서류", Settings())
