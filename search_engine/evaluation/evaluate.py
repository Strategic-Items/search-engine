"""Measure the live /v1/search against the reviewed query set.

The set is `data/queries_v1.jsonl`, copied from the lab repository and
corrected here; `data/queries_v1.manifest.json` records where it came from.
"""

import argparse
import json
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

# The lab labels gold by parent document, except HSK rows, which are their own id.
HSK_CATEGORY = "hsk"


def load_queries(path: Path) -> list[dict]:
    rows = []
    seen = set()
    for line_no, line in enumerate(path.open(encoding="utf-8"), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not row.get("gold"):
            raise ValueError(f"query without gold at line {line_no}: {row.get('qid')}")
        if not isinstance(row["gold"], list) or any(not isinstance(g, str) or not g for g in row["gold"]):
            raise ValueError(f"gold must be a nonempty list of IDs at line {line_no}")
        if not row.get("qid") or row["qid"] in seen:
            raise ValueError(f"missing or duplicate qid at line {line_no}")
        seen.add(row["qid"])
        if not isinstance(row.get("query"), str) or not row["query"].strip():
            raise ValueError(f"query text is required at line {line_no}")
        if row.get("gold_unit") not in (None, "parent_id"):
            raise ValueError(f"unsupported gold unit at line {line_no}: {row['gold_unit']}")
        for field in ("gold_groups", "evidence_groups"):
            groups = row.get(field)
            if groups is not None and (
                not isinstance(groups, list) or not groups or
                any(not isinstance(group, list) or not group or
                    any(not isinstance(item, str) or not item for item in group) for group in groups)
            ):
                raise ValueError(f"{field} must contain nonempty groups of IDs at line {line_no}")
        if "gold_groups" in row:
            grouped = [parent for group in row["gold_groups"] for parent in group]
            if set(grouped) != set(row["gold"]) or len(grouped) != len(set(grouped)):
                raise ValueError(f"gold_groups must partition gold at line {line_no}")
        rows.append(row)
    return rows


def indexed_ids(prepared_dir: Path) -> set[str]:
    """Every id and parent_id the prepared datasets would put in the index."""
    ids = set()
    for name in ("core.jsonl", "docs.jsonl", "hsk.jsonl"):
        path = prepared_dir / name
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                row = json.loads(line)
                ids.add(row["id"])
                ids.add(row.get("parent_id") or row["id"])
    return ids


def ranked_ids(result: dict, category: str) -> list[str]:
    """The ids this result offers, in rank order, in the unit the gold uses."""
    if category == HSK_CATEGORY:
        linkage = result.get("hsk") or {}
        return [hit["id"] for hit in linkage.get("hits", [])]
    return [hit["parent_id"] for hit in result.get("hits", [])]


def hit_at(ranked: list[str], gold: list[str], k: int) -> bool:
    """A query counts as answered when any of its gold ids appears in the top k."""
    return bool(set(ranked[:k]) & set(gold))


def recall_at(ranked: list[str], gold: list[str], k: int) -> float:
    """Fraction of distinct relevant parents retrieved, not any-hit accuracy."""
    if k < 1 or not gold:
        raise ValueError("positive k and nonempty gold are required")
    relevant = set(gold)
    return len(set(ranked[:k]) & relevant) / len(relevant)


def reciprocal_rank_at(ranked: list[str], gold: list[str], k: int) -> float:
    return next((1 / rank for rank, doc in enumerate(ranked[:k], 1) if doc in set(gold)), 0.0)


def quality_metrics(rows: list[dict], k: int) -> dict:
    if not rows:
        raise ValueError("evaluation query set is empty")
    n = len(rows)
    found = sum(len(set(r['returned'][:k]) & set(r['gold'])) for r in rows)
    relevant = sum(len(set(r['gold'])) for r in rows)
    metrics = {
        "queries": n,
        "hit_at_1": sum(hit_at(r['returned'], r['gold'], 1) for r in rows) / n,
        f"hit_at_{k}": sum(hit_at(r['returned'], r['gold'], k) for r in rows) / n,
        f"recall_at_{k}": sum(recall_at(r['returned'], r['gold'], k) for r in rows) / n,
        f"micro_recall_at_{k}": found / relevant,
        f"mrr_at_{k}": sum(reciprocal_rank_at(r['returned'], r['gold'], k) for r in rows) / n,
    }
    for field, ranked_field, prefix in (
        ("gold_groups", "returned", "group"),
        ("evidence_groups", "returned_chunks", "evidence"),
    ):
        eligible = [r for r in rows if r.get(field) and ranked_field in r]
        if not eligible:
            continue
        recovered = [sum(bool(set(group) & set(r[ranked_field][:k])) for group in r[field])
                     for r in eligible]
        metrics.update({
            f"{prefix}_queries": len(eligible),
            f"{prefix}_hit_at_{k}": sum(n > 0 for n in recovered) / len(eligible),
            f"{prefix}_recall_at_{k}": sum(n / len(r[field]) for n, r in zip(recovered, eligible)) / len(eligible),
            f"{prefix}_micro_recall_at_{k}": sum(recovered) / sum(len(r[field]) for r in eligible),
            f"{prefix}_all_at_{k}": sum(n == len(r[field]) for n, r in zip(recovered, eligible)) / len(eligible),
        })
    return metrics


def search(base_url: str, query: str, timeout: float = 30.0) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/search",
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def evaluate(queries: list[dict], base_url: str, prepared_dir: Path, k: int = 5) -> dict:
    if not queries or not 1 <= k <= 5:
        raise ValueError("nonempty queries and 1 <= k <= 5 required (public API returns at most 5)")
    known = indexed_ids(prepared_dir)
    coverage_known = any((prepared_dir / name).is_file()
                         for name in ("core.jsonl", "docs.jsonl", "hsk.jsonl"))
    per_query = []
    for row in queries:
        category = row.get("category", "unknown")
        gold = row["gold"]
        try:
            result = search(base_url, row["query"])
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{row['qid']}: search failed with HTTP {exc.code}") from exc
        ranked = ranked_ids(result, category)
        per_query.append({
            "qid": row["qid"],
            "category": category,
            "query": row["query"],
            "gold": gold,
            "first": hit_at(ranked, gold, 1),
            "top_k": hit_at(ranked, gold, k),
            # A gold document the index never received is a coverage gap, not a ranking miss.
            "gold_indexed": (not coverage_known) or set(gold) <= known,
            "gold_missing_ids": sorted(set(gold) - known) if coverage_known else None,
            "review_status": row.get("review_status"),
            "returned": ranked[:k],
            "returned_chunks": [hit["id"] for hit in result.get("hits", [])[:k] if "id" in hit],
            **{key: row[key] for key in ("gold_groups", "evidence_groups") if key in row},
        })

    categories = {}
    for entry in per_query:
        bucket = categories.setdefault(entry["category"], Counter())
        bucket["queries"] += 1
        bucket["first"] += entry["first"]
        bucket["top_k"] += entry["top_k"]
        bucket["gold_missing_from_index"] += not entry["gold_indexed"]
    totals = Counter()
    for bucket in categories.values():
        totals.update(bucket)
    # Ranking can only be judged where the gold document actually reached the index.
    answerable = Counter()
    for entry in per_query:
        if entry["gold_indexed"]:
            answerable["queries"] += 1
            answerable["first"] += entry["first"]
            answerable["top_k"] += entry["top_k"]
    return {
        "answerable": dict(answerable),
        "k": k,
        "base_url": base_url,
        "totals": dict(totals),
        "categories": {name: dict(counts) for name, counts in sorted(categories.items())},
        "reviewed": dict(Counter(entry["review_status"] for entry in per_query)),
        "queries": per_query,
        "metrics": quality_metrics(per_query, k),
        "coverage_known": coverage_known,
    }


def format_report(report: dict) -> str:
    k = report["k"]
    lines = [f"| 유형 | 질의 | 첫 결과 | 상위 {k}건 | 정답 미색인 |",
             "|---|---:|---:|---:|---:|"]
    for name, counts in report["categories"].items():
        lines.append(
            f"| {name} | {counts['queries']} | {counts['first']} / {counts['queries']} "
            f"| {counts['top_k']} / {counts['queries']} | {counts['gold_missing_from_index']} |"
        )
    totals = report["totals"]
    lines.append(
        f"| **합계** | {totals['queries']} | {totals['first']} / {totals['queries']} "
        f"| {totals['top_k']} / {totals['queries']} | {totals['gold_missing_from_index']} |"
    )
    answerable = report["answerable"]
    lines.append("")
    lines.append(
        f"정답이 색인된 질의만: {answerable['queries']}건 중 "
        f"첫 결과 {answerable['first']}, 상위 {k}건 {answerable['top_k']} "
        f"(나머지 {totals['queries'] - answerable['queries']}건은 순위가 아니라 색인 범위 문제)"
    )
    lines.append("정답 검토 상태: " + ", ".join(
        f"{status}={count}" for status, count in sorted(report["reviewed"].items(), key=lambda pair: str(pair[0]))))
    metrics = report["metrics"]
    lines.append(f"Recall@{k} (macro): {metrics[f'recall_at_{k}']:.4f}; "
                 f"MRR@{k}: {metrics[f'mrr_at_{k}']:.4f}")
    if not report["coverage_known"]:
        lines.append("주의: 코퍼스 파일이 없어 정답 색인 여부는 확인하지 못했습니다.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score the running search API against the lab's reviewed query set")
    parser.add_argument("queries_jsonl", type=Path, nargs="?",
                        default=Path("data/queries_v1.jsonl"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8092")
    parser.add_argument("--prepared", type=Path, default=Path("data/generated"),
                        help="Prepared datasets, used to tell coverage gaps from ranking misses")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--out", type=Path, help="Write the full per-query report as JSON")
    args = parser.parse_args()

    report = evaluate(load_queries(args.queries_jsonl), args.base_url, args.prepared, args.k)
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    print(format_report(report))
