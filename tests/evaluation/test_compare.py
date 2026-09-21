import json
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from search_engine.evaluation.compare import compare, percentile, verify_corpus, verify_gold
from search_engine.evaluation.evaluate import indexed_ids, quality_metrics, recall_at, reciprocal_rank_at
from search_engine.search.query import retrieve
from search_engine.search.results import SearchHit
from datetime import date


def response(*parents, failed=0):
    return {"_shards": {"failed": failed}, "hits": {"hits": [
        {"_id": f"{p}#0", "_source": {"parent_id": p}} for p in parents
    ]}}


def test_recall_counts_all_gold_and_not_duplicate_hits():
    assert recall_at(["a", "a", "x"], ["a", "b", "b"], 5) == .5
    assert recall_at(["a", "b"], ["a", "b"], 1) == .5
    assert reciprocal_rank_at(["x", "a", "b"], ["a", "b"], 5) == .5
    assert reciprocal_rank_at(["x", "a"], ["a"], 1) == 0


def test_macro_and_micro_recall_differ():
    result = quality_metrics([
        {"returned": ["a"], "gold": ["a"]},
        {"returned": ["b"], "gold": ["b", "c", "d"]},
    ], 5)
    assert result["hit_at_5"] == 1
    assert result["recall_at_5"] == pytest.approx(2 / 3)
    assert result["micro_recall_at_5"] == .5


def test_docs_only_coverage(tmp_path):
    (tmp_path / "docs.jsonl").write_text(json.dumps({"id": "a#0", "parent_id": "a"}))
    assert indexed_ids(tmp_path) == {"a", "a#0"}


def test_bm25_never_constructs_an_embedder(monkeypatch):
    client = Mock()
    client.search.return_value = response("a", "b")
    embedder = Mock()
    hits = retrieve(client, "docs", "q", date.today(), 5, embedder, mode="bm25", strict=True)
    assert [h.parent_id for h in hits] == ["a", "b"]
    embedder.embed_query.assert_not_called()
    assert client.search.call_count == 1
    assert client.search.call_args.kwargs["ignore_unavailable"] is False


def test_vector_never_executes_lexical_query():
    client = Mock()
    client.search.return_value = response("b", "a")
    embedder = Mock()
    embedder.embed_query.return_value = [0.1] * 768
    hits = retrieve(client, "docs", "q", date.today(), 5, embedder, mode="vector", strict=True)
    assert [h.parent_id for h in hits] == ["b", "a"]
    assert client.search.call_count == 1
    assert "knn" in client.search.call_args.kwargs["body"]["query"]


@pytest.mark.parametrize("mode,strict,raises", [
    ("hybrid", False, False), ("hybrid", True, True), ("vector", False, True),
])
def test_embedding_outages_cannot_masquerade_as_vector_scores(mode, strict, raises):
    client = Mock()
    client.search.return_value = response("a")
    embedder = Mock()
    embedder.embed_query.side_effect = httpx.ConnectError("down")
    if raises:
        with pytest.raises(httpx.ConnectError):
            retrieve(client, "docs", "q", date.today(), 5, embedder, mode=mode, strict=strict)
    else:
        assert retrieve(client, "docs", "q", date.today(), 5, embedder, mode=mode)[0].parent_id == "a"


def test_strict_evaluation_refuses_failed_shards():
    client = Mock()
    client.search.return_value = response("a", failed=1)
    with pytest.raises(RuntimeError, match="incomplete"):
        retrieve(client, "docs", "q", date.today(), 5, mode="bm25", strict=True)


def test_comparison_uses_same_depth_rotates_modes_and_keeps_samples(monkeypatch):
    calls = []
    def fake(client, index, query, as_of, depth, **kwargs):
        calls.append((kwargs["mode"], depth, kwargs["strict"]))
        return [SearchHit(id="a#0", parent_id="a")]
    monkeypatch.setattr("search_engine.evaluation.compare.retrieve", fake)
    report = compare([{"qid": "q1", "query": "q", "gold": ["a", "b"]}],
                     Mock(), "docs", repeats=2, warmup=0)
    assert calls == [(m, 10, True) for m in ("bm25", "vector", "hybrid", "vector", "hybrid", "bm25")]
    assert report["modes"]["hybrid"]["metrics"]["5"]["recall_at_5"] == .5
    assert report["modes"]["hybrid"]["latency"]["samples"] == 2
    assert percentile([1, 2, 3, 4], .95) == 4


def test_verification_refuses_stale_index(tmp_path, monkeypatch):
    corpus = tmp_path / "docs.jsonl"
    corpus.write_text(json.dumps({"id": "a#0", "title": "a", "parent_id": "a", "content_hash": "new"}))
    client = Mock()
    client.indices.get.return_value = {"docs-v1": {}}
    client.indices.get_mapping.return_value = {"docs-v1": {"mappings": {"properties": {
        "embedding": {"type": "knn_vector", "dimension": 768},
    }}}}
    monkeypatch.setattr("search_engine.evaluation.compare.scan", lambda *a, **kw: [
        {"_id": "a#0", "_source": {"parent_id": "a", "content_hash": "old"}}])
    with pytest.raises(ValueError, match="differs"):
        verify_corpus(client, "docs", corpus)


def test_gold_set_is_source_reviewed_not_search_labeled():
    path = Path(__file__).resolve().parents[2] / "data/queries_docs_v1.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 50
    assert len({r["qid"] for r in rows}) == len(rows)
    assert any(len(r["gold"]) > 1 for r in rows)
    for row in rows:
        assert row["review_status"] == "assistant_source_reviewed"
        assert {e["parent_id"] for e in row["evidence"]} == set(row["gold"])
        assert all(e["quote"] and e["source_path"] for e in row["evidence"])


