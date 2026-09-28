"""Ask whether per-query routing between bm25, vector and hybrid could pay off.

Reads a saved `search-compare` report and, for each query, scores every mode on
the primary chunk metric (evidence recall@k, ties broken by evidence MRR@k).
The oracle picks the best mode per query *after* seeing the labels, so it is an
upper bound on any router, not something a router can reach. If the oracle
barely beats always-hybrid, routing is not worth building.

Queries where a single retriever beats hybrid are listed with features that a
router could see before searching (identifier tokens, length, category), so a
reader can judge whether the winners share an observable trait.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from search_engine.evaluation.evaluate import flat_within

IDENTIFIER = re.compile(r"\d|제\s*\d+\s*조|[A-Za-z]{2,}")


def per_query(row: dict, k: int) -> tuple[float, float]:
    shown = flat_within(row["returned_chunks"], k)
    groups = row["evidence_groups"]
    recall = sum(bool(set(group) & set(shown)) for group in groups) / len(groups)
    wanted = {chunk for group in groups for chunk in group}
    rank = next((rank for rank, chunk in enumerate(shown, 1) if chunk in wanted), 0)
    return recall, 1 / rank if rank else 0.0


def features(query: str) -> dict:
    return {"identifier": bool(IDENTIFIER.search(query)), "chars": len(query)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    modes = list(report["modes"])
    rows = {mode: {r["qid"]: r for r in report["modes"][mode]["queries"]
                   if r.get("evidence_groups")} for mode in modes}
    qids = sorted(set.intersection(*(set(r) for r in rows.values())))
    scores = {qid: {mode: per_query(rows[mode][qid], args.k) for mode in modes} for qid in qids}
    n = len(qids)

    def mean(pick) -> tuple[float, float]:
        chosen = [scores[qid][pick(qid)] for qid in qids]
        return sum(c[0] for c in chosen) / n, sum(c[1] for c in chosen) / n

    best = {qid: max(modes, key=lambda mode: (scores[qid][mode], mode == "hybrid"))
            for qid in qids}
    summary = {mode: mean(lambda qid, mode=mode: mode) for mode in modes}
    summary["oracle"] = mean(best.get)
    for pair in (("bm25", "hybrid"), ("vector", "hybrid"), ("bm25", "vector")):
        summary["oracle_" + "+".join(pair)] = mean(
            lambda qid, pair=pair: max(pair, key=lambda mode: (scores[qid][mode], mode == "hybrid")))

    beats = []
    for qid in qids:
        hybrid = scores[qid]["hybrid"]
        for mode in modes:
            if mode != "hybrid" and scores[qid][mode] > hybrid:
                row = rows["hybrid"][qid]
                beats.append({"qid": qid, "winner": mode, "category": row.get("category"),
                              "query": row["query"], **features(row["query"]),
                              "winner_recall_mrr": scores[qid][mode], "hybrid_recall_mrr": hybrid})
    losses = [{"qid": qid, "category": rows["hybrid"][qid].get("category"),
               "query": rows["hybrid"][qid]["query"],
               **{mode: scores[qid][mode] for mode in modes}}
              for qid in qids if scores[qid]["hybrid"][0] < 1]

    by_category = defaultdict(Counter)
    for qid in qids:
        category = rows["hybrid"][qid].get("category", "unknown")
        by_category[category]["queries"] += 1
        for mode in modes:
            by_category[category][mode] += scores[qid][mode][0]
        by_category[category]["oracle"] += scores[qid][best[qid]][0]

    print(f"질의 {n}건, 근거 Recall@{args.k} / 근거 MRR@{args.k}\n")
    print("| 선택 | 근거 Recall | 근거 MRR |\n|---|---:|---:|")
    for name, (recall, mrr) in summary.items():
        print(f"| {name} | {recall:.4f} | {mrr:.4f} |")
    print(f"\n| 유형 | 질의 | {' | '.join(modes)} | oracle |\n|---|---:|" + "---:|" * (len(modes) + 1))
    for category, counts in sorted(by_category.items()):
        cells = " | ".join(f"{counts[mode] / counts['queries']:.3f}" for mode in [*modes, "oracle"])
        print(f"| {category} | {counts['queries']} | {cells} |")
    print(f"\n단일 검색기가 hybrid를 이긴 질의 {len(beats)}건:")
    for b in beats:
        print(f"- {b['qid']} [{b['category']}] {b['winner']} "
              f"{b['winner_recall_mrr'][0]:.2f}/{b['winner_recall_mrr'][1]:.2f} vs "
              f"hybrid {b['hybrid_recall_mrr'][0]:.2f}/{b['hybrid_recall_mrr'][1]:.2f} "
              f"식별자={b['identifier']} {b['chars']}자 :: {b['query']}")
    print(f"\nhybrid가 근거를 놓친 질의 {len(losses)}건:")
    for loss in losses:
        cells = " ".join(f"{mode}={loss[mode][0]:.2f}" for mode in modes)
        print(f"- {loss['qid']} [{loss['category']}] {cells} :: {loss['query']}")

    if args.out:
        args.out.write_text(json.dumps({
            "source": str(args.report), "k": args.k, "queries": n,
            "summary": {name: {"evidence_recall": r, "evidence_mrr": m}
                        for name, (r, m) in summary.items()},
            "oracle_choice": Counter(best.values()),
            "beats_hybrid": beats, "hybrid_misses": losses,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
