# Strategic Items Search Engine

실서비스에서 사용할 OpenSearch 검색 API와 색인 작업의 출발점이다. 검색 로직 비교와
평가셋은 기존 `/Users/jeongbin/git/search-engine` 실습 저장소에 두고, 이 저장소에는
운영 요청과 색인 배포에 필요한 코드만 둔다.

## 현재 제공하는 기능

- `POST /v1/search`: 제목·본문의 한국어 형태소/BM25 검색, 통제번호 정확 매칭,
  자료 유형과 시행일 필터, 청크의 부모 문서 중복 제거. `X-API-Key` 인증 필수.
- `search-index`: JSONL 문서를 새 인덱스에 색인하고 문서 수를 확인한 뒤 읽기 별칭을
  원자적으로 전환한다. 이전 인덱스는 롤백을 위해 보존한다.
- OpenSearch 3.8.0 + `analysis-nori` 로컬 개발 컨테이너. Dockerfile로 API 배포 가능.

## 로컬 실행

Python 3.11 이상과 Docker가 필요하다. API는 로컬에서 실행하고 OpenSearch만 Compose로 띄운다.

```bash
cp .env.example .env
# .env의 SEARCH_API_KEY를 실제 개발용 비밀값으로 교체
docker compose up -d --build --wait
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/search-index examples/documents.jsonl
.venv/bin/uvicorn search_engine.api:app --host 127.0.0.1 --port 8092
```

다른 터미널에서 검색한다.

```bash
curl -sS http://127.0.0.1:8092/v1/search \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <.env에 설정한 SEARCH_API_KEY>' \
  -d '{"query":"자가판정 신청 방법","as_of":"2026-09-15","k":5}'
```

`GET /health/live`는 앱 프로세스, `GET /health/ready`는 OpenSearch 연결을 확인한다.
테스트는 `.venv/bin/pytest -q`로 실행한다.

## 색인 입력 계약

JSONL 한 줄이 하나의 검색 문서다. `id`와 `title`은 필수다. `id`는 출처의 안정적인 ID여야
하며 한 입력 파일에서 중복될 수 없다. `body`, `code`, `source_type`, `source_url`,
`parent_id`, `published_at`, `effective_from`, `effective_to`, `content_hash`를 받을 수 있다.
날짜는 `YYYY-MM-DD` 또는 `YYYYMMDD`이며 `effective_to`는 **그 날짜부터 효력이 없는**
경계다. 날짜를 모르면 `null`로 둔다. 색인 입력에 빠진 기존 문서는 재색인으로 사라지므로,
수집 실패가 있는 부분 파일은 전체 재색인에 사용하면 안 된다.

검색 요청은 `query` 또는 `code` 중 하나를 담아야 한다. `as_of` 기본값은 요청일이며,
`source_types`는 자료 유형의 정확한 값 목록이다. 응답은 검색 청크의 `id`와 부모
`parent_id`, 제목·본문·출처·시행일을 반환한다.

## 운영 연결 전 확인할 것

이 저장소는 API·색인의 기반이다. 실제 출처별 수집/변경 이벤트, 삭제 확인 절차,
접근 권한, 운영 비밀값, TLS 인증서, 백업·모니터링, 독립 평가셋의 품질 기준은
서비스 환경에 맞게 연결해야 한다. `compose.yaml`은 로컬 개발용으로 보안 플러그인을
끄고 루프백에만 포트를 연다. 운영에서는 보안이 켜진 OpenSearch 클러스터에
`OPENSEARCH_URL`(HTTPS), 사용자명·비밀번호와 인증서 검증 설정을 제공한다.

색인 재생성이 실패하면 읽기 별칭은 이전 인덱스를 계속 가리킨다. 성공 후 이전 인덱스는
자동으로 삭제하지 않는다. 롤백하거나 보존 기간이 지난 뒤 운영자가 제거한다.
