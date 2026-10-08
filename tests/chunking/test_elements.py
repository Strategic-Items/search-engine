from search_engine.chunking.elements import markdown_to_elements

_SAMPLE = """<!-- page: 1 -->

# 제1장 총칙

## 제1조(목적)

이 고시는 전략물자의
수출입을 정한다.

<!-- page: 2 -->

| 구분 | 내용 |
|---|---|
| 가 | 나 |

![image](<assets/img-abc.png>)

<!-- image: file not saved -->
"""


def kinds(parsed):
    return [(e["type"], e["page"]) for e in parsed.elements]


def test_headings_keep_level_and_pages_follow_markers():
    parsed = markdown_to_elements(_SAMPLE)
    assert parsed.has_pages
    assert [(e["type"], e.get("level"), e["page"]) for e in parsed.elements[:3]] == [
        ("heading", 1, 1), ("heading", 2, 1), ("paragraph", None, 1)]
    assert parsed.elements[0]["text"] == "제1장 총칙"
    assert parsed.elements[2]["text"] == "이 고시는 전략물자의\n수출입을 정한다."


def test_pipe_table_and_images():
    parsed = markdown_to_elements(_SAMPLE)
    assert kinds(parsed)[3:] == [("table", 2), ("image", 2), ("image", 2)]
    assert parsed.elements[3]["text"].startswith("| 구분 |")
    assert parsed.elements[4]["path"] == "assets/img-abc.png"
    assert "path" not in parsed.elements[5]


def test_html_table_with_blank_line_inside_stays_one_element():
    parsed = markdown_to_elements('문단\n\n<table>\n<tr><td rowspan="2" colspan="1">a</td></tr>\n\n<tr><td>b</td></tr>\n</table>\n\n끝')
    assert [e["type"] for e in parsed.elements] == ["paragraph", "table", "paragraph"]
    assert "</table>" in parsed.elements[1]["text"]
    assert not parsed.has_pages


def test_multi_page_table_parts_merge_but_same_page_tables_do_not():
    parts = "<!-- page: 3 -->\n| a | b |\n|---|---|\n| 1 | 2 |\n\n<!-- page: 4 -->\n| a | b |\n|---|---|\n| 3 | 4 |"
    parsed = markdown_to_elements(f"<!-- page: 3 -->\n\n{parts}")
    assert [e["type"] for e in parsed.elements] == ["table"]
    assert parsed.elements[0]["page"] == 3

    twin = "<!-- page: 3 -->\n| a | b |\n|---|---|\n| 1 | 2 |\n\n<!-- page: 3 -->\n| c | d |\n|---|---|\n| 3 | 4 |"
    assert [e["type"] for e in markdown_to_elements(twin).elements] == ["table", "table"]


def test_page_marker_between_tables_separates_them():
    md = ("<!-- page: 3 -->\n| a | b |\n|---|---|\n| 1 | 2 |\n\n<!-- page: 4 -->\n\n"
          "<!-- page: 4 -->\n| c | d |\n|---|---|\n| 3 | 4 |")
    assert [e["type"] for e in markdown_to_elements(md).elements] == ["table", "table"]


def test_placeholders():
    parsed = markdown_to_elements("![page 2 image](#page-2)\n\n[표 셀 텍스트 없음]\n\n<!-- table content unavailable -->")
    assert [e["type"] for e in parsed.elements] == ["image", "paragraph", "table"]
