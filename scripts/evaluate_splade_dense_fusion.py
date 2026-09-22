"""Fuse saved SPLADE rankings with the deployed dense retriever using RRF.

SPLADE is still an offline experiment, so this script deliberately leaves the
production modes untouched. It fetches fresh dense candidates from OpenSearch,
then applies the same pre-fusion trimming and leader-preserving final cutoff as
the deployed hybrid path at parent-document granularity.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
import json
from pathlib import Path
from time import perf_counter

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search.query import build_vector_query


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def parent_ranking(hits: list[dict]) -> list[tuple[str, float]]:
    """Keep a parent's best dense chunk and preserve dense order."""
    seen = set()
    ranked = []
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
    return [(parent, score) for parent, score in ranked if score >= floor]


def rrf(splade: list[tuple[str, float]], dense: list[tuple[str, float]], k: int) -> list[dict]:
    scores = defaultdict(float)
    dense_rank = {}
    leaders = {ranked[0][0] for ranked in (splade, dense) if ranked}
    for ranked, name in ((splade, "splade"), (dense, "dense")):
        for rank, (parent, _) in enumerate(ranked, 1):
            scores[parent] += 1 / (k + rank)
            if name == "dense":
                dense_rank[parent] = rank
    ordered = sorted(scores, key=lambda parent: (
        -scores[parent], dense_rank.get(parent, len(scores) + 1), parent,
    ))
    return [{"parent_id": parent, "score": scores[parent], "leads": parent in leaders}
            for parent in ordered]


def rrf_chunks(splade: list[tuple[str, float]], dense: list[tuple[str, float]], k: int) -> list[dict]:
    return [{"chunk_id": row["parent_id"], "score": row["score"], "leads": row["leads"]}
            for row in rrf(splade, dense, k)]


def load_judgments(path: Path | None) -> dict[tuple[str, str], int]:
    if path is None:
        return {}
    judgments = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            qid, chunk_id, grade = line.split("\t")
            judgments[(qid, chunk_id)] = int(grade)
    return judgments


def baseline_chunk_rankings(path: Path, mode: str) -> list[dict]:
    report = json.loads(path.read_text(encoding="utf-8"))
    rankings = []
    for row in report["modes"][mode]["queries"]:
        seen = set()
        flat = []
        for chunks in row.get("returned_chunks", []):
            for chunk_id in chunks:
                if chunk_id not in seen:
                    seen.add(chunk_id)
                    flat.append({"chunk_id": chunk_id})
        rankings.append({"qid": row["qid"], "chunk_ranked": flat})
    return rankings


def chunk_metrics(rankings: list[dict], queries: dict[str, dict], judgments: dict, k: int = 5) -> dict:
    recovered = []
    exact = 0
    shown_total = 0
    ranks = []
    pooled_grades = []
    for row in rankings:
        query = queries[row["qid"]]
        shown = [hit["chunk_id"] for hit in row["chunk_ranked"][:k]]
        groups = query["evidence_groups"]
        wanted = {chunk for group in groups for chunk in group}
        shown_total += len(shown)
        recovered.append(sum(bool(set(group) & set(shown)) for group in groups))
        exact += len(set(shown) & wanted)
        ranks.append(next((rank for rank, chunk in enumerate(shown, 1) if chunk in wanted), 0))
        pooled_grades.extend(judgments.get((row["qid"], chunk)) for chunk in shown)
    n = len(rankings)
    judged = [grade for grade in pooled_grades if grade is not None]
    return {
        "k": k,
        "evidence_hit_at_k": sum(count > 0 for count in recovered) / n,
        "evidence_recall_at_k": sum(
            count / len(queries[row["qid"]]["evidence_groups"])
            for count, row in zip(recovered, rankings)) / n,
        "evidence_all_at_k": sum(
            count == len(queries[row["qid"]]["evidence_groups"])
            for count, row in zip(recovered, rankings)) / n,
        "evidence_precision_at_k_lower_bound": exact / shown_total if shown_total else 0.0,
        "mean_chunks_at_k": shown_total / n,
        "evidence_mrr_at_k": sum(1 / rank if rank else 0 for rank in ranks) / n,
        "evidence_first_rank_at_k": (
            sum(rank for rank in ranks if rank) / sum(bool(rank) for rank in ranks)
            if any(ranks) else 0.0),
        "pooled_judgment_coverage": len(judged) / len(pooled_grades) if pooled_grades else 0.0,
        "pooled_relevant_precision_lower_bound": (
            sum(grade >= 1 for grade in judged) / len(pooled_grades) if pooled_grades else None),
        "pooled_direct_precision_lower_bound": (
            sum(grade == 2 for grade in judged) / len(pooled_grades) if pooled_grades else None),
        "pooled_relevant_precision_on_judged": (
            sum(grade >= 1 for grade in judged) / len(judged) if judged else None),
        "pooled_direct_precision_on_judged": (
            sum(grade == 2 for grade in judged) / len(judged) if judged else None),
    }


