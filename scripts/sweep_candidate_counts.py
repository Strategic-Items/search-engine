"""BM25 후보 수와 dense 후보 수를 따로 바꿔 가며 성능을 비교하는 읽기 전용 실험.

실험 당시 운영 값은 BM25 25개(`min(k*5, 100)`), dense 50개였고, 결과에 따라 dense를 25개로 낮췄다.
검색 호출의 size / knn k만 바꾸고 나머지 경로(컷오프, 청크 우선 융합)는 그대로 둔다.
LLM 판정·필터·리랭커·질의 재작성은 끈다.
"""
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

LEXICAL = [5, 10, 25, 50, 100]
VECTOR = [10, 25, 50, 100, 200]
BASELINE = (25, 50)


class SizedClient:
    """검색 종류(knn 여부)에 따라 size와 knn k를 덮어쓴다."""

    def __init__(self, client, lexical, vector):
        self.client, self.lexical, self.vector = client, lexical, vector

    def search(self, **kwargs):
        kwargs = copy.deepcopy(kwargs)
        knn = kwargs.get('body', {}).get('query', {}).get('knn')
        if knn:
            (field,) = knn
            knn[field]['k'] = self.vector
            kwargs['size'] = self.vector
        else:
            kwargs['size'] = self.lexical
        return self.client.search(**kwargs)


class CachedEmbed:
    def __init__(self, embedder):
        self.embedder, self.cache = embedder, {}

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
    rows = json.loads(Path('data/generated/docs-v2/evaluation-135q-docs-only-no-judge.json')
                      .read_text())['queries']
    cases = [(lex, vec) for lex in LEXICAL for vec in VECTOR]
    # 벡터 후보 수는 retrieve가 max(k*5, 설정값)으로 읽으므로 하한을 없애기 위해 설정값을 최소로 둔다.
    variant = settings.model_copy(update={'search_vector_candidates': 1})
    results = {case: [] for case in cases}
    for position, row in enumerate(rows, 1):
        for lex, vec in cases:
            sized = SizedClient(client, lex, vec)
            with patch('search_engine.search.query.get_settings', return_value=variant):
                hits = retrieve(sized, index, row['query'], date.today(), 5,
                                embedder=embedder, mode='hybrid', strict=True,
                                answerability=False, query_rewrite=False)
            results[(lex, vec)].append(dict(
                row, returned=[h.parent_id for h in hits],
                returned_chunks=[list(h.chunk_ids) for h in hits]))
        if position % 15 == 0:
            print(f'{position}/{len(rows)}', flush=True)
    summaries = []
    for (lex, vec), group in results.items():
        m = quality_metrics(group, 5)
        chunks = sum(len(c) for r in group for c in r['returned_chunks']) / len(group)
        summaries.append({'bm25': lex, 'dense': vec, 'mean_chunks': chunks, 'metrics': m})
    output = Path('data/generated/candidate-counts-v1/sweep.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'indexes': index, 'queries': len(rows), 'llm': False,
                                  'baseline': BASELINE, 'cases': summaries},
                                 ensure_ascii=False, indent=2))
    print('bm25 dense | doc P@1 Hit@5 MRR | evid R@5 P@5 | chunks')
    for s in summaries:
        m = s['metrics']
        mark = '*' if (s['bm25'], s['dense']) == BASELINE else ' '
        print(f"{mark}{s['bm25']:>4} {s['dense']:>4} | {m['precision_at_1']*100:5.1f} "
              f"{m['hit_at_5']*100:5.1f} {m['mrr_at_5']:.3f} | "
              f"{m.get('evidence_recall_at_5', 0)*100:5.1f} "
              f"{m.get('evidence_precision_at_5', 0)*100:5.1f} | {s['mean_chunks']:.2f}")


if __name__ == '__main__':
    main()
