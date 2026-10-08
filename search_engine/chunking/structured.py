# 이식 원본: unstructured-doc-parser_ver2 src/docparser/chunking/structured.py -- 동작 일치를 확인하는 동안 본문은 그대로 두고 import만 바꿨다.
"""Semantic chunking for normalized elements (ISSUE 29-33).

## 표 (2026-09-29)

표는 기본적으로 쪼개지 않는다(표 하나 = 청크 하나). 다만 `chunk_size`를 넘는 표는 통째로 두면 검색에서 특정 행을
찾기 어렵다 -- 184행짜리 품목 목록이 6천 자짜리 청크 하나가 되면 "젓가락 HS코드" 같은 질의에 그 행만 꺼낼 수 없고,
임베딩도 184개 품목의 평균이 된다. 그래서 `tables`(원소별 논리 표 자료, `normalize.element_tables`)가 주어지면 큰 표는
**행 하나 = 청크 하나**로 나눈다. 여러 페이지에 걸친 표는 `tabledata`가 이미 한 논리 표로 이어 두었으므로 행 청크들이
같은 `table_id`를 공유한다.

행 청크 본문은 `열이름: 값` 줄로 쓴다. 행 값만 두면(`| 31 | 젓가락 | Chopsticks | 441919 |`) 무엇이 품목명이고 무엇이
코드인지 BM25도 임베딩도 알 수 없다. 머리글은 `tabledata`의 배경색 감지에 더해 생김새로 보강하고(`table_rows.py`),
그래도 없으면 열 이름을 `열1`, `열2`...로 둔다. 가로 병합으로 채워진 칸은 본문에서 한 번만 쓰고, 세로 병합은 행마다 반복한다
(그래야 행 청크 하나만 봐도 어느 분류에 속하는지 안다). 값이 하나도 없는 행은 청크로 만들지 않는다(내용 없는 청크는
벡터 공간 중심 근처에 놓여 아무 질의에나 딸려 나온다, CLAUDE.md "색인 계약에서 주의할 것").

메타데이터: 표 청크(쪼갠 것·안 쪼갠 것 모두, 논리 표가 하나로 대응될 때)에 `table_id`, `columns`, `row_count`(머리글
제외 데이터 행 수)를 붙이고, 행 청크에는 `row_id`, `row_index`(0부터, 데이터 행 기준), `values`(열 순서대로의 값)를 더
붙인다. 쪽 범위는 다른 청크와 같이 `page_start`/`page_end`다.

## 제목만 남는 청크를 만들지 않는다 (2026-10-01)

제목은 그 아래 본문을 여는 표지라 본문과 같은 청크에 있어야 한다. 예전엔 제목이 나올 때마다 청크를 닫아서, 제목 바로
뒤에 하위 제목이 오는 곳(`제1장` -> `제1조`, `[별지 서식]` -> 서식 제목, `부칙` -> `제1조`)마다 제목만 든 청크가 생겼다
(코퍼스 158건에서 489개). 규칙:
- 쌓인 것이 제목뿐이면(본문 원소가 없으면) 새 제목·크기 초과에서도 닫지 않는다 -- 이어지는 제목들과 첫 본문이 한 청크가
  되고, `heading_path`는 그 시점의 가장 깊은 제목까지다. 제목 글자는 본문 앞에 그대로 남는다.
- 긴 문단을 나눌 때 앞에 쌓인 제목은 첫 조각 앞에 붙인다(따로 내보내지 않는다).
- 본문으로 치지 않는 원소: 글자 없는 그림(OCR 없음)·빈 표 -- 색인 단계(`convert.index_text`)에서 자리표시가 지워지므로
  이것만 붙은 제목도 제목만 남는다.
- 행으로 나누는 큰 표 앞의 제목은 지금처럼 본문에 넣지 않고 `heading_path`(행 청크마다)로 남긴다.
- 제목 아래 본문이 아주 짧으면(`min_chunk_chars`=30자 미만: 문서 첫머리 행사명 한 줄, 제목+괄호 부제) 따로 청크로 내보내지
  않고 다음 청크(다음 제목 또는 표) 앞에 붙인다 -- 혼자서는 검색 단위가 못 된다.

## 쪽마다 되풀이되는 같은 제목 (2026-10-01)

장 제목을 쪽마다 머리에 다시 찍는 문서(안내서·매뉴얼)는 같은 제목이 쪽마다 새 절처럼 나온다. 이미 열려 있는 제목과 수준·글자가
같고, 새 쪽의 첫 글자 원소(앞에 그림만 있음)이면 새 절이 아니라 이어지는 절로 본다 -- 청크를 끊지 않고 제목 스택도 그대로
둔다. 글자만 같다고 합치지 않는다: 쪽 중간에 다시 나오거나 다른 수준이면 새 절이다.

## 쪽마다 되풀이되는 표 머리글 (2026-10-02)

여러 쪽에 걸친 표가 쪽마다 머리글을 다시 그리면, 그 머리글이 표에 붙지 못하고 문단(`NO.`/`대상품목`/`상세사양`)으로 떨어져
머리글 글자만 든 청크가 쪽마다 생긴다. 내용이 없어 검색에서 똑같은 청크가 되풀이된다. 문단만 든 청크의 줄이 바로 앞·뒤 표
청크의 열 이름과 차례대로 같으면 뺀다. 데이터 행은 손대지 않는다 -- 표 행을 합치면 행 청크가 희석된다.

## 칸 안 조문의 표제 (2026-10-02)

신·구조문 대비표는 현행·개정안 칸 하나에 조문 수십 개가 들어 있어 칸을 조각으로 나눈다(`table_rows._cell_pieces`). 조문 중간에서
잘린 조각은 어느 조문의 호인지 알 수 없어서(`9. 해당 물품등의 최종 목적지가…`가 `제39조의3(상황허가)`의 호인지), 조각이 시작하는
자리의 편·장·절·조 표제를 그 조각의 `heading_path` 뒤에 붙인다. 같은 조문의 현행 조각과 개정안 조각이 같은 경로를 갖는다.

## 표를 행으로 나눌지는 셀 글자 양으로 (2026-10-01)

병합 칸이 있는 표는 HTML 마크업(`<td rowspan=…>`)으로 직렬화돼 글자 수가 부풀려진다. 그 길이로 "큰 표"를 판단하면 빈칸 위주
서식(신청서·동의서)이 행마다 `열1: 성 명` 같은 조각 청크로 쪼개진다. 행 분할 여부는 HTML 태그를 뺀 표 글자 수로 판단한다.
"""

