from datetime import date
import logging
from unittest.mock import Mock, patch

import httpx
import pytest

from search_engine.config import Settings

from search_engine.search import (
    GUIDE_TYPES,
    SOURCE_TYPE_WEIGHT,
    build_query,
    retrieve,
    search_all,
    search_modes,
)


def matching_query(query: dict) -> dict:
    """The matching half of a query, whatever score functions wrap it."""
    return query.get("function_score", {}).get("query", query)


def boosts(query: dict, key: str) -> list[dict]:
    """Score functions whose filter mentions key, e.g. "range" or "source_type"."""
    functions = query.get("function_score", {}).get("functions", [])
    return [f for f in functions if key in str(f["filter"])]


def test_query_keeps_unknown_dates_and_filters_expired_documents():
    query = build_query("수출허가", date(2026, 9, 15))
    filters = matching_query(query)["bool"]["filter"]
    assert filters[0]["bool"]["should"][0]["range"]["effective_from"]["lte"] == "2026-09-15"
    assert filters[1]["bool"]["should"][0]["range"]["effective_to"]["gt"] == "2026-09-15"
    assert filters[0]["bool"]["should"][1]["bool"]["must_not"]["exists"]["field"] == "effective_from"


def test_retrieve_returns_unique_parent_documents():
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "chunk-1", "_score": 8.0, "_source": {"parent_id": "doc-1", "title": "A"}},
        {"_id": "chunk-2", "_score": 7.0, "_source": {"parent_id": "doc-1", "title": "A"}},
        {"_id": "doc-2", "_score": 6.0, "_source": {"title": "B"}},
    ]}}
    hits = retrieve(client, "search-documents", "수출허가", date.today(), 2, cutoff_ratio=0)
    assert [hit.parent_id for hit in hits] == ["doc-1", "doc-2"]
    assert client.search.call_args.kwargs["size"] == 10


def test_explicit_year_month_boosts_matching_publication_and_effective_dates():
    query = build_query("2026년 9월 개정 고시", date(2026, 9, 15))
    assert matching_query(query)["bool"]["minimum_should_match"] == 1
    assert boosts(query, "range")[0]["filter"]["range"]["published_at"] == {
        "gte": "2026-09-01", "lt": "2026-10-01",
    }


def test_a_whole_year_and_an_impossible_month_are_read_correctly():
    whole_year = build_query("2026년 개정", date(2026, 9, 15))
    assert boosts(whole_year, "range")[0]["filter"]["range"]["published_at"] == {
        "gte": "2026-01-01", "lt": "2027-01-01",
    }
    assert boosts(build_query("2026년 13월 개정", date(2026, 9, 15)), "range") == []


def test_search_all_adds_hsk_linkage_only_when_the_query_names_a_code():
    client = Mock()
    client.search.return_value = {"hits": {"hits": []}}
    assert search_all(client, "search-documents", "search-hsk", "허가", date.today()).hsk is None

    client.search.side_effect = [
        {"hits": {"hits": []}},
        {"hits": {"total": {"value": 1}, "hits": [
            {"_id": "hsk-1", "_source": {"hsk_code": "2826902000"}},
        ]}},
    ]
    result = search_all(client, "search-documents", "search-hsk", "HSK 2826-9020-00", date.today())
    assert result.hsk.hits[0].hsk_code == "2826902000"
    assert [call.kwargs["index"] for call in client.search.call_args_list[-2:]] == [
        "search-documents", "search-hsk",
    ]


def test_a_query_that_asks_for_a_procedure_lifts_the_guides():
    query = build_query("전문판정 신청은 어떤 절차로 진행되나요", date(2026, 9, 15))
    guides = boosts(query, "source_type")[0]
    assert guides["filter"]["terms"]["source_type"] == list(GUIDE_TYPES)
    assert guides["weight"] == SOURCE_TYPE_WEIGHT


def test_a_query_that_names_a_form_lifts_the_forms():
    query = build_query("최종사용자 서약서 양식 내려받기", date(2026, 9, 15))
    assert boosts(query, "source_type")[0]["filter"]["terms"]["source_type"] == ["민원서식"]


def test_the_word_in_a_notice_title_does_not_lift_the_guides():
    """`안내` is how notices title themselves, so it must not read as a guide."""
    query = build_query("제38차 전략물자 수출입고시 9월 1일 시행 안내", date(2026, 9, 15))
    assert boosts(query, "source_type") == []


def test_a_plain_query_carries_only_the_current_edition_boost():
    query = build_query("수출허가", date(2026, 9, 15))
    assert boosts(query, "range") == []
    assert boosts(query, "source_type") == []
    assert len(query["function_score"]["functions"]) == 1


