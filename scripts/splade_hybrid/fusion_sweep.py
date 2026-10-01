import json, numpy as np
from collections import defaultdict
exec(open("analyze_dense.py").read().split("for name, (tag")[0])
def wrrf(sp, de, k, w):
    sc = defaultdict(float); dr = {}; leaders = {x[0][0] for x in (sp, de) if x}
    for rk, wt, nm in ((sp, w, "s"), (de, 1.0, "d")):
        for i, (p, _) in enumerate(rk, 1):
            sc[p] += wt / (k + i)
            if nm == "d": dr[p] = i
    o = sorted(sc, key=lambda p: (-sc[p], dr.get(p, 999), p))
    return [{"parent_id": p, "score": sc[p], "leads": p in leaders} for p in o]
def scorefuse(sp, de, w):  # 각 목록의 1위 점수로 나눠 0~1로 맞춘 뒤 가중 합
    sc = defaultdict(float)
    for rk, wt in ((sp, w), (de, 1.0)):
        if rk:
            t = rk[0][1]
            for p, s in rk: sc[p] += wt * s / t
    leaders = {x[0][0] for x in (sp, de) if x}
    o = sorted(sc, key=lambda p: (-sc[p], p))
    return [{"parent_id": p, "score": sc[p], "leads": p in leaders} for p in o]
def load(name, tag, corpus, spl, m):
    rows = [json.loads(l) for l in open(corpus)]; parent = {r["id"]: r.get("parent_id") or r["id"] for r in rows}
    sp = {r["qid"]: r for r in json.load(open(spl))["results"]}
    e = np.load(f"emb-{m}-{tag}.npz"); ids = e["ids"]; sims = e["queries"] @ e["docs"].T; out = []
    for qi, qid in enumerate(e["qids"]):
        qid = str(qid); s = (1 + sims[qi]) / 2; seen = set(); pr = []
        for j in np.argsort(-s)[:50]:
            p = parent[ids[j]]
            if p not in seen: seen.add(p); pr.append((p, float(s[j])))
        out.append((ratio_cut(pr, 0.97), ratio_cut([(h["parent_id"], float(h["score"])) for h in sp[qid]["ranked"]], 0.97), sp[qid]["gold"]))
    return out
grid = [("rrf k=60 w=1 (현재)", lambda s, d: rrf(s, d, 60))]
for k in (10, 30, 100): grid.append((f"rrf k={k}", lambda s, d, k=k: rrf(s, d, k)))
for w in (0.5, 1.5, 2.0): grid.append((f"rrf k=60 SPLADE 가중 {w}", lambda s, d, w=w: wrrf(s, d, 60, w)))
for w in (0.5, 1.0, 2.0): grid.append((f"점수합(1위 정규화) SPLADE 가중 {w}", lambda s, d, w=w: scorefuse(s, d, w)))
data = {(n, m): load(n, *SETS[n], m) for n in SETS for m in ("bge", "rune")}
print(f"{'융합 방식':34s} | " + " | ".join(f"{n[:9]}·{m}" for n in SETS for m in ("bge", "rune")) + "   (P@1 / Hit@5, 최종 ratio 0.97, 단위 %)")
for label, fn in grid:
    cells = []
    for n in SETS:
        for m in ("bge", "rune"):
            rows = [{"gold": g, "ranked": fn(s, d)[:25]} for d, s, g in data[(n, m)]]
            r = metrics(rows, 0.97); cells.append(f"{r['P@1']*100:5.1f}/{r['Hit@5']*100:5.1f}")
    print(f"{label:34s} | " + " | ".join(cells))
