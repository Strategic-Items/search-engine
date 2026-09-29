"""어휘 검색 장치를 하나씩 켜거나 빼고 같은 질의를 다시 검색해 비교한다 (34단계, 읽기 전용).

`search-evaluate`가 만든 결과 파일의 질의와 정답표를 그대로 쓴다. 판정자·재작성·리랭커·LLM 청크 필터는 끄고,
현재 코드에서 `build_query`의 결과만 바꾼다. 장치마다 결과가 달라진 질문 수와 지표를 함께 낸다.

    .venv/bin/python scripts/ablate_lexical_devices.py --report data/generated/holdout-v1/results/mixed-title1-dfs-top5-audited.json \\
        --datasets core,docs --alias search-holdout
"""
import argparse
import copy
from datetime import date
import json
from pathlib import Path
from unittest.mock import patch

from search_engine.client import create_client
from search_engine.config import Settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.evaluation.evaluate import quality_metrics
from search_engine.search import query as Q

STANDARD_FIELDS = ["title^1", "body", "title.standard^1.5", "body.standard^0.5"]
ORIGINAL = Q.build_query


def _walk(node, edit):
    if isinstance(node, dict):
        edit(node)
        for value in node.values():
            _walk(value, edit)
    elif isinstance(node, list):
        for value in node:
            _walk(value, edit)


def variant_query(name: str):
    """장치 하나를 바꾼 `build_query`를 돌려준다."""
    def build(*args, **kwargs):
        body = copy.deepcopy(ORIGINAL(*args, **kwargs))

        def edit(node):
            multi = node.get("multi_match")
            if multi and name == "standard_on":
                multi["fields"] = STANDARD_FIELDS
            if multi and name == "synonyms_off":
                multi["analyzer"] = "korean_nori"
            functions = node.get("functions")
            if functions is not None:
                text = lambda f: json.dumps(f, ensure_ascii=False)
                if name == "edition_off":
                    node["functions"] = [f for f in functions if '"superseded_by"' not in text(f)]
                if name == "hint_off":
                    node["functions"] = [f for f in functions if '"range": {"period_hint"' not in text(f)]
            if name == "effective_off" and isinstance(node.get("filter"), list):
                node["filter"] = [f for f in node["filter"]
                                  if "effective_from" not in json.dumps(f) and "effective_to" not in json.dumps(f)]
        _walk(body, edit)
        return body
    return build


VARIANTS = ["current", "standard_on", "synonyms_off", "edition_off", "hint_off", "effective_off"]
KEYS = [("evidence_hit_at_5", "청크 Hit"), ("evidence_recall_at_5", "청크 Recall"), ("evidence_mrr_at_5", "청크 MRR"),
        ("evidence_precision_at_5", "청크 Precision"), ("mean_chunks_at_5", "평균 청크"),
        ("hit_at_5", "문서 Hit"), ("recall_at_5", "문서 Recall"), ("mrr_at_5", "문서 MRR"),
        ("precision_returned_at_5", "문서 Precision"), ("mean_returned_at_5", "평균 문서")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, help="search-evaluate 결과 JSON (질의와 정답표를 읽는다)")
    parser.add_argument("--datasets", default="core,docs", choices=["core,docs", "docs", "core"])
    parser.add_argument("--alias", default=None, help="core 별칭 (SEARCH_INDEX_ALIAS)")
    parser.add_argument("--variants", nargs="*", default=VARIANTS)
    parser.add_argument("--category-prefix", default="", help="예: identifier 로 식별자 질문만")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    overrides = {"search_document_datasets": args.datasets, "search_hsk_enabled": False,
                 "search_answerability_judge": False, "search_chunk_filter": False,
                 "search_rerank_chunks": False, "search_query_rewrite": False}
    if args.alias:
        overrides["search_index_alias"] = args.alias
    settings = Settings(**overrides)
    client, embedder = create_client(settings), OllamaEmbedder(settings)
    rows = [r for r in json.loads(Path(args.report).read_text())["queries"]
            if r.get("category", "").startswith(args.category_prefix)]
    results = {}
    for name in args.variants:
        patches = [patch("search_engine.search.query.get_settings", return_value=settings)]
        if name != "current":
            patches.append(patch.object(Q, "build_query", variant_query(name)))
        for p in patches:
            p.start()
        try:
            out = []
            for row in rows:
                hits = Q.retrieve(client, settings.document_aliases, row["query"], date.today(), 5, embedder=embedder,
                                  mode="hybrid", strict=True, answerability=False, query_rewrite=False)
                out.append(dict(row, returned=[h.parent_id for h in hits], returned_chunks=[h.chunk_ids for h in hits]))
        finally:
            for p in patches:
                p.stop()
        results[name] = out
    base = results.get("current")
    summary = {}
    for name, out in results.items():
        metrics = quality_metrics(out, 5)
        changed = 0 if base is None else sum(
            a["returned"] != b["returned"] or a["returned_chunks"] != b["returned_chunks"] for a, b in zip(base, out))
        summary[name] = {"changed_queries": changed, **{label: metrics.get(key) for key, label in KEYS}}
        print(f"{name:14} 달라진 질문 {changed:3}  " + " ".join(f"{metrics[key]:.3f}" for key, _ in KEYS))
    if args.output:
        Path(args.output).write_text(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
