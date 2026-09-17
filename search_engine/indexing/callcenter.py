"""Normalization for the STT call-centre chunk export.

The source export deliberately keeps its STT and analysis fields.  This model
turns one search-sized chunk into the stable shape used by the search engine
without pretending that a past consultation is an official source.
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
        # The inquiry is useful retrieval context, but the raw STT stays intact
        # below it so a result can always be inspected as a past case.
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
