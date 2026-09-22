import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "evaluate_splade_dense_fusion.py"
SPEC = importlib.util.spec_from_file_location("evaluate_splade_dense_fusion", SCRIPT)
assert SPEC and SPEC.loader
fusion = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fusion)

metrics = fusion.metrics
parent_ranking = fusion.parent_ranking
ratio_cut = fusion.ratio_cut
rrf = fusion.rrf
chunk_metrics = fusion.chunk_metrics


def test_parent_ranking_keeps_best_chunk_per_parent():
    hits = [
        {"_id": "a#0", "_score": 0.9, "_source": {"parent_id": "a"}},
        {"_id": "a#1", "_score": 0.8, "_source": {"parent_id": "a"}},
        {"_id": "b#0", "_score": 0.7, "_source": {"parent_id": "b"}},
    ]
    assert parent_ranking(hits) == [("a", 0.9), ("b", 0.7)]


def test_rrf_uses_dense_order_to_break_cross_list_tie():
    # a와 b는 각 목록에서 서로 1·2위라 RRF 점수가 같다. 운영 경로처럼 dense가 가른다.
    fused = rrf([("a", 2.0), ("b", 1.0)], [("b", 0.9), ("a", 0.8)], 60)
    assert [row["parent_id"] for row in fused] == ["b", "a"]
    assert all(row["leads"] for row in fused)


def test_ratio_cut_and_final_metrics_preserve_list_leaders():
    assert ratio_cut([("a", 10.0), ("b", 8.9)], 0.9) == [("a", 10.0)]
    rankings = [{
        "gold": ["b"],
        "ranked": [
            {"parent_id": "a", "score": 1.0, "leads": True},
            {"parent_id": "b", "score": 0.5, "leads": True},
            {"parent_id": "c", "score": 0.5, "leads": False},
        ],
    }]
    result = metrics(rankings, 0.9)
    assert result["hit_at_5"] == 1.0
    assert result["mean_returned"] == 2.0
    assert result["mrr_at_5"] == 0.5


def test_chunk_metrics_score_evidence_groups_and_report_judgment_coverage():
    rankings = [{
        "qid": "q1",
        "chunk_ranked": [
            {"chunk_id": "other"}, {"chunk_id": "answer"}, {"chunk_id": "unknown"},
        ],
    }]
    queries = {"q1": {"evidence_groups": [["answer", "equivalent"]]}}
    result = chunk_metrics(
        rankings, queries, {("q1", "other"): 0, ("q1", "answer"): 2}, k=3)

    assert result["evidence_hit_at_k"] == 1.0
    assert result["evidence_recall_at_k"] == 1.0
    assert result["evidence_precision_at_k_lower_bound"] == 1 / 3
    assert result["mean_chunks_at_k"] == 3.0
    assert result["evidence_mrr_at_k"] == 0.5
    assert result["pooled_judgment_coverage"] == 2 / 3
    assert result["pooled_relevant_precision_lower_bound"] == 1 / 3
    assert result["pooled_relevant_precision_on_judged"] == 0.5
