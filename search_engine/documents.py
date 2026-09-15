from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from search_engine.codes import extract, normalize_control


class SearchDocument(BaseModel):
    """Stable source ID and validity dates are required for operational indexing."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1)
    body: str = ""
    code: str = ""
    source_type: str = "unknown"
    source_url: str = ""
    parent_id: str | None = None
    published_at: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    content_hash: str | None = None

    @field_validator("id")
    @classmethod
    def validate_id_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 512:
            raise ValueError("OpenSearch document ID must be at most 512 UTF-8 bytes")
        return value

    @field_validator("published_at", "effective_from", "effective_to", mode="before")
    @classmethod
    def parse_source_date(cls, value):
        if value in (None, "", 0):
            return None
        if isinstance(value, int) or (isinstance(value, str) and len(value) == 8 and value.isdigit()):
            return date.fromisoformat(f"{str(value)[:4]}-{str(value)[4:6]}-{str(value)[6:]}")
        return value

    def index_source(self) -> dict:
        source = self.model_dump(mode="json", exclude_none=True)
        source["parent_id"] = self.parent_id or self.id
        source["codes_exact"] = extract(self.code)
        source["code_norm"] = normalize_control(self.code)
        if source.get("source_type") == "HSK 연계표":
            source["control_no_norm"] = normalize_control(str(source.get("control_number", "")))
        return source