from __future__ import annotations

import re

from search_engine.chunking.splitter import chunk_markdown
from search_engine.chunking import patterns
from search_engine.chunking.table_rows import (comparison_chunks, comparison_columns, form_lines, logical_tables, row_chunks,
                                           table_fields)

_PAGE_MARKER = re.compile(r"<!--\s*page:\s*(\d+)\s*-->")
_HTML_TAG = re.compile(r"<[^>]+>")
_PAGE_NUMBER_ONLY = re.compile(r"^\s*(?:[-–—]\s*\d{1,4}\s*[-–—]|\d{1,4}\s*/\s*\d{1,4}|-\s*\d{1,4}\s*/\s*\d{1,4}\s*-)\s*$")


def chunk_elements(
    elements: list[dict], *, document_id: str, chunk_size: int = 800, chunk_overlap: int = 100,
    tables: list[list[dict]] | None = None, min_chunk_chars: int = 30,
) -> list[dict]:
    """Chunk at heading/paragraph/list boundaries while keeping tables atomic.

    The heading stack and page bounds are copied to every chunk as explicit metadata.
    Without ``tables`` a table can exceed ``chunk_size``; preserving the whole table takes precedence.
    With ``tables`` (one entry per table element, see ``normalize.element_tables``) an oversized
    table is split into one chunk per data row (module docstring).
    """
    chunks: list[dict] = []
    heading_stack: list[tuple[int, str]] = []
    pending: list[dict] = []
    table_elements_seen = 0
    table_ids = 0

    def next_table_id() -> str:
        nonlocal table_ids
        table_ids += 1
        return f"{document_id}#table{table_ids - 1}"

    def render(block: dict) -> str:
        kind, text = block["type"], block["text"]
        if kind == "heading":
            return "#" * max(1, min(block.get("level") or 1, 6)) + " " + text
        if kind == "list_item":
            return text
        if kind == "image":
            return f"![page {block['page']} image](#page-{block['page']})"
        if kind == "table" and not text.strip():
            return "[표 셀 텍스트 없음]"
        return text

    def current_path() -> list[str]:
        # 열린 제목이 없으면 바로 앞 행 분할 표의 경로 -- 표 영역 안에서 칸에 못 든 글 조각(`normalize._outside_grid`)이 표 뒤에
        # 경로 없이 남았다('10년 별표 2 대비표 PDF: 표 아닌 청크가 이 조각 하나뿐이라 제목 경로 0/1로 탈락)
        return [title for _, title in heading_stack] or (list(last_table["path"]) if last_table else [])

    def flush() -> None:
        nonlocal pending
        if not pending:
            return
        text = "\n\n".join(render(item) for item in pending if render(item).strip()).strip()
        if text:
            pages = [item["page"] for item in pending]
            for item in pending:
                if item["type"] == "table":
                    pages.extend(int(page) for page in _PAGE_MARKER.findall(item.get("text", "")))
            chunks.append({
                "chunk_id": f"{document_id}#{len(chunks)}",
                "text": text,
                "document_id": document_id,
                "page_start": min(pages),
                "page_end": max(pages),
                "heading_path": current_path(),
                "element_types": list(dict.fromkeys(item["type"] for item in pending)),
                # 이 청크에 든 그림 원소(TextBundle에서 청크의 그림을 찾는 데 쓴다, #123). 그림이 없으면 키가 없다.
                **({"image_ids": ids} if (ids := [item["id"] for item in pending
                                                  if item["type"] == "image" and item.get("id")]) else {}),
            })
        pending = []

    def front_matter() -> bool:
        """문서 첫 섹션 제목(또는 부속 경계) 전의 짧은 앞머리(제목·부제·주석)인가: 아직 청크가 없고 열린 제목도 없으며
        `_FRONT_MATTER_MAX_CHARS` 이하. 이때는 닫지 않고 첫 섹션 청크 앞에 붙인다 -- 혼자 청크가 되면 맥락 없는 조각이다
        (반기 보고서 작성요령: `… 작성요령 / * "별지 19호의2 서식" 관련` 42자 청크가 모델 채점 저점)."""
        # 열린 경로가 부속 경계 표지(별표 머리 줄 등, 단계 0)뿐인 것도 앞머리다 -- `■ … [별표 1]` + 표 제목이 표와 떨어져 조각이 됐다
        return not chunks and all(level == 0 for level, _ in heading_stack) and size(pending) <= _FRONT_MATTER_MAX_CHARS

    def has_body(items: list[dict]) -> bool:
        """제목 말고 색인 본문에 남는 원소가 있는가(글자 없는 그림·빈 표는 색인 단계에서 지워진다)."""
        return any(not is_marker(item) and id(item) not in front_ids and (item.get("text") or "").strip() for item in items)

    front_ids: set[int] = set()  # 첫 섹션 청크에 붙인 앞머리 원소 -- 본문으로 세지 않아야 장 -> 조 제목 묶음이 이어진다

    label_only: set[int] = set()  # 표지 글자뿐인 부속 경계 문단(`[붙임][신설 …][개정 …]`) -- 제목처럼 뒤 내용과 한 청크가 된다

    def is_marker(item: dict) -> bool:
        return item["type"] == "heading" or id(item) in label_only

    def size(items: list[dict]) -> int:
        return sum(len(render(item)) for item in items) + max(0, len(items) - 1) * 2

    last_page = None  # 직전 글자 원소의 쪽(그림 제외) -- 쪽 머리 반복 제목 판단용
    questions = _faq_questions(elements)
    last_table = None   # 직전에 행으로 나눈 표의 열 이름·경로(머리글 없이 끊겨 이어진 표가 물려받는다)
    since_table = 0     # 그 뒤로 지나온 표 아닌 글자 수
    last_header = None  # 머리글이 있던 직전 표(행 분할 여부와 무관)의 열 이름·경로·끝 쪽 -- 머리글 없는 다음 쪽 표가 물려받는다
    heading_since = False  # 그 표 뒤로 제목·부속 표지가 나왔는가
    for element in elements:
        kind = element["type"]
        if kind != "table":
            since_table += len(element.get("text") or "")
        new_page = last_page is not None and element.get("page") != last_page
        if kind != "image":
            last_page = element.get("page")
        if id(element) in questions:
            # FAQ 질문: 질문과 답이 한 청크가 되게 질문마다 청크를 열고, 질문을 경로 끝에 둔다(앞 질문은 닫는다)
            if has_body(pending):
                flush()
            while heading_stack and heading_stack[-1][0] >= _QUESTION_LEVEL:
                heading_stack.pop()
            heading_stack.append((_QUESTION_LEVEL, " ".join(element["text"].split())[:_QUESTION_PATH_CHARS]))
            pending.append(element)
            continue
        boundary = (_part_boundary(element) if kind in ("heading", "paragraph")
                    # `■ 대외무역법 시행령 [별표 2] <개정 …>`은 `■` 때문에 목록 항목으로 들어온다 -- 별표 표지만 본다
                    # `◉ 산업통상자원부고시 제2021-202호`도 기호 때문에 목록 항목이다
                    else (patterns.annex_label_head(element.get("text") or "") or patterns.issuance_label(element.get("text") or ""))
                    if kind == "list_item" else None)
        if boundary is not None:
            # 부칙·붙임·별표·대비표 표지: 본칙의 장·조 경로를 닫고 이 표지 하나를 경로 뿌리로 둔다(모듈 docstring "부속 경계")
            if front_matter():
                front_ids.update(id(item) for item in pending)
            elif has_body(pending) and size(pending) >= min_chunk_chars:
                flush()
            heading_stack[:] = [(0, boundary)]
            heading_since = True
            text = (element.get("text") or "").strip()
            stripped = " ".join(_TRAILING_LAW_NOTES.sub("", text).split())
            if kind in ("paragraph", "list_item") and "\n" not in text and not _SENTENCE_END.search(text) and (
                    (stripped == boundary and stripped != " ".join(text.split()))  # 연혁 주석만 붙은 표지 줄
                    or len(text) <= _MARKER_LINE_MAX_CHARS):  # 표지 한 줄(영문 번역 꼬리, 발령 머리 줄 포함)
                label_only.add(id(element))  # 혼자 청크가 되면 내용 없는 청크다 -- 제목처럼 뒤 내용과 한 청크로
            pending.append(element)
            continue
        if kind == "paragraph" and patterns.AMENDMENT_INSTRUCTION.match(element.get("text") or ""):
            # 개정 지시문(`별표 22 제2호를 다음과 같이 한다.`): 앞에 실은 신설 조문(`제18조의3(…)`)의 내용이 아니라 고시 본문의
            # 다음 지시다. 조문 경로를 닫는다(닫지 않으면 뒤 지시문·별표 청크가 전부 그 조문 경로를 가졌다)
            # 발령 머리 줄이 경로 뿌리인 개정문이면, 지시문이 신설하는 번호 항목(`5. 해산물(…)`)이 제목으로 올라간 것까지 닫는다 --
            # 개정문에서 지시문은 항상 고시 본문 단계다(닫지 않으면 뒤 지시문이 `6. 섬유` 경로를 가졌다).
            notice = bool(heading_stack) and heading_stack[0][0] == 0 and patterns.issuance_label(heading_stack[0][1]) is not None

            def closes(title: str) -> bool:
                return patterns.closes_article(title) or (notice and not patterns.AMENDING_ARTICLE.search(title))

            if len(heading_stack) > (1 if notice else 0) and closes(heading_stack[-1][1]):
                if has_body(pending) and size(pending) >= min_chunk_chars:
                    flush()
                while len(heading_stack) > (1 if notice else 0) and closes(heading_stack[-1][1]):
                    heading_stack.pop()
        if kind == "table" and heading_stack and _SUPPLEMENTARY_HEAD.match(heading_stack[0][1]):
            # 부칙 아래 바로 오는 표는 부칙의 내용이 아니라 뒤에 붙은 별표·붙임이다(표지 줄 없이 표만 이어진 경우).
            # 부칙 경로는 닫되, 표 바로 앞에서 새로 연 제목(본문 없이 pending 끝에 쌓인 것)은 표의 제목이라 남긴다 -- 다 지우면
            # `부칙` -> `사업관리 … 세부지침`(붙임 표 제목) -> 표에서 행 청크 수백 개의 경로가 비었다.
            opened = set()
            for item in reversed(pending):
                if item["type"] != "heading":
                    break
                opened.add(item.get("text", ""))
            heading_stack[:] = [entry for entry in heading_stack[1:] if entry[1] in opened]
        if kind == "heading":
            heading_since = True
            level = max(1, element.get("level") or 1)
            if new_page and (level, element.get("text", "")) in heading_stack:
                continue  # 쪽 머리에 되풀이된, 이미 열린 제목 -- 이어지는 절(모듈 docstring)
            # 제목만 쌓여 있거나 본문이 아주 짧으면(`min_chunk_chars` 미만) 닫지 않는다 -- 다음 제목의 청크 앞에 이어 붙는다(모듈 docstring).
            # 문서 첫 섹션 전의 짧은 앞머리(`front_matter`)도 닫지 않는다.
            if front_matter():
                front_ids.update(id(item) for item in pending)
            elif has_body(pending) and size(pending) >= min_chunk_chars:
                flush()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, element.get("text", "")))
            pending.append(element)
            continue
        if kind == "table":
            objects = tables[table_elements_seen] if tables is not None and table_elements_seen < len(tables) else []
            table_elements_seen += 1
            if not element.get("text", "").strip():
                # 글자 없는 표는 색인 본문에 남지 않으므로 청크 경계가 되지 않는다(앞 제목만 남는 청크가 생긴다).
                # 표 번호(`table_ids`)는 원소 순서와 맞추려고 그대로 센다.
                table_ids += sum(1 for obj in objects for _ in logical_tables(obj))
                pending.append(element)
                continue
            # Keep any trailing headings with the table they introduce. 쌓인 것 전체가 아주 짧으면(제목+괄호 부제 등) 통째로 표와 묶는다.
            trailing_headings: list[dict] = []
            if pending and size(pending) < min_chunk_chars:
                trailing_headings, pending = pending, []
            while pending and is_marker(pending[-1]):
                trailing_headings.insert(0, pending.pop())
            if pending and size(pending) < min_chunk_chars:  # 표 앞에 남은 짧은 줄(`[별지 제21호 서식] 재수입신고서`)도 표와 함께
                trailing_headings, pending = pending + trailing_headings, []
            # 표 바로 앞의 단위 줄(`(단위: 밀리시버트)`)은 그 표의 것이다 -- 표와 같은 청크로 두고, 행으로 나누면 행마다 싣는다.
            lead_unit = ""
            while pending and pending[-1]["type"] == "paragraph" and _UNIT_LINE.match(pending[-1].get("text") or ""):
                lead_unit = lead_unit or _UNIT_LINE.match(pending[-1]["text"]).group(1).strip()
                trailing_headings.insert(0, pending.pop())
            if pending and front_matter():  # 문서 첫 표 앞의 짧은 앞머리(별표 머리 줄·표 제목)도 표와 함께 -- 따로 두면 맥락 없는 조각
                trailing_headings, pending = pending + trailing_headings, []
            flush()
            logical = [lt for obj in objects for lt in logical_tables(obj)]
            for lt in logical:
                if lead_unit and not lt.unit:
                    lt.unit = lead_unit
            # 머리글 없는 이어진 표: 표 사이에 짧은 줄(`주의`)이 끼어 같은 표가 두 표로 끊기면 뒤 표는 머리글이 없어 열 이름이
            # `열1/열2/열3`이 된다('10년 별표 2 대비표 PDF 24~34쪽). 바로 앞 표와 열 수가 같으면 그 열 이름과 경로를 잇는다.
            # 사이에 칸에서 흘러나온 글이 길어도(PDF 표 추출이 칸 글자를 표 밖 문단으로 흘린 경우) 바로 다음 쪽에서 이어지고 그 사이에
            # 제목이 없으면 같은 표다('11년 별표 2 대비표 PDF: 쪽마다 머리글 없는 4열 표).
            inherited_path = None
            for lt in logical:
                if (not lt.degraded and last_header and all(re.fullmatch(r"열\d+", c) for c in lt.columns)
                        and len(lt.columns) == len(last_header["columns"])
                        and (since_table <= _INHERIT_GAP_CHARS
                             or (not heading_since and lt.row_pages and lt.row_pages[0] <= last_header["page"] + 1))):
                    lt.columns = list(last_header["columns"])
                    inherited_path = last_header["path"]
            # 표 앞에 남은 짧은 글 줄(제목 아님): 행으로 나누는 경로에서는 본문에 두지 않으므로 경로 끝에 둔다(버리면 글자를 잃는다 --
            # 문서 첫 줄 `'10년 전략물자수출입고시 별표2 신구대비표(국문)`이 어디에도 없었다)
            lead_texts = [" ".join(t["text"].split()) for t in trailing_headings
                          if t["type"] != "heading" and (t.get("text") or "").strip()
                          and not _UNIT_LINE.match(t.get("text") or "")]  # 단위 줄은 행마다 `단위:`로 싣는다
            # 크기는 HTML 태그를 뺀 표 글자로 잰다 -- 병합 칸 표의 마크업(`<td rowspan=…>`) 길이로 재면 빈칸 서식도 큰 표가 된다
            table_chars = len(_HTML_TAG.sub("", element.get("text", "")))
            # 대비표는 크기와 상관없이 조문 쌍으로 -- 작은 대비표를 표 하나로 두면 현행·개정안이 좌우 칸 그대로 한 청크에 섞인다
            any_comparison = any(not lt.degraded and comparison_columns(lt.columns) for lt in logical)
            in_form = bool(heading_stack) and bool(_FORM_LABEL.search(heading_stack[0][1]))
            if in_form and not any_comparison and table_chars > chunk_size and not all(lt.degraded for lt in logical):
                # 별지(서식) 아래 큰 표: 데이터 표가 아니라 양식이라 행 청크로 나누지 않고, 칸 글자를 읽는 순서의 줄로 풀어 크기 단위로
                # 나눈다(`table_rows.form_lines`). 통째로 두면 HTML 태그 섞인 수천 자 청크, 행으로 나누면 서식 칸이 제목으로 복제됐다.
                path = [title for _, title in heading_stack]
                prefix = "\n\n".join(render(t) for t in trailing_headings if render(t).strip())
                for lt in logical:
                    table_id = next_table_id()
                    piece: list[tuple[int, str]] = []
                    pieces: list[list[tuple[int, str]]] = []
                    for page_line in (form_lines(lt) if not lt.degraded else []):
                        if piece and sum(len(l) + 1 for _, l in piece) + len(page_line[1]) > chunk_size:
                            pieces.append(piece)
                            piece = []
                        piece.append(page_line)
                    if piece:
                        pieces.append(piece)
                    for part in pieces:
                        body = "\n".join(line for _, line in part)
                        if prefix:
                            body, prefix = f"{prefix}\n\n{body}", ""
                        pages = [p for p, _ in part if p] or [element["page"]]
                        chunks.append({"chunk_id": f"{document_id}#{len(chunks)}", "document_id": document_id, "text": body,
                                       "page_start": min(pages), "page_end": max(pages), "heading_path": path,
                                       "element_types": ["table"], "table_id": table_id})
                last_table, since_table, heading_since = None, 0, False
                continue
            if any_comparison or (table_chars > chunk_size and any(lt.splittable or lt.has_oversized_row(chunk_size) for lt in logical)):
                # 머리 제목은 heading_path(-> 색인 제목)로 행 청크마다 남으므로 본문에 따로 두지 않는다.
                path = [title for _, title in heading_stack]
                for lt in logical:
                    table_id = next_table_id()
                    # 열린 제목이 없으면 표 제목 행(caption)이 경로가 된다 -- 문서 전체가 표 하나이고 표지가 표 첫 행에 든 별표
                    # (`[별표 2호의3] 상황허가 면제대상(제54조 관련)`)는 제목 원소가 없어 경로가 비었다.
                    caption_path = [" ".join(lt.caption.split())] if lt.caption else []  # 칸 줄바꿈(<br>)은 경로에 넣지 않는다
                    table_path = path or caption_path
                    if len(heading_stack) == 1 and heading_stack[0][0] == 0 and caption_path and caption_path[0] not in path[0]:
                        # 경로가 별표 표지뿐이면(`대외무역법 시행령 [별표 2]`) 표 제목 행을 경로에 더한다 -- 무슨 별표인지는 제목에 있다
                        table_path = path + caption_path
                    if inherited_path is not None:
                        table_path = inherited_path  # 끊긴 표의 뒤쪽: 앞 표와 같은 경로(사이에 낀 짧은 줄은 첫 행 본문 앞에)
                    # 표 앞 짧은 줄: 이미 경로에 있는 표지(부속 경계 `(붙임 1)`)는 빼고, 제목 모양이면 경로 끝에, 아니면(문장 `이 고시는
                    # … 시행한다.`) 첫 행 본문 앞에. 글자가 없는 조각(`.`)은 버린다.
                    lead_body = []
                    for text in lead_texts:
                        if text in table_path or len(_WORD_CHAR.findall(text)) < 2:
                            continue
                        if (" ".join(_TRAILING_LAW_NOTES.sub("", text).split()) in table_path
                                or patterns.annex_label_head(text) in table_path):
                            lead_body.append(text)  # 표지는 이미 경로에 있고 연혁 주석(`[신설 …][개정 …]`)만 남는다 -- 글자를 잃지 않게 본문에
                            continue
                        if inherited_path is None and len(text) <= _BOUNDARY_MAX_CHARS and not _SENTENCE_END.search(text):
                            table_path = table_path + [text]
                        else:
                            lead_body.append(text)
                    lead_texts = []  # 첫 논리 표에만
                    last_table = {"columns": list(lt.columns), "path": table_path}
                    if not lt.degraded and not all(re.fullmatch(r"열\d+", c) for c in lt.columns):
                        last_header = {"columns": list(lt.columns), "path": table_path,
                                       "page": lt.row_pages[-1] if lt.row_pages else element["page"]}
                    since_table, heading_since = 0, False
                    # 같은 표 노드 안의 작은 조각(열 구조가 달라 따로 남은 것)은 행을 나누지 않고 한 청크로 둔다.
                    comparison = not lt.degraded and comparison_columns(lt.columns) is not None
                    rows = (comparison_chunks(lt, table_id, chunk_size=chunk_size) if comparison  # 대비표: 조문 쌍 청크
                            else _list_chunks(lt, table_id, chunk_size) if lt.listlike or lt.outline  # 행마다 값 하나인 표 = 목록: 크기 단위로 묶는다
                            else row_chunks(lt, table_id, chunk_size=chunk_size))
                    if not comparison and not lt.splittable and rows and not lt.has_oversized_row(chunk_size):
                        rows = [{**rows[0], "text": "\n\n".join(r["text"] for r in rows),
                                 "page_start": min(r["page_start"] for r in rows),
                                 "page_end": max(r["page_end"] for r in rows)}]
                        for key in ("row_id", "row_index", "values"):
                            rows[0].pop(key)
                        rows[0].pop("section_path", None)  # 여러 행을 합친 청크에 첫 행의 조문만 붙이지 않는다
                    if lt.preamble:
                        # 표 첫 행 전체를 차지한 본문(별표의 일반기준): 행 청크 앞에 글 청크로(가./나. 줄바꿈 유지, 길면 나눈다)
                        pieces = [p.text for p in chunk_markdown(lt.preamble, chunk_size, chunk_overlap, min_chunk_chars=min_chunk_chars)]
                        for piece in pieces:
                            chunks.append({"chunk_id": f"{document_id}#{len(chunks)}", "document_id": document_id, "text": piece,
                                           "page_start": lt.row_pages[0] if lt.row_pages else element["page"],
                                           "page_end": lt.row_pages[0] if lt.row_pages else element["page"],
                                           "heading_path": table_path, "element_types": ["paragraph"]})
                    if lead_body and rows:  # 경로로 쓰지 않은 표 앞 줄은 첫 행 앞에(글자를 잃지 않게)
                        rows[0] = {**rows[0], "text": "\n".join(lead_body + [rows[0]["text"]])}
                    for row in rows:
                        section = row.pop("section_path", [])  # 칸 안 조문 표제(`table_rows._cell_sections`)
                        chunks.append({"chunk_id": f"{document_id}#{len(chunks)}", "document_id": document_id,
                                       "element_types": ["table"], **row, "heading_path": table_path + section})
                continue
            last_table, since_table = None, 0  # 통째로 둔 표 뒤 조각은 그 표의 경로를 쓰지 않는다(`current_path`)
            for lt in logical:  # 통째로 둔 표도 머리글은 다음 쪽 이어진 표에 물려준다
                if not lt.degraded and lt.columns and not all(re.fullmatch(r"열\d+", c) for c in lt.columns):
                    last_header = {"columns": list(lt.columns), "path": inherited_path or [t for _, t in heading_stack],
                                   "page": lt.row_pages[-1] if lt.row_pages else element["page"]}
            heading_since = False
            pending = [*trailing_headings, element]
            flush()
            if len(logical) == 1 and chunks and "table" in chunks[-1]["element_types"]:
                chunks[-1].update(table_fields(logical[0], next_table_id()))
            else:
                table_ids += len(logical)
            continue
        if kind in ("paragraph", "list_item") and _PAGE_NUMBER_ONLY.match(element.get("text", "")):
            continue  # 쪽 번호만 있는 줄(`- 1 -`, `3 / 12`)은 내용이 아니다 -- 혼자 청크가 되면 조각 청크다
        if not element.get("text", "").strip() and kind != "image":
            continue
        # Keep paragraph/list boundaries; split an oversized text block without
        # ever applying that fallback to tables.
        if size([element]) > chunk_size and kind in ("paragraph", "list_item"):
            leading: list[dict] = []  # 앞에 쌓인 제목은 첫 조각 앞에 붙인다
            while pending and is_marker(pending[-1]):
                leading.insert(0, pending.pop())
            flush()
            prefix = "\n\n".join(render(h) for h in leading)
            pieces = [p.text for p in chunk_markdown(element["text"], chunk_size, chunk_overlap, min_chunk_chars=1)]
            if len(pieces) > 1 and len(pieces[-1]) < min_chunk_chars:  # 꼬리 조각(`제50조제4항)`)은 앞 조각에
                # pop을 먼저 따로 한다 -- `pieces[-2] = … pieces.pop()`은 오른쪽(pop)이 먼저 돌아 대입 대상이 한 칸 앞
                # 조각이 되고, 세 조각일 때 첫 조각이 덮여 사라졌다(Q108 FAQ, 유실 검사로 발견)
                tail = pieces.pop()
                pieces[-1] = f"{pieces[-1]} {tail}"
            for index, piece in enumerate(pieces):
                text = f"{prefix}\n\n{piece}" if prefix and index == 0 else piece
                chunks.append({
                    "chunk_id": f"{document_id}#{len(chunks)}", "text": text,
                    "document_id": document_id, "page_start": element["page"],
                    "page_end": element["page"], "heading_path": current_path(),
                    "element_types": [kind],
                })
            continue
        if pending and has_body(pending) and size(pending + [element]) > chunk_size:
            flush()
        pending.append(element)
    flush()
    return _drop_repeated_headers(_attach_footnotes(chunks), document_id)


