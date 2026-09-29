"""Paired bootstrap between two `search-evaluate` reports on the same queries.

Reports the change in top-1 document hit and evidence recall@k (before -> after) with a
95% percentile interval over resampled queries. A change is only worth adopting when the
interval excludes 0; on a set where one query is 0.7-1.4p this is what separates a real
gain from noise.

    python scripts/paired_bootstrap.py before.json after.json [--k 5] [--seed 44]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random

from search_engine.evaluation.evaluate import hit_at, offered_within

RESAMPLES = 5000


def load(path: Path) -> dict[str, dict]:
    report = json.loads(path.read_text(encoding="utf-8"))
    return {row["qid"]: row for row in report["queries"]}


def per_query(row: dict, k: int) -> dict[str, float | None]:
    """Per-query scores; a metric is None when the query has no evidence label for it."""
    out = {"first": float(hit_at(row["returned"], row["gold"], 1))}
    groups = row.get("evidence_groups")
    if groups and "returned_chunks" in row:
        offered = offered_within(row["returned_chunks"], k)
        out["evidence_recall"] = sum(bool(set(g) & offered) for g in groups) / len(groups)
    else:
        out["evidence_recall"] = None
    return out


def interval(deltas: list[float], rng: random.Random) -> tuple[float, float]:
    n = len(deltas)
    means = sorted(sum(rng.choices(deltas, k=n)) / n for _ in range(RESAMPLES))
    return means[int(RESAMPLES * 0.025)], means[int(RESAMPLES * 0.975) - 1]


def compare(before: dict[str, dict], after: dict[str, dict], k: int, seed: int) -> dict:
    qids = sorted(set(before) & set(after))
    if not qids:
        raise ValueError("reports share no qids")
    only = len(set(before) ^ set(after))
    scores = {qid: (per_query(before[qid], k), per_query(after[qid], k)) for qid in qids}
    rng = random.Random(seed)
    result = {"queries": len(qids), "unpaired_qids_ignored": only, "k": k}
    for metric in ("first", "evidence_recall"):
        pairs = [(a[metric], b[metric]) for a, b in scores.values()
                 if a[metric] is not None and b[metric] is not None]
        if not pairs:
            continue
        deltas = [b - a for a, b in pairs]
        low, high = interval(deltas, rng)
        result[metric] = {
            "n": len(pairs),
            "before": sum(a for a, _ in pairs) / len(pairs),
            "after": sum(b for _, b in pairs) / len(pairs),
            "delta": sum(deltas) / len(deltas),
            "ci95": [low, high],
            "improved": sum(d > 0 for d in deltas), "worsened": sum(d < 0 for d in deltas),
            "excludes_zero": low > 0 or high < 0,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--seed", type=int, default=44)
    args = parser.parse_args()
    result = compare(load(args.before), load(args.after), args.k, args.seed)
    print(f"queries={result['queries']} (unpaired ignored: {result['unpaired_qids_ignored']})")
    for metric in ("first", "evidence_recall"):
        if metric in result:
            m = result[metric]
            print(f"{metric:16} {m['before']:.3f} -> {m['after']:.3f}  "
                  f"delta {m['delta'] * 100:+.1f}p  95% [{m['ci95'][0] * 100:+.1f}, "
                  f"{m['ci95'][1] * 100:+.1f}]p  +{m['improved']}/-{m['worsened']}  "
                  f"{'excludes 0' if m['excludes_zero'] else 'includes 0'}")


if __name__ == "__main__":
    main()
