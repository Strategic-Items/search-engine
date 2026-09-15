# 이전 실습 코퍼스 초기 적재 — 2026-09-15

원본: `/Users/jeongbin/git/search-engine/data/corpus_project_v1.jsonl` 및 같은 이름의
manifest. 원본 SHA-256은 `a1ba213c2da5508705a3d4974dc34f70b9e83bead2448bbfbf75700bb4e6e8e2`이다.
`search-prepare`는 이 해시를 원본 manifest와 대조한 뒤 로컬 `data/generated/`에
출력·체크섬 manifest를 만든다. 출력 JSONL은 Git에 넣지 않는다.

| 색인 별칭 | 범위 | 검색 단위 | 부모 문서/행 |
|---|---|---:|---:|
| `search-documents` | FAQ 206, 공지 2,663청크, 서식 623청크, 안내 7청크 | 3,499 | 278 |
| `search-hsk` | HSK 연계표 | 18,673 | 18,673 |

원본 FAQ 207건 중 `faq-042`는 현행 [온라인 자가판정 안내](https://www.yestrade.go.kr/judgements/self/guide)와
로그인 안내가 충돌한다는 실습 저장소의 공동 정답 검토에 따라 이 초기 색인에서 제외했다.
서식 623청크는 출처의 `form-게시물ID`를 사용해 게시판 목록 URL을 개별 상세 URL로
바꿨다. 대표 항목 `form-23311`의 상세 URL 응답을 확인했다. FAQ 206건은 원본에
서비스 URL이 없어 검색 결과의 출처 URL도 비어 있다.

`effective_from`이 없는 검색 단위는 1,595건이다. 서식의 게시일을 시행일로
간주하지 않고 `date_basis=publication_only`로 표시했다. 원본에는 `effective_to`가
채워진 행이 없어 오래된 서식의 폐지 여부는 자동으로 걸러지지 않는다. 서식은
2018-04-16부터 2026-09-04까지 혼재한다. 질문에 명시된 `2026년 9월`처럼 연·월이
있으면 해당 게시일 또는 시행일의 문서에 가점을 주지만, 이것이 현행성 검증을
대신하지는 않는다.

자료 갱신도 필요하다. 실습 자료 수집 시각은 2026-09-07이며 색인된 공지의
가장 늦은 게시일은 2026-09-01이다. [yesTrade 공식 홈](https://www.yestrade.go.kr/)에는
2026-09-14 공지가 이미 표시된다. 반면 [민원서식 게시판](https://www.yestrade.go.kr/user/boards/70/posts)의
최신 게시일은 2026-09-04로 이번 스냅샷과 일치한다. 따라서 이 색인은 이전 프로젝트의
**검증용 스냅샷**이며, 공지·서식 수집을 갱신하기 전에는 최신 운영 자료로 간주하지 않는다.

HSK는 10자리 문자열 `hsk_code`와 정규화한 `control_no_norm`을 별도 keyword 필드로
저장한다. 숫자 앞의 0을 보존하며 HSK 또는 통제번호의 정확 조회만 한다. 원본 HSK
18,673행 중 9,176행에는 연계 통제번호가 비어 있다. [공식 안내](https://www.yestrade.go.kr/hsk-control-search)대로
연계표는 전략물자 해당 *가능성* 정보이므로 빈 통제번호를 비해당 판정으로 취급하지 않는다.

## 검색 확인

`data/queries_project_v1_reviewed.jsonl`의 검토 중인 정답 질의를 부모 문서 기준으로
시험했다. 아래는 독립 운영 품질 지표가 아니라 현재 색인과 검색 경로의 회귀 확인이다.

| 질문 유형 | 질의 | 기본 검색 첫 결과/상위 5건 정답 | 유형 지정 첫 결과/상위 5건 정답 |
|---|---:|---:|---:|
| FAQ | 26 | 11 / 15 | — |
| 서식 | 12 | 6 / 9 | `민원서식`: 9 / 10 |
| 안내 | 7 | 0 / 5 | 안내 3종: 7 / 7 |
| 공지 | 10 | 9 / 10 | — |
| HSK 정확번호 | 18 | 18 / 18 (`/v1/hsk/search`) | — |

안내와 서식은 자료 유형을 지정해야 순위가 안정적이다. 기본 통합검색의 안내 첫 결과가
0/7인 상태이므로 이용자용 검색 화면에서는 안내·서식 경로를 분명히 선택하거나
질의 분류를 추가해 재평가해야 한다. FAQ의 기존 정답은 코퍼스 확대 및 `faq-042`
제외에 따른 공동 정답 재판정이 남아 있다.

## 재현

```bash
.venv/bin/search-prepare /Users/jeongbin/git/search-engine/data/corpus_project_v1.jsonl \
  --out data/generated
.venv/bin/search-index data/generated/core.jsonl --manifest data/generated/manifest.json
.venv/bin/search-index data/generated/hsk.jsonl --dataset hsk \
  --manifest data/generated/manifest.json
```

`search-index`는 입력 SHA-256과 건수를 manifest와 대조하고 새 색인의 문서 수를 확인한
뒤 별칭을 전환한다. 기존 색인은 롤백용으로 보존된다.
