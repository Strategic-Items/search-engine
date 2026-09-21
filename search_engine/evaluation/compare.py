"""읽기 전용이며, 하나의 코퍼스에 대한 프로덕션 검색 경로를 엄격하게 비교한다."""

import argparse
import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter

from opensearchpy.helpers import scan

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.evaluation.evaluate import load_queries, quality_metrics
from search_engine.indexing.indexer import file_sha256
from search_engine.indexing.documents import SearchDocument
from search_engine.search.query import MODES, retrieve


def percentile(values: list[float], fraction: float) -> float:
    """가장 가까운 순위 백분위수; 지연 시간 샘플은 JSON 보고서에 남아 있다."""
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def verify_corpus(client, alias: str, corpus: Path) -> tuple[str, dict]:
    """구체적인 인덱스를 고정하고 오래된 또는 부분적으로 임베딩된 코퍼스를 거부한다."""
    rows = [json.loads(line) for line in corpus.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    expected = {r["id"]: SearchDocument.model_validate(r).index_source() for r in rows}
    for source in expected.values():
        source.pop("embedding", None)
    if not rows or len(expected) != len(rows):
        raise ValueError("corpus must be nonempty with unique chunk IDs")
    manifest = corpus.with_name("manifest.json")
    if manifest.is_file():
        spec = json.loads(manifest.read_text(encoding="utf-8"))["datasets"]["docs"]
        if spec["count"] != len(rows) or spec["sha256"] != file_sha256(corpus):
            raise ValueError("corpus does not match docs manifest")
    concrete = ",".join(sorted(client.indices.get(index=alias)))
    if not concrete:
        raise ValueError("no indexes resolved")
    for mapping in client.indices.get_mapping(index=concrete).values():
        vector = mapping["mappings"]["properties"].get("embedding", {})
        if vector.get("type") != "knn_vector" or vector.get("dimension") != get_settings().search_embedding_dimensions:
            raise ValueError("index embedding mapping differs from configured dimensions")
    actual = {}
    for hit in scan(client, index=concrete, query={
        "query": {"match_all": {}}, "_source": {"excludes": ["embedding"]},
    }, raise_on_error=True):
        source = hit["_source"]
        if hit["_id"] in actual:
            raise ValueError("duplicate chunk ID across indexes")
        actual[hit["_id"]] = source
    if actual != expected:
        raise ValueError("live index differs from corpus; rebuild a dedicated docs index first")
    response = client.count(index=concrete, body={"query": {"exists": {"field": "embedding"}}})
    if response.get("_shards", {}).get("failed") or response["count"] != len(rows):
        raise ValueError("not every corpus chunk has an embedding")
    return concrete, {
        "path": str(corpus), "sha256": file_sha256(corpus), "chunks": len(rows),
        "parents": len({r["parent_id"] for r in expected.values()}), "indexes": concrete,
        "parent_ids": sorted({r["parent_id"] for r in expected.values()}),
    }


def verify_gold(queries: list[dict], corpus: Path, known: set[str]) -> None:
    chunks = {row["id"]: row for line in corpus.read_text(encoding="utf-8").splitlines()
              if line.strip() for row in [json.loads(line)]}
    for row in queries:
        if row.get("category") == "hsk" or set(row["gold"]) - known:
            raise ValueError(f"{row['qid']}: gold must name parents in the docs corpus")
        evidence = row.get("evidence", [])
        if {e["parent_id"] for e in evidence} != set(row["gold"]):
            raise ValueError(f"{row['qid']}: source evidence required for every gold parent")
        for item in evidence:
            chunk = chunks.get(item["chunk_id"], {})
            if (chunk.get("parent_id") != item["parent_id"] or
                    chunk.get("source_path") != item["source_path"] or
                    not item["quote"] or item["quote"] not in chunk.get("body", "")):
                raise ValueError(f"{row['qid']}: source evidence does not match corpus")
        supported_chunks = {item["chunk_id"] for item in evidence}
        for group in row.get("evidence_groups", []):
            if set(group) - supported_chunks:
                raise ValueError(f"{row['qid']}: every acceptable evidence chunk needs a verified quote")


def compare(queries: list[dict], client, index: str, *, ks: tuple[int, ...] = (1, 5, 10),
            repeats: int = 3, warmup: int = 1, as_of: date | None = None,
            query_rewrite: bool = False, modes: tuple[str, ...] = MODES) -> dict:
    if not queries or repeats < 1 or warmup < 0 or not ks or min(ks) < 1 or max(ks) > 20:
        raise ValueError("nonempty queries, positive repeats, nonnegative warmup, 1 <= k <= 20 required")
    as_of = as_of or date.today()
    depth = max(ks)
    results = {mode: [] for mode in modes}
    for _ in range(warmup):
        for mode in modes:
            retrieve(client, index, queries[0]["query"], as_of, depth, mode=mode, strict=True,
                     query_rewrite=query_rewrite)
    for position, row in enumerate(queries):
        samples = {mode: [] for mode in modes}
        rankings = {mode: [] for mode in modes}
        chunk_rankings = {mode: [] for mode in modes}
        for repeat in range(repeats):
            # 웜 캐시/순서 편향을 줄이기 위해 순서를 회전; 쿼리 임베딩은 절대 캐시하지 않음.
            offset = (position + repeat) % len(modes)
            for mode in modes[offset:] + modes[:offset]:
                start = perf_counter()
                hits = retrieve(client, index, row["query"], as_of, depth, mode=mode,
                                strict=True, query_rewrite=query_rewrite)
                samples[mode].append((perf_counter() - start) * 1000)
                rankings[mode].append([hit.parent_id for hit in hits])
                chunk_rankings[mode].append([hit.chunk_ids for hit in hits])
        for mode in modes:
            results[mode].append({
                **row, "returned": rankings[mode][0], "latency_ms": samples[mode],
                "rankings_stable": all(r == rankings[mode][0] for r in rankings[mode]),
                "repeat_rankings": rankings[mode],
                "returned_chunks": chunk_rankings[mode][0],
                "repeat_chunks": chunk_rankings[mode],
                "chunks_stable": all(ids == chunk_rankings[mode][0] for ids in chunk_rankings[mode]),
            })
    summary = {}
    for mode, rows in results.items():
        latency = [sample for row in rows for sample in row["latency_ms"]]
        categories = sorted({r.get("category", "unknown") for r in rows})
        summary[mode] = {
            "metrics": {str(k): quality_metrics(rows, k) for k in ks},
            "categories": {
                category: {str(k): quality_metrics(
                    [r for r in rows if r.get("category", "unknown") == category], k) for k in ks}
                for category in categories
            },
            "latency": {"samples": len(latency), "p50_ms": percentile(latency, .5),
                        "p95_ms": percentile(latency, .95), "mean_ms": sum(latency) / len(latency)},
            "unstable_queries": sum(not row["rankings_stable"] for row in rows),
            "queries": rows,
        }
    return {"as_of": as_of.isoformat(), "ks": list(ks), "retrieval_depth": depth,
            "lexical_candidates": min(depth * 5, 100),
            "vector_candidates": min(max(depth * 5, get_settings().search_vector_candidates), 1000),
            "repeats": repeats, "warmup_queries_per_mode": warmup,
            "query_rewrite": query_rewrite, "modes": summary}


def format_comparison(report: dict) -> str:
    lines = ["| 방식 | Precision@1 | Hit@5 | Precision@5 (반환분) | 평균 반환 | Recall@5 | Recall@10 | MRR@5 | p50 ms | p95 ms |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for mode, result in report["modes"].items():
        m5 = result["metrics"]["5"]
        m10 = result["metrics"]["10"]
        lat = result["latency"]
        lines.append(f"| {mode} | {m5['precision_at_1']:.1%} | {m5['hit_at_5']:.1%} | "
                     f"{m5['precision_returned_at_5']:.1%} | {m5['mean_returned_at_5']:.2f} | "
                     f"{m5['recall_at_5']:.1%} | {m10['recall_at_10']:.1%} | "
                     f"{m5['mrr_at_5']:.4f} | {lat['p50_ms']:.1f} | {lat['p95_ms']:.1f} |")
    if any("group_queries" in result["metrics"]["5"] for result in report["modes"].values()):
        lines.extend(["", "| 방식 | 논리 문서 Recall@5 | 논리 문서 Recall@10 | 근거 Recall@5 | 모든 근거@5 |",
                      "|---|---:|---:|---:|---:|"])
        for mode, result in report["modes"].items():
            m5, m10 = result["metrics"]["5"], result["metrics"]["10"]
            def percent(key, metrics):
                return f"{metrics[key]:.1%}" if key in metrics else "N/A"
            lines.append(f"| {mode} | {percent('group_recall_at_5', m5)} | "
                         f"{percent('group_recall_at_10', m10)} | {percent('evidence_recall_at_5', m5)} | "
                         f"{percent('evidence_all_at_5', m5)} |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queries", type=Path, nargs="?", default=Path("data/queries_docs_v1.jsonl"))
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--alias", help="Dedicated docs alias; defaults to SEARCH_DOCS_ALIAS")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--out", type=Path)
    parser.add_argument("--rewrite", action="store_true",
                        help="Also search a model-written rewrite of each query and fuse the "
                             "rankings; overrides SEARCH_QUERY_REWRITE for this run")
    parser.add_argument("--modes", default=",".join(MODES),
                        help=f"Comma-separated retrieval modes to compare. Known: {','.join(MODES)}")
    parser.add_argument("--validate-only", action="store_true",
                        help="Validate query labels and source quotes only; no OpenSearch/Ollama calls")
    args = parser.parse_args()
    modes = tuple(name.strip() for name in args.modes.split(",") if name.strip())
    if not modes or set(modes) - set(MODES):
        parser.error(f"--modes must name known modes: {','.join(MODES)}")
    queries = load_queries(args.queries)
    if args.validate_only:
        known = {json.loads(line)["parent_id"] for line in args.corpus.read_text(encoding="utf-8").splitlines()
                 if line.strip()}
        verify_gold(queries, args.corpus, known)
        print(json.dumps({"validated_queries": len(queries), "search_executed": False,
                          "queries_sha256": file_sha256(args.queries),
                          "corpus_sha256": file_sha256(args.corpus)}, ensure_ascii=False))
        return
    if args.out is None:
        parser.error("--out is required unless --validate-only is used")
    settings = get_settings()
    client = create_client(settings)
    concrete, corpus = verify_corpus(client, args.alias or settings.search_docs_alias, args.corpus)
    known = set(corpus.pop("parent_ids"))
    verify_gold(queries, args.corpus, known)
    report = compare(queries, client, concrete, repeats=args.repeats,
                     warmup=args.warmup, as_of=args.as_of, query_rewrite=args.rewrite,
                     modes=modes)
    report.update({
        "created_at": datetime.now(timezone.utc).isoformat(), "corpus": corpus,
        "queries_sha256": hashlib.sha256(args.queries.read_bytes()).hexdigest(),
        "settings": {key: getattr(settings, key) for key in (
            "ollama_embedding_model", "search_embedding_dimensions", "search_vector_candidates",
            "search_hybrid_rrf_k", "search_chunks_per_document",
            "search_query_rewrite_weight", "chat_provider", "chat_model")},
        "opensearch_version": client.info()["version"]["number"],
        "code_sha256": {"retrieval": file_sha256(Path(retrieve.__code__.co_filename)),
                        "comparison": file_sha256(Path(__file__)),
                        "metrics": file_sha256(Path(quality_metrics.__code__.co_filename))},
        "methodology": "parent-level macro recall over source-reviewed gold; single-process "
            "retrieval latency including uncached Ollama query embedding, excluding HTTP/LLM; "
            "same candidate depth for all cutoffs; strict failures (no lexical fallback); "
            "optional equivalent-parent group and final-returned-chunk evidence requirement recall, "
            "where @k cuts on documents and each document carries its returned chunks; "
            "unanswerable empty-gold queries excluded",
    })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(format_comparison(report))


if __name__ == "__main__":
    main()
