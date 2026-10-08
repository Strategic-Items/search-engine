# 이식 원본: unstructured-doc-parser_ver2 tests/test_chunking_structured.py (def6caf). 파서의 직렬화·PDF 구조 추출을 검사하던 테스트는 뺐다.
from search_engine.chunking.structured import chunk_elements


def test_chunk_elements_preserves_heading_path_pages_and_element_types():
    chunks = chunk_elements([
        {"type": "heading", "text": "제1조 목적", "level": 2, "page": 1},
        {"type": "paragraph", "text": "목적 본문", "page": 2},
    ], document_id="doc")

    assert len(chunks) == 1
    assert chunks[0]["document_id"] == "doc"
    assert chunks[0]["page_start"] == 1
    assert chunks[0]["page_end"] == 2
    assert chunks[0]["heading_path"] == ["제1조 목적"]
    assert chunks[0]["element_types"] == ["heading", "paragraph"]
    assert "## 제1조 목적" in chunks[0]["text"]


def test_table_is_kept_as_a_single_chunk_even_when_oversized():
    table = "| 값 |\n|---|\n" + "| 항목 |\n" * 120
    chunks = chunk_elements([{"type": "table", "text": table, "page": 2}],
                            document_id="doc", chunk_size=40)

    assert len(chunks) == 1
    assert chunks[0]["text"] == table.strip()
    assert chunks[0]["page_start"] == 2
    assert chunks[0]["page_end"] == 2


# ---- 민원·FAQ (#98): 질문 경계, 꼬리 조각, 표 앞 짧은 줄. 글자는 가상의 것이다.

def _p(text, kind="paragraph", page=1):
    return {"id": text[:8], "type": kind, "text": text, "page": page, "bbox": None, "level": None}


def test_faq_question_opens_a_chunk_and_keeps_its_answer():
    answer = "- 가상 답변 문장입니다. " * 25
    elements = []
    for n in range(1, 4):
        elements += [_p(f"☐ (가상 {n}) 가상 질문 {n}은 어떻게 되는가?", "list_item"), _p(answer, "list_item")]
    chunks = chunk_elements(elements, document_id="d")
    for n in range(1, 4):
        mine = [c for c in chunks if c["heading_path"] and c["heading_path"][-1].startswith(f"☐ (가상 {n})")]
        assert mine and mine[0]["text"].startswith(f"☐ (가상 {n})")                  # 질문으로 시작하는 청크
        assert all(f"가상 질문 {m}" not in c["text"] for c in mine for m in range(1, 4) if m != n)


def test_question_marks_below_threshold_do_not_split():
    elements = [_p("가상 문장입니다. 왜 그런가?"), _p("가상 설명 문장입니다. " * 3)]
    assert len(chunk_elements(elements, document_id="d")) == 1


def test_short_tail_piece_of_a_long_paragraph_joins_the_previous_piece():
    text = ("가상 긴 문장입니다. " * 70) + "제5조)"
    chunks = chunk_elements([_p(text)], document_id="d", chunk_size=400)
    assert all(len(c["text"]) >= 30 for c in chunks)


def test_two_line_question_opens_the_chunk_at_its_first_line():
    answer = "- 가상 답변 문장입니다. " * 25
    elements = [_p("☐ (가상 1) 가상 질문 1은 어떻게 되는가?", "list_item"), _p(answer, "list_item"),
                _p("☐ (가상 2) 가상 문서를 외국인이 보게", "list_item"), _p("될 수 있다면 어떻게 하는가?"), _p(answer, "list_item"),
                _p("☐ (가상 3) 가상 질문 3은?", "list_item"), _p(answer, "list_item")]
    chunks = chunk_elements(elements, document_id="d")
    second = next(c for c in chunks if "가상 2" in c["text"])
    assert second["text"].startswith("☐ (가상 2)") and "될 수 있다면" in second["text"]


# ---- 부속 경계(부칙·붙임·별표 표지가 본칙 경로를 닫는다)


def _body(text, page=1):
    return {"type": "paragraph", "text": text, "page": page}


def test_supplementary_paragraph_with_date_closes_article_path():
    chunks = chunk_elements([
        {"type": "heading", "text": "제3조(정의)", "level": 1, "page": 1},
        _body("이 지침에서 사용하는 용어의 뜻은 다음과 같다. " * 2),
        _body("부 칙(’15.7.30.)"),
        {"type": "heading", "text": "제1조(시행일)", "level": 1, "page": 1},
        _body("이 세부지침은 2015년 7월 30일부터 시행한다. 다른 규정은 따로 정한다."),
    ], document_id="doc")
    assert chunks[-1]["heading_path"] == ["부 칙(’15.7.30.)", "제1조(시행일)"]


