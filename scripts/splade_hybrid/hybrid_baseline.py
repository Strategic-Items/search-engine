"""현재 운영 hybrid(retrieve)를 같은 질의에 돌려 fusion 보고서와 같은 모양으로 저장한다."""
import json, sys
from datetime import date
from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.search.query import retrieve
alias, queries_path, as_of, out = sys.argv[1], sys.argv[2], date.fromisoformat(sys.argv[3]), sys.argv[4]
client = create_client(get_settings())
results = []
for l in open(queries_path):
    q = json.loads(l)
    if not q.get("gold"): continue
    hits = retrieve(client, alias, q["query"], as_of, 10, mode="hybrid", strict=True, answerability=False)
    ranked = [{"parent_id": h.parent_id, "score": float(h.score or 0), "leads": True} for h in hits[:5]]
    chunks = []
    for h in hits[:5]:
        for c in h.chunk_ids: chunks.append({"chunk_id": c})
    results.append({"qid": q["qid"], "gold": q["gold"], "ranked": ranked, "chunk_ranked": chunks})
json.dump({"results": results}, open(out, "w"), ensure_ascii=False)
print(len(results))
