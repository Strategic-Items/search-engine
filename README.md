# Strategic Items Search Engine

실서비스에서 사용할 OpenSearch 검색 API와 색인 작업의 출발점이다. 검색 로직 비교
실험은 기존 `/Users/jeongbin/git/search-engine` 실습 저장소에 두고, 이 저장소에는
운영 요청과 색인 배포에 필요한 코드를 둔다.

정답 질의는 `data/queries_v1.jsonl`로 가져와 여기서 관리한다. 실습 저장소에서는
git 미추적 상태여서 수정 이력이 남지 않았기 때문이다. 출처와 원본 체크섬은
`data/queries_v1.manifest.json`에, 재판정 내역은 [gold_review_v1](docs/gold_review_v1.md)에
있다. 코퍼스 원본은 여전히 실습 저장소에 있고, `search-prepare`의 출력은
`data/generated/`에만 두며 Git에 넣지 않는다.

## 현재 제공하는 기능

- `POST /v1/search`: 제목·본문의 한국어 형태소/BM25 검색과 Ollama 임베딩 HNSW
  벡터 검색을 RRF로 결합한 하이브리드 검색,
  시행일 필터, 청크의 부모 문서 중복 제거. 결과 한 건은 문서 하나이며, 그 문서에서
  함께 검색된 다른 청크를 `passages`에 실어 보낸다. 검색어에 10자리 HSK 코드가
  있으면 HSK 연계표도 함께 정확 조회한다.
- `POST /v1/rag/stream`: 검색 근거가 있는 답변만 Ollama로 스트리밍하며, `fetch`로
  SSE 응답을 읽는다.
- `search-index`: JSONL 문서를 새 인덱스에 색인하고 문서 수를 확인한 뒤 읽기 별칭을
  원자적으로 전환한다. 이전 인덱스는 롤백을 위해 보존한다.
- `search-prepare`: 이전 실습 코퍼스에서 FAQ·안내·공지·서식과 HSK 연계표를
  별도 데이터셋으로 준비하고 원본/출력 체크섬을 기록한다.
- OpenSearch 3.8.0 + `analysis-nori` 로컬 개발 컨테이너. Dockerfile로 API 배포 가능.
- OpenSearch Dashboards 로컬 관리 화면(`http://127.0.0.1:5603`).

## 로컬 실행

Python 3.11 이상, Docker와 Ollama가 필요하다. API와 Ollama는 로컬에서 실행하고
OpenSearch와 Dashboards를 Compose로 띄운다. 먼저 `ollama serve`를 실행하고
`ollama pull qwen2.5:3b`(또는 `OLLAMA_CHAT_MODEL`에 지정한 모델)과
`ollama pull nomic-embed-text`(또는 `OLLAMA_EMBEDDING_MODEL`)를 받아 둔다. 임베딩 모델의
차원은 `SEARCH_EMBEDDING_DIMENSIONS`와 반드시 같아야 한다(기본 `nomic-embed-text`: 768).

```bash
cd /Users/jeongbin/git/searchEngine
colima start  # 이 Mac의 Docker 컨텍스트가 Colima인 경우
cp .env.example .env  # 첫 설정 때만 실행; 기존 .env의 비밀값을 덮어쓰지 않도록 주의
docker compose up -d --build --wait
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/uvicorn search_engine.api:app --host 127.0.0.1 --port 8092
```

빈 클러스터에서 예제 2건만 시험할 때는 `search-index examples/documents.jsonl`을 실행한다.
**현재 로컬 클러스터에는 이전 프로젝트 자료가 색인돼 있으므로 이 명령을 다시 실행하면
읽기 별칭이 예제 2건으로 바뀐다.**

이전 프로젝트 자료를 다시 준비·색인하려면 아래 명령을 쓴다. 준비 출력은
`data/generated/`에만 보관하고 Git에는 넣지 않는다.

```bash
.venv/bin/search-prepare /Users/jeongbin/git/search-engine/data/corpus_project_v1.jsonl \
  --out data/generated
.venv/bin/search-index data/generated/core.jsonl --manifest data/generated/manifest.json
.venv/bin/search-index data/generated/hsk.jsonl --dataset hsk \
  --manifest data/generated/manifest.json
```

