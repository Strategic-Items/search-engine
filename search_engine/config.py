"""HTTP 레이어와 독립적인 런타임 설정."""

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
    # 문서 파서에 의해 소스 파일(HWP/HWPX/PDF)에서 파싱된 문서.
    # 별도의 인덱스로, 하나의 코퍼스를 재구성할 때 다른 코퍼스가 손상되지 않도록: 각각의
    # 재구성은 전체 인덱스를 대체한다.
    search_docs_alias: str = "search-docs"
    search_docs_prefix: str = "search-docs-v"
    # 과거 콜센터 사례는 의도적으로 공식
    # 지식/RAG 별칭에서 제외되며, 전용 엔드포인트를 통해만 쿼리된다.
    search_callcenter_alias: str = "search-callcenter"
    search_callcenter_prefix: str = "search-callcenter-v"
    search_hsk_alias: str = "search-hsk"
    search_hsk_prefix: str = "search-hsk-v"
    search_document_datasets: Literal["core,docs", "docs", "core"] = "core,docs"
    search_mode: Literal["bm25", "vector", "hybrid"] = "hybrid"
    search_hsk_enabled: bool = True
    search_number_of_replicas: int = Field(default=0, ge=0)
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:3b"
# 임베딩 모델과 챗 모델을 분리한다: 챗 모델은 일반적으로 훨씬 크며
# Ollama의 임베딩 엔드포인트를 노출하지 않을 수 있다.
# 한국어 전용: 코퍼스와 질문은 모두 한국어이다. 한
# 영어 중심 모델은 이를 거의 무작위로 점수 매긴다.
# 자세한 내용은 docs/evaluation/stages/stage-06-embedding-model.md에 있다. 이를 대체한
# 다국어 bge-m3도 한계가 있었고, 같은 구조를 한국어로 미세 조정한 모델은
# 벡터 MRR@5를 0.9074에서 0.9407로 높였다.
# (docs/evaluation/stages/stage-13-bge-m3-ko.md).
#
# Ollama에서 다른 모델처럼 실행할 수 있도록 GGUF로 제공한다. 제3자가 변환한 모델이므로
# 원본 safetensors와 사전에 대조했다.
# 채택: 25개 쿼리에 대해 코사인 0.99998 이상
# (docs/evaluation/stages/stage-15-adopt-bge-m3-ko.md).
#
# 이 값을 변경하려면 모든 데이터셋의 재인덱싱과 SEARCH_SCORE_FLOOR_VECTOR의 재측정이 필요하다.
# SEARCH_SCORE_FLOOR_VECTOR, 이는 이 모델의 스케일에서의 원시 코사인 값이다.
    ollama_embedding_model: str = "hf.co/Neuwhufbox/BGE-m3-ko-gguf:F16"
    ollama_temperature: float = 0.4