def metrics(rankings: list[dict], final_ratio: float) -> dict:
    returned = []
    for row in rankings:
        ranked = row["ranked"]
        floor = ranked[0]["score"] * final_ratio if ranked else 0.0
        kept = [hit["parent_id"] for hit in ranked
                if hit["score"] >= floor or hit["leads"]][:5]
        returned.append((kept, set(row["gold"])))
    relevant = sum(sum(parent in gold for parent in kept) for kept, gold in returned)
    count = sum(len(kept) for kept, _ in returned)
    reciprocal = lambda kept, gold: next(
        (1 / rank for rank, parent in enumerate(kept, 1) if parent in gold), 0.0)
    return {
        "final_ratio": final_ratio,
        "precision_at_1": sum(bool(kept) and kept[0] in gold
                              for kept, gold in returned) / len(returned),
        "hit_at_5": sum(any(parent in gold for parent in kept)
                        for kept, gold in returned) / len(returned),
        "precision_returned": relevant / count if count else 0.0,
        "mean_returned": count / len(returned),
        "mrr_at_5": sum(reciprocal(kept, gold) for kept, gold in returned) / len(returned),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--splade", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--alias", default="search-docs-only")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 9, 17))
    parser.add_argument("--candidates", type=int, default=50)
    parser.add_argument("--splade-trim", type=float, default=0.97)
    parser.add_argument("--dense-trim", type=float, default=0.97)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--judgments", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--baseline-mode", default="hybrid")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    splade_report = json.loads(args.splade.read_text(encoding="utf-8"))
    splade_by_qid = {row["qid"]: row for row in splade_report["results"]}
    queries = [row for row in rows(args.queries) if row.get("gold")]
    queries_by_qid = {row["qid"]: row for row in queries}
    settings = get_settings()
    client = create_client(settings)
    embedder = OllamaEmbedder(settings)
    rankings = []
    dense_seconds = 0.0

    for query in queries:
        started = perf_counter()
        vector = embedder.embed_query(query["query"])
        response = client.search(
            index=args.alias,
            body={"query": build_vector_query(
                vector, args.as_of, args.candidates, query["query"])},
            size=args.candidates,
        )
        dense_seconds += perf_counter() - started
        dense = ratio_cut(parent_ranking(response["hits"]["hits"]), args.dense_trim)
        dense_chunks = ratio_cut(chunk_ranking(response["hits"]["hits"]), args.dense_trim)
        saved = splade_by_qid[query["qid"]]["ranked"]
        splade = ratio_cut(
            [(hit["parent_id"], float(hit["score"])) for hit in saved],
            args.splade_trim,
        )
        saved_chunks = splade_by_qid[query["qid"]].get("chunk_ranked")
        if saved_chunks is None:
            raise ValueError("SPLADE report has no chunk_ranked data; rerun evaluate_splade.py")
        splade_chunks = ratio_cut(
            [(hit["chunk_id"], float(hit["score"])) for hit in saved_chunks],
            args.splade_trim,
        )
        rankings.append({
            "qid": query["qid"], "gold": query["gold"],
            "ranked": rrf(splade, dense, args.rrf_k)[:25],
            "chunk_ranked": rrf_chunks(splade_chunks, dense_chunks, args.rrf_k)[:100],
        })

    sweeps = [metrics(rankings, ratio) for ratio in (0.0, 0.80, 0.90, 0.95, 0.97, 0.99, 1.0)]
    judgments = load_judgments(args.judgments)
    report = {
        "method": "splade+dense RRF", "queries": len(queries), "alias": args.alias,
        "as_of": args.as_of.isoformat(), "candidates": args.candidates,
        "splade_trim": args.splade_trim, "dense_trim": args.dense_trim,
        "rrf_k": args.rrf_k, "dense_elapsed_seconds": dense_seconds,
        "sweeps": sweeps,
        "chunk_metrics": chunk_metrics(rankings, queries_by_qid, judgments),
        "results": rankings,
    }
    if args.baseline:
        report["baseline_chunk_metrics"] = chunk_metrics(
            baseline_chunk_rankings(args.baseline, args.baseline_mode),
            queries_by_qid, judgments,
        )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(json.dumps(sweeps, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
