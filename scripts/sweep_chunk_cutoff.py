"""LLM 없이 문서 컷오프와 벡터 청크 점수 컷오프를 비교하는 읽기 전용 실험."""
import copy
from datetime import date
import json
from pathlib import Path
from unittest.mock import patch

from search_engine.client import create_client
from search_engine.config import Settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.evaluation.evaluate import quality_metrics
from search_engine.search.query import retrieve


class CachedSearch:
    def __init__(self, client):
        self.client = client
        self.cache = {}
        self.vector_scores = {}

    def search(self, **kwargs):
        key = json.dumps(kwargs, sort_keys=True)
        if key not in self.cache:
            response = self.client.search(**kwargs)
            self.cache[key] = copy.deepcopy(response)
            if 'knn' in kwargs.get('body', {}).get('query', {}):
                self.vector_scores.update({h['_id']: h['_score'] for h in response['hits']['hits']})
        return copy.deepcopy(self.cache[key])


class CachedEmbed:
    def __init__(self, embedder):
        self.embedder = embedder
        self.cache = {}

    def embed_query(self, query):
        if query not in self.cache:
            self.cache[query] = self.embedder.embed_query(query)
        return self.cache[query]


def main():
    settings = Settings(search_answerability_judge=False, search_chunk_filter=False,
                        search_rerank_chunks=False, search_query_rewrite=False)
    client = create_client(settings)
    embedder = CachedEmbed(OllamaEmbedder(settings))
    index = ','.join(sorted(client.indices.get(index=settings.search_docs_alias)))
    rows = json.loads(Path('data/generated/docs-v2/evaluation-135q-docs-only-no-judge.json').read_text())['queries']
    cases = [(doc, kind, value) for doc in [.90, .95, .98, .99, 1.0]
             for kind, value in [('ratio', 0), ('ratio', .95), ('ratio', .98),
                                 ('ratio', .99), ('ratio', .995), ('ratio', 1.0),
                                 ('floor', .80), ('floor', .85), ('floor', .90)]]
    results = {str(case): [] for case in cases}
    missing = 0
    for position, row in enumerate(rows, 1):
        cached = CachedSearch(client)
        for doc, kind, value in cases:
            variant = settings.model_copy(update={'search_cutoff_ratio_hybrid': doc,
                                                   'search_cutoff_ratio_vector': max(settings.search_cutoff_ratio_vector, doc)})
            with patch('search_engine.search.query.get_settings', return_value=variant):
                hits = retrieve(cached, index, row['query'], date.today(), 5,
                                embedder=embedder, mode='hybrid', strict=True,
                                answerability=False, query_rewrite=False)
            scores = cached.vector_scores
            top = max((scores[c] for h in hits for c in h.chunk_ids if c in scores), default=0)
            threshold = top * value if kind == 'ratio' else value
            parents, chunks = [], []
            for hit in hits:
                kept = [c for c in hit.chunk_ids
                        if not value or c not in scores or scores[c] >= threshold]
                if kept:
                    parents.append(hit.parent_id)
                    chunks.append(kept)
            result = dict(row, returned=parents, returned_chunks=chunks)
            results[str((doc, kind, value))].append(result)
            if doc == .90 and value == 0:
                missing += sum(c not in scores for h in hits for c in h.chunk_ids)
        if position % 15 == 0:
            print(f'{position}/{len(rows)}', flush=True)
    summaries = []
    for case in cases:
        group = results[str(case)]
        metrics = quality_metrics(group, 5)
        covered = [r for r in group if any(r['returned_chunks'])]
        summaries.append({'document_ratio': case[0], 'chunk_kind': case[1], 'chunk_value': case[2],
                          'metrics': metrics, 'nonempty_queries': len(covered),
                          'conditional_chunk_precision': quality_metrics(covered, 5)['evidence_precision_at_5'] if covered else 0})
    output = Path('data/generated/chunk-cutoff-v1/sweep.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'indexes': index, 'queries': len(rows), 'llm': False,
        'chunk_scores': 'OpenSearch knn vector score; ratio to best selected chunk across documents',
        'missing_vector_score_chunks_preserved': missing, 'cases': summaries,
        'query_results': results}, ensure_ascii=False, indent=2))
    for case in summaries:
        m = case['metrics']
        print(case['document_ratio'],case['chunk_kind'],case['chunk_value'],
              'P',round(m['evidence_precision_at_5']*100,2),
              'R',round(m['evidence_recall_at_5']*100,2),
              'covered',case['nonempty_queries'],
              'conditional P',round(case['conditional_chunk_precision']*100,2))


if __name__ == '__main__':
    main()
