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


def test_no_per_document_cap_allows_one_document_to_fill_only_the_total_budget():
    same = [chunk(f"s{i}", "S") for i in range(15)]
    groups = select(same, same, chunks_per_document=None, dense_within_document=True)
    assert groups == [[f"s{i}" for i in range(10)]]


def test_no_document_cap_allows_more_than_five_documents_under_the_total_budget():
    candidates = [chunk(f"c{i}", f"P{i}") for i in range(15)]
    groups = select(candidates, candidates, max_documents=None, chunks_per_document=None)
    assert len(groups) == 10
    assert sum(map(len, groups)) == 10


def test_current_edition_backfill_cannot_exceed_the_final_chunk_budget():
    from search_engine.search.query import _limit_chunk_budget
    from search_engine.search.results import SearchHit, Passage

    original = SearchHit(id="old#0", parent_id="old", title="Old", body="0",
                         passages=[Passage(id=f"old#{i}", body=str(i)) for i in range(1, 10)])
    current = SearchHit(id="current#0", parent_id="current", title="Current", body="new")
    assert [cid for h in _limit_chunk_budget([original, current], 10) for cid in h.chunk_ids] == original.chunk_ids
    assert len(original.passages) == 9
    # With room for the linked edition, preserve it and trim the next document.
    tail = SearchHit(id="tail#0", parent_id="tail", title="Tail", body="tail",
                     passages=[Passage(id=f"tail#{i}", body=str(i)) for i in range(1, 5)])
    short = original.model_copy(update={"passages": original.passages[:5]})
    limited = _limit_chunk_budget([short, current, tail], 10)
    assert [len(h.chunk_ids) for h in limited] == [6, 1, 3]
    assert limited[1].id == "current#0"
    assert len(tail.passages) == 4


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


def test_dense_evidence_replaces_rrf_overlap_without_expanding_budgets():
    lex = [chunk("shared1", "A"), chunk("shared2", "A"), chunk("b", "B")]
    vec = [chunk("shared1", "A"), chunk("answer", "A"),
           chunk("shared2", "A"), chunk("b", "B")]
    old = select(lex, vec, cutoff_ratio=0.7, chunks_per_document=2)
    new = select(lex, vec, cutoff_ratio=0.7, chunks_per_document=2,
                 dense_within_document=True)
    assert old == [["shared1", "shared2"], ["b"]]
    assert new == [["shared1", "answer"], ["b"]]
    assert list(map(len, old)) == list(map(len, new))


def test_dense_selection_does_not_admit_rejected_parents_or_their_copies():
    lex = [chunk("a", "A", "공지", "2026-01-01")]
    vec = [chunk("a", "A", "공지", "2026-01-01"),
           chunk("copy", "COPY", "공지", "2026-01-01"), chunk("other", "B")]
    assert select(lex, vec, cutoff_ratio=0.95, dense_within_document=True) == [["a"]]


def test_dense_selection_keeps_lexical_evidence_when_dense_has_no_same_parent():
    assert select([chunk("lex", "A")], [chunk("dense", "B")],
                  dense_within_document=True) == [["dense"], ["lex"]]


def test_dense_selection_preserves_the_lexical_leader_for_exact_identifiers():
    lex = [chunk("exact_code", "A"), chunk("shared", "A")]
    vec = [chunk("shared", "A"), chunk("nearby", "A")]
    assert select(lex, vec, chunks_per_document=2, dense_within_document=True) == [["shared", "exact_code"]]


def test_one_slot_does_not_drop_an_already_selected_lexical_leader():
    lex = [chunk("exact", "A")]
    vec = [chunk("other", "B"), chunk("nearby", "A")]
    assert select(lex, vec, chunks_per_document=1, dense_within_document=True) == [["other"], ["exact"]]


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


def test_extract_control_numbers_keeps_only_control_codes():
    from search_engine.codes import extract_control_numbers

    assert extract_control_numbers("별표 2 통제번호 3A002.d.1의 개정반영, 제21조 ML8과 2B352") == ["3A002.d.1", "ML8", "2B352"]
    assert extract_control_numbers("자율준수무역거래자 지정 요건은 제21조의7인가요?") == []
