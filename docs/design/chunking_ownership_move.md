# 청킹을 검색엔진으로 옮긴다 — 2026-10-08

지금 청킹은 `unstructured-doc-parser_ver2`가 한다(`chunking/chunker.py`, `chunking/structured.py`,
`chunking/table_rows.py`). 파서는 요소 목록(`elements`)과 표 자료(`tables`)를 받아 `chunk_elements()`로
청크를 만들고, `export/search_jsonl.py`가 그 청크를 `docs.jsonl`로 직렬화해 넘긴다. 연결 지점은
[문서 파서 연동](doc_parser_import.md)이 정한 대로 파일 하나다.

**이 문서가 정하는 것**: 청킹을 검색엔진으로 옮긴다. 파서는 더 이상 `docs.jsonl`(청크)을 만들지 않고,
문서 하나당 [TextBundle](https://textbundle.org/spec/) 하나(`text.markdown` + `info.json` + `assets/`)만
만든다. 검색엔진이 번들을 읽어 요소로 되돌리고, 지금 파서가 하는 것과 같은 규칙으로 청킹한다.

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

1. 지금의 `docs.jsonl`과 그 번들로 새 청커를 읽기 전용으로 돌려 비교한다. **docs 코퍼스는 고정이므로
   재생성하지 않는다** — 비교는 메모리/임시 파일에서만 하고 커밋하지 않는다.
2. 비교 항목: 문서별 청크 수, 본문 글자 단위 일치율, `heading_path`, 표 청크의 `row_index`/`values`.
   차이 나는 문서는 포맷(HWP/HWPX/PDF)과 구조(표 유무, 대비표, FAQ)별로 원인을 분류한다.
3. 성능은 서비스와 같은 청크 컷오프 0.95를 건 상태로만 재서, 지금 파서 청킹과 같은 수준인지 확인한다.
   컷오프 없는 Precision은 보고하지 않는다.

## 단계

1. `bundle.py` + `elements.py`(제목·문단·쪽 경계만, 표는 평문으로 통과) + `splitter.py`로 표 없는
   문서부터 일치율을 확인한다.
2. `tables.py`(격자 복원 + `logical_tables`)와 `structured.py`의 표 행 분할·대비표·서식 줄·목록형 표를
   이식한다. 가장 큰 단계다.
3. `_attach_footnotes`/`_drop_repeated_headers` 같은 후처리와 색인 연결(`SearchDocument` 생성)을 잇고
   전체 비교를 돌린다.
4. 일치가 확인되면 파서의 `docparser/chunking/`과 `export/search_jsonl.py`의 청킹 경로를 걷어내고,
   파서는 TextBundle만 내보내게 `pipeline.py`를 정리한다.

## 정해야 할 것

1. **파서가 표 머리글 행을 표시해 내보낼까?** HTML에 `<th>`나 속성 하나만 추가해도 배경색 감지 정보가
   보존되고, 번들 경로의 머리글 판정이 지금 파서 수준으로 돌아간다. 요청하는 쪽을 추천한다 — 번들
   계약에 필드 하나를 더하는 수준이라 "번들은 구조 그대로, 인덱스는 중복"이라는 기존 원칙과도 맞는다.
2. **`info.json`을 검색엔진이 직접 읽는 것으로 번들 합의를 바꾼다.** `textbundle.py`와 이 문서를 같이
   고친다.
3. **중간 산출물(`docs.jsonl` 동등물)을 디스크에 남길지.** 디버깅과 `search-index` CLI의 기존 사용
   패턴(파일 경로를 인자로 받음)을 생각하면 남기는 쪽이 운영 전환 비용이 작다. 다만 "`docs.jsonl`은
   파서 산출물"이라는 지금 문서 구조는 "검색엔진이 생성한 캐시"로 성격이 바뀐다.

## 진행 상황 (2026-10-08)

- **1단계 완료**: `params.py`, `splitter.py`(파서 `chunker.py` 이식, 파서의 `test_chunker.py`를 그대로 옮긴 테스트 통과).
- **`bundle.py`, `elements.py` 완료**: 파서 저장소의 번들 189개(`data/category_chunks`)를 전부 읽어, 제목·문단·표 본문
  글자가 원문과 줄 단위로 어긋나는 문서가 0건임을 확인했다(원소 3만여 개: 문단 12,956, 제목 2,870, 표 394, 그림 79).
  쪽 표지가 없는 번들(HWP 계열)이 115개라 `has_pages=False` 경로가 흔하다 -- 청크에 쪽을 싣지 않는 처리가 필요하다.
- **표 원소의 한계**: 여러 쪽에 걸친 표는 "서로 다른 쪽의 연속된 표 블록"을 한 원소로 합치고, 같은 쪽의 인접한 두 표는
  별개로 둔다. 같은 쪽에 놓인 한 표의 두 부분은 구분할 수 없다(`elements.py` docstring).
## 동작 일치 비교 (2026-10-08)

`scripts/compare_bundle_chunking.py`가 번들 189개(`data/category_chunks`)를 새 청커로 청킹해 파서의 `docs.jsonl` 본문과 글자 단위로
대조한다(읽기 전용). 테스트: `tests/chunking/test_parser_parity.py`.

| 포맷 | 문서 | 청크 전부 일치 |
|---|---:|---:|
| hwp5 | 110 | 110 |
| hwpx | 46 | 46 |
| hwpml | 5 | 5 |
| pdf | 28 | 15 |

- **이식한 청커 자체는 정확하다.** PDF 어긋난 13건을 파서로 다시 파싱해 *원래 원소와 원래 표 자료*를 이식한 `chunk_elements`에 넣으면
  13건 모두 `docs.jsonl`과 같다. 어긋남은 전부 번들에서 원소·표를 되살릴 때 잃는 정보에서 온다.
- **HWP 계열은 손실이 없다**(칸 안 줄바꿈이 `<br>`로 남고 배경색 머리글 감지를 쓰지 않는다).
- **PDF에서 번들에 안 남는 것**(13건에서 확인한 원인):
  1. 표 칸 안 줄바꿈 — 병합 칸이 없는 PDF 표는 파이프 표로 나가는데 칸 줄바꿈을 공백으로 잇는다(`table_markdown`, `hard_breaks=False`).
     그러나 청커가 받는 표 자료는 줄바꿈을 `clean_cell`로 정리한 것이라 목록 줄(`1.`/`가.`)이 줄바꿈으로 남고 한 글자 줄 연속
     (`현`/`행`)이 붙는다. 표 어긋남 77건 중 73건이 이것이다. 공백으로 이은 글에서 줄바꿈 위치를 되짚는 것은 불가능하다
     (`할 수`처럼 정상 문장도 한 글자 낱말이 이어진다).
  2. 내보내지 않은 그림 — 장식·조각 그림은 번들에 줄을 쓰지 않는다(`textbundle.py`). 청커는 그림 원소를 보고 질문 줄 연속 판정(`_faq_questions`)
     과 청크 경계를 정하므로 FAQ·신구대비표 4건이 갈린다.
  3. 목록 항목과 문단의 구분 — 둘 다 평문이라 1건이 갈린다(`_part_boundary`가 종류를 본다).
  4. 표 머리글 행(배경색 감지)과 쪽마다 되풀이되는 머리글 제거 — 표 4개, 여러 쪽 표 2건.
- 맞추려면 파서가 번들에 이 네 가지를 더 실어야 한다. 가장 작은 형태는 PDF 표 칸을 `clean_cell` 결과로 쓰고 줄바꿈을 `<br>`로 남기기,
  내보내지 않은 그림 자리에 `<!-- image: omitted -->`, 목록 항목 표지, 표 머리글 행 표시다. 번들(= docs 코퍼스)을 다시 만들어야 하므로
  docs 코퍼스 고정 원칙과 부딪친다 — 사용자 결정이 필요하다.

- **남은 것**: 색인 연결(`SearchDocument` 생성, 제목 60자 정리, `chunk_index` 번호), `Settings`로 파라미터 이동, core 통합, 파서 쪽 청킹 제거.