# FAQ 질문 줄: 물음표로 끝나는 짧은 문단·목록 항목. 문서에 `_QUESTION_MIN`개 이상 있으면 문답 문서로 보고 질문마다 청크를 연다
# (실측: CP 설명회 주요 질의응답 -- `☐ (포괄허가) …?` 다음 답 `- …`가 청크 경계에서 질문과 갈렸다).
_QUESTION = re.compile(r"[?？]\s*$")
_QUESTION_MIN = 3
_SENTENCE_DONE = re.compile(r"[.?!？。]\s*$|다\s*$")
_ITEM_START = re.compile(r"^\s*(?:[☐□ㅇ○●◦•·※\-–—*]|Q\s*\d|\d+[.)]|[가-힣][.)]|[(（][^)）]{1,12}[)）])")
_QUESTION_MAX_CHARS = 300
_QUESTION_LEVEL = 99            # 질문은 열린 제목들 아래 가장 깊은 단계
_QUESTION_PATH_CHARS = 80


def _list_chunks(table, table_id: str, chunk_size: int) -> list[dict]:
    """행마다 값이 한두 개뿐인 표(`LogicalTable.listlike`/`outline`)를 행 순서대로 청크 크기만큼 묶는다. 값 앞에 열 이름(`열1:`)은
    붙이지 않는다(값이 둘이면 ` | `로 잇는다).

    목록형 표(`outline`)는 구역 줄(`1. 1종화학물질`, `가. 독성화학물질`)을 따라가 청크마다 `구역:` 줄로 싣는다 -- 표 제목에 첫 구역이
    붙어 모든 청크에 반복되던 것(특정화학물질 별표: 2종·3종 구역 청크에도 `1. 1종화학물질 … 예) 사린 …`) 대신, 그 청크가 속한 구역을
    준다. 구역이 바뀌면 새 청크를 열고, 구역 이름뿐인 줄은 `구역:` 줄로 대신한다. 칸 중간에 구역 줄이 있으면(앞 항목 글 다음 줄에
    `2. 2종화학물질`) 그 줄에서 나눈다.
    """
    head = ([f"표: {table.caption}"] if table.caption else []) + ([f"단위: {table.unit}"] if table.unit else [])
    base = table_fields(table, table_id)
    outline = table.outline
    state = {"prefix": list(head), "cur": [], "pages": [], "section": "", "area_only": True}
    areas: list[tuple[int, str]] = []
    out: list[dict] = []

    def emit() -> None:
        if state["cur"]:
            out.append({**base, "text": "\n".join(state["prefix"] + state["cur"]),
                        "page_start": min(state["pages"]), "page_end": max(state["pages"])})

    def add(value: str, page: int) -> None:
        opens = bool(_FORM_SECTION.match(value))  # 서식 칸 번호(①~⑳)에서 새 청크 -- 칸 하나가 한 단위
        cur = state["cur"]
        if cur and (opens or len("\n".join(state["prefix"] + cur + [value])) > chunk_size):
            emit()
            # 크기 때문에 칸 중간에서 나뉘면 뒤 조각에도 칸 제목 줄을 둔다(`c. □ Will be used …`만 남으면 무엇을 묻는 칸인지 모른다)
            section = state["section"]
            state["cur"] = [section] if section and not opens and len(section) <= _FORM_SECTION_MAX_CHARS else []
            state["pages"] = []
        if opens:
            state["section"] = value
        state["cur"].append(value)
        state["pages"].append(page)

    def pieces(row: list[str], spill: set[int]) -> list[tuple[str, str]]:
        """행 -> (첫 줄, 조각 글) 목록. 첫 줄은 구역 이름을 정할 때 쓴다(조각 글은 다음 항목 줄까지 이어질 수 있다)."""
        own = list(dict.fromkeys(v.strip() for c, v in enumerate(row) if v.strip() and c not in spill))
        if not own:
            return []
        if not outline or len(own) != 1:
            return [(own[0].splitlines()[0], " | ".join(" ".join(v.split()) for v in own))]
        parts, block = [], []
        for line in own[0].splitlines():
            if block and (_AREA_NUMBER.match(line) or _AREA_LETTER.match(line)):
                parts.append((block[0], " ".join(" ".join(block).split())))
                block = []
            block.append(line)
        if block:
            parts.append((block[0], " ".join(" ".join(block).split())))
        return parts

    for index, row in enumerate(table.rows):
        spill = table.spill[index] if index < len(table.spill) else set()
        page = table.row_pages[index]
        for first, value in pieces(row, spill):
            if not value:
                continue
            if outline:
                rank = 1 if _AREA_NUMBER.match(first) else 2 if _AREA_LETTER.match(first) else None
                if rank:
                    while areas and areas[-1][0] >= rank:
                        areas.pop()
                    label = " ".join(first.split())
                    areas.append((rank, label[:_AREA_MAX_CHARS]))
                    if not state["area_only"]:
                        emit()  # 구역이 바뀌면 새 청크
                    state.update(cur=[], pages=[], area_only=True,
                                 prefix=head + [f"구역: {' > '.join(name for _, name in areas)}"])
                    if value == label and len(label) <= _AREA_MAX_CHARS:
                        continue  # 구역 이름뿐인 줄은 `구역:` 줄로 대신한다
                state["area_only"] = False
            add(value, page)
    emit()
    return out


