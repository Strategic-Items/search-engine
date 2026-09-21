import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from search_engine.config import Settings
from search_engine.indexing.indexer import document_actions, rebuild
from search_engine.config import get_settings
from search_engine.indexing.mapping import index_body


def write(tmp_path: Path, *rows: dict, name: str = "docs.jsonl") -> Path:
    path = tmp_path / name
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def patch_cluster(monkeypatch, client: Mock, bulk_results=((True, {}),), **settings) -> Mock:
    """모의 클러스터를 가리키도록 재구성하라. 이 클러스터의 대량 쓰기 작업은 bulk_results를 보고한다."""
    client.ping.return_value = True
    monkeypatch.setattr("search_engine.indexing.indexer.get_settings", lambda: Settings(**settings))
    monkeypatch.setattr("search_engine.indexing.indexer.create_client", lambda settings: client)
    monkeypatch.setattr("search_engine.indexing.indexer.streaming_bulk",
                        lambda *a, **kw: list(bulk_results))
    return client


def test_document_actions_validates_ids_and_source_dates(tmp_path: Path):
    path = write(tmp_path, {"id": "faq-1", "title": "허가", "code": "5D002",
                            "effective_from": 20260901})
    action = next(document_actions(path, "new-index"))
    assert action["_id"] == "faq-1"
    assert action["_index"] == "new-index"
    assert action["_source"]["codes_exact"] == ["5d002"]
    assert action["_source"]["effective_from"] == "2026-09-01"


def test_document_actions_rejects_a_repeated_id(tmp_path: Path):
    path = write(tmp_path, {"id": "faq-1", "title": "허가"}, {"id": "faq-1", "title": "허가"})
    with pytest.raises(ValueError, match="duplicate document ID"):
        list(document_actions(path, "new-index"))


def test_callcenter_actions_normalize_raw_stt_chunks(tmp_path: Path):
    path = write(tmp_path, {
        "chunk_id": "sg01#c0", "call_id": "sg01", "seq": 0, "text": "공작기계 상담 내용",
        "call_inquiry": "공작기계 판정 방법", "categories": ["판정"],
        "entities": [{"type": "품목", "normalized": "공작기계"}],
    })

    action = next(document_actions(path, "call-index", callcenter=True))

    assert action["_id"] == "sg01#c0"
    assert action["_source"]["parent_id"] == "sg01"
    assert action["_source"]["title"] == "콜센터 상담 사례 · 판정"
    assert "문의 요약: 공작기계 판정 방법" in action["_source"]["body"]


def test_rebuild_keeps_old_index_and_atomically_moves_alias(tmp_path, monkeypatch):
    path = write(tmp_path, {"id": "faq-1", "title": "허가"})
    client = Mock()
    client.count.return_value = {"count": 1}
    client.indices.get_alias.return_value = {"old-index": {}}
    patch_cluster(monkeypatch, client)

    index_name, count = rebuild(path)

    assert count == 1
    assert index_name.startswith("search-documents-v")
    assert client.indices.update_aliases.call_args.kwargs["body"]["actions"] == [
        {"remove": {"index": "old-index", "alias": "search-documents"}},
        {"add": {"index": index_name, "alias": "search-documents"}},
    ]
    client.indices.delete.assert_not_called()


def test_rebuild_applies_the_configured_replica_count(tmp_path, monkeypatch):
    path = write(tmp_path, {"id": "faq-1", "title": "허가"})
    client = Mock()
    client.count.return_value = {"count": 1}
    client.indices.get_alias.return_value = {}
    patch_cluster(monkeypatch, client, search_number_of_replicas=2)

    rebuild(path)

    body = client.indices.create.call_args.kwargs["body"]
    assert body["settings"]["number_of_replicas"] == 2