원본 문서(HWP/HWPX/PDF)를 파싱해 만든 코퍼스는 별도 데이터셋 `docs`로 색인한다.
색인은 데이터셋마다 인덱스를 통째로 교체하므로, 분리해 두면 한쪽을 다시 만들어도
다른 쪽이 사라지지 않는다.

```bash
# unstructured-doc-parser 저장소에서 코퍼스를 먼저 만든다
.venv/bin/search-index ../unstructured-doc-parser/data/chunks/docs.jsonl \
  --dataset docs \
  --manifest ../unstructured-doc-parser/data/chunks/manifest.json
```

검색은 `core`와 `docs`를 함께 조회한다(`Settings.document_aliases`). 연동 계약은
[문서 파서 연동 기록](docs/doc_parser_import.md)에 있다.

### 파서 데이터만 사용하기

`.env`의 `SEARCH_DOCUMENT_DATASETS=docs`로 설정하고 API를 재시작하면 검색과 RAG가
파서 문서만 조회한다. 이 모드에서는 10자리 HSK 질의도 외부 HSK 연계표를 조회하지
않는다. `SEARCH_MODE`는 `bm25`, `vector`, `hybrid` 중 선택한다(기본 `hybrid`).
`core,docs`와 `core`도 지원하며, `SEARCH_HSK_ENABLED=false`는 모든 모드에서
HSK 조회를 끈다. 기존 인덱스를 삭제하거나 별칭을 다른 데이터셋으로 옮길 필요는 없다.

현재 로컬 `.env`는 `docs` / `hybrid` / `search-docs-only` 전용 별칭을 사용한다.
기존 `search-docs`·`search-documents`는 그대로 유지했다. 파서 산출물 갱신 후에는
현재 `.env`로 `search-index --dataset docs`를 실행하면 전용 별칭만 교체된다.

### 검색 품질 비교와 Recall

파서가 새 `data/chunks/docs.jsonl`을 만들었다면, 먼저 아래 명령으로 전용 별칭을
새 인덱스로 교체한다. 새 인덱스가 완성된 뒤 별칭을 바꾸므로, 실패하면 기존 검색
인덱스는 계속 유지된다.

```bash
cd /Users/jeongbin/git/searchEngine

.venv/bin/search-index \
  /Users/jeongbin/git/unstructured-doc-parser/data/chunks/docs.jsonl \
  --dataset docs \
  --manifest /Users/jeongbin/git/unstructured-doc-parser/data/chunks/manifest.json
```

그 다음 최신 파서 산출물로 세 검색 방식(BM25·벡터·하이브리드)을 비교한다. 이 명령은
읽기 전용이며, 라이브 색인과 JSONL의 청크 ID·본문·벡터가 모두 일치하는지도 먼저
검증한다. `--out` 파일에는 질문별 순위, Recall, 근거 청크 지표, 지연시간 원자료가 남는다.

```bash
cd /Users/jeongbin/git/searchEngine

.venv/bin/search-compare data/queries_docs_v2.jsonl \
  --corpus /Users/jeongbin/git/unstructured-doc-parser/data/chunks/docs.jsonl \
  --alias search-docs-only \
  --repeats 3 --as-of 2026-09-16 \
  --out data/generated/docs-v2/comparison-parser-latest.json
```

결과는 표준 출력과 `comparison-parser-latest.json`에서 확인한다. `--repeats 3`은
각 질문과 방식을 세 번 실행해 순위 안정성과 p50/p95 시간을 측정한다. 실행 날짜가
달라지면 `--as-of`도 해당 기준일로 바꾼다. 이 비교는 `.env`의 `SEARCH_MODE`와 관계없이
세 방식을 모두 실행하므로, 기본 모드를 바꾸기 전 판단 자료로 쓸 수 있다.

