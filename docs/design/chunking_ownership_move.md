# 청킹을 검색엔진으로 옮긴다 — 2026-10-08

지금 청킹은 `unstructured-doc-parser_ver2`가 한다(`chunking/chunker.py`, `chunking/structured.py`,
`chunking/table_rows.py`). 파서는 요소 목록(`elements`)과 표 자료(`tables`)를 받아 `chunk_elements()`로
청크를 만들고, `export/search_jsonl.py`가 그 청크를 `docs.jsonl`로 직렬화해 넘긴다. 연결 지점은
[문서 파서 연동](doc_parser_import.md)이 정한 대로 파일 하나다.

**이 문서가 정하는 것**: 청킹을 검색엔진으로 옮긴다. 파서는 더 이상 `docs.jsonl`(청크)을 만들지 않고,
문서 하나당 [TextBundle](https://textbundle.org/spec/) 하나(`text.markdown` + `info.json` + `assets/`)만
만든다. 검색엔진이 번들을 읽어 요소로 되돌리고, 파서가 하던 것과 같은 규칙(삭제 20개를 뺀 뒤의 것)으로 청킹한다. 마크다운만으로는
정보가 모자라서 입력은 번들 안 구조 파일로 간다 -- 아래 "파서 쪽 진행".

## 파서 쪽 진행 (unstructured-doc-parser_ver2 #129, `def6caf`)

이 문서를 쓴 같은 날 파서 쪽이 같은 방향의 작업을 머지했다. 이 문서의 나머지는 그 결과를 전제로 고쳤다.

- **청킹 규칙 74개를 분류했다**(`src/docparser/chunking/CHUNKING_RULES.md`): 남김 32(구조 보존), **삭제 20**(특정 문서 증상을 고치던
  규칙 -- 코드에서 걷어냄), 옮김 22(청크 경계·크기·표현 정책 -- 검색엔진 책임, 아직 파서에 있음). 청커는 652 -> 약 400줄,
  `table_rows`는 726 -> 약 530줄이 됐다. **삭제한 규칙은 검색엔진으로 가져오지 않는다.** 이식본(`structured.py`, `table_rows.py`)을
  삭제 뒤 코드로 다시 가져왔다.
- **파서 출력 계약 초안**(`docs/PARSER_OUTPUT_CONTRACT.md`): 번들에 `structure.json`(원소 목록 + 논리 표 자료)을 더하고, 코퍼스 수준
  `docs.jsonl`(청크 행)을 `documents.jsonl`(문서 행)로 바꾼다. 원소에는 `heading_path`·`part`·`boundary`·`skip`이 붙는다.
  이 문서가 앞서 짚은 "번들 마크다운에서 잃는 정보"(표 칸 줄바꿈, 내보내지 않은 그림 자리, 목록 항목 구분, 머리글 표시)는 이 계약이
  구조 파일로 해결한다 -- **청킹 입력은 `text.markdown`이 아니라 `structure.json`**이라는 것이 이 문서의 결론이 됐다.
- 계약의 "정해야 할 것" 8개는 검색 담당(이 저장소) 답을 기다린다. 아래 "정해야 할 것"에 이쪽 의견을 적었다.

따라서 마크다운에서 원소를 되살리는 경로(`elements.py`, `tables.py`)는 **구조 파일이 나오기 전까지의 임시 경로이자 비교 도구**다.
`structure.json`을 읽는 경로가 생기면 core 같은 마크다운뿐인 입력의 대체 경로로만 남긴다.

## 연결 지점이 한 단계 앞으로 옮긴다

```
지금:
  파일 → 파서: 파싱 → 정규화 원소 → chunk_elements() → docs.jsonl   (파서가 청킹)
         ──────────────────────────────── 파일(docs.jsonl) ────────────────────────────────
         검색엔진: search-index docs.jsonl --dataset docs

바뀐 뒤:
  파일 → 파서: 파싱 → 정규화 원소 → elements_to_markdown() → TextBundle  (파서는 청킹 안 함)
         ─────────────────────── 파일(bundles/*.textbundle) ───────────────────────
         검색엔진: bundle 읽기 → markdown → 원소 복원 → chunk_elements() → SearchDocument → search-index
```

파일 계약은 그대로 "파일 하나"다. 다만 그 파일이 이미 청크로 쪼개진 `docs.jsonl`이 아니라, 문서
전체가 든 TextBundle이다. 두 저장소는 여전히 서로를 import하지 않는다.

## 왜 옮기는가

- **청킹 파라미터(청크 크기, 겹침, 최소 길이)를 바꿀 때마다 파서를 다시 돌려야 했다.** 파서 실행은
  HWP/PDF 파싱을 포함해 무겁고, 검색 쪽 실험(42·43단계 등)은 파서를 건드릴 권한도 필요도 없어야 한다.
- **core 코퍼스가 이미 같은 문제를 겪고 있다.** `scripts/rechunk_core.py`가 "청커는 파서 저장소가
  소유하지만 규약을 베끼면 갈라진다"며 파서 소스를 `--parser-src`로 빌려 쓰는 우회를 썼다. 청킹을
  검색엔진이 가지면 이 우회가 없어지고 core·docs가 코드 한 벌을 공유한다([26단계](../evaluation/stages/)
  가 정한 "core와 docs는 같은 청킹 규약"이 import 없이도 지켜진다).
- **TextBundle은 이미 검색엔진에 넘어오고 있다.** `textbundle.py`가 이미 번들을 만들어 docs.jsonl과
  같이 커밋하기로 했다(#123, 2026-10-07). 번들이 원문의 정본이 되면, docs.jsonl이 그 원문을 다시
  요약한 결과라는 이중 표현을 없앨 수 있다.

## 번들에서 얼마나 되돌릴 수 있는가 (실측)

`data/category_chunks/*/bundles/*.textbundle/text.markdown`을 열어 확인했다(2026-10-08).

| 청커가 쓰는 입력 | 번들에 남아 있는가 |
|---|---|
| 제목과 수준 | 남음 — `#`~`######` |
| 쪽 경계 | 남음 — `<!-- page: N -->` 주석(`normalized_markdown.py`). HWP는 쪽 개념이 없어 주석이 아예 없을 수 있다 |
| 문단/목록 항목 텍스트 | 남음 — 목록 항목은 원래 표지(`- `, `1)`, `가.` 등)가 텍스트에 이미 접혀 들어가 있다(`list_item`은 "DocumentElement에 별도 표지 필드가 없어 표지를 텍스트에 접는다"), 그래서 렌더링에 마커를 다시 안 붙여도 글자로는 남는다 |
| 표 격자(칸 병합 포함) | 남음, 두 가지 모양으로 — 병합 칸이 있으면 `<table><tr><td rowspan colspan>...`(PDF `normalize.py:119`/`api.py:156`와 HWP가 **같은 `table_markdown()` 함수**를 쓴다), 없으면 평범한 Markdown 파이프 표(`\| ... \|`). 어느 쪽이든 칸의 행·열·병합 범위·글자를 그대로 되돌릴 수 있다 |
| 표 머리글 행(배경색 감지, `tabledata.header_rows`) | **사라짐.** 두 표현 모두 어느 행이 머리글인지 표시가 없다. `table_rows.py`도 이미 색 감지가 없을 때 생김새 휴리스틱(`_header_like`)으로 떨어지므로, 번들에서는 늘 그 휴리스틱 경로를 탄다 |
| 그림 원소 id | 상대 경로 링크로 바뀜(`assets/img-*.*`) — id 대신 경로로 추적 |
| FAQ 질문 판정(`_faq_questions`) | 남음 — 문단/목록 항목 텍스트와 물음표 여부만 본다 |
| `tabledata`의 `hard_breaks`(칸 안 줄바꿈이 문단 경계인 표, HWP) | 렌더링 시점에 이미 `<br>`로 반영돼 있어 플래그 자체는 필요 없다 — HTML을 다시 읽으면 `<br>`가 줄바꿈 경계로 보인다 |

**결론: 표 구조는 거의 손실 없이 되돌릴 수 있고, 유일하게 완전히 사라지는 정보는 표 머리글의 배경색
힌트다.** 그런데 그 힌트는 지금도 없을 때를 위한 휴리스틱이 이미 코드에 있으므로, 번들 경로에서는
그 휴리스틱만 쓰는 셈이다 — 새 실패 모드가 아니라 기존 폴백 경로가 상시화되는 것이다.

## 구성

```
search_engine/chunking/              # 새 패키지
  bundle.py       # 번들 폴더 하나 읽기: text.markdown, info.json(document 메타), assets 경로 맵
  elements.py     # markdown → 정규화 원소 목록 (normalized_markdown.elements_to_markdown의 역변환)
  tables.py       # <table> HTML / 파이프 표 → LogicalTable (table_rows.py 이식)
  structured.py   # chunk_elements 이식 — 제목 스택, 부속 경계, FAQ 질문, 표 행 분할, 대비표, 후처리
  splitter.py     # chunk_markdown 이식 — RecursiveCharacterTextSplitter + 한국어 법령 구분자
  params.py       # chunk_size=800, chunk_overlap=100, min_chunk_chars=30, CHUNKER_VERSION
```

흐름: `bundle.py`(번들 읽기) → `elements.py`(markdown→원소) → `structured.py`(원소→청크, 내부에서
`tables.py`·`splitter.py` 사용) → 기존 `convert._element_chunks`와 동등한 후처리(`index_text`,
heading 60자 자르기) → `SearchDocument` → 기존 `indexer.py`. `indexer.py`와 `SearchDocument` 계약은
바꾸지 않는다.

파서 쪽 패키지(`docparser.chunking`)는 동작 일치를 확인한 뒤(아래 "검증") 폐기한다. **이식이지
공용화가 아니다** — 소유자가 검색엔진 하나로 좁혀지므로 두 번째 패키지를 남겨 봐도 가져다 쓸 곳이 없다.

## 원칙

- **core도 같은 길을 탄다.** `rechunk_core.py`가 복원한 원문(2,400자 고정 슬라이스를 겹침 제거로 되붙인
  것)을 markdown으로 보고 같은 `structured.chunk_elements`/`splitter.chunk_markdown`에 넣는다. core는
  표나 제목 구조가 없는 평문이므로 `elements.py`의 markdown→원소 변환에서 문단 하나로만 떨어진다 — 실질
  적으로는 `splitter.chunk_markdown`만 타는 경로다. core 코퍼스는 고정이라 지금 당장 재생성하지 않고,
  코드 통합만 맞춰 둔다.
- **파라미터는 `Settings`로 옮긴다.** 파서를 다시 돌리지 않고 `chunk_size`/`chunk_overlap`을 실험할 수
  있어야 한다. 값을 바꾸면 색인 manifest에 `CHUNKER_VERSION`을 남겨, 다른 버전으로 만든 청크가 같은
  인덱스에 섞이는 것을 추적할 수 있게 한다.
- **문서 속성(`document_type`, `effective_date` 등)은 `info.json`의 `document` 객체에서 읽는다.**
  textbundle 설계 당시 "검색엔진은 info.json을 직접 쓰지 않는다"로 잠정 합의했는데(`textbundle.py`
  모듈 docstring), 이번 변경으로 그 합의를 뒤집어야 한다 — 검색엔진이 `info.json`을 직접 읽는 쪽이
  새 정본이 된다. 파서 쪽과 다시 맞춰야 할 부분이다(아래 "정해야 할 것" 1).
- **`docs.jsonl`은 더 이상 파서 산출물이 아니다.** 검색엔진이 번들에서 만들어낸 청크를 `SearchDocument`
  로 바로 색인한다. 중간 JSONL 파일을 디스크에 남길지는 디버깅 편의 문제이고 계약은 아니다.

## 검증

1. **이식이 정확한가**: 파서가 원본에서 만든 *원래 원소·표 자료*를 이식한 `chunk_elements`에 넣어 파서 자신의 청크와 글자 단위로
   대조한다(`scripts/compare_parser_chunker.py`, 읽기 전용). 삭제 20개 뒤의 파서 코드가 기준이다 -- 이전 `docs.jsonl`은 삭제된 규칙으로
   만든 것이라 기준이 못 된다(전달물은 다시 만들지 않았다).
2. **입력이 충분한가**: 같은 스크립트가 번들 마크다운에서 되살린 입력으로도 돌려 어긋난 문서를 센다. 구조 파일이 나오면 그 입력으로
   같은 비교를 한다.
3. 성능은 서비스와 같은 청크 컷오프 0.95를 건 상태로만 재서, 이전 청킹과 같은 수준인지 확인한다. 컷오프 없는 Precision은 보고하지 않는다.

## 단계

1. `splitter.py`, `bundle.py`, `elements.py` -- 완료.
2. `structured.py`, `table_rows.py`, `tables.py`, 후처리(`postprocess.py`) 이식 -- 완료(삭제 20개 뒤 코드, 위 검증 1 통과).
3. **`structure.json` 읽기**: 계약이 확정되면 원소·논리 표를 `chunk_elements`에 바로 넣는 입구를 만든다. 계약의 `tables[]`는 이미
   논리 표(`logical_tables()` 결과)라서 `chunk_elements`가 표 자료(`tabledata` 모양)뿐 아니라 논리 표도 받게 고쳐야 한다.
4. "옮김" 22개를 이쪽 정책으로 정리한다 -- 완료(아래 "옮김 22개 정책": 위치와 조절 값을 `ChunkPolicy`로 모음, 값은 그대로).
5. 색인 연결(`SearchDocument` 생성, 제목 정리, `chunk_index` 번호)과 `Settings`로 파라미터 이동, core 통합.
6. 일치와 성능이 확인되면 파서가 청킹 경로를 걷어낸다(계약의 구현 순서 6).

## 정해야 할 것 (계약 초안 8개 질문에 대한 이쪽 의견)

1. **청킹 입력** -- `structure.json`. 표·대비표를 구조로 받아야 하고, 마크다운만으로는 PDF 13/28개가 어긋난다(아래 실측).
2. **구조 파일의 위치** -- 번들 안 `structure.json`을 추천한다. 문서 하나의 원문·그림·구조가 한 폴더에 모이고, 이 저장소는 이미 번들
   폴더를 단위로 읽는다. TextBundle 규격 밖 파일이지만 규격은 추가 파일을 막지 않는다.
3. **`skip` 원소** -- 목록에 남기고 표시(초안대로). 무엇을 뺄지는 검색엔진이 정해야 실험할 수 있다.
4. **표 행의 형태** -- 지금 `logical_tables()`가 쓰는 `rows`(병합 칸 채움) + `merges`면 충분하다. 이식한 청커가 이미 그것으로 동작한다.
5. **대비표** -- 파서가 조문 쌍(`pairs`)까지 만드는 쪽이 낫다. 조문 구조 인식은 파서의 패턴 지식이고(계약 원칙 3), 쌍의 청크 표현만 이쪽이 정한다.
6. **문서 메타데이터** -- `documents.jsonl` 한 곳. 청크마다 붙이는 일은 이쪽이 한다.
7. **전환 기간** -- 이전 전달물(`docs.jsonl`)은 그대로 둔다. 새 경로의 성능을 컷오프 0.95로 재서 같음을 보인 뒤에 바꾼다.
8. **그림 설명** -- 이쪽에서 생성할 계획이 없으면 파서 출력에서 뺀다. 결정이 필요하다.

## 옮김 22개 정책

파서 규칙 목록(`CHUNKING_RULES.md`)에서 "옮김"으로 분류된 22개는 이제 이 저장소의 정책이다. 코드는 파서 것을 그대로 가져왔고, **정한 것은 소유와
위치와 조절 방법**이다. 값은 바꾸지 않았다 -- 청크 길이·경계는 검색 품질에 걸리므로 측정 없이 고치지 않는다(컷오프 0.95 기준 비교가 먼저).
숫자로 정해지는 것은 `ChunkPolicy`(`params.py`)에 모았고 기본값은 파서가 쓰던 값이다. 기본값은 `tests/chunking/test_policy.py`가 고정한다.

| 규칙 | 정책 | 위치 | 조절 값 |
|---|---|---|---|
| A1 | 크기를 넘으면 청크를 닫는다. 문단·목록 항목 경계에서만 자른다 | `structured.chunk_elements` | `chunk_size`=800 |
| A3 | 원소 하나가 크기를 넘으면 글자 수 분할기로 나눈다. 짧은 꼬리는 앞 조각에 | `structured`, `splitter` | `chunk_size`, `chunk_overlap`=100, `min_chunk_chars`=30 |
| A4 | 크기 이하 표는 표 하나 = 청크 하나, 앞 제목과 같은 청크 | `structured` 표 분기 | `chunk_size` |
| B1 | 쌓인 것이 제목뿐이면 닫지 않는다 | `structured` | (구조 규칙, 값 없음) |
| B2 | 본문이 아주 짧으면 다음 청크 앞에 붙인다 | `structured` | `min_chunk_chars` |
| B3 | 긴 문단을 나눌 때 앞의 제목은 첫 조각 앞에 | `structured` | -- |
| B4 | 글자 없는 그림·빈 표는 본문이 아니다 | `structured.has_body` | -- |
| D1 | 물음표로 끝나는 짧은 줄이 3개 이상이면 문답 문서: 질문마다 청크 | `structured._faq_questions` | `question_min`=3, `question_max_chars`=300, `question_path_chars`=80 |
| E1 | 표 크기는 HTML 태그를 뺀 글자 수로 재고, 크기를 넘고 나눌 수 있을 때만 행으로 | `structured` 표 분기 | `chunk_size` |
| E3 | 행으로 나누는 표는 앞 제목을 본문에 넣지 않고 `heading_path`로 | `structured` | -- |
| E7 | 같은 표 안의 나눌 수 없는 조각은 한 청크로 다시 합친다 | `structured` | -- |
| E10 | 대비표는 크기와 상관없이 조문 쌍 청크로 | `structured` -> `table_rows.comparison_chunks` | -- |
| E11, H1 | (파서에서 이미 삭제된 목록형 표 묶기) | -- | -- |
| G1 | 행 하나 = 청크 하나, 본문은 `열이름: 값` 줄, 첫 줄에 `표:`·`단위:` | `table_rows.row_chunks` | -- |
| G6 | 행이 크기를 넘으면 칸 단위로: 짧은 칸은 머리 줄, 중간 칸은 한 청크, 긴 칸은 글자 수 분할 | `table_rows._cell_pieces` | `row_key_max_chars`=40, `long_cell_ratio`=0.5 |
| I6 | 조문 없는 짧은 쌍은 다음 쌍 앞에 붙인다 | `table_rows.comparison_chunks` | `carry_max_chars`=40 |
| I7 | 청크 글 형식: 키 머리 줄 + `현행:` / `개정안:` + 사유 | `table_rows.comparison_chunks` | -- |
| I8 | 쌍이 크기의 1.5배를 넘으면 현행·개정안을 각각 조각으로 | `table_rows.comparison_chunks` | `pair_oversize_ratio`=1.5 |
| K4 | 청크 제목 = `문서 제목 — 절 표시` | `postprocess.chunk_title` / `section_label` | `heading_max_chars`=60 |
| L1 | 분할기 구분자 우선순위(제목 -> `제N조` -> `1.` -> `가.` -> 빈 줄 -> 줄바꿈 -> `. ` -> 공백) | `splitter._KOREAN_LEGAL_SEPARATORS` | -- |
| L2 | 짧은 조각은 다음 조각과 합친다 | `splitter._merge_tiny_pieces` | `min_chunk_chars` |

- K4는 색인 단계의 규칙이라 파서의 `chunks_to_documents`에서 가져와 `postprocess`에 두었다. 번들 189개의 청크 제목 6,612개 중 6,549개가 파서가 낸
  제목과 같고, 나머지 63개는 문서 제목에 `(산업통상자원부 공고 제…호)`가 덧붙은 것이다 -- 같은 제목의 문서를 가르는 코퍼스 수준 작업(`pipeline.disambiguate_titles`)이라
  청킹 규칙이 아니다.
- **측정 후보**(값을 바꾸려면 컷오프 0.95로 먼저 잴 것): `chunk_size`/`chunk_overlap`, `min_chunk_chars`, `long_cell_ratio`와 `pair_oversize_ratio`(표 청크 길이),
  `question_min`(문답 문서 판정). 나머지는 값이 아니라 구조 규칙이라 측정으로 정할 대상이 아니다.
- 파서 #129가 지적한 증상(서식이 행 조각으로 나뉨, 머리글 없이 끊긴 표가 `열1/열2`, 첫 행 일반기준 본문이 머리글 탐지를 막음)은 삭제된 규칙이 막던
  것이다. 이 저장소가 청킹을 가져가면 이쪽 정책으로 다룰 일이다 -- 지금은 다루지 않았다.

## 동작 일치 비교 (2026-10-08, 삭제 20개 뒤 파서 코드 기준)

`scripts/compare_parser_chunker.py`로 번들 189개(`data/category_chunks`)를 파서의 청크와 대조했다.

| 포맷 | 문서 | 원래 원소·표 자료 -> 이식 청커 | 번들 마크다운 -> 이식 청커 |
|---|---:|---:|---:|
| hwp5 | 110 | 110 | 110 |
| hwpx | 46 | 46 | 46 |
| hwpml | 5 | 5 | 5 |
| pdf | 28 | 28 | 15 |

- **이식은 정확하다**: 원래 원소·표 자료를 넣으면 189개 전부 파서의 청크와 글자까지 같다. (PUA 기호 정규화는 파서가 청크 본문에서 하던
  것인데, 계약 K2가 원소 `text`에서 하도록 옮기므로 이쪽 청커는 하지 않는다. 마크다운 입력은 이미 정규화돼 있다.)
- **HWP 계열은 마크다운만으로 충분하다**(칸 안 줄바꿈이 `<br>`로 남고 배경색 머리글 감지를 쓰지 않는다).
- **PDF 13개가 마크다운만으로는 어긋난다.** 원인은 번들 마크다운에 안 남는 정보다:
  1. 표 칸 안 줄바꿈 -- 병합 칸이 없는 PDF 표는 파이프 표로 나가며 칸 줄바꿈을 공백으로 잇는다. 청커가 받는 표 자료는 `clean_cell`로
     정리돼 목록 줄이 줄바꿈으로 남고 한 글자 줄 연속(`현`/`행`)이 붙는다. 표 어긋남의 대부분이다. 공백으로 이은 글에서 줄바꿈 위치를
     되짚는 것은 불가능하다(`할 수`처럼 정상 문장도 한 글자 낱말이 이어진다).
  2. 내보내지 않은 그림 -- 장식·조각 그림은 번들에 줄을 쓰지 않지만 청커는 그림 원소로 질문 줄 연속 판정과 청크 경계를 정한다.
  3. 목록 항목과 문단의 구분.
  4. 표 머리글 행(배경색 감지)과 쪽마다 되풀이되는 머리글 제거.
- 이 네 가지는 계약의 `structure.json`(원소 `type`/`skip`, 논리 표 `rows`/`header_detected`)이 싣는 정보와 겹친다. 그래서 번들 마크다운을
  다시 만드는 대신 구조 파일을 받는 쪽으로 간다.

## 버전 기록과 실험 방법

청킹은 계속 바꾸고 재므로 버전마다 남긴다: [chunking_versions.md](../evaluation/chunking_versions.md)(표)와 `docs/evaluation/chunking_versions/v<N>.json`(정책값,
코퍼스 통계, 검색 결과). v0은 파서의 기존 `docs.jsonl`(규칙 74개, 비교 기준), v1은 이 저장소의 이식 청커다.

- 바꾼 뒤: `params.py`의 `CHUNKER_VERSION`을 올리고 `scripts/chunking/run_version.sh <버전> "<요약>" "<무엇을 왜>"`. 번들에서 코퍼스를 만들고
  (`build_corpus_from_bundles.py`), 서비스 별칭과 따로 `exp-chk-{law,admin}-v<N>` 인덱스에 색인하고, v0 인덱스(`exp-chk-*-old`)와 같은 질문으로
  비교하고(`eval_category_chunking.py`), 기록(`record_chunking_version.py`)까지 한다.
- 평가는 서비스 검색 경로(hybrid, 청크 RRF)와 서비스 컷오프를 쓰고 0.95도 함께 낸다. 정답 청크는 청킹이 바뀌면 ID가 달라지므로 필수 구절로 인덱스마다
  다시 정한다 -- 라벨이 청크에서 사라진 질문 수를 같이 본다. 이 재정의는 공식 라벨과 완전히 같지 않다(법령 150문항 중 124문항이 같고, 나머지는 대부분
  구절 기준이 더 엄격하다). 그래서 **버전끼리 같은 규칙으로 잰 상대 비교**로만 읽는다. 라벨과 무관한 "필수 구절 반환"을 같이 낸다.

## 이 저장소에서 아직 안 한 것

`structure.json` 읽기(파서가 아직 내지 않는다), 색인 연결(`SearchDocument` 생성, `chunk_index` 번호), 파라미터의 `Settings` 이동, core 통합.
파서의 통과 판정(`category_gate.py`)이 보던 청킹 결과 검사(30자 미만·제목만 있는 청크, 1,200자 초과, `heading_path` 비율)는 이쪽에서 다시 세워야 한다.

옮긴 테스트: 파서의 청킹 테스트 6개 파일(`test_heading_chunks`, `test_table_cells`, `test_table_rows`, `test_table_feedback`, `test_chunking_structured`,
`test_amendment_notice`)을 `tests/chunking/`으로 가져왔다. 파서의 직렬화(`table_markdown`)·`legal_structure`·`docs.jsonl` 행 만들기를 검사하던 테스트는
이 저장소 소관이 아니라 뺐다.
