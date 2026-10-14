"""카테고리 검색의 SPLADE: 질의 모양, 모드, 청크 단위 hybrid, 설정이 없을 때의 BM25."""

from datetime import date
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from search_engine.api import app
from search_engine.config import Settings
from search_engine.search import CATEGORY_MODES, MODES, build_splade_query, retrieve
from search_engine.search.results import ModeComparison
from search_engine.sparse import TERM_PREFIX, sparse_enabled, sparse_terms

AS_OF = date(2026, 10, 6)


def hit(chunk_id, parent, score=1.0):
    return {"_id": chunk_id, "_score": score,
            "_source": {"parent_id": parent, "title": f"문서 {parent}", "body": f"본문 {chunk_id}"}}


def test_sparse_terms_keep_the_heaviest_terms_under_a_prefixed_key():
    terms = sparse_terms({7: 0.5, 9: 1.25, 3: 0.1}, top_terms=2)
    assert terms == {f"{TERM_PREFIX}9": 1.25, f"{TERM_PREFIX}7": 0.5}


def test_splade_query_scores_the_sparse_field_and_filters_by_validity():
    body = build_splade_query({"t1": 0.5}, AS_OF)
    assert body["bool"]["must"] == [{"neural_sparse": {"splade": {"query_tokens": {"t1": 0.5}}}}]
    assert len(body["bool"]["filter"]) == 2


def test_sparse_is_off_until_a_model_is_configured():
    assert not sparse_enabled(Settings(search_splade_model=""))
    assert sparse_enabled(Settings(search_splade_model="/models/splade-c"))


def test_splade_mode_searches_only_the_sparse_field():
    client = Mock()
    client.search.return_value = {"hits": {"hits": [hit("a#0", "A", 9.0), hit("b#0", "B", 8.9)]}}
    with patch("search_engine.search.query.encode_sparse_query", return_value={"t1": 1.0}) as encode:
        hits = retrieve(client, "search-admin", "멘토링", AS_OF, 5, mode="splade",
                        score_floor=0.0, answerability=False)
    encode.assert_called_once_with("멘토링")
    assert client.search.call_count == 1
    assert "neural_sparse" in client.search.call_args.kwargs["body"]["query"]["bool"]["must"][0]
    assert [h.parent_id for h in hits] == ["A", "B"]


def test_hybrid_with_splade_fuses_chunks_and_keeps_the_leader_of_each_list():
    client = Mock()
    sparse = [hit("a#0", "A"), hit("a#1", "A"), hit("b#0", "B")]
    dense = [hit("c#0", "C"), hit("a#0", "A"), hit("b#0", "B")]
    client.search.side_effect = [{"hits": {"hits": sparse}}, {"hits": {"hits": dense}}]
    embedder = Mock()
    embedder.embed_query.return_value = [0.1] * 4
    with patch("search_engine.search.query.encode_sparse_query", return_value={"t1": 1.0}):
        hits = retrieve(client, "search-admin", "멘토링", AS_OF, 5, embedder, mode="hybrid",
                        lexical="splade", chunk_first=True, chunk_first_cutoff_ratio=0.95,
                        score_floor=0.0, answerability=False)
    assert "neural_sparse" in client.search.call_args_list[0].kwargs["body"]["query"]["bool"]["must"][0]
    assert "knn" in client.search.call_args_list[1].kwargs["body"]["query"]
    # a#0은 두 목록에서 1·2위, c#0은 dense 1위라 컷오프 아래여도 1위 청크로 남는다.
    ids = [h.id for h in hits] + [p.id for h in hits for p in h.passages]
    assert "a#0" in ids and "c#0" in ids


def test_bm25_stays_the_default_lexical_retriever():
    client = Mock()
    client.search.return_value = {"hits": {"hits": [hit("a#0", "A")]}}
    with patch("search_engine.search.query.encode_sparse_query") as encode:
        retrieve(client, "search-documents", "질문", AS_OF, 3, mode="bm25",
                 score_floor=0.0, answerability=False, query_rewrite=False)
    encode.assert_not_called()
    assert "neural_sparse" not in str(client.search.call_args.kwargs["body"])


def test_unknown_lexical_retriever_is_rejected():
    with pytest.raises(ValueError):
        retrieve(Mock(), "a", "q", AS_OF, 3, lexical="other")


def category_compare(monkeypatch, model):
    seen = {}

    def fake_modes(client, alias, query, as_of, k, modes=MODES, **options):
        seen.update(modes=tuple(modes), options=options)
        return ModeComparison(query=query, modes=[])

    monkeypatch.setattr("search_engine.api.routes.create_client", lambda: Mock())
    monkeypatch.setattr("search_engine.api.routes.search_modes", fake_modes)
    monkeypatch.setattr("search_engine.api.routes.get_settings",
                        lambda: Settings(search_splade_model=model))
    response = TestClient(app).post("/v1/categories/admin/search/compare", json={"query": "멘토링"})
    assert response.status_code == 200
    return seen


def test_category_search_uses_splade_and_chunk_rrf_when_the_model_is_set(monkeypatch):
    seen = category_compare(monkeypatch, "/models/splade-c")
    assert seen["modes"] == CATEGORY_MODES
    assert seen["options"]["lexical"] == "splade"
    assert seen["options"]["chunk_first"] is True
    assert seen["options"]["chunk_first_cutoff_ratio"] == 0.7
    assert seen["options"]["chunk_first_dense_within_document"] is True
    assert seen["options"]["chunk_first_document_limits"] is False
    assert seen["options"]["chunk_first_single_modes"] is True


