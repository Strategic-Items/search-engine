from pathlib import Path

from search_engine.indexing.mapping import HSK_INDEX_BODY, index_body
from search_engine.indexing.synonyms import load_synonyms


def test_a_group_becomes_one_rule(tmp_path: Path):
    path = tmp_path / "synonyms.txt"
    path.write_text("# 주석\n캐치올, 상황허가\n\n  \nEL , 수출허가서\n", encoding="utf-8")
    assert load_synonyms(path) == ["캐치올, 상황허가", "EL, 수출허가서"]


def test_a_line_with_one_term_is_not_a_rule(tmp_path: Path):
    path = tmp_path / "synonyms.txt"
    path.write_text("외톨이\n캐치올, 상황허가  # 꼬리 주석\n", encoding="utf-8")
    assert load_synonyms(path) == ["캐치올, 상황허가"]


def test_the_shipped_dictionary_loads():
    rules = load_synonyms()
    assert len(rules) > 10
    assert all("," in rule for rule in rules)


def test_synonyms_expand_before_the_part_of_speech_filter():
    """그 필터는 토큰을 제거하고, 동의어 그래프는 그 간격을 넘을 수 없다."""
    analyzer = index_body(8)["settings"]["analysis"]["analyzer"]["korean_nori_search"]
    assert analyzer["filter"].index("domain_synonyms") < \
        analyzer["filter"].index("korean_pos")


def test_only_the_body_expands_synonyms():
    """제목은 문자 그대로 유지되어 문서 이름을 지정할 때도 정확히 일치하게 한다."""
    properties = index_body(8)["mappings"]["properties"]
    assert properties["body"]["search_analyzer"] == "korean_nori_search"
    assert "search_analyzer" not in properties["title"]


def test_auxiliary_verbs_and_copulas_are_dropped():
    """대화형 종결은 검색어를 남겨서는 안 된다.

    "알려줘"는 알리(VV) + 어(EC) + 주(VX) + 어(EC)로 토크나이즈된다. Lucene의 기본 스톱태그는 종결어미를 제거하지만 주는 유지한다. 이는 "주 :"로 시작하는 표 노트의 머리글과 일치하게 되는데, 제목에서 이는 매우 드물기 때문에 모든 내용 단어에 대한 실제 일치보다 높은 점수를 얻고, 일치한 문서들에 대한 비율 컷오프를 높인다.
    """
    for body in (index_body(8), HSK_INDEX_BODY):
        stoptags = body["settings"]["analysis"]["filter"]["korean_pos"]["stoptags"]
        assert {"VX", "VCP", "VCN"} <= set(stoptags)
        assert "VV" not in stoptags, "content verbs still carry the topic"
