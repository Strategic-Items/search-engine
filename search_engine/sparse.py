"""SPLADE 희소 벡터 인코더: 색인할 때 문서를, 검색할 때 질의를 같은 방식으로 만든다.

38단계에서 파인튜닝한 모델(설정 C)을 `SEARCH_SPLADE_MODEL` 경로에서 읽는다. torch·transformers는
무거운 선택 의존성이라(`pip install .[sparse]`) 모델을 쓰는 순간에만 가져온다.
"""

from collections.abc import Sequence
from functools import lru_cache

from search_engine.config import Settings, get_settings

# OpenSearch rank_features 필드는 필드 이름에 숫자만 오는 것을 꺼려서 토큰 ID 앞에 접두어를 붙인다.
TERM_PREFIX = "t"


def sparse_enabled(settings: Settings | None = None) -> bool:
    return bool((settings or get_settings()).search_splade_model)


def sparse_terms(weights: dict[int, float], top_terms: int) -> dict[str, float]:
    """가중치가 큰 term만 남겨 rank_features·neural_sparse가 읽는 모양으로 만든다."""
    best = sorted(weights.items(), key=lambda item: -item[1])[:top_terms]
    return {f"{TERM_PREFIX}{token}": round(weight, 4) for token, weight in best}


class SparseEncoder:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        if not self.settings.search_splade_model:
            raise RuntimeError("SEARCH_SPLADE_MODEL is not set")
        try:
            import torch
            from transformers import AutoModelForMaskedLM, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - 설치 환경에 따라 다르다
            raise RuntimeError("SPLADE needs torch and transformers: pip install .[sparse]") from exc
        self._torch = torch
        path = self.settings.search_splade_model
        self._tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
        self._device = "mps" if torch.backends.mps.is_available() else "cpu"
        self._model = AutoModelForMaskedLM.from_pretrained(
            path, trust_remote_code=True).to(self._device).eval()

    def encode(self, texts: Sequence[str], max_length: int, batch_size: int = 8) -> list[dict[str, float]]:
        torch, settings = self._torch, self.settings
        vectors: list[dict[str, float]] = []
        for start in range(0, len(texts), batch_size):
            batch = self._tokenizer(
                list(texts[start:start + batch_size]), padding=True, truncation=True,
                max_length=max_length, return_tensors="pt").to(self._device)
            with torch.inference_mode():
                logits = self._model(**batch).logits
                pooled = torch.log1p(torch.relu(logits)).masked_fill(
                    ~batch["attention_mask"].bool().unsqueeze(-1), 0).amax(dim=1).cpu()
            for row in pooled:
                active = torch.nonzero(row >= settings.search_splade_min_weight).flatten()
                vectors.append(sparse_terms({int(i): float(row[i]) for i in active},
                                            settings.search_splade_top_terms))
        return vectors

    def encode_documents(self, texts: Sequence[str]) -> list[dict[str, float]]:
        return self.encode(texts, self.settings.search_splade_doc_max_length)

    def encode_query(self, query: str) -> dict[str, float]:
        return self.encode([query], self.settings.search_splade_query_max_length)[0]


@lru_cache(maxsize=1)
def get_encoder() -> SparseEncoder:
    """모델 로드는 느리니(수 초) 프로세스에서 한 번만 한다."""
    return SparseEncoder()


@lru_cache(maxsize=256)
def encode_query(query: str) -> dict[str, float]:
    """같은 질문을 모드마다 다시 인코딩하지 않는다."""
    return get_encoder().encode_query(query)
