"""What a search returns. The stores translate their rows into these models."""

from pydantic import BaseModel


class SearchHit(BaseModel):
    """One document chunk, with the parent it belongs to."""

    id: str
    parent_id: str
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
    # Set when a newer edition of the same form exists, so a caller can say so.
    superseded_by: str | None = None


class HskHit(BaseModel):
    """One HSK linkage row. Never a final strategic-items determination."""

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