파서 전용 정답 세트는 `data/queries_docs_v1.jsonl`에 있다. 50개 질문의 정답을 원문
근거로 작성했으며 `gold`는 원본 파일의 `parent_id`다. 각 정답에는 근거 청크·본문
인용·원본 경로가 붙어 있다. **AI가 근거를 검토한 개발 평가셋이지, 사람이 독립 검수한
운영 승인 평가셋은 아니다.** 작성 범위와 한계는 같은 이름의 manifest에 기록했다.

```bash
# 세 가지 방식의 비교: 실제 색인과 파일의 일치 및 임베딩 전체 존재를 먼저 검증
.venv/bin/python -m search_engine.evaluation.compare \
  --corpus data/generated/docs-v1/docs.jsonl \
  --alias search-docs-only \
  --repeats 3 \
  --out data/generated/docs-v1/comparison.json

# 실행 중인 API의 기본 상위 5건 평가 (docs.jsonl이 있는 디렉터리를 전달)
.venv/bin/search-evaluate data/queries_docs_v1.jsonl \
  --base-url http://127.0.0.1:8092 \
  --prepared data/generated/docs-v1 \
  --k 5 --out data/generated/docs-v1/api-quality.json
```

`search-compare`도 같은 비교 명령이다(새 entry point는 `pip install -e .` 후 사용).
비교에서는 한 번 가져온 상위 10개 부모 문서로 @1/@5/@10을 계산한다. 세 방식 모두
같은 시행일·구체 인덱스·후보 깊이를 사용하며, 샤드 실패·타임아웃·임베딩 오류는
평가를 중단한다. 하이브리드 운영 검색의 임베딩 장애 시 BM25 폴백은 유지한다.

- Hit@k: 정답 문서를 하나라도 찾은 질문의 비율.
- Recall@k: 질문마다 `찾은 정답 부모 수 / 전체 정답 부모 수`를 계산한 평균(macro).
  모든 질문의 정답 수를 합산한 micro Recall도 JSON에 기록한다.
- MRR@k: 첫 정답의 순위 역수 평균. k 안에 정답이 없으면 0.
- p50/p95: 워밍업 후 단일 프로세스 검색 경로 시간. 벡터/하이브리드는 매번 Ollama
  질의 임베딩을 포함하고 HTTP·LLM 답변 생성은 제외한다. 동시 부하/QPS 측정은 아니다.

기본 API는 상위 5건이며 비교 도구는 상위 10건 요청으로 후보 수를 정하므로 두 결과가
다를 수 있다. API 평가의 `--prepared`는 입력 파일 기준 색인 범위 확인이고, 비교 도구는
실제 클러스터의 청크 ID·부모 ID·content hash·벡터 매핑까지 검증한다.

문서를 찾는 것과 답이 적힌 청크를 고르는 것은 별개다. 후자는 문서당 반환 청크 수로
조정하며, 기본값 4에서 v2 근거 Recall@5가 30.0% → 70.0%로 올랐고 문서 지표는 그대로다.
근거를 더 담을수록 RAG 프롬프트가 길어지므로 `OLLAMA_NUM_CTX`(기본 16384)를 함께 본다.
단계별 수치와 이 선택의 근거는 [검색 성능 이력](docs/performance_history.md)에 있다.

실측 결과와 재현 절차: [docs 검색 평가](docs/docs_evaluation_v1.md).
코퍼스·평가셋 변경에 따른 단계별 수치와 해석: [검색 성능 이력](docs/performance_history.md).

### 자연어 평가셋 v2 (검토 후 실험)

v1은 키워드 기준선으로 유지했다. v2는 표현 변경 12개·상황 설명 22개·복수 근거
6개의 질문과 별도 무응답 질문 8개다. 전체 질문·검토용 답안·원문 근거는
[v2 검토 문서](docs/queries_docs_v2_review.md)에서 확인한다. 사람 검수 대기 초안이다.

