from datetime import date
import json
from pathlib import Path
from unittest.mock import Mock

import httpx

from search_engine.config import Settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.indexing.indexer import document_actions
from search_engine.indexing.mapping import index_body
from search_engine.search.query import build_vector_query, retrieve


def test_embedding_mapping_is_an_hnsw_cosine_index():
    mapping = index_body(3)
    assert mapping["settings"]["index"]["knn"] is True
    field = mapping["mappings"]["properties"]["embedding"]
    assert field["dimension"] == 3
    assert field["method"] == {"name": "hnsw", "engine": "faiss", "space_type": "cosinesimil"}


def test_ollama_embedding_request_and_dimension_validation(monkeypatch):
    seen = {}

    def post(url, **kwargs):
        seen.update(url=url, **kwargs)
        return httpx.Response(200, json={"embeddings": [[0, 0.5, 1]]}, request=httpx.Request("POST", url))

    monkeypatch.setattr("search_engine.embeddings.httpx.post", post)
    settings = Settings(ollama_base_url="http://ollama.test", search_embedding_dimensions=3)
    embedder = OllamaEmbedder(settings)
    assert embedder.embed_query("수출 허가") == [0.0, 0.5, 1.0]
    assert seen["url"] == "http://ollama.test/api/embed"
    assert seen["json"] == {"model": settings.ollama_embedding_model, "input": ["수출 허가"]}


def test_document_action_stores_the_embedding(tmp_path: Path):
    path = tmp_path / "docs.jsonl"
    path.write_text(json.dumps({"id": "one", "title": "허가", "body": "신청 절차"}) + "\n", encoding="utf-8")
    embedder = Mock()
    embedder.embed.return_value = [[0.1, 0.2]]
    action = next(document_actions(path, "test", embedder))
    assert action["_source"]["embedding"] == [0.1, 0.2]
    embedder.embed.assert_called_once_with([embedding_text("허가", "신청 절차")])


def test_hybrid_search_fuses_bm25_and_vector_rankings(monkeypatch):
    monkeypatch.setattr("search_engine.search.query.get_settings", lambda: Settings(
        search_vector_candidates=10, search_hybrid_rrf_k=60,
    ))
    client = Mock()
    client.search.side_effect = [
        {"hits": {"hits": [
            {"_id": "lex", "_source": {"title": "lex"}},
            {"_id": "both", "_source": {"title": "both"}},
        ]}},
        {"hits": {"hits": [
            {"_id": "both", "_source": {"title": "both"}},
            {"_id": "semantic", "_source": {"title": "semantic"}},
        ]}},
    ]
    embedder = Mock()
    embedder.embed_query.return_value = [0.1, 0.2]
    hits = retrieve(client, "documents", "의미 검색", date(2026, 9, 15), 3, embedder)
    assert [hit.id for hit in hits] == ["both", "lex", "semantic"]
    vector_call = client.search.call_args_list[1]
    assert vector_call.kwargs["body"]["query"] == build_vector_query([0.1, 0.2], date(2026, 9, 15), 15)
