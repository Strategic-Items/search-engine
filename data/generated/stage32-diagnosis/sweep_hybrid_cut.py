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
    gp = {p for g in q.get("gold_groups") or [q["gold"]] for p in g}
    ev = q.get("evidence_groups") or []
    rec = sum(1 for g in ev if chunks & set(g)) / len(ev) if ev else None
    top1 = bool(ret) and ret[0] in gp
    hit5 = bool(set(ret) & gp)
    dprec = sum(1 for p in ret if p in gp) / len(ret) if ret else 0.0
    cprec = (sum(1 for c in chunks if any(c in g for g in ev)) / len(chunks)) if chunks and ev else 0.0
    return rec, top1, hit5, dprec, cprec, len(ret), len(chunks)


ratios = [float(x) for x in sys.argv[1].split(",")]
out = {}
for name, path, alias in SETS:
    qs = [q for q in load(path) if q.get("answerable", True) is not False]
    for r in ratios:
        S.search_cutoff_ratio_hybrid = r
        per = []
        for q in qs:
            hits = Q.retrieve(client, alias, q["query"], AS_OF, 5, emb, mode="hybrid")
            per.append((q["qid"], score(q, hits), [h.parent_id for h in hits]))
        recs = [s[0] for _, s, _ in per if s[0] is not None]
        n = len(per)
        m = lambda i: sum(s[i] for _, s, _ in per) / n
        print(f"{name:10s} cut={r:.2f} n={n} evRecall@5={sum(recs)/len(recs):.3f} top1={m(1):.3f} "
              f"hit@5={m(2):.3f} docPrec={m(3):.3f} chunkPrec(lb)={m(4):.3f} docs={m(5):.2f} chunks={m(6):.2f}",
              flush=True)
        out[f"{name}@{r}"] = per
json.dump(out, open(os.path.dirname(__file__) + "/sweep_out.json", "w"), ensure_ascii=False)
