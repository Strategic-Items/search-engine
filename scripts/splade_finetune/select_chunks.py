"""전략물자 학습 청크를 고른다. 평가 질의(docs_v2*)의 근거 청크는 제외한다."""
import glob, json, sys

corpus = [json.loads(l) for l in open("data/generated/docs-v2/review-corpus/docs.jsonl")]
ev = set()
for f in glob.glob("data/queries_docs_v2*.jsonl"):
    for l in open(f):
        q = json.loads(l)
        for g in q.get("evidence_groups") or []: ev.update(g)
        for e in q.get("evidence") or []: ev.add(e["chunk_id"])
kw = ("전략물자", "이중용도", "전략기술", "수출허가", "통제품목", "캐치올")
chosen = [r for r in corpus
          if sum(r["title"].count(k) + r["body"].count(k) for k in kw) >= 2
          and r["id"] not in ev and len(r["body"]) >= 150]
json.dump(chosen, open(sys.argv[1] if len(sys.argv) > 1 else "train_chunks.json", "w"), ensure_ascii=False)
print(len(chosen))
