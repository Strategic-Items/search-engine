import sys, json, time, numpy as np, torch
from sentence_transformers import SentenceTransformer
name, tag, corpus, queries, out = sys.argv[1:6]
use_prompt = name.startswith("telepix/")
m = SentenceTransformer(name, device="mps"); m.max_seq_length = 512
rows = [json.loads(l) for l in open(corpus)]
qs = [q for q in map(json.loads, open(queries)) if q.get("gold")]
t = time.time()
d = m.encode([f"제목: {r['title']}\n\n본문: {r['body']}".strip() for r in rows], batch_size=8, normalize_embeddings=True, convert_to_numpy=True)
ds = time.time() - t
lat = []
m.encode(["워밍업"], prompt_name="query" if use_prompt else None)
q = []
for x in qs:
    t = time.time(); q.append(m.encode([x["query"]], prompt_name="query" if use_prompt else None, normalize_embeddings=True, convert_to_numpy=True)[0]); lat.append((time.time() - t) * 1000)
lat.sort()
np.savez(out, docs=d, queries=np.stack(q), ids=np.array([r["id"] for r in rows]), qids=np.array([x["qid"] for x in qs]))
print(tag, "dim", d.shape[1], "doc_s", round(ds), "q_p50_ms", round(lat[len(lat)//2], 1))
