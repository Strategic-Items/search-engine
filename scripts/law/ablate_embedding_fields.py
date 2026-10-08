"""Add one metadata field at a time to the dense or SPLADE input and measure law-category retrieval.

Frozen corpus = the live `search-law` physical index. Dense arms are scored by exact cosine
(no HNSW rebuild noise) with SPLADE fixed; SPLADE arms are scored in a temporary clone of the
index with dense fixed. Every number uses the service chunk cutoffs (SPLADE 0.80, dense 0.93,
hybrid chunk RRF 0.95). Arms resume from out/arms/*.json, vectors are cached in out/vectors/.
Run: .venv/bin/python scripts/law/ablate_embedding_fields.py
"""
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from opensearchpy.helpers import scan, streaming_bulk

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.indexing.law import law_embedding_title
from search_engine.search import query as retrieval
from search_engine.sparse import SparseEncoder

AS_OF = date(2026, 10, 6)

# 한 번에 하나씩 본문 앞 제목 아래에 `라벨: 값` 한 줄을 더한다. 값이 없는 청크는 입력이 그대로다.
FIELDS = {
    'doc_type': ('문서종류', lambda r: r.get('doc_type')),
    'doc_status': ('판본', lambda r: r.get('doc_status')),
    'issuer': ('발급기관', lambda r: r.get('issuer')),
    'doc_number': ('문서번호', lambda r: r.get('doc_number')),
    'published_at': ('공포일', lambda r: r.get('published_at')),
    'revision_date': ('개정일', lambda r: r.get('revision_date')),
    'effective_from': ('시행일', lambda r: r.get('effective_from')),
    'superseded_by': ('대체 고시', lambda r: r.get('superseded_by')),
    'columns': ('표 열', lambda r: ', '.join(r['columns']) if r.get('columns') else None),
    'caption': ('표 제목', lambda r: r.get('caption')),
}


def text_for(row, retriever, params):
    title = law_embedding_title(row) if retriever == 'dense' else row['title']
    lines = []
    for p in params:
        label, getter = FIELDS[p]
        value = getter(row)
        if value:
            lines.append(f'{label}: {value}')
    if not lines:
        return embedding_text(title, row['body'])
    return f'제목: {title}\n' + '\n'.join(lines) + f'\n\n본문: {row["body"]}'.strip()