def test_category_hybrid_can_return_the_seventh_evidence_chunk_from_one_document():
    client = Mock()
    candidates = [hit(f"p#{i}", "p") for i in range(12)]
    client.search.side_effect = [{"hits": {"hits": candidates}}, {"hits": {"hits": candidates}}]
    embedder = Mock()
    embedder.embed_query.return_value = [0.1] * 4
    with patch("search_engine.search.query.encode_sparse_query", return_value={"t1": 1.0}):
        hits = retrieve(client, "search-admin", "멘토링", AS_OF, 5, embedder, mode="hybrid",
                        lexical="splade", chunk_first=True, chunk_first_cutoff_ratio=0.7,
                        chunk_first_dense_within_document=True, chunk_first_document_limits=False,
                        score_floor=0.0, answerability=False)
    assert len(hits) == 1
    assert hits[0].chunk_ids == [f"p#{i}" for i in range(10)]


def test_category_splade_uses_raw_score_cutoff_and_the_chunk_budget_without_a_document_cap():
    client = Mock()
    # 1위 점수 10.0의 0.7배 아래(6.9)는 자르고, 한 문서에 청크 열두 개가 있어도 예산 10개까지 싣는다
    candidates = [hit(f"p#{i}", "p", score=10.0 - i * 0.1) for i in range(12)]
    candidates += [hit("q#0", "q", score=6.0)]
    client.search.return_value = {"hits": {"hits": candidates}}
    with patch("search_engine.search.query.encode_sparse_query", return_value={"t1": 1.0}):
        hits = retrieve(client, "search-law", "전략물자", AS_OF, 5, mode="splade",
                        lexical="splade", chunk_first=True, chunk_first_cutoff_ratio=0.7,
                        chunk_first_document_limits=False, chunk_first_single_modes=True,
                        score_floor=0.0, answerability=False)
    chunks = [c for h in hits for c in h.chunk_ids]
    assert len(chunks) == 10
    assert "q#0" not in chunks


def test_category_hybrid_keeps_more_than_five_documents_without_expanding_candidates():
    client = Mock()
    candidates = [hit(f"p{i}#0", f"p{i}") for i in range(12)]
    client.search.side_effect = [{"hits": {"hits": candidates}}, {"hits": {"hits": candidates}}]
    embedder = Mock()
    embedder.embed_query.return_value = [0.1] * 4
    with patch("search_engine.search.query.encode_sparse_query", return_value={"t1": 1.0}):
        hits = retrieve(client, "search-admin", "멘토링", AS_OF, 5, embedder, mode="hybrid",
                        lexical="splade", chunk_first=True, chunk_first_cutoff_ratio=0.7,
                        chunk_first_dense_within_document=True, chunk_first_document_limits=False,
                        score_floor=0.0, answerability=False)
    assert len(hits) == 10
    assert [h.id for h in hits] == [f"p{i}#0" for i in range(10)]
    assert all(call.kwargs["size"] == 25 for call in client.search.call_args_list)


def test_category_search_falls_back_to_bm25_without_a_model(monkeypatch):
    seen = category_compare(monkeypatch, "")
    assert seen["modes"] == MODES
    assert "lexical" not in seen["options"]


def test_splade_query_carries_the_docket_filter_like_the_dense_query():
    body = build_splade_query({"t1": 0.5}, AS_OF, "공고 제2026-496호 개정이유")
    assert len(body["bool"]["filter"]) == 3
    clauses = body["bool"]["filter"][2]["bool"]["should"]
    assert {"match_phrase": {"body": "2026 496"}} in clauses
    assert {"term": {"doc_number_norm": "2026-496"}} in clauses


def test_docket_filter_names_the_whole_document_by_its_indexed_number():
    from search_engine.search.query import _docket_filter
    assert _docket_filter("개정이유를 알려줘") == []
    clauses = _docket_filter("제2011-275호")[0]["bool"]["should"]
    assert {"term": {"doc_number_norm": "2011-275"}} in clauses


def test_concurrent_queries_initialize_once_and_serialize_shared_gpu_model(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    import time
    from search_engine import sparse

    state = {'created': 0, 'active': 0}
    barrier = Barrier(2)

    class Encoder:
        def __init__(self):
            state['created'] += 1
            time.sleep(0.02)

        def encode_query(self, query):
            state['active'] += 1
            try:
                assert state['active'] == 1, 'Shared GPU model entered concurrently'
                time.sleep(0.02)
                return {'t1': 1.0}
            finally:
                state['active'] -= 1

    monkeypatch.setattr(sparse, 'SparseEncoder', Encoder)
    sparse._cached_encoder.cache_clear()
    sparse.encode_query.cache_clear()
    def run(query):
        barrier.wait()
        return sparse.encode_query(query)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, ['first', 'second']))
        assert state['created'] == 1
        assert results == [{'t1': 1.0}, {'t1': 1.0}]
    finally:
        sparse._cached_encoder.cache_clear()
        sparse.encode_query.cache_clear()


def test_category_compare_returns_one_chunk_per_result_in_score_order():
    from search_engine.api.routes import _one_chunk_per_result
    from search_engine.search.results import ModeComparison, ModeResults, Passage, SearchHit

    doc = SearchHit(id="a#0", parent_id="a", score=9.0, title="별표 19", body="첫 청크",
                    passages=[Passage(id="a#1", body="둘째", score=8.0),
                              Passage(id="a#2", body="셋째", score=7.5)])
    other = SearchHit(id="b#0", parent_id="b", score=8.5, title="다른 문서", body="다른 청크")
    comparison = ModeComparison(query="q", modes=[ModeResults(mode="splade", hits=[doc, other])])
    rows = _one_chunk_per_result(comparison).modes[0].hits
    assert [row.id for row in rows] == ["a#0", "b#0", "a#1", "a#2"]
    assert all(row.passages == [] for row in rows)
    assert [row.parent_id for row in rows] == ["a", "b", "a", "a"]
    assert rows[2].body == "둘째"