```bash
# 파일/정답/인용 검증만 수행; 검색이나 외부 서비스 호출 없음
.venv/bin/search-compare data/queries_docs_v2.jsonl \
  --corpus data/generated/docs-v1/docs.jsonl --validate-only

# 검토 후 비교; 기존 v1 결과를 덮어쓰지 않는다.
# 최신 파서 산출물은 바로 위의 '검색 품질 비교와 Recall' 명령을 사용한다.
.venv/bin/search-compare data/queries_docs_v2.jsonl \
  --corpus data/generated/docs-v1/docs.jsonl \
  --alias search-docs-only --repeats 3 --as-of 2026-09-16 \
  --out data/generated/docs-v2/comparison.json
```

v2에는 대체 가능한 부모 파일 `gold_groups`와 사실별 대체 근거 청크
`evidence_groups`를 추가했다. 비교 결과에 논리 문서 `group_recall_at_k`, 최종 반환
청크의 `evidence_recall_at_k` 및 모든 근거를 찾은 `evidence_all_at_k`가 함께 기록된다.
각 근거 그룹은 청크 하나라도 찾으면 충족하며, 같은 시행령의 다른 포맷은 문서
그룹 하나로 취급한다. 기존 물리 부모 Recall도 유지한다. 유형별 결과는 JSON의
`categories`에서 확인한다. 근거 지표는 생성 답변의 사실성 평가나 전체 후보 풀의
청크 Recall이 아니며, 부모마다 청크 하나를 반환하는 현재 로직의 제한도 반영한다.

`queries_docs_v2_unanswerable.jsonl`의 8개 질문은 정답이 없어 Recall 분모에 넣지
않는다. 현재 비교 도구에는 자동 무응답 판정 기능이 없으므로 별도 사람이 검토한다.

이번 초기 적재 범위와 검토 결과는 [import_v1 기록](docs/import_v1.md)에 있다.

다른 터미널에서 검색한다.

```bash
curl -sS http://127.0.0.1:8092/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"자가판정 신청 방법"}'
```

일반 검색에 10자리 HSK 코드를 넣으면 문서 결과(`hits`)와 HSK 연계표 결과(`hsk`)를
함께 반환한다. HSK 연계표는 전략물자 해당 여부의 확정 판정이 아니다.

```json
{"query":"HSK 2826902000"}
```

RAG는 검색 결과가 있을 때만 답변을 생성한다. 스트림 중 Ollama 오류는 HTTP 상태가 아니라
`event: error` 프레임으로 전달되므로 클라이언트가 이 이벤트를 실패로 처리해야 한다.

```bash
curl -N http://127.0.0.1:8092/v1/rag/stream \
  -H 'Content-Type: application/json' \
  -d '{"query":"자가판정 유효기간","session_id":"s1"}'
```

구현 결정과 제한은 [RAG v1 기록](docs/rag_v1.md)에 정리했다.

`GET /health/live`는 앱 프로세스, `GET /health/ready`는 OpenSearch 연결을 확인한다.
테스트는 `.venv/bin/pytest -q`로 실행한다.

## 웹 관리 화면

색인 후 `http://127.0.0.1:5603`에서 OpenSearch Dashboards를 연다.
`Management > Dashboards Management > Index patterns`에서 `search-documents`를
인덱스 패턴으로 만들고 시간 필터는 사용하지 않음을 선택한다. `Discover`에서
색인된 문서를 조회하거나 `Dev Tools`에서 `GET search-documents/_search`를 실행할 수 있다.
HSK 행을 보려면 `search-hsk` 인덱스 패턴을 별도로 만든다.
Dashboards는 색인·데이터를 확인하는 관리 화면이며, 서비스 이용자에게 제공할 검색 화면은
별도로 만들어야 한다.

## 코드 구조

`search_engine/` 아래는 의존 방향이 한쪽으로만 흐르는 계층이다.
`api → rag → search → client/config`, `indexing → client/config`.

