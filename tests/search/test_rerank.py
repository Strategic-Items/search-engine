from unittest.mock import patch

import pytest

from search_engine.config import Settings
from search_engine.search.rerank import rerank_passages
from search_engine.search.results import Passage, SearchHit


def hit(**kwargs):
    return SearchHit.model_validate({
        "id": "c0", "parent_id": "p", "title": "제목", "body": "본문0",
        "passages": [Passage(id="c1", body="본문1"), Passage(id="c2", body="본문2")],
        **kwargs,
    })


def respond(payload, status=200):
    class Response:
        def json(self):
            return payload

        def raise_for_status(self):
            if status >= 400:
                raise RuntimeError(status)

    return Response()


class TestRerankPassages:
    def test_orders_passages_by_score(self):
        # the document's own body scores worst, so both passages move ahead of it
        with patch("httpx.post", return_value=respond([0.1, 0.2, 0.9])):
            hits = rerank_passages("질문", [hit()], Settings())
        assert [p.id for p in hits[0].passages] == ["c2", "c1"]

    def test_accepts_the_index_score_shape(self):
        with patch("httpx.post", return_value=respond(
                {"results": [{"index": 0, "score": 0.1},
                             {"index": 1, "score": 0.9},
                             {"index": 2, "score": 0.2}]})):
            hits = rerank_passages("질문", [hit()], Settings())
        assert [p.id for p in hits[0].passages] == ["c1", "c2"]

    def test_keeps_order_when_the_sidecar_is_unreachable(self):
        with patch("httpx.post", side_effect=OSError("refused")):
            hits = rerank_passages("질문", [hit()], Settings())
        assert [p.id for p in hits[0].passages] == ["c1", "c2"]

    def test_keeps_order_when_the_sidecar_miscounts(self):
        with patch("httpx.post", return_value=respond([0.9])):
            hits = rerank_passages("질문", [hit()], Settings())
        assert [p.id for p in hits[0].passages] == ["c1", "c2"]

    def test_scores_only_up_to_the_depth_and_keeps_the_tail(self):
        passages = [Passage(id=f"c{i}", body=f"본문{i}") for i in range(1, 5)]
        settings = Settings(search_rerank_depth=3)
        with patch("httpx.post", return_value=respond([0.1, 0.2, 0.9])) as post:
            hits = rerank_passages("질문", [hit(passages=passages)], settings)
        assert len(post.call_args.kwargs["json"]["documents"]) == 3
        # c2 and c1 are reordered; c3 and c4 were never scored and keep their order
        assert [p.id for p in hits[0].passages] == ["c2", "c1", "c3", "c4"]

    def test_leaves_a_document_with_no_extra_chunks_alone(self):
        with patch("httpx.post") as post:
            rerank_passages("질문", [hit(passages=[])], Settings())
        post.assert_not_called()

    def test_no_hits_is_not_a_request(self):
        with patch("httpx.post") as post:
            assert rerank_passages("질문", [], Settings()) == []
        post.assert_not_called()


class TestSettings:
    def test_off_by_default(self):
        assert Settings().search_rerank_chunks is False

    def test_depth_must_leave_something_to_compare(self):
        with pytest.raises(ValueError):
            Settings(search_rerank_depth=1)
