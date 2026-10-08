# 이식 원본: unstructured-doc-parser_ver2 tests/test_table_cells.py (def6caf). 파서의 직렬화·PDF 구조 추출을 검사하던 테스트는 뺐다.
"""표 칸 안에 문서 한 편이 든 표(대비표·별표 서식 등)의 청킹 원칙(`chunking/table_rows.py`).

- 머리글 + 데이터 한 행짜리 표도 첫 행이 머리글 모양이고 둘째 행은 아니면 머리글로 본다.
- 행 하나가 청크 크기를 넘으면 긴 칸은 그 칸의 글을 문서처럼 구조(조문 -> 번호 -> 문단) 경계로 나누고, 짧은 칸은 한 청크로
  모은다. 조각은 어느 표·행·열의 몇 번째인지 메타데이터로 남는다. 글자는 가상의 것이다.
"""

import pytest

from search_engine.chunking.structured import chunk_elements
from search_engine.chunking.table_rows import logical_tables


def _article_text(count, words=30):
    return "\n".join(f"제{n}조(항목{n}) " + " ".join(["가나다라 마바사"] * words) + "을 정한다." for n in range(1, count + 1))


def _table(rows):
    return {"rows": rows, "header_rows": 0, "merges": [], "pages": [1]}


def _element(rows):
    text = "\n".join(" | ".join(r) for r in rows)
    return {"id": "t", "type": "table", "text": text, "page": 1, "bbox": None, "level": None}


@pytest.mark.parametrize("header, data", [
    (["원문", "해설", "비고"], [_article_text(12), _article_text(14), "조문 이동"]),
    (["구분", "내용"], ["가나다", _article_text(20)]),
    (["항목", "기준", "근거"], ["라마바", _article_text(9), _article_text(9)]),
])
def test_two_row_table_with_document_cells(header, data):
    rows = [header, data]
    (lt,) = logical_tables(_table(rows))
    assert lt.columns == header and len(lt.rows) == 1          # 머리글 + 데이터 한 행

    chunks = chunk_elements([_element(rows)], document_id="d", tables=[[_table(rows)]], chunk_size=800)
    assert max(len(c["text"]) for c in chunks) <= 800 + 80   # 칸 이름 줄만큼의 여유
    long_columns = {name for name, value in zip(header, data) if len(value) > 400}
    pieces = [c for c in chunks if c.get("column")]
    assert {c["column"] for c in pieces} == long_columns
    keys = [f"{n}: {v}" for n, v in zip(header, data) if len(v) <= 40]   # 행 식별자 칸(짧은 값)
    for c in pieces:
        lines = c["text"].split("\n")
        assert lines[:len(keys)] == keys                        # 조각마다 행 식별자를 머리 줄로 단다
        assert lines[len(keys)] == c["column"] + ":"            # 그다음 어느 열의 조각인지
        assert lines[len(keys) + 1].startswith("제") or c["piece_index"] > 0   # 첫 조각은 조문 경계에서 시작
        assert c["row_id"].endswith("#row0") and c["table_id"]
    assert not any(len(c["text"]) < 30 for c in chunks)         # 식별자만 든 짧은 청크를 따로 만들지 않는다
    for column in long_columns:                                 # 칸의 모든 조문이 빠짐없이 들어간다
        joined = "\n".join(c["text"] for c in pieces if c["column"] == column)
        value = data[header.index(column)]
        assert all(line.split(" ", 1)[0] in joined for line in value.splitlines())


def test_two_short_rows_keep_no_header_when_ambiguous():
    (lt,) = logical_tables(_table([["가", "나"], ["다", "라"]]))
    assert lt.columns == ["열1", "열2"] and len(lt.rows) == 2


def test_small_row_is_not_split_into_cells():
    rows = [["구분", "내용"], ["가", "짧은 값"], ["나", "또 짧은 값"]]
    chunks = chunk_elements([_element(rows)], document_id="d", tables=[[_table(rows)]], chunk_size=800)
    assert not any(c.get("column") for c in chunks)


# ---- 칸 안 조문 표제를 조각의 heading_path로 (#108). 글자는 가상의 것이다.

