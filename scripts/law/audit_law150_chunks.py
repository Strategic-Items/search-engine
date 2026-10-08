"""Audit the frozen law150 chunks and local HWP text for context/content loss."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/generated/law150-2026-10-07'


def main():
    chunks = [json.loads(l) for l in (OUT/'corpus.jsonl').read_text().splitlines()]
    results = json.loads((OUT/'results.json').read_text())['results']
    by_id = {c['id']:c for c in chunks}
    summary = json.loads((OUT/'summary.json').read_text())
    missed = sorted({r['qid'][-3:] for r in summary['misses']})
    findings = []
    def finding(key, severity, suffix, indices, related, description, recommendation):
        selected=[c for c in chunks if c['parent_id'].endswith(suffix) and c['chunk_index'] in indices]
        assert len(selected)==len(indices)
        findings.append({'id':key,'severity':severity,'related_questions':related,'description':description,
                         'recommendation':recommendation,'source_path':selected[0]['source_path'],
                         'chunks':[{'id':c['id'],'title':c['title'],'heading_path':c['heading_path'],'body':c['body']} for c in selected]})
    finding('unit-and-column-loss','high','fd12575a',[0,1,2,3],['125'],
            '금액 행은 반환됐지만 만원 단위는 #0000에, 1차·2차·3차 이상 위반 머리글은 #0002에 따로 있다. #0003의 숫자 이름은 열3·열4·열5다.',
            '다단 머리글을 해석하여 1차 위반 과태료(만원) 등 의미 있는 열 이름과 단위를 각 행에 전달한다.')
    finding('fine-unit-separated','high','c9907040',[0,2],['143'],
            '과태료 금액: 500만 반환되고 (단위: 만원)은 일반기준 청크에 남아 있다.',
            '표 앞 일반기준에서 단위를 추출하여 해당 표의 숫자 행에 함께 보존한다.')
    finding('dose-unit-separated','medium','479808ed',[0,1],['111'],
            '밀리시버트 단위와 선량표가 별도 청크다. dense는 필수 근거를 모두 반환하지 못했다.',
            '선량표 본문 청크에 단위를 붙인다. 표 전체를 하나로 유지하더라도 앞 단위 문맥을 함께 둔다.')
    finding('content-loss-and-polluted-caption','high','009c74ea',[0,20],['130'],
            '원본 HWP에서 추출한 CAS 55개 중 청크에는 53개만 있다. 107-44-8과 96-64-0이 빠졌다. 또 1종화학물질 및 첫 물질 설명이 22개 행 전체의 표 설명에 반복된다.',
            '실제 데이터 행을 표 제목/머리글로 소비하지 않도록 하고, 병합 셀의 부가 열 값도 보존한다. 물질 구분은 현재 구역의 헤더만 사용한다.')
    finding('merged-cell-context-loss','medium','74764c6e',[1,2],['148'],
            '필기시험 행에는 원자로조종사면허가 있으나 다음 실기시험 행에는 면허의 종류 필드가 없다. 현재 148번은 감독자 행을 찾아 성공했지만 같은 표의 다른 면허 실기 질문은 취약하다.',
            '세로 병합으로 이어진 면허명을 다음 행에도 유지한다. 빈 칸을 임의로 모두 채우지 말고 실제 병합 범위를 따른다.')
    finding('parallel-lines-flattened','medium','37e0d8f5',[0],['103'],
            '관광업소 명칭과 주소의 셀 내부 줄바꿈이 사라져 두 목록이 긴 문자열로 합쳐졌다. 한국의 집과 관광식당도 서로 다른 목록 항목인데 청크에는 연달아 붙는다.',
            '셀 내부 줄바꿈을 보존하고 원본 구조가 허용하는 경우 항목과 주소의 대응을 유지한다. 103번 문구도 원본 항목에 맞춰 별도 검토한다.')
    case_review=[]
    structural={'111','125','143'}
    weakened={'076','130'}
    for qid in missed:
        q=results[qid]['question']
        case_review.append({'qid':qid,'query':q['query'],
                            'classification':'청크 맥락 결손 동반' if qid in structural else ('청크 문맥/본문 품질 보완 가능, 미적중의 단독 원인 미확정' if qid in weakened else '정답 본문 보존; 이번 검토에서 청크 절단·내용 손실 미확인'),
                            'evidence':[{'id':c,'body':by_id[c]['body'],'heading_path':by_id[c]['heading_path']} for g in q['evidence_groups'] for c in g]})
    raw=OUT/'chunk_audit_raw'
    source_md=raw/'law-276643-b0000-00.hwp.md'
    text=source_md.read_text()
    indexed='\n'.join(c['body'] for c in chunks if c['parent_id'].endswith('009c74ea'))
    cas=lambda t:set(re.findall(r'\b\d{2,7}-\d{2}-\d\b',t))
    lost=sorted(cas(text)-cas(indexed));assert lost==['107-44-8','96-64-0']
    for qid in ['125','143']:
        d=results[qid];groups=d['question']['evidence_groups'];window=d['hybrid']['window']
        assert any(c in window for c in groups[0]) and not any(c in window for c in groups[1])
    data={'scope':{'documents':len({c['parent_id'] for c in chunks}),'chunks':len(chunks),
                   'missed_questions_reviewed':len(missed),'excluded_reviewed':['053'],
                   'note':'전체 청크 구조 스캔 + 미적중 질문 근거 검토 + 선택한 원본 HWP 5개 재추출. 전체 파일의 렌더링·내용 완전성 검증은 아니다.'},
          'structural_scan':{'short_under_80_chars':sum(len(c['body'].strip())<80 for c in chunks),'unit_marked':sum(bool(re.search(r'단위\s*[:：]',c['body'])) for c in chunks),'generic_column_labelled':sum(bool(re.fullmatch(r'(?:열\d+:\s*[^\n]+\s*)+',c['body'])) for c in chunks),'note':'구조 특성 개수이며 오류 개수가 아니다.'},
          'cas_comparison':{'raw':len(cas(text)),'indexed':len(cas(indexed)),'missing':lost},
          'findings':findings,'miss_review':case_review,
          'label_followups':{'103':'한국의 집과 관광식당은 원본의 별도 항목. 질문 문구가 평탄화된 텍스트를 따라 합쳐져 재작성 필요.','148':'질문은 원자로조종감독자지만 조종사 실기시험 #0002도 정답에 포함됨. #0000 감독자 근거도 반환되어 질문 성공은 별도로 판단하되 Precision 라벨 재검토 필요.'},
          'excluded053':'질문 2B201과 근거 1C351.a.50/51 불일치 및 신규 추가 주장 미입증. 청크 손실로 분류하지 않는다.'}
    (OUT/'chunk_audit.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    lines=['# 법령 150문서 청크 검토 (2026-10-07)','',
           '이번 평가의 6,288청크를 구조적으로 스캔하고, 세 모드 중 하나라도 최종 근거를 놓친 24문항과 제외된 053번을 검토했다. 원본 HWP 5개의 텍스트를 다시 추출해 청크와 대조했다. 모든 파일을 화면 렌더링하여 전수 검증한 결과는 아니다.','',
           '## 확인한 문제','', '| 문제 | 관련 질문 | 확인 내용 |','|---|---|---|']
    for f in findings:lines.append('| '+f['id']+' | '+', '.join(f['related_questions'])+' | '+f['description']+' |')
    lines+=['','## 원본·청크 근거','']
    for f in findings:
        lines+=['### '+f['id'],'', '- 원본: `'+f['source_path']+'`','- 조치 방향: '+f['recommendation'],'']
        for c in f['chunks']:lines+=['`'+c['id']+'`','', '```text',c['body'],'```','']
    lines+=['## 검색 실패와 구분','',
            '- hybrid 누락 12문항 모두 합산 후보에 근거가 있었다. 125·143은 단위 헤더가 분리된 청크 구조와 컷오프가 함께 작용했다.',
            '- 001·012·022·039·043·048·075·078·080 등은 답을 담은 청크가 보존돼 있다. 본문을 못 찾았다는 사실만으로 청킹 버그라고 보지 않는다.',
            '- 076은 주의사항 본문이 온전하고 별지 제4호 경로도 유지되지만, 청크 제목은 영어 Classification (Application) Form이다. 한국어 전문판정(신청)서 이름이 인접 #0012에 있어 제목 문맥 전달을 보완할 여지가 있다. 검색 실패의 단독 원인이라고 확정하지 않는다.',
            '- 130번의 타분 번호 자체는 청크에 남아 있다. 같은 원본에서 사린·소만 번호가 유실된 것은 확인했지만 이번 130번 미적중을 그 손실 탓으로 단정하지 않는다.',
            '- 053은 질문/라벨의 통제번호가 서로 다르다. 이전 답변의 근거 불완전이라는 설명보다 구체적인 원인은 이 불일치다.','',
            '## 추가 질문·라벨 확인','',
            '- 103번은 청크의 한국의 집 관광식당이라는 붙은 문자열을 질문에 사용했다. 원본 셀 안에서는 한국의 집과 관광식당이 별도 목록 항목이므로 질문 문구를 재작성해야 한다.',
            '- 148번은 조종감독자 질문인데 조종사 실기시험 #0002도 정답에 들어갔다. 감독자 근거 #0000 역시 실제 반환됐으므로 성공 여부와 별개로 청크 Precision 라벨을 재검토해야 한다.',
            '- 현재 점수는 동결된 기존 질문·라벨의 결과다. 이번 추가 검토에서는 원본 질문·라벨·색인을 바꾸지 않았고, 라벨 수정 후의 재집계는 아직 하지 않았다.','',
            '## 우선순위','',
            '1. 원문 값 보존: 55개 CAS 중 2개가 빠지는 행 소비 문제부터 막는다.',
            '2. 표의 다단 열 이름·단위를 각 행에 전달한다. 125·143은 실제 반환 창에서 결손이 드러났다.',
            '3. 실제 세로 병합 범위의 면허명 및 셀 내부 줄바꿈을 보존한다.',
            '4. 별지 이름 같은 한국어 문맥을 이어받고, 청크 변경 뒤 근거 라벨을 다시 연결해 재색인·재평가한다.','',
            '이 검토는 진단이다. 보완 후 성능이 얼마나 달라지는지는 아직 측정하지 않았다. 단순히 이웃 청크를 붙이면 규정·판본·열의 의미가 섞일 수 있으므로 원본 표의 경계를 기준으로 처리해야 한다.']
    report='\n'.join(lines)
    (OUT/'chunk_audit.md').write_text(report)
    (ROOT/'docs/evaluation/law150_chunk_audit_2026-10-07.md').write_text(report)
    print(json.dumps({'findings':len(findings),'missed_questions_reviewed':len(missed),'cas_missing':lost},ensure_ascii=False))

if __name__=='__main__':
    main()
