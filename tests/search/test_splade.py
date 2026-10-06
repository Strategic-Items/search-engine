"""카테고리 검색의 SPLADE: 질의 모양, 모드, 청크 단위 hybrid, 설정이 없을 때의 BM25."""

from datetime import date
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from search_engine.api import app
from search_engine.config import Settings
from search_engine.search import CATEGORY_MODES, MODES, build_splade_query, retrieve
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
        return {"query": query, "modes": []}

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
    assert seen["options"]["chunk_first_cutoff_ratio"] == 0.95


def test_category_search_falls_back_to_bm25_without_a_model(monkeypatch):
    seen = category_compare(monkeypatch, "")
    assert seen["modes"] == MODES
    assert "lexical" not in seen["options"]
