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
