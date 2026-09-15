from pathlib import Path

from search_engine.mapping import INDEX_BODY
from search_engine.synonyms import load_synonyms


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
    analyzer = INDEX_BODY["settings"]["analysis"]["analyzer"]["korean_nori_search"]
    assert analyzer["filter"].index("domain_synonyms") < \
        analyzer["filter"].index("nori_part_of_speech")


def test_only_the_body_expands_synonyms():
    """Titles stay literal so that naming a document still matches it exactly."""
    properties = INDEX_BODY["mappings"]["properties"]
    assert properties["body"]["search_analyzer"] == "korean_nori_search"
    assert "search_analyzer" not in properties["title"]