def _long_article(number, title, items, words=12, number_text=None):
    """조문 하나: 표제 줄 + 각 호. 호가 많아 조문 중간에서 조각이 잘리게 만든다."""
    head = f"{number_text or f'제{number}조'}({title}) 다음 각 호의 경우를 말한다."
    return "\n".join([head] + [f"{i}. " + " ".join(["사바아자 차카타"] * words) + "인 경우" for i in range(1, items + 1)])


def _comparison(current, revised):
    rows = [["원문", "해설"], [current, revised]]  # 대비표가 아닌 긴 칸 표(대비표는 `comparison_chunks`)
    return chunk_elements([_element(rows)], document_id="d", tables=[[_table(rows)]], chunk_size=800)


@pytest.mark.parametrize("cell, parents, articles", [
    # 조문 중간에서 잘린 조각(호만 있음)도 그 조문 표제를 경로에 갖는다
    ("\n".join([_long_article(3, "허가", 12), _long_article(4, "신고", 12)]), [], ["제3조(허가)", "제4조(신고)"]),
    # 표제 앞의 법령명 줄(짧은 줄)과 장 줄
    ("가상법\n제2장 수출입\n" + _long_article(10, "통제", 14), ["제2장 수출입"], ["제10조(통제)"]),
    # 가지번호 조문과 한자 표기(옛 법령) -- 표제 글자는 원문 그대로
    ("\n".join([_long_article(0, "가지", 10, number_text="제7조의2"), _long_article(0, "罰則", 10, number_text="第9條")]),
     [], ["제7조의2(가지)", "第9條(罰則)"]),
], ids=["mid-article", "law-name-and-chapter", "branch-and-hanja"])
def test_cell_pieces_carry_article_heading(cell, parents, articles):
    chunks = _comparison(cell, "가나다라 " * 10)
    pieces = [c for c in chunks if c.get("column") == "원문"]
    assert len(pieces) >= 3
    seen = []
    for c in pieces:
        assert c["heading_path"][:-1] == parents                # 조 위의 장·절
        article = c["heading_path"][-1]                         # 조각마다 조문 표제가 있다
        assert article in articles
        body = c["text"].split("\n", 1)[1]
        if any(body.lstrip().startswith(a.split("(")[0]) for a in articles):
            assert body.lstrip().startswith(article.split("(")[0])  # 표제 줄로 시작하면 그 표제
        seen.append(article)
    assert seen == sorted(seen, key=articles.index) and set(seen) == set(articles)   # 조문 순서대로, 빠짐없이


def test_current_and_revised_pieces_share_article_path():
    """같은 조문의 현행 조각과 개정안 조각이 같은 경로를 갖는다 -- 쌍을 경로로 잇는다."""
    current = "\n".join(_long_article(n, f"항목{n}", 6) for n in (1, 2, 3))
    revised = "\n".join(_long_article(n, f"항목{n}", 8) for n in (1, 2, 3))
    chunks = _comparison(current, revised)
    paths = {col: {tuple(c["heading_path"]) for c in chunks if c.get("column") == col} for col in ("원문", "해설")}
    assert paths["원문"] and paths["원문"] <= paths["해설"]


@pytest.mark.parametrize("cell", [
    # 조문 구조가 없는 칸: 번호 목록·인용만 있다
    "\n".join(f"{i}. " + " ".join(["사바아자 차카타"] * 12) for i in range(1, 15)),
    # 줄 첫머리의 조문 인용("제21조제1항의 규정에 의하여")은 표제가 아니다
    "\n".join(f"제21조제{i}항의 규정에 의하여 " + " ".join(["사바아자 차카타"] * 12) for i in range(1, 15)),
    # 괄호 표제 없는 "제5조 …" 문장도 표제로 보지 않는다
    "\n".join(f"제{i}조 " + " ".join(["사바아자 차카타"] * 12) + "을 준용한다." for i in range(1, 15)),
])
def test_cell_pieces_without_article_structure_keep_table_path(cell):
    chunks = _comparison(cell, "가나다라 " * 10)
    pieces = [c for c in chunks if c.get("column") == "원문"]
    assert len(pieces) >= 2
    assert all(c["heading_path"] == [] for c in pieces)
    assert all("section_path" not in c for c in chunks)


# ---- 쪽마다 되풀이되는 표 머리글이 문단으로 떨어진 청크 (#108)

def _rows_table(rows, page):
    return {"rows": rows, "header_rows": 1, "merges": [], "pages": [page], "row_pages": [page] * len(rows)}


