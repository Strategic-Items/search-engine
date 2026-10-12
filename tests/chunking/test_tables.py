from search_engine.chunking.tables import clean_cell, element_tables, table_objects


def test_pipe_table_round_trips_with_escapes():
    text = "<!-- page: 2 -->\n| 구분 | 내용 |\n|---|---|\n| a\\|b | c |\n| 1 | 2 |"
    [table] = table_objects(text, 2, hard_breaks=False)
    assert table["rows"] == [["구분", "내용"], ["a|b", "c"], ["1", "2"]]
    assert table["pages"] == [2] and "row_pages" not in table and "hard_breaks" not in table


def test_html_table_keeps_merges_and_fills_merged_cells():
    html = ('<table>\n<tr><td rowspan="2" colspan="1">분류</td><td rowspan="1" colspan="1">갑</td></tr>\n'
            '<tr><td rowspan="1" colspan="1">을</td></tr>\n</table>')
    [table] = table_objects(html, 1, hard_breaks=True)
    assert table["rows"] == [["분류", "갑"], ["분류", "을"]]
    assert table["merges"] == [{"row": 0, "col": 0, "rowspan": 2, "colspan": 1}]
    assert table["hard_breaks"] is True


def test_hwp_cells_keep_paragraph_breaks_exactly():
    html = '<table>\n<tr><td rowspan="1" colspan="2">[별표]<br><br>제목</td></tr>\n</table>'
    [table] = table_objects(html, 1, hard_breaks=True)
    assert table["rows"][0][0] == "[별표]\n\n제목"


def test_multi_page_parts_with_same_columns_join_with_row_pages():
    text = ("<!-- page: 3 -->\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
            "<!-- page: 4 -->\n| a | b |\n|---|---|\n| 3 | 4 |")
    [table] = table_objects(text, 3, hard_breaks=False)
    assert len(table["rows"]) == 4 and table["pages"] == [3, 4]
    assert table["row_pages"] == [3, 3, 4, 4]


def test_parts_with_different_columns_stay_separate():
    text = "<!-- page: 3 -->\n| a | b |\n|---|---|\n| 1 | 2 |\n\n<!-- page: 4 -->\n| a |\n|---|\n| 3 |"
    assert len(table_objects(text, 3, hard_breaks=False)) == 2


def test_clean_cell_keeps_list_lines_and_joins_wrapped_ones():
    assert clean_cell("가 나\n다 라\n1. 항목\n2. 항목") == "가 나 다 라\n1. 항목\n2. 항목"
    assert clean_cell("현\n행") == "현행"
    assert element_tables([{"type": "table", "text": "", "page": 1}], hard_breaks=False) == [[]]


def test_pdf_continuation_recovers_real_header_across_body_paragraphs():
    elements = [
        {"type": "table", "page": 1, "text": "| 코드 | 국문 | 영문 |\n|---|---|---|\n| ML1 | 첫 품목 | First item |\n| ML2 | 둘째 품목 | Second item |"},
        {"type": "paragraph", "page": 2, "text": "표 밖으로 추출된 이어지는 긴 기술 설명입니다. " * 10},
        {"type": "table", "page": 2, "text": "| ML3 | 셋째 품목 | Third item |\n|---|---|---|\n| ML4 | 넷째 품목 | Fourth item |"},
        {"type": "table", "page": 3, "text": "| ML5 | 다섯째 품목 | Fifth item |\n|---|---|---|\n| ML6 | 여섯째 품목 | Sixth item |"},
    ]
    tables = element_tables(elements, hard_breaks=False)
    assert tables[1][0]["column_names"] == ["코드", "국문", "영문"]
    assert tables[2][0]["column_names"] == ["코드", "국문", "영문"]
    assert tables[1][0]["rows"][0] == ["ML3", "셋째 품목", "Third item"]


def test_pdf_new_section_cannot_inherit_unrelated_header():
    elements = [
        {"type": "table", "page": 1, "text": "| 코드 | 내용 |\n|---|---|\n| 1 | 첫 항목 |\n| 2 | 둘째 항목 |"},
        {"type": "heading", "page": 2, "level": 1, "text": "다른 별표"},
        {"type": "table", "page": 2, "text": "| 100 | 금액 |\n|---|---|\n| 200 | 금액 |"},
    ]
    tables = element_tables(elements, hard_breaks=False)
    assert "column_names" not in tables[1][0]
    assert "column_names" not in element_tables([elements[0], elements[2]], hard_breaks=True)[1][0]


def test_explicit_html_header_is_preserved_even_with_long_column_title():
    from search_engine.chunking.table_rows import logical_tables
    title = "장비의 세부 기술적 특성과 적용 요건을 설명하는 긴 열 제목"
    html = f'<table><tr><th>구분</th><th>{title}</th></tr><tr><td>A</td><td>설비</td></tr></table>'
    [table] = table_objects(html, 1, hard_breaks=True)
    [logical] = logical_tables(table)
    assert logical.columns == ["구분", title]
    assert logical.rows == [["A", "설비"]]


def test_column_names_are_not_carried_across_a_page_gap_or_a_same_page_table():
    first = {"type": "table", "page": 1, "text": "| Field A | Field B |\n|---|---|\n| 1 | 100 |\n| 2 | 200 |"}
    for page in [1, 3]:
        second = {"type": "table", "page": page, "text": "| 10 | 300 |\n|---|---|\n| 20 | 400 |"}
        assert "column_names" not in element_tables([first, second], hard_breaks=False)[1][0]


def test_column_names_are_not_assigned_to_a_different_width():
    first = {"type": "table", "page": 1, "text": "| Field A | Field B |\n|---|---|\n| 1 | 100 |\n| 2 | 200 |"}
    second = {"type": "table", "page": 2, "text": "| 10 | 300 | 400 |\n|---|---|---|\n| 20 | 500 | 600 |"}
    assert "column_names" not in element_tables([first, second], hard_breaks=False)[1][0]
