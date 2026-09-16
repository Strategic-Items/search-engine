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

- `POST /v1/search`: 제목·본문의 한국어 형태소/BM25 검색,
  시행일 필터, 청크의 부모 문서 중복 제거. 검색어에 10자리 HSK 코드가 있으면 HSK
  연계표도 함께 정확 조회한다.
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
`ollama pull qwen2.5:3b`(또는 `OLLAMA_CHAT_MODEL`에 지정한 모델)을 받아 둔다.

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
수집 실패가 있는 부분 파일은 전체 재색인에 사용하면 안 된다.

검색 요청은 `query`만 담아야 한다. 서버는 현재 날짜 기준으로 유효한 문서를 검색하며,
응답은 검색 청크의 `id`와 부모 `parent_id`, 제목·본문·출처·시행일을 반환한다.
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
