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
    """한 번 실행에서는 사용 가능해 보였지만 재현되지 않았다.

정확한 거절은 약 0.10에, 잘못된 거절은 약 0.85에 돌아왔으며, 이는 거짓 거절률을 14.8%에서 2.2%로 낮추었을 것이다. 그러나 같은 쿼리가 같은 패스워드에서 실행되었을 때, 한 번은 0.10, 다음 번에는 0.85가 나왔는데, 이는 제공되는 모델의 출력이 요청이 배치되는 방식에 따라 변하기 때문이다. 판결은 모든 반복에서 안정적이었으므로, 오직 판결만 읽는다.
    """
    for confidence in (0.0, 0.1, 0.85, 0.95):
        with judging(json.dumps({"answerable": False, "confidence": confidence, "reason": ""})):
            assert is_unanswerable("질문", [hit()], Settings()) is True


def test_an_answerable_verdict_keeps_the_results():
    with judging(json.dumps({"answerable": True, "confidence": 0.0, "reason": ""})):
        assert is_unanswerable("질문", [hit()], Settings()) is False


@pytest.mark.parametrize("reply", ["", "not json", json.dumps({"confidence": 0.0})])
def test_an_unreadable_verdict_keeps_the_results(reply):
    """대답하지 않은 판사는 판결이 아니다."""
    with judging(reply):
        assert is_unanswerable("질문", [hit()], Settings()) is False


def test_an_unreachable_judge_keeps_the_results():
    """이미 무언가를 찾은 검색은 두 번째 의견에서 실패해서는 안 된다."""
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
    """컨텍스트를 세 번째로 줄이면 거짓 거절이 135개 중 26개에서 51개로 증가했다:
    증거는 종종 문서를 순위 매긴 청크 밖에 위치해 있다."""
    seen = {}

    def capture(prompt, **kwargs):
        seen["prompt"] = prompt
        return json.dumps({"answerable": True, "confidence": 0.9, "reason": ""})

    with patch("search_engine.search.answerability.generate", capture):
        is_unanswerable("질문", [hit(body="본문", passages=("증거 문장",))], Settings())
    assert "증거 문장" in seen["prompt"]
