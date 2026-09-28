"""저장된 검색 후보를 고정하고 청크 필터만 비교한다 (재검색 아님)."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from time import perf_counter

from search_engine.client import create_client
from search_engine.config import Settings
from search_engine.evaluation.evaluate import quality_metrics
from search_engine.search.chunk_filter import filter_chunks
from search_engine.search.results import SearchHit, Passage


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', default='data/generated/docs-v2/evaluation-135q-docs-only-no-judge.json')
    parser.add_argument('--output', default='data/generated/chunk-filter-v1/evaluation.json')
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    settings = Settings()
    client = create_client(settings)
    rows = json.loads(Path(args.report).read_text())['queries']
    ids = sorted({chunk for row in rows for group in row['returned_chunks'] for chunk in group})
    sources = {}
    for start in range(0, len(ids), 200):
        result = client.search(index=settings.search_docs_alias, body={
            'query': {'ids': {'values': ids[start:start + 200]}}, 'size': 200})
        sources.update({hit['_id']: hit['_source'] for hit in result['hits']['hits']})
    missing = set(ids) - sources.keys()
    if missing:
        raise RuntimeError(f'{len(missing)} saved chunks missing from current index')
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    def run(row):
        hits = []
        for parent, chunks in zip(row['returned'], row['returned_chunks']):
            lead = sources[chunks[0]]
            hits.append(SearchHit(id=chunks[0], parent_id=parent,
                title=lead.get('title', ''), body=lead.get('body', ''),
                passages=[Passage(id=chunk, body=sources[chunk].get('body', '')) for chunk in chunks[1:]]))
        started = perf_counter()
        filtered = filter_chunks(row['query'], hits, settings)
        result = dict(row, returned=[hit.parent_id for hit in filtered],
                      returned_chunks=[hit.chunk_ids for hit in filtered])
        result['filter_ms'] = (perf_counter() - started) * 1000
        result['grades'] = [[hit.chunk_relevance, *[p.relevance for p in hit.passages]] for hit in filtered]
        result['filter_failed'] = bool(filtered) and any(hit.chunk_relevance is None for hit in filtered)
        return result

    results = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run, row): row['qid'] for row in rows}
        for future in as_completed(futures):
            result = future.result()
            results[result['qid']] = result
            output.with_suffix('.progress.json').write_text(json.dumps(list(results.values()), ensure_ascii=False))
            if len(results) % 15 == 0:
                print(f'{len(results)}/{len(rows)}', flush=True)
    filtered = [results[row['qid']] for row in rows]
    summary = {'source': args.report, 'model': settings.chat_model,
               'comparison': 'fixed saved candidates; answerability judge not applied',
               'baseline': quality_metrics(rows, 5), 'filtered': quality_metrics(filtered, 5),
               'filter_failures': sum(row['filter_failed'] for row in filtered),
               'queries': filtered}
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != 'queries'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
