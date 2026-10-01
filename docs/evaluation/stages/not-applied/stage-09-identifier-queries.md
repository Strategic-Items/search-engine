# 9단계: 식별자 질의 15문항 추가 (2026-09-18)

기존 120문항에는 공고번호·조문번호·HSK 코드로 찾는 질의가 **한 건도 없었다**. 연도 숫자는
72건 있었지만 그건 문맥 속 숫자이지 정확 일치로 변별되는 토큰이 아니다. 그래서 BM25가
잘하는 종류의 질문을 평가셋이 물어본 적이 없었고, "하이브리드가 BM25보다 낫다"는 지금까지의
결론은 그 구간을 보지 않은 채 내린 것이었다.

검토 코퍼스의 실제 고시·공고 번호와 조문 번호로 15문항을 추가했다(`docs-v2-121`~`135`,
카테고리 `identifier_number` 6 / `identifier_article` 4 / `identifier_mixed` 5).
평가셋의 원래 작성 규칙은 질문에 식별자를 넣지 말라고 정하고 있으므로, 이 15문항은
manifest에 예외로 명시했다. 정답 추세를 기존 카테고리와 섞어 읽으면 안 된다.

## 순위만 본 결과 (컷오프 없음)

| 카테고리 | 질의 | bm25 MRR | dense MRR | hybrid MRR |
|---|---:|---:|---:|---:|
| identifier_number | 6 | **0.917** | 0.556 | 0.778 |
| identifier_article | 4 | **0.417** | 0.300 | 0.362 |
| identifier_mixed | 5 | **1.000** | 0.900 | 1.000 |
| paraphrase | 34 | 0.860 | **0.957** | 0.924 |
| scenario | 68 | 0.850 | **0.957** | 0.942 |

식별자 구간에서는 BM25가 세 유형 모두 1위다. dense는 `제2026-598호`와 `제2026-584호`를
임베딩 공간에서 구분하지 못해 Hit@5가 66.7%까지 떨어진다. 하이브리드는 RRF로 dense의 틀린
순위를 섞어 받으면서 BM25 단독보다 나빠진다. 지금까지 보이지 않던 하이브리드의 약점이다.

## 컷오프가 정답을 잘라낸다

운영 기본값(hybrid 0.95)을 적용하면 identifier_number의 하이브리드 Hit@5가 100% → 66.7%로
떨어진다. 순위에서 빠진 것이 아니라 **잘린 것이다.**

| 질의 | bm25 순위(최고점 대비) | hybrid 순위(최고점 대비) |
|---|---|---|
| docs-v2-121 (제2026-598호) | 1위 (1.000) | 3위 (0.632) → 0.95에 잘림 |
| docs-v2-123 (제2026-584호) | 1위 (1.000) | 3위 (0.593) → 0.95에 잘림 |

BM25는 식별자가 일치하면 1위를 최고점으로 밀어올리지만, RRF는 순위 기반이라 그 확신이
점수에 남지 않는다. 정답이 3위로 내려가고 상대 점수도 0.6 근처로 깔려서, 비율 컷오프가
정답을 잘라내는 경로가 만들어진다. 컷오프 비율을 조정해 해결할 문제가 아니라, 어휘 경로가
정확히 일치했을 때 그 신호를 융합 이후까지 살리는 문제다.

## 전체 135문항 (운영 기본 컷오프 적용)

| 방식 | Precision@1 | Hit@5 | Precision@5 (반환분) | 평균 반환 | Recall@5 | MRR@5 | p50 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| bm25 | 80.0% | 86.7% | 75.2% | 1.59 | 85.4% | 0.8265 | 19.2 |
| dense | 89.6% | 91.9% | 89.1% | 1.33 | 89.4% | 0.9074 | 107.3 |
| hybrid | 89.6% | 91.9% | 85.6% | 1.37 | 89.9% | 0.9062 | 128.0 |

이 단계부터 `search-compare`가 분모를 k로 고정한 Precision@5 대신 **반환분 기준** 정밀도와
평균 반환 건수를 함께 낸다. 컷오프가 목록을 줄이는 방식으로 작동하므로, 분모가 고정된
정의로는 컷오프의 효과가 지표에 전혀 나타나지 않았다.

기존 120문항 구간만 보면 하이브리드 Hit@5 95.0%, 신규 15문항에서는 66.7%다. 전체 수치가
내려간 것은 검색이 나빠져서가 아니라 평가셋이 지금까지 안 보던 구간을 물어보기 시작했기
때문이다. 8단계 이전 수치와 직접 비교하지 않는다.

원자료는 `data/generated/docs-v2/comparison-135q.json`, 컷오프 비율 곡선은
[컷오프 비율 스윕](../../cutoff_precision_sweep.md)에 있다.

3단계 수치를 다시 만들려면 `SEARCH_CHUNKS_PER_DOCUMENT=1`로 실행한다.

원자료는 로컬 생성 파일인 `data/generated/docs-v1/comparison.json`,
`data/generated/docs-v2/comparison.json`,
`data/generated/docs-v2/comparison-parser-latest.json`,
`data/generated/docs-v2/comparison-chunks-per-doc-4.json`,
`data/generated/docs-v2/comparison-query-rewrite.json`,
`data/generated/docs-v2/comparison-bge-m3.json`,
`data/generated/docs-v2/comparison-bge-m3-rewrite.json`,
`data/generated/docs-v2/comparison-120q.json`(8단계 n=4),
`data/generated/docs-v2/comparison-120q-chunks6.json`(8단계 n=6),
`data/generated/docs-v2/comparison-135q.json`(9단계)에 보관한다.
1~5단계 수치는 `nomic-embed-text` 색인에서 얻은 것이라, 현재 색인으로는 재현되지 않는다.
