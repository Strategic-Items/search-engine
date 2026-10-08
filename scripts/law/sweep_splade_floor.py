"""법령 150문항에서 SPLADE 절대 점수 하한이 반환 결과에 주는 영향을 잰다.

서비스 경로(retrieve, hybrid + 청크 우선 + 컷오프 0.95)에서 SPLADE 후보 25개를 RRF 전에 하한으로 거르고
(search_score_floor_splade, query.py의 검색기별 게이트), SPLADE 단독은 서비스 단독 창(1위의 80%, 청크 10·문서 5·문서당 6)
앞에서 같은 하한으로 거른다. 하한 0이 현재 서비스다. 컷오프를 건 상태의 값만 본다.

    .venv/bin/python scripts/law/sweep_splade_floor.py
"""
import json
import sys
from datetime import date
from pathlib import Path

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search import query as retrieval
from search_engine.search.query import build_splade_query
from search_engine.sparse import SparseEncoder

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_explorer_law100 import single_window  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
AS_OF = date(2026, 10, 7)
FLOORS = [0, 6, 7, 8, 9, 10, 11, 12]


def parent(c):
    return c.split("#")[0]


def stats(rows):
    n = len(rows)
    ok = sum(r["found"] for r in rows)
    return (f"{ok}/{n} = {ok / n:.3f}", sum(r["cp"] for r in rows) / n, sum(r["dp"] for r in rows) / n,
            sum(r["size"] for r in rows) / n, sum(r["size"] == 0 for r in rows))


def main() -> None:
    settings = get_settings()
    settings.search_chunk_filter = False
    settings.search_answerability_judge = False
    client = create_client(settings)
    index = list(client.indices.get_alias(name="search-law"))[0]
    questions = [json.loads(l) for l in (ROOT / "data/queries_law150_v1.jsonl").read_text().splitlines() if l.strip()]
    questions = [q for q in questions if q.get("gold") and q.get("positive_review", {}).get("evaluation_eligible", True)]
    texts = [q["query"].strip() for q in questions]
    vectors = dict(zip(texts, OllamaEmbedder(settings).embed(texts)))
    sparse = dict(zip(texts, SparseEncoder(settings).encode(texts, settings.search_splade_query_max_length)))
    retrieval.encode_sparse_query = lambda q: sparse[q]

    class Frozen:
        def embed_query(self, q):
            return vectors[q.strip()]

    raw = {}
    for q in questions:
        t = q["query"].strip()
        raw[t] = client.search(index=index, body={"query": build_splade_query(sparse[t], AS_OF, t)}, size=100,
                               _source=["parent_id"])["hits"]["hits"]

    def score(q, window):
        gold = {c for g in q["evidence_groups"] for c in g}
        docs = list(dict.fromkeys(parent(c) for c in window))
        found = all(any(c in window for c in g) for g in q["evidence_groups"])
        return {"found": found, "cp": sum(c in gold for c in window) / len(window) if window else 0.0,
                "dp": sum(d in set(q["gold"]) for d in docs) / len(docs) if docs else 0.0, "size": len(window)}

    print(f"{len(questions)}문항, 기준일 {AS_OF}, 청크 컷오프: hybrid 0.95 · SPLADE 0.80\n")
    for mode in ("hybrid", "splade"):
        print(f"### {mode}\n| SPLADE 하한 | 청크 Recall | 청크 Precision | 문서 Precision | 평균 청크 | 빈 결과 |\n|---|---|---|---|---|---|")
        for floor in FLOORS:
            rows = []
            for q in questions:
                t = q["query"].strip()
                if mode == "hybrid":
                    settings.search_score_floor_splade = float(floor)
                    hits = retrieval.retrieve(client, "search-law", q["query"], AS_OF, 5, Frozen(), mode="hybrid",
                                              lexical="splade", chunk_first=True,
                                              chunk_first_cutoff_ratio=settings.search_category_cutoff_ratio,
                                              score_floor=None, answerability=False, rerank_chunks=False,
                                              query_rewrite=False, strict=True)
                    window = [c for h in hits for c in h.chunk_ids]
                else:
                    hits_ = [h for h in raw[t] if h["_score"] >= floor]
                    status = single_window(hits_, 0.80)
                    window = [h["_id"] for h in hits_ if status[h["_id"]] == "keep"]
                rows.append(score(q, window))
            rec, cp, dp, size, empty = stats(rows)
            print(f"| {floor} | {rec} | {cp:.3f} | {dp:.3f} | {size:.2f} | {empty} |")
        settings.search_score_floor_splade = 0.0
        print()


if __name__ == "__main__":
    main()
