"""Compare adding heading_path to SPLADE input on a frozen live category index.

Clone the index without moving its alias; replace only SPLADE vectors. Dense
candidates are cached from the baseline index and shared across both arms.
Run: .venv/bin/python scripts/law/compare_splade_heading_path.py
"""
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

from opensearchpy.helpers import scan, streaming_bulk

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.indexing.law import law_embedding_title
from search_engine.search import query as retrieval
from search_engine.sparse import SparseEncoder

AS_OF = date(2026, 10, 6)


def metrics(rows):
    n = len(rows)
    return {
        'questions': n,
        'evidence_found': sum(r['rank'] is not None for r in rows),
        'evidence_recall': sum(r['rank'] is not None for r in rows) / n,
        'evidence_hit_at_5': sum(r['rank'] is not None and r['rank'] <= 5 for r in rows) / n,
        'evidence_mrr': sum(1 / r['rank'] if r['rank'] else 0 for r in rows) / n,
        'gold_precision_lower_bound': sum(r['gold_precision'] for r in rows) / n,
        'document_hit': sum(r['document_hit'] for r in rows),
        'document_precision': sum(r['document_precision'] for r in rows) / n,
        'average_chunks': sum(len(r['window']) for r in rows) / n,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alias', default='search-law')
    parser.add_argument('--queries', type=Path, default=Path('data/queries_law100_v1.jsonl'))
    parser.add_argument('--out', type=Path, default=Path('data/generated/splade-heading-path-2026-10-06'))
    parser.add_argument('--experiment-index', help='Reuse an already encoded experimental index')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    settings.search_chunk_filter = False
    settings.search_answerability_judge = False
    client = create_client(settings)
    physical = list(client.indices.get_alias(name=args.alias))
    if len(physical) != 1:
        raise ValueError('Expected exactly one baseline physical index')
    baseline = physical[0]
    rows = sorted((h['_source'] for h in scan(client, index=baseline, query={'query': {'match_all': {}}, '_source': {'excludes': ['embedding', 'splade']}})), key=lambda r: r['id'])
    questions = [json.loads(line) for line in args.queries.read_text().splitlines() if line.strip()]
    questions = [q for q in questions if q.get("positive_review", {}).get("evaluation_eligible", True)]
    if not rows or not questions:
        raise ValueError('Empty corpus or questions')
    ids = {r['id'] for r in rows}
    for q in questions:
        if not any(set(group) & ids for group in q['evidence_groups']):
            raise ValueError('Gold absent from baseline: ' + q['qid'])
    corpus_text = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows)
    (args.out / 'corpus.jsonl').write_text(corpus_text)
    (args.out / 'queries.jsonl').write_text(args.queries.read_text())
    meta = {
        'as_of': AS_OF.isoformat(), 'baseline_index': baseline,
        'corpus_sha256': hashlib.sha256(corpus_text.encode()).hexdigest(),
        'queries_sha256': hashlib.sha256(args.queries.read_bytes()).hexdigest(),
        'documents': len({r['parent_id'] for r in rows}), 'chunks': len(rows),
        'model': settings.search_splade_model,
        'max_length': settings.search_splade_doc_max_length,
        'query_max_length': settings.search_splade_query_max_length,
        'top_terms': settings.search_splade_top_terms, 'min_weight': settings.search_splade_min_weight,
        'rrf_k': settings.search_hybrid_rrf_k,
        'hybrid_cutoff': settings.search_category_cutoff_ratio, 'splade_cutoff': 0.80,
        'candidates_hybrid': {'splade': 25, 'dense': max(25, settings.search_vector_candidates)},
        'candidates_single_splade': 100, 'max_documents': 5, 'max_chunks': 10, 'per_document': 6,
        'baseline_input': 'title + body', 'experiment_input': 'title + heading_path + body',
        'dense_control': 'Identical candidates from baseline physical index, cached across arms',
    }
    print(json.dumps(meta, ensure_ascii=False), flush=True)
    encoder = SparseEncoder(settings)
    retrieval.encode_sparse_query = lambda query: query_vectors[query]
    print('Encoding query vectors once', flush=True)
    query_vectors = dict(zip((q['query'].strip() for q in questions), encoder.encode([q['query'].strip() for q in questions], settings.search_splade_query_max_length)))

    old_texts = [embedding_text(r['title'], r['body']) for r in rows]
    new_texts = [embedding_text(law_embedding_title(r), r['body']) for r in rows]
    lengths_old = [len(t) for t in encoder._tokenizer(old_texts, truncation=False)['input_ids']]
    lengths_new = [len(t) for t in encoder._tokenizer(new_texts, truncation=False)['input_ids']]
    meta['input_diagnostics'] = {
        'changed_chunks': sum(a != b for a, b in zip(old_texts, new_texts)),
        'truncated_baseline': sum(n > settings.search_splade_doc_max_length for n in lengths_old),
        'truncated_heading_path': sum(n > settings.search_splade_doc_max_length for n in lengths_new),
        'average_added_tokens': sum(b - a for a, b in zip(lengths_old, lengths_new)) / len(rows),
    }
    print('Input diagnostics:', meta['input_diagnostics'], flush=True)
    # Confirm that the stored baseline vectors came from the same model and input.
    sample_rows = rows[::max(1, len(rows) // 8)][:8]
    encoded_sample = encoder.encode_documents([embedding_text(r['title'], r['body']) for r in sample_rows])
    stored_sample = {h['_id']: h['_source']['splade'] for h in client.mget(index=baseline, body={'ids': [r['id'] for r in sample_rows]}, _source_includes=['splade'])['docs']}
    max_delta = max(abs(vec.get(k, 0) - stored_sample[r['id']].get(k, 0)) for r, vec in zip(sample_rows, encoded_sample) for k in set(vec) | set(stored_sample[r['id']]))
    meta['baseline_sample_max_weight_delta'] = max_delta
    if max_delta > 0.02:
        raise ValueError(f'Baseline encoder mismatch: max delta={max_delta}; re-encode both arms before comparing')
    print('Baseline sample verified:', max_delta, flush=True)

    experiment = args.experiment_index or ('exp-' + args.alias.removeprefix('search-') + '-splade-heading-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S'))
    meta['experiment_index'] = experiment
    if not args.experiment_index:
        mapping = client.indices.get_mapping(index=baseline)[baseline]['mappings']
        original = client.indices.get_settings(index=baseline)[baseline]['settings']['index']
        index_settings = {key: original[key] for key in ('analysis', 'number_of_shards', 'number_of_replicas', 'knn') if key in original}
        client.indices.create(index=experiment, body={'settings': index_settings, 'mappings': mapping})
        cloned = client.reindex(body={'source': {'index': baseline}, 'dest': {'index': experiment}}, request_timeout=300)
        if cloned.get('failures') or cloned['created'] != len(rows):
            raise RuntimeError('Index clone incomplete: ' + str(cloned))
        print('Experimental clone ready:', experiment, flush=True)
        started = perf_counter()
        for offset in range(0, len(rows), 64):
            batch = rows[offset:offset + 64]
            vectors = encoder.encode_documents(new_texts[offset:offset + 64])
            actions = ({'_op_type': 'update', '_index': experiment, '_id': r['id'], 'script': {'source': 'ctx._source.splade = params.v', 'params': {'v': v}}} for r, v in zip(batch, vectors))
            for ok, item in streaming_bulk(client, actions, chunk_size=64, raise_on_error=True):
                if not ok:
                    raise RuntimeError(str(item))
            if offset % 512 == 0 or offset + 64 >= len(rows):
                print(f'Encoded {min(offset + 64, len(rows))}/{len(rows)} chunks in {perf_counter() - started:.1f}s', flush=True)
        meta['encoding_seconds'] = perf_counter() - started
        client.indices.refresh(index=experiment)
    clone_ids = {h['_id'] for h in scan(client, index=experiment, query={'query': {'match_all': {}}, '_source': False})}
    if clone_ids != ids:
        raise ValueError('Corpus differs between arms')
    (args.out / 'metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')

    # Keep the dense list identical even if rebuilding an HNSW graph changes ANN ordering.
    dense_cache = {}
    class FixedDenseClient:
        def search(self, **kwargs):
            if 'knn' in kwargs.get('body', {}).get('query', {}):
                key = json.dumps({k: v for k, v in kwargs.items() if k != 'index'}, sort_keys=True)
                if key not in dense_cache:
                    dense_cache[key] = client.search(**{**kwargs, 'index': baseline})
                return dense_cache[key]
            return client.search(**kwargs)
    fixed = FixedDenseClient()
    dense_encoder = OllamaEmbedder(settings)
    class FixedEmbeddings:
        cache = {}
        def embed_query(self, query):
            if query not in self.cache:
                self.cache[query] = dense_encoder.embed_query(query)
            return self.cache[query]
    dense_encoder_fixed = FixedEmbeddings()

    def single_window(index, query):
        response = client.search(index=index, body={'query': retrieval.build_splade_query(query_vectors[query.strip()], AS_OF)}, size=100, _source=False)
        hits = response['hits']['hits']
        if response.get('timed_out') or response['_shards']['failed']:
            raise RuntimeError('Partial SPLADE results')
        floor = hits[0]['_score'] * 0.80 if hits else 0
        docs, count, window = [], Counter(), []
        for h in hits:
            if h['_score'] < floor:
                break
            parent = h['_id'].split('#')[0]
            if parent not in docs:
                if len(docs) >= 5:
                    continue
                docs.append(parent)
            if len(window) < 10 and count[parent] < 6:
                window.append(h['_id'])
                count[parent] += 1
        return window

    outcomes = {}
    for variant, index in [('baseline', baseline), ('heading_path', experiment)]:
        outcomes[variant] = {}
        for mode in ['splade', 'hybrid']:
            results = []
            for number, q in enumerate(questions, 1):
                if mode == 'splade':
                    window = single_window(index, q['query'])
                else:
                    hits = retrieval.retrieve(fixed, index, q['query'], AS_OF, 5, dense_encoder_fixed, mode='hybrid', lexical='splade', chunk_first=True, chunk_first_cutoff_ratio=settings.search_category_cutoff_ratio, score_floor=0.0, answerability=False, rerank_chunks=False, query_rewrite=False, strict=True)
                    window = [c for h in hits for c in h.chunk_ids]
                gold = {c for group in q['evidence_groups'] for c in group}
                documents = list(dict.fromkeys(c.split('#')[0] for c in window))
                rank = next((i for i, cid in enumerate(window, 1) if cid in gold), None)
                results.append({'qid': q['qid'], 'query': q['query'], 'category': q['category'], 'subset': ('old50' if number <= 50 else 'new50') if len(questions) == 100 else 'all', 'rank': rank, 'window': window, 'gold_precision': sum(c in gold for c in window) / len(window) if window else 0, 'document_hit': bool(set(documents) & set(q['gold'])), 'document_precision': sum(d in q['gold'] for d in documents) / len(documents) if documents else 0})
                if number % 20 == 0:
                    print(f'Evaluated {variant}/{mode}: {number}/{len(questions)}', flush=True)
            outcomes[variant][mode] = {'metrics': metrics(results), 'subsets': {part: metrics([r for r in results if r['subset'] == part]) for part in dict.fromkeys(r['subset'] for r in results)}, 'results': results}
            (args.out / 'results.json').write_text(json.dumps({'metadata': meta, 'outcomes': outcomes}, ensure_ascii=False, indent=2) + '\n')
            print(variant, mode, outcomes[variant][mode]['metrics'], flush=True)
    delta = {}
    for mode in ['splade', 'hybrid']:
        before = outcomes['baseline'][mode]['results']
        after = outcomes['heading_path'][mode]['results']
        delta[mode] = {'gained': [b for a, b in zip(before, after) if a['rank'] is None and b['rank'] is not None], 'lost': [b for a, b in zip(before, after) if a['rank'] is not None and b['rank'] is None], 'changed_windows': sum(a['window'] != b['window'] for a, b in zip(before, after))}
    (args.out / 'results.json').write_text(json.dumps({'metadata': meta, 'outcomes': outcomes, 'delta': delta}, ensure_ascii=False, indent=2) + '\n')
    print('Saved:', args.out / 'results.json', flush=True)
    print('Gains/losses:', {m: {k: len(v) if isinstance(v, list) else v for k, v in d.items()} for m, d in delta.items()}, flush=True)


if __name__ == '__main__':
    main()
