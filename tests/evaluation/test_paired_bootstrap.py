import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[2] / "scripts" / "paired_bootstrap.py"
SPEC = importlib.util.spec_from_file_location("paired_bootstrap", SCRIPT)
assert SPEC and SPEC.loader
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)

compare = bootstrap.compare
per_query = bootstrap.per_query


def row(qid, returned, gold, chunks, groups):
    return {"qid": qid, "returned": returned, "gold": gold,
            "returned_chunks": chunks, "evidence_groups": groups}


def test_per_query_counts_evidence_groups_within_k_documents():
    r = row("q", ["a", "b"], ["b"], [["a", "a#0"], ["b", "b#0"]], [["b#0"], ["c#0"]])
    assert per_query(r, 5) == {"first": 0.0, "evidence_recall": 0.5}
    assert per_query(r, 1)["evidence_recall"] == 0.0


def test_query_without_evidence_labels_is_skipped_for_recall():
    r = {"qid": "q", "returned": ["a"], "gold": ["a"]}
    assert per_query(r, 5) == {"first": 1.0, "evidence_recall": None}


def test_interval_excludes_zero_only_for_a_consistent_gain():
    def make(hit):
        return {f"q{i}": row(f"q{i}", ["a" if hit(i) else "x"], ["a"],
                             [["a#0" if hit(i) else "x#0"]], [["a#0"]]) for i in range(40)}
    before = make(lambda i: False)
    gain = compare(before, make(lambda i: i < 30), 5, 44)
    assert gain["first"]["excludes_zero"] and gain["first"]["delta"] == 0.75
    flat = compare(make(lambda i: i < 20), make(lambda i: i < 20), 5, 44)
    assert flat["first"]["delta"] == 0 and not flat["first"]["excludes_zero"]


def test_unpaired_qids_are_ignored_and_counted():
    a = {"q1": row("q1", ["a"], ["a"], [["a#0"]], [["a#0"]])}
    b = {**a, "q2": row("q2", ["a"], ["a"], [["a#0"]], [["a#0"]])}
    assert compare(a, b, 5, 44)["unpaired_qids_ignored"] == 1
