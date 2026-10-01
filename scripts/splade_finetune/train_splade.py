import json, re, random, sys, time, argparse
import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer
from synth_queries import Q

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--lr", type=float, default=5e-6)
ap.add_argument("--epochs", type=int, default=3)
ap.add_argument("--bs", type=int, default=4)
ap.add_argument("--lam_q", type=float, default=3e-4)
ap.add_argument("--lam_d", type=float, default=1e-4)
ap.add_argument("--neg_pool", type=int, default=30)
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()
random.seed(a.seed); torch.manual_seed(a.seed)

REPO = "/Users/jeongbin/git/searchEngine/"
corpus = [json.loads(l) for l in open(REPO + "data/generated/docs-v2/review-corpus/docs.jsonl")]
sel = json.load(open("train_chunks.json"))
M = "telepix/PIXIE-Splade-v1.5"
tok = AutoTokenizer.from_pretrained(M, trust_remote_code=True)
model = AutoModelForMaskedLM.from_pretrained(M, trust_remote_code=True).to("mps")
dev = "mps"

def norm(t):
    t = re.sub(r"<[^>]+>|&lt;|&gt;|[\s#*|\\]", "", t)
    return t
def shingles(t, k=30, step=10):
    return {t[i:i+k] for i in range(0, max(1, len(t) - k), step)}
ntext = [norm(r["body"]) for r in corpus]
id2i = {r["id"]: i for i, r in enumerate(corpus)}
sh = [shingles(t) for t in ntext]

def doc_text(r): return f"제목: {r['title']}\n\n본문: {r['body']}"
def enc(texts, L, grad=True):
    b = tok(texts, padding=True, truncation=True, max_length=L, return_tensors="pt").to(dev)
    w = torch.log1p(torch.relu(model(**b).logits)).masked_fill(~b["attention_mask"].bool().unsqueeze(-1), 0)
    return w.amax(1)

# 1) base-model sparse vectors for hard-negative mining
model.eval()
t0 = time.time(); D = []
with torch.no_grad():
    for s in range(0, len(corpus), 8):
        D.append(enc([doc_text(r) for r in corpus[s:s+8]], 256).cpu())
D = torch.cat(D); print("corpus encoded", D.shape, round(time.time() - t0), "s", flush=True)

def twins_of(i):  # same text in another format: share >=1 shingle (negatives) 
    return {j for j in range(len(corpus)) if j != i and sh[i] & sh[j]}

import glob
ev = set()
for f in glob.glob(REPO + "data/queries_docs_v2*.jsonl"):
    for l in open(f):
        q = json.loads(l)
        for g in q.get("evidence_groups") or []: ev.update(g)
        for e in q.get("evidence") or []: ev.add(e["chunk_id"])
banned = {id2i[c] for c in ev if c in id2i}
banned |= {j for i in list(banned) for j in twins_of(i)}  # same text in other formats
print("banned negatives (eval evidence + twins):", len(banned), flush=True)
examples = []
with torch.no_grad():
    for idx, qs in Q.items():
        pi = id2i[sel[idx]["id"]]
        tw = twins_of(pi) | {pi}
        for q in qs:
            qv = enc([q], 64).cpu()[0]
            sc = D @ qv
            order = torch.argsort(sc, descending=True).tolist()
            pool = [j for j in order[:a.neg_pool + len(tw) + len(banned) + 5] if j not in tw and j not in banned][:a.neg_pool]
            examples.append({"q": q, "pos": pi, "tw": tw, "pool": pool})
print("examples", len(examples), flush=True)
json.dump([{"q": e["q"], "pos": corpus[e["pos"]]["id"], "twins": [corpus[j]["id"] for j in e["tw"]],
            "neg_pool": [corpus[j]["id"] for j in e["pool"][:5]]} for e in examples],
          open(a.out + ".examples.json", "w"), ensure_ascii=False, indent=1)

# 2) train
model.train()
opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
steps = a.epochs * ((len(examples) + a.bs - 1) // a.bs)
sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1, (s + 1) / 5) * max(0.1, 1 - s / steps))
step = 0
def flops(v): return (v.mean(0) ** 2).sum()
for ep in range(a.epochs):
    random.shuffle(examples)
    for s in range(0, len(examples), a.bs):
        batch = examples[s:s + a.bs]
        qv = enc([e["q"] for e in batch], 64)
        dids = []
        for e in batch:
            dids.append(e["pos"]); dids.append(random.choice(e["pool"]))
        dv = enc([doc_text(corpus[j]) for j in dids], 256)
        sc = qv @ dv.T
        mask = torch.zeros_like(sc, dtype=torch.bool)  # twins of a query's positive are not negatives
        for i, e in enumerate(batch):
            for k, j in enumerate(dids):
                if k != 2 * i and (j in e["tw"] or j == e["pos"]): mask[i, k] = True
        sc = sc.masked_fill(mask, -1e4)
        ce = torch.nn.functional.cross_entropy(sc, torch.tensor([2 * i for i in range(len(batch))], device=dev))
        fq, fd = flops(qv), flops(dv)
        loss = ce + a.lam_q * fq + a.lam_d * fd
        loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step(); opt.zero_grad(); step += 1
        if step % 5 == 0 or step == 1:
            print(f"ep{ep} step{step}/{steps} ce={ce.item():.3f} flops_q={fq.item():.1f} flops_d={fd.item():.1f}", flush=True)
model.save_pretrained(a.out); tok.save_pretrained(a.out); print("saved", a.out)
