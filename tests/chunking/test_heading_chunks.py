# 이식 원본: unstructured-doc-parser_ver2 tests/test_heading_chunks.py (def6caf). 파서의 직렬화·PDF 구조 추출을 검사하던 테스트는 뺐다.
"""청킹 원칙: 제목은 단독 청크가 되지 않고 이어지는 본문과 묶이며, 제목 정보는 지우지 않는다(`chunking/structured.py`).

특정 문서가 아니라 "제목 뒤에 무엇이 오는가"의 모양(하위 제목, 긴 문단, 큰 표, 글자 없는 그림, 문서 끝)마다 같은 원칙이
지켜지는지 본다. 원소 글자는 가상의 것이다.
"""

import pytest

from search_engine.chunking.structured import chunk_elements


def _h(text, level=1):
    return {"id": text, "type": "heading", "text": text, "page": 1, "bbox": None, "level": level}


def _p(text, kind="paragraph"):
    return {"id": text[:20], "type": kind, "text": text, "page": 1, "bbox": None, "level": None}


def _heading_only(chunk):
    return all(line.startswith("#") for line in chunk["text"].splitlines() if line.strip())


# 제목 뒤에 바로 하위 제목이 오는 여러 모양: 장->조, 부록 표지->서식 제목, 부칙->조, 번호 절->번호 소절, 3단 연속
CHAINS = [
    [_h("제1장 가나다", 1), _h("제1조(목적)", 2)],
    [_h("[별지 제3호 서식]", 1), _h("라마바 신청서", 2)],
    [_h("부 칙", 1), _h("제1조(시행일)", 2)],
    [_h("1. 사업 개요", 1), _h("가. 추진 배경", 2)],
    [_h("제1편 총칙", 1), _h("제1장 통칙", 2), _h("제1조(목적)", 3)],
]


@pytest.mark.parametrize("chain", CHAINS)
def test_heading_chain_joins_the_first_body_and_keeps_every_title(chain):
    body = _p("이 기준은 가나다의 운영에 필요한 사항을 정한다.")
    chunks = chunk_elements([*chain, body, _h("다음 절", 1), _p("다음 본문이다.")], document_id="d")
    first = chunks[0]
    assert not any(_heading_only(c) for c in chunks)
    for heading in chain:                       # 제목 글자는 지우지 않고 본문 앞에 남는다
        assert heading["text"] in first["text"]
    assert body["text"] in first["text"]
    assert first["heading_path"][-1] == chain[-1]["text"]  # 경로는 가장 깊은 제목까지


@pytest.mark.parametrize("chain", CHAINS)
def test_heading_before_an_oversized_paragraph_stays_with_its_first_piece(chain):
    long_text = " ".join(["가나다라마바사아자차카타파하 문장이다."] * 80)
    chunks = chunk_elements([*chain, _p(long_text)], document_id="d", chunk_size=300, chunk_overlap=0)
    assert len(chunks) > 1
    assert not any(_heading_only(c) for c in chunks)
    assert chunks[0]["text"].startswith("#") and long_text[:20] in chunks[0]["text"]


@pytest.mark.parametrize("filler", [
    {"type": "image", "text": "", "page": 1, "bbox": None, "level": None, "id": "img"},   # OCR 없는 그림
    {"type": "table", "text": "", "page": 1, "bbox": None, "level": None, "id": "tbl"},   # 빈 표
])
def test_element_without_indexable_text_is_not_a_body(filler):
    chunks = chunk_elements([_h("가. 절차"), filler, _p("신청서를 낸다.")], document_id="d")
    assert not any(_heading_only(c) for c in chunks)
    assert any("가. 절차" in c["text"] and "신청서를 낸다." in c["text"] for c in chunks)


def test_heading_with_its_own_body_still_starts_a_new_chunk():
    chunks = chunk_elements([_h("제1조(목적)", 2), _p("이 기준은 가나다의 운영에 필요한 목적을 정한다."), _h("제2조(정의)", 2), _p("이 기준에서 쓰는 용어의 뜻은 다음과 같이 정한다.")],
                            document_id="d")
    assert [c["heading_path"][-1] for c in chunks] == ["제1조(목적)", "제2조(정의)"]


def test_small_heading_chain_before_a_body_does_not_split_on_size():
    chunks = chunk_elements([_h("제1장 가나다"), _h("제1조(목적)", 2), _p("가" * 790)], document_id="d", chunk_size=800)
    assert not any(_heading_only(c) for c in chunks)


def test_long_front_matter_stays_its_own_chunk():
    long_intro = "가상 개정 이유 문장이 길게 이어진다. " * 10  # 150자 초과
    chunks = chunk_elements([_p(long_intro), _h("1. 배경"), _p("가상 배경 문장이 여기에 들어간다. 일관성 있는 작성을 유도한다.")],
                            document_id="d")
    assert len(chunks) == 2 and chunks[0]["heading_path"] == []
