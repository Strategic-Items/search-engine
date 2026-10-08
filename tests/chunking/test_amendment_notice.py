# 이식 원본: unstructured-doc-parser_ver2 tests/test_amendment_notice.py (def6caf). 파서의 직렬화·PDF 구조 추출을 검사하던 테스트는 뺐다.
"""개정고시안 구조(2026-10-07): 앞 개정 이유 목록 / 발령 머리 줄 / 신설 조문 / 개정 지시문 / 별지 서식 / 대비표.

실측: `전략물자수출입고시 일부개정고시_최종.pdf`에서 "라. 기타" 항목 아래로 고시 본문·서식·대비표가 전부 매달렸고, 개정 지시문이
앞 신설 조문(`제18조의3`) 경로를 가졌으며, 표지 뒤 영문 꼬리가 붙은 별지 표지를 못 알아봤고, 서식 표가 행 청크로 쪼개졌다.
"""

from search_engine.chunking.structured import chunk_elements
from search_engine.chunking import patterns


def test_part_boundary_lines():
    for text in ("[별지 제2호 서식]", "[별지 제2호의2 서식] Annexed paper No. 2-2", "산업통상부고시 제 2026-101 호",
                 "국방부훈령 제3031호", "신ㆍ구조문대비표"):
        assert patterns.part_boundary_line(text), text
    for text in ("[별표 1] 이 표는 다음과 같이 적용한다.", "지식경제부 고시 제2011-276호에 따라 개정한다.",
                 "신·구조문대비표를 참고하여 의견을 제출하시기 바랍니다."):
        assert not patterns.part_boundary_line(text), text
    assert patterns.annex_label_head("[별지 제2호의2 서식] Annexed paper No. 2-2") == "[별지 제2호의2 서식] Annexed paper No. 2-2"
    assert patterns.annex_label_head("[별표 1] 이 표는 다음과 같이 적용한다.") is None  # 표지 뒤 본문 문장


def test_amendment_instruction():
    for text in ("제20조제1항제4호를 제3호로 하고, 같은 항 제5호를 삭제한다.", "별표 22 제2호를 다음과 같이 한다.",
                 "별지 제3호서식을 삭제한다.", "제54조의2제2항 중 “1항부터 제3항”을 “제1항”으로 한다.", "별표 1을 별첨과 같이 한다."):
        assert patterns.AMENDMENT_INSTRUCTION.match(text), text
    for text in ("제5조에 따른 신청은 서면으로 한다.", "제2조(정의) 이 규정에서 사용하는 용어는 다음과 같이 한다."):
        assert not patterns.AMENDMENT_INSTRUCTION.match(text), text


def _p(text, kind="paragraph", page=1):
    return {"type": kind, "text": text, "page": page}


def _notice():
    return [
        _p("1. 개정이유 가상 고시의 신청서류를 합리화하여 수출자 편의를 높인다.", "list_item"),
        _p("라. 기 타 : 신․구조문대비표", "list_item"),
        _p("산업통상부고시 제 2026-101 호", page=2),
        _p("가상 고시 일부를 다음과 같이 개정한다.", page=2),
        {"type": "heading", "text": "제18조의3(수출자의 의무)", "level": 1, "page": 2},
        _p("① 수출자는 가상 물품을 수출하기 전에 거래관련자의 신원을 반드시 확인하여야 한다.", "list_item", page=2),
        _p("제20조제1항제4호를 제3호로 하고, 같은 항 제5호를 삭제한다.", page=2),
        _p("별표 22 제2호를 다음과 같이 한다. 별지 제3호서식을 삭제한다.", page=3),
        _p("[별지 제2호의2 서식] Annexed paper No. 2-2", page=5),
        _p("가상 서식의 안내 문장이 여기에 들어간다. 서식 칸은 신청인이 채운다.", page=5),
    ]


