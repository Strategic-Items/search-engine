"""Compare ranking with exactly 25 SPLADE and 25 dense candidates.

Run with .venv/bin/python scripts/law/compare_retrieval_selection.py.
Only reads the service index; writes reproducible evaluation artifacts locally.
"""
import json
from datetime import date
from pathlib import Path
from time import perf_counter

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search import query as retrieval
from search_engine.sparse import SparseEncoder

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/generated/law-reference-only-2026-10-12"
AS_OF = date(2026, 10, 7)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    # The category evaluation measures retrieval without an LLM relevance filter.
    settings.search_chunk_filter = False
    settings.search_answerability_judge = False
    client = create_client(settings)
    index = next(iter(client.indices.get_alias(name=settings.search_law_alias)))
    questions = [json.loads(line) for line in (ROOT / "data/queries_law150_v1.jsonl").read_text().splitlines()]
    questions = [q for q in questions if q.get("positive_review", {}).get("evaluation_eligible", True)]
    # Both arms share encodings, chunks, labels, candidate counts and return limits.
    texts = [q["query"] for q in questions]
    vectors = dict(zip(texts, OllamaEmbedder(settings).embed(texts)))
    terms = dict(zip(texts, SparseEncoder(settings).encode(texts, settings.search_splade_query_max_length)))
    original_encoder = retrieval.encode_sparse_query
    retrieval.encode_sparse_query = lambda query: terms[query]

    class Frozen:
        def embed_query(self, query):
            return vectors[query]

    service = {}
    try:
        for name, reference_boost in (("before", 0.0), ("after", 6.0)):
            settings.search_law_reference_boost = reference_boost
            found = top1 = total = precision = 0
            misses, windows, elapsed = [], {}, []
            for i, q in enumerate(questions, 1):
                start = perf_counter()
                hits = retrieval.retrieve(client, index, q["query"], AS_OF, 5, Frozen(),
                                          mode="hybrid", lexical="splade", chunk_first=True,
                                          chunk_first_cutoff_ratio=0.7, hybrid_candidates=25,
                                          law_ranking=True, score_floor=0.0, answerability=False,
                                          rerank_chunks=False, query_rewrite=False, strict=True)
                elapsed.append((perf_counter() - start) * 1000)
                ids = [cid for h in hits for cid in h.chunk_ids]
                gold = {cid for g in q["evidence_groups"] for cid in g}
                success = all(set(g) & set(ids) for g in q["evidence_groups"])
                found += success
                top1 += bool(hits and hits[0].parent_id in q["gold"])
                total += len(ids)
                precision += len(gold & set(ids)) / len(ids) if ids else 0
                windows[q["qid"]] = ids
                if not success:
                    misses.append(q["qid"][-3:])
                if i % 25 == 0:
                    print(f"{name} {i}/{len(questions)}", flush=True)
            service[name] = dict(bm25_enabled=False, reference_boost=reference_boost,
                                 candidates_per_retriever=25, found=found, n=len(questions), top1=top1,
                                 mean_chunks=total/len(questions), precision_lower_bound=precision/len(questions),
                                 mean_search_ms=sum(elapsed)/len(elapsed), misses=misses, windows=windows)
            print(name, {k: v for k, v in service[name].items() if k != "windows"}, flush=True)
    finally:
        retrieval.encode_sparse_query = original_encoder
    (OUT / "service-comparison.json").write_text(json.dumps(
        {"index": index, "as_of": str(AS_OF), "evaluation": "frozen evidence_groups",
         "before": service["before"], "after": service["after"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
