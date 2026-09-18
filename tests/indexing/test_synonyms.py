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
    """That filter drops tokens, and a synonym graph cannot span the gap."""
    analyzer = index_body(8)["settings"]["analysis"]["analyzer"]["korean_nori_search"]
    assert analyzer["filter"].index("domain_synonyms") < \
        analyzer["filter"].index("korean_pos")


def test_only_the_body_expands_synonyms():
    """Titles stay literal so that naming a document still matches it exactly."""
    properties = index_body(8)["mappings"]["properties"]
    assert properties["body"]["search_analyzer"] == "korean_nori_search"
    assert "search_analyzer" not in properties["title"]


def test_auxiliary_verbs_and_copulas_are_dropped():
    """A conversational ending must not leave a search term behind.

    "알려줘" tokenizes to 알리(VV) + 어(EC) + 주(VX) + 어(EC). Lucene's default
    stoptags drop the endings but keep 주, which then matches the "주 :" that
    heads a table note -- rare enough in titles to outscore a real match on
    every content word, and to lift the ratio cutoff over the documents that
    did match.
    """
    for body in (index_body(8), HSK_INDEX_BODY):
        stoptags = body["settings"]["analysis"]["filter"]["korean_pos"]["stoptags"]
        assert {"VX", "VCP", "VCN"} <= set(stoptags)
        assert "VV" not in stoptags, "content verbs still carry the topic"