def test_document_kind_and_period_boosts_apply_together():
    query = build_query("2026년 9월 개정 전문판정 신청서 양식", date(2026, 9, 15))
    assert boosts(query, "source_type")[0]["filter"]["terms"]["source_type"] == ["민원서식"]
    assert [f["filter"]["range"] for f in boosts(query, "range")] == [
        {"published_at": {"gte": "2026-09-01", "lt": "2026-10-01"}},
        {"effective_from": {"gte": "2026-09-01", "lt": "2026-10-01"}},
    ]


def test_boosting_never_removes_a_document_from_the_result_set():
    """Boosts reorder what matched; they must not become filters."""
    query = build_query("전문판정 절차", date(2026, 9, 15))
    assert query["function_score"]["boost_mode"] == "sum"
    matching = matching_query(query)["bool"]
    assert matching["minimum_should_match"] == 1
    assert "source_type" not in str(matching["filter"])


def test_an_index_dropping_out_of_a_search_is_reported(monkeypatch, caplog):
    """A failed shard still returns 200, so the only signal is a log line."""
    client = Mock()
    client.search.return_value = {
        "_shards": {"total": 2, "successful": 1, "failed": 1, "failures": [
            {"index": "search-documents-v1",
             "reason": {"reason": "Field 'embedding' is not knn_vector type."}},
        ]},
        "hits": {"hits": []},
    }
    embedder = Mock()
    embedder.embed_query.return_value = [0.1] * 768

    with caplog.at_level(logging.WARNING):
        retrieve(client, "search-documents,search-docs", "허가", date(2026, 9, 16), 5, embedder, cutoff_ratio=0)

    assert "search-documents-v1" in caplog.text
    assert "not knn_vector type" in caplog.text


def test_a_document_carries_its_other_matching_chunks():
    """The chunk that ranks a document is rarely the chunk that answers the question."""
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "c1", "_score": 8.0, "_source": {"parent_id": "doc-1", "body": "one"}},
        {"_id": "c2", "_score": 7.0, "_source": {"parent_id": "doc-1", "body": "two"}},
        {"_id": "c3", "_score": 6.0, "_source": {"parent_id": "doc-1", "body": "three"}},
        {"_id": "c9", "_score": 5.0, "_source": {"parent_id": "doc-2", "body": "other"}},
    ]}}
    hits = retrieve(client, "search-documents", "수출허가", date.today(), 2,
                    chunks_per_document=3, cutoff_ratio=0)
    assert [hit.parent_id for hit in hits] == ["doc-1", "doc-2"]
    assert hits[0].chunk_ids == ["c1", "c2", "c3"]
    assert hits[0].bodies == ["one", "two", "three"]
    assert hits[1].chunk_ids == ["c9"]


def test_one_chunk_per_document_keeps_the_single_chunk_shape():
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "c1", "_score": 8.0, "_source": {"parent_id": "doc-1", "body": "one"}},
        {"_id": "c2", "_score": 7.0, "_source": {"parent_id": "doc-1", "body": "two"}},
    ]}}
    hits = retrieve(client, "search-documents", "수출허가", date.today(), 2,
                    chunks_per_document=1, cutoff_ratio=0)
    assert [hit.chunk_ids for hit in hits] == [["c1"]]
    assert hits[0].passages == []


def test_extra_chunks_never_displace_another_document():
    """Passages ride along with their document; they do not consume a result slot."""
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "c1", "_score": 9.0, "_source": {"parent_id": "doc-1", "body": "a"}},
        {"_id": "c2", "_score": 8.0, "_source": {"parent_id": "doc-1", "body": "b"}},
        {"_id": "c3", "_score": 7.0, "_source": {"parent_id": "doc-1", "body": "c"}},
        {"_id": "c4", "_score": 6.0, "_source": {"parent_id": "doc-2", "body": "d"}},
        {"_id": "c5", "_score": 5.0, "_source": {"parent_id": "doc-3", "body": "e"}},
    ]}}
    hits = retrieve(client, "search-documents", "수출허가", date.today(), 3,
                    chunks_per_document=4, cutoff_ratio=0)
    assert [hit.parent_id for hit in hits] == ["doc-1", "doc-2", "doc-3"]


def lexical_hits(*pairs: tuple[str, str]) -> dict:
    return {"hits": {"hits": [
        {"_id": cid, "_score": 9.0 - i, "_source": {"parent_id": pid, "body": cid}}
        for i, (cid, pid) in enumerate(pairs)
    ]}}


