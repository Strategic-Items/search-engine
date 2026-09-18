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
    # Past call-centre cases are deliberately excluded from the official
    # knowledge/RAG aliases and queried only by their dedicated endpoint.
    search_callcenter_alias: str = "search-callcenter"
    search_callcenter_prefix: str = "search-callcenter-v"
    search_hsk_alias: str = "search-hsk"
    search_hsk_prefix: str = "search-hsk-v"
    search_document_datasets: Literal["core,docs", "docs", "core"] = "core,docs"
    search_mode: Literal["bm25", "vector", "hybrid", "sparse", "hybrid_sparse"] = "hybrid"
    search_hsk_enabled: bool = True
    search_number_of_replicas: int = Field(default=0, ge=0)
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:3b"
    # Keep the embedding model separate from the chat model: chat models are
    # usually much larger and may not expose Ollama's embedding endpoint.
    # Multilingual: the corpus and the questions are Korean, and an English-first
    # model scores them close to randomly (docs/evaluation/stages/stage-06-embedding-model.md).
    ollama_embedding_model: str = "bge-m3"
    ollama_temperature: float = 0.4
    # Ollama silently drops the front of a prompt that exceeds the context window,
    # which would cut the grounding rules and leave the evidence, and the window
    # covers the answer as well as the prompt. At six chunks per document the
    # longest docs v2 prompt measured 14,068 tokens, which 16,384 would leave
    # only about 2,300 tokens to answer within, so this leaves real headroom.
    # Only the ollama provider reads this; an OpenAI-compatible server fixes its
    # window at startup instead (vLLM's --max-model-len).
    ollama_num_ctx: int = Field(default=24576, ge=512)
    ollama_timeout_seconds: float = Field(default=120.0, gt=0)
    # Where the chat model lives. "ollama" speaks Ollama's native API at
    # OLLAMA_BASE_URL; "openai" speaks the OpenAI-compatible protocol (vLLM,
    # SGLang, llama.cpp, LM Studio) at CHAT_BASE_URL_OVERRIDE. Embeddings stay
    # on Ollama either way: the mapping fixes the vector width, so moving them
    # means a reindex of every dataset.
    chat_provider: Literal["ollama", "openai"] = "ollama"
    # Both fall back to the OLLAMA_* settings, so an Ollama-only deployment
    # keeps configuring one URL and one model name.
    chat_base_url_override: str = ""
    chat_model_override: str = ""
    # Local servers ignore the value but still want a well-formed header.
    chat_api_key: str = "none"
    # Must match OLLAMA_EMBEDDING_MODEL exactly; changing either needs a reindex
    # of every dataset, since the mapping fixes the vector width per index.
    search_embedding_dimensions: int = Field(default=1024, ge=1)
    search_vector_candidates: int = Field(default=50, ge=1, le=1_000)
    search_hybrid_rrf_k: int = Field(default=60, ge=1)
    # Chunks carried per returned document. Ranking still returns one document
    # per slot; this only decides how much of that document comes with it.
    # 6 rather than 4: on docs v2's 120 questions the evidence a document was
    # labelled for sat outside its first four candidate chunks in 9 questions,
    # and every one of those chunks was already in the pool the search fetched.
    # Evidence recall saturates at 16, but the context doubles to get there.
    search_chunks_per_document: int = Field(default=6, ge=1, le=20)
    # Search the question and a model-written rewrite of it, fused. Off by
    # default: on docs v2 it buys one to two questions out of forty and costs
    # roughly half a second per search, and it puts the chat model in the path
    # of a search that otherwise has no model dependency at all.
    search_query_rewrite: bool = False
    # How much the rewrite's ranking counts against the original's. Below 1 so a
    # rewrite that went wrong cannot outvote the question the user actually asked.
    search_query_rewrite_weight: float = Field(default=0.5, gt=0.0, le=1.0)
    # Drop every hit scoring below this fraction of the search's own best score,
    # so a list of ten pads out with near misses no more. A ratio rather than an
    # absolute floor because the three modes score on scales that share no unit,
    # and because the absolute value of a score turned out to carry no signal:
    # on docs v2 the unanswerable questions' best hits scored inside -- often
    # above -- the answerable ones' range, so no floor separates them. The ratio
    # only ever says "this is far worse than the best this search found", which
    # is a claim the scores do support. Calibrated on docs v2's 120 questions;
    # 1.0 keeps the top hit alone, 0.0 disables the cutoff. The top hit always
    # survives a ratio, which measures every hit against the best one, so the
    # ratio alone can never empty a result list. Emptying it is the absolute
    # floor's job, below.
    search_cutoff_ratio_bm25: float = Field(default=0.90, ge=0.0, le=1.0)
    search_cutoff_ratio_vector: float = Field(default=0.99, ge=0.0, le=1.0)
    search_cutoff_ratio_hybrid: float = Field(default=0.95, ge=0.0, le=1.0)
    # Learned-sparse scores are dot products over rank_features, on a scale of
    # their own again. Calibrated on docs v2's 135 questions: sparse scores fall
    # away fast, so 0.90 still returns 1.40 documents at 86.5% precision, and
    # 0.95 is the knee -- 89.4% over 1.25 documents, holding Hit@5 at 91.9%.
    search_cutoff_ratio_sparse: float = Field(default=0.95, ge=0.0, le=1.0)
    # An absolute floor under the ratio cutoff. The ratio only ever says "far
    # worse than the best this search found", so it cannot empty a result list:
    # the top hit is its own reference and always clears it. A floor can, which
    # is the only way a search says "nothing here answers this".
    #
    # Applied per retriever before fusion, not after: RRF scores are built from
    # ranks, so once the lists are fused no absolute value survives to test.
    #
    # Off by default, unlike the ratios above: a ratio is scale free, but these
    # are raw scores, so a shipped number would encode one corpus's statistics.
    # Measured on this deployment's corpus (docs v2, 135 answerable questions
    # against 8 unanswerable and 12 out-of-domain), the lossless point is
    # bm25 14.75 and vector 0.768 -- set there, every out-of-domain query
    # returns nothing in all three modes and 1 of 8 unanswerable ones does.
    # Those values live in .env, where a deployment's own measurement belongs.
    #
    # What this does NOT do is decide relevance. A single rare token can carry
    # a document over the floor, and an in-domain question the corpus cannot
    # answer still scores inside the answerable range -- the reason abstention
    # needs a relevance judge, not a threshold. Raising these past the lossless
    # point trades answered questions for refused ones.
    #
    # BM25 scores move with corpus statistics and vector scores with the
    # embedding model, so BOTH MUST BE RE-MEASURED when either changes.
    # 0.0 disables a floor.
    search_score_floor_bm25: float = Field(default=0.0, ge=0.0)
    search_score_floor_vector: float = Field(default=0.0, ge=0.0)
    # RRF scores carry no relevance signal, so there is nothing to threshold
    # here; the per-retriever floors above already gated what reached fusion.
    search_score_floor_hybrid: float = Field(default=0.0, ge=0.0)
    search_score_floor_sparse: float = Field(default=0.0, ge=0.0)
    # Where the learned-sparse query encoder lives. bge-m3's sparse head is not
    # served by Ollama, so it runs behind its own HTTP endpoint; empty disables
    # the sparse modes rather than failing a search that never asked for them.
    sparse_encoder_url: str = ""
    search_sparse_candidates: int = Field(default=50, ge=1, le=1_000)
    rag_top_k: int = Field(default=5, ge=1)

    def cutoff_ratio(self, mode: str) -> float:
        return {
            "bm25": self.search_cutoff_ratio_bm25,
            "vector": self.search_cutoff_ratio_vector,
            "hybrid": self.search_cutoff_ratio_hybrid,
            "sparse": self.search_cutoff_ratio_sparse,
        }[mode]

    def score_floor(self, mode: str) -> float:
        return {
            "bm25": self.search_score_floor_bm25,
            "vector": self.search_score_floor_vector,
            "hybrid": self.search_score_floor_hybrid,
            "hybrid_sparse": self.search_score_floor_hybrid,
            "sparse": self.search_score_floor_sparse,
        }[mode]

    @property
    def chat_base_url(self) -> str:
        return self.chat_base_url_override or self.ollama_base_url

    @property
    def chat_model(self) -> str:
        return self.chat_model_override or self.ollama_chat_model

    @property
    def document_aliases(self) -> str:
        """Selected document indexes; a single corpus never reads other aliases."""
        aliases = {"core": self.search_index_alias, "docs": self.search_docs_alias}
        return ",".join(dict.fromkeys(aliases[name] for name in self.search_document_datasets.split(",")))


@lru_cache
def get_settings() -> Settings:
    return Settings()
