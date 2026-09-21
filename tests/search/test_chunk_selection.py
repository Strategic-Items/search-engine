"""Which chunks of a document get carried, and which one leads."""

from search_engine.search.query import _candidates_by_parent, _with_passages
from search_engine.search.results import SearchHit


def chunk(chunk_id, parent="p"):
    return {"_id": chunk_id, "_source": {"parent_id": parent, "body": f"본문 {chunk_id}"},
            "_score": 1.0}


def hit(chunk_id="lex1"):
    return SearchHit.model_validate(
        {"id": chunk_id, "parent_id": "p", "title": "제목", "body": f"본문 {chunk_id}"})


class TestCandidatesByParent:
    def test_the_dense_list_orders_the_chunks(self):
        lexical = ([chunk("lex1"), chunk("lex2")], 1.0, "bm25")
        dense = ([chunk("vec1"), chunk("vec2")], 1.0, "vector")
        # fusion hands them over lexical-first; the dense order is the one kept
        assert [c["_id"] for c in _candidates_by_parent([lexical, dense])["p"]] == [
            "vec1", "vec2", "lex1", "lex2"]

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
        # ranking picked lex1 for this document; the dense pool leads with vec1
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
