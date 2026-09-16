from pydantic import BaseModel, ConfigDict, model_validator


class SearchRequest(BaseModel):
    """The public search request. Users provide only a natural-language query."""

    model_config = ConfigDict(extra="forbid")

    query: str = ""

    @model_validator(mode="after")
    def require_search_term(self):
        if not self.query.strip():
            raise ValueError("query is required")
        return self


class RagRequest(BaseModel):
    """A grounded RAG request; extra fields are deliberately rejected."""

    model_config = ConfigDict(extra="forbid")

    query: str = ""
    session_id: str | None = None

    @model_validator(mode="after")
    def require_search_term(self):
        if not self.query.strip():
            raise ValueError("query is required")
        return self
