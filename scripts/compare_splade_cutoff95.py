"""BM25+vector와 SPLADE+vector를 같은 문서/청크 전달 정책으로 비교한다."""
import copy
from datetime import date
import json
from pathlib import Path
from unittest.mock import patch

from search_engine.client import create_client
from search_engine.config import Settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.evaluation.evaluate import quality_metrics
from search_engine.search.query import retrieve, _validity_filters, _docket_filter


def main():
    settings = Settings(search_answerability_judge=False, search_chunk_filter=False,
                        search_query_rewrite=False, search_rerank_chunks=False)
    client = create_client(settings)
    index = ','.join(sorted(client.indices.get(index=settings.search_docs_alias)))
    query_rows = json.loads(Path('data/generated/docs-v2/evaluation-135q-docs-only-no-judge.json').read_text())['queries']
    saved = json.loads(Path('data/generated/docs-v2/comparison-135q-splade-ko.json').read_text())
    rankings = {r['qid']:r['chunk_ranked'] for r in saved['results']}
    wanted = sorted({c['chunk_id'] for rank in rankings.values() for c in rank})
    sources = {}
    for start in range(0,len(wanted),200):
        response = client.search(index=index,body={'query':{'ids':{'values':wanted[start:start+200]}},'size':200})
        sources.update({h['_id']:h['_source'] for h in response['hits']['hits']})
    if set(wanted)-sources.keys():
        raise ValueError('SPLADE saved corpus differs from live index')
    embedder = OllamaEmbedder(settings)
    results = {'bm25_vector':[], 'splade_vector':[]}
    unscored = {method:0 for method in results}
    as_of = date.today()
    for position,row in enumerate(query_rows,1):
        vector = embedder.embed_query(row['query'])
        class FixedEmbed:
            def embed_query(self,q):
                return vector
        # Filter saved SPLADE candidates using the same validity/docket constraints.
        allowed = client.search(index=index,body={'query':{'bool':{'filter':[
            *_validity_filters(as_of), *_docket_filter(row['query']),
            {'ids':{'values':[c['chunk_id'] for c in rankings[row['qid']]]}}]}},
            'size':len(rankings[row['qid']]), '_source':False})
        allowed_ids = {h['_id'] for h in allowed['hits']['hits']}
        splade_hits = [{'_id':c['chunk_id'],'_score':c['score'],'_source':sources[c['chunk_id']]}
                       for c in rankings[row['qid']] if c['chunk_id'] in allowed_ids][:settings.search_vector_candidates]
        cache, scores = {}, {}
        class ReplayClient:
            method = 'bm25_vector'
            def search(self,**kwargs):
                query = kwargs.get('body',{}).get('query',{})
                # The only lexical search in retrieve: rewrite disabled.
                is_lexical = 'knn' not in query and ('function_score' in query or 'bool' in query and ('must' in query['bool'] or 'should' in query['bool']))
                if self.method == 'splade_vector' and is_lexical:
                    return {'_shards':{'failed':0},'hits':{'hits':copy.deepcopy(splade_hits)}}
                key=json.dumps(kwargs,sort_keys=True)
                if key not in cache:
                    cache[key]=client.search(**kwargs)
                    if 'knn' in query:
                        scores.update({h['_id']:h['_score'] for h in cache[key]['hits']['hits']})
                return copy.deepcopy(cache[key])
        replay = ReplayClient()
        for method in results:
            replay.method=method
            # SPLADE scores have a different scale; BM25's absolute floor is not reused.
            variant = settings if method=='bm25_vector' else settings.model_copy(update={'search_score_floor_bm25':0.0})
            with patch('search_engine.search.query.get_settings',return_value=variant):
                hits=retrieve(replay,index,row['query'],as_of,5,embedder=FixedEmbed(),
                              mode='hybrid',strict=True,query_rewrite=False,answerability=False)
            top=max((scores[c] for h in hits for c in h.chunk_ids if c in scores),default=0)
            parents, chunks=[],[]
            for hit in hits:
                kept=[c for c in hit.chunk_ids if c not in scores or scores[c]>=top*.95]
                unscored[method]+=sum(c not in scores for c in hit.chunk_ids)
                if kept:
                    parents.append(hit.parent_id);chunks.append(kept)
            results[method].append(dict(row,returned=parents,returned_chunks=chunks))
        if position%15==0:
            print(f'{position}/{len(query_rows)}',flush=True)
    summaries={}
    for method,rows in results.items():
        first=sum(bool(r['returned_chunks'] and any(r['returned_chunks'][0][0] in g for g in r['evidence_groups'])) for r in rows)
        summaries[method]={'metrics':quality_metrics(rows,5),'firstChunk':first,
                           'firstChunkAccuracy':first/len(rows),'unscoredChunksPreserved':unscored[method]}
    report={'source_splade':'data/generated/docs-v2/comparison-135q-splade-ko.json',
            'splade_model':saved['model'],'index':index,'queries':len(query_rows),'llm':False,
            'policy':{'document_top_k':5,'chunks_per_document':settings.search_chunks_per_document,
                      'document_ratio':settings.search_cutoff_ratio_hybrid,
                      'lexical_fusion_ratio':settings.fusion_trim_ratio('bm25'),
                      'dense_fusion_ratio':settings.fusion_trim_ratio('vector'),'chunk_ratio':.95,
                      'chunk_score':'native vector score, global best selected chunk; unknown scores preserved'},
            'methods':summaries,'query_results':results}
    output=Path('data/generated/splade-cutoff95-v1/comparison.json');output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(summaries,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
