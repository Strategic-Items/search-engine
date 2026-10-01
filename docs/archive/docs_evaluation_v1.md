# 파서 데이터 전용 검색 평가 — 2026-09-16

> **임베딩 모델이 `nomic-embed-text`(768차원)이던 시점의 기록이다.** 색인은 그 뒤
> `bge-m3`(1024차원)로 교체했고, dense·하이브리드 수치는 더 이상 유효하지 않다.
> BM25 수치는 임베딩과 무관하므로 그대로 유효하다. 현재 결론과 단계별 이력은
> [검색 성능 이력](../evaluation/performance_history.md)에 있다.

## 결과

당시 개발 평가셋에서는 BM25가 가장 정확하고 빠르다. 기본 운영 방식은 기존과 같은
`hybrid`로 유지했다. (이 v1 키워드 세트는 아직 `bge-m3`로 다시 재지 않았다.)

| 방식 | Hit@1 | Hit@5 | Recall@5 | Recall@10 | MRR@5 | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| bm25 | 90.0% | 98.0% | 98.0% | 100.0% | 0.9267 | 16.6 | 30.4 |
| dense | 38.0% | 60.0% | 58.0% | 65.0% | 0.4667 | 52.9 | 88.8 |
| hybrid | 68.0% | 88.0% | 87.0% | 99.0% | 0.7523 | 71.3 | 133.3 |

Recall@k는 질문마다 `검색된 정답 부모 수 / 전체 정답 부모 수`를 계산한 평균(macro)이다.
Hit@k는 정답 하나라도 찾으면 성공이므로 Recall과 다르다. micro Recall도 JSON에 기록했다.
부모 문서 단위 지표이므로 반환 청크에 실제 답변 구절이 포함됐다는 보장은 아니다.
Recall의 분모는 이 평가셋에 표시한 정답이다. 모든 질문에 대해 전체 코퍼스의 관련성을
사람이 완전 판정한 것은 아니므로, 전체 관련 문서를 빠짐없이 찾는 절대 Recall로 해석하면 안 된다.

## 질문 유형별 Recall@5

| 질문 유형 | 질문 수 | BM25 Recall@5 | dense Recall@5 | 하이브리드 Recall@5 |
|---|---:|---:|---:|---:|
| content | 20 | 95.0% | 30.0% | 70.0% |
| multi_document | 4 | 100.0% | 25.0% | 87.5% |
| multi_format | 6 | 100.0% | 100.0% | 100.0% |
| title | 20 | 100.0% | 80.0% | 100.0% |

현재 dense 검색은 특히 본문 내용 질문에서 약했다. 이번 결과만으로 특정 원인을 확정하지
않았다. 모델·한국어 입력 표현·HTML/표의 임베딩 입력·청킹·RRF 후보 수를 각각 분리해
검증해야 한다. 정답에 맞춰 가중치를 조정하지 않고 이 결과를 기준선으로 남긴다.

## 기본 HTTP API 결과와 비교 조건의 차이

별도 포트 8093에서 실제 API를 실행해 50개 질문을 평가했다. 기본 상위 5건 기준
Hit@1 68.0%, Hit@5 96.0%,
Recall@5 95.0%, MRR@5 0.7760.
입력 파일에 모든 정답 부모가 있으며, HTTP 검색 결과가 파서 공고문만 포함하고
HSK 코드 질의는 연계표를 조회하지 않는 것도 확인했다.

3방식 비교는 상위 10건 요청으로 BM25 50청크 / dense 50청크 후보를 가져온 후
@1/@5/@10을 같은 순위표에서 계산한다. 기본 API는 BM25 25청크 / dense 50청크
후보로 상위 5건을 만든다. 후보를 늘리면 RRF에 들어가는 부모 집합이 바뀌므로
하이브리드 Recall@5는 비교의 87%와 기본 API의 95%로 다르다.
동일 설정 결과로 혼동하면 안 된다. `search-evaluate --k`는 API가 반환할 수 있는
상위 5건보다 큰 값을 거부한다.

## 데이터·검수 수준·측정 조건

- 최신 원본 36건 → 1,041청크, 파싱 건너뜀 없음.
- 질문 50개 / 정답 표시 66개 / 정답 부모 23개. 제목 20개, 내용 20개,
  같은 시행령의 3개 포맷 질문 6개, 복수 문서를 모두 요구하는 질문 4개.
- 검색 비교 전에 파서 본문으로 정답을 작성했고, 원본 경로·부모 ID·근거 청크 ID·
  본문 인용을 붙였다. 평가 실행 전 인용이 현재 청크에 그대로 존재하는지 검증했다.