# Ollama는 컨텍스트 창을 초과하는 프롬프트의 앞부분을 조용히 버린다.
# 그러면 지지 규칙이 잘려 증거가 남게 되고, 창문이 될 것이다
# 응답과 프롬프트를 모두 포함한다. 문서당 6개의 조각으로
# longest docs v2 프롬프트는 14,068 토큰을 측정했으며, 16,384는 남는다.
# 답변에 약 2,300 토큰만 사용하므로, 이는 실제 여유 공간을 남겨준다.
# ollama 제공자만 이 값을 읽는다; OpenAI와 호환되는 서버는 이를 수정한다
# 시작 시 창 대신 (vLLM의 --max-model-len).
    ollama_num_ctx: int = Field(default=24576, ge=512)
    ollama_timeout_seconds: float = Field(default=120.0, gt=0)
    # 채팅 모델이 위치한 곳. "ollama"는 OLLAMA_BASE_URL에서 Ollama의 기본 API를 사용한다.
    # "openai"는 CHAT_BASE_URL_OVERRIDE에서 OpenAI와 호환되는 프로토콜(vLLM,
    # SGLang, llama.cpp, LM Studio)을 사용한다. 임베딩은 어떤 경우에도 Ollama에 남는다: 매핑은 벡터 너비를 고정하므로, 이동하면 모든 데이터셋의 재색인을 의미한다.
    # 두 경우 모두 OLLAMA_* 설정으로 되돌아가므로, Ollama만 사용하는 배포에서는 하나의 URL과 하나의 모델 이름만 구성하면 된다.
    # 모든 데이터셋의 재색인을 의미합니다.
    chat_provider: Literal["ollama", "openai"] = "ollama"
    # 둘 다 OLLAMA_* 설정으로 백업하므로, Ollama 전용 배포의 경우
    # 하나의 URL과 하나의 모델 이름을 구성하는 것을 유지한다.
    chat_base_url_override: str = ""
    chat_model_override: str = ""
    # 로컬 서버는 값을 무시하지만 여전히 잘 형성된 헤더를 원한다.
    chat_api_key: str = "none"
    # OLLAMA_EMBEDDING_MODEL과 정확히 일치해야 하며, 둘 중 하나를 변경하면 재인덱싱이 필요하다.
    # 모든 데이터셋의 경우, 매핑이 인덱스당 벡터 너비를 고정하기 때문에.
    search_embedding_dimensions: int = Field(default=1024, ge=1)
    search_vector_candidates: int = Field(default=50, ge=1, le=1_000)
    search_hybrid_rrf_k: int = Field(default=60, ge=1)
    # 반환되는 문서당 포함되는 청크 수. 랭킹은 여전히 하나의 문서를 반환한다.
    # 슬롯당; 이는 단지 그 문서의 어느 정도가 함께 제공되는지를 결정한다.
    # 4보다 6: docs v2의 120개 질문에서 문서가 레이블링된 증거는
    # 첫 네 개의 후보 청크 외부에 있었으며, 9개의 질문에서
    # 그리고 그 모든 청크는 검색이 가져온 풀에 이미 있었다.
    # 증거 검색은 16에서 포화되지만, 그에 도달하기 위해 컨텍스트는 두 배가 된다.
    search_chunks_per_document: int = Field(default=6, ge=1, le=20)
    # 질문과 모델이 작성한 재작성된 질문을 병합하여 검색한다. 오프
    # 기본값: on docs v2에서는 40개 중 1~2개의 질문을 확보하고 비용이
    # 검색당 약 반초이며, 이는 챗 모델을 전혀 모델 의존성이 없는 검색의 경로에 놓는다.
    # 검색이 전혀 모델 의존성이 없는 경우.
    search_query_rewrite: bool = False
    # 재작성된 질문의 순위가 원래 질문의 순위에 얼마나 영향을 미치는가. 1보다 작아야 사용자가 실제로 물은 질문보다 잘못된 재작성된 질문이 우세하지 않도록 한다.
    # 재작성된 질문이 잘못된 경우, 사용자가 실제로 물은 질문보다 우세할 수 없도록 한다.
    search_query_rewrite_weight: float = Field(default=0.5, gt=0.0, le=1.0)
    # 검색의 최고 점수의 이 분율보다 낮은 점수를 받는 모든 히트를 제거한다.
    # 그래서 near misses가 없는 열 개의 패드 리스트. 절대적인 하한이 아니라 비율로 사용한다. 이유는 세 가지 모드의 점수가 공통된 단위를 공유하지 않기 때문이며,
    # 절대적인 바닥값은 세 가지 모드의 점수가 공통된 단위를 공유하지 않기 때문에
    # 그리고 점수의 절대값이 신호를 전달하지 않는다는 것이 밝혀졌기 때문에:
    # docs v2에서 unanswerable 질문의 최고 점수는 내부에서 -- 종종
    # 위쪽 -- 답변 가능한 것들의 범위이므로, floor가 그들을 분리하지 않는다. 비율
    # 항상 "이것은 이 검색이 찾은 최고의 것보다 훨씬 나쁘다"라고만 말한다.
    #는 점수가 지지하는 주장입니다. docs v2의 120개 질문에 대해 캘리브레이션되었습니다;
    # 1.0은 최상위 히트만 유지하고, 0.0은 컷오프를 비활성화한다. 최상위 히트는 항상
    # 비율을 살아남는다. 이는 모든 검색 결과를 최고 성능의 결과와 비교하여 측정하므로, 비율만으로는 결과 목록을 비울 수 없다. 결과 목록을 비우는 것은 아래의 절대 하한값의 역할이다.
    # 비율만으로는 결과 목록을 비울 수 없다. 결과 목록을 비우는 것은 절대
    # 하한값의 임무이다. 아래를 참조.
    search_cutoff_ratio_bm25: float = Field(default=0.90, ge=0.0, le=1.0)
    search_cutoff_ratio_vector: float = Field(default=0.99, ge=0.0, le=1.0)
    # 하이브리드 비율은 RRF 점수에 적용되며, 같은 논리는 성립하지 않는다.
    # 순위 기반 점수는 문서가 얼마나 높은 순위로 검색되었는지를 나타내며, 얼마나 뒤에 순위를 차지했는지도 나타낸다.
    # 따라서 엄격한 비율만으로는 "두 검색기 모두 문서를 발견해야 한다"로 해석된다 ( `_ratio_cut` 참조).
    # 여기서는 두 가지가 이를 대체한다. 목록들은 각각의 스케일에서 잘려진다.
    # 이전에
    # 융합이며, 자체 목록을 이끄는 문서는 이 조건에서 제외된다.
    # 비율 -- 이는 결정에서 목록 수를 제외하게 만드는 것이다.
    # 그 제외 조건으로 인해 값 자체는 크게 중요하지 않게 된다: 0.80과 0.90
    # docs v2의 135에서 반환된 정밀도의 0.4p 이내에서 동일하게 점수를 받았다.
    search_cutoff_ratio_hybrid: float = Field(default=0.90, ge=0.0, le=1.0)