_FORM_SECTION = re.compile(r"^\s*[①-⑳]")  # ①~⑳
_AREA_NUMBER = re.compile(r"^\s*\d{1,2}\.\s")  # 목록형 표의 구역 줄: `1. 1종화학물질`
_AREA_LETTER = re.compile(r"^\s*[가-하]\.\s")    # 하위 구역 줄: `가. 독성화학물질`
_AREA_MAX_CHARS = 40
_FORM_SECTION_MAX_CHARS = 200


# 부속 경계(본칙 뒤에 붙는 부분의 표지). 이 줄이 나오면 그때까지 열린 장·조 경로를 닫는다 -- 닫지 않으면 마지막 부칙
# `제1조(시행일)`이 뒤 붙임·별표·대비표 청크 전부의 경로가 됐다(실측: 법령 50건 중 7건 129청크).
# 부칙은 날짜를 괄호로 덧붙이거나(`부 칙(’15.7.30.)`) 본문 첫 문장이 같은 줄에 붙어 나온다(PDF 줄 병합).
_SUPPLEMENTARY_HEAD = re.compile(r"^\s*부\s*칙\s*(?:[<〈(（\[][^>〉)）\]\n]{0,30}[>〉)）\]])?")
# 붙임 표지: `(붙임 1)`, `<붙임2>`, `붙임 1 전략물자 해석 사례` -- 뒤 제목은 짧고 문장이 아니어야 한다("첨부 서류를 제출한다"는 본문)
_ATTACHMENT_LABEL = re.compile(r"^\s*[<\[【(（]?\s*(?:붙임|별첨|첨부|유첨)\s*\d*\s*[>\]】)）]?(?:\s|$)")
# 문장이거나 공문 끝 붙임 목록 줄(`붙임 1. 평가지표 1부.` -- 부수가 붙은 첨부 목록)이면 표지가 아니다
_SENTENCE_END = re.compile(r"(?:다|요|음|함|\d\s*부)\s*[.。]?\s*$")
_BOUNDARY_MAX_CHARS = 60
_UNIT_LINE = re.compile(r"^\s*[(（\[<〈]?\s*단\s*위\s*[:：]\s*([^)）\]>〉]{1,20}?)\s*[)）\]>〉]?\s*$")  # 표 앞 단위 줄
_FRONT_MATTER_MAX_CHARS = 150  # 첫 섹션 청크 앞에 붙일 앞머리(제목·부제·주석)의 최대 글자 수
_MARKER_LINE_MAX_CHARS = 60  # 표지 한 줄로 보는 길이(`[별지 제2호의2 서식] Annexed paper No. 2-2`)
# 경로 뿌리가 이 표지면 그 아래 표는 서식(양식)이다: `[별지 제2호 서식]`, `[서식 제1호]`, `<제3호 서식>`. `<서식 목록>`은 서식들의
# 목록(데이터 표)이라 아니다(행정·업무 서식목록 문서가 행 청크를 잃었다).
_FORM_LABEL = re.compile(r"별\s*지|서\s*식\s*제?\s*\d+|제?\s*\d+\s*호\s*(?:의\s*\d+\s*)?서\s*식")
# 줄 끝에 이어진 연혁 주석 괄호들(`[신설 2015.7.30.][개정 2017.6.14.]`) -- patterns.LAW_NOTE와 같은 조건을 줄 끝 반복으로
_TRAILING_LAW_NOTES = re.compile(
    r"(?:\s*[\[<〈](?=[^\]>〉]*(?:신설|개정|삭제|이동|폐지))(?=[^\]>〉]*\d{2,4}\s*[.,]\s*\d{1,2})[^\]>〉]*[\]>〉])+\s*$")
