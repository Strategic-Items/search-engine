"""Runtime settings, independent from the HTTP layer."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    opensearch_url: str = "http://localhost:9203"
    opensearch_username: str = ""
    opensearch_password: str = ""
    opensearch_verify_certs: bool = True
    search_index_alias: str = "search-documents"
    search_index_prefix: str = "search-documents-v"
    # Documents parsed out of source files (HWP/HWPX/PDF) by the doc parser.
    # A separate index so rebuilding one corpus cannot drop the other: every
    # rebuild replaces its whole index.
    search_docs_alias: str = "search-docs"
    search_docs_prefix: str = "search-docs-v"
    search_hsk_alias: str = "search-hsk"
    search_hsk_prefix: str = "search-hsk-v"
    search_number_of_replicas: int = Field(default=0, ge=0)
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:3b"
    # Keep the embedding model separate from the chat model: chat models are
    # usually much larger and may not expose Ollama's embedding endpoint.
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_temperature: float = 0.4
    ollama_timeout_seconds: float = Field(default=120.0, gt=0)
    search_embedding_dimensions: int = Field(default=768, ge=1)
    search_vector_candidates: int = Field(default=50, ge=1, le=1_000)
    search_hybrid_rrf_k: int = Field(default=60, ge=1)
    rag_top_k: int = Field(default=5, ge=1)

    @property
    def document_aliases(self) -> str:
        """Every index the document search reads, as OpenSearch's index list.

        Reading both corpora through one search keeps ranking a single fused
        list. RRF compares ranks, not scores, so the per-index IDF difference
        between the two does not distort the result.
        """
        return f"{self.search_index_alias},{self.search_docs_alias}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