def test_rebuild_rejects_empty_index_before_publish(tmp_path, monkeypatch):
    path = write(tmp_path)
    client = Mock()
    client.indices.get_alias.return_value = {}
    patch_cluster(monkeypatch, client, bulk_results=())

    with pytest.raises(ValueError, match="empty index"):
        rebuild(path)

    client.indices.update_aliases.assert_not_called()
    client.indices.delete.assert_called_once()


def test_rebuild_refuses_a_count_that_disagrees_with_the_manifest(tmp_path, monkeypatch):
    path = write(tmp_path, {"id": "faq-1", "title": "허가"})
    client = Mock()
    client.indices.get_alias.return_value = {}
    patch_cluster(monkeypatch, client)

    with pytest.raises(RuntimeError, match="input count mismatch"):
        rebuild(path, expected_count=2)

    client.indices.update_aliases.assert_not_called()
    client.indices.delete.assert_called_once()


def test_rebuild_refuses_an_index_the_cluster_did_not_actually_fill(tmp_path, monkeypatch):
    path = write(tmp_path, {"id": "faq-1", "title": "허가"})
    client = Mock()
    client.count.return_value = {"count": 0}
    client.indices.get_alias.return_value = {}
    patch_cluster(monkeypatch, client)

    with pytest.raises(RuntimeError, match="index count mismatch"):
        rebuild(path)

    client.indices.update_aliases.assert_not_called()


def test_rebuild_refuses_input_that_does_not_match_its_manifest_checksum(tmp_path, monkeypatch):
    path = write(tmp_path, {"id": "faq-1", "title": "허가"})
    client = Mock()
    patch_cluster(monkeypatch, client)

    with pytest.raises(ValueError, match="checksum"):
        rebuild(path, expected_sha256="0" * 64)

    client.indices.create.assert_not_called()


def test_rebuild_never_deletes_an_index_that_is_already_serving(tmp_path, monkeypatch):
    """별칭 교체가 성공했지만 호출이 실패를 보고하면, 인덱스는 살아남아야 한다."""
    path = write(tmp_path, {"id": "faq-1", "title": "허가"})
    client = Mock()
    client.count.return_value = {"count": 1}
    client.indices.get_alias.return_value = {}
    patch_cluster(monkeypatch, client)

    def swap_then_fail(body=None):
        client.indices.get_alias.return_value = {
            body["actions"][-1]["add"]["index"]: {},
        }
        raise RuntimeError("transport error after the swap")

    client.indices.update_aliases.side_effect = swap_then_fail

    with pytest.raises(RuntimeError, match="transport error"):
        rebuild(path)

    client.indices.delete.assert_not_called()


def test_rebuild_stops_when_the_cluster_is_unavailable(tmp_path, monkeypatch):
    path = write(tmp_path, {"id": "faq-1", "title": "허가"})
    client = Mock()
    patch_cluster(monkeypatch, client)
    client.ping.return_value = False

    with pytest.raises(RuntimeError, match="unavailable"):
        rebuild(path)

    client.indices.create.assert_not_called()


def test_rebuild_hsk_uses_separate_alias_and_mapping(tmp_path, monkeypatch):
    path = write(tmp_path, {"id": "hsk-1", "title": "HSK 0123456789",
                            "hsk_code": "0123456789", "source_type": "HSK 연계표"},
                 name="hsk.jsonl")
    client = Mock()
    client.count.return_value = {"count": 1}
    client.indices.get_alias.return_value = {}
    patch_cluster(monkeypatch, client)

    index_name, count = rebuild(path, dataset="hsk", expected_count=1)

    assert count == 1
    assert index_name.startswith("search-hsk-v")
    assert "hsk_code" in client.indices.create.call_args.kwargs["body"]["mappings"]["properties"]
    actions = client.indices.update_aliases.call_args.kwargs["body"]["actions"]
    assert actions[-1] == {"add": {"index": index_name, "alias": "search-hsk"}}


def test_rebuild_rejects_an_unknown_dataset(tmp_path):
    path = write(tmp_path, {"id": "faq-1", "title": "허가"})
    with pytest.raises(ValueError, match="unknown dataset"):
        rebuild(path, dataset="other")


