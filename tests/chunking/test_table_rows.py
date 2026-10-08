# 이식 원본: unstructured-doc-parser_ver2 tests/test_table_rows.py (def6caf). 파서의 직렬화·PDF 구조 추출을 검사하던 테스트는 뺐다.
"""큰 표를 행 단위 청크로 나누기(`chunking/structured.py`). 논리 표 자료는 `tabledata` 모양을 합성한다."""

from search_engine.chunking.structured import chunk_elements


def _table(rows, *, header_rows=1, pages=None, row_pages=None, merges=(), degraded=False):
    table = {"type": "table", "rows": rows, "header_rows": header_rows, "merges": list(merges),
             "pages": pages or [1]}
    if row_pages:
        table["row_pages"] = row_pages
    if degraded:
        table["degraded"] = True
    return table


def _elements(table_text, *, before=()):
    return [*before, {"type": "table", "text": table_text, "page": 1}]


ITEMS = [["순번", "품목명", "HS코드"]] + [[str(i), f"품목{i}", f"{130000 + i}"] for i in range(1, 41)]


def test_large_table_becomes_one_chunk_per_row_with_shared_table_id():
    table = _table(ITEMS, pages=[1, 2], row_pages=[1] * 21 + [2] * 20)
    chunks = chunk_elements(_elements("x" * 2000, before=[{"type": "heading", "text": "품목 목록", "level": 1, "page": 1}]),
                            document_id="doc", tables=[[table]])
    rows = [c for c in chunks if "row_id" in c]
    assert len(rows) == 40
    assert {c["table_id"] for c in rows} == {"doc#table0"}
    first, last = rows[0], rows[-1]
    assert first["text"] == "순번: 1\n품목명: 품목1\nHS코드: 130001"
    assert first["columns"] == ["순번", "품목명", "HS코드"]
    assert first["row_count"] == 40
    assert (first["row_index"], first["row_id"], first["values"]) == (0, "doc#table0#row0", ["1", "품목1", "130001"])
    assert (first["page_start"], last["page_start"], last["page_end"]) == (1, 2, 2)
    assert first["heading_path"] == ["품목 목록"]


def test_small_table_stays_whole_and_gets_table_metadata():
    table = _table([["구분", "값"], ["A", "1"], ["B", "2"]])
    chunks = chunk_elements(_elements("| 구분 | 값 |\n|---|---|\n| A | 1 |\n| B | 2 |"), document_id="doc", tables=[[table]])
    assert len(chunks) == 1
    assert chunks[0]["table_id"] == "doc#table0"
    assert chunks[0]["columns"] == ["구분", "값"] and chunks[0]["row_count"] == 2
    assert "row_id" not in chunks[0]


def test_without_tables_the_old_behaviour_is_kept():
    chunks = chunk_elements(_elements("x" * 2000), document_id="doc")
    assert len(chunks) == 1 and "table_id" not in chunks[0]


def test_undetected_plain_header_row_is_inferred():
    rows = [["구분", "직위명", "요건"]] + [[f"제{i}호", f"직위{i}", "근무경력 " * 30] for i in range(1, 5)]
    chunks = chunk_elements(_elements("x" * 2000), document_id="doc", tables=[[_table(rows, header_rows=0)]])
    assert chunks[0]["columns"] == ["구분", "직위명", "요건"]
    assert chunks[0]["row_count"] == 4


def test_data_like_first_row_is_not_taken_as_header():
    rows = [["1", "인삼 추출물", "130219"], ["2", "홍삼 추출물", "130219"], ["3", "콜라 추출물", "130219"]]
    chunks = chunk_elements(_elements("x" * 2000), document_id="doc", tables=[[_table(rows, header_rows=0)]])
    assert chunks[0]["columns"] == ["열1", "열2", "열3"]
    assert chunks[0]["row_count"] == 3