- **AI가 원문 근거를 검토한 개발 평가셋이다. 독립된 사람의 검수나 운영 승인 평가가 아니다.**
  36개 파일 중 23개를 정답으로 지정한 소규모 세트이며, 실제 사용자·무응답 질문과
  별도 독립 평가셋으로 확대해야 일반화 성능을 판단할 수 있다.
- 같은 시행령의 HWPML/HWPX/PDF는 3개 물리 파일, 3개 정답 부모로 계산했다.
  따라서 포맷별 파일 Recall이며 중복을 묶은 고유 법령 내용 Recall과는 다르다.
- OpenSearch 3.8.0, Ollama `nomic-embed-text`,
  768차원, RRF k=60, 기준일 2026-09-16.
- 구체 인덱스 `search-docs-only-v20260916063510-8696c3`로 고정했다.
  파일/manifest 체크섬·전체 live `_source` 일치·벡터 매핑·전체 벡터 존재를 검증했다.
- 질문당 각 방식 3회, 각 방식 첫 질문 1회 워밍업 제외, 순서 순환, 방식별 150개 시간 샘플.
  반복 순위 변동은 0건이었다. p50/p95는 nearest-rank 방식이다.
- 질의 임베딩 캐시는 사용하지 않았다. 시간은 단일 프로세스 검색 호출 기준으로,
  dense/하이브리드는 Ollama 질의 임베딩을 포함한다. HTTP·LLM 생성·동시 부하·QPS는 제외.
  로컬 머신 부하와 캐시에 따라 지연시간은 달라진다.
- 샤드 실패·타임아웃·임베딩 장애 시 평가를 중단한다. BM25 폴백으로 dense 평가가
  성공한 것처럼 보고하지 않는다. 운영 hybrid의 기존 폴백은 유지했다.

## 현재 로컬 설정과 재현

로컬 `.env`에 아래 값을 적용했다(기존 비밀값 유지, Git 미포함).

```dotenv
SEARCH_DOCUMENT_DATASETS=docs
SEARCH_MODE=hybrid
SEARCH_HSK_ENABLED=false
SEARCH_DOCS_ALIAS=search-docs-only
SEARCH_DOCS_PREFIX=search-docs-only-v
```

기존 `search-docs` 707청크 및 core/HSK 인덱스는 변경하지 않았다.
최신 데이터의 `search-docs-only` 전용 인덱스는 사용할 수 있도록 유지했다.
이미 실행 중인 API는 설정을 캐시하므로 재시작해야 적용된다.
검증용 8093 API는 테스트 후 종료했다.

코퍼스 스냅샷·전체 질의별 순위/시간 JSON은 Git에 넣지 않고 로컬에 보관했다.

```bash
cd /Users/jeongbin/git/searchEngine
.venv/bin/search-compare data/queries_docs_v1.jsonl \
  --corpus data/generated/docs-v1/docs.jsonl \
  --alias search-docs-only --repeats 3 --as-of 2026-09-16 \
  --out data/generated/docs-v1/comparison.json
```

기본 API 평가는 다른 터미널에서 API를 실행한 후 아래 명령으로 재현한다.

```bash
.venv/bin/uvicorn search_engine.api:app --host 127.0.0.1 --port 8093
```

```bash
.venv/bin/search-evaluate data/queries_docs_v1.jsonl \
  --base-url http://127.0.0.1:8093 --prepared data/generated/docs-v1 \
  --k 5 --out data/generated/docs-v1/api-quality.json
```

스냅샷이 없는 환경에서는 파서 전체를 다시 실행해 `skipped`를 확인한 뒤 현재 설정으로
`search-index ... --dataset docs --manifest ...`를 실행한다. 그 산출물 경로를
`--corpus`와 `--prepared`에 전달한다. 코퍼스가 다르면 새 평가 실행으로 기록한다.

요약·코드/데이터 체크섬: [docs_v1_summary.json](../evaluation/docs_v1_summary.json).
질문 작성 범위·한계: [정답 세트 manifest](../../data/queries_docs_v1.manifest.json).
구현 검증: 검색엔진 테스트 122개 통과, CLI 설치/도움말 및 HTTP docs-only/HSK 제외 확인.

다음 단계는 원문 기준 독립 검수와 평가셋 확대다. 이후 입력 정리·모델·후보 수·RRF를
개발 세트에서 비교하고, 별도 평가셋으로 개선 효과를 확인해야 한다.