# 비율 cutoff 아래의 절대 하한. 비율은 오직 "매우", "이 검색이 찾은 최고보다 나쁘다"라고만 말하므로 결과 목록을 비울 수 없다:
# 최상위 결과는 자체 참조이며 항상 이를 통과시킨다. 하한은 그렇지 않으며, 이는
# 검색이 "여기에 이에 대한 답변이 없다"고 말하는 유일한 방법이다.
#
# 리트리버별로 융합 전에 적용됨, 융합 후가 아님: RRF 점수는 순위에서 생성되므로
# 리스트가 융합된 후에는 절대값이 남아 테스트할 수 없음.
#
# 위의 비율과 달리 기본적으로 비활성화됨: 비율은 척도에 영향을 받지 않지만, 이들은
# 원시 점수이므로 배포된 숫자는 하나의 코퍼스 통계를 인코딩할 수 있음.
# 이 배포의 코퍼스(문서 v2, 135개의 답변 가능한 질문)
# 8개의 답변 불가능한 질문과 12개의 도메인 외 질문에 대해 측정된 결과, 손실 없는 점은
# bm25 14.75와 벡터 0.768임 -- 여기에 설정하면 모든 도메인 외 쿼리
#는 세 가지 모드 모두에서 아무것도 반환하지 않으며, 8개의 답변 불가능한 질문 중 하나만 반환함.
# 이 값들은 .env에 있으며, 배포의 자체 측정 결과가 포함된다.
#
# 이는 관련성을 결정하지 않는다. 단일한 드문 토큰 하나가
# 문서를 기준선을 넘게 만들 수 있고, 도메인 내 질문이라도 코퍼스가 대답할 수 없는 경우
# 여전히 답변 가능 범위 내에서 점수를 받는다 -- 이는 기피가
# 관련성 판정자(judge)를 필요로 하며, 임계값이 아니라 필요하다는 이유이다. 이 값을 손실 없는
# 지점 이상으로 올리면 답변 가능한 질문이 감소하고 거절되는 질문이 늘어난다.
#
# BM25 점수는 코퍼스 통계와 함께 움직이고, 벡터 점수는 임베딩 모델과 함께 움직이므로, 둘 중 하나가 변경될 때마다 BOTH MUST BE RE-MEASURED
# 둘 다 재측정되어야 한다.
# 0.0은 바닥을 비활성화한다.
    search_score_floor_bm25: float = Field(default=0.0, ge=0.0)
    search_score_floor_vector: float = Field(default=0.0, ge=0.0)
    # RRF 점수에는 관련성 신호가 없으므로 임계값을 설정할 것이 없다.
    # 여기서는; 위의 각 검색기 바닥이 이미 융합에 도달한 것을 가로막았다.
    search_score_floor_hybrid: float = Field(default=0.0, ge=0.0)
    # 검색된 텍스트가 실제로 질문에 답하는지 챗 모델에게 묻고, 아니라고 말하면 아무것도 반환하지 않는다.
    # 같은 이유로 기본적으로 비활성화된다. 쿼리 재작성은: 챗 모델을 검색 경로에 포함시키고, 그렇지 않으면 모델 의존성이 없는 검색을 수행하며, 0.1초가 걸리는 검색에 대해 약 2초가 소요된다.
    #
    #
    #
    #
    # 이는 도메인 내 질문과
    # 코퍼스가 답변할 수 없는 질문을 구분하는 유일한 측정 기준이다. 점수 하한선은 8개 중 0개를 거부하고,
    # 크로스-엔코더 재정렬기기는 8개 중 0개를 거부하며, 판정자는 7개를 거부한다. 그 대가로
    # 코퍼스가 답변할 수 있는 질문의 14.8%도 거부한다. 이것이 이 기능이 기본이 아니라 선택 사항인 이유이다.
    # (docs/evaluation/stages/stage-18-llm-answerability-judge.md).
    # 반환된 각 문서의 자체 청크를 쿼리에 대비하여 재정렬하여,
    search_answerability_judge: bool = False
    # 답변을 담고 있는 청크가 독자(또는 판정자, 또는 RAG)가
    # 답변을 담고 있는 청크는 독자(또는 판독자, 또는 RAG)가
    # prompt) 먼저 보입니다. 이 실행 시 문서는 이미 정렬되어 있습니다;
    # 변경되는 문서는 없습니다.
    #
    # 기본적으로 비활성화되어 있습니다: 약 0.1초 소요되는 검색에 약 1.2초가 추가되며,
    # 이는 쿼리 재작성과 위의 판독기와 동일한 거래입니다.
    #
    # 하이브리드에서만 가치가 있습니다. 벡터 검색은 동일한 임베딩으로 청크를 선택했으므로,
    # 문서 내 순서는 이미 올바르며, 재정렬은 evidence recall@6을 0.0p만큼 이동시킵니다.
    # RRF는 순위를 기반으로 융합하고 그 순서를 혼란스럽게 합니다 -- 하이브리드의 rank-1 evidence recall은 벡터보다 24.6p 낮습니다.

