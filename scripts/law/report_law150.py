"""Summarize frozen retrieval traces, separately for existing and new questions."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/generated/law150-2026-10-07'
MODES = ('splade','dense','hybrid')


def rank(ids, groups):
    rs = [next((i for i,c in enumerate(ids,1) if c in g),None) for g in groups]
    return max(rs) if rs and all(r is not None for r in rs) else None


def main():
    results = json.loads((OUT/'results.json').read_text())
    records = list(results['results'].values())
    eligible = [r for r in records if r['question'].get('positive_review',{}).get('evaluation_eligible',True)]
    metrics, misses = {}, []
    for cohort in ('all','existing100','new50'):
        selected = [r for r in eligible if cohort=='all' or r['question']['cohort']==cohort]
        metrics[cohort] = {}
        for mode in MODES:
            got=rawgot=docgot=0
            mrr=precision=size=0
            for record in selected:
                q=record['question']; groups=q['evidence_groups']; gold={c for g in groups for c in g}
                window=record[mode]['window']; raw=[c for c,s in record[mode]['raw']]
                r=rank(window,groups); rr=rank(raw[:5],groups)
                got+=r is not None; rawgot+=rr is not None
                mrr+=1/r if r else 0
                precision+=sum(c in gold for c in window)/len(window) if window else 0
                size+=len(window)
                docgot+=any(c.split('#')[0] in q['gold'] for c in window)
                if cohort=='all' and r is None:
                    missing=[g for g in groups if not any(c in g for c in window)]
                    reason='후보 밖' if any(not any(c in g for c in raw) for g in missing) else '후보 존재 · 컷오프 또는 반환 한도에서 누락'
                    if q.get('additional_phrases') and any(c in groups[0] for c in window) and not any(c in groups[-1] for c in window):
                        reason='숫자 행 반환 · 단위 헤더 누락'
                    misses.append({'qid':q['qid'],'query':q['query'],'cohort':q['cohort'],'mode':mode,'reason':reason,
                                   'missing_groups':missing,'raw_rank':rank(raw,groups),'window':window})
            n=len(selected)
            metrics[cohort][mode]={'n':n,'returned_found':got,'returned_recall':got/n,'raw_top5_found':rawgot,
                                   'raw_top5_recall':rawgot/n,'returned_mrr':mrr/n,'precision_lower_bound':precision/n,
                                   'doc_hit':docgot,'mean_chunks':size/n}
    summary={'index':results['index'],'as_of':results['as_of'],'settings':results['settings'],
             'questions':len(records),'eligible':len(eligible),'excluded':[r['question']['qid'] for r in records if r not in eligible],
             'metrics':metrics,'misses':misses}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    (OUT/'misses.json').write_text(json.dumps(misses,ensure_ascii=False,indent=2))
    lines=['# 법령·고시 150문서 검색 평가 (2026-10-07)','',
           '150문서·6,288청크를 재색인하고 기존 100문항에 새 자료 기반 50문항을 더했다. 정답 근거가 불완전한 053번을 제외한 149문항을 채점했다. 새 50문항은 검색 결과를 보기 전에 작성·동결했고, 추가된 49개 파일을 모두 포함한다.','',
           f"- 색인: `{summary['index']}`",f"- 검색 기준일: {summary['as_of']}",
           '- SPLADE 80%, dense 93%, hybrid 95% 컷오프. hybrid는 각 25개 후보의 청크 RRF(k=60).',
           '- 청크 최대 10개, 문서 최대 5개, 문서당 최대 6개. LLM 필터·답변 판정·리랭커·질문 재작성 없음.',
           '- dense/SPLADE 제목 경로 추가 옵션은 모두 꺼짐. 모델·설정은 results.json에 기록했다.','',
           '## 측정 결과','']
    for cohort,label in [('all','전체 149문항'),('existing100','기존 질문 99문항'),('new50','새 질문 50문항')]:
        lines += ['### '+label,'','| 방식 | 최종 반환 근거 회수 | 원순위 상위 5 근거 회수 | 최종 반환 MRR | 청크 Precision 하한 | 문서 적중 | 평균 반환 청크 |','|---|---|---|---|---|---|---|']
        for mode,m in metrics[cohort].items():
            lines.append(f"| {mode} | {m['returned_found']}/{m['n']} ({m['returned_recall']:.3f}) | {m['raw_top5_found']}/{m['n']} ({m['raw_top5_recall']:.3f}) | {m['returned_mrr']:.3f} | {m['precision_lower_bound']:.3f} | {m['doc_hit']}/{m['n']} | {m['mean_chunks']:.2f} |")
        lines += ['']
    lines += ['## 해석과 한계','',
        '- 새 50문항 중 hybrid가 놓친 125·143번은 과태료 숫자 행은 반환했지만 금액 단위(만원)를 담은 헤더 청크가 누락된 경우다. 일부 근거 반환이며 요건 충족으로 세지 않는다.',
        '- 근거 회수는 모든 evidence_groups에서 최소 한 청크가 있는 경우만 성공이다. MRR은 모든 요건이 충족되는 마지막 첫 근거의 순위를 사용한다.',
        '- 상위 5는 컷오프 전 청크 순위이며, 최종 반환은 서비스가 돌려주는 문서별 청크 창이다. 두 지표는 서로 다르다.',
        '- Precision은 정답 라벨 청크 비율의 질문별 평균이다. 라벨 밖의 관련 청크를 인정하지 않아 하한이다.',
        '- 질문은 본문을 읽고 만든 점검용이며 실제 이용자 질문 또는 생성 답변 정확도 평가가 아니다.',
        '- 이전 101문서 코퍼스와 비교하면 공통 청크 ID 4,681개 중 본문 1,858개가 바뀌었고, 75개 ID가 없어졌다. 단순히 파일 수만 증가한 실험이 아니므로 과거 100문항 수치와 직접 비교하지 않는다.',
        '- 새 질문은 같은 법령 원본과 지정 별표에 근거 범위를 제한한다. 다른 판·다른 별표에서 일부 구절이 같다는 이유만으로 정답에 넣지 않았다.','',
        '## 재현','', '```bash', '.venv/bin/search-index --dataset law', '.venv/bin/python scripts/law/build_law150_queries.py',
        'QUERIES_FILE=data/queries_law150_v1.jsonl AS_OF=2026-10-07 RESULTS_FILE=data/generated/law150-2026-10-07/results.json .venv/bin/python scripts/law/build_explorer_law100.py',
        '.venv/bin/python scripts/law/report_law150.py', '.venv/bin/python scripts/law/attribute_dense.py', '.venv/bin/python scripts/law/attribute_explorer_gold.py','```','',
        '원본·질문 스냅샷, SHA-256, 새 질문별 본문 근거, 전체 후보와 반환 결과, 놓친 질문은 `data/generated/law150-2026-10-07/`에 보관한다. 탐색기의 법령 URL 키 `law100`은 기존 링크 호환을 위해 유지하지만 내용은 150문항이다.','',
        '## 놓친 질문','']
    for mode in MODES:
        lines += ['### '+mode,'']
        for miss in misses:
            if miss['mode']==mode:
                lines.append(f"- {miss['qid']}: {miss['query']} — {miss['reason']} (근거 요건 후보 순위: {miss['raw_rank'] or '없음'})")
        lines += ['']
    report='\n'.join(lines)
    (OUT/'report.md').write_text(report)
    (ROOT/'docs/evaluation/law150_search_2026-10-07.md').write_text(report)
    # Keep the explorer's miss explanation aligned with these saved traces.
    from attribute_dense import load_object, DETAIL
    cath, span, detail = load_object(DETAIL, 'CATH')
    if len(cath.get('law100', {})) == len(records):
        for miss in misses:
            if miss['mode'] != 'hybrid':
                continue
            d = cath['law100'].get(miss['qid'][-3:])
            if not d:
                continue
            if miss['reason'] == '숫자 행 반환 · 단위 헤더 누락':
                d['diagnosis'] = '과태료 숫자 행은 반환했지만 금액 단위(만원)가 적힌 헤더 청크가 누락됐습니다.'
            elif miss['reason'] == '후보 밖':
                d['diagnosis'] = '합산 후보에 필요한 근거 요건이 없습니다.'
            else:
                d['diagnosis'] = '근거는 합산 후보에 있지만 컷오프 또는 반환 한도 뒤 필요한 청크가 누락됐습니다.'
        DETAIL.write_text(detail[:span[0]] + json.dumps(cath, ensure_ascii=False, separators=(',', ':')) + detail[span[1]:])
    print(json.dumps(metrics,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
