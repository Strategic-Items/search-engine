from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from search_engine.api.routes import app
from search_engine.config import Settings, get_settings


@pytest.mark.parametrize("datasets,expected", [
    ("core,docs", "search-documents,search-docs"),
    ("docs", "search-docs"), ("core", "search-documents"),
])
def test_dataset_selection(datasets, expected):
    assert Settings(search_document_datasets=datasets).document_aliases == expected


def test_duplicate_aliases_are_deduplicated():
    assert Settings(search_index_alias="same", search_docs_alias="same").document_aliases == "same"


@pytest.mark.parametrize("values", [
    {"search_document_datasets": "typo"}, {"search_mode": "typo"},
])
def test_invalid_configuration_fails(values):
    with pytest.raises(ValidationError):
        Settings(**values)


def test_docs_only_disables_hsk_even_for_code_queries(monkeypatch):
    monkeypatch.setenv("SEARCH_DOCUMENT_DATASETS", "docs")
    monkeypatch.setenv("SEARCH_MODE", "bm25")
    get_settings.cache_clear()
    client = Mock()
    client.search.return_value = {"hits": {"hits": []}}
    monkeypatch.setattr("search_engine.api.routes.create_client", lambda: client)
    result = TestClient(app).post("/v1/search", json={"query": "HSK 2826902000"})
    assert result.status_code == 200
    assert result.json()["hsk"] is None
    assert client.search.call_count == 1
    assert client.search.call_args.kwargs["index"] == "search-docs"


def test_hsk_can_be_disabled_in_combined_mode(monkeypatch):
    monkeypatch.setenv("SEARCH_HSK_ENABLED", "false")
    monkeypatch.setenv("SEARCH_MODE", "bm25")
    get_settings.cache_clear()
    client = Mock()
    client.search.return_value = {"hits": {"hits": []}}
    monkeypatch.setattr("search_engine.api.routes.create_client", lambda: client)
    assert TestClient(app).post("/v1/search", json={"query": "2826902000"}).json()["hsk"] is None
    assert client.search.call_count == 1
