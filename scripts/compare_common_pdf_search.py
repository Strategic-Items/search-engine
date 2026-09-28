"""Compare every PDF shared by live index and new export; preserve background.

All existing 135 questions measure document retrieval. The 15 existing PDF
questions additionally use explicit content evidence fixtures, independent of IDs.
New PDFs without baseline are inventoried, never scored as improvements.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from unittest.mock import patch
from uuid import uuid4

from opensearchpy.helpers import scan, streaming_bulk
from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.indexing.documents import SearchDocument
from search_engine.search.query import retrieve
from compare_pdf_search import norm, FixedQueryEmbedder

OUT = Path('data/generated/common-pdf-search-ab')
CURRENT = Path('/Users/jeongbin/git/unstructured-doc-parser_ver2/data/chunks/docs.jsonl')
QUERIES = Path('data/queries_docs_v2.jsonl')
PREVIOUS_CHECKS = Path('/Users/jeongbin/git/unstructured-doc-parser_ver2/scripts/issue34/comparison_2026_587/evidence_checks.jsonl')


def read(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def key(path):
    # Only known review tags at the filename end; statutory identifier stays intact.
    return re.sub(r'\((?:법령|표위주)\)(?=\.pdf$)', '', path)


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    settings = get_settings().model_copy(update={'search_chunk_filter':False,
                                                'search_answerability_judge':False,
                                                'search_rerank_chunks':False,
                                                'search_query_rewrite':False})
    client = create_client(settings)
    aliases = list(client.indices.get_alias(name=settings.search_docs_alias))
    assert len(aliases)==1
    source = aliases[0]
    corpus = list(scan(client,index=source,query={'query':{'match_all':{}}}))
    old_by_path, new_by_path = defaultdict(list), defaultdict(list)
    current_rows = read(CURRENT)
    for h in corpus:
        if h['_source'].get('source_path','').endswith('.pdf'):
            old_by_path[key(h['_source']['source_path'])].append(h['_source'])
    for row in current_rows:
        new_by_path[key(row['source_path'])].append(row)
    common = sorted(old_by_path.keys() & new_by_path.keys())
    if not common:
        raise ValueError('No shared PDFs')
    for name in common:
        assert len({r['parent_id'] for r in old_by_path[name]})==1
        assert len({r['parent_id'] for r in new_by_path[name]})==1
    old_parents = {r['parent_id'] for name in common for r in old_by_path[name]}
    remap = {old_by_path[name][0]['parent_id']:new_by_path[name][0]['parent_id'] for name in common}
    background = [h for h in corpus if h['_source']['parent_id'] not in old_parents]
    arms = {'previous':[deepcopy(r) for name in common for r in old_by_path[name]],
            'current':[SearchDocument.model_validate(r).index_source() for name in common for r in new_by_path[name]]}
    inventory = {'source_index':source,'source_count':len(corpus),'fixed_background':len(background),
                 'current_sha256':hashlib.sha256(CURRENT.read_bytes()).hexdigest(),
                 'queries_sha256':hashlib.sha256(QUERIES.read_bytes()).hexdigest(),
                 'common':[{'path':name,'previous_chunks':len(old_by_path[name]),
                            'current_chunks':len(new_by_path[name]),
                            'old_parent':old_by_path[name][0]['parent_id'],
                            'new_parent':new_by_path[name][0]['parent_id']} for name in common],
                 'new_without_baseline':sorted(new_by_path.keys()-old_by_path.keys()),
                 'old_without_current':sorted(old_by_path.keys()-new_by_path.keys()),
                 'model':settings.ollama_embedding_model,'as_of':date.today().isoformat(),
                 'llm_filter':False,'target_vectors_regenerated_for_both':True,
                 'background_vectors':'copied unchanged','query_vectors':'shared between arms and modes'}
    write_json('inventory.json',inventory)
    write_json('previous_pdf_snapshot.json',arms['previous'])
    write_json('current_pdf_snapshot.json',arms['current'])
    print(f'Common PDFs {len(common)}, new without baseline {len(inventory["new_without_baseline"])}, background {len(background)}',flush=True)
    # Explicit fixtures for every PDF question in the existing independent dataset.
    export_clause = '보세판매장에서 외국인에게 국내에서 생산(제조ㆍ가공ㆍ조립ㆍ수리ㆍ재생 또는 개조하는 것을 말한다. 이하 같다)된 물품을 매도하는 것'
    fixtures = {r['qid']:r['required_evidence'] for r in read(PREVIOUS_CHECKS) if r['group']=='existing_search_question'}
    fixtures.update({
        'docs-v2-005':[export_clause],
        'docs-v2-010':['블랙매스 및 블랙파우더','2620.99.0000','할당'],
        'docs-v2-025':['출입증 교환','면접 시 본인확인','총 2개의 신분증 필요'],
        'docs-v2-026':['면접시간 20분 전까지'],
        'docs-v2-027':['2026. 9. 18.(금)','산업통상부 홈페이지','나라 일터','합격자 개별 통보','발표일이 지연될 수 있음'],
        'docs-v2-036':['면접시간 20분 전까지','총 2개의 신분증 필요'],
        'docs-v2-040':[export_clause,'제37조(전략물자 판정 업무 등의 위탁)','판정 및 통보 업무','위탁한다'],
        'docs-v2-132':['2026. 9. 14.(월) 13:30 ~ 17:00','정부세종청사 13동 산업통상부 626호'],
    })
    queries = read(QUERIES)
    pdf_questions = [q for q in queries if any(key(e.get('source_path','')) in common for e in q.get('evidence',[]))]
    assert set(fixtures)=={q['qid'] for q in pdf_questions}
    write_json('evidence_fixtures.json',fixtures)
    # Verify fixture availability independent of retrieval; missing anchors are visible.
    availability=[]
    for q in pdf_questions:
        paths={key(e['source_path']) for e in q['evidence'] if e['source_path'].endswith('.pdf')}
        for arm,groups in [('previous',old_by_path),('current',new_by_path)]:
            texts=[norm(r['body']) for path in paths for r in groups[path]]
            availability.append({'qid':q['qid'],'arm':arm,
                                 'found':[any(norm(a) in t for t in texts) for a in fixtures[q['qid']]]})
    write_json('evidence_availability.json',availability)
    embedder=OllamaEmbedder(settings)
    cache_path=OUT/'embedding_cache.jsonl'
    cache={r['key']:r['vector'] for r in read(cache_path)} if cache_path.exists() else {}
    def vector_key(text):
        return hashlib.sha256((settings.ollama_embedding_model+'\n'+text).encode()).hexdigest()
    def cached_embed(texts):
        todo=list(dict.fromkeys(t for t in texts if vector_key(t) not in cache))
        with cache_path.open('a') as file:
            for start in range(0,len(todo),16):
                batch=todo[start:start+16]
                for text,vector in zip(batch,embedder.embed(batch)):
                    k=vector_key(text);cache[k]=vector
                    file.write(json.dumps({'key':k,'vector':vector})+'\n')
                file.flush()
                print(f'Embeddings {min(start+16,len(todo))}/{len(todo)}',flush=True)
        return [cache[vector_key(t)] for t in texts]
    for arm,rows in arms.items():
        vectors=cached_embed([embedding_text(r['title'],r['body']) for r in rows])
        for row,vector in zip(rows,vectors):row['embedding']=vector
        print(f'{arm} ready {len(rows)} PDF chunks',flush=True)
    q_vectors=dict(zip((q['qid'] for q in queries),cached_embed([q['query'] for q in queries])))
    original_settings=client.indices.get_settings(index=source)[source]['settings']['index']
    index_settings={k:original_settings[k] for k in ('analysis','number_of_shards','number_of_replicas','knn')}
    mapping=client.indices.get_mapping(index=source)[source]['mappings']
    created=[];results=[]
    try:
        for arm,rows in arms.items():
            target=f'common-pdf-ab-{uuid4().hex[:12]}-{arm}'
            client.indices.create(index=target,body={'settings':index_settings,'mappings':mapping});created.append(target)
            actions=[{'_index':target,'_id':h['_id'],'_source':h['_source']} for h in background]
            actions += [{'_index':target,'_id':r['id'],'_source':r} for r in rows]
            for ok,_ in streaming_bulk(client,actions,chunk_size=200,raise_on_error=True):assert ok
            client.indices.refresh(index=target);assert client.count(index=target)['count']==len(actions)
            for mode in ('bm25','vector','hybrid'):
                for n,q in enumerate(queries,1):
                    with patch('search_engine.search.query.get_settings',return_value=settings):
                        hits=retrieve(client,target,q['query'],date.today(),5,
                                      embedder=FixedQueryEmbedder(q_vectors[q['qid']]),mode=mode,
                                      strict=True,answerability=False,query_rewrite=False,rerank_chunks=False)
                    translate=lambda pid:remap.get(pid,pid) if arm=='current' else pid
                    gold_groups=[[translate(pid) for pid in group] for group in q.get('gold_groups',[q['gold']])]
                    returned=[h.parent_id for h in hits]
                    found_groups=[any(pid in returned for pid in group) for group in gold_groups]
                    relevant={pid for group in gold_groups for pid in group}
                    rank=next((i+1 for i,h in enumerate(hits) if h.parent_id in relevant),None)
                    record={'arm':arm,'mode':mode,'qid':q['qid'],'query':q['query'],
                            'document_all_at_5':all(found_groups),'document_group_recall':sum(found_groups)/len(found_groups),
                            'mrr_at_5':1/rank if rank else 0,
                            'hits':[h.model_dump() for h in hits],
                            'changed_pdf_question':q['qid'] in fixtures}
                    if q['qid'] in fixtures:
                        paths={key(e['source_path']) for e in q['evidence'] if e['source_path'].endswith('.pdf')}
                        groups=old_by_path if arm=='previous' else new_by_path
                        target_parents={groups[path][0]['parent_id'] for path in paths}
                        passages=[(h.parent_id,h.id,h.body) for h in hits]
                        passages += [(h.parent_id,p.id,p.body) for h in hits for p in h.passages]
                        passages=list({cid:(pid,cid,body) for pid,cid,body in passages}.values())
                        anchors=[norm(a) for a in fixtures[q['qid']]]
                        found=[any(pid in target_parents and anchor in norm(body) for pid,_,body in passages) for anchor in anchors]
                        record.update(evidence_found=found,evidence_all=all(found),
                                      evidence_recall=sum(found)/len(found),
                                      normalized_chars=sum(len(norm(body)) for _,_,body in passages),
                                      returned_chunks=len(passages),
                                      pdf_document_hit=any(h.parent_id in target_parents for h in hits),
                                      document_paths=sorted(paths))
                    results.append(record)
                    if n%25==0 or n==len(queries):print(f'{arm} {mode} {n}/{len(queries)}',flush=True)
                write_json('results.json',{'inventory':inventory,'queries':results})
    finally:
        for target in created:client.indices.delete(index=target)
        assert list(client.indices.get_alias(name=settings.search_docs_alias))==aliases
        print('Temporary indexes removed; service alias unchanged',flush=True)
    summaries=[]
    for scope in ('all135','pdf15'):
        for mode in ('bm25','vector','hybrid'):
            for arm in arms:
                group=[r for r in results if r['arm']==arm and r['mode']==mode and
                       (scope=='all135' or r['changed_pdf_question'])]
                fields=['document_all_at_5','document_group_recall','mrr_at_5']
                if scope=='pdf15':fields+=['pdf_document_hit','evidence_all','evidence_recall','normalized_chars']
                summaries.append({'scope':scope,'arm':arm,'mode':mode,'n':len(group),
                                  **{f:sum(r[f] for r in group)/len(group) for f in fields}})
    write_json('summary.json',summaries)
    lines=['# 공통 PDF 전체 검색 비교','','실제 이전 색인의 공통 PDF 4개를 현재 청크로 교체하고 나머지 HWP/HWPX 문서는 고정했다.',
           '새 PDF 34개는 이전 기준선이 없어 비교 색인에 추가하지 않았다. 목록은 inventory.json에 있다.',
           '동일 모델로 양쪽 공통 PDF를 재임베딩하고 질문 벡터를 공유했다. 서비스 alias는 유지하고 임시 색인은 제거했다.',
           'LLM 필터·답변 가능성 판정·재랭킹·재작성은 끈 검색기 비교다. 상위 문서 5개·문서당 최대 6개 청크 기준.', '',
           '| 문서 | 이전 청크 | 현재 청크 |','|---|---:|---:|']
    lines += [f"| {Path(r['path']).name} | {r['previous_chunks']} | {r['current_chunks']} |" for r in inventory['common']]
    lines += ['', '## 기존 전체 질문 135개: 문서 검색', '',
              '| 모드 | 버전 | 모든 정답 문서군 발견 | 문서군 Recall | MRR@5 |','|---|---|---:|---:|---:|']
    for r in summaries:
        if r['scope']=='all135':lines.append(f"| {r['mode']} | {r['arm']} | {r['document_all_at_5']:.3f} | {r['document_group_recall']:.3f} | {r['mrr_at_5']:.3f} |")
    lines+=['','## PDF 관련 기존 질문 15개: 실제 반환 근거','','| 모드 | 버전 | PDF 발견 | 근거 완비율 | 필수 구절 Recall | 평균 정규화 본문 길이 |','|---|---|---:|---:|---:|---:|']
    for r in summaries:
        if r['scope']=='pdf15':lines.append(f"| {r['mode']} | {r['arm']} | {r['pdf_document_hit']:.3f} | {r['evidence_all']:.3f} | {r['evidence_recall']:.3f} | {r['normalized_chars']:.1f} |")
    lines+=['','## 문서별 하이브리드 결과','','| PDF | 질문 수 | 근거 완비 이전→현재 | 평균 본문 이전→현재 |','|---|---:|---|---|']
    for path in common:
        groups=[[r for r in results if r['mode']=='hybrid' and r['arm']==arm and path in r.get('document_paths',[])] for arm in arms]
        if groups[0]:
            rates=[f"{sum(r['evidence_all'] for r in g)}/{len(g)}" for g in groups]
            lengths=[f"{sum(r['normalized_chars'] for r in g)/len(g):.1f}" for g in groups]
            lines.append(f"| {Path(path).name} | {len(groups[0])} | {' → '.join(rates)} | {' → '.join(lengths)} |")
    lines+=['','## 개선·회귀 질문','','청크 ID가 아닌 필수 구절 기준이며, 해당 PDF에서 반환된 근거만 인정한다.']
    lookup={(r['arm'],r['mode'],r['qid']):r for r in results}
    for mode in ('bm25','vector','hybrid'):
        for q in pdf_questions:
            before=lookup['previous',mode,q['qid']];after=lookup['current',mode,q['qid']]
            if before['evidence_all']!=after['evidence_all']:
                lines.append(f"- {mode} {q['qid']}: {'개선' if after['evidence_all'] else '회귀'} — {q['query']}")
    lines += ['', '정규화는 공백·제목 기호·페이지 주석·HTML 태그 제거다. 문자 수는 토큰 수가 아니다.',
              '근거 포함은 검색된 본문에서 필수 구절을 확인하는 대리지표이며 의미적 답변 정확성 전체를 평가하지 않는다.',
              '문서별 질문 수가 적고, 새 PDF 34개에는 비교 기준선과 기존 근거 질문이 없다. 전체 38개가 개선됐다고 일반화할 수 없다.',
              '이 비교는 HWP/HWPX 배경을 유지한다. 현재 PDF 전용 JSONL을 통째로 배포하면서 기존 HWP/HWPX를 제거하는 효과와는 다르다.']
    budget_rows=[]
    path_parents={arm:{path:groups[path][0]['parent_id'] for path in common}
                  for arm,groups in [('previous',old_by_path),('current',new_by_path)]}
    for record in results:
        if record['mode']!='hybrid' or not record['changed_pdf_question']:
            continue
        for budget in (1000,2000,4000,8000):
            left=budget;selected=[]
            for hit in record['hits']:
                for passage in [{'body':hit['body']},*hit['passages']]:
                    if left<=0:
                        break
                    text=norm(passage['body'])
                    selected.append((hit['parent_id'],text[:left]))
                    left-=min(left,len(text))
            relevant={path_parents[record['arm']][path] for path in record['document_paths']}
            found=[any(pid in relevant and norm(a) in text for pid,text in selected)
                   for a in fixtures[record['qid']]]
            budget_rows.append({'arm':record['arm'],'qid':record['qid'],
                                'budget_chars':budget,'found':found,'all_evidence':all(found)})
    write_json('character_budget_checks.json',budget_rows)
    lines+=['','## 하이브리드 동일 문자 예산 점검','',
            '반환 순서대로 정규화 본문을 자른다. 토큰 예산이 아닌 문자 예산의 대리지표다.','',
            '| 문자 예산 | 이전 근거 완비 | 현재 근거 완비 |','|---|---:|---:|']
    for budget in (1000,2000,4000,8000):
        counts=[sum(r['all_evidence'] for r in budget_rows if r['arm']==arm and r['budget_chars']==budget) for arm in arms]
        lines.append(f'| {budget} | {counts[0]}/15 | {counts[1]}/15 |')
    (OUT/'report.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines),flush=True)


if __name__=='__main__':main()