def test_notice_paths_close_lists_articles_and_open_forms():
    chunks = chunk_elements(_notice(), document_id="d")
    by_text = {c["text"].split("\n")[0][:12]: c["heading_path"] for c in chunks}
    article = next(c for c in chunks if "제18조의3" in c["text"])
    assert article["heading_path"] == ["산업통상부고시 제 2026-101 호", "제18조의3(수출자의 의무)"]
    form = next(c for c in chunks if "가상 서식" in c["text"])
    assert form["heading_path"] == ["[별지 제2호의2 서식] Annexed paper No. 2-2"]  # 영문 꼬리가 붙은 표지
    assert not any(c["text"].strip() == "[별지 제2호의2 서식] Annexed paper No. 2-2" for c in chunks)  # 표지만 든 청크 없음


def test_instructions_inside_an_amending_article_stay_in_it():
    # 부칙 `제4조(다른 법률의 개정)`은 조문 내용 자체가 다른 법률을 고치는 지시문이다 -- 지시문이 나와도 조문을 닫지 않는다
    chunks = chunk_elements([
        _p("부칙 <제13459호, 2015.8.11.>"),
        {"type": "heading", "text": "제4조(다른 법률의 개정)", "level": 1, "page": 1},
        _p("① 가상 법률 일부를 다음과 같이 개정한다.", "list_item"),
        _p("제118조제4항 본문 중 “가상 법률 이름”을 “새 가상 법률 이름”으로 한다."),
    ], document_id="d")
    assert chunks[-1]["heading_path"] == ["부칙 <제13459호, 2015.8.11.>", "제4조(다른 법률의 개정)"]
    assert patterns.closes_article("제18조의3(수출자의 의무)") and not patterns.closes_article("제4조(다른 법률의 개정)")


def test_law_center_annex_header_line_is_a_label():
    # 국가법령정보센터 별표 파일 머리 줄: `■` 때문에 목록 항목으로 들어오고 법령명이 대괄호 앞에 있다
    assert patterns.annex_label_head("■ 대외무역법 시행령 [별표 2] <개정 2014.1.28>") == "대외무역법 시행령 [별표 2]"
    assert patterns.annex_label_head("자세한 내용은 [별표 1] 참조") is None  # 본문 속 별표 언급
    rows = [["위반행위의 종류와 과징금의 금액(제60조제1항 관련)"] * 3, ["위반행위", "근거 법조문", "과징금 금액"]]
    rows += [[f"{k}. 가상 위반행위 문장 " * 4, "법 제33조의2제2항", f"가상 금액 {k} " * 6] for k in range(1, 6)]
    table = {"type": "table", "rows": rows, "header_rows": 0, "merges": [], "pages": [1], "row_pages": [1] * len(rows)}
    chunks = chunk_elements([_p("■ 대외무역법 시행령 [별표 2] <개정 2014.1.28>", "list_item"),
                             {"type": "table", "text": "x" * 2000, "page": 1}], document_id="d", tables=[[table]])
    assert all(c["heading_path"] == ["대외무역법 시행령 [별표 2]", "위반행위의 종류와 과징금의 금액(제60조제1항 관련)"] for c in chunks)
    assert sum("<개정 2014.1.28>" in c["text"] for c in chunks) == 1  # 머리 줄 글자는 첫 행 앞에 남는다


def test_bulleted_issuance_line_and_inserted_items_in_a_notice():
    # `◉ 산업통상자원부고시 제2021-202호`(기호 때문에 목록 항목)도 발령 머리 줄이고, 지시문이 신설하는 번호 항목이 제목으로
    # 올라가도 다음 지시문에서 닫힌다
    assert patterns.issuance_label("◉ 산업통상자원부고시 제2021-202호") == "산업통상자원부고시 제2021-202호"
    chunks = chunk_elements([
        _p("◉ 산업통상자원부고시 제2021-202호", "list_item"),
        _p("가상 고시 일부를 다음과 같이 개정한다. 제49조제1항에 제5호 및 제6호를 각각 다음과 같이 신설한다."),
        {"type": "heading", "text": "5. 해산물(가상 설명)", "level": 1, "page": 1},
        {"type": "heading", "text": "6. 섬유(가상 설명)", "level": 1, "page": 1},
        _p("제49조의2의 제목 “수입 허가절차”를 “수출입 허가절차”로 한다. 같은 조 제1항 중 “수입”을 “수출입”으로 한다."),
    ], document_id="d")
    assert all(c["heading_path"][:1] == ["산업통상자원부고시 제2021-202호"] for c in chunks)
