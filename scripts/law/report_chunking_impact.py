"""Summarize measured chunking interventions without conflating scores and recall."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
result=json.loads((ROOT/'data/generated/chunking-impact/results.json').read_text())
measures=[(key,rev,m) for key,es in result['measurements'].items() for rev,m in es.items()]

def outcome(before,after):
 if before is None:return 0 if after is None else 1
 return -1 if after is None else (1 if after<before else (-1 if after>before else 0))

def rank(n):return '근거 미충족' if n is None else str(n)+'위'

def change(a,b):return rank(a)+' → '+rank(b)

lines=['# 청킹 변경의 dense·SPLADE 영향도와 근거 반환 비교','','## 측정 범위',f"{len(result['measurements'])}개 질문에 연결된 {len(measures)}건을 측정했다. 현재 모델과 배경 코퍼스를 고정하고 대상 문서의 Git 전후 청크를 교체했다. 질문 전체 비교는 해당 커밋으로 모델 입력이 달라진 현재 문서를 함께 교체했다.",'','- dense: 비교 청크의 정확한 코사인, 질문 어절 삭제 전후 영향, 수정 구간 삭제 영향.','- SPLADE: 질문·청크 희소 벡터 내적, 토큰별 기여, 수정 구간 삭제 영향.','- 후보와 반환: SPLADE/dense 각각 25개 후보의 RRF(k=60), 80%/93%/95% 컷오프, 10청크/5문서/문서당 6청크. Hybrid는 저장소의 실제 문서 묶음·사본 제외 함수로 계산했다.','- 질문 근거: 허용된 정답 문서의 필수 답 구절을 반환 청크에서 충족하는지 확인했다. 111·125·143은 단위까지 필요하다. 운영 LLM 답변 품질을 측정한 것은 아니다.','','## 점수와 순위 변화','','| 비교 항목 | 상승·개선 | 감소·악화 | 동일 |','|---|---:|---:|---:|']
for label,field,eps in [('dense 코사인','denseCosine',1e-5),('SPLADE 내적','spladeScore',1e-4)]:
 values=[m['delta'][field] for _,_,m in measures]
 lines.append(f'| {label} | {sum(v>eps for v in values)} | {sum(v<-eps for v in values)} | {sum(abs(v)<=eps for v in values)} |')
for i,label in enumerate(['SPLADE 전체 근거 반환','dense 전체 근거 반환','Hybrid 전체 근거 반환']):
 values=[outcome(m['globalBefore']['returnedRanks'][i],m['globalAfter']['returnedRanks'][i]) for _,_,m in measures]
 lines.append(f'| {label} | {values.count(1)} | {values.count(-1)} | {values.count(0)} |')
new=[(key,rev,m) for key,rev,m in measures if m['globalBefore']['returnedRanks'][2] is None and m['globalAfter']['returnedRanks'][2] is not None]
lines+=['',f'Hybrid의 질문 전체 필수 근거가 새로 반환된 비교는 {len(new)}건({len(set(key for key,_,_ in new))}개 질문)이다. 같은 질문의 여러 변경은 독립적인 비교이며 이 수치를 운영 전체 Recall 증가로 환산하지 않는다.','','## 발표 사례','','| 질문·변경 | dense 코사인 | SPLADE 점수 | 질문 전체 Hybrid 근거 |','|---|---|---|---|']
selected=[('law100-033','e1749ca'),('law100-038','9cc9c54'),('law100-082','9cc9c54'),('law100-089','9cc9c54'),('law100-111','e400e04'),('law100-125','e400e04'),('law100-130','e400e04'),('law100-143','e400e04'),('faq30-025','e400e04')]
for key,rev in selected:
 m=result['measurements'][key][rev];a,b=m['before'],m['after']
 lines.append(f"| {key} · {rev} | {a['denseCosine']:.4f} → {b['denseCosine']:.4f} | {a['spladeScore']:.4f} → {b['spladeScore']:.4f} | {change(m['globalBefore']['returnedRanks'][2],m['globalAfter']['returnedRanks'][2])} |")
lines+=['','## 모든 질문별 비교','','| 질문·변경 | dense 변화 | SPLADE 변화 | 대상 문서 Hybrid | 질문 전체 Hybrid |','|---|---:|---:|---|---|']
for key,rev,m in measures:
 lines.append(f"| {key} · {rev} | {m['delta']['denseCosine']:+.4f} | {m['delta']['spladeScore']:+.4f} | {change(m['before']['returnedRanks'][2],m['after']['returnedRanks'][2])} | {change(m['globalBefore']['returnedRanks'][2],m['globalAfter']['returnedRanks'][2])} |")
lines+=['','## 해석 범위','','점수 상승은 순위 상승의 충분조건이 아니다. 경쟁 청크와 후보 수·컷오프가 영향을 준다. 단위나 예외를 추가하면 dense 점수가 내려가도 답변 근거는 완전해질 수 있다. 제목 경로를 모델 입력에 넣지 않는 설정에서는 경로만 바뀌어도 모델 점수는 바뀌지 않는다.','','코사인·희소 내적으로 오프라인에서 정확히 다시 정렬한 실험이다. 실험마다 수정 전후 문서 구성과 모델 입력 외 배경은 고정했다. 운영 ANN 색인 재생성·날짜/번호 필터·판본 가중치·LLM 답변 평가를 포함하지 않았다. 필수 구절 판정은 현재 ID 기반 라벨을 과거 청크 번호에 옮기는 방식이 아니며, 복수 반환 청크에 걸친 근거도 함께 확인한다.','','## 재현','','```sh','python3 scripts/law/audit_chunking_history.py','python3 scripts/law/build_explorer_chunking_history.py','PYTHONPATH=. .venv/bin/python scripts/law/measure_chunking_impact.py','python3 scripts/law/report_chunking_impact.py','```','','원본 결과·벡터 캐시는 `data/generated/chunking-impact/`, 화면 데이터는 `docs/presentation/question_explorer/data/category-chunking-impact.js`에 있다.','','모델·배경 식별 정보:','','```json',json.dumps(result['metadata'],ensure_ascii=False,indent=2),'```']
(ROOT/'docs/evaluation/chunking_impact_2026-10-07.md').write_text('\n'.join(lines)+'\n')
print('written report',len(measures),'comparisons')
