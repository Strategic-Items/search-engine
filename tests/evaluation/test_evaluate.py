import json
from pathlib import Path

import pytest

from search_engine.evaluation.evaluate import (
    evaluate,
    hit_at,
    indexed_ids,
    load_queries,
    quality_metrics,
    precision_at,
    ranked_ids,
)


def write_queries(tmp_path: Path, *rows: dict) -> Path:
    path = tmp_path / "queries.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_gold_is_read_in_the_unit_each_category_uses():
    result = {
        "hits": [{"parent_id": "doc-1"}, {"parent_id": "doc-2"}],
        "hsk": {"total": 1, "hits": [{"id": "hsk-9"}]},
    }
    assert ranked_ids(result, "faq_legacy") == ["doc-1", "doc-2"]
    assert ranked_ids(result, "hsk") == ["hsk-9"]


def test_a_query_without_hsk_linkage_ranks_nothing_for_the_hsk_category():
    assert ranked_ids({"hits": [{"parent_id": "doc-1"}], "hsk": None}, "hsk") == []


def test_any_gold_inside_the_cutoff_counts_as_answered():
    assert hit_at(["a", "b", "c"], ["c"], 5)
    assert not hit_at(["a", "b", "c"], ["c"], 2)
    assert hit_at(["a"], ["z", "a"], 1)
    assert not hit_at([], ["a"], 5)


def test_precision_uses_k_slots_and_counts_duplicate_parents_once():
    assert precision_at(["a", "a", "x", "b", "y", "c"], ["a", "b", "c"], 5) == .4
    assert precision_at(["a"], ["a"], 5) == .2
    assert precision_at([], ["a"], 5) == 0
    with pytest.raises(ValueError):
        precision_at(["a"], ["a"], 0)


def test_precision_and_mrr_average_queries_including_misses():
    metrics = quality_metrics([
        {"returned": ["x", "a", "b"], "gold": ["a", "b"]},
        {"returned": [], "gold": ["c"]},
    ], 5)
    assert metrics["precision_at_5"] == .2
    assert metrics["precision_at_1"] == 0
    assert metrics["mrr_at_5"] == .25


def test_precision_at_one_matches_first_result_accuracy():
    metrics = quality_metrics([
        {"returned": ["a", "x"], "gold": ["a"]},
        {"returned": ["x", "b"], "gold": ["b"]},
        {"returned": [], "gold": ["c"]},
    ], 5)
    assert metrics["precision_at_1"] == pytest.approx(1 / 3)
    assert metrics["precision_at_1"] == metrics["hit_at_1"]


def test_queries_without_gold_are_refused(tmp_path: Path):
    path = write_queries(tmp_path, {"qid": "q1", "query": "허가", "gold": []})
    with pytest.raises(ValueError, match="without gold"):
        load_queries(path)


def test_an_unsupported_gold_unit_is_refused(tmp_path: Path):
    path = write_queries(tmp_path, {"qid": "q1", "query": "허가", "gold": ["doc-1"],
                                    "gold_unit": "chunk_id"})
    with pytest.raises(ValueError, match="unsupported gold unit"):
        load_queries(path)


def test_indexed_ids_covers_documents_and_their_parents(tmp_path: Path):
    (tmp_path / "core.jsonl").write_text(
        json.dumps({"id": "chunk-1", "parent_id": "doc-1"}) + "\n", encoding="utf-8")
    (tmp_path / "hsk.jsonl").write_text(
        json.dumps({"id": "hsk-1"}) + "\n", encoding="utf-8")
    assert indexed_ids(tmp_path) == {"chunk-1", "doc-1", "hsk-1"}


def test_a_gold_document_that_was_never_indexed_is_reported_separately(tmp_path, monkeypatch):
    (tmp_path / "core.jsonl").write_text(
        json.dumps({"id": "doc-1", "parent_id": "doc-1"}) + "\n", encoding="utf-8")
    (tmp_path / "hsk.jsonl").write_text("", encoding="utf-8")
    queries = [
        {"qid": "q1", "query": "있는 문서", "gold": ["doc-1"], "category": "faq_legacy"},
        {"qid": "q2", "query": "없는 문서", "gold": ["doc-404"], "category": "faq_legacy"},
    ]
    monkeypatch.setattr("search_engine.evaluation.evaluate.search",
                        lambda *a, **kw: {"hits": [{"parent_id": "doc-1"}], "hsk": None})

    report = evaluate(queries, "http://127.0.0.1:8092", tmp_path)

    assert report["totals"]["first"] == 1
    assert report["totals"]["gold_missing_from_index"] == 1
    assert [entry["gold_indexed"] for entry in report["queries"]] == [True, False]


def test_scores_are_grouped_by_category(tmp_path, monkeypatch):
    queries = [
        {"qid": "q1", "query": "a", "gold": ["doc-1"], "category": "guide"},
        {"qid": "q2", "query": "b", "gold": ["doc-9"], "category": "form"},
    ]
    monkeypatch.setattr("search_engine.evaluation.evaluate.search", lambda *a, **kw: {
        "hits": [{"parent_id": "doc-2"}, {"parent_id": "doc-1"}], "hsk": None})

    report = evaluate(queries, "http://127.0.0.1:8092", tmp_path)

    assert report["categories"]["guide"] == {
        "queries": 1, "first": 0, "top_k": 1, "gold_missing_from_index": 0}
    assert report["categories"]["form"]["top_k"] == 0


