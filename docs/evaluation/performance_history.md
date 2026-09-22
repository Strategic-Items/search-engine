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
- [14. 절대 바닥값으로 한 번 더 자르기](stages/stage-14-absolute-score-floor.md) — 도메인 밖은 전부 거르지만, 도메인 안의 무응답은 여전히 못 거른다
- [15. BGE-m3-ko 채택](stages/stage-15-adopt-bge-m3-ko.md) — 변환본을 검증해 Ollama로 서빙하고, 바닥값을 다시 쟀다
- [16. 어휘 바닥값을 걷고 벡터에 주제 판정을 맡긴다](stages/stage-16-vector-decides-topicality.md) — BM25 바닥값은 관련성이 아니라 질의 길이를 재고 있었다. 해제는 되돌렸고, 노이즈 게이트로만 남긴다
- [17. BM25 대신 sparse를 섞으면](stages/stage-17-sparse-instead-of-bm25.md) — 어휘 짝으로는 낫지만, 융합이 강점을 평균 내버린다
- [18. 도메인 안 무응답을 거를 수 있는가](stages/stage-18-llm-answerability-judge.md) — 리랭커는 0/8, LLM 판정은 7/8. 관련도가 아니라 사실의 유무를 물어야 한다
- [19. 문서는 맞는데 청크가 틀렸다](stages/stage-19-chunk-rerank-within-document.md) — 판정자 거짓 거절의 절반은 근거가 문서 내 7~21위로 밀려 안 보인 것이었다. 문서 내 재정렬로 14.8% → 7.4%
- [20. 진단이 맞으면 해법은 공짜였다](stages/stage-20-dense-order-inside-documents.md) — 같은 진단이 cross-encoder 대신 밀집 순서를 가리키고 있었다. 지연 0으로 근거 `@1` +23.3p
- [21. 컷오프가 융합을 투표로 바꿔 놓고 있었다](stages/stage-21-fusion-cutoff-and-judge-polarity.md) — RRF 점수에 비율 컷오프는 "두 검색기 모두에 있어야 한다"는 뜻이었다. P@1 +3.0p, Hit@5 +3.7p, 지연 0. 판정자 폴라리티 규칙 한 줄로 거짓 거절 5.9% → 3.7%
- [22. 어휘 검색이 본문 근거를 버리고 있었다](stages/stage-22-most-fields-instead-of-best-fields.md) — `best_fields`가 문서를 단일 최고 필드로만 점수 내고 있었다. `most_fields` 한 단어로 Hit@5 +1.5p, 반환분 정밀도 +4.1p, 반환 수는 감소. bm25 단독은 17단계 sparse와 동률이 된다
- [23. 채점 단위를 청크로 옮겼다](stages/stage-23-chunk-is-the-scoring-unit.md) — 검색이 아니라 재는 자를 바꿨다. 답변 모델이 받는 것은 문서가 아니라 청크이므로 근거 청크 지표가 주 지표이고 문서 지표는 진단용이다. 근거 Precision·MRR을 새로 더했다. 22단계 순위를 다시 재도 하이브리드 우위는 유지되고 더 선명해진다(문서 P@1은 벡터와 동률이지만 근거 R@5는 +5.9p)
- [24. SPLADE를 현재 검색기와 같은 135문항에 세웠다](stages/stage-24-splade-against-current-retrievers.md) — SPLADE+dense는 현재 BM25+dense보다 문서 P@1 94.8% → 97.8%, 청크 근거 Recall 91.1% → 94.1%로 오른다. 기존 판정표에 있는 청크만 비교하면 풀링 Precision 53.0% → 61.1%, 직접 답 Precision 31.4% → 38.1%다. 첫 근거 순위와 미판정 19%의 선택 편향, 온라인 비용은 남는다

## 단계에 걸친 문서

- [공통 측정 조건과 재현](measurement_conditions.md) — 측정 조건과 각 단계를 다시 만드는 명령
- [단계 1~7 한눈에 보기](stages_1_7_overview.md) — 일곱 단계를 같은 표에서 비교한다
- [단계 2~7 근거 청크 지표](evidence_chunk_metrics_v2.md) — 문서가 아니라 답이 적힌 청크가 반환됐는지를 따로 측정한다
- [현재 판단과 다음 측정](current_judgment.md) — 지금까지 확정된 것과 아직 재지 않은 것
- [판정자 프롬프트 스윕](judge_prompt_sweep.md) — 다섯 프롬프트로 거짓 거절 8→1까지 움직였지만 무응답 포착은 22/26에서 꿈쩍하지 않는다. 채택한 것은 없다
- [컷오프 비율 스윕](cutoff_precision_sweep.md) — 비율별 반환분 정밀도 곡선
- [v1 기준선](baseline_v1.md) — v1 평가셋 자체의 기록
