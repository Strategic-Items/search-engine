import json, os
G = os.path.dirname(os.path.abspath(__file__)) + "/"
top = lambda r: bool(r["ranked"]) and r["ranked"][0]["parent_id"] in set(r["gold"])
def load(tag):
    out = {}
    for n in ("docs", "hs", "val"):
        p = f"{G}ev-{tag}-{n}.json"
        if not os.path.exists(p): return None
        j = json.load(open(p)); s = {x["ratio"]: x for x in j["sweeps"]}[0.97]
        out[n] = {"p1": sum(top(r) for r in j["results"]), "n": len(j["results"]), "hit5": s["hit_at_5"], "mrr": s["mrr_at_5"], "retp": s["precision_returned"], "terms": j["mean_document_terms"]}
    return out
import sys
tags = sys.argv[1].split(",") if len(sys.argv) > 1 else ["base", "A", "B", "C"]; OUTNAME = sys.argv[2] if len(sys.argv) > 2 else "RESULTS.md"; res = {t: load(t) for t in tags}
L = ["# 대량 합성 질의 파인튜닝 결과 (자동 생성)", "", "SPLADE 단독, ratio 0.97. P@1은 문항 수(분모는 docs_v2 135, holdout-small 69, 검증 36).", "",
     "| 모델 | docs_v2 P@1 | holdout-small P@1 | 검증 P@1 | 깨끗한 두 세트 합 | docs_v2 Hit@5 | holdout Hit@5 | 검증 Hit@5 | docs_v2 MRR | 문서당 term(docs) |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
b = res["base"]
for t in tags:
    r = res[t]
    if not r: L.append(f"| {t} | (평가 없음) | | | | | | | | |"); continue
    L.append(f"| {t} | {r['docs']['p1']}/{r['docs']['n']} | {r['hs']['p1']}/{r['hs']['n']} | {r['val']['p1']}/{r['val']['n']} | {r['hs']['p1']+r['val']['p1']} | {r['docs']['hit5']:.3f} | {r['hs']['hit5']:.3f} | {r['val']['hit5']:.3f} | {r['docs']['mrr']:.3f} | {r['docs']['terms']:.0f} |")
L += ["", "## 사전 판정 기준", "", "후보 인정: 깨끗한 두 세트(holdout-small+검증) P@1 합이 기준보다 3개 이상 높고, docs_v2 P@1이 129 이상.", ""]
if b:
    base_sum = b["hs"]["p1"] + b["val"]["p1"]
    for t in tags[1:]:
        r = res[t]
        if not r: continue
        s = r["hs"]["p1"] + r["val"]["p1"]; ok = (s >= base_sum + 3) and r["docs"]["p1"] >= 129
        L.append(f"- {t}: 합 {s} (기준 {base_sum}, 차이 {s - base_sum:+d}), docs_v2 {r['docs']['p1']} → **{'후보 통과' if ok else '기준 미달'}**")
open(G + OUTNAME, "w").write("\n".join(L) + "\n"); print("\n".join(L))