_WORD_CHAR = re.compile(r"[가-힣A-Za-z0-9]")
_INHERIT_GAP_CHARS = 100  # 끊긴 표 사이에 낄 수 있는 글자 수(`주의` 같은 한 줄) -- 이보다 길면 다른 표다


def _part_boundary(element: dict) -> str | None:
    """원소가 부속 경계 표지면 경로에 쓸 표지 글자를, 아니면 None."""
    text = (element.get("text") or "").strip()
    first = text.split("\n", 1)[0].strip()
    head = _SUPPLEMENTARY_HEAD.match(first)
    if head:
        label = " ".join(head.group(0).split())
        # 같은 줄에 본문이 이어지면 날짜 괄호가 붙은 표지일 때만(`부 칙(’17.6.14.) 이 지침은 …`) -- "부칙에 따라 …" 같은 본문 언급과 가른다
        if not first[head.end():].strip() or label[-1] in ")）]>〉":
            return label
        return None
    # 붙임·별표 표지 뒤에 붙은 연혁 주석(`[붙임][신설 2015.7.30.][개정 …]`)은 표지의 일부가 아니다 -- 떼고 본다.
    # 부칙은 떼지 않는다: `부 칙 <2차개정 2005. 12. 27>`의 괄호는 어느 부칙인지 가르는 표지다.
    first = _TRAILING_LAW_NOTES.sub("", first).strip() or first
    annex = patterns.annex_label_head(first)  # 표지 뒤 영문 번역 꼬리(`[별지 제2호의2 서식] Annexed paper No. 2-2`)는 떼고 표지만
    if annex:
        return annex
    if patterns.issuance_label(first):
        return patterns.issuance_label(first)  # 발령 문서 머리 줄(`산업통상부고시 제 2026-101 호`): 앞 개정 이유 목록과 본문의 경계
    if len(first) <= 20 and patterns.COMPARISON_TABLE.search(first):
        return " ".join(first.split())  # 대비표 제목 줄(문단으로 나와도)
    if len(first) > _BOUNDARY_MAX_CHARS:
        return None
    if (_ATTACHMENT_LABEL.match(first) and not _SENTENCE_END.search(first)) or patterns.ANNEX_LABEL.match(first) or (
            patterns.COMPARISON_TABLE.search(first) and element["type"] == "heading"):
        return " ".join(first.split())
    return None


