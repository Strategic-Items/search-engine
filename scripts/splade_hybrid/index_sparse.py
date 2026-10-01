"""실험 인덱스에 SPLADE 희소 벡터를 색인하고 검색 지연·크기·순위를 잰다. 운영 인덱스·별칭은 건드리지 않는다."""
import json, sys, time
from opensearchpy.helpers import bulk
from search_engine.client import create_client
from search_engine.config import get_settings
index, corpus, sp, queries, out = sys.argv[1:6]
c = create_client(get_settings())
assert index.startswith("exp-"), "experimental indexes only"
if c.indices.exists(index=index): c.indices.delete(index=index)
c.indices.create(index=index, body={
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {"properties": {"parent_id": {"type": "keyword"}, "splade": {"type": "rank_features"}}}})
rows = [json.loads(l) for l in open(corpus)]
vec = json.load(open(sp))
t = time.time()
bulk(c, ({"_index": index, "_id": r["id"], "_source": {"parent_id": r["parent_id"], "splade": {f"t{k}": v for k, v in vec["docs"][r["id"]].items()}}} for r in rows), chunk_size=200)
c.indices.refresh(index=index); c.indices.forcemerge(index=index, max_num_segments=1)
idx_seconds = time.time() - t
st = c.indices.stats(index=index, metric="store,docs")["indices"][index]["primaries"]
qv = json.load(open(queries))["queries"] if "queries" in json.load(open(queries)) else None
qs = {q["qid"]: q for q in map(json.loads, open(sys.argv[6])) if q.get("gold")}
lat, took, res = [], [], []
def run(q):
    body = {"size": 100, "_source": False, "query": {"neural_sparse": {"splade": {"query_tokens": {f"t{k}": v for k, v in qv[q["qid"]].items()}}}}}
    t = time.time(); r = c.search(index=index, body=body); return (time.time() - t) * 1000, r["took"], r["hits"]["hits"]
run(next(iter(qs.values())))
for qid, q in qs.items():
    ms, tk, hits = run(q); lat.append(ms); took.append(tk)
    seen, ranked = set(), []
    for h in hits:
        p = c.get(index=index, id=h["_id"], _source=["parent_id"])["_source"]["parent_id"]
        if p not in seen: seen.add(p); ranked.append((p, h["_score"]))
    res.append({"qid": qid, "gold": q["gold"], "ranked": ranked[:25]})
lat.sort(); took.sort()
def r97(rows_, ratio):
    n = h = mrr = ret = rel = 0
    for r in rows_:
        top = r["ranked"][0][1]; kept = [p for p, s in r["ranked"][:5] if s >= top * ratio]; g = set(r["gold"])
        n += 1; h += any(p in g for p in kept); ret += len(kept); rel += sum(p in g for p in kept)
        mrr += next((1 / i for i, p in enumerate(kept, 1) if p in g), 0)
    return {"ratio": ratio, "P@1": sum(r["ranked"][0][0] in set(r["gold"]) for r in rows_) / n, "hit@5": h / n, "retP": rel / ret, "mean_ret": ret / n, "mrr": mrr / n}
summary = {"index": index, "chunks": st["docs"]["count"], "store_bytes": st["store"]["size_in_bytes"], "index_seconds": idx_seconds,
           "search_ms_client": {"p50": lat[len(lat)//2], "p95": lat[int(len(lat)*.95)-1]}, "took_ms": {"p50": took[len(took)//2], "p95": took[int(len(took)*.95)-1]},
           "quality": [r97(res, x) for x in (0.0, 0.97)]}
json.dump({"summary": summary, "results": res}, open(out, "w"), ensure_ascii=False)
print(json.dumps(summary, ensure_ascii=False, indent=1))
