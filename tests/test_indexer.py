import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from search_engine.config import Settings
from search_engine.indexer import document_actions, rebuild


def write(tmp_path: Path, *rows: dict, name: str = "docs.jsonl") -> Path:
    path = tmp_path / name
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def patch_cluster(monkeypatch, client: Mock, bulk_results=((True, {}),), **settings) -> Mock:
    """Point rebuild at a mock cluster whose bulk writes report bulk_results."""
    client.ping.return_value = True
    monkeypatch.setattr("search_engine.indexer.get_settings", lambda: Settings(**settings))
    monkeypatch.setattr("search_engine.indexer.create_client", lambda settings: client)
    monkeypatch.setattr("search_engine.indexer.streaming_bulk",
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
    """If the alias swap succeeds but the call reports failure, the index must survive."""
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