def _faq_questions(elements: list[dict]) -> set[int]:
    """질문이 시작하는 원소들. 질문이 두 줄로 갈려 물음표 줄이 이어짐이면(앞 원소가 문장으로 끝나지 않았고 물음표 줄이 기호로
    시작하지 않음) 앞 원소가 질문의 시작이다 -- 물음표 줄에서 청크를 열면 질문 앞부분이 앞 청크에 남는다."""
    openers = []
    for i, e in enumerate(elements):
        text = e.get("text", "")
        if not (e["type"] in ("paragraph", "list_item") and len(text) <= _QUESTION_MAX_CHARS and _QUESTION.search(text)):
            continue
        prev = elements[i - 1] if i else None
        continued = (prev is not None and prev["type"] in ("paragraph", "list_item")
                     and not _SENTENCE_DONE.search(prev.get("text", "")) and not _ITEM_START.match(text))
        openers.append(prev if continued else e)
    return {id(e) for e in openers} if len(openers) >= _QUESTION_MIN else set()


# 표 각주: 행으로 나눈 표 바로 뒤 청크가 `*` 표식 줄로 시작하면 각 각주를 같은 개수의 `*`가 붙은 값을 가진 행 청크 끝에 붙인다.
# 각주 청크는 그대로 둔다(표식 없는 ※ 주석과 전체 각주가 남는다). 실측: 별표 19 -- `사후거래보고*****` 행과 그 뜻이 다른 청크에 있었다.
_FOOTNOTE_LINE = re.compile(r"^\s*(\*+)\s*(\S.*)$")
_MAX_FOOTNOTE_CHARS = 300
# 표 전체 주석: `※`/`※※` 줄은 행 쪽에 같은 표식이 없다(실측: 별표 19 -- `※※ 허가면제 … 사전신고를 한 경우 사후거래보고는 생략
# 가능`이 표식 없이 표 밑에만 있어 "사전신고했다면 사후거래보고 안 해도 되나" 질문이 답을 놓쳤다). 행 쪽에 같은 표식이 없으면 표
# 전체 조건으로 보고 모든 행 청크에 붙인다. 행마다 되풀이되므로 몇 줄 안 될 때만(그 이상이면 작성요령 같은 안내문이다).
_TABLE_NOTE_LINE = re.compile(r"^\s*(※+)\s*(\S.*)$")
_MAX_TABLE_NOTES = 3


