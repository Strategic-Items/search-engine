from datetime import date
from unittest.mock import Mock

from search_engine.indexing.prepare import form_slot, supersessions
from search_engine.search import build_query, retrieve


def form(parent_id: str, title: str, published_at: str | None) -> dict:
    return {"parent_id": parent_id, "title": title, "published_at": published_at}


def test_both_title_spellings_name_the_same_slot():
    assert form_slot("[38차 개정, 26.9.1] 별지 4. 전문판정(신청)서") == ("별지", "4")
    assert form_slot("[별지 제4호 서식] 전문판정(신청)서") == ("별지", "4")
    assert form_slot("[별지 제2호의3 서식] 최종사용자 서약서") == ("별지", "2의3")
    assert form_slot("[38차 개정, 26.9.1] 별표2. 이중용도품목") == ("별표", "2")


def test_a_form_of_another_statute_is_not_the_same_slot():
    """행정절차법 별지 제2호는 전략물자 서식과 별개의 자체 서식 번호를 사용한다."""
    assert form_slot("[행정절차법 별지 제2호] 지위승계 통지서") is None
    assert form_slot("전략물자 수출거래 보고서") is None


def test_the_newest_edition_supersedes_the_older_ones():
    rows = [
        form("form-old", "[별지 제4호 서식] 전문판정(신청)서", "2021-12-02"),
        form("form-new", "[38차 개정, 26.9.1] 별지 4. 전문판정(신청)서", "2026-09-04"),
    ]
    assert supersessions(rows) == {"form-old": "form-new"}


def test_forms_in_different_slots_never_supersede_each_other():
    rows = [
        form("form-a", "[별지 제4호 서식] 전문판정(신청)서", "2021-12-02"),
        form("form-b", "[별지 제6호] 포괄수출허가(신청)서", "2026-09-04"),
    ]
    assert supersessions(rows) == {}


def test_editions_published_the_same_day_do_not_supersede_each_other():
    """38번째 개정판은 한 슬롯의 두 가지 변형을 함께 출시했다."""
    rows = [
        form("form-a", "[38차 개정, 26.9.1] 별지 2의3. END-USER STATEMENT", "2026-09-04"),
        form("form-b", "[38차 개정, 26.9.1] 별지 2의3. END-USER STATEMENT(for Wassenaar)",
             "2026-09-04"),
    ]
    assert supersessions(rows) == {}


def test_a_form_without_a_date_cannot_be_ordered():
    rows = [
        form("form-old", "[별지 제4호 서식] 전문판정(신청)서", None),
        form("form-new", "[38차 개정, 26.9.1] 별지 4. 전문판정(신청)서", "2026-09-04"),
    ]
    assert supersessions(rows) == {}


def test_the_current_edition_outranks_the_retired_one_by_default():
    functions = build_query("전문판정 신청서", date(2026, 9, 15))["function_score"]["functions"]
    current = [f for f in functions if "must_not" in str(f["filter"])]
    assert current and current[0]["filter"]["bool"]["must_not"] == {
        "exists": {"field": "superseded_by"}
    }


def test_the_replacement_follows_the_retired_document_it_names():
    client = Mock()
    client.search.side_effect = [
        {"hits": {"hits": [
            {"_id": "form-old", "_score": 9.0, "_source": {
                "parent_id": "form-old", "title": "옛 서식",
                "superseded_by": "form-new"}},
            {"_id": "other", "_score": 8.0, "_source": {"parent_id": "other", "title": "다른 문서"}},
        ]}},
        {"hits": {"hits": [
            {"_id": "form-new#c1", "_source": {"parent_id": "form-new", "title": "현행 서식"}},
        ]}},
    ]

    hits = retrieve(client, "search-documents", "전문판정 신청서", date.today(), 5, cutoff_ratio=0)

    assert [hit.parent_id for hit in hits] == ["form-old", "form-new", "other"]
    assert hits[0].superseded_by == "form-new"
    assert hits[1].score is None


