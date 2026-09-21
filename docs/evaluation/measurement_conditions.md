# 공통 측정 조건과 재현

## 공통 측정 조건

- OpenSearch 3.8.0. 임베딩 모델은 1~5단계 `nomic-embed-text`(768차원),
  6단계부터 `bge-m3`(1024차원). RRF k=60.
- 기준일 `2026-09-16`, 문서 36개, 청크 1,041개.
- 각 질문/방식 3회, 방식별 워밍업 1회, 실행 순서 회전.
- 아래 주 표는 상위 10개 부모 문서를 요청하고, 그 순위에서 @1/@5/@10을 계산한
  `search-compare` 결과다. 따라서 웹 API의 기본 반환 5개와 후보 수가 다를 수 있다.
- 시간은 단일 프로세스 검색 호출 기준이다. 벡터/하이브리드는 질의 임베딩을 포함하고,
  HTTP 왕복·LLM 답변 생성·동시 부하·QPS는 제외한다.
- v1/v2 모두 AI가 원문 근거를 검토한 개발용 평가셋이며, 독립적인 사람 검수나 운영
  승인용 평가가 아니다.

## 재현

```bash
cd /Users/jeongbin/git/searchEngine

.venv/bin/search-compare data/queries_docs_v2.jsonl \
  --corpus /Users/jeongbin/git/unstructured-doc-parser/data/chunks/docs.jsonl \
  --alias search-docs-only --repeats 3 --as-of 2026-09-16 \
  --out data/generated/docs-v2/comparison-parser-latest.json   # 3단계

.venv/bin/search-compare data/queries_docs_v2.jsonl \
  --corpus /Users/jeongbin/git/unstructured-doc-parser/data/chunks/docs.jsonl \
  --alias search-docs-only --repeats 3 --as-of 2026-09-16 \
  --out data/generated/docs-v2/comparison-chunks-per-doc-4.json   # 4단계

.venv/bin/search-compare data/queries_docs_v2.jsonl \
  --corpus /Users/jeongbin/git/unstructured-doc-parser/data/chunks/docs.jsonl \
  --alias search-docs-only --repeats 3 --as-of 2026-09-16 --rewrite \
  --out data/generated/docs-v2/comparison-query-rewrite.json   # 5단계

# 6·7단계는 bge-m3(1024차원)로 재색인한 뒤 실행한다.
.venv/bin/search-index /Users/jeongbin/git/unstructured-doc-parser/data/chunks/docs.jsonl \
  --dataset docs --manifest /Users/jeongbin/git/unstructured-doc-parser/data/chunks/manifest.json

.venv/bin/search-compare data/queries_docs_v2.jsonl \
  --corpus /Users/jeongbin/git/unstructured-doc-parser/data/chunks/docs.jsonl \
  --alias search-docs-only --repeats 3 --as-of 2026-09-16 \
  --out data/generated/docs-v2/comparison-bge-m3.json   # 6단계

.venv/bin/search-compare data/queries_docs_v2.jsonl \
  --corpus /Users/jeongbin/git/unstructured-doc-parser/data/chunks/docs.jsonl \
  --alias search-docs-only --repeats 3 --as-of 2026-09-16 --rewrite \
  --out data/generated/docs-v2/comparison-bge-m3-rewrite.json   # 7단계

SEARCH_CHUNKS_PER_DOCUMENT=6 .venv/bin/search-compare data/queries_docs_v2.jsonl \
  --corpus data/generated/docs-v2/review-corpus/docs.jsonl \
  --alias search-docs-only --repeats 3 --as-of 2026-09-17 \
  --out data/generated/docs-v2/comparison-120q-chunks6.json   # 8단계

SEARCH_CHUNKS_PER_DOCUMENT=6 .venv/bin/search-compare data/queries_docs_v2.jsonl \
  --corpus data/generated/docs-v2/review-corpus/docs.jsonl \
  --alias search-docs-only --repeats 3 --as-of 2026-09-17 --modes hybrid,vector \
  --out data/generated/docs-v2/comparison-135q-fusion-trim.json   # 21단계
```

## 판정자 측정

18·20·21단계의 무응답 포착과 거짓 거절은 `search-compare`가 아니라 별도 실행이다.
CLI가 없어 매번 스크립트를 쓴다. 질문 세트는 `data/queries_docs_v2.jsonl` 135건과
`data/queries_docs_v2_unanswerable.jsonl` 26건이고, 각 질의를 `mode="hybrid"`,
`chunks_per_document=6`, `k=5`로 검색한 뒤 `is_unanswerable`에 건다. 기록하는 것은
질의마다 `gold_retrieved`와 `judge_rejected` 둘이다.

거짓 거절은 **`gold_retrieved`가 참인 거절만** 센다. 문서를 못 가져와서 거절한 것은
판정자가 옳은 것이므로 따로 센다 — 21단계가 20단계의 4건을 다시 열게 된 것이 이
구분에서 나왔다.

**조건당 1회 실행이고, 판정자에는 실행 간 변동이 1~2건 폭으로 있다.** 같은 코드로
다시 재면 목록이 달라진다. 1~2건 차이로 조건을 가르면 안 된다.

원자료: `judge-dense-ordered-chunks.json`(20단계),
`judge-fusion-trim.json`·`judge-fusion-trim-polarity.json`·`judge-fusion-trim-judge-rules.json`(21단계).
