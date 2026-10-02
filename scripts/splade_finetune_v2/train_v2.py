import argparse, json, random, time
import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True); ap.add_argument("--lr", type=float, default=2e-6); ap.add_argument("--epochs", type=int, default=1)
ap.add_argument("--bs", type=int, default=8); ap.add_argument("--lam", type=float, default=1e-5); ap.add_argument("--neg_pool", type=int, default=15)
ap.add_argument("--exclude_siblings", action="store_true"); ap.add_argument("--max_examples", type=int, default=10**9); ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args(); random.seed(a.seed); torch.manual_seed(a.seed); dev = "mps"
R = "/Users/jeongbin/git/searchEngine/"; G = "/private/tmp/claude-501/-Users-jeongbin-git-searchEngine/b71074ab-b8c9-4f2a-a981-afa2931fdbd2/scratchpad/gen/"
corpus = {}
for p in (R + "data/generated/docs-v2/review-corpus/docs.jsonl", R + "data/generated/core.jsonl"):
    for l in open(p): r = json.loads(l); corpus[r["id"]] = r
ex = json.load(open(G + "train_examples.json"))[:a.max_examples]
parent = {i: r["parent_id"] for i, r in corpus.items()}
if a.exclude_siblings:
    for e in ex: e["negs"] = [n for n in e["negs"] if parent[n] != parent[e["pos"]]]
    ex = [e for e in ex if len(e["negs"]) >= 3]
    print("형제 청크 제외 후 예시", len(ex), flush=True)
M = "telepix/PIXIE-Splade-v1.5"; tok = AutoTokenizer.from_pretrained(M, trust_remote_code=True)
model = AutoModelForMaskedLM.from_pretrained(M, trust_remote_code=True).to(dev).train()
opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
steps = a.epochs * ((len(ex) + a.bs - 1) // a.bs); sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1, (s + 1) / 20) * max(0.1, 1 - s / steps))
def enc(texts, L):
    b = tok(texts, padding=True, truncation=True, max_length=L, return_tensors="pt").to(dev)
    return torch.log1p(torch.relu(model(**b).logits)).masked_fill(~b["attention_mask"].bool().unsqueeze(-1), 0).amax(1)
dt = lambda i: f"제목: {corpus[i]['title']}\n\n본문: {corpus[i]['body']}"
flops = lambda v: (v.mean(0) ** 2).sum()
step = 0; t0 = time.time(); ema = None
for ep in range(a.epochs):
    random.shuffle(ex)
    for s in range(0, len(ex), a.bs):
        batch = ex[s:s + a.bs]; qv = enc([e["q"] for e in batch], 64); ids = []
        for e in batch: ids += [e["pos"], random.choice(e["negs"][:a.neg_pool])]
        dv = enc([dt(i) for i in ids], 256); sc = qv @ dv.T
        mask = torch.zeros_like(sc, dtype=torch.bool)
        for i, e in enumerate(batch):
            tw = set(e["tw"]) | {e["pos"]}
            for k, j in enumerate(ids):
                if k != 2 * i and (j in tw or (a.exclude_siblings and parent[j] == parent[e["pos"]])): mask[i, k] = True
        ce = torch.nn.functional.cross_entropy(sc.masked_fill(mask, -1e4), torch.tensor([2 * i for i in range(len(batch))], device=dev))
        loss = ce + a.lam * (flops(qv) + flops(dv)); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step(); sched.step(); opt.zero_grad(); step += 1
        if step % 40 == 0: torch.mps.empty_cache()
        ema = ce.item() if ema is None else 0.95 * ema + 0.05 * ce.item()
        if step % 25 == 0 or step == 1: print(f"ep{ep} {step}/{steps} ce_ema={ema:.3f} {time.time()-t0:.0f}s", flush=True)
model.save_pretrained(a.out); tok.save_pretrained(a.out); print("saved", a.out, flush=True)