```
config.py      환경변수 설정
client.py      OpenSearch 클라이언트
codes.py       통제번호·법령 참조 정규화 (색인·검색 공용)

api/           HTTP 표면 (uvicorn search_engine.api:app)
  routes.py      FastAPI 앱과 라우트
  schemas.py     요청 스키마
search/        런타임 질의 경로
  query.py       문서 질의 조립, 검색, HSK 병합(search_all)
  hsk.py         HSK 코드 추출, 연계표 조회
  results.py     검색 응답 모델
indexing/      오프라인 색인 파이프라인
  prepare.py     실습 코퍼스 → core/hsk 데이터셋 (search-prepare)
  indexer.py     색인 재생성과 읽기 별칭 전환 (search-index)
  documents.py   색인 입력 문서 모델
  mapping.py     인덱스 매핑
  synonyms.py    동의어 사전 로딩
rag/           검색 기반 답변 파이프라인
evaluation/    검색 품질 측정 (search-evaluate)
```

`search`와 `indexing`은 서로를 부르지 않는다. 각 패키지의 `__init__.py`가 공개
이름을 재수출하므로 `from search_engine.search import search_all`처럼 패키지
단위로 임포트한다.

## 색인 입력 계약

JSONL 한 줄이 하나의 검색 문서다. `id`와 `title`은 필수다. `id`는 출처의 안정적인 ID여야
하며 한 입력 파일에서 중복될 수 없다. `body`, `code`, `source_type`, `source_url`,
`parent_id`, `published_at`, `effective_from`, `effective_to`, `content_hash`를 받을 수 있다.
날짜는 `YYYY-MM-DD` 또는 `YYYYMMDD`이며 `effective_to`는 **그 날짜부터 효력이 없는**
경계다. 날짜를 모르면 `null`로 둔다. 색인 입력에 빠진 기존 문서는 재색인으로 사라지므로,
수집 실패가 있는 부분 파일은 전체 재색인에 사용하면 안 된다. 이는 `core`뿐 아니라
`docs`·`hsk`에도 똑같이 적용된다 -- 데이터셋마다 인덱스가 통째로 교체된다.

임베딩은 색인할 때 이 저장소가 직접 만든다(`core`, `docs`). 입력에 `embedding`을 담아
보낼 필요가 없고, 담아도 덮어쓴다. 대신 `search-index`를 실행하기 전에 Ollama가 떠
있고 `OLLAMA_EMBEDDING_MODEL`이 받아져 있어야 한다.

검색 요청은 `query`만 담아야 한다. 서버는 현재 날짜 기준으로 유효한 문서를 검색하며,
응답은 검색 청크의 `id`와 부모 `parent_id`, 제목·본문·출처·시행일을 반환한다.
`passages`에는 같은 문서에서 함께 검색된 다른 청크가 순위대로 담긴다
(`SEARCH_CHUNKS_PER_DOCUMENT` - 1개까지). 순위는 여전히 슬롯당 문서 하나이므로
`passages`가 다른 문서를 결과에서 밀어내지 않는다. `SEARCH_CHUNKS_PER_DOCUMENT=1`이면
`passages`는 항상 비어 있고 종전과 같은 응답이 된다.
`query`에 10자리 HSK 코드(공백·하이픈 허용)가 있으면 `hsk` 필드에 연계표 결과도
반환하고, 그 외에는 `hsk`가 `null`이다.

## 운영 연결 전 확인할 것

이 저장소는 API·색인의 기반이다. 실제 출처별 수집/변경 이벤트, 삭제 확인 절차,
접근 권한, 운영 비밀값, TLS 인증서, 백업·모니터링, 독립 평가셋의 품질 기준은
서비스 환경에 맞게 연결해야 한다. `compose.yaml`은 로컬 개발용으로 보안 플러그인을
끄고 루프백에만 포트를 연다. 운영에서는 보안이 켜진 OpenSearch 클러스터에
`OPENSEARCH_URL`(HTTPS), 사용자명·비밀번호와 인증서 검증 설정을 제공한다.
다중 노드 운영 클러스터에서는 `SEARCH_NUMBER_OF_REPLICAS`도 1 이상으로 설정한다.

색인 재생성이 실패하면 읽기 별칭은 이전 인덱스를 계속 가리킨다. 성공 후 이전 인덱스는
자동으로 삭제하지 않는다. 롤백하거나 보존 기간이 지난 뒤 운영자가 제거한다.
