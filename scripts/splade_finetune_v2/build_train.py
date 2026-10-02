"""검증 통과 질의를 기준 모델로 채점해 난이도를 고르고, 정답 사본·평가 근거를 뺀 hard negative를 붙인다."""
import glob, json, re, random, sys, time, collections
import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer
R = "/Users/jeongbin/git/searchEngine/"; G = "/private/tmp/claude-501/-Users-jeongbin-git-searchEngine/b71074ab-b8c9-4f2a-a981-afa2931fdbd2/scratchpad/gen/"
random.seed(11); dev = "mps"
rows = []
for p in (R + "data/generated/docs-v2/review-corpus/docs.jsonl", R + "data/generated/core.jsonl"):
    rows += [json.loads(l) for l in open(p)]
id2i = {r["id"]: i for i, r in enumerate(rows)}
def norm(t): return re.sub(r"<[^>]+>|&lt;|&gt;|[\s#*|\\\-:]", "", t)
def sh(t, k=30, step=10): return {t[i:i + k] for i in range(0, max(1, len(t) - k), step)}
S = [sh(norm(r["body"])) for r in rows]
inv = collections.defaultdict(list)
for i, st in enumerate(S):
    for g in st: inv[g].append(i)
def twins(i):  # 조각을 60% 이상 공유하는 사본
    c = collections.Counter(j for g in S[i] for j in inv[g] if j != i)
    return {j for j, n in c.items() if n >= 0.6 * min(len(S[i]), len(S[j]))}
ev = set()
for f in glob.glob(R + "data/queries_*.jsonl"):
    for l in open(f):
        q = json.loads(l)
        for g in q.get("evidence_groups") or []: ev.update(g)
        for e in q.get("evidence") or []: ev.add(e["chunk_id"])
banned = {id2i[c] for c in ev if c in id2i}
for i in list(banned): banned |= twins(i)
print("평가 근거와 사본(음성 후보에서 제외):", len(banned), flush=True)
gen = [json.loads(l) for l in open(G + "generated.jsonl")]
items = []
for g in gen:
    pos = id2i[g["id"]]; tw = twins(pos) | {pos}
    for q in g["queries"]:
        if q.get("ok") and q["type"] != "keyword": items.append({"q": q["q"], "type": q["type"], "pos": pos, "tw": tw})
print("검증 통과 질의", len(items), flush=True)
M = "telepix/PIXIE-Splade-v1.5"
tok = AutoTokenizer.from_pretrained(M, trust_remote_code=True)
model = AutoModelForMaskedLM.from_pretrained(M, trust_remote_code=True).to(dev).eval()
def enc(texts, L):
    out = []
    with torch.inference_mode():
        for s in range(0, len(texts), 16):
            b = tok(texts[s:s + 16], padding=True, truncation=True, max_length=L, return_tensors="pt").to(dev)
            w = torch.log1p(torch.relu(model(**b).logits)).masked_fill(~b["attention_mask"].bool().unsqueeze(-1), 0).amax(1)
            out.append(w.half().cpu())
    return torch.cat(out)
t0 = time.time(); D = enc([f"제목: {r['title']}\n\n본문: {r['body']}" for r in rows], 256); print("문서 인코딩", round(time.time() - t0), "s", flush=True)
Q = enc([x["q"] for x in items], 64); print("질의 인코딩", round(time.time() - t0), "s", flush=True)
Dm = D.to(dev); ranks = []
bad = torch.zeros(len(rows), dtype=torch.bool); bad[list(banned)] = True
for s in range(0, len(items), 256):
    sc = (Q[s:s + 256].to(dev) @ Dm.T).float()
    order = torch.argsort(sc, dim=1, descending=True).cpu()
    for k in range(order.shape[0]):
        it = items[s + k]; ol = order[k].tolist(); rk = next((r for r, j in enumerate(ol, 1) if j in it["tw"]), 10**6)
        it["rank"] = rk; it["negs"] = [j for j in ol[:80] if j not in it["tw"] and not bad[j]][:30]
print("채점 완료", round(time.time() - t0), "s", flush=True)
cnt = collections.Counter("1위" if it["rank"] == 1 else "2~5위" if it["rank"] <= 5 else "6~50위" if it["rank"] <= 50 else "50위 밖" for it in items)
print("정답 순위 분포:", dict(cnt), flush=True)
hard = [it for it in items if 2 <= it["rank"] <= 50]
easy = [it for it in items if it["rank"] == 1]; random.shuffle(easy)
keep = hard + easy[: max(1, len(hard) // 4)]   # 쉬운 질의는 망각 방지용으로 25%만
random.shuffle(keep)
json.dump([{"q": it["q"], "type": it["type"], "pos": rows[it["pos"]]["id"], "tw": [rows[j]["id"] for j in it["tw"]], "rank": it["rank"],
            "negs": [rows[j]["id"] for j in it["negs"]]} for it in keep], open(G + "train_examples.json", "w"), ensure_ascii=False)
print("학습 예시", len(keep), "(어려움", len(hard), "+ 쉬운 것", len(keep) - len(hard), ")", flush=True)
print("유형별:", dict(collections.Counter(it["type"] for it in keep)))