def _attach_footnotes(chunks: list[dict]) -> list[dict]:
    for i in range(1, len(chunks)):
        table_id = chunks[i - 1].get("table_id")
        if not table_id or chunks[i].get("table_id") or "row_id" not in chunks[i - 1]:
            continue
        notes: dict[int, str] = {}
        table_notes: list[tuple[str, str]] = []
        for line in chunks[i]["text"].split("\n"):
            m = _FOOTNOTE_LINE.match(line)
            if m and len(m.group(2)) <= _MAX_FOOTNOTE_CHARS:
                notes.setdefault(len(m.group(1)), m.group(2).strip())
            m = _TABLE_NOTE_LINE.match(line)
            if m and len(m.group(2)) <= _MAX_FOOTNOTE_CHARS:
                table_notes.append((m.group(1), m.group(2).strip()))
        rows = [row for row in chunks if row.get("table_id") == table_id]
        # 행 쪽에 같은 ※ 표식이 붙어 있으면 표 전체 주석이 아니다(그런 표는 아직 없다 -- 그때는 붙이지 않고 각주 청크에 둔다)
        if len(table_notes) > _MAX_TABLE_NOTES or any(
                re.search(r"(?<=\S)※", row["text"]) for row in rows):
            table_notes = []
        if not notes and not table_notes:
            continue
        for row in rows:
            marks = {len(run) for run in re.findall(r"(?<=\S)(\*+)(?!\S*\w)", row["text"])}
            extra = [f"{'*' * n} {notes[n]}" for n in sorted(marks) if n in notes]
            extra += [f"{mark} {note}" for mark, note in table_notes]
            if extra:
                row["text"] = row["text"] + "\n" + "\n".join(extra)
    return chunks


