"""OpenSearch 다국어 sparse 모델(문서: SPLADE, 질의: 토큰+IDF 조회)을 evaluate_splade.py와 같은 방식으로 평가한다."""
import argparse, json, time
from collections import defaultdict
import torch
from sentence_transformers.sparse_encoder import SparseEncoder
ap = argparse.ArgumentParser()
ap.add_argument("--corpus"); ap.add_argument("--queries"); ap.add_argument("--out")
ap.add_argument("--max-length", type=int, default=256); ap.add_argument("--prune", type=float, default=0.1)
ap.add_argument("--top-terms", type=int, default=256); ap.add_argument("--device", default="mps"); ap.add_argument("--bs", type=int, default=8)
a = ap.parse_args()
rows = lambda p: [json.loads(l) for l in open(p) if l.strip()]
corpus = rows(a.corpus); queries = [q for q in rows(a.queries) if q.get("gold")]
model = SparseEncoder("opensearch-project/opensearch-neural-sparse-encoding-multilingual-v1", device=a.device)
model.max_seq_length = a.max_length
def todicts(t, prune):
    t = t.to("cpu").coalesce() if t.is_sparse else t.to("cpu").to_sparse().coalesce()
    idx, val = t.indices(), t.values(); out = [dict() for _ in range(t.shape[0])]
    for r, c, v in zip(idx[0].tolist(), idx[1].tolist(), val.tolist()): out[r][c] = v
    res = []
    for d in out:
        if not d: res.append(d); continue
        m = max(d.values()) * prune
        kept = sorted(((c, v) for c, v in d.items() if v >= m), key=lambda p: -p[1])[:a.top_terms]
        res.append(dict(kept))
    return res
texts = [f"제목: {r.get('title','')}\n\n본문: {r.get('body','')}" for r in corpus]
t0 = time.time(); dv = []
for s in range(0, len(texts), 64): dv += todicts(model.encode_document(texts[s:s+64], batch_size=a.bs, convert_to_sparse_tensor=True), a.prune)
doc_seconds = time.time() - t0
lat = []; qv = []
model.encode_query(queries[0]["query"])
for q in queries:
    t = time.time(); qv += todicts(model.encode_query([q["query"]], convert_to_sparse_tensor=True), 0.0); lat.append((time.time() - t) * 1000)
lat.sort()
post = defaultdict(list)
for i, v in enumerate(dv):
    for tk, w in v.items(): post[tk].append((i, w))
rankings = []
for q, v in zip(queries, qv):
    cs = defaultdict(float)
    for tk, qw in v.items():
        for i, dw in post.get(tk, ()): cs[i] += qw * dw
    ps = {}
    for i, s in cs.items():
        p = corpus[i].get("parent_id") or corpus[i]["id"]; ps[p] = max(s, ps.get(p, 0.0))
    ranked = sorted(ps.items(), key=lambda x: (-x[1], x[0])); cr = sorted(cs.items(), key=lambda x: (-x[1], corpus[x[0]]["id"]))
    rankings.append({"qid": q["qid"], "gold": q["gold"], "ranked": [{"parent_id": p, "score": s} for p, s in ranked[:25]],
                     "chunk_ranked": [{"chunk_id": corpus[i]["id"], "parent_id": corpus[i].get("parent_id") or corpus[i]["id"], "score": s} for i, s in cr[:100]]})
sweeps = []
for ratio in (0.0, 0.80, 0.90, 0.95, 0.97, 0.99, 1.0):
    ret = []
    for r in rankings:
        top = r["ranked"][0]["score"] if r["ranked"] else 0.0
        ret.append(([h["parent_id"] for h in r["ranked"][:5] if h["score"] >= top * ratio], set(r["gold"])))
    rel = sum(sum(p in g for p in k) for k, g in ret); cnt = sum(len(k) for k, _ in ret)
    rr = lambda k, g: next((1 / i for i, p in enumerate(k, 1) if p in g), 0.0)
    sweeps.append({"ratio": ratio, "precision_at_1": sum(bool(k) and k[0] in g for k, g in ret) / len(ret), "hit_at_5": sum(any(p in g for p in k) for k, g in ret) / len(ret),
                   "precision_returned": rel / cnt if cnt else 0.0, "mean_returned": cnt / len(ret), "mrr_at_5": sum(rr(k, g) for k, g in ret) / len(ret)})
json.dump({"model": "opensearch-neural-sparse-encoding-multilingual-v1", "prune": a.prune, "corpus_chunks": len(corpus), "queries": len(queries),
           "elapsed_seconds": doc_seconds, "mean_document_terms": sum(map(len, dv)) / len(dv), "mean_query_terms": sum(map(len, qv)) / len(qv),
           "query_latency_ms": {"p50": lat[len(lat) // 2], "p95": lat[int(len(lat) * .95) - 1], "device": a.device},
           "sweeps": sweeps, "results": rankings}, open(a.out, "w"), ensure_ascii=False)
print(json.dumps({"terms_doc": sum(map(len, dv)) / len(dv), "terms_q": sum(map(len, qv)) / len(qv), "doc_s": round(doc_seconds), "q_p50_ms": round(lat[len(lat)//2], 1)}))
for s in sweeps:
    if s["ratio"] in (0.0, 0.95, 0.97): print({k: round(v, 3) for k, v in s.items()})
