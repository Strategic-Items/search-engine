from datetime import date
from unittest.mock import Mock

from search_engine.prepare import form_slot, supersessions
from search_engine.search import build_query, retrieve


def form(parent_id: str, title: str, published_at: str | None) -> dict:
    return {"parent_id": parent_id, "title": title, "published_at": published_at}


def test_both_title_spellings_name_the_same_slot():
    assert form_slot("[38차 개정, 26.9.1] 별지 4. 전문판정(신청)서") == ("별지", "4")
    assert form_slot("[별지 제4호 서식] 전문판정(신청)서") == ("별지", "4")
    assert form_slot("[별지 제2호의3 서식] 최종사용자 서약서") == ("별지", "2의3")
    assert form_slot("[38차 개정, 26.9.1] 별표2. 이중용도품목") == ("별표", "2")


def test_a_form_of_another_statute_is_not_the_same_slot():
    """행정절차법 별지 제2호 numbers its own forms, not the export-control ones."""
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
    """The 38th revision put two variants of one slot out together."""
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

    hits = retrieve(client, "search-documents", "전문판정 신청서", date.today(), 5)

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

    hits = retrieve(client, "search-documents", "전문판정 신청서", date.today(), 5)

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

    hits = retrieve(client, "search-documents", "전문판정 신청서", date.today(), 2)

    assert [hit.parent_id for hit in hits] == ["form-old", "form-new"]