def _drop_repeated_headers(chunks: list[dict], document_id: str) -> list[dict]:
    """표 머리글만 문단으로 떨어져 나온 청크를 뺀다(모듈 docstring "쪽마다 되풀이되는 표 머리글").

    본문 줄이 바로 앞이나 뒤 표 청크의 열 이름과 차례대로 같은 청크만 뺀다. 열 이름은 표 청크에 이미 있으므로 잃는 글자가 없다.
    """
    def lines(chunk: dict) -> list[str]:
        return [" ".join(line.split()) for line in chunk["text"].splitlines() if line.strip()]

    def header_of(chunk: dict | None) -> list[str]:
        if not chunk or "table" not in chunk.get("element_types", []):
            return []
        return [" ".join(c.split()) for c in chunk.get("columns") or [] if c.strip()]

    keep = []
    for i, chunk in enumerate(chunks):
        if chunk.get("element_types") == ["paragraph"]:
            body = lines(chunk)
            neighbors = (chunks[i - 1] if i else None, chunks[i + 1] if i + 1 < len(chunks) else None)
            if len(body) >= 2 and any(body == header_of(n) for n in neighbors):
                continue
        keep.append(chunk)
    if len(keep) == len(chunks):
        return chunks
    return [{**chunk, "chunk_id": f"{document_id}#{i}"} for i, chunk in enumerate(keep)]

