from unittest.mock import patch

import pytest

from search_engine.config import Settings
from search_engine.search.rerank import select_passages
from search_engine.search.results import Passage, SearchHit


def candidate(chunk_id, body):
    return {"_id": chunk_id, "_source": {"body": body}, "_score": 1.0}


def hit(**kwargs):
    return SearchHit.model_validate(
        {"id": "c0", "parent_id": "p", "title": "제목", "body": "본문0", **kwargs})


def respond(payload, status=200):
    class Response:
        def json(self):
            return payload

        def raise_for_status(self):
            if status >= 400:
                raise RuntimeError(status)

    return Response()


POOL = {"p": [candidate(f"c{i}", f"본문{i}") for i in range(8)]}


class TestSelectPassages:
    def test_selects_from_the_whole_pool_not_the_carried_chunks(self):
        # 증거는 풀의 7번째 위치에 있다 -- 여섯 개의 절단을 넘은 곳
        scores = [0.0] * 8
        scores[7] = 9.0
        with patch("httpx.post", return_value=respond(scores)):
            hits = [hit()]
            assert select_passages("질문", hits, POOL, 6, Settings()) is True
        assert hits[0].id == "c7"
        assert hits[0].chunk_ids[0] == "c7"

    def test_promotes_the_best_chunk_over_the_one_ranking_chose(self):
        scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.9]
        with patch("httpx.post", return_value=respond(scores)):
            hits = [hit()]
            select_passages("질문", hits, POOL, 3, Settings())
        assert hits[0].id == "c7" and hits[0].body == "본문7"
        assert [p.id for p in hits[0].passages] == ["c6", "c5"]

    def test_carries_exactly_chunks_per_document(self):
        with patch("httpx.post", return_value=respond([float(i) for i in range(8)])):
            hits = [hit()]
            select_passages("질문", hits, POOL, 4, Settings())
        assert len(hits[0].chunk_ids) == 4

    def test_scores_every_document_in_one_request(self):
        pool = {"p": POOL["p"], "q": [candidate("d0", "다0"), candidate("d1", "다1")]}
        hits = [hit(), hit(id="d0", parent_id="q", body="다0")]
        with patch("httpx.post", return_value=respond([1.0] * 10)) as post:
            select_passages("질문", hits, pool, 6, Settings())
        assert post.call_count == 1
        assert len(post.call_args.kwargs["json"]["documents"]) == 10

    def test_accepts_the_index_score_shape(self):
        payload = {"results": [{"index": i, "score": float(i)} for i in range(8)]}
        with patch("httpx.post", return_value=respond(payload)):
            hits = [hit()]
            select_passages("질문", hits, POOL, 2, Settings())
        assert hits[0].id == "c7"

    def test_depth_caps_the_pool(self):
        settings = Settings(search_rerank_depth=3)
        with patch("httpx.post", return_value=respond([0.1, 0.9, 0.2])) as post:
            hits = [hit()]
            select_passages("질문", hits, POOL, 3, settings)
        assert len(post.call_args.kwargs["json"]["documents"]) == 3
        assert hits[0].id == "c1"

    def test_reports_failure_so_the_caller_can_fall_back(self):
        with patch("httpx.post", side_effect=OSError("refused")):
            hits = [hit()]
            assert select_passages("질문", hits, POOL, 6, Settings()) is False
        assert hits[0].id == "c0" and hits[0].passages == []

    def test_reports_failure_when_the_sidecar_miscounts(self):
        with patch("httpx.post", return_value=respond([0.9])):
            hits = [hit()]
            assert select_passages("질문", hits, POOL, 6, Settings()) is False

    def test_no_hits_is_not_a_request(self):
        with patch("httpx.post") as post:
            assert select_passages("질문", [], {}, 6, Settings()) is True
        post.assert_not_called()


class TestSettings:
    def test_off_by_default(self):
        assert Settings().search_rerank_chunks is False

    def test_depth_must_leave_something_to_compare(self):
        with pytest.raises(ValueError):
            Settings(search_rerank_depth=1)
