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
```
