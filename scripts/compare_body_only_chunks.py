"""문서는 기존 검색으로 고정하고 청크 임베딩에서 제목 영향만 비교한다."""
from datetime import date
import hashlib
import json
import math
from pathlib import Path
from unittest.mock import patch

from search_engine.client import create_client
from search_engine.config import Settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.evaluation.evaluate import quality_metrics
from search_engine.search.query import retrieve, _candidates_by_parent


def cosine(left, right):
    denom = math.sqrt(sum(x*x for x in left) * sum(x*x for x in right))
    return sum(a*b for a, b in zip(left, right)) / denom if denom else 0.0


def main():
    settings = Settings(search_answerability_judge=False, search_chunk_filter=False,
                        search_rerank_chunks=False, search_query_rewrite=False)
    client = create_client(settings)
    embedder = OllamaEmbedder(settings)
    index = ','.join(sorted(client.indices.get(index=settings.search_docs_alias)))
    output = Path('data/generated/body-only-chunks-v1')
    output.mkdir(parents=True, exist_ok=True)
    rows = json.loads(Path('data/generated/docs-v2/evaluation-135q-docs-only-no-judge.json').read_text())['queries']
    candidates_file = output / 'candidates.json'
    if candidates_file.exists():
        data = json.loads(candidates_file.read_text())
        if data['index'] != index or data['model'] != settings.ollama_embedding_model:
            raise ValueError('cached index/model mismatch')
        records, sources = data['records'], data['sources']
    else:
        records, sources = [], {}
        for position, row in enumerate(rows, 1):
            query_vector = embedder.embed_query(row['query'])
            class FixedEmbedder:
                def embed_query(self, query):
                    return query_vector
            captured = {}
            def capture(lists):
                pool = _candidates_by_parent(lists)
                captured.update(pool)
                return pool
            with patch('search_engine.search.query.get_settings', return_value=settings), \
                 patch('search_engine.search.query._candidates_by_parent', side_effect=capture):
                hits = retrieve(client, index, row['query'], date.today(), 5,
                                embedder=FixedEmbedder(), mode='hybrid', strict=True,
                                answerability=False, query_rewrite=False)
            pools = []
            for hit in hits:
                pool = captured.get(hit.parent_id, [])
                for candidate in pool:
                    sources[candidate['_id']] = candidate['_source']
                ids = list(dict.fromkeys([*hit.chunk_ids, *[c['_id'] for c in pool]]))
                pools.append(ids)
            records.append({'row': row, 'parents': [h.parent_id for h in hits],
                            'baseline_chunks': [h.chunk_ids for h in hits],
                            'pools': pools, 'query_vector': query_vector})
            if position % 15 == 0:
                print(f'candidates {position}/{len(rows)}', flush=True)
        wanted = {chunk for r in records for pool in r['pools'] for chunk in pool}
        missing = list(wanted - sources.keys())
        if missing:
            result = client.search(index=index, body={'query': {'ids': {'values': missing}}, 'size': len(missing)})
            sources.update({h['_id']: h['_source'] for h in result['hits']['hits']})
        if wanted - sources.keys() or any(not sources[c].get('embedding') for c in wanted):
            raise ValueError('missing source or title+body embedding')
        candidates_file.write_text(json.dumps({'index': index, 'model': settings.ollama_embedding_model,
                                               'records': records, 'sources': sources}, ensure_ascii=False))
    cache_file = output / 'body-vectors.jsonl'
    cache = {}
    if cache_file.exists():
        for line in cache_file.read_text().splitlines():
            item = json.loads(line)
            cache[item['key']] = item['vector']
    def key(source):
        text = '본문: ' + source.get('body', '')
        return hashlib.sha256((settings.ollama_embedding_model + '\n' + text).encode()).hexdigest()
    unique = {key(source): '본문: ' + source.get('body', '') for source in sources.values()}
    pending = [(k, text) for k, text in unique.items() if k not in cache]
    print(f'body embeddings: {len(pending)} pending / {len(unique)} unique', flush=True)
    with cache_file.open('a') as file:
        for start in range(0, len(pending), 8):
            batch = pending[start:start+8]
            vectors = embedder.embed([text for _, text in batch])
            for (k, _), vector in zip(batch, vectors):
                cache[k] = vector
                file.write(json.dumps({'key': k, 'vector': vector}) + '\n')
            file.flush()
            if start % 80 == 0 or start+8 >= len(pending):
                print(f'body embeddings {min(start+8,len(pending))}/{len(pending)}', flush=True)
    cases = {('current',0): []}
    ratios = [0,.90,.95,.98,.99,.995,1.0]
    for method in ['title_body', 'body_only']:
        for ratio in ratios:
            cases[method,ratio] = []
    for record in records:
        row, parents, pools, qv = record['row'], record['parents'], record['pools'], record['query_vector']
        cases['current',0].append(dict(row, returned=parents, returned_chunks=record['baseline_chunks']))
        for method in ['title_body', 'body_only']:
            scores = {c: cosine(qv, sources[c]['embedding'] if method == 'title_body' else cache[key(sources[c])])
                      for pool in pools for c in pool}
            ranked = [sorted(pool, key=lambda c: -scores[c])[:settings.search_chunks_per_document] for pool in pools]
            top = max((scores[c] for pool in ranked for c in pool), default=0)
            for ratio in ratios:
                kept = [[c for c in pool if not ratio or scores[c] >= top*ratio] for pool in ranked]
                chosen = [(p, pool) for p, pool in zip(parents, kept) if pool]
                cases[method,ratio].append(dict(row, returned=[p for p,_ in chosen],
                                                  returned_chunks=[pool for _,pool in chosen]))
    summaries = []
    for (method,ratio), group in cases.items():
        summaries.append({'method':method,'ratio':ratio,'metrics':quality_metrics(group,5)})
    report = {'index':index,'model':settings.ollama_embedding_model,'llm':False,
              'body_text_format':'본문: {body}; removes explicit title field, retains headings inside body',
              'score':'exact cosine, relative to maximum selected chunk across fixed documents',
              'document_selection':'fixed existing title+body hybrid search, candidate pool before six-chunk truncation',
              'cases':summaries,'query_results':{str(k):v for k,v in cases.items()}}
    (output/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    for s in summaries:
        m=s['metrics']
        print(s['method'],s['ratio'],'P',round(m['evidence_precision_at_5']*100,2),
              'R',round(m['evidence_recall_at_5']*100,2),
              'all',round(m['evidence_all_at_5']*100,2),
              'chunks',round(m['mean_chunks_at_5'],2))


if __name__ == '__main__':
    main()