def test_a_rewrite_is_searched_alongside_the_question_not_instead_of_it(monkeypatch):
    monkeypatch.setattr("search_engine.search.query.rewrite_query",
                        lambda query: "수출자 서약서 폐지")
    client = Mock()
    client.search.side_effect = [
        lexical_hits(("c1", "doc-1")),
        lexical_hits(("c2", "doc-2")),
    ]
    hits = retrieve(client, "search-documents", "업체의 약속 문서", date.today(), 5,
                    mode="bm25", query_rewrite=True, chunks_per_document=1, cutoff_ratio=0)
    searched = [call.kwargs["body"]["query"] for call in client.search.call_args_list]
    assert "업체의 약속 문서" in str(searched[0])
    assert "수출자 서약서 폐지" in str(searched[1])
    assert {hit.parent_id for hit in hits} == {"doc-1", "doc-2"}


def test_the_original_query_outranks_the_rewrite_at_the_same_rank(monkeypatch):
    """A rewrite that went wrong may add a document; it may not displace the answer."""
    monkeypatch.setattr("search_engine.search.query.rewrite_query", lambda query: "엉뚱한 말")
    client = Mock()
    client.search.side_effect = [
        lexical_hits(("c1", "doc-original")),
        lexical_hits(("c2", "doc-rewrite")),
    ]
    hits = retrieve(client, "search-documents", "질문", date.today(), 5,
                    mode="bm25", query_rewrite=True, chunks_per_document=1, cutoff_ratio=0)
    assert [hit.parent_id for hit in hits] == ["doc-original", "doc-rewrite"]


def test_a_rewrite_outage_narrows_the_search_instead_of_failing_it(monkeypatch, caplog):
    def refuse(query):
        raise httpx.ConnectError("no ollama")
    monkeypatch.setattr("search_engine.search.query.rewrite_query", refuse)
    client = Mock()
    client.search.return_value = lexical_hits(("c1", "doc-1"))
    with caplog.at_level(logging.WARNING):
        hits = retrieve(client, "search-documents", "질문", date.today(), 5,
                        mode="bm25", query_rewrite=True, chunks_per_document=1, cutoff_ratio=0)
    assert [hit.parent_id for hit in hits] == ["doc-1"]
    assert "query rewrite unavailable" in caplog.text


def test_an_evaluation_run_refuses_to_measure_without_the_rewrite(monkeypatch):
    def refuse(query):
        raise httpx.ConnectError("no ollama")
    monkeypatch.setattr("search_engine.search.query.rewrite_query", refuse)
    client = Mock()
    client.search.return_value = lexical_hits(("c1", "doc-1"))
    with pytest.raises(httpx.HTTPError):
        retrieve(client, "search-documents", "질문", date.today(), 5,
                 mode="bm25", query_rewrite=True, strict=True, cutoff_ratio=0)


def test_an_unbounded_bm25_score_is_reported_as_the_retriever_gave_it():
    """Scores stay on the retriever's own scale; nothing rescales them."""
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "c1", "_score": 15.0, "_source": {"parent_id": "doc-1"}},
        {"_id": "c2", "_score": 900.0, "_source": {"parent_id": "doc-2"}},
    ]}}
    hits = retrieve(client, "search-documents", "질문", date.today(), 5, mode="bm25", cutoff_ratio=0)
    assert [hit.score for hit in hits] == [15.0, 900.0]


def test_a_replacement_edition_is_offered_without_a_score_it_never_earned():
    client = Mock()
    client.search.side_effect = [
        {"hits": {"hits": [
            {"_id": "old", "_score": 9.0,
             "_source": {"parent_id": "doc-old", "superseded_by": "doc-new"}},
        ]}},
        {"hits": {"hits": [
            {"_id": "new", "_score": 1.0, "_source": {"parent_id": "doc-new"}},
        ]}},
    ]
    hits = retrieve(client, "search-documents", "질문", date.today(), 5, mode="bm25", cutoff_ratio=0)
    assert [hit.parent_id for hit in hits] == ["doc-old", "doc-new"]
    assert hits[0].score == 9.0
    assert hits[1].score is None


def test_comparing_modes_embeds_the_question_once(monkeypatch):
    """Two modes disagreeing must mean the mode differed, not the vector."""
    calls = []

    def embed(text):
        calls.append(text)
        return [0.1, 0.2]

    monkeypatch.setattr("search_engine.search.query.OllamaEmbedder",
                        lambda settings: Mock(embed_query=embed))
    client = Mock()
    client.search.return_value = lexical_hits(("c1", "doc-1"))
    comparison = search_modes(client, "search-documents", "질문", date.today(), 5)
    assert [mode.mode for mode in comparison.modes] == ["bm25", "vector", "hybrid"]
    assert calls == ["질문"]


