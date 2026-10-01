"""holdout-small 벡터를 복제해 84k 규모 실험 인덱스를 만들고 검색 지연과 크기를 잰다(합성 규모 추정)."""
import json, sys, time
from opensearchpy.helpers import bulk
from search_engine.client import create_client
from search_engine.config import get_settings
S = sys.argv[1]; index = "exp-splade-synth84k-v1"; copies = 39
c = create_client(get_settings())
if c.indices.exists(index=index): c.indices.delete(index=index)
c.indices.create(index=index, body={"settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {"properties": {"parent_id": {"type": "keyword"}, "splade": {"type": "rank_features"}}}})
sp = json.load(open(f"{S}/sp-hs.json")); docs = sp["docs"]; qv = sp["queries"]
def gen():
    for k in range(copies):
        for i, v in docs.items():
            yield {"_index": index, "_id": f"{i}#c{k}", "_source": {"parent_id": i.split("#")[0], "splade": {f"t{t}": w for t, w in v.items()}}}
t = time.time(); bulk(c, gen(), chunk_size=500, request_timeout=120)
c.indices.refresh(index=index); c.indices.forcemerge(index=index, max_num_segments=1, request_timeout=900)
sec = time.time() - t
st = c.indices.stats(index=index, metric="store,docs")["indices"][index]["primaries"]
def q(v): return {"size": 100, "_source": False, "query": {"neural_sparse": {"splade": {"query_tokens": {f"t{k}": x for k, x in v.items()}}}}}
c.search(index=index, body=q(next(iter(qv.values()))))
lat, took = [], []
for rep in range(3):
    for v in qv.values():
        t = time.time(); r = c.search(index=index, body=q(v)); lat.append((time.time() - t) * 1000); took.append(r["took"])
lat.sort(); took.sort(); n = len(lat)
print(json.dumps({"chunks": st["docs"]["count"], "store_MB": round(st["store"]["size_in_bytes"] / 1e6, 1), "build_seconds": round(sec),
                  "client_ms": {"p50": round(lat[n // 2], 1), "p95": round(lat[int(n * .95) - 1], 1)}, "took_ms": {"p50": took[n // 2], "p95": took[int(n * .95) - 1]}, "samples": n}))
