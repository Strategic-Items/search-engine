# 파서 문서 검색 성능 이력

단계별 측정 기록의 색인이다. 각 단계는 자체 문서를 갖고, 이 파일은 링크만 남긴다.
숫자가 내려간 이유가 검색 시스템의 회귀인지 평가셋이 더 어려워졌기 때문인지 구분할 수
있도록, 각 문서는 그 단계의 코퍼스와 질문 세트를 함께 기록한다.

읽기 전에 [공통 측정 조건과 재현](measurement_conditions.md)을 먼저 본다. 단계마다
코퍼스·평가셋·임베딩 모델이 달라, 조건을 모르면 단계 간 수치를 잘못 비교하게 된다.

## 단계

- [1. 초기 기준선](stages/stage-01-initial-baseline.md) — v1 키워드 50문항, 어휘 검색에 유리한 조건에서 출발한다
- [2. 자연어 기준선](stages/stage-02-natural-language-baseline.md) — v2 자연어 40문항으로 바꾸자 벡터·하이브리드의 약점이 드러난다
- [3. 최신 파서 재추출·재색인](stages/stage-03-parser-reextraction.md) — 파서만 새로 돌려도 검색 성능은 거의 그대로다
- [4. 문서당 청크 여러 개 반환](stages/stage-04-chunks-per-document.md) — 순위 단위는 두고 반환 단위만 분리해 근거 Recall을 올린다
- [5. 질의 재작성 융합](stages/stage-05-query-rewrite.md) — 품질은 오르지만 검색이 0.6초가 되어 기본값은 꺼짐이다
- [6. 임베딩 모델 교체](stages/stage-06-embedding-model.md) — `bge-m3`로 바꾸자 순위가 뒤집힌다. 벡터의 약세는 모델 선택의 결과였다
- [7. 모델 교체 후 질의 재작성은 남는가](stages/stage-07-rewrite-after-model.md) — 재작성이 고치던 문제를 임베딩 모델이 이미 고쳤다
- [8. 120문항 평가셋과 문서당 청크 6개](stages/stage-08-120q-chunks6.md) — 평가셋을 키우고 문서당 청크를 6으로 올린다
- [9. 식별자 질의 15문항 추가](stages/stage-09-identifier-queries.md) — 식별자 구간에서 하이브리드가 무너지고, 컷오프가 정답을 잘라낸다
- [10. 학습형 sparse(bge-m3)를 어휘 경로로](stages/stage-10-learned-sparse.md) — 정밀도를 맞추면 벡터와 동률이다. 같은 비율로 모드를 비교하면 안 된다
- [11. Qwen3-Embedding-0.6B는 bge-m3를 넘는가](stages/stage-11-qwen3-embedding.md) — 넘지 못한다. 남은 구멍은 임베딩 모델의 문제가 아니다
- [12. 구어체 어미가 검색을 망가뜨린다](stages/stage-12-auxiliary-verb-stoptags.md) — 보조용언이 검색 토큰으로 남아 엉뚱한 1위를 만들고, 컷오프가 정답을 잘라낸다
- [13. dragonkue/BGE-m3-ko는 bge-m3를 넘는가](stages/stage-13-bge-m3-ko.md) — 넘는다. 포화라고 봤던 구간이 실은 다국어 모델의 천장이었다

## 단계에 걸친 문서

- [공통 측정 조건과 재현](measurement_conditions.md) — 측정 조건과 각 단계를 다시 만드는 명령
- [단계 1~7 한눈에 보기](stages_1_7_overview.md) — 일곱 단계를 같은 표에서 비교한다
- [단계 2~7 근거 청크 지표](evidence_chunk_metrics_v2.md) — 문서가 아니라 답이 적힌 청크가 반환됐는지를 따로 측정한다
- [현재 판단과 다음 측정](current_judgment.md) — 지금까지 확정된 것과 아직 재지 않은 것
- [컷오프 비율 스윕](cutoff_precision_sweep.md) — 비율별 반환분 정밀도 곡선
- [v1 기준선](baseline_v1.md) — v1 평가셋 자체의 기록
