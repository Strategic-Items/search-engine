from datetime import date
from hmac import compare_digest

from fastapi import Depends, FastAPI, Header, HTTPException
from opensearchpy import OpenSearchException
from pydantic import BaseModel, ConfigDict, model_validator

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.results import SearchResults
from search_engine.search import search_all

app = FastAPI(title="Strategic Items Search", version="0.1.0")


class SearchRequest(BaseModel):
    """The public search request. Users provide only a natural-language query."""

    model_config = ConfigDict(extra="forbid")

    query: str = ""

    @model_validator(mode="after")
    def require_search_term(self):
        if not self.query.strip():
            raise ValueError("query is required")
        return self


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    configured = get_settings().search_api_key
    if not configured:
        raise HTTPException(status_code=503, detail="search API key is not configured")
    if x_api_key is None or not compare_digest(x_api_key, configured):
        raise HTTPException(status_code=401, detail="invalid API key")


@app.get("/health/live")
def live() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict:
    try:
        if not create_client().ping():
            raise HTTPException(status_code=503, detail="OpenSearch unavailable")
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="OpenSearch unavailable") from exc
    return {"status": "ok"}


@app.post("/v1/search", dependencies=[Depends(require_api_key)])
def search(request: SearchRequest) -> SearchResults:
    settings = get_settings()
    try:
        return search_all(
            create_client(), settings.search_index_alias, settings.search_hsk_alias,
            request.query, date.today(), 5,
        )
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="search unavailable") from exc
