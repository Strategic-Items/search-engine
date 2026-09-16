from datetime import date

from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from opensearchpy import OpenSearchException
from pydantic import BaseModel, ConfigDict, model_validator

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.results import SearchResults
from search_engine.search import search_all
from search_engine.rag import pipeline

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


@app.post("/v1/search")
def search(request: SearchRequest) -> SearchResults:
    settings = get_settings()
    try:
        return search_all(
            create_client(), settings.search_index_alias, settings.search_hsk_alias,
            request.query, date.today(), 5,
        )
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="search unavailable") from exc


@app.post("/v1/rag/stream")
async def rag_stream(request: RagRequest) -> StreamingResponse:
    try:
        turn = await pipeline.prepare_turn(request.query, request.session_id)
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="search unavailable") from exc
    return StreamingResponse(
        _as_sse(pipeline.stream_answer(turn)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


async def _as_sse(chunks: AsyncIterator[str | pipeline.StreamError]) -> AsyncIterator[str]:
    async for chunk in chunks:
        if isinstance(chunk, pipeline.StreamError):
            yield f"event: error\ndata: {chunk.message}\n\n"
            return
        # SSE requires each physical line to carry a data prefix.
        payload = "\n".join(f"data: {line}" for line in chunk.splitlines() or [""])
        yield f"{payload}\n\n"
    yield "event: done\ndata: done\n\n"