def metrics(rows):
    n = len(rows)
    return {
        'questions': n,
        'chunk_found': sum(r['rank'] is not None for r in rows),
        'chunk_recall': sum(r['rank'] is not None for r in rows) / n,
        'group_recall': sum(r['group_recall'] for r in rows) / n,
        'hit_at_5': sum(r['rank'] is not None and r['rank'] <= 5 for r in rows) / n,
        'mrr': sum(1 / r['rank'] if r['rank'] else 0 for r in rows) / n,
        'chunk_precision_lower_bound': sum(r['gold_precision'] for r in rows) / n,
        'document_hit': sum(r['document_hit'] for r in rows),
        'document_precision': sum(r['document_precision'] for r in rows) / n,
        'average_chunks': sum(len(r['window']) for r in rows) / n,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alias', default='search-law')
    parser.add_argument('--queries', type=Path, default=Path('data/queries_law100_v1.jsonl'))
    parser.add_argument('--out', type=Path, default=Path('data/generated/embedding-fields-2026-10-06'))
    parser.add_argument('--fields', nargs='*', default=list(FIELDS))
    parser.add_argument('--skip-all-arm', action='store_true')
    args = parser.parse_args()
    for sub in ('arms', 'vectors'):
        (args.out / sub).mkdir(parents=True, exist_ok=True)
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
    base_dense = np.array([r.pop('embedding') for r in rows], dtype=np.float32)
    questions = [json.loads(line) for line in args.queries.read_text().splitlines() if line.strip()]
    questions = [q for q in questions if q.get("positive_review", {}).get("evaluation_eligible", True)]
    for q in questions:
        if not any(set(g) & set(ids) for g in q['evidence_groups']):
            raise ValueError('Gold missing: ' + q['qid'])
    corpus = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows)
    (args.out / 'corpus.jsonl').write_text(corpus)
    (args.out / 'queries.jsonl').write_text(args.queries.read_text())
    meta = {
        'as_of': AS_OF.isoformat(), 'baseline_index': baseline, 'documents': len({r['parent_id'] for r in rows}),
        'chunks': len(rows), 'questions': len(questions),
        'corpus_sha256': hashlib.sha256(corpus.encode()).hexdigest(),
        'query_sha256': hashlib.sha256(args.queries.read_bytes()).hexdigest(),
        'dense_model': settings.ollama_embedding_model, 'splade_model': settings.search_splade_model,
        'cutoffs': {'splade': 0.80, 'dense': 0.93, 'hybrid': settings.search_category_cutoff_ratio},
        'rrf_k': settings.search_hybrid_rrf_k, 'candidates_hybrid': {'splade': 25, 'dense': max(25, settings.search_vector_candidates)},
        'single_candidates': {'splade': 100, 'dense': 50}, 'max_documents': 5, 'per_document': 6, 'max_chunks': 10,
        'baseline_input': {'dense': 'title + heading_path + body', 'splade': 'title + body'},
        'fields': {k: v[0] for k, v in FIELDS.items()},
        'fill': {k: sum(bool(v[1](r)) for r in rows) for k, v in FIELDS.items()},
    }
    (args.out / 'metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(meta, ensure_ascii=False), flush=True)

    embedder = OllamaEmbedder(settings)
    encoder = SparseEncoder(settings)
    base_texts = {'dense': [text_for(r, 'dense', []) for r in rows], 'splade': [text_for(r, 'splade', []) for r in rows]}
    # 기준 벡터가 지금 인코더·입력과 같은지 확인한다.
    sample = list(range(0, len(rows), max(1, len(rows) // 8)))[:8]
    check = np.array(embedder.embed([base_texts['dense'][i] for i in sample]), dtype=np.float32)
    cos = np.sum(check * base_dense[sample], axis=1) / np.linalg.norm(check, axis=1) / np.linalg.norm(base_dense[sample], axis=1)
    if cos.min() < 0.9999:
        raise ValueError(f'dense baseline mismatch {cos.min()}')
    stored = {h['_id']: h['_source']['splade'] for h in client.mget(index=baseline, body={'ids': [rows[i]['id'] for i in sample]}, _source_includes=['splade'])['docs']}
    enc = encoder.encode_documents([base_texts['splade'][i] for i in sample])
    delta = max(abs(v.get(k, 0) - stored[rows[i]['id']].get(k, 0)) for i, v in zip(sample, enc) for k in set(v) | set(stored[rows[i]['id']]))
    if delta > 0.02:
        raise ValueError(f'splade baseline mismatch {delta}')
    print('Baselines verified:', float(cos.min()), delta, flush=True)

    texts = [q['query'].strip() for q in questions]
    query_dense = np.array(embedder.embed(texts), dtype=np.float32)
    qvec = {t: v.tolist() for t, v in zip(texts, query_dense)}
    query_at = {t: i for i, t in enumerate(texts)}
    query_norm = query_dense / np.linalg.norm(query_dense, axis=1, keepdims=True)
    sparse_q = dict(zip(texts, encoder.encode(texts, settings.search_splade_query_max_length)))
    retrieval.encode_sparse_query = lambda q: sparse_q[q]

    class FrozenQueries:
        def embed_query(self, q):
            return qvec[q.strip()]

    filter_cache = {}

    def allowed_ids(flt):
        key = json.dumps(flt, sort_keys=True)
        if key not in filter_cache:
            response = client.search(index=baseline, body={'query': flt}, size=len(rows), _source=False)
            if response.get('timed_out') or response['_shards']['failed']:
                raise RuntimeError('Partial filter results')
            filter_cache[key] = {h['_id'] for h in response['hits']['hits']}
        return filter_cache[key]

    class Controlled:
        def __init__(self, scores, sparse_index):
            self.scores, self.sparse_index = scores, sparse_index

        def search(self, **kwargs):
            query = kwargs.get('body', {}).get('query', {})
            if 'knn' in query:
                config = query['knn']['embedding']
                text = next(t for t, v in qvec.items() if v == config['vector'])
                allowed = allowed_ids(config.get('filter', {'match_all': {}}))
                row = self.scores[query_at[text]]
                order = [int(i) for i in np.argsort(-row, kind='stable') if ids[int(i)] in allowed][:kwargs.get('size', config['k'])]
                hits = [{'_id': ids[i], '_score': float(row[i]), '_source': rows[i]} for i in order]
                return {'hits': {'hits': hits}, '_shards': {'failed': 0}, 'timed_out': False}
            return client.search(**{**kwargs, 'index': self.sparse_index})

    def window_of(hits, floor_ratio):
        floor = hits[0]['_score'] * floor_ratio if hits else 0
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

    def evaluate(scores, sparse_index):
        control = Controlled(scores, sparse_index)
        out = {}
        for mode in ('dense', 'splade', 'hybrid'):
            results = []
            for number, q in enumerate(questions, 1):
                text = q['query'].strip()
                if mode == 'dense':
                    resp = control.search(index=baseline, body={'query': retrieval.build_vector_query(qvec[text], AS_OF, 50, q['query'])}, size=50, _source=False)
                    window = window_of(resp['hits']['hits'], 0.93)
                elif mode == 'splade':
                    resp = client.search(index=sparse_index, body={'query': retrieval.build_splade_query(sparse_q[text], AS_OF)}, size=100, _source=False)
                    if resp.get('timed_out') or resp['_shards']['failed']:
                        raise RuntimeError('Partial SPLADE results')
                    window = window_of(resp['hits']['hits'], 0.80)
                else:
                    hits = retrieval.retrieve(control, sparse_index, q['query'], AS_OF, 5, FrozenQueries(), mode='hybrid', lexical='splade', chunk_first=True, chunk_first_cutoff_ratio=settings.search_category_cutoff_ratio, score_floor=0.0, answerability=False, rerank_chunks=False, query_rewrite=False, strict=True)
                    window = [c for h in hits for c in h.chunk_ids]
                gold = {c for g in q['evidence_groups'] for c in g}
                docs = list(dict.fromkeys(c.split('#')[0] for c in window))
                rank = next((i for i, c in enumerate(window, 1) if c in gold), None)
                results.append({
                    'qid': q['qid'], 'category': q['category'], 'subset': 'old50' if number <= 50 else 'new50',
                    'rank': rank, 'window': window,
                    'group_recall': sum(bool(set(g) & set(window)) for g in q['evidence_groups']) / len(q['evidence_groups']),
                    'gold_precision': sum(c in gold for c in window) / len(window) if window else 0,
                    'document_hit': bool(set(docs) & set(q['gold'])),
                    'document_precision': sum(d in q['gold'] for d in docs) / len(docs) if docs else 0})
            out[mode] = {'metrics': metrics(results), 'subsets': {s: metrics([r for r in results if r['subset'] == s]) for s in ('old50', 'new50')}, 'results': results}
        return out

    def dense_vectors(name, params):
        path = args.out / 'vectors' / f'dense-{name}.npy'
        if path.exists():
            return np.load(path)
        new_texts = [text_for(r, 'dense', params) for r in rows]
        changed = [i for i in range(len(rows)) if new_texts[i] != base_texts['dense'][i]]
        vectors = base_dense.copy()
        started = perf_counter()
        for off in range(0, len(changed), 32):
            pos = changed[off:off + 32]
            vectors[pos] = np.asarray(embedder.embed([new_texts[i] for i in pos]), dtype=np.float32)
            if off % 640 == 0:
                print(f'  dense {name}: {min(off + 32, len(changed))}/{len(changed)} {perf_counter() - started:.0f}s', flush=True)
        np.save(path, vectors)
        return vectors

    def splade_index(name, params):
        """기준 인덱스를 복제해 바뀐 청크의 SPLADE만 갈아 끼운다. 임시 인덱스 이름을 돌려준다."""
        new_texts = [text_for(r, 'splade', params) for r in rows]
        changed = [i for i in range(len(rows)) if new_texts[i] != base_texts['splade'][i]]
        index = 'exp-law-fields-' + name.replace('_', '-') + datetime.now(timezone.utc).strftime('%H%M%S')
        mapping = client.indices.get_mapping(index=baseline)[baseline]['mappings']
        original = client.indices.get_settings(index=baseline)[baseline]['settings']['index']
        client.indices.create(index=index, body={'settings': {k: original[k] for k in ('analysis', 'number_of_shards', 'number_of_replicas', 'knn') if k in original}, 'mappings': mapping})
        cloned = client.reindex(body={'source': {'index': baseline}, 'dest': {'index': index}}, request_timeout=600, wait_for_completion=True)
        if cloned.get('failures') or cloned['created'] != len(rows):
            raise RuntimeError('Clone incomplete')
        started = perf_counter()
        for off in range(0, len(changed), 64):
            pos = changed[off:off + 64]
            vectors = encoder.encode_documents([new_texts[i] for i in pos])
            actions = ({'_op_type': 'update', '_index': index, '_id': rows[i]['id'], 'script': {'source': 'ctx._source.splade = params.v', 'params': {'v': v}}} for i, v in zip(pos, vectors))
            for ok, item in streaming_bulk(client, actions, chunk_size=64, raise_on_error=True):
                if not ok:
                    raise RuntimeError(str(item))
        client.indices.refresh(index=index)
        print(f'  splade {name}: {len(changed)} chunks {perf_counter() - started:.0f}s', flush=True)
        return index, len(changed)

    base_scores = (query_norm @ (base_dense / np.linalg.norm(base_dense, axis=1, keepdims=True)).T + 1) / 2

    def run_arm(name, dense_params, splade_params):
        done = args.out / 'arms' / f'{name}.json'
        if done.exists():
            print('skip', name, flush=True)
            return
        started = perf_counter()
        scores, sparse_index, changed = base_scores, baseline, {}
        if dense_params:
            v = dense_vectors(name, dense_params)
            scores = (query_norm @ (v / np.linalg.norm(v, axis=1, keepdims=True)).T + 1) / 2
            changed['dense'] = int(sum(text_for(r, 'dense', dense_params) != b for r, b in zip(rows, base_texts['dense'])))
        temp = None
        try:
            if splade_params:
                temp, changed['splade'] = splade_index(name, splade_params)
                sparse_index = temp
            result = evaluate(scores, sparse_index)
        finally:
            if temp:
                client.indices.delete(index=temp, ignore_unavailable=True)
        record = {'arm': name, 'dense_params': dense_params, 'splade_params': splade_params, 'changed_chunks': changed, 'seconds': perf_counter() - started, 'outcomes': result}
        done.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
        print(name, {m: {k: round(v, 3) for k, v in result[m]['metrics'].items() if k in ('chunk_found', 'group_recall', 'chunk_precision_lower_bound', 'mrr')} for m in result}, flush=True)

    run_arm('baseline', [], [])
    for f in args.fields:
        run_arm(f'dense-{f}', [f], [])
        run_arm(f'splade-{f}', [], [f])

    # 개별 시험에서 hybrid 청크 회수를 깎지 않은 필드만 모아 양쪽에 함께 넣는다.
    if not args.skip_all_arm:
        base = json.loads((args.out / 'arms' / 'baseline.json').read_text())['outcomes']['hybrid']['metrics']['chunk_found']
        keep = {'dense': [], 'splade': []}
        for f in args.fields:
            for side in keep:
                arm = json.loads((args.out / 'arms' / f'{side}-{f}.json').read_text())['outcomes']['hybrid']['metrics']['chunk_found']
                if arm >= base:
                    keep[side].append(f)
        meta['combined_selection'] = keep
        (args.out / 'metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
        run_arm('combined', keep['dense'], keep['splade'])
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