def test_two_line_header_with_vertical_merge_is_absorbed():
    rows = [["구분", "직위명", "요건"], ["구분", "직위명", "경력"]] + [[f"{i}호", f"직위{i}", "경력 " * 50] for i in range(3)]
    chunks = chunk_elements(_elements("x" * 2000), document_id="doc", tables=[[_table(rows, header_rows=0)]])
    assert chunks[0]["columns"] == ["구분", "직위명", "요건 경력"]
    assert chunks[0]["row_count"] == 3


def test_horizontal_merge_is_written_once_and_vertical_merge_repeats():
    rows = [["분류", "항목", "비고", "기타"],
            ["반도체", "장비", "전체 적용", "전체 적용"],
            ["반도체", "소재", "해당 없음", "x"],
            ["철강", "판재", "해당 없음", "y"]]
    merges = [{"row": 1, "col": 0, "rowspan": 2, "colspan": 1}, {"row": 1, "col": 2, "rowspan": 1, "colspan": 2}]
    chunks = chunk_elements(_elements("x" * 2000), document_id="doc", tables=[[_table(rows, merges=merges)]])
    assert chunks[0]["text"] == "분류: 반도체\n항목: 장비\n비고: 전체 적용"
    assert chunks[1]["text"].startswith("분류: 반도체\n항목: 소재")
    assert chunks[0]["values"] == ["반도체", "장비", "전체 적용", "전체 적용"]


def test_empty_rows_do_not_become_chunks():
    rows = [["a", "b"], ["1", "x"], ["", ""], ["2", "y"]]
    chunks = chunk_elements(_elements("x" * 2000), document_id="doc", tables=[[_table(rows)]])
    assert [c["row_index"] for c in chunks] == [0, 2]


def test_degraded_part_is_kept_as_plain_text():
    grid = _table(ITEMS)
    degraded = _table([["격자 없는 글자"]], header_rows=0, pages=[3], degraded=True)
    chunks = chunk_elements(_elements("x" * 2000), document_id="doc", tables=[[grid, degraded]])
    assert chunks[-1]["text"] == "격자 없는 글자"
    assert chunks[-1]["table_id"] == "doc#table1" and "row_id" not in chunks[-1]


def test_table_ids_stay_in_document_order():
    small = _table([["a", "b"], ["1", "2"], ["3", "4"]])
    big = _table(ITEMS)
    elements = [{"type": "table", "text": "| a | b |", "page": 1}, {"type": "table", "text": "x" * 2000, "page": 2}]
    chunks = chunk_elements(elements, document_id="doc", tables=[[small], [big]])
    assert chunks[0]["table_id"] == "doc#table0"
    assert {c["table_id"] for c in chunks[1:]} == {"doc#table1"}


# --- 표 제목 행 / 가로 병합 머리글 / 붙은 표 나누기 (table_rows.py) ----------------------------------------------

def _logical(rows, **kw):
    from search_engine.chunking.table_rows import logical_tables
    return logical_tables(_table(rows, header_rows=kw.pop("header_rows", 0), **kw))


def test_caption_row_is_split_off_and_prefixed_to_rows():
    """`<표 2> ...`가 가로 병합으로 격자 첫 행을 채운 경우(통상법률 논문 실측)."""
    rows = [["<표 2> 수출지역 그룹"] * 3, ["그룹", "대상국", "비고"], ["A", "미국", "화이트"], ["B", "한국", "변경"]]
    [lt] = _logical(rows)
    assert lt.caption == "<표 2> 수출지역 그룹"
    assert lt.columns == ["그룹", "대상국", "비고"] and len(lt.rows) == 2
    chunks = chunk_elements(_elements("x" * 2000), document_id="doc", tables=[[_table(rows, header_rows=0)]])
    assert chunks[0]["text"].startswith("표: <표 2> 수출지역 그룹\n그룹: A")
    assert chunks[0]["caption"] == "<표 2> 수출지역 그룹"


