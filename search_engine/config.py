"""Runtime settings, independent from the HTTP layer."""

from functools import lru_cache
from typing import Literal

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
    search_document_datasets: Literal["core,docs", "docs", "core"] = "core,docs"
    search_mode: Literal["bm25", "vector", "hybrid"] = "hybrid"
    search_hsk_enabled: bool = True
    search_number_of_replicas: int = Field(default=0, ge=0)
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:3b"
    # Keep the embedding model separate from the chat model: chat models are
    # usually much larger and may not expose Ollama's embedding endpoint.
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_temperature: float = 0.4
    # Ollama silently drops the front of a prompt that exceeds the context window,
    # which would cut the grounding rules and leave the evidence, and the window
    # covers the answer as well as the prompt. At four chunks per document the
    # longest docs v2 prompt measured 7,695 tokens, so this leaves room to answer.
    ollama_num_ctx: int = Field(default=16384, ge=512)
    ollama_timeout_seconds: float = Field(default=120.0, gt=0)
    search_embedding_dimensions: int = Field(default=768, ge=1)
    search_vector_candidates: int = Field(default=50, ge=1, le=1_000)
    search_hybrid_rrf_k: int = Field(default=60, ge=1)
    # Chunks carried per returned document. Ranking still returns one document
    # per slot; this only decides how much of that document comes with it.
    search_chunks_per_document: int = Field(default=4, ge=1, le=20)
    # Search the question and a model-written rewrite of it, fused. Off by
    # default: on docs v2 it buys one to two questions out of forty and costs
    # roughly half a second per search, and it puts the chat model in the path
    # of a search that otherwise has no model dependency at all.
    search_query_rewrite: bool = False
    # How much the rewrite's ranking counts against the original's. Below 1 so a
    # rewrite that went wrong cannot outvote the question the user actually asked.
    search_query_rewrite_weight: float = Field(default=0.5, gt=0.0, le=1.0)
    rag_top_k: int = Field(default=5, ge=1)

    @property
    def document_aliases(self) -> str:
        """Selected document indexes; a single corpus never reads other aliases."""
        aliases = {"core": self.search_index_alias, "docs": self.search_docs_alias}
        return ",".join(dict.fromkeys(aliases[name] for name in self.search_document_datasets.split(",")))


@lru_cache
def get_settings() -> Settings:
    return Settings()
