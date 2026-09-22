"""Evaluate a Hugging Face SPLADE checkpoint on the docs-v2 corpus.

This script intentionally has no project runtime dependency on torch. Run it in
the experimental ML container; the production search service stays unchanged.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from time import perf_counter

import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def encode(texts, tokenizer, model, *, batch_size: int, max_length: int, min_weight: float):
    vectors = []
    for start in range(0, len(texts), batch_size):
        batch = tokenizer(
            texts[start:start + batch_size], padding=True, truncation=True,
            max_length=max_length, return_tensors="pt",
        )
        with torch.inference_mode():
            logits = model(**batch).logits
            weights = torch.log1p(torch.relu(logits))
            weights = weights.masked_fill(~batch["attention_mask"].bool().unsqueeze(-1), 0)
            pooled = weights.amax(dim=1).cpu()
        for vector in pooled:
            active = torch.nonzero(vector >= min_weight, as_tuple=False).flatten()
            vectors.append({int(i): float(vector[i]) for i in active})
    return vectors


def reciprocal_rank(ranked: list[str], gold: set[str]) -> float:
    return next((1 / rank for rank, parent in enumerate(ranked, 1) if parent in gold), 0.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--model", default="telepix/PIXIE-Splade-v1.5")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--min-weight", type=float, default=0.01)
    parser.add_argument("--top-terms", type=int, default=256)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    corpus = rows(args.corpus)
    queries = [row for row in rows(args.queries) if row.get("gold")]
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForMaskedLM.from_pretrained(args.model, trust_remote_code=True).eval()

    document_texts = [f"제목: {row.get('title', '')}\n\n본문: {row.get('body', '')}" for row in corpus]
    started = perf_counter()
    document_vectors = encode(
        document_texts, tokenizer, model, batch_size=args.batch_size,
        max_length=args.max_length, min_weight=args.min_weight,
    )
    query_vectors = encode(
        [row["query"] for row in queries], tokenizer, model,
        batch_size=args.batch_size, max_length=args.max_length,
        min_weight=args.min_weight,
    )

    postings = defaultdict(list)
    for index, vector in enumerate(document_vectors):
        for token, weight in sorted(vector.items(), key=lambda item: -item[1])[:args.top_terms]:
            postings[token].append((index, weight))

    rankings = []
    for query, vector in zip(queries, query_vectors):
        chunk_scores = defaultdict(float)
        for token, query_weight in sorted(vector.items(), key=lambda item: -item[1])[:args.top_terms]:
            for index, document_weight in postings.get(token, ()):
                chunk_scores[index] += query_weight * document_weight
        parent_scores = {}
        for index, score in chunk_scores.items():
            parent = corpus[index].get("parent_id") or corpus[index]["id"]
            parent_scores[parent] = max(score, parent_scores.get(parent, 0.0))
        ranked = sorted(parent_scores.items(), key=lambda item: (-item[1], item[0]))
        chunk_ranked = sorted(chunk_scores.items(), key=lambda item: (-item[1], corpus[item[0]]["id"]))
        rankings.append({
            "qid": query.get("qid") or query.get("id"), "gold": query["gold"],
            "ranked": [{"parent_id": parent, "score": score} for parent, score in ranked[:25]],
            # 부모로 접기 전의 순위를 남겨야 답변 모델이 실제로 받는 청크를 채점할 수 있다.
            "chunk_ranked": [{
                "chunk_id": corpus[index]["id"],
                "parent_id": corpus[index].get("parent_id") or corpus[index]["id"],
                "score": score,
            } for index, score in chunk_ranked[:100]],
        })

    sweeps = []
    for ratio in (0.0, 0.80, 0.90, 0.95, 0.97, 0.99, 1.0):
        returned = []
        for row in rankings:
            top = row["ranked"][0]["score"] if row["ranked"] else 0.0
            kept = [hit["parent_id"] for hit in row["ranked"][:5]
                    if hit["score"] >= top * ratio]
            returned.append((kept, set(row["gold"])))
        relevant = sum(sum(parent in gold for parent in kept) for kept, gold in returned)
        count = sum(len(kept) for kept, _ in returned)
        sweeps.append({
            "ratio": ratio,
            "precision_at_1": sum(bool(kept) and kept[0] in gold for kept, gold in returned) / len(returned),
            "hit_at_5": sum(any(parent in gold for parent in kept) for kept, gold in returned) / len(returned),
            "precision_returned": relevant / count if count else 0.0,
            "mean_returned": count / len(returned),
            "mrr_at_5": sum(reciprocal_rank(kept, gold) for kept, gold in returned) / len(returned),
        })

    report = {
        "model": args.model, "corpus_chunks": len(corpus), "queries": len(queries),
        "max_length": args.max_length, "min_weight": args.min_weight,
        "top_terms": args.top_terms, "elapsed_seconds": perf_counter() - started,
        "mean_document_terms": sum(map(len, document_vectors)) / len(document_vectors),
        "mean_query_terms": sum(map(len, query_vectors)) / len(query_vectors),
        "sweeps": sweeps, "results": rankings,
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(json.dumps(sweeps, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
