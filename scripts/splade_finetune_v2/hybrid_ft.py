import json, sys, numpy as np
from collections import defaultdict
exec(open("../analyze_dense.py").read().split("for name, (tag")[0])   # rrf, ratio_cut, metrics
R = "/Users/jeongbin/git/searchEngine/data/"
SETS = {"docs": ("docs_v2 135", "queries_docs_v2.jsonl", R + "generated/docs-v2/review-corpus/docs.jsonl", "docs"),
        "hs": ("holdout-small 69", "queries_holdout_v1_adjudicated.jsonl", "../holdout-small.jsonl", "hs"),
        "val": ("검증 36", "queries_validation_v2.jsonl", "../validation-small.jsonl", "val")}
def chunk_rrf(a, b, k=60):
    sc = defaultdict(float)
    for rk in (a, b):
        for i, c in enumerate(rk, 1): sc[c] += 1 / (k + i)
    return sorted(sc, key=lambda c: (-sc[c], c))
def evid(rows, Q, k=5):
    n = hit = rec = mrr = p1 = 0
    for qid, ch in rows:
        groups = Q[qid].get("evidence_groups") or []
        if not groups: continue
        n += 1; sh = ch[:k]; s = set(sh); got = [bool(set(g) & s) for g in groups]; hit += any(got); rec += sum(got) / len(groups)
        want = {c for g in groups for c in g}; rk = next((i for i, c in enumerate(sh, 1) if c in want), 0); mrr += 1 / rk if rk else 0; p1 += bool(sh) and sh[0] in want
    return hit / n, rec / n, mrr / n, p1 / n
dense_name = sys.argv[1] if len(sys.argv) > 1 else "bge"
for key, (lab, qf, corpus, tag) in SETS.items():
    rows = [json.loads(l) for l in open(corpus)]; parent = {r["id"]: r.get("parent_id") or r["id"] for r in rows}
    Q = {q["qid"]: q for q in map(json.loads, open(R + qf)) if q.get("gold")}
    e = np.load(f"../emb-{dense_name}-{tag}.npz"); ids = e["ids"]; sims = e["queries"] @ e["docs"].T; qpos = {str(q): i for i, q in enumerate(e["qids"])}
    print(f"\n=== {lab} · dense={dense_name} · SPLADE+dense (RRF k=60, 사전 컷 0.97, 최종 컷 0.97) ===")
    print(f"{'SPLADE':6s} | 문서: {'P@1':>5s} {'Hit@5':>6s} {'반환분P':>7s} {'평균반환':>6s} {'MRR':>6s} | 청크(상위5): {'Hit':>5s} {'Recall':>6s} {'MRR':>6s} {'1위적중':>6s}")
    for t in ("base", "A", "C", "D", "E"):
        sp = {r["qid"]: r for r in json.load(open(f"ev-{t}-{key}.json"))["results"]}
        drows, crows = [], []
        for qid, q in Q.items():
            s = (1 + sims[qpos[qid]]) / 2; order = np.argsort(-s)[:50]; seen = set(); pr = []
            for j in order:
                p = parent[ids[j]]
                if p not in seen: seen.add(p); pr.append((p, float(s[j])))
            spl = ratio_cut([(h["parent_id"], float(h["score"])) for h in sp[qid]["ranked"]], 0.97)
            drows.append({"gold": q["gold"], "ranked": rrf(spl, ratio_cut(pr, 0.97))[:25]})
            dch = [ids[j] for j in order]; sch = [h["chunk_id"] for h in sp[qid]["chunk_ranked"]]
            crows.append((qid, chunk_rrf(sch, dch)))
        m = metrics(drows, 0.97); c = evid(crows, Q)
        print(f"{t:6s} | 문서: {m['P@1']:5.3f} {m['Hit@5']:6.3f} {m['retP']:7.3f} {m['ret']:6.2f} {m['MRR']:6.3f} | 청크: {c[0]:5.3f} {c[1]:6.3f} {c[2]:6.3f} {c[3]:6.3f}")
