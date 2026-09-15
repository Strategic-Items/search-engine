import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from search_engine.config import Settings
from search_engine.indexer import document_actions, rebuild


def test_document_actions_validates_ids_and_source_dates(tmp_path: Path):
    path = tmp_path / "docs.jsonl"
    path.write_text(json.dumps({"id": "faq-1", "title": "허가", "code": "5 d 002",
                                "effective_from": 20260901}) + "\n")
    action = next(document_actions(path, "new-index"))
    assert action["_id"] == "faq-1"
    assert action["_source"]["code_norm"] == "5D002"
    assert action["_source"]["effective_from"] == "2026-09-01"


def test_rebuild_keeps_old_index_and_atomically_moves_alias(tmp_path, monkeypatch):
    path = tmp_path / "docs.jsonl"
    path.write_text('{"id":"faq-1","title":"허가"}\n')
    client = Mock()
    client.ping.return_value = True
    client.count.return_value = {"count": 1}
    client.indices.get_alias.return_value = {"old-index": {}}
    monkeypatch.setattr("search_engine.indexer.get_settings", lambda: Settings())
    monkeypatch.setattr("search_engine.indexer.create_client", lambda settings: client)
    monkeypatch.setattr("search_engine.indexer.streaming_bulk", lambda *a, **kw: [(True, {})])

    index_name, count = rebuild(path)
    assert count == 1
    assert index_name.startswith("search-documents-v")
    actions = client.indices.update_aliases.call_args.kwargs["body"]["actions"]
    assert actions == [
        {"remove": {"index": "old-index", "alias": "search-documents"}},
        {"add": {"index": index_name, "alias": "search-documents"}},
    ]
    client.indices.delete.assert_not_called()


def test_rebuild_rejects_empty_index_before_publish(tmp_path, monkeypatch):
    path = tmp_path / "docs.jsonl"
    path.write_text("")
    client = Mock()
    client.ping.return_value = True
    client.indices.get_alias.return_value = {}
    monkeypatch.setattr("search_engine.indexer.get_settings", lambda: Settings())
    monkeypatch.setattr("search_engine.indexer.create_client", lambda settings: client)
    monkeypatch.setattr("search_engine.indexer.streaming_bulk", lambda *a, **kw: [])

    with pytest.raises(ValueError, match="empty index"):
        rebuild(path)
    client.indices.update_aliases.assert_not_called()
    client.indices.delete.assert_called_once()
