"""오프라인 인덱서와 검색 경로에서 공유하는 Ollama 임베딩."""

from collections.abc import Sequence

import httpx

from search_engine.config import Settings, get_settings


def embedding_text(title: str, body: str) -> str:
    """임베딩 모델에 보내는 레이블링된 문서 표현을 생성한다."""
    return f"제목: {title}\n\n본문: {body}".strip()


class OllamaEmbedder:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        response = httpx.post(
            f"{self.settings.ollama_base_url.rstrip('/')}/api/embed",
            json={"model": self.settings.ollama_embedding_model, "input": list(texts)},
            timeout=self.settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        embeddings = response.json().get("embeddings")
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise ValueError("Ollama returned an invalid embedding response")
        out: list[list[float]] = []
        for vector in embeddings:
            if not isinstance(vector, list) or len(vector) != self.settings.search_embedding_dimensions:
                raise ValueError(
                    "embedding dimension does not match SEARCH_EMBEDDING_DIMENSIONS "
                    f"({self.settings.search_embedding_dimensions})"
                )
            out.append([float(value) for value in vector])
        return out

    def embed_query(self, query: str) -> list[float]:
        return self.embed([query])[0]
