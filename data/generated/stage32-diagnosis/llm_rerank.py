"""LLM 등급으로 문서 순위를 다시 매기면 정답이 1위로 오는가 (읽기 전용 실험).

후보: 컷오프·트림 없는 하이브리드 상위 20부모 × 부모당 밀집 순서 청크 4개.
등급: chunk_filter와 같은 프롬프트로 청크마다 0/1/2.
순서: 부모의 최고 등급 내림차순, 같으면 원래 융합 순위. 최고 등급 0인 부모는 뺀다.
전달: 상위 5부모의 등급 1 이상 청크.
"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

os.environ["SEARCH_ANSWERABILITY_JUDGE"] = "false"
os.environ["SEARCH_CHUNK_FILTER"] = "false"
os.environ["SEARCH_QUERY_REWRITE"] = "false"
os.environ["SEARCH_RERANK_CHUNKS"] = "false"
sys.path.insert(0, "/Users/jeongbin/git/searchEngine")
from opensearchpy import OpenSearch
from search_engine.config import get_settings
from search_engine.search import query as Q
from search_engine.search.chunk_filter import SYSTEM
from search_engine.rag.llm import generate
from search_engine.embeddings import OllamaEmbedder

S = get_settings()
client = OpenSearch(S.opensearch_url)
emb = OllamaEmbedder(S)
AS_OF = date(2026, 9, 25)
POOL, PER_DOC, K = 20, 4, 5
HERE = os.path.dirname(os.path.abspath(__file__))
G = "/Users/jeongbin/git/searchEngine/data/generated/"
CURRENT = {json.loads(l)["qid"]: json.loads(l)["query"]
           for l in open("/Users/jeongbin/git/searchEngine/data/queries_docs_v2.jsonl") if l.strip()}
SETS = [
    ("docs135", G + "holdout-v1/results/mixed-title1-dfs-top5-audited.json", "search-holdout,search-docs-only"),
    ("holdout69", G + "holdout-v1/results/holdout-title1-dfs-top5-audited.json", "search-holdout"),
    ("val36comb", G + "validation-v2/queries_combined_returned_audited.jsonl", "search-holdout,search-docs-only"),
    ("date14", G + "date-validation-v1/queries_returned_audited.jsonl", "search-holdout,search-docs-only"),
    ("ptopic7", G + "period-topic-v1/queries_returned_audited.jsonl", "search-holdout,search-docs-only"),
]


def load(path):
    if path.endswith(".jsonl"):
        return [json.loads(l) for l in open(path) if l.strip()]
    return json.load(open(path))["queries"]


def grade(query, chunks):
    grades = []
    for start in range(0, len(chunks), 6):
        batch = chunks[start:start + 6]
        prompt = json.dumps({"question": query, "passages": [
            {"index": i, "title": t, "body": b} for i, (t, b) in enumerate(batch)]}, ensure_ascii=False)
        for attempt in range(3):
            try:
                raw = generate(prompt, temperature=0.0, max_tokens=500, settings=S,
                               system=SYSTEM + f"\n이번 입력은 {len(batch)}개다. grades에 정확히 {len(batch)}개의 정수를 반환하라.",
                               json_object=True)
                values = json.loads(raw)["grades"]
                if len(values) == len(batch) and all(v in (0, 1, 2) for v in values):
                    grades.extend(values)
                    break
            except Exception:
                time.sleep(1)
        else:
            grades.extend([None] * len(batch))  # 판정 실패는 표시하고 원래 순위로 둔다
    return grades


def score(q, parents, chunks):
    gp = {p for g in q.get("gold_groups") or [] for p in g} | set(q.get("gold") or [])
    ev = q.get("evidence_groups") or []
    rec = sum(1 for g in ev if chunks & set(g)) / len(ev) if ev else None
    return {"rec": rec, "top1": bool(parents) and parents[0] in gp, "hit5": bool(set(parents) & gp),
            "dprec": sum(p in gp for p in parents) / len(parents) if parents else 0.0,
            "cprec": (sum(any(c in g for g in ev) for c in chunks) / len(chunks)) if chunks and ev else 0.0,
            "docs": len(parents), "chunks": len(chunks)}


def run(item):
    name, q, alias = item
    text = CURRENT.get(q["qid"], q["query"]) if name == "docs135" else q["query"]
    base = Q.retrieve(client, alias, text, AS_OF, K, emb, mode="hybrid")
    base_parents = [h.parent_id for h in base]
    base_chunks = {h.id for h in base} | {p.id for h in base for p in h.passages}
    wide = Q.retrieve(client, alias, text, AS_OF, POOL, emb, mode="hybrid",
                      cutoff_ratio=0, chunks_per_document=PER_DOC)
    flat = [(h.parent_id, i, c) for i, h in enumerate(wide)
            for c in [(h.id, h.title, h.body), *[(p.id, h.title, p.body) for p in h.passages]]]
    grades = grade(text, [(t, b) for _, _, (_, t, b) in flat])
    best, kept = {}, {}
    for (parent, rank, (cid, _, _)), g in zip(flat, grades):
        g = 1 if g is None else g
        best[parent] = max(best.get(parent, -1), g)
        if g > 0:
            kept.setdefault(parent, []).append(cid)
    order = sorted({p: r for p, r, _ in flat}.items(), key=lambda pr: (-best[pr[0]], pr[1]))
    parents = [p for p, _ in order if best[p] > 0][:K]
    chunks = {c for p in parents for c in kept.get(p, [])}
    gp = {p for g in q.get("gold_groups") or [] for p in g} | set(q.get("gold") or [])
    return {"set": name, "qid": q["qid"],
            "base": score(q, base_parents, base_chunks), "llm": score(q, parents, chunks),
            "base_parents": base_parents, "llm_parents": parents,
            "gold_in_pool": bool(gp & set(best)), "gold_best_grade": max([best[p] for p in gp if p in best], default=None),
            "top_grades": [(p, best[p]) for p, _ in order[:8]], "failed_grades": grades.count(None)}


items = [(n, q, a) for n, p, a in SETS for q in load(p) if q.get("answerable", True) is not False]
t0 = time.time()
with ThreadPoolExecutor(8) as ex:
    rows = list(ex.map(run, items))
json.dump(rows, open(HERE + "/llm_rerank_out.json", "w"), ensure_ascii=False, indent=1)
print(f"{len(rows)} queries in {time.time() - t0:.0f}s, failed grade batches: {sum(r['failed_grades'] for r in rows)}")
for name, *_ in SETS:
    rs = [r for r in rows if r["set"] == name]
    for mode in ("base", "llm"):
        m = lambda k: sum(r[mode][k] for r in rs) / len(rs)
        recs = [r[mode]["rec"] for r in rs if r[mode]["rec"] is not None]
        print(f"{name:10s} {mode:4s} n={len(rs)} evRecall@5={sum(recs)/len(recs):.3f} top1={m('top1'):.3f} "
              f"hit@5={m('hit5'):.3f} docPrec={m('dprec'):.3f} chunkPrec(lb)={m('cprec'):.3f} docs={m('docs'):.2f} chunks={m('chunks'):.2f}")
    print(f"{name:10s} gold in pool of {POOL}: {sum(r['gold_in_pool'] for r in rs)}/{len(rs)}")
