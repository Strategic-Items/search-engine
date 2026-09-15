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

from search_engine.config import get_settings

# The lab labels gold by parent document, except HSK rows, which are their own id.
HSK_CATEGORY = "hsk"


def load_queries(path: Path) -> list[dict]:
    rows = []
    for line_no, line in enumerate(path.open(encoding="utf-8"), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not row.get("gold"):
            raise ValueError(f"query without gold at line {line_no}: {row.get('qid')}")
        if row.get("gold_unit") not in (None, "parent_id"):
            raise ValueError(f"unsupported gold unit at line {line_no}: {row['gold_unit']}")
        rows.append(row)
    return rows


def indexed_ids(prepared_dir: Path) -> set[str]:
    """Every id and parent_id the prepared datasets would put in the index."""
    ids = set()
    for name in ("core.jsonl", "hsk.jsonl"):
        path = prepared_dir / name
        if not path.is_file():
            return set()
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


def search(base_url: str, api_key: str, query: str, timeout: float = 30.0) -> dict:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/v1/search",
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def evaluate(
    queries: list[dict], base_url: str, api_key: str, prepared_dir: Path, k: int = 5,
) -> dict:
    known = indexed_ids(prepared_dir)
    per_query = []
    for row in queries:
        category = row.get("category", "unknown")
        gold = row["gold"]
        try:
            result = search(base_url, api_key, row["query"])
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
            "gold_indexed": (not known) or bool(set(gold) & known),
            "review_status": row.get("review_status"),
            "returned": ranked[:k],
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
        f"{status}={count}" for status, count in sorted(report["reviewed"].items())))
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

    api_key = get_settings().search_api_key
    if not api_key:
        raise SystemExit("SEARCH_API_KEY is not configured; the API would reject every request")
    report = evaluate(load_queries(args.queries_jsonl), args.base_url, api_key,
                      args.prepared, args.k)
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    print(format_report(report))
