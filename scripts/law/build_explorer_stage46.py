"""Publish the frozen stage-46 comparison in the question explorer; no search tuning.

Run after build_explorer_law100.py and add_explorer_doc_metrics.py.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / 'docs/presentation/question_explorer'
COMPARISON = ROOT / 'data/generated/law-reference-only-2026-10-12/service-comparison.json'


def completion_rank(ids, groups):
    positions = {cid: i for i, cid in enumerate(ids, 1)}
    ranks = [min((positions[cid] for cid in g if cid in positions), default=None) for g in groups]
    return max(ranks) if ranks and all(r is not None for r in ranks) else None


def main():
    comparison = json.loads(COMPARISON.read_text())
    questions = [json.loads(line) for line in (ROOT / 'data/queries_law150_v1.jsonl').read_text().splitlines()]
    data = {k: v for k, v in comparison.items() if k not in ('before', 'after')}
    deployment_path = ROOT / 'data/generated/server-runtime/deployment-stage46.json'
    if deployment_path.exists():
        deployment = json.loads(deployment_path.read_text())
        data['deployment'] = {key: deployment[key] for key in ('deployed_at', 'base_url', 'commit', 'health_live', 'health_ready')}
        data['deployment']['verified_questions'] = [entry['qid'] for entry in deployment['verification'] if entry.get('complete_evidence')]
    for arm in ('before', 'after'):
        data[arm] = {k: v for k, v in comparison[arm].items() if k != 'windows'}
    data['questions'] = {}
    for q in questions:
        if not q.get('positive_review', {}).get('evaluation_eligible', True):
            continue
        data['questions'][q['qid'][-3:]] = {arm: completion_rank(comparison[arm]['windows'][q['qid']], q['evidence_groups']) for arm in ('before', 'after')}
    stage = dict(k='d46', num=46, l='46단계', t='법령 명시 근거 일치 가산점', status='적용',
                 head='SPLADE 상위 25개를 고르기 전에 명시 근거 일치에 가산점을 줍니다',
                 what=['법령 SPLADE 조회에 조문·별표·별지의 제목 경로 일치 +6, 통제번호의 본문 일치 +6, 근거 범위와 대상 항목의 본문 일치 +6을 더합니다. 각 조건은 한 번만 더합니다.',
                       'BM25를 제외하고 SPLADE 25 + dense 25만 조회합니다. 추가 조문·통제번호 후보 조회는 없습니다. 가산점은 조회 순위에만 작용하며 최종 합산은 기존 RRF(k=60)입니다.'],
                 why=['037·075·076이 새로 근거 요건을 충족했고 기존 성공의 회귀는 없습니다. 첫 문서 적중은 1문항 줄었습니다.',
                      '현재 질문셋으로 선택한 규칙이라 과적합 위험이 있습니다. 추가 튜닝을 중단하고 설정을 고정했으며 새 법령·새 질문에서 검증해야 합니다.'],
                 cond='150문서·6,288청크 · 149문항(053 제외) · 기준일 2026-10-07 · 70% 컷오프 · 최대 10청크·5문서·문서당 6청크 · LLM 필터·판정·리랭커 끔',
                 hd=['조건', '근거 반환', '첫 문서 적중', 'Precision 하한', '평균 청크'],
                 rows=[['가산점 0', '144/149', '129/149', '0.2313', '7.987'], ['가산점 6', '147/149', '128/149', '0.2547', '7.738']],
                 note='043은 직접 근거가 일반 규정의 여러 판본에 밀리고, 125는 금액과 단위가 분리돼 반환 한도에서 단위가 빠집니다. 파싱·청킹·색인·라벨을 바꾸지 않은 비교이며 생성 답변 정확도를 측정한 값이 아닙니다.' +
                      (' 2026-10-12 로컬 API(8092)를 재시작해 반영했고, 실제 HTTP 요청에서 037·075·076의 모든 근거 요건 충족과 서버 상태 정상을 확인했습니다. 기존 서비스 LLM 청크 필터 설정은 유지했습니다.' if 'deployment' in data else ' 서버 배포 기록은 아직 없습니다.'))
    dump = lambda obj: json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    (EXP / 'data/law-ranking-stage46.js').write_text('/* 46단계: 고정된 법령 조회 비교. 과거 100문항과 직접 비교하지 않는다. */\nwindow.LAW_STAGE46='+dump(data)+';\nDSTG.push('+dump(stage)+');\n')
    print('stage46 questions:', len(data['questions']))


if __name__ == '__main__':
    main()
