"""청크 우선 선택: 문서를 먼저 고르지 않고 청크 점수로 자른다."""

from search_engine.search.query import _chunk_first


def chunk(chunk_id, parent="p", title=None, published_at=None):
    # 제목과 발행일이 같은 부모는 사본으로 취급되므로 부모마다 다른 제목을 준다
    source = {"parent_id": parent, "title": title or f"문서 {parent}", "body": f"본문 {chunk_id}"}
    if published_at:
        source["published_at"] = published_at
    return {"_id": chunk_id, "_source": source, "_score": 1.0}


def select(lex, vec, **kw):
    options = dict(rrf_k=60, max_chunks=10, cutoff_ratio=0.0, max_documents=5,
                   chunks_per_document=6)
    options.update(kw)
    groups = _chunk_first([(lex, 1.0, "bm25"), (vec, 1.0, "vector")], "질의", **options)
    return [[c["_id"] for c in group] for group in groups]


def test_a_chunk_found_by_both_lists_leads_and_its_document_comes_first():
    lex = [chunk("a1", "A"), chunk("b1", "B")]
    vec = [chunk("b1", "B"), chunk("a1", "A")]
    # 두 목록에서 1위와 2위로 엇갈린 두 청크는 동점이고 밀집 순위가 앞선 b1이 먼저 온다
    assert select(lex, vec) == [["b1"], ["a1"]]


def test_a_chunk_is_not_dropped_because_its_document_ranks_low():
    # 문서 A는 청크를 여럿 데려와 앞을 차지하지만, 정답 청크 g는 문서 B의 하나뿐이다
    lex = [chunk(f"a{i}", "A") for i in range(1, 6)] + [chunk("g", "B")]
    vec = [chunk(f"a{i}", "A") for i in range(1, 6)] + [chunk("g", "B")]
    groups = select(lex, vec, max_chunks=6, chunks_per_document=5)
    assert ["g"] in groups


def test_the_chunk_budget_limits_what_is_carried():
    lex = [chunk(f"c{i}", f"P{i}") for i in range(1, 9)]
    vec = [chunk(f"c{i}", f"P{i}") for i in range(1, 9)]
    assert sum(map(len, select(lex, vec, max_chunks=4))) == 4


def test_documents_are_capped_and_chunks_per_document_are_capped():
    lex = [chunk(f"c{i}", f"P{i}") for i in range(1, 8)]
    assert len(select(lex, [], max_documents=3)) == 3
    same = [chunk(f"s{i}", "S") for i in range(1, 9)]
    assert len(select(same, [], chunks_per_document=3)[0]) == 3


def test_cutoff_drops_weak_chunks_but_keeps_each_lists_first():
    lex = [chunk("l1", "L"), chunk("l2", "L2")]
    vec = [chunk("v1", "V"), chunk("v2", "V2")]
    # 1위는 1/61, 2위는 1/62라 비율 0.99에서 2위(l2, v2)만 잘리고 각 목록의 1위는 남는다
    assert {c for g in select(lex, vec, cutoff_ratio=0.99) for c in g} == {"l1", "v1"}
    assert {c for g in select(lex, vec, cutoff_ratio=0.9) for c in g} == {"l1", "l2", "v1", "v2"}


def test_a_copy_of_a_document_already_carried_is_not_carried_again():
    lex = [chunk("o1", "orig", "같은 공고", "2026-01-01"), chunk("c1", "copy", "같은 공고", "2026-01-01")]
    assert select(lex, []) == [["o1"]]


def test_a_leading_chunk_of_no_document_is_needed_to_start():
    assert select([], []) == []


def test_document_agreement_lifts_a_document_both_lists_found_through_different_chunks():
    lex = [chunk("b1", "B"), chunk("a1", "A")]
    vec = [chunk("x1", "X"), chunk("a2", "A")]
    # 청크만 보면 b1·x1(각 목록 1위)이 앞서지만, 문서 A는 두 검색기가 함께 올린 문서다
    assert select(lex, vec)[0][0] in ("b1", "x1")
    assert {c for c in select(lex, vec, agreement=1.0)[0]} == {"a1", "a2"}


def retired(chunk_id, parent):
    item = chunk(chunk_id, parent)
    item["_source"]["superseded_by"] = "01_새판"
    return item


def pick(query, weight):
    # 옛 판 R이 두 목록 모두에서 근소하게 앞서고, 새 판 N이 바로 뒤에 온다
    lex = [retired("r1", "R"), chunk("n1", "N")]
    vec = [retired("r1", "R"), chunk("n1", "N")]
    options = dict(rrf_k=60, max_chunks=10, cutoff_ratio=0.0, max_documents=5, chunks_per_document=6)
    groups = _chunk_first([(lex, 1.0, "bm25"), (vec, 1.0, "vector")], query,
                          superseded_weight=weight, **options)
    return [[c["_id"] for c in group] for group in groups]


def test_a_retired_edition_is_scored_down_when_the_question_names_no_edition():
    assert pick("처리기간은 며칠인가요", 1.0) == [["r1"], ["n1"]]
    assert pick("처리기간은 며칠인가요", 0.5) == [["n1"], ["r1"]]


def test_a_question_that_names_an_edition_keeps_the_retired_edition_first():
    assert pick("2015년 개정안의 처리기간은", 0.5) == [["r1"], ["n1"]]
    assert pick("17차 개정에서 정의는", 0.5) == [["r1"], ["n1"]]