def test_attachment_label_after_supplementary_starts_new_root():
    chunks = chunk_elements([
        _body("부칙"),
        {"type": "heading", "text": "제1조(시행일)", "level": 1, "page": 1},
        _body("이 고시는 공포한 날부터 시행한다. 다만 일부 조항은 따로 정한 날부터 시행한다."),
        _body("(붙임 1)", page=2),
        _body("해석 사례를 정리하면 다음과 같으며 각 사례는 판정에 참고한다.", page=2),
    ], document_id="doc")
    assert chunks[-1]["heading_path"] == ["(붙임 1)"]


def test_body_mentions_are_not_boundaries():
    for text in ("부칙에 따라 종전 규정을 적용한다.", "붙임 1. 평가지표 1부.", "첨부 서류를 제출하여야 한다."):
        chunks = chunk_elements([
            {"type": "heading", "text": "제5조(신청)", "level": 1, "page": 1},
            _body(text + " 이 경우 신청인은 기한을 지켜야 한다."),
        ], document_id="doc")
        assert chunks[-1]["heading_path"] == ["제5조(신청)"], text


# ---- 이름이 같은 이웃 열(머리글 칸 하나가 하위 열 여럿에 걸침)은 한 줄로


def test_repeated_column_names_merge_into_one_line():
    from search_engine.chunking.table_rows import _named_lines

    assert _named_lines([("구분", "개별"), ("특례", "다음 중 하나"), ("특례", "1. 최대주주"), ("특례", "가 지역"),
                         ("등급 A", "면제")]) == ["구분: 개별", "특례: 다음 중 하나 > 1. 최대주주 > 가 지역", "등급 A: 면제"]
    assert _named_lines([("열1", "a"), ("열2", "b"), ("열1", "c")]) == ["열1: a", "열2: b", "열1: c"]


# ---- 키(통제번호)로 행이 나뉜 대비표 / 끊겨 이어진 머리글 없는 표 / 표 앞 짧은 줄


def _tbl(rows, pages=1):
    return {"type": "table", "rows": rows, "header_rows": 0, "merges": [], "pages": [pages],
            "row_pages": [pages] * len(rows)}


# ---- 부칙 뒤 붙임 표의 경로(heading_path가 비던 문제, 2026-10-07)


def _annex_table():
    table = _tbl([["통제번호", "해석 세부지침"]] + [[f"1A00{k}", f"가상 해석 문장 {k} " * 15] for k in range(6)])
    table["header_rows"] = 1
    return table


def _supplementary_then_annex(label):
    return [
        {"type": "heading", "text": "부 칙(’24. 2. 24.)", "level": 1, "page": 1},
        _body("이 지침은 2024년 2월 24일부터 시행한다."),
        *([_body(label)] if label else []),
        {"type": "heading", "text": "가상 세부지침", "level": 2, "page": 1},
        {"type": "table", "text": "x" * 2000, "page": 1},
    ]


def test_attachment_label_with_revision_notes_is_a_boundary_and_keeps_its_text():
    label = "[붙임][신설 2015.7.30.][개정 2017.6.14.]"
    chunks = chunk_elements(_supplementary_then_annex(label), document_id="doc", tables=[[_annex_table()]])
    rows = [c for c in chunks if c.get("row_id")]
    assert rows and all(c["heading_path"] == ["[붙임]", "가상 세부지침"] for c in rows)
    assert not any(c["text"].strip() == label for c in chunks)  # 표지 줄만 든 청크를 만들지 않는다
    assert sum(label in c["text"] for c in chunks) == 1        # 연혁 주석 글자는 잃지 않는다


def test_supplementary_date_notes_are_not_stripped():
    chunks = chunk_elements([
        _body("부 칙 <2차개정 2005. 12. 27>"),
        {"type": "heading", "text": "제1조(시행일)", "level": 1, "page": 1},
        _body("이 고시는 공포한 날부터 시행한다. 다만 일부 조항은 따로 정한 날부터 시행한다."),
    ], document_id="doc")
    assert chunks[-1]["heading_path"] == ["부 칙 <2차개정 2005. 12. 27>", "제1조(시행일)"]
