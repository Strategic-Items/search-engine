"""검색이 반환하는 것. 스토어는 행을 이 모델들로 변환한다."""

from pydantic import BaseModel


class Passage(BaseModel):
    """이미 일치한 문서의 추가적인 조각."""

    id: str
    body: str = ""
    score: float | None = None
    relevance: int | None = None


class SearchHit(BaseModel):
    """부모 문서에 속한 하나의 문서 조각."""

    id: str
    parent_id: str
    # 리트리버가 사용하는 스케일에서의 리트리버 자체 점수.
    score: float | None = None
    title: str = ""
    body: str = ""
    code: str = ""
    source_type: str = "unknown"
    source_url: str = ""
    published_at: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    date_basis: str = "unknown"
    # 동일한 형태의 더 새로운 판이 존재할 때 설정되며, 호출자가 이를 알 수 있도록 한다.
    superseded_by: str | None = None
    # 법령·고시 카테고리에서만 채워진다: 조문·별표 경로와 부모 문서의 속성.
    heading_path: list[str] = []
    doc_type: str = ""
    doc_status: str = ""
    doc_number: str = ""
    issuer: str = ""
    # 이와 동일한 부모의 다른 조각들 중 일치한 것들, 최고 순위부터.
    # 질문에 대한 답변은 종종 다른 조각에 있으며, 그 조각은 이전에 버려졌었다.
    # 질문에 대한 답변은 종종 다른 조각에 있으며, 그 조각은 이전에 버려졌었다.
    # `id`/`body`는 문서의 기본 조각으로 유지된다.
    passages: list[Passage] = []
    chunk_relevance: int | None = None
    # 고립된 콜센터 코퍼스에서만 존재한다. 이들을 선택적으로 유지함으로써
    # 공유 리트리버가 간결하고 유용한 케이스 카드를 반환할 수 있게 한다.
    # 공식 문서 응답 계약을 변경하는 중.
    call_id: str = ""
    call_inquiry: str = ""
    categories: list[str] = []
    start_sec: float | None = None
    end_sec: float | None = None

    @property
    def chunk_ids(self) -> list[str]:
        """이 검색 결과에 포함된 모든 청크, 우선적으로 주요 청크."""
        return [self.id] + [passage.id for passage in self.passages]

    @property
    def bodies(self) -> list[str]:
        return [self.body] + [passage.body for passage in self.passages]


class HskHit(BaseModel):
    """하나의 HSK 연결 행. 결코 최종 전략 항목 결정이 아님."""

    id: str
    hsk_code: str = ""
    control_number: str = ""
    name_ko: str = ""
    name_en: str = ""
    source_url: str = ""
    retrieved_at: str | None = None
    linkage_notice: str = ""


class HskResults(BaseModel):
    total: int
    hits: list[HskHit]


class SearchResults(BaseModel):
    query: str
    hits: list[SearchHit]
    hsk: HskResults | None = None


class ModeResults(BaseModel):
    """한 검색 모드가 쿼리에 대해 반환한 결과와 그 결과를 얻기 위해 소요된 비용."""

    mode: str
    hits: list[SearchHit] = []
    latency_ms: float = 0.0
    # 이 모드만 실패했을 때 설정됨. 전체 요청이 실패한 비교
    # 한 리트리버가 다운되어 발생한 경우 비교 대상이 되는 것을 숨길 수 있으므로,
    # 다운된 모드는 자신의 이유를 보고하고 다른 모드는 여전히 응답한다.
    error: str = ""


class ModeComparison(BaseModel):
    """모든 검색 모드를 통해 동일한 쿼리를 실행한 결과, 측면 비교를 위해."""

    query: str
    modes: list[ModeResults]


class DocumentChunk(BaseModel):
    """문서의 한 조각으로, 문서가 작성된 순서대로."""

    id: str
    body: str = ""


class Document(BaseModel):
    """조각들로 인덱싱된 문서를 다시 조립한 전체 문서.

검색은 조각들을 순위付け하므로, 검색 결과는 공고문 중간에서 잘려 나간 조각을 보여준다. 이를 맥락 속에서 읽는다는 것은 문서를 읽는 것이며, 문서는 인덱스에서 조각들로만 존재한다.
"""

    parent_id: str
    title: str = ""
    code: str = ""
    source_type: str = "unknown"
    source_url: str = ""
    published_at: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    superseded_by: str | None = None
    chunks: list[DocumentChunk] = []
