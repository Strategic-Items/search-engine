"""근거를 놓친 질의를 '정답이 어느 목록까지 살아남았는가'로 분류한다 (읽기 전용)."""
import json, os, sys
from datetime import date
from collections import Counter

sys.path.insert(0, "/Users/jeongbin/git/searchEngine")
from opensearchpy import OpenSearch
from search_engine.config import get_settings
from search_engine.search.query import build_query, build_vector_query, _ratio_cut
from search_engine.embeddings import OllamaEmbedder

S = get_settings()
client = OpenSearch(S.opensearch_url)
emb = OllamaEmbedder(S)
AS_OF = date(2026, 9, 25)
R = "/Users/jeongbin/git/searchEngine/data/generated/holdout-v1/results/"
SETS = {"docs": ("mixed-title1-dfs-top5-audited.json", "search-holdout,search-docs-only"),
        "holdout": ("holdout-title1-dfs-top5-audited.json", "search-holdout")}


def parents(hits):
    return {h["_source"].get("parent_id") for h in hits}


rows = []
for name, (f, alias) in SETS.items():
    opts = {"search_type": "dfs_query_then_fetch"} if "," in alias else {}
    for q in json.load(open(R + f))["queries"]:
        got = {c for g in q["returned_chunks"] for c in g}
        groups = q["evidence_groups"]
        missed = [g for g in groups if not got & set(g)]
        if not missed:
            continue
        lex = client.search(index=alias, body={"query": build_query(q["query"], AS_OF)},
                            size=25, **opts)["hits"]["hits"]
        vec = client.search(index=alias, body={"query": build_vector_query(
            emb.embed_query(q["query"]), AS_OF, 50, q["query"])}, size=50)["hits"]["hits"]
        lf = [h for h in lex if h["_score"] >= S.score_floor("bm25")]
        vf = [h for h in vec if h["_score"] >= S.score_floor("vector")]
        lt, vt = _ratio_cut(lf, S.fusion_trim_ratio("bm25")), _ratio_cut(vf, S.fusion_trim_ratio("vector"))
        for g in missed:
            gp = {c.split("#")[0] for c in g}
            in_lt, in_vt = bool(gp & parents(lt)), bool(gp & parents(vt))
            in_lr, in_vr = bool(gp & parents(lf)), bool(gp & parents(vf))
            # 같은 근거 그룹의 서로 다른 부모가 각 목록에 따로 잡혔는가(사본 분산)
            split = in_lt and in_vt and not (gp & parents(lt) & parents(vt))
            if in_lt and in_vt and not split:
                kind = "both-trimmed: fused rank/window"
            elif split:
                kind = "split across duplicate parents"
            elif in_lt or in_vt:
                other_raw = in_vr if in_lt else in_lr
                kind = ("one list only (other raw has it, trimmed)" if other_raw
                        else "one list only (other retriever misses)")
            elif in_lr or in_vr:
                kind = "raw only, trimmed out of both"
            else:
                kind = "not in candidates"
            rows.append((name, q["qid"], kind, sorted(gp)[:2]))

c = Counter(k for _, _, k, _ in rows)
print(len(rows), "missed evidence groups")
for k, v in c.most_common():
    print(f"  {v:3d}  {k}")
for r in rows:
    print(r[0], r[1], "|", r[2], "|", r[3])
