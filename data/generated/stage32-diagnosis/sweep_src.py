"""하이브리드 최종 비율 컷오프만 바꿔 204문항(+동결 검증셋)을 재검색한다. 판정자 끔, 읽기 전용."""
import json, os, sys
from datetime import date

os.environ["SEARCH_ANSWERABILITY_JUDGE"] = "false"
os.environ["SEARCH_CHUNK_FILTER"] = "false"
os.environ["SEARCH_QUERY_REWRITE"] = "false"
os.environ["SEARCH_RERANK_CHUNKS"] = "false"
sys.path.insert(0, "/Users/jeongbin/git/searchEngine")
from opensearchpy import OpenSearch
from search_engine.config import get_settings
from search_engine.search import query as Q
from search_engine.embeddings import OllamaEmbedder

S = get_settings()
client = OpenSearch(S.opensearch_url)
DUP = json.load(open(os.path.dirname(os.path.abspath(__file__)) + "/faq_dup_map.json"))
MERGE = {"on": False}
_search = client.search


def search(*a, **kw):
    """FAQ 첨부 사본의 parent_id를 원 FAQ로 바꿔, 융합에서 한 문서로 세게 한다."""
    resp = _search(*a, **kw)
    if MERGE["on"]:
        for h in resp["hits"]["hits"]:
            p = h["_source"].get("parent_id")
            if p in DUP:
                h["_source"]["parent_id"] = DUP[p]
    return resp


client.search = search
# 127은 2026-09-29에 질문을 고쳤다. 저장 결과의 옛 문구 대신 현재 질의셋의 문구를 쓴다.
CURRENT = {json.loads(l)["qid"]: json.loads(l)["query"]
           for l in open("/Users/jeongbin/git/searchEngine/data/queries_docs_v2.jsonl") if l.strip()}


class Cached:
    def __init__(self):
        self.e, self.c = OllamaEmbedder(S), {}

    def embed_query(self, t):
        if t not in self.c:
            self.c[t] = self.e.embed_query(t)
        return self.c[t]


emb = Cached()
AS_OF = date(2026, 9, 25)
G = "/Users/jeongbin/git/searchEngine/data/generated/"
SETS = [
    ("docs135", G + "holdout-v1/results/mixed-title1-dfs-top5-audited.json", "search-holdout,search-docs-only"),
    ("holdout69", G + "holdout-v1/results/holdout-title1-dfs-top5-audited.json", "search-holdout"),
]
extra = sys.argv[2:] if len(sys.argv) > 2 else []
for spec in extra:  # name=path=alias  (queries jsonl or result json)
    n, p, a = spec.split("=")
    SETS.append((n, p, a))


def load(path):
    if path.endswith(".jsonl"):
        return [json.loads(l) for l in open(path) if l.strip()]
    return json.load(open(path))["queries"]


def score(q, hits):
    ret = [h.parent_id for h in hits]
    chunks = {h.id for h in hits} | {p.id for h in hits for p in (h.passages or [])}
    gp = {p for g in q.get("gold_groups") or [] for p in g} | set(q.get("gold") or [])
    ev = q.get("evidence_groups") or []
    rec = sum(1 for g in ev if chunks & set(g)) / len(ev) if ev else None
    top1 = bool(ret) and ret[0] in gp
    hit5 = bool(set(ret) & gp)
    dprec = sum(1 for p in ret if p in gp) / len(ret) if ret else 0.0
    cprec = (sum(1 for c in chunks if any(c in g for g in ev)) / len(chunks)) if chunks and ev else 0.0
    return rec, top1, hit5, dprec, cprec, len(ret), len(chunks)


variants = sys.argv[1].split(",")  # base, prank, notrim, prank+notrim, ...
_orig_rrf = Q._rrf
_orig_split = Q.split_source_clause


def parent_rank_rrf(ranked_lists, rrf_k):
    """같은 융합이되, 순위를 청크 위치가 아니라 목록 안의 부모 순서로 센다."""
    squeezed = []
    for hits, weight, retriever in ranked_lists:
        seen, firsts = set(), []
        for hit in hits:
            p = hit["_source"].get("parent_id") or hit["_id"]
            if p not in seen:
                seen.add(p)
                firsts.append(hit)
        squeezed.append((firsts, weight, retriever))
    return _orig_rrf(squeezed, rrf_k)
out = {}
for name, path, alias in SETS:
    qs = [q for q in load(path) if q.get("answerable", True) is not False]
    for r in variants:
        MERGE["on"] = False
        Q.split_source_clause = (lambda q: (None, q)) if r == "nosrc" else _orig_split
        Q._rrf = parent_rank_rrf if "prank" in r else _orig_rrf
        S.search_fusion_trim_bm25 = 0.0 if "notrim" in r else 0.90
        S.search_fusion_trim_vector = 0.0 if "notrim" in r else 0.97
        S.search_cutoff_ratio_hybrid = float(r.split("cut")[1]) if "cut" in r else 0.90
        per = []
        for q in qs:
            text = CURRENT.get(q["qid"], q["query"]) if name == "docs135" else q["query"]
            hits = Q.retrieve(client, alias, text, AS_OF, 5, emb, mode="hybrid")
            per.append((q["qid"], score(q, hits), [h.parent_id for h in hits]))
        recs = [s[0] for _, s, _ in per if s[0] is not None]
        n = len(per)
        m = lambda i: sum(s[i] for _, s, _ in per) / n
        print(f"{name:10s} {r:20s} n={n} evRecall@5={sum(recs)/len(recs):.3f} top1={m(1):.3f} "
              f"hit@5={m(2):.3f} docPrec={m(3):.3f} chunkPrec(lb)={m(4):.3f} docs={m(5):.2f} chunks={m(6):.2f}",
              flush=True)
        out[f"{name}@{r}"] = per
json.dump(out, open(os.path.dirname(os.path.abspath(__file__)) + "/src_out.json", "w"), ensure_ascii=False)
