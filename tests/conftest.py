"""Test-wide isolation from the embedding service.

`retrieve` builds its own `OllamaEmbedder` when the caller passes none, so a
test that does not mention embedding still reaches out to a local Ollama --
and then behaves differently depending on which models happen to be pulled on
the machine running it. Standing in for the service keeps that out of the
tests: the vector half of the search is exercised by passing an embedder in.
"""

import httpx
import pytest

from search_engine.config import get_settings


@pytest.fixture(autouse=True)
def isolate_local_corpus_settings(monkeypatch):
    """A developer's corpus or chat .env must not change default contract tests."""
    for key, value in {
        "SEARCH_DOCUMENT_DATASETS": "core,docs", "SEARCH_MODE": "hybrid",
        "SEARCH_HSK_ENABLED": "true", "SEARCH_DOCS_ALIAS": "search-docs",
        "SEARCH_DOCS_PREFIX": "search-docs-v",
        "CHAT_PROVIDER": "ollama", "CHAT_BASE_URL_OVERRIDE": "",
        "CHAT_MODEL_OVERRIDE": "", "CHAT_API_KEY": "none",
        # Score floors are raw scores calibrated on whatever corpus a developer
        # happens to run, so a deployment's values would silently empty the
        # result lists these tests assert on.
        "SEARCH_SCORE_FLOOR_BM25": "0", "SEARCH_SCORE_FLOOR_VECTOR": "0",
        "SEARCH_SCORE_FLOOR_HYBRID": "0", "SEARCH_SCORE_FLOOR_SPARSE": "0",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def no_ambient_embedding_service(monkeypatch, request):
    """Make the unasked-for embedder unavailable, as it is when Ollama is down.

    Search degrades to lexical-only in that case, which is the behaviour the
    tests that do not inject an embedder are written against.
    """
    if request.node.get_closest_marker("uses_embedding_service"):
        return

    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("no embedding service in tests")

    monkeypatch.setattr("search_engine.search.query.OllamaEmbedder", unavailable)
