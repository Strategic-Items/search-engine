import json, numpy as np
from collections import defaultdict
exec(open("../analyze_dense.py").read().split("for name, (tag")[0])   # rrf, ratio_cut, metrics
P = "/Users/jeongbin/git/unstructured-doc-parser_ver2/data/category_chunks/"
SETS = {"law": ("법령·고시 (21문항, 청크 673)", P + "01_법령고시/docs.jsonl"), "admin": ("행정·업무 (30문항, 청크 183)", P + "02_행정업무/docs.jsonl")}
TAGS = ("base", "A", "C", "D", "E")
def chunk_rrf(a, b, k=60):
    sc = defaultdict(float)
    for rk in (a, b):
        for i, c in enumerate(rk, 1): sc[c] += 1 / (k + i)
    return sorted(sc, key=lambda c: (-sc[c], c))
def evid(rows, Q, k=5):
    n = hit = rec = mrr = p1 = allg = 0
    for qid, ch in rows:
        groups = Q[qid].get("evidence_groups") or []
        if not groups: continue
        n += 1; sh = ch[:k]; s = set(sh); got = [bool(set(g) & s) for g in groups]; hit += any(got); rec += sum(got) / len(groups); allg += all(got)
        want = {c for g in groups for c in g}; rk = next((i for i, c in enumerate(sh, 1) if c in want), 0); mrr += 1 / rk if rk else 0; p1 += bool(sh) and sh[0] in want
    return hit / n, rec / n, allg / n, mrr / n, p1 / n
def top1(r): return bool(r["ranked"]) and r["ranked"][0]["parent_id"] in set(r["gold"])
for key, (lab, corpus) in SETS.items():
    rows = [json.loads(l) for l in open(corpus)]; parent = {r["id"]: r.get("parent_id") or r["id"] for r in rows}
    Q = {q["qid"]: q for q in map(json.loads, open(f"queries_{key}_v1.jsonl")) if q.get("gold")}
    e = np.load(f"emb-bge-{key}.npz"); ids = e["ids"]; sims = e["queries"] @ e["docs"].T; qpos = {str(q): i for i, q in enumerate(e["qids"])}
    # dense 단독
    drows = []; dch = {}
    for qid in Q:
        s = (1 + sims[qpos[qid]]) / 2; order = np.argsort(-s)[:50]; seen = set(); pr = []
        for j in order:
            p = parent[ids[j]]
            if p not in seen: seen.add(p); pr.append((p, float(s[j])))
        drows.append({"gold": Q[qid]["gold"], "ranked": [{"parent_id": p, "score": v, "leads": True} for p, v in ratio_cut(pr, 0.97)]}); dch[qid] = [ids[j] for j in order]
    md = metrics(drows, 0.0); cd = evid([(q, dch[q]) for q in Q], Q)
    print(f"\n=== {lab} ===")
    print(f"{'구성':14s} | 문서: {'P@1':>5s} {'Hit@5':>6s} {'반환분P':>7s} {'반환':>5s} {'MRR':>6s} | 청크(상위5): {'Hit':>5s} {'Recall':>6s} {'모든':>5s} {'MRR':>6s} {'1위':>5s}")
    print(f"{'dense(BGE)만':14s} | 문서: {md['P@1']:5.3f} {md['Hit@5']:6.3f} {md['retP']:7.3f} {md['ret']:5.2f} {md['MRR']:6.3f} | 청크: {cd[0]:5.3f} {cd[1]:6.3f} {cd[2]:5.3f} {cd[3]:6.3f} {cd[4]:5.3f}")
    for t in TAGS:
        sp = {r["qid"]: r for r in json.load(open(f"ev-{t}-{key}.json"))["results"]}
        srows = []; crows = []; frows = []; fcrows = []
        for qid in Q:
            r = sp[qid]; srows.append({"gold": Q[qid]["gold"], "ranked": [{"parent_id": h["parent_id"], "score": h["score"], "leads": True} for h in r["ranked"]]})
            crows.append((qid, [h["chunk_id"] for h in r["chunk_ranked"]]))
            s = (1 + sims[qpos[qid]]) / 2; order = np.argsort(-s)[:50]; seen = set(); pr = []
            for j in order:
                p = parent[ids[j]]
                if p not in seen: seen.add(p); pr.append((p, float(s[j])))
            spl = ratio_cut([(h["parent_id"], float(h["score"])) for h in r["ranked"]], 0.97)
            frows.append({"gold": Q[qid]["gold"], "ranked": rrf(spl, ratio_cut(pr, 0.97))[:25]})
            fcrows.append((qid, chunk_rrf([h["chunk_id"] for h in r["chunk_ranked"]], dch[qid])))
        ms = metrics(srows, 0.97); cs = evid(crows, Q); mf = metrics(frows, 0.97); cf = evid(fcrows, Q)
        print(f"{'SPLADE '+t:14s} | 문서: {ms['P@1']:5.3f} {ms['Hit@5']:6.3f} {ms['retP']:7.3f} {ms['ret']:5.2f} {ms['MRR']:6.3f} | 청크: {cs[0]:5.3f} {cs[1]:6.3f} {cs[2]:5.3f} {cs[3]:6.3f} {cs[4]:5.3f}")
        print(f"{'  +dense '+t:14s} | 문서: {mf['P@1']:5.3f} {mf['Hit@5']:6.3f} {mf['retP']:7.3f} {mf['ret']:5.2f} {mf['MRR']:6.3f} | 청크: {cf[0]:5.3f} {cf[1]:6.3f} {cf[2]:5.3f} {cf[3]:6.3f} {cf[4]:5.3f}")
