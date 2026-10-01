"""PIXIE-Splade 희소 벡터를 만들어 저장한다: 문서(상위 256 term)와 질의."""
import json, sys, time, argparse
import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer
ap = argparse.ArgumentParser()
ap.add_argument("--corpus"); ap.add_argument("--queries"); ap.add_argument("--out")
ap.add_argument("--device", default="mps"); ap.add_argument("--top", type=int, default=256)
a = ap.parse_args()
M = "telepix/PIXIE-Splade-v1.5"
tok = AutoTokenizer.from_pretrained(M, trust_remote_code=True)
model = AutoModelForMaskedLM.from_pretrained(M, trust_remote_code=True).to(a.device).eval()
def enc(texts, L):
    b = tok(texts, padding=True, truncation=True, max_length=L, return_tensors="pt").to(a.device)
    with torch.inference_mode():
        w = torch.log1p(torch.relu(model(**b).logits)).masked_fill(~b["attention_mask"].bool().unsqueeze(-1), 0).amax(1).cpu()
    out = []
    for v in w:
        idx = torch.nonzero(v >= 0.01).flatten()
        pairs = sorted(((int(i), float(v[i])) for i in idx), key=lambda p: -p[1])[:a.top]
        out.append({str(i): round(x, 4) for i, x in pairs})
    return out
res = {}
if a.corpus:
    rows = [json.loads(l) for l in open(a.corpus)]
    t = time.time(); vecs = []
    for s in range(0, len(rows), 8):
        vecs += enc([f"제목: {r['title']}\n\n본문: {r['body']}" for r in rows[s:s+8]], 256)
    res["docs"] = {r["id"]: v for r, v in zip(rows, vecs)}; res["doc_seconds"] = time.time() - t
if a.queries:
    qs = [json.loads(l) for l in open(a.queries)]; qs = [q for q in qs if q.get("gold")]
    enc([qs[0]["query"]], 256)  # warmup
    lat, qv = [], {}
    for q in qs:
        t = time.time(); qv[q["qid"]] = enc([q["query"]], 256)[0]; lat.append((time.time() - t) * 1000)
    lat.sort(); res["queries"] = qv
    res["query_latency_ms"] = {"device": a.device, "p50": lat[len(lat)//2], "p95": lat[int(len(lat)*.95)-1], "n": len(lat)}
json.dump(res, open(a.out, "w"))
print(json.dumps({k: v for k, v in res.items() if k not in ("docs", "queries")}))
