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
    """쿼리의 매칭 부분, 어떤 점수 함수가 감싸든 상관없이."""
    return query.get("function_score", {}).get("query", query)


def boosts(query: dict, key: str) -> list[dict]:
    """필터에 key를 언급하는 점수 함수, 예: "range" 또는 "source_type"."""
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
    """공고 제목에도 `안내`가 쓰이므로 이를 안내서로 해석하면 안 된다."""
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
        {"period_hint": {"gte": "2026-09-01", "lt": "2026-10-01"}},
    ]


def test_period_hint_is_boosted_below_a_known_publication_date():
    """힌트는 추정이므로 아는 날짜를 덮어써서는 안 된다."""
    query = build_query("2026년 9월 고시", date(2026, 9, 15))
    weights = {next(iter(f["filter"]["range"])): f["weight"] for f in boosts(query, "range")}
    assert weights["period_hint"] < weights["published_at"]


def test_boosting_never_removes_a_document_from_the_result_set():
    """매칭된 결과를 재정렬하는 데 부스트를 적용함; 필터가 되어서는 안 됨."""
    query = build_query("전문판정 절차", date(2026, 9, 15))
    assert query["function_score"]["boost_mode"] == "sum"
    matching = matching_query(query)["bool"]
    assert matching["minimum_should_match"] == 1
    assert "source_type" not in str(matching["filter"])


def test_an_index_dropping_out_of_a_search_is_reported(monkeypatch, caplog):
    """실패한 샤드도 200을 반환하므로, 유일한 신호는 로그 라인뿐임."""
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
    """문서를 순위 매기는 청크는 질문에 답하는 청크가 되기 드물다."""
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
    """패스aggio는 문서와 함께 이동함; 결과 슬롯을 소비하지 않음."""
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
    """잘못된 재작성은 문서를 추가할 수 있음; 답을 대체할 수는 없음."""
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
    """점수는 검색기 자체의 척도를 유지하며, 아무런 재스케일링도 수행하지 않는다."""
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
    """두 모드가 불일치하면 모드가 달랐음을 의미하며, 벡터가 달랐음을 의미하지 않는다."""
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
    """비교가 절대 해서는 안 되는 한 가지는 어느 모드가 깨졌는지를 숨기는 것이다."""
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
    # 하이브리드는 임베더와 함께 실패하기보다는 자신의 어휘적 부분을 유지한다.
    assert [hit.parent_id for hit in by_mode["hybrid"].hits] == ["doc-1"]


def test_a_hit_far_behind_the_best_is_not_offered():
    """가까운 실패로 채워진 10개의 결과는 컷오프가 막아야 하는 것이다."""
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
    """점수는 어떤 문서가 가장 잘 맞는지를 말하며, 어떤 문서도 답변을 제공하는지를 말하지 않는다.
    따라서 컷오프는 꼬리를 잘라내지만 리스트를 비우지는 않는다."""
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "c1", "_score": 0.01, "_source": {"parent_id": "doc-1"}},
        {"_id": "c2", "_score": 0.009, "_source": {"parent_id": "doc-2"}},
    ]}}
    hits = retrieve(client, "search-documents", "질문", date.today(), 5,
                    mode="bm25", cutoff_ratio=1.0)
    assert [hit.parent_id for hit in hits] == ["doc-1"]


def test_the_cutoff_reads_each_mode_on_its_own_scale():
    """BM25 20.0과 RRF 0.03은 모두 '가장 좋은 것'이다; 비율은 하나의 임계값이 둘 다에서 같은 의미를 갖게 해준다."""
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
    """비율이 할 수 없는 일: 찾은 것이 아무것도 질문에 답변하지 않는다고 말하는 것이다.

    비율은 모든 히트를 최고 히트와 비교하여 측정하므로, 최고 히트는 자신의 기준이 되며 항상 살아남는다.
    원시 점수에 바닥선이 있어야만 아무것도 반환하지 않을 수 있다."""
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
    """RRF 점수는 순위이므로, 리스트를 융합하기 전에 바닥값(floor) 계산이 먼저 수행되어야 한다.

    어휘적 히트 점수는 바닥값 아래에 있고, 벡터 히트는 그 위에 있으므로, 융합된 순위에 도달할 수 있는 것은 벡터 문서뿐이다.
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
    """하이브리드를 순위가 아닌 투표로 만드는 데 사용되는 비율 cutoff.

    RRF 점수는 `1/(k+rank)` 항들의 합으로 구성되므로, 두 리스트 모두에서 발견된 문서는 단 하나의 리스트에서만 발견된 문서보다 점수가 두 배 높다: k=60일 때, `2/61` 대 `1/61`이다. 최고 히트에 대한 비율로 측정하면 0.5이며, 하이브리드 비율은 0.95였다. 따라서 리더링 문서가 두 리스트 모두에 포함된 경우, 즉 v2의 135개 질문 중 132개의 경우, 어느 하나의 리트리버만 발견한 문서는 살아남을 수 없었다. 3개의 질문에서 답이 손실되었으며, 이 경우 딥 리트리버가 순위 1에 있었다.
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
    # doc-both는 어휘 리스트에서 1위이고 딥 리스트에서 2위이므로, 이
    # 점수는 doc-dense-only의 1/61 대비 1/61 + 1/62: 비율은 0.497이다.
    assert [hit.parent_id for hit in hits] == ["doc-both", "doc-dense-only"]


def test_fusion_ties_are_broken_on_the_dense_order_not_the_chunk_id():
    """각각 다른 리스트에서 1위로 순위 매겨진 두 문서는 동일한 점수를 얻는다.

    리스트를 자른 후에는 타이가 정상적인 경우이며, 특수한 경우가 아니므로, 이를 어떻게 깨는지가 P@1을 결정한다. 여기서는 청크 ID가 어휘 문서를 먼저 배치할 것이며, 딥 순서가 파이프라인에서 신뢰하는 것이다.
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
    """트림은 어떤 투표를 하게 할지를 결정하는 것이지, 반환된 문서가 어떤 것을 담고 있을지를 결정하는 것이 아니다.

    문서의 패스가 선택되는 후보는 융합이 읽는 리스트와 동일하므로, 그 자리에서 트림을 수행하면 반환되는 문서에서 청크를 제거하게 된다 -- 이는 스테이지 20이 의존하는 풀(pool)이다.
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
    # l2와 v2는 모두 각각의 리트리버의 트림 기준보다 훨씬 낮으며, 둘 다 투표하지 않았다.
    assert sorted(hits[0].chunk_ids) == ["l1", "l2", "v1", "v2"]