def test_a_dead_retriever_reports_itself_without_blanking_the_comparison(monkeypatch):
    """The one thing a comparison must never do is hide which mode broke."""
    def refuse(text):
        raise httpx.ConnectError("no ollama")

    monkeypatch.setattr("search_engine.search.query.OllamaEmbedder",
                        lambda settings: Mock(embed_query=refuse))
    client = Mock()
    client.search.return_value = lexical_hits(("c1", "doc-1"))
    comparison = search_modes(client, "search-documents", "질문", date.today(), 5)
    by_mode = {mode.mode: mode for mode in comparison.modes}
    assert [hit.parent_id for hit in by_mode["bm25"].hits] == ["doc-1"]
    assert "ConnectError" in by_mode["vector"].error
    assert by_mode["vector"].hits == []
    # Hybrid keeps its lexical half rather than failing with the embedder.
    assert [hit.parent_id for hit in by_mode["hybrid"].hits] == ["doc-1"]


def test_a_hit_far_behind_the_best_is_not_offered():
    """Ten results padded out with near misses is what the cutoff exists to stop."""
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "c1", "_score": 20.0, "_source": {"parent_id": "doc-1"}},
        {"_id": "c2", "_score": 19.0, "_source": {"parent_id": "doc-2"}},
        {"_id": "c3", "_score": 4.0, "_source": {"parent_id": "doc-3"}},
    ]}}
    hits = retrieve(client, "search-documents", "질문", date.today(), 5,
                    mode="bm25", cutoff_ratio=0.9)
    assert [hit.parent_id for hit in hits] == ["doc-1", "doc-2"]


def test_the_best_hit_survives_any_cutoff():
    """A score says which document fits best, never whether any document answers,
    so the cutoff trims the tail and never empties the list."""
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "c1", "_score": 0.01, "_source": {"parent_id": "doc-1"}},
        {"_id": "c2", "_score": 0.009, "_source": {"parent_id": "doc-2"}},
    ]}}
    hits = retrieve(client, "search-documents", "질문", date.today(), 5,
                    mode="bm25", cutoff_ratio=1.0)
    assert [hit.parent_id for hit in hits] == ["doc-1"]


def test_the_cutoff_reads_each_mode_on_its_own_scale():
    """A BM25 20.0 and an RRF 0.03 are both "the best there is"; the ratio is
    what lets one threshold mean the same thing in either."""
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "c1", "_score": 0.0328, "_source": {"parent_id": "doc-1"}},
        {"_id": "c2", "_score": 0.0320, "_source": {"parent_id": "doc-2"}},
        {"_id": "c3", "_score": 0.0160, "_source": {"parent_id": "doc-3"}},
    ]}}
    hits = retrieve(client, "search-documents", "질문", date.today(), 5,
                    mode="bm25", cutoff_ratio=0.95)
    assert [hit.parent_id for hit in hits] == ["doc-1", "doc-2"]


def test_an_absolute_floor_can_empty_the_list():
    """What the ratio cannot do: say that nothing found answers the question.

    The ratio measures every hit against the best hit, so the best hit is its
    own reference and always survives. Only a floor on the raw score can
    return nothing.
    """
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "c1", "_score": 0.01, "_source": {"parent_id": "doc-1"}},
    ]}}
    kept = retrieve(client, "search-documents", "질문", date.today(), 5,
                    mode="bm25", cutoff_ratio=1.0, score_floor=0.0)
    assert [hit.parent_id for hit in kept] == ["doc-1"]

    emptied = retrieve(client, "search-documents", "질문", date.today(), 5,
                       mode="bm25", cutoff_ratio=1.0, score_floor=0.5)
    assert emptied == []


def test_the_floor_gates_each_retriever_before_fusion():
    """RRF scores are ranks, so a floor has to run before the lists are fused.

    The lexical hit scores under the floor and the vector hit over it, so only
    the vector document may reach the fused ranking.
    """
    client = Mock()
    client.search.side_effect = [
        {"hits": {"hits": [{"_id": "lex", "_score": 1.0, "_source": {"parent_id": "doc-lex"}}]}},
        {"hits": {"hits": [{"_id": "vec", "_score": 0.9, "_source": {"parent_id": "doc-vec"}}]}},
    ]
    embedder = Mock()
    embedder.embed_query.return_value = [0.1, 0.2]
    with patch("search_engine.search.query.get_settings", lambda: Settings(
        search_score_floor_bm25=5.0, search_score_floor_vector=0.5,
    )):
        hits = retrieve(client, "search-documents", "질문", date.today(), 5,
                        mode="hybrid", embedder=embedder)
    assert [hit.parent_id for hit in hits] == ["doc-vec"]


