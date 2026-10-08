"""Sweep the superseded-edition score weight of the category hybrid (chunk RRF + 0.95 cutoff).

For questions that do not name an edition, chunks of documents with `superseded_by` are scored
`weight` times their RRF score before the cutoff. weight=1 is the shipped behaviour.
Run: .venv/bin/python scripts/law/sweep_superseded_weight.py [--alias search-admin --queries ...]
"""
import argparse
from datetime import date
import json
from pathlib import Path

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search import query as retrieval
from search_engine.sparse import SparseEncoder

AS_OF = date(2026, 10, 6)
WEIGHTS = [1.0, 0.99, 0.98, 0.97, 0.96, 0.95, 0.93, 0.9, 0.8, 0.5, 0.0]


def summarize(rows):
    n = len(rows)
    return {
        'questions': n,
        'chunk_found': sum(r['rank'] is not None for r in rows),
        'mrr': sum(1 / r['rank'] if r['rank'] else 0 for r in rows) / n,
        'chunk_precision_lower_bound': sum(r['gold_precision'] for r in rows) / n,
        'document_hit': sum(r['document_hit'] for r in rows),
        'document_precision': sum(r['document_precision'] for r in rows) / n,
        'superseded_docs_per_question': sum(r['superseded_docs'] for r in rows) / n,
        'average_chunks': sum(len(r['window']) for r in rows) / n,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alias', default='search-law')
    parser.add_argument('--queries', type=Path, default=Path('data/queries_law100_v1.jsonl'))
    parser.add_argument('--out', type=Path, default=Path('data/generated/superseded-weight-2026-10-07'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    settings.search_chunk_filter = False
    settings.search_answerability_judge = False
    client = create_client(settings)
    index = list(client.indices.get_alias(name=args.alias))[0]
    questions = [json.loads(line) for line in args.queries.read_text().splitlines() if line.strip()]
    questions = [q for q in questions if q.get("positive_review", {}).get("evaluation_eligible", True)]
    texts = [q['query'].strip() for q in questions]
    vectors = dict(zip(texts, OllamaEmbedder(settings).embed(texts)))
    sparse = dict(zip(texts, SparseEncoder(settings).encode(texts, settings.search_splade_query_max_length)))
    retrieval.encode_sparse_query = lambda q: sparse[q]

    class Frozen:
        def embed_query(self, q):
            return vectors[q.strip()]

    superseded = {h['_source']['parent_id'] for h in client.search(index=index, body={'query': {'exists': {'field': 'superseded_by'}}, '_source': ['parent_id']}, size=10000)['hits']['hits']}
    print('superseded documents:', len(superseded), flush=True)
    out = {}
    for weight in WEIGHTS:
        settings.search_chunk_first_superseded_weight = weight
        results = []
        for q in questions:
            hits = retrieval.retrieve(client, index, q['query'], AS_OF, 5, Frozen(), mode='hybrid', lexical='splade', chunk_first=True, chunk_first_cutoff_ratio=settings.search_category_cutoff_ratio, score_floor=0.0, answerability=False, rerank_chunks=False, query_rewrite=False, strict=True)
            window = [c for h in hits for c in h.chunk_ids]
            gold = {c for g in q['evidence_groups'] for c in g}
            docs = list(dict.fromkeys(c.split('#')[0] for c in window))
            results.append({
                'qid': q['qid'], 'names_edition': retrieval.names_edition(q['query']),
                'rank': next((i for i, c in enumerate(window, 1) if c in gold), None), 'window': window,
                'gold_precision': sum(c in gold for c in window) / len(window) if window else 0,
                'document_hit': bool(set(docs) & set(q['gold'])),
                'document_precision': sum(d in q['gold'] for d in docs) / len(docs) if docs else 0,
                'superseded_docs': sum(d in superseded for d in docs)})
        base = out.get(1.0, {}).get('results')
        out[weight] = {
            'metrics': summarize(results),
            'no_edition_named': summarize([r for r in results if not r['names_edition']]),
            'edition_named': summarize([r for r in results if r['names_edition']]),
            'results': results}
        if base:
            out[weight]['gained'] = [b['qid'] for a, b in zip(base, results) if a['rank'] is None and b['rank'] is not None]
            out[weight]['lost'] = [b['qid'] for a, b in zip(base, results) if a['rank'] is not None and b['rank'] is None]
            out[weight]['changed_windows'] = sum(a['window'] != b['window'] for a, b in zip(base, results))
        m = out[weight]['metrics']
        print(weight, {k: round(v, 3) for k, v in m.items()}, 'gained', out[weight].get('gained'), 'lost', out[weight].get('lost'), 'changed', out[weight].get('changed_windows'), flush=True)
    (args.out / f'{args.alias}.json').write_text(json.dumps({'alias': args.alias, 'index': index, 'queries': str(args.queries), 'weights': out}, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