def test_the_core_index_is_built_with_the_synonym_dictionary(tmp_path, monkeypatch):
    path = write(tmp_path, {"id": "faq-1", "title": "허가"})
    client = Mock()
    client.count.return_value = {"count": 1}
    client.indices.get_alias.return_value = {}
    patch_cluster(monkeypatch, client)

    rebuild(path)

    body = client.indices.create.call_args.kwargs["body"]
    rules = body["settings"]["analysis"]["filter"]["domain_synonyms"]["synonyms"]
    assert rules and all("," in rule for rule in rules)


def test_the_hsk_index_carries_no_synonyms(tmp_path, monkeypatch):
    path = write(tmp_path, {"id": "hsk-1", "title": "HSK 0123456789",
                            "hsk_code": "0123456789", "source_type": "HSK 연계표"},
                 name="hsk.jsonl")
    client = Mock()
    client.count.return_value = {"count": 1}
    client.indices.get_alias.return_value = {}
    patch_cluster(monkeypatch, client)

    rebuild(path, dataset="hsk")

    body = client.indices.create.call_args.kwargs["body"]
    assert "domain_synonyms" not in body["settings"]["analysis"].get("filter", {})


def test_rebuild_docs_uses_its_own_alias_but_the_document_mapping(tmp_path, monkeypatch):
    """문서 코퍼스는 별도로 인덱싱되지만 핵심과 함께 검색 가능하게 유지된다."""
    path = write(tmp_path, {"id": "notice-1#0000", "title": "공고문",
                            "parent_id": "notice-1", "source_type": "공고문"},
                 name="docs.jsonl")
    client = Mock()
    client.count.return_value = {"count": 1}
    client.indices.get_alias.return_value = {}
    patch_cluster(monkeypatch, client)

    index_name, count = rebuild(path, dataset="docs", expected_count=1)

    assert count == 1
    assert index_name.startswith("search-docs-v")
    body = client.indices.create.call_args.kwargs["body"]
    assert body["mappings"] == index_body(
        get_settings().search_embedding_dimensions)["mappings"]
    assert body["settings"]["analysis"]["filter"]["domain_synonyms"]["synonyms"]
    actions = client.indices.update_aliases.call_args.kwargs["body"]["actions"]
    assert actions[-1] == {"add": {"index": index_name, "alias": "search-docs"}}


def test_rebuilding_docs_leaves_the_core_alias_alone(tmp_path, monkeypatch):
    """별도의 데이터셋이 존재하므로 한 코퍼스가 다른 코퍼스를 떨어뜨릴 수 없다."""
    path = write(tmp_path, {"id": "notice-1#0000", "title": "공고문"}, name="docs.jsonl")
    client = Mock()
    client.count.return_value = {"count": 1}
    client.indices.get_alias.return_value = {}
    patch_cluster(monkeypatch, client)

    rebuild(path, dataset="docs")

    assert client.indices.get_alias.call_args.kwargs["name"] == "search-docs"
    touched = {action[verb]["alias"]
               for action in client.indices.update_aliases.call_args.kwargs["body"]["actions"]
               for verb in action}
    assert touched == {"search-docs"}


def test_docs_are_embedded_like_core(tmp_path, monkeypatch):
    """두 문서 코퍼스는 하나의 하이브리드 검색을 통해 읽히므로, 둘 다 벡터가 필요하다."""
    path = write(tmp_path, {"id": "notice-1#0000", "title": "공고문"}, name="docs.jsonl")
    client = Mock()
    client.count.return_value = {"count": 1}
    client.indices.get_alias.return_value = {}
    patch_cluster(monkeypatch, client)
    embedders = []
    monkeypatch.setattr("search_engine.indexing.indexer.OllamaEmbedder",
                        lambda settings: embedders.append(settings) or Mock())

    rebuild(path, dataset="docs")

    assert len(embedders) == 1
