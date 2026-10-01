import json, sys, random
sys.path.insert(0, "scripts")
from evaluate_splade_dense_fusion import metrics, chunk_metrics, load_judgments
from pathlib import Path
S = sys.argv[1]; R = "data/"
def Q(p): return {q["qid"]: q for q in map(json.loads, open(R + p)) if q.get("gold")}
def doc_row(m): return {k: round(v, 3) for k, v in m.items() if k != "final_ratio"}
def pick(m, keys): return {k: round(m[k], 3) if m[k] is not None else None for k in keys}
CK = ["evidence_hit_at_k", "evidence_recall_at_k", "evidence_all_at_k", "evidence_mrr_at_k", "evidence_first_rank_at_k", "mean_chunks_at_k",
      "pooled_relevant_precision_on_judged", "pooled_direct_precision_on_judged", "pooled_judgment_coverage"]
def top1(r): return bool(r["ranked"]) and r["ranked"][0]["parent_id"] in set(r["gold"])
def boot(a, b, n=5000, seed=44):
    d = [float(y) - float(x) for x, y in zip(a, b)]; rng = random.Random(seed); m = len(d)
    s = sorted(sum(d[rng.randrange(m)] for _ in range(m)) / m for _ in range(n))
    return round(sum(d) / m * 100, 1), round(s[int(.025 * n)] * 100, 1), round(s[int(.975 * n) - 1] * 100, 1)
for name, qp, hyb, ftrim, funtrim, jp in [
    ("docs_v2 135", "queries_docs_v2.jsonl", "hybrid-docs-noans.json", "fusion-docs-trim.json", "fusion-docs-untrim.json", R + "generated/docs-v2/pooled-judgments/relevance-135q.tsv"),
    ("holdout-small 69", "queries_holdout_v1_adjudicated.jsonl", "hybrid-hs-noans.json", "fusion-holdout-small.json", "fusion-hs-untrim.json", None)]:
    qs = Q(qp); J = load_judgments(Path(jp)) if jp else {}
    h = json.load(open(f"{S}/{hyb}"))["results"]; ft = json.load(open(f"{S}/{ftrim}")); fu = json.load(open(f"{S}/{funtrim}"))
    print(f"\n=== {name} ===")
    mh = metrics(h, 0.0)
    print("문서  hybrid         ", doc_row(mh))
    for r in (0.97, 1.0):
        s = [x for x in ft["sweeps"] if x["final_ratio"] == r][0]
        print(f"문서  SPLADE+dense r{r}", doc_row(s))
    print("청크  hybrid         ", pick(chunk_metrics(h, qs, J), CK))
    print("청크  SPLADE+dense   ", pick(chunk_metrics(fu["results"], qs, J), CK))
    a = [top1(x) for x in h]; b = [top1(x) for x in ft["results"]]
    print("P@1 paired bootstrap (pp, 95% CI):", boot(a, b), "wins", sum((not x) and y for x, y in zip(a, b)), "losses", sum(x and not y for x, y in zip(a, b)))
    cat = {}
    for x, y in zip(h, ft["results"]):
        c = qs[x["qid"]].get("category", "?"); cat.setdefault(c, [0, 0, 0]); cat[c][0] += 1; cat[c][1] += bool(top1(x)); cat[c][2] += bool(top1(y))
    print("카테고리별 P@1 (n, hybrid, S+dense):", cat)
