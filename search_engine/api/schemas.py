from pydantic import BaseModel, ConfigDict, model_validator


class SearchRequest(BaseModel):
    """공개 검색 요청. 사용자는 자연어 쿼리만 제공한다."""

    model_config = ConfigDict(extra="forbid")

    query: str = ""

    @model_validator(mode="after")
    def require_search_term(self):
        if not self.query.strip():
            raise ValueError("query is required")
        return self


class RagRequest(BaseModel):
    """지면 기반 RAG 요청; 추가 필드는 의도적으로 거부됨."""

    model_config = ConfigDict(extra="forbid")

    query: str = ""
    session_id: str | None = None

    @model_validator(mode="after")
    def require_search_term(self):
        if not self.query.strip():
            raise ValueError("query is required")
        return self