def test_a_replacement_already_in_the_results_is_not_repeated():
    client = Mock()
    client.search.return_value = {"hits": {"hits": [
        {"_id": "form-old", "_score": 9.0, "_source": {
            "parent_id": "form-old", "title": "옛 서식", "superseded_by": "form-new"}},
        {"_id": "form-new", "_score": 8.0, "_source": {"parent_id": "form-new", "title": "현행"}},
    ]}}

    hits = retrieve(client, "search-documents", "전문판정 신청서", date.today(), 5, cutoff_ratio=0)

    assert [hit.parent_id for hit in hits] == ["form-old", "form-new"]
    assert client.search.call_count == 1


def test_following_a_pointer_never_returns_more_than_asked_for():
    client = Mock()
    client.search.side_effect = [
        {"hits": {"hits": [
            {"_id": "form-old", "_score": 9.0, "_source": {
                "parent_id": "form-old", "title": "옛 서식", "superseded_by": "form-new"}},
            {"_id": "other", "_score": 8.0, "_source": {"parent_id": "other", "title": "다른 문서"}},
        ]}},
        {"hits": {"hits": [
            {"_id": "form-new", "_source": {"parent_id": "form-new", "title": "현행 서식"}},
        ]}},
    ]

    hits = retrieve(client, "search-documents", "전문판정 신청서", date.today(), 2, cutoff_ratio=0)

    assert [hit.parent_id for hit in hits] == ["form-old", "form-new"]


def notice(parent_id: str, title: str, published_at: str | None) -> dict:
    return {"parent_id": parent_id, "source_type": "공지사항",
            "title": title, "published_at": published_at}


def test_a_gosi_edition_is_a_slot_but_other_notices_are_not():
    from search_engine.indexing.prepare import document_slot

    assert document_slot("공지사항", "제38차 전략물자수출입고시 개정 안내(9.1 시행)") == (
        "고시", "전략물자수출입고시")
    assert document_slot("공지사항", "시스템 점검 안내(5.21일(목) 18:30 ~ 20:30)") is None
    assert document_slot(
        "공지사항", "제38차 「전략물자 수출입고시」 별표 2 개정에 따른 전략물자-HSK 연계표") is None


def test_the_later_gosi_edition_replaces_the_earlier_one():
    rows = [
        notice("n-37", "제37차 전략물자수출입고시 개정 안내(2.2 시행)", "2026-02-01"),
        notice("n-38", "제38차 전략물자수출입고시 개정 안내(9.1 시행)", "2026-09-01"),
    ]
    assert supersessions(rows) == {"n-37": "n-38"}


def test_a_draft_is_never_the_text_in_force_even_when_it_is_the_newest():
    """현재 판 이후 다음 판의 초안이 출판된다."""
    rows = [
        notice("n-38", "제38차 전략물자수출입고시 개정 안내(9.1 시행)", "2026-09-01"),
        notice("n-draft", "｢전략물자 수출입고시｣ 일부개정(안) 행정예고", "2026-10-01"),
    ]
    assert supersessions(rows) == {"n-draft": "n-38"}


def test_a_draft_with_no_enacted_edition_to_point_at_is_left_alone():
    rows = [notice("n-draft", "｢전략물자 수출입고시｣ 일부개정(안) 행정예고", "2026-07-24")]
    assert supersessions(rows) == {}


def test_only_a_gosi_notice_reads_as_a_draft():
    from search_engine.indexing.prepare import is_gosi_draft

    assert is_gosi_draft("공지사항", "｢전략물자 수출입고시｣ 일부개정(안) 행정예고")
    assert not is_gosi_draft("공지사항", "무역안보 현안설명회 개최 안내(12.8(월), SETEC)")
    assert not is_gosi_draft("공지사항", "제38차 전략물자수출입고시 개정 안내(9.1 시행)")
    assert not is_gosi_draft("민원서식", "[별지 제4호 서식] 전문판정(신청)서")
