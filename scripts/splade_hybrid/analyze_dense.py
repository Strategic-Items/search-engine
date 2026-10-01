import json, sys, numpy as np
from collections import defaultdict
R = "/Users/jeongbin/git/searchEngine/data/"
SETS = {"docs_v2 135": ("docs", R + "generated/docs-v2/review-corpus/docs.jsonl", "eval-PIXIE-Splade-v1.5.json"),
        "holdout-small 69": ("hs", "holdout-small.jsonl", "splade-holdout-small.json")}
def ratio_cut(rk, r):
    if not r or not rk or rk[0][1] <= 0: return rk
    f = rk[0][1] * r; return [(p, s) for p, s in rk if s >= f]
def rrf(sp, de, k=60):
    sc = defaultdict(float); dr = {}; leaders = {x[0][0] for x in (sp, de) if x}
    for rk, nm in ((sp, "s"), (de, "d")):
        for i, (p, _) in enumerate(rk, 1):
            sc[p] += 1 / (k + i)
            if nm == "d": dr[p] = i
    order = sorted(sc, key=lambda p: (-sc[p], dr.get(p, len(sc) + 1), p))
    return [{"parent_id": p, "score": sc[p], "leads": p in leaders} for p in order]
def metrics(rows, ratio):
    ret = []
    for r in rows:
        rk = r["ranked"]; fl = rk[0]["score"] * ratio if rk else 0
        ret.append(([h["parent_id"] for h in rk if h["score"] >= fl or h["leads"]][:5], set(r["gold"])))
    rel = sum(sum(p in g for p in k) for k, g in ret); cnt = sum(len(k) for k, _ in ret); n = len(ret)
    rr = lambda k, g: next((1 / i for i, p in enumerate(k, 1) if p in g), 0.0)
    return {"P@1": sum(bool(k) and k[0] in g for k, g in ret) / n, "Hit@5": sum(any(p in g for p in k) for k, g in ret) / n,
            "retP": rel / cnt if cnt else 0, "ret": cnt / n, "MRR": sum(rr(k, g) for k, g in ret) / n}
for name, (tag, corpus, spl) in SETS.items():
    rows = [json.loads(l) for l in open(corpus)]; parent = {r["id"]: r.get("parent_id") or r["id"] for r in rows}
    sp = {r["qid"]: r for r in json.load(open(spl))["results"]}
    print(f"\n=== {name} ===")
    for m, label in (("bge", "BGE-m3-ko (현재 dense, HF 오프라인)"), ("rune", "PIXIE-Rune-v1.5"), ("spell", "PIXIE-Spell-v1.5-0.6B")):
        e = np.load(f"emb-{m}-{tag}.npz"); ids = e["ids"]; sims = e["queries"] @ e["docs"].T
        dense_rows, fus_rows = [], []
        for qi, qid in enumerate(e["qids"]):
            s = (1 + sims[qi]) / 2; order = np.argsort(-s)[:50]; seen = set(); pr = []
            for j in order:
                p = parent[ids[j]]
                if p not in seen: seen.add(p); pr.append((p, float(s[j])))
            dn = ratio_cut(pr, 0.97); g = sp[str(qid)]["gold"]
            dense_rows.append({"gold": g, "ranked": [{"parent_id": p, "score": v, "leads": True} for p, v in dn]})
            spl_rk = ratio_cut([(h["parent_id"], float(h["score"])) for h in sp[str(qid)]["ranked"]], 0.97)
            fus_rows.append({"gold": g, "ranked": rrf(spl_rk, dn)[:25]})
        f = lambda m_: " ".join(f"{k} {v:.3f}" for k, v in m_.items())
        print(f"{label:34s} dense 단독 :", f(metrics(dense_rows, 0.0)))
        for r in (0.97, 1.0): print(f"{'':34s} +SPLADE r{r}:", f(metrics(fus_rows, r)))
