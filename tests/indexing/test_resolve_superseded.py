"""번호로 적힌 대체 관계를 부모 문서 ID로 푼다."""

from search_engine.indexing.law import resolve_superseded


def parents():
    return {
        "old": {"superseded_by": "산업통상자원부 고시 제2015-145호", "doc_number": "고시 제2014-15호", "doc_status": "개정", "chunks": 10},
        "draft": {"superseded_by": None, "doc_number": "산업통상자원부 고시 제2015-145호", "doc_status": "안", "chunks": 99},
        "body": {"superseded_by": None, "doc_number": "산업통상자원부 고시 제2015-145호", "doc_status": "개정", "chunks": 20},
        "amend": {"superseded_by": None, "doc_number": "산업통상자원부 고시 제2015-145호", "doc_status": "개정", "chunks": 4},
    }


def test_the_enacted_larger_document_wins_among_documents_sharing_a_number():
    assert resolve_superseded(parents()) == {"old": "body"}


def test_a_pointer_that_is_already_a_parent_id_is_left_alone():
    data = parents()
    data["old"]["superseded_by"] = "body"
    assert resolve_superseded(data) == {}


def test_a_document_never_resolves_to_itself_and_unknown_numbers_stay_unresolved():
    data = parents()
    data["body"]["superseded_by"] = "산업통상자원부 고시 제2015-145호"
    data["amend"]["superseded_by"] = "대통령령 제99999호"
    resolved = resolve_superseded(data)
    assert resolved["body"] == "amend" and "amend" not in resolved


def test_statute_numbers_without_a_year_resolve_too():
    data = {"a": {"superseded_by": "대통령령 제30418호", "chunks": 1},
            "b": {"doc_number": "대통령령 제30418호", "doc_status": "개정", "chunks": 5}}
    assert resolve_superseded(data) == {"a": "b"}
