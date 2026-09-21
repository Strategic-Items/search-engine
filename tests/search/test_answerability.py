import json
from unittest.mock import patch

import pytest

from search_engine.config import Settings
from search_engine.search.answerability import is_unanswerable
from search_engine.search.results import Passage, SearchHit


def hit(title="공고문", body="본문", passages=()):
    return SearchHit(id="c1", parent_id="d1", title=title, body=body,
                     passages=[Passage(id=f"p{i}", body=b) for i, b in enumerate(passages)])


def judging(reply):
    return patch("search_engine.search.answerability.generate", lambda *a, **k: reply)


def test_the_confidence_the_model_reports_is_ignored():
    """It looked usable in one run and did not reproduce.

    Correct refusals came back near 0.10 and mistaken ones near 0.85, which
    would have cut false rejections from 14.8% to 2.2% -- but the same query
    over the same passages returned 0.10 in one run and 0.85 in the next, since
    the served model's output moves with how requests are batched. The verdict
    was stable across every repeat, so only the verdict is read.
    """
    for confidence in (0.0, 0.1, 0.85, 0.95):
        with judging(json.dumps({"answerable": False, "confidence": confidence, "reason": ""})):
            assert is_unanswerable("질문", [hit()], Settings()) is True


def test_an_answerable_verdict_keeps_the_results():
    with judging(json.dumps({"answerable": True, "confidence": 0.0, "reason": ""})):
        assert is_unanswerable("질문", [hit()], Settings()) is False


@pytest.mark.parametrize("reply", ["", "not json", json.dumps({"confidence": 0.0})])
def test_an_unreadable_verdict_keeps_the_results(reply):
    """A judge that did not answer is not a verdict."""
    with judging(reply):
        assert is_unanswerable("질문", [hit()], Settings()) is False


def test_an_unreachable_judge_keeps_the_results():
    """A search that already found something must not fail on a second opinion."""
    def boom(*args, **kwargs):
        raise RuntimeError("chat model down")

    with patch("search_engine.search.answerability.generate", boom):
        assert is_unanswerable("질문", [hit()], Settings()) is False


def test_nothing_retrieved_is_not_sent_to_the_judge():
    def boom(*args, **kwargs):
        raise AssertionError("judge called with no hits")

    with patch("search_engine.search.answerability.generate", boom):
        assert is_unanswerable("질문", [], Settings()) is False


def test_the_judge_sees_the_passages_not_just_the_ranked_chunk():
    """Cutting the context to a third took false rejections from 26 to 51 of 135:
    the evidence often sits outside the chunk that ranked the document."""
    seen = {}

    def capture(prompt, **kwargs):
        seen["prompt"] = prompt
        return json.dumps({"answerable": True, "confidence": 0.9, "reason": ""})

    with patch("search_engine.search.answerability.generate", capture):
        is_unanswerable("질문", [hit(body="본문", passages=("증거 문장",))], Settings())
    assert "증거 문장" in seen["prompt"]