def _item_rows(start, count):
    return [[str(n), f"품목{n}", " ".join(["규격 설명"] * 30) + f" {n}"] for n in range(start, start + count)]


def _paragraph(text, page, n):
    return {"id": f"p{n}", "type": "paragraph", "text": text, "page": page, "bbox": None, "level": None}


@pytest.mark.parametrize("header_lines", [
    ["NO.", "대상품목", "상세사양"],
    ["번호", "품목", "사양"],
], ids=["no-item-spec", "number-item-spec"])
def test_repeated_header_paragraph_chunk_is_dropped(header_lines):
    header = header_lines
    t1 = [header] + _item_rows(1, 5)
    t2 = [header] + _item_rows(6, 5)
    elements = [_element(t1), *[_paragraph(h, 2, i) for i, h in enumerate(header)], {**_element(t2), "page": 2}]
    chunks = chunk_elements(elements, document_id="d", tables=[[_rows_table(t1, 1)], [_rows_table(t2, 2)]], chunk_size=800)
    assert not any(c["element_types"] == ["paragraph"] for c in chunks)
    assert [c["chunk_id"] for c in chunks] == [f"d#{i}" for i in range(len(chunks))]
    assert sum(1 for c in chunks if c.get("row_id")) == 10       # 데이터 행은 그대로


@pytest.mark.parametrize("texts", [
    ["NO.", "대상품목"],                               # 열 이름 일부만 -- 머리글이 아니다
    ["대상품목", "NO.", "상세사양"],                    # 순서가 다르다
    ["NO.", "대상품목", "상세사양", "비고 사항"],         # 다른 줄이 더 있다
], ids=["partial", "reordered", "extra-line"])
def test_paragraphs_not_matching_header_are_kept(texts):
    header = ["NO.", "대상품목", "상세사양"]
    t1 = [header] + _item_rows(1, 5)
    elements = [_element(t1), *[_paragraph(t, 2, i) for i, t in enumerate(texts)]]
    chunks = chunk_elements(elements, document_id="d", tables=[[_rows_table(t1, 1)]], chunk_size=800)
    assert any(c["element_types"] == ["paragraph"] for c in chunks)


def test_piece_starting_with_several_short_articles_takes_the_first():
    """조각 첫머리에 짧은 조문이 잇달아 와도 경로는 조각이 여는 첫 조문이다. 다음 조각은 마지막으로 열린 조문을 잇는다."""
    from search_engine.chunking.table_rows import _cell_sections

    pieces = ["제50조의2(교육명령 등) 명령할 수 있다.\n第54條(罰則) 다음 각 호의 자는 처벌한다.\n1. 가나다라",
              "2. 수출허가를 받지 아니하고 수출한 자",
              "제2장 보칙\n제60조(과태료) 부과한다."]
    assert _cell_sections(pieces) == [["제50조의2(교육명령 등)"], ["第54條(罰則)"], ["제2장 보칙", "제60조(과태료)"]]


def test_caption_tie_break_is_stable_across_hash_seeds():
    """제목 행의 값 순서가 실행마다 같아야 한다 -- set 순서(실행마다 다른 해시)에 따르면 재생성할 때마다 제목이 바뀐다.
    값이 둘인 제목 행은 둘 다 남긴다(앞 칸부터, 특정화학물질 CAS 번호 유실 수정)."""
    import os
    import subprocess
    import sys

    code = ("from search_engine.chunking.table_rows import logical_tables;"
            "rows=[['주요 경력','주요 경력','이 력','이 력'],['가','나','다','라'],['마','바','사','아'],['자','차','카','타']];"
            "print(logical_tables({'rows':rows,'header_rows':0,'merges':[],'pages':[1]})[0].caption)")
    seen = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "PYTHONHASHSEED": str(seed), "PYTHONPATH": "src", "PYTHONIOENCODING": "utf-8"}).stdout.strip() for seed in range(8)}
    assert seen == {"주요 경력 이 력"}


