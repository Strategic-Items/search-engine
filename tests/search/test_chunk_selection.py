"""문서의 어떤 청크가 전달되고, 어떤 청크가 선도하는가."""

from search_engine.search.query import _candidates_by_parent, _with_passages
from search_engine.search.results import SearchHit


def chunk(chunk_id, parent="p"):
    return {"_id": chunk_id, "_source": {"parent_id": parent, "body": f"본문 {chunk_id}"},
            "_score": 1.0}


def hit(chunk_id="lex1"):
    return SearchHit.model_validate(
        {"id": chunk_id, "parent_id": "p", "title": "제목", "body": f"본문 {chunk_id}"})


class TestCandidatesByParent:
    def test_the_dense_list_picks_the_leading_chunk(self):
        lexical = ([chunk("lex1"), chunk("lex2")], 1.0, "bm25")
        dense = ([chunk("vec1"), chunk("vec2")], 1.0, "vector")
        # 퓨전은 그들을 어휘 우선으로 넘긴다; 첫 청크는 밀집이 고른 것이고,
        # 나머지는 두 리스트의 순위를 합친 순서다(lex1은 어휘 1위라 vec2보다 앞선다)
        assert [c["_id"] for c in _candidates_by_parent([lexical, dense])["p"]] == [
            "vec1", "lex1", "vec2", "lex2"]

    def test_a_chunk_the_lexical_list_ranks_high_is_not_pushed_out_by_dense_order(self):
        # docs-v2-034: 정답 청크가 BM25 2위, 밀집 9위였다. 밀집 순서만 따르면 여섯 자리 밖이다.
        dense = ([chunk(f"vec{i}") for i in range(1, 9)] + [chunk("gold")], 1.0, "vector")
        lexical = ([chunk("lex1"), chunk("gold")], 1.0, "bm25")
        chosen = [c["_id"] for c in _candidates_by_parent([lexical, dense])["p"]][:6]
        assert chosen[0] == "vec1" and "gold" in chosen

    def test_the_rewrite_weight_scales_a_lists_vote(self):
        dense = ([chunk("vec1"), chunk("vec2")], 1.0, "vector")
        # 어휘 1위 청크 하나만 든 목록: 표가 1이면 vec2(밀집 2위)를 앞서고, 0.1이면 뒤에 선다
        heavy = ([chunk("only")], 1.0, "bm25")
        light = ([chunk("only")], 0.1, "bm25")
        assert [c["_id"] for c in _candidates_by_parent([dense, heavy])["p"]] == [
            "vec1", "only", "vec2"]
        assert [c["_id"] for c in _candidates_by_parent([dense, light])["p"]] == [
            "vec1", "vec2", "only"]

    def test_lexical_only_chunks_are_still_carried(self):
        dense = ([chunk("vec1")], 1.0, "vector")
        lexical = ([chunk("vec1"), chunk("lex1")], 1.0, "bm25")
        assert [c["_id"] for c in _candidates_by_parent([dense, lexical])["p"]] == [
            "vec1", "lex1"]

    def test_one_list_is_left_as_it_is(self):
        lexical = ([chunk("lex1"), chunk("lex2")], 1.0, "bm25")
        assert [c["_id"] for c in _candidates_by_parent([lexical])["p"]] == ["lex1", "lex2"]


class TestWithPassages:
    def test_the_leading_chunk_comes_from_the_pool_not_from_ranking(self):
        pool = {"p": [chunk("vec1"), chunk("vec2"), chunk("lex1")]}
        # ranking은 이 문서에 대해 lex1을 선택함; 밀집 풀은 vec1으로 선도함
        hits = _with_passages([hit("lex1")], pool, 3)
        assert hits[0].id == "vec1"
        assert hits[0].body == "본문 vec1"
        assert hits[0].chunk_ids == ["vec1", "vec2", "lex1"]

    def test_carries_at_most_chunks_per_document(self):
        pool = {"p": [chunk(f"c{i}") for i in range(10)]}
        assert len(_with_passages([hit("c0")], pool, 4)[0].chunk_ids) == 4

    def test_the_ranking_chunk_is_kept_when_no_list_carried_it(self):
        pool = {"p": [chunk("vec1")]}
        hits = _with_passages([hit("orphan")], pool, 3)
        assert "orphan" in hits[0].chunk_ids

    def test_one_chunk_per_document_leaves_the_hit_alone(self):
        pool = {"p": [chunk("vec1"), chunk("vec2")]}
        hits = _with_passages([hit("lex1")], pool, 1)
        assert hits[0].id == "lex1" and hits[0].passages == []

    def test_a_document_with_no_candidates_keeps_its_own_chunk(self):
        hits = _with_passages([hit("lex1")], {}, 6)
        assert hits[0].chunk_ids == ["lex1"]
