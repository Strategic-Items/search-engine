# 이식 원본: unstructured-doc-parser_ver2 tests/test_table_feedback.py (def6caf). 파서의 직렬화·PDF 구조 추출을 검사하던 테스트는 뺐다.
"""표 구조 보존: 단위, 다단 머리글, 제목 칸에 붙은 데이터 줄, 칸 안 줄바꿈(Markdown), 표 앞 짧은 줄.

검색 담당 피드백(2026-10-07)에서 나온 테스트 가운데 표 구조를 지키는 것만 남겼다. 특정 문서 증상을 고치던 규칙(목록형 표의
구역 추적, 앞 행 키 물려받기, 표 첫 행 본문 분리, 행 청크의 ` / ` 줄 구분)은 2026-10-08에 걷어냈다(`chunking/CHUNKING_RULES.md`).
"""

from search_engine.chunking.structured import chunk_elements
from search_engine.chunking.table_rows import logical_tables, row_chunks


def _table(rows, merges=()):
    return {"rows": rows, "header_rows": 0, "merges": list(merges), "pages": [1], "row_pages": [1] * len(rows)}


def test_unit_and_two_row_header_below_title_rows():
    # 법령 머리 줄 -> 표 제목(끝에 단위) -> 2단 머리글 -> 데이터
    rows = [["■ 가상 시행령 [별표]"] * 5, ["과태료의 부과기준(제23조 관련) (단위: 만원)"] * 5,
            ["위반행위", "근거 법조문", "과태료 금액", "과태료 금액", "과태료 금액"],
            ["위반행위", "근거 법조문", "1차 위반", "2차 위반", "3차 이상 위반"],
            ["가. 가상 위반", "법 제24조제1항제1호", "1,000", "1,500", "3,000"],
            ["나. 가상 위반", "법 제24조제1항제2호", "1,500", "2,000", "3,000"]]
    merges = [{"row": r, "col": 0, "rowspan": 1, "colspan": 5} for r in range(2)] + [
        {"row": 2, "col": 0, "rowspan": 2, "colspan": 1}, {"row": 2, "col": 1, "rowspan": 2, "colspan": 1},
        {"row": 2, "col": 2, "rowspan": 1, "colspan": 3}]
    [lt] = logical_tables(_table(rows, merges))
    assert lt.unit == "만원" and len(lt.rows) == 2
    assert lt.columns == ["위반행위", "근거 법조문", "과태료 금액 1차 위반", "과태료 금액 2차 위반", "과태료 금액 3차 이상 위반"]
    text = row_chunks(lt, "t")[0]["text"]
    assert "단위: 만원" in text and "과태료 금액 1차 위반: 1,000" in text


def test_data_line_stuck_to_the_caption_cell_stays_data_and_no_value_is_lost():
    # 제목 칸에 첫 데이터 줄이 붙어 있으면 제목 줄만 제목으로 쓴다. 표의 값은 어느 것도 사라지지 않는다.
    rows = [["■ 가상 법률 [별표]"] * 4, ["가상 물질(제2조 관련)\n1. 1종화학물질"] * 4,
            ["가. 독성화학물질", "(등록번호)", "(등록번호)", "(등록번호)"],
            ["예) 가상A: 설명", "예) 가상A: 설명", "(107-44-8)\n(96-64-0)", "(107-44-8)\n(96-64-0)"],
            ["1) 가상B: 설명", "1) 가상B: 설명", "(78-53-5)", "(78-53-5)"]]
    [lt] = logical_tables(_table(rows))
    assert lt.caption.startswith("■ 가상 법률 [별표]") and "1종" not in lt.caption
    text = "\n".join(c["text"] for c in row_chunks(lt, "t"))
    for value in ("1. 1종화학물질", "가. 독성화학물질", "107-44-8", "96-64-0", "78-53-5"):
        assert value in text


def test_short_line_before_a_row_split_table_is_not_lost():
    # 행으로 나누는 표는 앞 제목을 본문에 두지 않는다. 제목이 아닌 짧은 줄은 첫 행 본문 앞에 남는다(글자를 잃지 않는다).
    rows = [["통제번호", "해석"]] + [[f"1A00{k}", f"가상 해석 문장 {k} " * 15] for k in range(6)]
    table = {**_table(rows), "header_rows": 1}
    elements = [{"type": "paragraph", "text": "가상 표 앞 한 줄", "page": 1}, {"type": "table", "text": "x" * 2000, "page": 1}]
    chunks = chunk_elements(elements, document_id="doc", tables=[[table]])
    assert sum("가상 표 앞 한 줄" in c["text"] for c in chunks) == 1
    assert chunks[0]["text"].startswith("가상 표 앞 한 줄\n통제번호: 1A000")
    assert len([c for c in chunks if c.get("row_id")]) == 6
