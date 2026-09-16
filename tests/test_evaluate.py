import json
from pathlib import Path

import pytest

from search_engine.evaluate import (
    evaluate,
    hit_at,
    indexed_ids,
    load_queries,
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
    monkeypatch.setattr("search_engine.evaluate.search",
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
    monkeypatch.setattr("search_engine.evaluate.search", lambda *a, **kw: {
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
    monkeypatch.setattr("search_engine.evaluate.search",
                        lambda *a, **kw: {"hits": [{"parent_id": "doc-1"}], "hsk": None})

    report = evaluate(queries, "http://127.0.0.1:8092", tmp_path)

    assert report["totals"]["queries"] == 2
    assert report["answerable"] == {"queries": 1, "first": 1, "top_k": 1}
