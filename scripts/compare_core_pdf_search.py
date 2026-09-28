"""Core+docs retrieval A/B on frozen live core and all current PDF chunks."""
from collections import defaultdict
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import httpx

from opensearchpy.helpers import scan, streaming_bulk
from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.indexing.documents import SearchDocument
from search_engine.search.query import retrieve
from compare_pdf_search import norm, FixedQueryEmbedder
from compare_common_pdf_search import key

OUT=Path('data/generated/core-pdf-search-ab')
CURRENT=Path('/Users/jeongbin/git/unstructured-doc-parser_ver2/data/chunks/docs.jsonl')
COMMON=Path('data/generated/common-pdf-search-ab')


def read(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    settings=get_settings().model_copy(update={'search_document_datasets':'core,docs',
        'search_chunk_filter':False,'search_answerability_judge':False,
        'search_rerank_chunks':False,'search_query_rewrite':False})
    client=create_client(settings)
    core_aliases=list(client.indices.get_alias(name=settings.search_index_alias))
    docs_aliases=list(client.indices.get_alias(name=settings.search_docs_alias))
    assert len(core_aliases)==len(docs_aliases)==1
    core,docs=core_aliases[0],docs_aliases[0]
    original_core_count=client.count(index=core)['count']
    old_hits=list(scan(client,index=docs,query={'query':{'match_all':{}}}))
    previous=[h['_source'] for h in old_hits]
    current=[SearchDocument.model_validate(r).index_source() for r in read(CURRENT)]
    old_paths,new_paths=defaultdict(list),defaultdict(list)
    for r in previous:old_paths[key(r.get('source_path',''))].append(r)
    for r in current:new_paths[key(r['source_path'])].append(r)
    shared=sorted(old_paths.keys() & new_paths.keys())
    old_targets=[r for path in shared for r in old_paths[path]]
    new_targets=[r for path in shared for r in new_paths[path]]
    background=[r for r in previous if key(r.get('source_path','')) not in shared]
    remap={old_paths[path][0]['parent_id']:new_paths[path][0]['parent_id'] for path in shared}
    arms={'previous':deepcopy(previous),'common_pdf_only':deepcopy(background+new_targets),
          'current_pdf_export':deepcopy(current),'current_pdf_keep_hwp':deepcopy(background+current)}
    docs_questions=[dict(q,question_set='docs135') for q in read(Path('data/queries_docs_v2.jsonl'))]
    core_questions=[dict(q,question_set='core75') for q in read(Path('data/queries_v1.jsonl')) if q['category']!='hsk']
    questions=docs_questions+core_questions
    assert len(questions)==210
    core_parents={h['_source']['parent_id'] for h in scan(client,index=core,
        query={'_source':['parent_id'],'query':{'match_all':{}}})}
    assert all(set(q['gold']) & core_parents for q in core_questions)
    fixtures=json.loads((COMMON/'evidence_fixtures.json').read_text())
    inventory={'core_index':core,'core_chunks':original_core_count,'previous_docs_index':docs,
        'previous_docs_chunks':len(previous),'shared_pdf_count':len(shared),
        'current_pdf_count':len(new_paths),'arm_docs_counts':{a:len(rows) for a,rows in arms.items()},
        'current_export_sha256':hashlib.sha256(CURRENT.read_bytes()).hexdigest(),
        'question_counts':{'docs135':135,'core75':75},'hsks_excluded':18,
        'as_of':date.today().isoformat(),'model':settings.ollama_embedding_model,
        'k':5,'chunks_per_document':settings.search_chunks_per_document,
        'llm_filter_and_judge':False,'mode':['bm25','hybrid'],
        'note':'Frozen core plus one temporary docs index; shared query vectors; DFS for lexical cross-index search.'}
    inventory['embedding_overflow_policy']='On context overflow only: same per-input prefix reduction for all arms; full text retained in lexical index.'
    write('inventory.json',inventory)
    print(inventory['arm_docs_counts'],flush=True)
    cache={}
    for cache_path in [COMMON/'embedding_cache.jsonl',OUT/'embedding_cache.jsonl']:
        if cache_path.exists():cache.update({r['key']:r['vector'] for r in read(cache_path)})
    embedder=OllamaEmbedder(settings)
    def cache_key(text):return hashlib.sha256((settings.ollama_embedding_model+'\n'+text).encode()).hexdigest()
    def cached(texts,label):
        pending=list(dict.fromkeys(t for t in texts if cache_key(t) not in cache))
        with (OUT/'embedding_cache.jsonl').open('a') as file:
            for start in range(0,len(pending),16):
                batch=pending[start:start+16]
                try:
                    vectors=embedder.embed(batch)
                except httpx.HTTPStatusError as error:
                    if error.response.status_code!=400 or 'context length' not in error.response.text:
                        raise
                    vectors=[]
                    for text in batch:
                        used=text
                        while True:
                            try:
                                vector=embedder.embed([used])[0]
                                break
                            except httpx.HTTPStatusError as single_error:
                                if single_error.response.status_code!=400 or 'context length' not in single_error.response.text:
                                    raise
                                if len(used)<256:
                                    raise
                                used=used[:len(used)//2]
                        vectors.append(vector)
                        if used!=text:
                            record={'key':cache_key(text),'original_chars':len(text),'embedded_prefix_chars':len(used)}
                            with (OUT/'embedding_overflows.jsonl').open('a') as overflow_file:
                                overflow_file.write(json.dumps(record)+'\n')
                            print(f'Overflow prefix fallback {len(text)} -> {len(used)} chars',flush=True)
                for text,vector in zip(batch,vectors):
                    k=cache_key(text);cache[k]=vector;file.write(json.dumps({'key':k,'vector':vector})+'\n')
                file.flush();print(f'{label} embeddings {min(start+16,len(pending))}/{len(pending)}',flush=True)
        return [cache[cache_key(t)] for t in texts]
    # Reuse current-model vectors already generated for common PDFs in preceding A/B.
    q_vectors=dict(zip([q['qid'] for q in questions],cached([q['query'] for q in questions],'query')))
    source_settings=client.indices.get_settings(index=docs)[docs]['settings']['index']
    index_settings={k:source_settings[k] for k in ['analysis','number_of_shards','number_of_replicas','knn']}
    mapping=client.indices.get_mapping(index=docs)[docs]['mappings']
    results=[];created=[]
    prior_results=OUT/'results.json'
    if prior_results.exists():
        saved=json.loads(prior_results.read_text())
        checks=['core_index','previous_docs_index','current_export_sha256','model','as_of']
        if all(saved['inventory'][k]==inventory[k] for k in checks):
            results=saved['queries']
    try:
        for arm,rows in arms.items():
            existing=[r for r in results if r['arm']==arm]
            if len(existing)==420 and len({(r['mode'],r['qid']) for r in existing})==420:
                print(f'{arm}: reuse {len(existing)} completed results',flush=True)
                continue
            results=[r for r in results if r['arm']!=arm]
            # Existing HWP/HWPX and core vectors stay fixed. All PDF targets use the same model.
            pdf_rows=[r for r in rows if r.get('source_path','').endswith('.pdf')]
            vectors=cached([embedding_text(r['title'],r['body']) for r in pdf_rows],arm)
            for r,vector in zip(pdf_rows,vectors):r['embedding']=vector
            target=f'core-pdf-ab-{uuid4().hex[:12]}-{arm.replace("_","-")}'
            client.indices.create(index=target,body={'settings':index_settings,'mappings':mapping});created.append(target)
            actions=[{'_index':target,'_id':r['id'],'_source':r} for r in rows]
            for ok,_ in streaming_bulk(client,actions,chunk_size=200,raise_on_error=True):assert ok
            client.indices.refresh(index=target);assert client.count(index=target)['count']==len(rows)
            indexed_parents=core_parents|{r['parent_id'] for r in rows}
            print(f'{arm}: search {core} + {len(rows)} docs chunks',flush=True)
            for mode in ['bm25','hybrid']:
                for i,q in enumerate(questions,1):
                    with patch('search_engine.search.query.get_settings',return_value=settings):
                        hits=retrieve(client,f'{core},{target}',q['query'],date.today(),5,
                            embedder=FixedQueryEmbedder(q_vectors[q['qid']]),mode=mode,strict=True,
                            answerability=False,query_rewrite=False,rerank_chunks=False)
                    translate=lambda p:remap.get(p,p) if arm!='previous' else p
                    groups=[[translate(p) for p in g] for g in q.get('gold_groups',[q['gold']])]
                    gold={p for g in groups for p in g};returned=[h.parent_id for h in hits]
                    found=[any(p in returned for p in g) for g in groups]
                    rank=next((i+1 for i,p in enumerate(returned) if p in gold),None)
                    r={'arm':arm,'mode':mode,'qid':q['qid'],'question_set':q['question_set'],
                       'query':q['query'],'document_hit_at_5':bool(rank),
                       'document_p1':bool(returned and returned[0] in gold),
                       'document_all_at_5':all(found),'document_recall':sum(found)/len(found),
                       'mrr_at_5':1/rank if rank else 0,
                       'gold_available':all(any(p in indexed_parents for p in g) for g in groups),
                       'hits':[h.model_dump() for h in hits]}
                    if q['qid'] in fixtures:
                        paths={key(e['source_path']) for e in q['evidence'] if e['source_path'].endswith('.pdf')}
                        path_groups=old_paths if arm=='previous' else new_paths
                        pdf_parents={path_groups[path][0]['parent_id'] for path in paths}
                        passages=[(h.parent_id,h.id,h.body) for h in hits]
                        passages += [(h.parent_id,p.id,p.body) for h in hits for p in h.passages]
                        passages=list({cid:(pid,cid,body) for pid,cid,body in passages}.values())
                        anchors=[norm(a) for a in fixtures[q['qid']]]
                        ef=[any(pid in pdf_parents and a in norm(body) for pid,_,body in passages) for a in anchors]
                        r.update(evidence_all=all(ef),evidence_recall=sum(ef)/len(ef),
                                 evidence_found=ef,normalized_chars=sum(len(norm(body)) for _,_,body in passages))
                    results.append(r)
                    if i%30==0 or i==len(questions):print(f'{arm} {mode} {i}/{len(questions)}',flush=True)
                write('results.json',{'inventory':inventory,'queries':results})
    finally:
        for target in created:client.indices.delete(index=target)
        assert list(client.indices.get_alias(name=settings.search_index_alias))==core_aliases
        assert list(client.indices.get_alias(name=settings.search_docs_alias))==docs_aliases
        assert client.count(index=core)['count']==original_core_count
        print('Temporary indexes removed; core and docs aliases unchanged',flush=True)
    summaries=[]
    for scope in ['docs135','core75','pdf15']:
        for arm in arms:
            for mode in ['bm25','hybrid']:
                group=[r for r in results if r['arm']==arm and r['mode']==mode and
                    (r['qid'] in fixtures if scope=='pdf15' else r['question_set']==scope)]
                fields=['document_hit_at_5','document_p1','document_all_at_5','document_recall','mrr_at_5','gold_available']
                if scope=='pdf15':fields+=['evidence_all','evidence_recall','normalized_chars']
                summaries.append({'scope':scope,'arm':arm,'mode':mode,'n':len(group),
                    **{f:sum(r[f] for r in group)/len(group) for f in fields}})
    write('summary.json',summaries)
    lines=['# core+docs PDF 변경 검색 비교','',
        '실제 core 3,956청크를 고정하고 네 가지 docs 버전을 각각 함께 검색했다. 두 색인은 DFS로 어휘 통계를 합친다.',
        '- previous: 기존 docs 1,198청크.',
        '- common_pdf_only: 공통 PDF 4개만 변경. 기존 HWP/HWPX 유지.',
        '- current_pdf_export: 현재 PDF 전용 JSONL 38개를 그대로 적용. 기존 HWP/HWPX 제외.',
        '- current_pdf_keep_hwp: PDF 38개와 기존 HWP/HWPX를 함께 유지.',
        'LLM 필터·답변 가능성 판정·재랭커·재작성은 껐다. 질문 벡터 공유, PDF는 같은 모델로 임베딩. 서비스 alias는 변경하지 않았다.','']
    overflow_path=OUT/'embedding_overflows.jsonl'
    if overflow_path.exists():
        overflow_rows=read(overflow_path)
        lines += [f"임베딩 입력 길이 초과 {len({r['key'] for r in overflow_rows})}개는 평가용으로 앞부분을 줄여 임베딩했다. 어휘 색인 본문은 전체를 보존했다.",
                  '현재 JSONL 전체를 기존 임베딩 코드에 그대로 넣으면 길이 초과로 실패한다. 전체 PDF 실험은 이 예외 처리를 포함한 결과이며 기존 설정 그대로의 배포 검증은 아니다.','']
    for scope in ['core75','docs135','pdf15']:
        lines += [f'## {scope}','',
            '| 버전 | 검색 | 정답 문서 가용률 | Hit@5 | P@1 | 모든 문서군 발견 | MRR@5 |'+(' 근거 완비율 |' if scope=='pdf15' else ''),
            '|---|---|---:|---:|---:|---:|---:|'+('---:|' if scope=='pdf15' else '')]
        for r in summaries:
            if r['scope']==scope:lines.append(f"| {r['arm']} | {r['mode']} | {r['gold_available']:.3f} | {r['document_hit_at_5']:.3f} | {r['document_p1']:.3f} | {r['document_all_at_5']:.3f} | {r['mrr_at_5']:.3f} |"+(f" {r['evidence_all']:.3f} |" if scope=='pdf15' else ''))
    lookup={(r['arm'],r['mode'],r['qid']):r for r in results}
    changes=[]
    for arm in list(arms)[1:]:
        for q in questions:
            before=lookup['previous','hybrid',q['qid']];after=lookup[arm,'hybrid',q['qid']]
            if before['document_all_at_5']!=after['document_all_at_5'] or before['document_p1']!=after['document_p1']:
                changes.append({'arm':arm,'qid':q['qid'],'query':q['query'],'question_set':q['question_set'],
                    'before_all':before['document_all_at_5'],'after_all':after['document_all_at_5'],
                    'before_p1':before['document_p1'],'after_p1':after['document_p1'],
                    'gold_available':after['gold_available']})
    write('hybrid_changes.json',changes)
    lines+=['','core 질문 75개는 문서 정답 라벨만 있어 근거 완비를 채점하지 않았다. legacy 라벨의 공동 정답 검토 한계가 있다.',
        'PDF 근거 15개는 필수 구절 포함으로 채점했다. 현재 PDF-only 버전의 docs 가용률 하락은 청킹 실패와 문서 제외 효과를 구분해야 한다.',
        'core를 재청킹한 실험은 아니다. docs 변경이 core+docs 검색에 미치는 영향을 비교했다.',
        '34개 새 PDF의 직접 전후 비교 기준선은 없지만, 추가된 PDF가 기존 질문의 경쟁 결과에 미치는 효과는 측정했다.',
        '전체 검색 본문과 질문별 변화는 results.json, hybrid_changes.json에 보존했다.']
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines),flush=True)


if __name__=='__main__':main()
