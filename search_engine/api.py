from datetime import date
from hmac import compare_digest

from fastapi import Depends, FastAPI, Header, HTTPException
from opensearchpy import OpenSearchException
from pydantic import BaseModel, Field, model_validator

from search_engine.client import create_client
from search_engine.codes import extract, normalize_control
from search_engine.config import get_settings
from search_engine.hsk import retrieve_hsk
from search_engine.search import retrieve

app = FastAPI(title="Strategic Items Search", version="0.1.0")


class SearchRequest(BaseModel):
    query: str = ""
    code: str | None = None
    as_of: date = Field(default_factory=date.today)
    source_types: list[str] = Field(default_factory=list)
    k: int = Field(default=5, ge=1, le=20)

    @model_validator(mode="after")
    def require_search_term(self):
        if not self.query.strip() and not (self.code and self.code.strip()):
            raise ValueError("query or code is required")
        if self.code and not extract(self.code):
            raise ValueError("code must contain a control number or legal reference")
        return self


class HskSearchRequest(BaseModel):
    hsk_code: str | None = None
    control_number: str | None = None
    k: int = Field(default=50, ge=1, le=200)

    @model_validator(mode="after")
    def require_exact_key(self):
        if not (self.hsk_code or (self.control_number and normalize_control(self.control_number))):
            raise ValueError("hsk_code or control_number is required")
        if self.hsk_code and not (len(self.hsk_code) == 10 and self.hsk_code.isdigit()):
            raise ValueError("HSK code must be exactly 10 digits")
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
def search(request: SearchRequest) -> dict:
    settings = get_settings()
    try:
        hits = retrieve(
            create_client(), settings.search_index_alias,
            request.query, request.code, request.as_of,
            request.source_types, request.k,
        )
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="search unavailable") from exc
    return {"query": request.query, "as_of": request.as_of, "hits": hits}


@app.post("/v1/hsk/search", dependencies=[Depends(require_api_key)])
def search_hsk(request: HskSearchRequest) -> dict:
    settings = get_settings()
    try:
        result = retrieve_hsk(
            create_client(), settings.search_hsk_alias,
            request.hsk_code, request.control_number, request.k,
        )
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="HSK search unavailable") from exc
    return {"hsk_code": request.hsk_code,
            "control_number": request.control_number, **result}
