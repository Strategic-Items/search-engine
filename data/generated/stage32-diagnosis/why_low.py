"""잘린 21개 근거 그룹: 정답의 검색기별 부모 순위와, 그 위를 차지한 문서의 성질 (읽기 전용)."""
import json, sys, collections
from datetime import date

sys.path.insert(0, "/Users/jeongbin/git/searchEngine")
from opensearchpy import OpenSearch
from search_engine.config import get_settings
from search_engine.search.query import build_query, build_vector_query
from search_engine.embeddings import OllamaEmbedder

S = get_settings()
client = OpenSearch(S.opensearch_url)
emb = OllamaEmbedder(S)
AS_OF = date(2026, 9, 25)
R = "/Users/jeongbin/git/searchEngine/data/generated/holdout-v1/results/"
TARGET = {  # classify_all.py 결과에서 잘린 경우(one list only / raw only)
    "docs-v2-008", "docs-v2-009", "docs-v2-017", "docs-v2-018", "docs-v2-037", "docs-v2-039",
    "docs-v2-081", "docs-v2-086", "docs-v2-097", "docs-v2-101", "docs-v2-103", "docs-v2-104",
    "docs-v2-106", "holdout-v1-001", "holdout-v1-004", "holdout-v1-028", "holdout-v1-033",
    "holdout-v1-037", "holdout-v1-050"}
SETS = {"mixed-title1-dfs-top5-audited.json": "search-holdout,search-docs-only",
        "holdout-title1-dfs-top5-audited.json": "search-holdout"}

# 부모별 전체 청크 수
sizes = collections.Counter()
for alias in ("search-holdout", "search-docs-only"):
    r = client.search(index=alias, body={"size": 0, "aggs": {"p": {"terms": {"field": "parent_id", "size": 20000}}}})
    for b in r["aggregations"]["p"]["buckets"]:
        sizes[b["key"]] = b["doc_count"]


def parent_rank(hits, gp):
    seen = []
    for i, h in enumerate(hits, 1):
        p = h["_source"].get("parent_id")
        if p not in seen:
            seen.append(p)
        if p in gp:
            return i, len(seen), seen[:-1]
    return None, None, seen


rows = []
for f, alias in SETS.items():
    opts = {"search_type": "dfs_query_then_fetch"} if "," in alias else {}
    for q in json.load(open(R + f))["queries"]:
        if q["qid"] not in TARGET:
            continue
        got = {c for g in q["returned_chunks"] for c in g}
        vec = emb.embed_query(q["query"])
        lex = client.search(index=alias, body={"query": build_query(q["query"], AS_OF)}, size=300, **opts)["hits"]["hits"]
        vh = client.search(index=alias, body={"query": build_vector_query(vec, AS_OF, 300, q["query"])}, size=300)["hits"]["hits"]
        for g in q["evidence_groups"]:
            if got & set(g):
                continue
            gp = {c.split("#")[0] for c in g}
            row = {"qid": q["qid"], "query": q["query"], "gold": sorted(gp),
                   "gold_size": max(sizes[p] for p in gp)}
            for name, hits in (("bm25", lex), ("vector", vh)):
                crank, prank, above = parent_rank(hits, gp)
                row[name] = {"chunk_rank": crank, "parent_rank": prank,
                             "top_score": hits[0]["_score"],
                             "gold_score": next((h["_score"] for h in hits if h["_source"].get("parent_id") in gp), None),
                             "above": [(p, sizes[p]) for p in above[:8]],
                             "chunks_above": crank - 1 if crank else len(hits),
                             "chunks_above_from_top3_parents": 0}
                if crank:
                    c = collections.Counter(h["_source"].get("parent_id") for h in hits[:crank - 1])
                    row[name]["chunks_above_from_top3_parents"] = sum(n for _, n in c.most_common(3))
                    row[name]["top_titles"] = [h["_source"].get("title", "")[:40] for h in hits[:3]]
            rows.append(row)

json.dump(rows, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
for r in rows:
    print("=====", r["qid"], r["query"][:70])
    print("   gold", r["gold"][0][:60], "chunks", r["gold_size"])
    for n in ("bm25", "vector"):
        x = r[n]
        print(f"   {n:6s} chunk#{x['chunk_rank']} parent#{x['parent_rank']} score {x['gold_score']} / top {x['top_score']:.3f}"
              f" | chunks above from 3 parents: {x['chunks_above_from_top3_parents']}/{x['chunks_above']}")
        print("          above:", [(p[:30], s) for p, s in x["above"][:5]])
