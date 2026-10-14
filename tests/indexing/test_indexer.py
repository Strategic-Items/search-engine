import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from search_engine.config import Settings
from search_engine.embeddings import embedding_text
from search_engine.indexing.indexer import document_actions, rebuild, encoding_metadata
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


def test_category_encoding_metadata_records_actual_input_and_window_settings():
    metadata = encoding_metadata(Settings(search_splade_model="/models/checkpoint",
                                          search_splade_doc_max_length=256), "source-hash")
    assert metadata["corpus_sha256"] == "source-hash"
    assert metadata["sparse_doc_max_length"] == 256
    assert metadata["sparse_window_overlap"] == 64
    assert metadata["sparse_document_strategy"] == "overlapping-windows-max-pool-v1"


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


def test_indexing_drops_download_copies_and_carries_the_period_hint(tmp_path: Path):
    """파서 산출물은 prepare를 거치지 않으므로 색인기가 같은 규칙을 걸어야 한다."""
    path = tmp_path / "docs.jsonl"
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in [
        {"id": "a#0", "parent_id": "a", "title": "안내", "body": "2016. 3. 8. 발신",
         "chunk_index": 0, "source_path": "안내문.hwp"},
        {"id": "b#0", "parent_id": "b", "title": "안내", "body": "2016. 3. 8. 발신",
         "chunk_index": 0, "source_path": "안내문 (1).hwp"},
        {"id": "c#0", "parent_id": "c", "title": "고시", "body": "2016. 3. 8. 발신",
         "chunk_index": 0, "source_path": "고시.hwp", "published_at": "2020-01-01"},
    ]), encoding="utf-8")

    dropped: list[str] = []
    actions = list(document_actions(path, "idx", dropped=dropped))

    assert [action["_id"] for action in actions] == ["a#0", "c#0"]
    assert dropped == ["b#0"]
    assert actions[0]["_source"]["period_hint"] == "2016-03-08"
    # 발행일을 아는 문서는 추정으로 덮지 않는다.
    assert "period_hint" not in actions[1]["_source"]


class _CountingEmbedder:
    """묶음마다 부른 횟수와 받은 텍스트를 남기는 가짜 임베더."""

    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        # 본문을 그대로 벡터 자리에 넣어 어느 문서 것인지 확인할 수 있게 한다.
        return [[float(len(text)), text] for text in texts]


class _CountingSparse:
    def __init__(self):
        self.calls = []

    def encode_documents(self, texts):
        self.calls.append(list(texts))
        return [{} for _ in texts]


def test_law_embedding_removes_path_headings_but_keeps_the_source_body(tmp_path: Path):
    body = "# 제1조(목적)\n\n목적 본문.\n\n## 제1항\n\n항 본문."
    path = write(tmp_path, {
        "id": "law#0", "parent_id": "law", "title": "시행령 — 제1항", "body": body,
        "heading_path": ["제1조(목적)", "제1항"], "source_type": "법령", "chunk_index": 0,
    })
    embedder = _CountingEmbedder()
    sparse = _CountingSparse()

    actions = list(document_actions(path, "law-index", embedder, law=True,
                                    sparse=sparse, dense_heading_path=True, sparse_heading_path=True))

    expected = embedding_text("시행령 — 제1조(목적) > 제1항", "목적 본문.\n\n항 본문.")
    assert embedder.calls == [[expected]]
    assert sparse.calls == [[expected]]
    assert actions[0]["_source"]["body"] == body


def test_batched_embeddings_stay_with_their_own_document(tmp_path: Path):
    """묶어 보내도 벡터가 제 문서에 붙어야 한다. 짝이 어긋나면 조용히 오답이 된다."""
    path = tmp_path / "corpus.jsonl"
    rows = [{"id": f"d{i}", "parent_id": f"d{i}", "title": f"제목{i}",
             "body": "본" * (i + 1), "source_type": "공지사항", "chunk_index": 0}
            for i in range(7)]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                    encoding="utf-8")
    embedder = _CountingEmbedder()
    actions = list(document_actions(path, "idx", embedder, batch=3))

    assert [a["_id"] for a in actions] == [f"d{i}" for i in range(7)]
    for action in actions:
        source = action["_source"]
        assert source["embedding"][1] == embedding_text(source["title"], source["body"])
    # 7건을 3묶음으로: 3 + 3 + 1
    assert [len(call) for call in embedder.calls] == [3, 3, 1]
