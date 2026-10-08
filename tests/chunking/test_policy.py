"""검색엔진이 소유한 청킹 정책(`ChunkPolicy`)과 청크 제목(K4). 기본값은 파서가 쓰던 값이라 바꾸면 이 테스트가 알린다."""

from search_engine.chunking.params import DEFAULT_POLICY, ChunkPolicy
from search_engine.chunking.postprocess import chunk_title, section_label
from search_engine.chunking.structured import chunk_elements


def test_defaults_are_the_values_the_parser_used():
    assert (DEFAULT_POLICY.chunk_size, DEFAULT_POLICY.chunk_overlap, DEFAULT_POLICY.min_chunk_chars) == (800, 100, 30)
    assert (DEFAULT_POLICY.question_min, DEFAULT_POLICY.question_max_chars, DEFAULT_POLICY.question_path_chars) == (3, 300, 80)
    assert (DEFAULT_POLICY.row_key_max_chars, DEFAULT_POLICY.long_cell_chars) == (40, 400)
    assert (DEFAULT_POLICY.pair_oversize_ratio, DEFAULT_POLICY.carry_max_chars, DEFAULT_POLICY.heading_max_chars) == (1.5, 40, 60)


def _p(text):
    return {"type": "paragraph", "text": text, "page": 1}


def test_chunk_size_comes_from_the_policy_and_explicit_arguments_override_it():
    elements = [_p("가나다 " * 60), _p("라마바 " * 60)]
    default = chunk_elements(elements, document_id="d")
    small = chunk_elements(elements, document_id="d", policy=ChunkPolicy(chunk_size=200, chunk_overlap=20))
    override = chunk_elements(elements, document_id="d", chunk_size=200, chunk_overlap=20)
    assert len(small) > len(default)
    assert [c["text"] for c in small] == [c["text"] for c in override]


def test_question_min_decides_whether_a_document_is_question_and_answer():
    elements = [_p("처음 질문인가요?"), _p("답이다."), _p("둘째 질문인가요?"), _p("답이다.")]
    assert chunk_elements(elements, document_id="d")[0]["heading_path"] == []
    qa = chunk_elements(elements, document_id="d", policy=ChunkPolicy(question_min=2))
    assert [c["heading_path"] for c in qa] == [["처음 질문인가요?"], ["둘째 질문인가요?"]]


def test_section_label_keeps_the_article_number_and_parenthesised_title_only():
    assert section_label("**제8조(정의)** 이 영에서 사용하는 용어의 뜻은 다음과 같다.") == "제8조(정의)"
    assert section_label("제5조의2 본문이 이어진다") == "제5조의2"
    assert section_label("## 가" * 40).endswith("…")


def test_chunk_title_skips_a_label_the_document_title_already_has():
    assert chunk_title("전략물자수출입고시", "제8조(정의)") == "전략물자수출입고시 — 제8조(정의)"
    assert chunk_title("[별표 4] 통제번호의 분류", "통제번호의 분류") == "[별표 4] 통제번호의 분류"
    assert chunk_title("문서", "") == "문서"