def test_table_caption_becomes_path_when_no_heading_is_open():
    """문서 전체가 표 하나이고 표지가 표 첫 행(가로 병합)에 든 별표: 제목 원소가 없으니 표 제목이 행 청크의 경로가 된다."""
    caption = "[별표 9] 가상 면제대상(제5조 관련)"
    rows = [[caption] * 3, ["번호", "분류", "내용"]] + [[str(n), f"제{n}류", "가상 품목 설명 " * 8] for n in range(1, 12)]
    table = {"rows": rows, "header_rows": 0, "merges": [{"row": 0, "col": 0, "rowspan": 1, "colspan": 3}], "pages": [1]}
    chunks = chunk_elements([_element(rows)], document_id="d", tables=[[table]], chunk_size=800)
    assert chunks and all(c["heading_path"] == [caption] for c in chunks)

    # 열린 제목이 있으면 그 경로를 그대로 쓴다(표 제목은 본문 첫 줄 `표: …`로만)
    heading = {"id": "h", "type": "heading", "text": "제2장 가상", "page": 1, "bbox": None, "level": 1}
    chunks = chunk_elements([heading, _element(rows)], document_id="d", tables=[[table]], chunk_size=800)
    assert all(c["heading_path"] == ["제2장 가상"] for c in chunks if c.get("row_id"))


# ---- 빈 서식(입력란 표)은 행으로 나누지 않는다 (#110)

def _form_table(rows):
    return {"rows": rows, "header_rows": 0, "merges": [], "pages": [1]}


def test_comparison_row_chunks_carry_the_article_of_the_row():
    """행 하나 = 조문 한 쌍인 대비표: 행 청크마다 그 행의 조문이 경로에 붙는다(현행이 비면 개정안의 조문)."""
    rows = [["현 행", "개 정 안"]]
    for n in range(1, 9):
        body = " ".join(["가상 조문 내용"] * 12)
        rows.append([f"제{n}조(항목{n}) {body}" if n != 5 else "<신 설>", f"제{n}조(항목{n}) {body} 개정"])
    chunks = chunk_elements([_element(rows)], document_id="d", tables=[[_table(rows)]], chunk_size=800)
    by_row = [c for c in chunks if c.get("row_id")]
    assert len(by_row) == 8
    for n, chunk in enumerate(by_row, start=1):
        assert chunk["heading_path"][-1] == f"제{n}조(항목{n})"


# ---- 신·구조문 대비표 (#115): 조문 쌍 청크. 글자는 가상의 것이다.

from search_engine.chunking.table_rows import comparison_columns, same_as_current  # noqa: E402


@pytest.mark.parametrize("columns, expected", [
    (["현 행", "개 정 안"], (0, 1, None)),
    (["대외무역법시행령(현행)", "개 정 안", "비 고"], (0, 1, 2)),
    (["현행", "과기부․산자부 개정(안)", "개정 사유"], (0, 1, 2)),
    (["조항", "개정 전", "개정 후"], (1, 2, None)),
    (["현행", "개정", "개정사유"], (0, 1, 2)),
    (["번호", "품목", "규격"], None),                 # 대비표가 아니다
    (["구분", "개정 이유"], None),                    # 현행 열이 없다
], ids=["two-col", "law-name-col", "ministry-draft", "before-after", "short-revised", "not-comparison", "no-current"])
def test_comparison_columns(columns, expected):
    assert comparison_columns(columns) == expected


def test_same_as_current_marks_collapse_but_page_numbers_stay():
    assert same_as_current("① ------------- 제21조에 따른 - - - - - 허가") == "① … 제21조에 따른 … 허가"
    assert same_as_current("- 1 -") == "- 1 -"


def _articles(numbers, words=18, prefix=""):
    return "\n".join(f"{prefix}제{n}조(항목{n}) " + " ".join(["가상 조문 내용"] * words) + "을 정한다." for n in numbers)


def test_comparison_table_pairs_articles_across_one_big_cell():
    """칸 하나에 조문 여럿: 같은 조문의 현행·개정안이 한 청크, 신설 조문은 현행이 `<신설>`, 순서는 현행 순서 + 신설은 앞 조문 뒤."""
    current = _articles([1, 2, 4])
    revised = "\n".join([_articles([1]), _articles([2], prefix=""), "제3조(항목3) 가상 신설 조문.", _articles([4])])
    rows = [["현 행", "개 정 안"], [current, revised]]
    chunks = chunk_elements([_element(rows)], document_id="d", tables=[[_table(rows)]], chunk_size=800)
    pairs = [c for c in chunks if c.get("row_id")]
    assert [c["heading_path"][-1] for c in pairs] == ["제1조(항목1)", "제2조(항목2)", "제3조(항목3)", "제4조(항목4)"]
    new = pairs[2]["text"]
    assert "현 행:\n<신설>" in new and "개 정 안:\n제3조(항목3)" in new
    assert all("현 행:" in c["text"] and "개 정 안:" in c["text"] for c in pairs)


