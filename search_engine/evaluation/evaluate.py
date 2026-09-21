"""live /v1/search를 검토된 쿼리 세트에 대해 측정한다.

세트는 `data/queries_v1.jsonl`이며, 실험실 저장소에서 복사하여
여기서 수정한 것이다; `data/queries_v1.manifest.json`은 그것이 어디에서 왔는지 기록한다.
"""

import argparse
import json
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

# 실험실 레이블은 부모 문서에 따라 골드를 지정하며, HSK 행을 제외하고는 그 자체가 id이다.
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
    """준비된 데이터셋이 인덱스에 넣을 모든 id와 parent_id."""
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
    """이 결과가 제공하는 id들, 골드가 사용하는 단위에서 순위 순서로."""
    if category == HSK_CATEGORY:
        linkage = result.get("hsk") or {}
        return [hit["id"] for hit in linkage.get("hits", [])]
    return [hit["parent_id"] for hit in result.get("hits", [])]


def hit_at(ranked: list[str], gold: list[str], k: int) -> bool:
    """골드 id 중 하나가 상위 k에 포함되면 쿼리가 답변된 것으로 간주한다."""
    return bool(set(ranked[:k]) & set(gold))


def recall_at(ranked: list[str], gold: list[str], k: int) -> float:
    """중복되지 않는 관련 부모 문서의 추출 비율, 단일 출현 정확도가 아니다."""
    if k < 1 or not gold:
        raise ValueError("positive k and nonempty gold are required")
    relevant = set(gold)
    return len(set(ranked[:k]) & relevant) / len(relevant)


def reciprocal_rank_at(ranked: list[str], gold: list[str], k: int) -> float:
    return next((1 / rank for rank, doc in enumerate(ranked[:k], 1) if doc in set(gold)), 0.0)


def precision_at(ranked: list[str], gold: list[str], k: int) -> float:
    """k 슬롯당 고유한 관련 부모; 채워지지 않은 슬롯은 실수로 간주.

    precision_at_1에 사용되며 이전 보고서를 읽을 때 사용된다. k > 1에서는 사용하지 마라: 컷오프를 사용하면 목록이 보통 k보다 짧아지고, 대부분의 쿼리에는 단일 골드 부모가 있으므로 고정된 분모는 평균을 거의 1/k로 제한하고, 순위나 컷오프가 변경되더라도 지표가 움직이지 않는다.
    """
    if k < 1 or not gold:
        raise ValueError("positive k and nonempty gold are required")
    return len(set(ranked[:k]) & set(gold)) / k


def precision_returned_at(ranked: list[str], gold: list[str], k: int) -> float:
    """실제로 반환된 문서당 고유한 관련 부모 수, k로 제한.

    이는 검색이 사용자 앞에 놓은 문서 중 얼마나 많은 문서가 관련 있는지를 나타내는 정밀도이다. 양쪽 모두 고유한 부모를 세므로 반복된 부모가 분모를 부풀릴 수 없다. `precision_at`과 달리 점수 컷오프에 반응하며, 이는 목록을 재정렬하는 것이 아니라 단축시킨다. 아무것도 반환하지 않는 검색은 0점을 받는다.
    """
    if k < 1 or not gold:
        raise ValueError("positive k and nonempty gold are required")
    shown = set(ranked[:k])
    return len(shown & set(gold)) / len(shown) if shown else 0.0


def offered_within(ranked: list, k: int) -> set[str]:
    """처음 k개의 반환된 문서가 제공하는 ID들.

    `returned`은 각 문서당 하나의 부모 ID를 나열하지만, `returned_chunks`는 그 문서의 청크를 중첩한다. 중첩된 목록을 자르면 @k가 문서에 대한 컷오프가 되므로, 문서당 더 많은 청크를 포함해도 창을 줄이지 않는다.
    """
    return {item for entry in ranked[:k]
            for item in ([entry] if isinstance(entry, str) else entry)}


def quality_metrics(rows: list[dict], k: int) -> dict:
    if not rows:
        raise ValueError("evaluation query set is empty")
    n = len(rows)
    found = sum(len(set(r['returned'][:k]) & set(r['gold'])) for r in rows)
    relevant = sum(len(set(r['gold'])) for r in rows)
    metrics = {
        "queries": n,
        "hit_at_1": sum(hit_at(r['returned'], r['gold'], 1) for r in rows) / n,
        "precision_at_1": sum(precision_at(r['returned'], r['gold'], 1) for r in rows) / n,
        f"hit_at_{k}": sum(hit_at(r['returned'], r['gold'], k) for r in rows) / n,
        f"recall_at_{k}": sum(recall_at(r['returned'], r['gold'], k) for r in rows) / n,
        f"precision_returned_at_{k}": sum(
            precision_returned_at(r['returned'], r['gold'], k) for r in rows) / n,
        f"mean_returned_at_{k}": sum(len(r['returned'][:k]) for r in rows) / n,
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
        recovered = [sum(bool(set(group) & offered_within(r[ranked_field], k)) for group in r[field])
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
            # 인덱스가 결코 받지 못한 골드 문서는 커버리지 갭이며, 순위 실수는 아니다.
            "gold_indexed": (not coverage_known) or set(gold) <= known,
            "gold_missing_ids": sorted(set(gold) - known) if coverage_known else None,
            "review_status": row.get("review_status"),
            "returned": ranked[:k],
            "returned_chunks": [
                [hit["id"], *(passage["id"] for passage in hit.get("passages", []))]
                for hit in result.get("hits", [])[:k] if "id" in hit
            ],
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
    # 순위는 골드 문서가 실제로 인덱스에 도달한 곳에서만 판단할 수 있다.
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
    lines.append(f"Precision@1 (macro): {metrics['precision_at_1']:.4f}; "
                 f"Precision@{k} (반환분 기준, macro): {metrics[f'precision_returned_at_{k}']:.4f} "
                 f"(평균 {metrics[f'mean_returned_at_{k}']:.2f}건); "
                 f"Recall@{k} (macro): {metrics[f'recall_at_{k}']:.4f}; "
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
