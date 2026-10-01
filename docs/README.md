# 문서 색인

문서는 종류별로 나눠 둔다. 저장소 개요와 실행 방법은 최상위 [README](../README.md)에 있다.

## design/ — 설계·구현 결정

무엇을 왜 그렇게 만들었는지. 코드가 바뀌면 함께 갱신한다.

| 문서 | 내용 |
|---|---|
| [retrieval_v1](design/retrieval_v1.md) | **검색 경로 전체.** 두 검색기, 융합, 컷오프, 주제 판정 |
| [import_v1](design/import_v1.md) | 이전 실습 코퍼스 초기 적재와 체크섬 검증 경로 |
| [doc_parser_import](design/doc_parser_import.md) | `unstructured-doc-parser`와의 연동 계약 |
| [supersession](design/supersession_v1.md) | 폐지·대체 서식을 가려내는 방식 |
| [synonyms](design/synonyms_v1.md) | 동의어 사전의 출처와 운영 원칙 |
| [query_intent_boost](design/query_intent_boost.md) | 질의 문장에서 자료 유형을 읽어 가점하는 방식 |
| [rag_v1](design/rag_v1.md) | RAG 파이프라인 이식 범위와 제외 항목 |

## evaluation/ — 성능 측정

측정한 날짜·코퍼스·질의셋이 함께 적혀 있어야 한다. 수치를 인용할 때는 어느 코퍼스인지 확인한다.

| 문서 | 내용 |
|---|---|
| [performance_history](evaluation/performance_history.md) | **여기부터 본다.** 단계별 측정 이력의 색인 |
| [evaluation/stages/applied/](evaluation/stages/applied/) | **적용된 단계.** 검색 코드에 들어간 것. 기본 꺼짐인 선택 기능(5·14·18·19·31단계)도 여기에 둔다 |
| [evaluation/stages/not-applied/](evaluation/stages/not-applied/) | **적용 안 된 단계.** 기준선·측정·채택하지 않은 실험. 검색 동작을 바꾸지 않았다 |
| [measurement_conditions](evaluation/measurement_conditions.md) | 공통 측정 조건과 단계별 재현 명령 |
| [stages_1_7_overview](evaluation/stages_1_7_overview.md) | 단계 1~7을 같은 표에서 비교 |
| [evidence_chunk_metrics_v2](evaluation/evidence_chunk_metrics_v2.md) | 단계 2~7의 근거 청크 지표 |
| [current_judgment](evaluation/current_judgment.md) | 지금까지 확정된 것과 아직 재지 않은 것 |
| [next_ideas](evaluation/next_ideas.md) | 아직 시도하지 않은 개선 방법 후보(미측정 가설) |
| [cutoff_precision_sweep](evaluation/cutoff_precision_sweep.md) | 점수 컷오프 비율 스윕 (docs v2 120문항) |
| [baseline_v1](evaluation/baseline_v1.md) | 자료 유형 가점 이전의 기준선 (2026-09-15) |
| `docs_v1_summary.json`, `docs_v2_stages_summary.json` | 위 문서들이 인용하는 원자료 |

정밀도는 **반환 건수 대비 정답 비율**로 보고한다. 분모를 k로 고정한 Precision@k는
정답이 1개인 질의가 대부분이라 상한이 0.25 부근에 묶여 컷오프·랭킹 변화에 반응하지 않는다.

## datasets/ — 평가셋과 정답지

| 문서 | 내용 |
|---|---|
| [queries_docs_v2_review](datasets/queries_docs_v2_review.md) | 자연어 평가셋 v2 120문항 원문 검토본 |
| [gold_review_v1](datasets/gold_review_v1.md) | v1 정답지 재판정 내역 |

## archive/ — 결론이 뒤집힌 기록

측정 자체는 정확하지만 전제가 바뀌어 현재 결론과 다르다. 이력 확인용으로만 읽는다.

| 문서 | 왜 보관하는가 |
|---|---|
| [docs_evaluation_v1](archive/docs_evaluation_v1.md) | 임베딩이 `nomic-embed-text`(768차원)이던 시점. 벡터·하이브리드 수치 무효 |
| [docs_evaluation_v2](archive/docs_evaluation_v2.md) | 같은 이유로 벡터 약세 진단이 6단계에서 뒤집힘 |