def test_the_answerable_subset_excludes_gold_that_never_reached_the_index(tmp_path, monkeypatch):
    (tmp_path / "core.jsonl").write_text(
        json.dumps({"id": "doc-1", "parent_id": "doc-1"}) + "\n", encoding="utf-8")
    (tmp_path / "hsk.jsonl").write_text("", encoding="utf-8")
    queries = [
        {"qid": "q1", "query": "a", "gold": ["doc-1"], "category": "faq_legacy"},
        {"qid": "q2", "query": "b", "gold": ["doc-404"], "category": "faq_legacy"},
    ]
    monkeypatch.setattr("search_engine.evaluation.evaluate.search",
                        lambda *a, **kw: {"hits": [{"parent_id": "doc-1"}], "hsk": None})

    report = evaluate(queries, "http://127.0.0.1:8092", tmp_path)

    assert report["totals"]["queries"] == 2
    assert report["answerable"] == {"queries": 1, "first": 1, "top_k": 1}


def test_empty_docs_file_is_known_empty_coverage(tmp_path, monkeypatch):
    (tmp_path / "docs.jsonl").write_text("")
    monkeypatch.setattr("search_engine.evaluation.evaluate.search", lambda *a, **kw: {"hits": []})
    report = evaluate([{"qid": "q", "query": "q", "gold": ["a"]}], "http://example", tmp_path)
    assert report["coverage_known"]
    assert report["queries"][0]["gold_missing_ids"] == ["a"]
    assert report["totals"]["gold_missing_from_index"] == 1


def test_partial_gold_coverage_is_not_fully_answerable(tmp_path, monkeypatch):
    (tmp_path / "docs.jsonl").write_text(json.dumps({"id": "a", "parent_id": "a"}))
    monkeypatch.setattr("search_engine.evaluation.evaluate.search", lambda *a, **kw: {
        "hits": [{"parent_id": "a"}]})
    report = evaluate([{"qid": "q", "query": "q", "gold": ["a", "b"]}], "http://example", tmp_path)
    assert report["metrics"]["recall_at_5"] == .5
    assert not report["queries"][0]["gold_indexed"]
    assert report["queries"][0]["gold_missing_ids"] == ["b"]


def test_api_cutoff_above_five_is_refused(tmp_path):
    with pytest.raises(ValueError, match="at most 5"):
        evaluate([{"qid": "q", "query": "q", "gold": ["a"]}], "http://example", tmp_path, k=10)


@pytest.mark.parametrize("gold", ["a", [""], [1]])
def test_malformed_gold_is_refused(tmp_path, gold):
    with pytest.raises(ValueError, match="list of IDs"):
        load_queries(write_queries(tmp_path, {"qid": "q", "query": "q", "gold": gold}))


def test_duplicate_query_ids_are_refused(tmp_path):
    row = {"qid": "q", "query": "q", "gold": ["a"]}
    with pytest.raises(ValueError, match="duplicate qid"):
        load_queries(write_queries(tmp_path, row, row))


@pytest.mark.parametrize("groups", [[], [[]], "a", [[1]], [[""]]])
def test_malformed_gold_groups_are_refused(tmp_path, groups):
    row = {"qid": "q", "query": "q", "gold": ["a"], "gold_groups": groups}
    with pytest.raises(ValueError, match="nonempty groups"):
        load_queries(write_queries(tmp_path, row))


@pytest.mark.parametrize("groups", [[["a"], ["a"]], [["b"]]])
def test_groups_must_partition_gold(tmp_path, groups):
    row = {"qid": "q", "query": "q", "gold": ["a"], "gold_groups": groups}
    with pytest.raises(ValueError, match="partition gold"):
        load_queries(write_queries(tmp_path, row))


def test_http_evaluation_scores_actual_evidence_chunks(tmp_path, monkeypatch):
    monkeypatch.setattr("search_engine.evaluation.evaluate.search", lambda *a, **kw: {
        "hits": [{"id": "a#0", "parent_id": "a"}]})
    report = evaluate([{"qid": "q", "query": "q", "gold": ["a"],
                        "gold_groups": [["a"]], "evidence_groups": [["a#0"], ["a#1"]]}],
                      "http://example", tmp_path)
    assert report["metrics"]["group_recall_at_5"] == 1
    assert report["metrics"]["evidence_recall_at_5"] == .5


def test_k_cuts_on_documents_even_when_each_carries_several_chunks():
    """More chunks per document must widen the evidence window, never narrow it."""
    rows = [{
        "qid": "q1", "gold": ["doc-1"], "returned": ["doc-1", "doc-2"],
        "returned_chunks": [["c1", "c2", "c3", "c4"], ["c9"]],
        "evidence_groups": [["c4"]],
    }]
    metrics = quality_metrics(rows, 1)
    assert metrics["evidence_recall_at_1"] == 1.0
    assert metrics["evidence_all_at_1"] == 1.0


def test_a_single_chunk_per_document_still_measures_the_same_way():
    rows = [{
        "qid": "q1", "gold": ["doc-1"], "returned": ["doc-1", "doc-2"],
        "returned_chunks": [["c1"], ["c9"]],
        "evidence_groups": [["c4"]],
    }]
    assert quality_metrics(rows, 2)["evidence_recall_at_2"] == 0.0