def test_a_document_only_the_dense_retriever_found_can_still_be_returned():
    """The ratio cutoff used to make the hybrid a vote rather than a ranking.

    An RRF score is a sum of `1/(k+rank)` terms, so a document both lists
    found opens at twice the score of one only a single list found: with k=60,
    `2/61` against `1/61`. Measured as a ratio against the best hit that is
    0.5, and the hybrid ratio was 0.95 -- so whenever the leading document was
    in both lists, which was 132 of docs v2's 135 questions, nothing either
    retriever found alone could survive. Three questions lost their answer
    this way with the dense retriever holding it at rank 1.
    """
    client = Mock()
    client.search.side_effect = [
        {"hits": {"hits": [
            {"_id": "l1", "_score": 20.0, "_source": {"parent_id": "doc-both"}},
        ]}},
        {"hits": {"hits": [
            {"_id": "v1", "_score": 0.90, "_source": {"parent_id": "doc-dense-only"}},
            {"_id": "v2", "_score": 0.89, "_source": {"parent_id": "doc-both"}},
        ]}},
    ]
    embedder = Mock()
    embedder.embed_query.return_value = [0.1, 0.2]
    with patch("search_engine.search.query.get_settings", lambda: Settings(
        search_score_floor_bm25=0.0, search_score_floor_vector=0.0,
    )):
        hits = retrieve(client, "search-documents", "질문", date.today(), 5,
                        mode="hybrid", embedder=embedder)
    # doc-both leads the lexical list and is second in the dense one, so it
    # scores 1/61 + 1/62 against doc-dense-only's 1/61: a ratio of 0.497.
    assert [hit.parent_id for hit in hits] == ["doc-both", "doc-dense-only"]


def test_fusion_ties_are_broken_on_the_dense_order_not_the_chunk_id():
    """Two documents each ranked first in a different list score identically.

    Ties are the normal case after the lists are trimmed, not an edge case, so
    what breaks them decides P@1. Here the chunk ids would put the lexical
    document first; the dense order is what the pipeline trusts.
    """
    client = Mock()
    client.search.side_effect = [
        {"hits": {"hits": [
            {"_id": "aaa", "_score": 20.0, "_source": {"parent_id": "doc-lexical"}},
        ]}},
        {"hits": {"hits": [
            {"_id": "zzz", "_score": 0.90, "_source": {"parent_id": "doc-dense"}},
        ]}},
    ]
    embedder = Mock()
    embedder.embed_query.return_value = [0.1, 0.2]
    with patch("search_engine.search.query.get_settings", lambda: Settings(
        search_score_floor_bm25=0.0, search_score_floor_vector=0.0,
    )):
        hits = retrieve(client, "search-documents", "질문", date.today(), 5,
                        mode="hybrid", embedder=embedder)
    assert [hit.parent_id for hit in hits] == ["doc-dense", "doc-lexical"]


def test_trimming_for_fusion_leaves_the_passage_pool_whole():
    """The trim decides what votes, not what a returned document may carry.

    The candidates a document's passages are chosen from are the same lists
    the fusion reads, so trimming them in place would take chunks away from
    documents that do get returned -- the pool stage 20 depends on.
    """
    client = Mock()
    client.search.side_effect = [
        {"hits": {"hits": [
            {"_id": "l1", "_score": 20.0, "_source": {"parent_id": "doc-1", "body": "a"}},
            {"_id": "l2", "_score": 2.0, "_source": {"parent_id": "doc-1", "body": "b"}},
        ]}},
        {"hits": {"hits": [
            {"_id": "v1", "_score": 0.90, "_source": {"parent_id": "doc-1", "body": "c"}},
            {"_id": "v2", "_score": 0.40, "_source": {"parent_id": "doc-1", "body": "d"}},
        ]}},
    ]
    embedder = Mock()
    embedder.embed_query.return_value = [0.1, 0.2]
    with patch("search_engine.search.query.get_settings", lambda: Settings(
        search_score_floor_bm25=0.0, search_score_floor_vector=0.0,
    )):
        hits = retrieve(client, "search-documents", "질문", date.today(), 5,
                        mode="hybrid", embedder=embedder, chunks_per_document=4,
                        rerank_chunks=False)
    # l2 and v2 are both well under their retriever's trim and neither voted.
    assert sorted(hits[0].chunk_ids) == ["l1", "l2", "v1", "v2"]
