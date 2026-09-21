"""임베딩 서비스에 대한 테스트 전역 격리.

`retrieve`는 호출자가 None을 전달할 경우 자체 `OllamaEmbedder`를 생성하므로,
임베딩을 언급하지 않는 테스트도 로컬 Ollama에 연결하게 되며,
실행 중인 머신에 어떤 모델들이 다운로드되어 있는지에 따라 다르게 동작한다.
서비스를 대체함으로써 이를 테스트에서 제외할 수 있다: 벡터 검색의 절반은 embedder를 전달함으로써 테스트된다.
"""

import httpx
import pytest

from search_engine.config import get_settings


@pytest.fixture(autouse=True)
def isolate_local_corpus_settings(monkeypatch):
    """개발자의 코퍼스나 채팅 .env는 기본 계약 테스트를 변경해서는 안 된다."""
    for key, value in {
        "SEARCH_DOCUMENT_DATASETS": "core,docs", "SEARCH_MODE": "hybrid",
        "SEARCH_HSK_ENABLED": "true", "SEARCH_DOCS_ALIAS": "search-docs",
        "SEARCH_DOCS_PREFIX": "search-docs-v",
        "CHAT_PROVIDER": "ollama", "CHAT_BASE_URL_OVERRIDE": "",
        "CHAT_MODEL_OVERRIDE": "", "CHAT_API_KEY": "none",
        # 점수 하한선은 개발자가 실행하는 어떤 코퍼스에 따라 조정된 원시 점수이므로
        # 배포 시의 값이 조용히 결과 목록을 비우게 될 수 있다
        # 이 테스트들이 확인하는 결과 목록
        "SEARCH_SCORE_FLOOR_BM25": "0", "SEARCH_SCORE_FLOOR_VECTOR": "0",
        "SEARCH_SCORE_FLOOR_HYBRID": "0", "SEARCH_SCORE_FLOOR_SPARSE": "0",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def no_ambient_embedding_service(monkeypatch, request):
    """Ollama가 다운된 경우와 같이, 원하지 않는 embedder를 사용할 수 없게 만든다.

    그 경우 검색은 어휘적 검색만으로 저하되며, 이는 embedder를 주입하지 않는 테스트들이 작성된 동작 방식이다.
    """
    if request.node.get_closest_marker("uses_embedding_service"):
        return

    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("no embedding service in tests")

    monkeypatch.setattr("search_engine.search.query.OllamaEmbedder", unavailable)