# 재랭킹은 그것을 되사오고 그 이상을 가져온다
# (docs/evaluation/stages/stage-19-chunk-rerank-within-document.md)
    search_rerank_chunks: bool = False
# HTTP 사이카드, 임베딩과 챗과 마찬가지로: 크로스엔코더는 이 과정에서 빠진다.
# {model, query, documents}를 받아들여 각 문서에 대한 점수를 반환하는 모든 엔드포인트는 작동한다.
# 점수를 반환한다.
    search_rerank_base_url: str = "http://localhost:8080"
    # 기본 모델, 한국어에 맞춤 조정된 모델이 아닌. 이 한국어 코퍼스에서
    # `bge-reranker-v2-m3-ko`는 랭크 1에서 9.0p worse였고 랭크 6에서 0.7p better였다 -- 한 가지 요구사항 -- 한국어에 맞춤 조정이 한 것과 반대였다.
    #
    # stage 13에서의 임베딩. 한국어 튜닝은 바이엔코더에 도움이 되었고, 크로스엔코더에는 해로웠다.
    # 양쪽을 바꾸기 전에 다시 측정하라.
    search_rerank_model: str = "BAAI/bge-reranker-v2-m3"
    # 문서의 후보 중 몇 개가 점수를 매겨지는가; 나머지는 순서를 유지한다.
    # 최악의 경우에 대한 상한선이며, 지연 시간 조절 장치가 아니다. 문서 하나당
    # 중앙값에서 8개의 후보를 가지고 있으므로, 이는 약 1%의 후보에만 영향을 준다.
    # p50는 그대로 유지하고 p95는 4분의 1로 줄인다.
    search_rerank_depth: int = Field(default=20, ge=2)
    search_rerank_timeout_seconds: float = Field(default=30.0, gt=0)
    rag_top_k: int = Field(default=5, ge=1)

    # 각 리트리버 목록의 얼마나 들어가서 융합되는가. 위의 컷오프 비율과는 별도로, 다른 질문에 답한다: "아니오"가 아니라
    #
    # 이건 보여줄 만한 가치가 있지만 다른 검색기의 투표를 허용할 만한 가치가 있는가
    # 반대". 벡터의 자체 0.99는 코사인 점수에 비해 너무 좁다
    # 가까이 놓여 있으므로 단일 청크를 허용하고 디ensa 순위를 지정한다
    # RRF는 결합에 도달하지 못하는 것을 읽기 위해 존재한다. docs v2의 135에서 이동
    # 디ensa 트림을 0.99에서 0.97로 변경하면 P@1이 93.3%에서 94.1%로, Hit@5가
    # 96.3%에서 97.0%로 증가한다; 0.90은 둘 다 포기했다(91.1% / 93.3%)
    search_fusion_trim_bm25: float = Field(default=0.90, ge=0.0, le=1.0)
    search_fusion_trim_vector: float = Field(default=0.97, ge=0.0, le=1.0)

    def fusion_trim_ratio(self, retriever: str) -> float:
        return {
            "bm25": self.search_fusion_trim_bm25,
            "vector": self.search_fusion_trim_vector,
        }.get(retriever, 0.0)

    def cutoff_ratio(self, mode: str) -> float:
        return {
            "bm25": self.search_cutoff_ratio_bm25,
            "vector": self.search_cutoff_ratio_vector,
            "hybrid": self.search_cutoff_ratio_hybrid,
        }[mode]

    def score_floor(self, mode: str) -> float:
        return {
            "bm25": self.search_score_floor_bm25,
            "vector": self.search_score_floor_vector,
            "hybrid": self.search_score_floor_hybrid,
        }[mode]

    @property
    def chat_base_url(self) -> str:
        return self.chat_base_url_override or self.ollama_base_url

    @property
    def chat_model(self) -> str:
        return self.chat_model_override or self.ollama_chat_model

    @property
    def document_aliases(self) -> str:
        """선택된 문서 인덱스; 단일 코퍼스는 다른 별칭을 읽지 않는다."""
        aliases = {"core": self.search_index_alias, "docs": self.search_docs_alias}
        return ",".join(dict.fromkeys(aliases[name] for name in self.search_document_datasets.split(",")))


@lru_cache
def get_settings() -> Settings:
    return Settings()