def test_single_fragment_first_row_is_a_caption():
    rows = [["", "", "수출규", ""], ["연도", "분기", "수량", "금액"], ["2019", "1", "10", "20"], ["2019", "2", "11", "21"]]
    [lt] = _logical(rows)
    assert lt.caption == "수출규" and lt.columns == ["연도", "분기", "수량", "금액"]


def test_horizontally_merged_header_is_recognised():
    """`특례 | 특례 | 등급 | 등급`처럼 병합 칸이 채워진 머리글(SW 수출통제 안내서 실측)."""
    rows = [["구분", "특례", "특례", "등급", "등급"], ["구분", "특례", "특례", "A", "AA"],
            ["중소", "O", "X", "1", "2"], ["대기업", "X", "O", "3", "4"]]
    [lt] = _logical(rows)
    assert lt.columns == ["구분", "특례", "특례", "등급 A", "등급 AA"]
    assert len(lt.rows) == 2


def test_two_line_header_with_blank_upper_cell():
    rows = [["연도", "분기", "한국", "", "세계", ""], ["연도", "분기", "수량(톤)", "금액", "수량(톤)", "금액"],
            ["2019", "1", "10,082", "2,083", "11,196", "2,423"], ["2019", "2", "8,436", "1,778", "9,648", "2,104"]]
    [lt] = _logical(rows)
    assert lt.columns == ["연도", "분기", "한국 수량(톤)", "금액", "세계 수량(톤)", "금액"]


def test_data_row_with_numbers_is_not_a_caption():
    rows = [["합계", "합계", "합계", "100"], ["a", "b", "c", "d"], ["1", "2", "3", "4"], ["5", "6", "7", "8"]]
    # 제목처럼 생긴 합계 행은 알려진 한계 -- 다만 값은 잃지 않는다(값이 둘인 제목 행은 둘 다 남긴다, 특정화학물질 CAS 번호 유실)
    assert _logical(rows)[0].caption == "합계 100"
    rows = [["100", "100", "100", "x"], ["a", "b", "c", "d"], ["1", "2", "3", "4"]]
    assert _logical(rows)[0].caption == ""


def test_data_row_sharing_one_value_with_the_header_is_not_absorbed():
    """코드리뷰(CodeRabbit): 윗줄과 한 칸만 같은 데이터 행을 하위 머리글로 흡수하면 그 행 청크가 빠진다."""
    rows = [["분류", "항목", "비고"], ["분류", "장비", "전체 적용"], ["철강", "판재", "해당 없음"], ["철강", "봉강", "x"]]
    [lt] = _logical(rows)  # merges 없음: 두 칸 이상 같아야 머리글
    assert lt.columns == ["분류", "항목", "비고"] and len(lt.rows) == 3


def test_with_merge_info_only_a_real_vertical_merge_extends_the_header():
    rows = [["분류", "항목", "비고"], ["분류", "항목", "세부"], ["철강", "판재", "x"], ["철강", "봉강", "y"]]
    header_merge = [{"row": 0, "col": 0, "rowspan": 2, "colspan": 1}, {"row": 0, "col": 1, "rowspan": 2, "colspan": 1}]
    [lt] = _logical(rows, merges=header_merge)
    assert lt.columns == ["분류", "항목", "비고 세부"] and len(lt.rows) == 2

    # 병합 정보가 있는데 윗줄 머리글에서 이어진 세로 병합이 없으면, 값이 두 칸 같아도 데이터로 둔다.
    data_merge = [{"row": 2, "col": 0, "rowspan": 2, "colspan": 1}]
    [lt] = _logical(rows, merges=data_merge)
    assert lt.columns == ["분류", "항목", "비고"] and len(lt.rows) == 3


def test_long_single_cell_first_row_is_not_a_caption():
    """도표 글자가 통째로 칸 하나에 든 첫 행을 제목으로 삼으면 모든 행 청크 본문에 복제된다(KIEP 보고서 34쪽 실측)."""
    rows = [["도표 글자 " * 30, "", ""], ["a", "b", "c"], ["1", "2", "3"], ["4", "5", "6"]]
    assert _logical(rows)[0].caption == ""
