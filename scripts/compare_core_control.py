"""Read-only core-alone control using shared query vectors from combined A/B."""
from datetime import date
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.search.query import retrieve
from compare_pdf_search import FixedQueryEmbedder


def main():
    out=Path('data/generated/core-pdf-search-ab')
    settings=get_settings().model_copy(update={'search_document_datasets':'core,docs',
        'search_chunk_filter':False,'search_answerability_judge':False,
        'search_rerank_chunks':False,'search_query_rewrite':False})
    cache={}
    for path in [Path('data/generated/common-pdf-search-ab/embedding_cache.jsonl'),out/'embedding_cache.jsonl']:
        if path.exists():
            for line in path.open():
                r=json.loads(line);cache[r['key']]=r['vector']
    client=create_client(settings)
    indexes=list(client.indices.get_alias(name=settings.search_index_alias));assert len(indexes)==1
    queries=[json.loads(l) for l in Path('data/queries_v1.jsonl').read_text().splitlines()]
    queries=[q for q in queries if q['category']!='hsk']
    results=[]
    for mode in ['bm25','hybrid']:
        for q in queries:
            key=hashlib.sha256((settings.ollama_embedding_model+'\n'+q['query']).encode()).hexdigest()
            with patch('search_engine.search.query.get_settings',return_value=settings):
                hits=retrieve(client,indexes[0],q['query'],date.today(),5,
                    embedder=FixedQueryEmbedder(cache[key]),mode=mode,strict=True,
                    answerability=False,query_rewrite=False,rerank_chunks=False)
            gold=set(q['gold']);parents=[h.parent_id for h in hits]
            rank=next((i+1 for i,p in enumerate(parents) if p in gold),None)
            results.append({'qid':q['qid'],'mode':mode,'document_hit_at_5':bool(rank),
                'document_p1':bool(parents and parents[0] in gold),
                'mrr_at_5':1/rank if rank else 0,'hits':[h.model_dump() for h in hits]})
        rows=[r for r in results if r['mode']==mode]
        print(mode,'P1',sum(r['document_p1'] for r in rows),'Hit5',sum(r['document_hit_at_5'] for r in rows),
            'MRR',sum(r['mrr_at_5'] for r in rows)/len(rows),flush=True)
    (out/'core_only_control.json').write_text(json.dumps({'index':indexes[0],'queries':results},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
