"""Isolated search A/B: live PDF chunks vs new export, fixed background corpus."""
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from html import unescape
from unittest.mock import patch
from uuid import uuid4

from opensearchpy.helpers import scan, streaming_bulk
from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.indexing.documents import SearchDocument
from search_engine.search.query import retrieve


SNAP = Path('/Users/jeongbin/git/unstructured-doc-parser_ver2/scripts/issue34/comparison_2026_587')
OUT = Path('data/generated/pdf-chunk-search-ab')


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def norm(text):
    text = re.sub(r'<!--.*?-->|<[^>]+>', '', text, flags=re.DOTALL)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    return re.sub(r'\s+', '', unescape(text))


class FixedQueryEmbedder:
    def __init__(self, vector):
        self.vector = vector

    def embed_query(self, query):
        return self.vector


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    live_settings = get_settings()
    settings = live_settings.model_copy(update={'search_answerability_judge': False,
                                               'search_chunk_filter': False,
                                               'search_rerank_chunks': False,
                                               'search_query_rewrite': False})
    client = create_client(settings)
    source_indexes = list(client.indices.get_alias(name=settings.search_docs_alias))
    if len(source_indexes) != 1:
        raise ValueError('Expected a single frozen source index')
    source = source_indexes[0]
    old_snapshot = load(SNAP / 'engine_index_snapshot.jsonl')
    new_rows = load(SNAP / 'current.jsonl')
    old_parent = old_snapshot[0]['parent_id']
    new_parent = new_rows[0]['parent_id']
    corpus = list(scan(client, index=source, query={'query': {'match_all': {}}}))
    baseline = [h for h in corpus if h['_source'].get('parent_id') == old_parent]
    background = [h for h in corpus if h['_source'].get('parent_id') != old_parent]
    if len(baseline) != 26 or len(new_rows) != 42:
        raise ValueError('Unexpected target counts')
    if {h['_id']: h['_source']['body'] for h in baseline} != {r['id']: r['body'] for r in old_snapshot}:
        raise ValueError('Live source differs from saved baseline')
    embedder = OllamaEmbedder(settings)
    arms = {'previous': [deepcopy(h['_source']) for h in baseline],
            'current': [SearchDocument.model_validate(r).index_source() for r in new_rows]}
    # Regenerate BOTH target versions using the same current model; background is frozen.
    for name, rows in arms.items():
        for start in range(0, len(rows), 16):
            batch = rows[start:start+16]
            vectors = embedder.embed([embedding_text(r['title'], r['body']) for r in batch])
            for row, vector in zip(batch, vectors):
                row['embedding'] = vector
            print(f'{name} embedded {min(start+16,len(rows))}/{len(rows)}', flush=True)
    cases = [r for r in load(SNAP / 'evidence_checks.jsonl') if r['group'] == 'existing_search_question']
    # Additional extraction probes catch restored schedule values that the seven questions omit.
    cases += [
        {'qid': 'schedule-final', 'query': '2026년 산업부 홍보 이미지 디자이너 휴직대체 채용 최종합격자 발표일은 언제야?',
         'required_evidence': ['최종합격자발표', '26.10.15.(목)']},
        {'qid': 'schedule-period', 'query': '2026년 산업부 홍보 이미지 디자이너 휴직대체 채용 모집공고와 원서접수 기간은 언제야?',
         'required_evidence': ['모집공고 및 원서접수', '26.9.8.(화)', '26.9.22.(화)']},
    ]
    vectors = {r['qid']: embedder.embed_query(r['query']) for r in cases}
    metadata = {'source_index': source, 'background_chunks': len(background),
                'previous_chunks': len(baseline), 'current_chunks': len(new_rows),
                'model': settings.ollama_embedding_model, 'query_vectors_shared': True,
                'target_vectors_regenerated_for_both': True, 'k_documents': 5,
                'chunks_per_document': settings.search_chunks_per_document,
                'as_of': date.today().isoformat(),
                'llm_filter_and_answerability': False,
                'settings': settings.model_dump(exclude={
                    'opensearch_password','opensearch_username','opensearch_url',
                    'ollama_base_url','chat_base_url_override','chat_api_key','search_rerank_base_url'})}
    mapping = client.indices.get_mapping(index=source)[source]['mappings']
    original_settings = client.indices.get_settings(index=source)[source]['settings']['index']
    index_settings = {key: original_settings[key] for key in ('analysis', 'number_of_shards', 'number_of_replicas', 'knn')}
    created = []
    results = []
    try:
        for arm, rows in arms.items():
            target = f'pdf-chunk-ab-{uuid4().hex[:12]}-{arm}'
            client.indices.create(index=target, body={'settings': index_settings, 'mappings': mapping})
            created.append(target)
            actions = [{'_op_type': 'index', '_index': target, '_id': h['_id'], '_source': h['_source']} for h in background]
            actions += [{'_op_type': 'index', '_index': target, '_id': r['id'], '_source': r} for r in rows]
            for ok, item in streaming_bulk(client, actions, chunk_size=200, raise_on_error=True):
                if not ok:
                    raise RuntimeError('Bulk failed')
            client.indices.refresh(index=target)
            assert client.count(index=target)['count'] == len(actions)
            print(f'{arm} indexed {len(actions)} chunks', flush=True)
            parent = old_parent if arm == 'previous' else new_parent
            for mode in ('bm25','vector','hybrid'):
                for case in cases:
                    with patch('search_engine.search.query.get_settings', return_value=settings):
                        hits = retrieve(client, target, case['query'], date.today(), 5,
                                        embedder=FixedQueryEmbedder(vectors[case['qid']]),
                                        mode=mode, strict=True, query_rewrite=False,
                                        answerability=False, rerank_chunks=False)
                    passages = [(h.parent_id, h.id, h.body) for h in hits]
                    passages += [(h.parent_id,p.id,p.body) for h in hits for p in h.passages]
                    # Deduplicate by chunk ID. Only target-document matches count as evidence.
                    passages = list({chunk_id: (pid,chunk_id,body) for pid,chunk_id,body in passages}.values())
                    anchors = [norm(a) for a in case['required_evidence']]
                    found = [any(pid == parent and a in norm(body) for pid,_,body in passages) for a in anchors]
                    relevant = sum(pid == parent and any(a in norm(body) for a in anchors) for pid,_,body in passages)
                    rank = next((i+1 for i,h in enumerate(hits) if h.parent_id == parent),None)
                    results.append({'arm':arm, 'mode':mode, 'qid':case['qid'], 'query':case['query'],
                                    'document_rank':rank, 'document_hit_at_5':rank is not None,
                                    'mrr_at_5':1/rank if rank else 0,
                                    'evidence_recall':sum(found)/len(found), 'all_evidence':all(found),
                                    'evidence_precision':relevant/len(passages) if passages else 0,
                                    'returned_chunks':len(passages),
                                    'normalized_chars':sum(len(norm(body)) for _,_,body in passages),
                                    'found':found, 'required_evidence':case['required_evidence'],
                                    'hits':[h.model_dump() for h in hits]})
                print(f'{arm} {mode}: {len(cases)} queries done', flush=True)
        (OUT / 'results.json').write_text(json.dumps({'metadata':metadata,'queries':results},ensure_ascii=False,indent=2))
        lines = ['# PDF 청킹 검색 A/B', '',
                 '실제 이전 색인의 배경 문서는 고정하고, 대상 PDF만 이전/현재 청크로 바꾼 격리 색인 비교다.',
                 '양쪽 대상 PDF를 동일 모델로 재임베딩하고, 각 질문 벡터를 공유했다. 서비스 alias는 변경하지 않았다.',
                 'LLM 필터·답변 가능성 판정·재작성·재랭커는 꺼서 검색기 자체를 측정했다.',
                 '상위 문서 5개와 문서당 최대 6개 청크 기준. 7개 기존 질문과 2개 일정표 추출 질문을 별도로 보고한다.', '',
                 '| 질문셋 | 검색 | 버전 | 문서 Hit@5 | MRR@5 | 필수 구절 Recall | 근거 완비율 | 구절 포함 청크 Precision | 평균 반환 청크 |',
                 '|---|---|---|---:|---:|---:|---:|---:|---:|']
        summaries = []
        for group in ('existing7','schedule2'):
            for mode in ('bm25','vector','hybrid'):
                for arm in arms:
                    rows = [r for r in results if r['arm']==arm and r['mode']==mode and
                            (r['qid'].startswith('docs-v2-') if group=='existing7' else r['qid'].startswith('schedule-'))]
                    values = {key:sum(r[key] for r in rows)/len(rows) for key in
                              ('document_hit_at_5','mrr_at_5','evidence_recall','all_evidence','evidence_precision','returned_chunks')}
                    summaries.append({'group':group,'mode':mode,'arm':arm,**values})
                    lines.append(f"| {group} | {mode} | {arm} | {values['document_hit_at_5']:.3f} | {values['mrr_at_5']:.3f} | {values['evidence_recall']:.3f} | {values['all_evidence']:.3f} | {values['evidence_precision']:.3f} | {values['returned_chunks']:.2f} |")
        lines += ['', '필수 구절의 포함 여부는 청크 ID와 독립적으로 평가했다. Precision은 구절 하나 이상을 포함한 청크 비율이라는 대리지표이며 의미적 관련성 전체를 측정하지 않는다.',
                  '최소근거 청크를 선택하는 이론적 검사와 달리, 이 보고서는 실제 retrieve가 반환한 본문만 채점한다.',
                  '표본 9개·PDF 한 건이므로 전체 코퍼스 개선으로 일반화하지 않는다. background 임베딩은 이전 색인의 벡터를 유지했다.',
                  '동일 문자 예산 평가 및 답변 정확성 평가는 포함하지 않았다. 모든 검색 본문·근거별 결과·설정은 results.json에 보존했다.',
                  '일정 질문 2개는 변경 내용을 확인한 뒤 추가한 진단 질문이며 독립 홀드아웃 평가가 아니다.', '',
                  '## 하이브리드 반환 본문 길이', '']
        for arm in arms:
            group = [r for r in results if r['arm']==arm and r['mode']=='hybrid' and r['qid'].startswith('docs-v2-')]
            mean_chars = sum(r['normalized_chars'] for r in group) / len(group)
            lines.append(f'- {arm}: 기존 7개 질문의 평균 정규화 본문 {mean_chars:.1f}자.')
        (OUT / 'summary.json').write_text(json.dumps(summaries,indent=2))
        (OUT / 'report.md').write_text('\n'.join(lines)+'\n')
        print('\n'.join(lines),flush=True)
    finally:
        for index in created:
            client.indices.delete(index=index)
        assert list(client.indices.get_alias(name=settings.search_docs_alias)) == source_indexes
        print('Temporary indexes removed; original alias unchanged',flush=True)


if __name__ == '__main__':
    main()
