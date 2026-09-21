"""STT 콜센터 청크 내보내기의 정규화.

원본 내보내기에서는 의도적으로 STT와 분석 필드를 유지한다. 이 모델은 과거 상담이 공식 소스인 것처럼 가장하지 않고, 검색 크기의 청크 하나를 검색 엔진에서 사용하는 안정적인 형태로 바꾼다.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CallCenterChunk(BaseModel):
    model_config = ConfigDict(extra="allow")

    chunk_id: str = Field(min_length=1, max_length=512)
    call_id: str = Field(min_length=1, max_length=512)
    seq: int = Field(ge=0)
    text: str = Field(min_length=1)
    call_inquiry: str = ""
    categories: list[str] = []
    keywords: list[str] = []
    entities: list[dict] = []
    start_sec: float | None = None
    end_sec: float | None = None
    seg_ids: list[str] = []

    @field_validator("chunk_id", "call_id")
    @classmethod
    def validate_id_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 512:
            raise ValueError("OpenSearch document ID must be at most 512 UTF-8 bytes")
        return value

    def index_source(self) -> dict:
        category = self.categories[0] if self.categories else "기타"
        inquiry = self.call_inquiry.strip() or "상담 내용"
        # 문의는 유용한 검색 맥락이지만, 원시 STT는 그대로 유지된다
        # 아래에 있으므로 결과는 항상 과거 사례로 검사할 수 있다.
        body = f"문의 요약: {inquiry}\n\n상담 내용: {self.text}"
        return {
            "id": self.chunk_id,
            "parent_id": self.call_id,
            "title": f"콜센터 상담 사례 · {category}",
            "body": body,
            "source_type": "콜센터 상담 사례",
            "call_id": self.call_id,
            "seq": self.seq,
            "call_inquiry": inquiry,
            "categories": self.categories,
            "keywords": self.keywords,
            "entities": self.entities,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "seg_ids": self.seg_ids,
        }