def test_comparison_rows_continuing_over_pages_are_rejoined_per_column():
    """쪽마다 한 행인 대비표: 현행 열은 앞 조문이 이어지고 개정안 열은 새 조문으로 시작해도 조문 경계가 맞는다."""
    rows = [["현행", "개정안"],
            [_articles([1], words=40) + "\n제2조(항목2) 가상 앞부분", _articles([1], words=40) + "\n제2조(항목2) 가상 개정 앞부분"],
            ["가상 뒷부분이 이어진다.\n" + _articles([3], words=40), "제3조(항목3) 가상 개정 전부."]]
    table = {"rows": rows, "header_rows": 1, "merges": [], "pages": [1, 2], "row_pages": [1, 1, 2]}
    chunks = chunk_elements([_element(rows)], document_id="d", tables=[[table]], chunk_size=800)
    by_article = {c["heading_path"][-1]: c["text"] for c in chunks if c.get("row_id")}
    assert "가상 뒷부분이 이어진다." in by_article["제2조(항목2)"]        # 쪽을 넘은 현행 글이 제2조에 붙는다
    assert "가상 뒷부분" not in by_article["제3조(항목3)"]


def test_reason_attached_only_when_row_has_one_pair():
    rows = [["현행", "개정안", "개정 사유"], [_articles([5]), _articles([5]), "가상 결의 반영"]] * 1
    rows = [rows[0]] + [[_articles([n]), _articles([n]), f"가상 사유 {n}"] for n in range(1, 8)]
    chunks = chunk_elements([_element(rows)], document_id="d", tables=[[_table(rows)]], chunk_size=800)
    pairs = [c for c in chunks if c.get("row_id")]
    assert all("개정 사유: 가상 사유" in c["text"] for c in pairs) and len(pairs) == 7


def test_placeholder_only_pair_is_carried_into_the_next_article():
    """조문 없는 짧은 쌍(법령명 줄, `<신설>`/`<삭제>`)은 혼자 청크가 되지 않고 다음 조문 쌍 앞에 붙는다(글자는 남는다)."""
    rows = [["현 행", "개 정 안"], ["가상법", "가상법"], ["<신 설>", "<삭제>"],
            [_articles([1], words=40), _articles([1], words=40)], [_articles([2], words=40), _articles([2], words=40)]]
    chunks = chunk_elements([_element(rows)], document_id="d", tables=[[_table(rows)]], chunk_size=800)
    pairs = [c for c in chunks if c.get("row_id")]
    assert all(len(c["text"]) >= 30 for c in pairs)
    assert "가상법" in pairs[0]["text"] and "<신 설>" in pairs[0]["text"] and pairs[0]["heading_path"][-1] == "제1조(항목1)"


@pytest.mark.parametrize("text", ["- 1 -", "- 12 -", "3 / 12", " - 2 / 9 - "])
def test_page_number_only_paragraph_is_not_a_chunk(text):
    body = {"id": "p", "type": "paragraph", "text": "가상 본문 문장입니다. " * 6, "page": 1, "bbox": None, "level": None}
    page_no = {"id": "n", "type": "paragraph", "text": text, "page": 1, "bbox": None, "level": None}
    chunks = chunk_elements([body, page_no], document_id="d")
    assert all(text.strip() not in c["text"] for c in chunks)


def test_keyed_comparison_rows_are_not_merged_and_keep_their_key():
    """행마다 통제번호가 다른 대비표(`통제기준 | 개정 전 | 개정 후`): 행이 곧 단위다 -- 이어 붙이지 않고 통제번호를 머리 줄로."""
    rows = [["통제기준", "개정 전", "개정 후"]] + [[f"{n}A00{n}", "<신규>", "가상 해석 기준 문장. " * 12] for n in range(1, 7)]
    chunks = chunk_elements([_element(rows)], document_id="d", tables=[[_table(rows)]], chunk_size=800)
    pairs = [c for c in chunks if c.get("row_id")]
    assert len(pairs) == 6
    assert [c["text"].splitlines()[0] for c in pairs] == [f"통제기준: {n}A00{n}" for n in range(1, 7)]
