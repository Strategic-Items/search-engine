"""Compare dense title+heading_path+body with title+body on a frozen corpus.

Keep SPLADE and query vectors fixed. Score both dense arms by exact cosine so
HNSW rebuilding cannot confound the input change. Also replay the service ANN
baseline to measure differences between exact and approximate retrieval.
"""
import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from opensearchpy.helpers import scan

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.indexing.law import law_embedding_title
from search_engine.search import query as retrieval
from search_engine.sparse import SparseEncoder
from compare_splade_heading_path import metrics

AS_OF = date(2026, 10, 6)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alias', default='search-law')
    parser.add_argument('--queries', type=Path, default=Path('data/queries_law100_v1.jsonl'))
    parser.add_argument('--out', type=Path, default=Path('data/generated/dense-heading-path-2026-10-06'))
    parser.add_argument('--batch-size', type=int, default=32)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    settings.search_chunk_filter = False
    settings.search_answerability_judge = False
    client = create_client(settings)
    physical = list(client.indices.get_alias(name=args.alias))
    if len(physical) != 1:
        raise ValueError('Expected one physical index')
    baseline = physical[0]
    rows = sorted((h['_source'] for h in scan(client, index=baseline, query={'query': {'match_all': {}}, '_source': {'excludes': ['splade']}})), key=lambda r: r['id'])
    ids = [r['id'] for r in rows]
    ids_at = {cid: i for i, cid in enumerate(ids)}
    base_vectors = np.array([r.pop('embedding') for r in rows], dtype=np.float32)
    questions = [json.loads(line) for line in args.queries.read_text().splitlines() if line.strip()]
    for q in questions:
        if not any(set(g) & set(ids) for g in q['evidence_groups']):
            raise ValueError('Gold missing: ' + q['qid'])
    corpus = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows)
    (args.out / 'corpus.jsonl').write_text(corpus)
    (args.out / 'queries.jsonl').write_text(args.queries.read_text())
    old_texts = [embedding_text(law_embedding_title(r), r['body']) for r in rows]
    new_texts = [embedding_text(r['title'], r['body']) for r in rows]
    changed = [i for i, (a, b) in enumerate(zip(old_texts, new_texts)) if a != b]
    meta = {
        'as_of': AS_OF.isoformat(), 'baseline_index': baseline,
        'documents': len({r['parent_id'] for r in rows}), 'chunks': len(rows),
        'questions': len(questions), 'changed_chunks': len(changed),
        'model': settings.ollama_embedding_model,
        'dimensions': settings.search_embedding_dimensions,
        'corpus_sha256': hashlib.sha256(corpus.encode()).hexdigest(),
        'query_sha256': hashlib.sha256(args.queries.read_bytes()).hexdigest(),
        'baseline_vectors_sha256': hashlib.sha256(base_vectors.tobytes()).hexdigest(),
        'dense_score': '(1 + cosine_similarity) / 2; verified against live Faiss scores',
        'baseline_input': 'title + heading_path + body', 'experiment_input': 'title + body',
        'sparse_control': 'Fixed vectors and cached candidates from baseline physical index',
        'dense_cutoff': 0.93, 'hybrid_cutoff': settings.search_category_cutoff_ratio,
        'rrf_k': settings.search_hybrid_rrf_k,
        'candidates_hybrid': {'splade': 25, 'dense': max(25, settings.search_vector_candidates)},
        'dense_single_candidates': 50, 'max_chunks': 10, 'max_documents': 5, 'per_document': 6,
        'approximation_control': 'Service ANN baseline + exact baseline + exact no-heading_path arm',
    }
    print(json.dumps(meta, ensure_ascii=False), flush=True)
    embedder = OllamaEmbedder(settings)
    sample_at = list(range(0, len(rows), max(1, len(rows) // 8)))[:8]
    check = np.array(embedder.embed([old_texts[i] for i in sample_at]), dtype=np.float32)
    cos = np.sum(check * base_vectors[sample_at], axis=1) / np.linalg.norm(check, axis=1) / np.linalg.norm(base_vectors[sample_at], axis=1)
    meta['baseline_sample_min_cosine'] = float(cos.min())
    if cos.min() < 0.9999:
        raise ValueError('Live dense baseline does not match current encoder and input')
    print('Baseline sample min cosine:', meta['baseline_sample_min_cosine'], flush=True)
    vectors_path = args.out / 'embeddings.npz'
    if vectors_path.exists():
        cached = np.load(vectors_path)
        if list(cached['ids']) != ids or str(cached['model']) != settings.ollama_embedding_model or not np.array_equal(cached['baseline'], base_vectors):
            raise ValueError('Cached corpus/model differs')
        new_vectors = cached['without_path']
        print('Reusing frozen no-heading_path vectors', flush=True)
    else:
        new_vectors = base_vectors.copy()
        started = perf_counter()
        for offset in range(0, len(changed), args.batch_size):
            positions = changed[offset:offset + args.batch_size]
            vectors = embedder.embed([new_texts[i] for i in positions])
            new_vectors[positions] = np.asarray(vectors, dtype=np.float32)
            if offset % 256 == 0 or offset + args.batch_size >= len(changed):
                print(f'Encoded {min(offset + args.batch_size, len(changed))}/{len(changed)} changed chunks in {perf_counter() - started:.1f}s', flush=True)
        meta['encoding_seconds'] = perf_counter() - started
        np.savez_compressed(vectors_path, ids=np.array(ids), model=np.array(settings.ollama_embedding_model), baseline=base_vectors, without_path=new_vectors)
    meta['average_vector_cosine'] = float(np.mean(np.sum(base_vectors * new_vectors, axis=1) / np.linalg.norm(base_vectors, axis=1) / np.linalg.norm(new_vectors, axis=1)))
    (args.out / 'metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    normalized = {
        'baseline_exact': base_vectors / np.linalg.norm(base_vectors, axis=1, keepdims=True),
        'without_path': new_vectors / np.linalg.norm(new_vectors, axis=1, keepdims=True),
    }
    query_vectors = np.array(embedder.embed([q['query'].strip() for q in questions]), dtype=np.float32)
    qvectors = {q['query'].strip(): v.tolist() for q, v in zip(questions, query_vectors)}
    scores = {arm: ((query_vectors / np.linalg.norm(query_vectors, axis=1, keepdims=True)) @ v.T + 1) / 2 for arm, v in normalized.items()}
    query_at = {q['query'].strip(): i for i, q in enumerate(questions)}
    dense_cache, sparse_cache, filter_cache = {}, {}, {}
    sparse = SparseEncoder(settings)
    sparse_queries = dict(zip((q['query'].strip() for q in questions), sparse.encode([q['query'].strip() for q in questions], settings.search_splade_query_max_length)))
    retrieval.encode_sparse_query = lambda q: sparse_queries[q]
    class FrozenQueries:
        def embed_query(self, q):
            return qvectors[q.strip()]
    frozen_queries = FrozenQueries()

    class ControlledClient:
        def __init__(self, arm):
            self.arm = arm
        def search(self, **kwargs):
            query = kwargs.get('body', {}).get('query', {})
            if 'knn' in query:
                key = json.dumps({k: v for k, v in kwargs.items() if k != 'index'}, sort_keys=True)
                if self.arm == 'service_baseline':
                    if key not in dense_cache:
                        dense_cache[key] = client.search(**{**kwargs, 'index': baseline})
                    return dense_cache[key]
                config = query['knn']['embedding']
                vector = config['vector']
                # Retrieve only the matching query's precomputed exact scores.
                text = next(text for text, v in qvectors.items() if v == vector)
                filter_key = json.dumps(config.get('filter', {'match_all': {}}), sort_keys=True)
                if filter_key not in filter_cache:
                    response = client.search(index=baseline, body={'query': config.get('filter', {'match_all': {}})}, size=len(rows), _source=False)
                    if response.get('timed_out') or response['_shards']['failed']:
                        raise RuntimeError('Partial validity/number filter results')
                    filter_cache[filter_key] = {h['_id'] for h in response['hits']['hits']}
                allowed = filter_cache[filter_key]
                order = np.argsort(-scores[self.arm][query_at[text]], kind='stable')
                order = [int(i) for i in order if ids[int(i)] in allowed][:kwargs.get('size', config['k'])]
                hits = [{'_id': ids[i], '_score': float(scores[self.arm][query_at[text], i]), '_source': rows[i]} for i in order]
                return {'hits': {'hits': hits}, '_shards': {'failed': 0}, 'timed_out': False}
            if 'neural_sparse' in query or ('bool' in query and any('neural_sparse' in q for q in query['bool'].get('must', []))):
                key = json.dumps({k: v for k, v in kwargs.items() if k != 'index'}, sort_keys=True)
                if key not in sparse_cache:
                    sparse_cache[key] = client.search(**{**kwargs, 'index': baseline})
                return sparse_cache[key]
            return client.search(**{**kwargs, 'index': baseline})

    def dense_single(control, q):
        response = control.search(index=baseline, body={'query': retrieval.build_vector_query(qvectors[q.strip()], AS_OF, 50, q)}, size=50, _source=False)
        hits = response['hits']['hits']
        floor = hits[0]['_score'] * 0.93 if hits else 0
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
    for arm in ['service_baseline', 'baseline_exact', 'without_path']:
        outcomes[arm] = {}
        control = ControlledClient(arm)
        for mode in ['vector', 'hybrid']:
            results = []
            for number, q in enumerate(questions, 1):
                if mode == 'vector':
                    window = dense_single(control, q['query'])
                else:
                    hits = retrieval.retrieve(control, baseline, q['query'], AS_OF, 5, frozen_queries, mode='hybrid', lexical='splade', chunk_first=True, chunk_first_cutoff_ratio=settings.search_category_cutoff_ratio, score_floor=0.0, answerability=False, rerank_chunks=False, query_rewrite=False, strict=True)
                    window = [cid for h in hits for cid in h.chunk_ids]
                gold = {cid for g in q['evidence_groups'] for cid in g}
                docs = list(dict.fromkeys(cid.split('#')[0] for cid in window))
                rank = next((i for i, cid in enumerate(window, 1) if cid in gold), None)
                results.append({'qid': q['qid'], 'query': q['query'], 'category': q['category'], 'rank': rank, 'window': window, 'gold_precision': sum(cid in gold for cid in window) / len(window) if window else 0, 'document_hit': bool(set(docs) & set(q['gold'])), 'document_precision': sum(d in q['gold'] for d in docs) / len(docs) if docs else 0})
                if number % 20 == 0:
                    print(f'Evaluated {arm}/{mode}: {number}/{len(questions)}', flush=True)
            outcomes[arm][mode] = {'metrics': metrics(results), 'results': results}
            print(arm, mode, outcomes[arm][mode]['metrics'], flush=True)
            (args.out / 'results.json').write_text(json.dumps({'metadata': meta, 'outcomes': outcomes}, ensure_ascii=False, indent=2) + '\n')
    deltas = {}
    for compare, left, right in [('input_change', 'baseline_exact', 'without_path'), ('ann_vs_exact', 'service_baseline', 'baseline_exact')]:
        deltas[compare] = {}
        for mode in ['vector', 'hybrid']:
            before, after = outcomes[left][mode]['results'], outcomes[right][mode]['results']
            deltas[compare][mode] = {'gained': [b for a, b in zip(before, after) if a['rank'] is None and b['rank'] is not None], 'lost': [b for a, b in zip(before, after) if a['rank'] is not None and b['rank'] is None], 'changed_windows': sum(a['window'] != b['window'] for a, b in zip(before, after))}
    (args.out / 'results.json').write_text(json.dumps({'metadata': meta, 'outcomes': outcomes, 'deltas': deltas}, ensure_ascii=False, indent=2) + '\n')
    print('Saved:', args.out / 'results.json', flush=True)
    print('Changes:', {c: {m: {k: len(v) if isinstance(v, list) else v for k, v in d.items()} for m, d in modes.items()} for c, modes in deltas.items()}, flush=True)


if __name__ == '__main__':
    main()