def test_strict_evaluation_refuses_timeout():
    client = Mock()
    client.search.return_value = {**response("a"), "timed_out": True}
    with pytest.raises(RuntimeError, match="incomplete"):
        retrieve(client, "docs", "q", date.today(), 5, mode="bm25", strict=True)


def test_bm25_keeps_original_score_and_best_chunk():
    client = Mock()
    r = response("a", "a", "b")
    for score, h in enumerate(r["hits"]["hits"], 10):
        h["_score"] = score
    client.search.return_value = r
    hits = retrieve(client, "docs", "q", date.today(), 5, mode="bm25")
    assert [h.parent_id for h in hits] == ["a", "b"]
    assert [h.score for h in hits] == [10, 12]


@pytest.mark.parametrize("kwargs", [{"repeats": 0}, {"warmup": -1}, {"ks": (0, 5)}, {"ks": (21,)}])
def test_comparison_rejects_invalid_arguments(kwargs):
    with pytest.raises(ValueError):
        compare([{"qid": "q", "query": "q", "gold": ["a"]}], Mock(), "docs", **kwargs)


def test_evidence_must_match_current_body(tmp_path):
    corpus = tmp_path / "docs.jsonl"
    corpus.write_text(json.dumps({"id": "a#0", "parent_id": "a", "source_path": "a.pdf", "body": "real quote"}))
    row = {"qid": "q", "gold": ["a"], "evidence": [{
        "parent_id": "a", "chunk_id": "a#0", "source_path": "a.pdf", "quote": "invented",
    }]}
    with pytest.raises(ValueError, match="does not match"):
        verify_gold([row], corpus, {"a"})
    row["evidence"][0]["quote"] = "real quote"
    verify_gold([row], corpus, {"a"})
    row["evidence"] = []
    with pytest.raises(ValueError, match="every gold parent"):
        verify_gold([row], corpus, {"a"})


def test_equivalent_parent_copies_count_as_one_logical_document():
    metrics = quality_metrics([{
        "gold": ["a-hwp", "a-pdf", "b"], "gold_groups": [["a-hwp", "a-pdf"], ["b"]],
        "returned": ["a-hwp", "a-pdf"],
    }], 5)
    assert metrics["recall_at_5"] == pytest.approx(2 / 3)
    assert metrics["group_recall_at_5"] == .5
    assert metrics["group_all_at_5"] == 0


def test_evidence_recall_counts_required_facts_not_all_alternative_chunks():
    metrics = quality_metrics([{
        "gold": ["a"], "returned": ["a"], "returned_chunks": ["a#1"],
        "evidence_groups": [["a#0", "a#1"], ["a#2"]],
    }], 5)
    assert metrics["recall_at_5"] == 1
    assert metrics["evidence_hit_at_5"] == 1
    assert metrics["evidence_recall_at_5"] == .5
    assert metrics["evidence_all_at_5"] == 0


def test_one_chunk_can_support_two_required_facts():
    metrics = quality_metrics([{
        "gold": ["a"], "returned": ["a"], "returned_chunks": ["a#1"],
        "evidence_groups": [["a#1"], ["a#1", "a#2"]],
    }], 5)
    assert metrics["evidence_recall_at_5"] == 1
    assert metrics["evidence_all_at_5"] == 1


def test_validate_only_does_not_connect_to_services(tmp_path, monkeypatch, capsys):
    from search_engine.evaluation.compare import main
    queries = tmp_path / "queries.jsonl"
    corpus = tmp_path / "docs.jsonl"
    corpus.write_text(json.dumps({"id": "a#0", "parent_id": "a", "source_path": "a.pdf", "body": "proof"}))
    queries.write_text(json.dumps({
        "qid": "q", "query": "question", "gold": ["a"], "evidence": [{
            "parent_id": "a", "chunk_id": "a#0", "source_path": "a.pdf", "quote": "proof",
        }],
    }))
    monkeypatch.setattr("sys.argv", ["search-compare", str(queries), "--corpus", str(corpus), "--validate-only"])
    client_factory = Mock(side_effect=AssertionError("service connection is forbidden"))
    monkeypatch.setattr("search_engine.evaluation.compare.create_client", client_factory)
    main()
    assert json.loads(capsys.readouterr().out)["search_executed"] is False
    client_factory.assert_not_called()


def test_v2_questions_have_answer_level_evidence():
    root = Path(__file__).resolve().parents[2]
    rows = [json.loads(line) for line in (root / "data/queries_docs_v2.jsonl").read_text().splitlines()]
    assert len(rows) == 135
    assert len({r["qid"] for r in rows}) == len(rows)
    assert {r["category"] for r in rows} == {
        "paraphrase", "scenario", "multi_evidence",
        # 식별자를 일부러 넣은 질의. 어휘 정확 일치 경로를 검증한다.
        "identifier_number", "identifier_article", "identifier_mixed"}
    for r in rows:
        assert r["reference_answer"] and r["human_review"] == "pending"
        assert r["evidence_requirements"]
        assert r["evidence_groups"] == [req["acceptable_chunk_ids"] for req in r["evidence_requirements"]]
        assert {p for group in r["gold_groups"] for p in group} == set(r["gold"])
        assert {e["parent_id"] for e in r["evidence"]} == set(r["gold"])


def test_negative_cases_are_separate_from_recall_denominator():
    root = Path(__file__).resolve().parents[2]
    rows = [json.loads(line) for line in (root / "data/queries_docs_v2_unanswerable.jsonl").read_text().splitlines()]
    manifest = json.loads((root / "data/queries_docs_v2.manifest.json").read_text())
    assert len(rows) == manifest["negative_queries"]
    assert all(not r["answerable"] and not r["gold"] and r["reason"] for r in rows)
