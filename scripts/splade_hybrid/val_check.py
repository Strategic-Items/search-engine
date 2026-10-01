import json, numpy as np
exec(open("fusion_sweep.py").read().split("grid = [")[0])
SETS["validation_v2 36"] = ("val", "validation-small.jsonl", "splade-val.json")
cand = lambda s, d: scorefuse(s, d, 1.0); base = lambda s, d: rrf(s, d, 60)
top = lambda r: bool(r) and r[0]["parent_id"] in G
for m in ("bge", "rune"):
    data = load("validation_v2 36", *SETS["validation_v2 36"], m)
    res = {}
    for nm, fn in (("RRF k=60 (현재)", base), ("점수합 가중 1.0 (후보)", cand)):
        rows = [{"gold": g, "ranked": fn(s, d)[:25]} for d, s, g in data]
        res[nm] = rows; r = metrics(rows, 0.97)
        print(f"{m:5s} {nm:22s}", " ".join(f"{k} {v:.3f}" for k, v in r.items()))
    a, b = res["RRF k=60 (현재)"], res["점수합 가중 1.0 (후보)"]
    t1 = lambda r: bool(r["ranked"]) and r["ranked"][0]["parent_id"] in set(r["gold"])
    print(f"      P@1 후보 승 {sum((not t1(x)) and t1(y) for x, y in zip(a, b))} 패 {sum(t1(x) and not t1(y) for x, y in zip(a, b))}")
