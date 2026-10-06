"""Compare fusion formulas for SPLADE(config C)+dense, on live dense retrieval.

Each query's dense candidates come from the live cluster (OllamaEmbedder +
OpenSearch), same as evaluate_splade_dense_fusion.py. SPLADE comes from a
saved config-C report (ev-C-*.json from the stage-38 fine-tune run) so this
needs no GPU. The point is isolating the fusion *formula* -- RRF at
different k, SPLADE-weighted RRF, and top-1-normalized weighted sum -- while
holding everything else (trims, candidates, query set) fixed. Production
itself stays on bm25+dense; this is an offline comparison only.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import json
from pathlib import Path

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search.query import build_vector_query


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def parent_ranking(hits: list[dict]) -> list[tuple[str, float]]:
    seen, ranked = set(), []
    for hit in hits:
        parent = hit["_source"].get("parent_id") or hit["_id"]
        if parent not in seen:
            seen.add(parent)
            ranked.append((parent, float(hit["_score"])))
    return ranked


def chunk_ranking(hits: list[dict]) -> list[tuple[str, float]]:
    return [(hit["_id"], float(hit["_score"])) for hit in hits]


def ratio_cut(ranked: list[tuple[str, float]], ratio: float) -> list[tuple[str, float]]:
    if not ratio or not ranked or ranked[0][1] <= 0:
        return ranked
    floor = ranked[0][1] * ratio
    return [(key, score) for key, score in ranked if score >= floor]


def rrf(splade: list[tuple[str, float]], dense: list[tuple[str, float]], *,
        k: int, splade_weight: float = 1.0) -> list[dict]:
    scores: dict[str, float] = defaultdict(float)
    dense_rank: dict[str, int] = {}
    leaders = {ranked[0][0] for ranked in (splade, dense) if ranked}
    for ranked, name, weight in ((splade, "splade", splade_weight), (dense, "dense", 1.0)):
        for rank, (key, _) in enumerate(ranked, 1):
            scores[key] += weight / (k + rank)
            if name == "dense":
                dense_rank[key] = rank
    ordered = sorted(scores, key=lambda key: (-scores[key], dense_rank.get(key, len(scores) + 1), key))
    return [{"key": key, "score": scores[key], "leads": key in leaders} for key in ordered]


def scorefuse(splade: list[tuple[str, float]], dense: list[tuple[str, float]], *,
              splade_weight: float = 1.0) -> list[dict]:
    """Normalize each list by its own top score (0..1), then weighted sum (CombSUM-style)."""
    scores: dict[str, float] = defaultdict(float)
    for ranked, weight in ((splade, splade_weight), (dense, 1.0)):
        if ranked:
            top = ranked[0][1]
            for key, score in ranked:
                scores[key] += weight * score / top
    leaders = {ranked[0][0] for ranked in (splade, dense) if ranked}
    ordered = sorted(scores, key=lambda key: (-scores[key], key))
    return [{"key": key, "score": scores[key], "leads": key in leaders} for key in ordered]


def metrics(rankings: list[dict], final_ratio: float) -> dict:
    returned = []
    for row in rankings:
        ranked = row["fused"]
        floor = ranked[0]["score"] * final_ratio if ranked else 0.0
        kept = [hit["key"] for hit in ranked if hit["score"] >= floor or hit["leads"]][:5]
        returned.append((kept, set(row["gold"])))
    relevant = sum(sum(key in gold for key in kept) for kept, gold in returned)
    count = sum(len(kept) for kept, _ in returned)
    reciprocal = lambda kept, gold: next(
        (1 / rank for rank, key in enumerate(kept, 1) if key in gold), 0.0)
    n = len(returned)
    return {
        "precision_at_1": sum(bool(kept) and kept[0] in gold for kept, gold in returned) / n,
        "hit_at_5": sum(any(key in gold for key in kept) for kept, gold in returned) / n,
        "precision_returned": relevant / count if count else 0.0,
        "mean_returned": count / n,
        "mrr_at_5": sum(reciprocal(kept, gold) for kept, gold in returned) / n,
    }


def evidence_metrics(rankings: list[dict], queries: dict[str, dict], k: int = 5) -> dict:
    recovered, ranks, n = [], [], 0
    for row in rankings:
        groups = queries[row["qid"]].get("evidence_groups") or []
        if not groups:
            continue
        n += 1
        shown = [hit["key"] for hit in row["fused_chunks"][:k]]
        shown_set = set(shown)
        hits = [bool(set(group) & shown_set) for group in groups]
        recovered.append(sum(hits) / len(groups))
        wanted = {chunk for group in groups for chunk in group}
        rank = next((i for i, chunk in enumerate(shown, 1) if chunk in wanted), 0)
        ranks.append(rank)
    return {
        "evidence_hit_at_k": sum(bool(rank) for rank in ranks) / n,
        "evidence_recall_at_k": sum(recovered) / n,
        "evidence_mrr_at_k": sum(1 / rank if rank else 0 for rank in ranks) / n,
    }


FUSIONS = [
    ("rrf k=60 (현재)", lambda s, d: rrf(s, d, k=60)),
    ("rrf k=30", lambda s, d: rrf(s, d, k=30)),
    ("rrf k=100", lambda s, d: rrf(s, d, k=100)),
    ("rrf k=60, SPLADE가중 1.5", lambda s, d: rrf(s, d, k=60, splade_weight=1.5)),
    ("rrf k=60, SPLADE가중 0.5", lambda s, d: rrf(s, d, k=60, splade_weight=0.5)),
    ("점수합(1위 정규화)", lambda s, d: scorefuse(s, d)),
    ("점수합, SPLADE가중 1.5", lambda s, d: scorefuse(s, d, splade_weight=1.5)),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--splade", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--alias", required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 10, 6))
    parser.add_argument("--candidates", type=int, default=50)
    parser.add_argument("--splade-trim", type=float, default=0.97)
    parser.add_argument("--dense-trim", type=float, default=0.97)
    parser.add_argument("--final-ratio", type=float, default=0.97)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    splade_report = json.loads(args.splade.read_text(encoding="utf-8"))
    splade_by_qid = {row["qid"]: row for row in splade_report["results"]}
    queries = [row for row in rows(args.queries) if row.get("gold")]
    queries_by_qid = {row["qid"]: row for row in queries}
    settings = get_settings()
    client = create_client(settings)
    embedder = OllamaEmbedder(settings)

    per_query = []
    for query in queries:
        saved = splade_by_qid[query["qid"]]
        splade_parents = ratio_cut(
            [(hit["parent_id"], float(hit["score"])) for hit in saved["ranked"]], args.splade_trim)
        splade_chunks = ratio_cut(
            [(hit["chunk_id"], float(hit["score"])) for hit in saved["chunk_ranked"]], args.splade_trim)
        vector = embedder.embed_query(query["query"])
        response = client.search(
            index=args.alias,
            body={"query": build_vector_query(vector, args.as_of, args.candidates, query["query"])},
            size=args.candidates,
        )
        hits = response["hits"]["hits"]
        dense_parents = ratio_cut(parent_ranking(hits), args.dense_trim)
        dense_chunks = ratio_cut(chunk_ranking(hits), args.dense_trim)
        per_query.append((query["qid"], query["gold"], splade_parents, dense_parents,
                          splade_chunks, dense_chunks))

    report = {"splade_trim": args.splade_trim, "dense_trim": args.dense_trim,
              "final_ratio": args.final_ratio, "queries": len(per_query), "variants": []}
    header = f"{'융합 방식':28s} | {'P@1':>6s} {'Hit@5':>6s} {'MRR@5':>6s} | 청크 {'Hit':>5s} {'Recall':>6s} {'MRR':>6s}"
    print(header)
    for label, fuse in FUSIONS:
        rankings = []
        for qid, gold, sp, de, spc, dec in per_query:
            rankings.append({
                "qid": qid, "gold": gold,
                "fused": fuse(sp, de)[:25],
                "fused_chunks": fuse(spc, dec)[:25],
            })
        m = metrics(rankings, args.final_ratio)
        e = evidence_metrics(rankings, queries_by_qid)
        print(f"{label:28s} | {m['precision_at_1']:6.3f} {m['hit_at_5']:6.3f} {m['mrr_at_5']:6.3f} | "
              f"{e['evidence_hit_at_k']:5.3f} {e['evidence_recall_at_k']:6.3f} {e['evidence_mrr_at_k']:6.3f}")
        report["variants"].append({"label": label, "doc_metrics": m, "evidence_metrics": e})

    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
