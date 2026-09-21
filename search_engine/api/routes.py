from datetime import date
import json
from pathlib import Path

from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from opensearchpy import OpenSearchException

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.api.schemas import RagRequest, SearchRequest
from search_engine.rag import pipeline
from search_engine.search import (
    Document,
    ModeComparison,
    SearchResults,
    fetch_document,
    search_all,
    search_modes,
)

app = FastAPI(title="Strategic Items Search", version="0.1.0")

EVALUATION_DATA = Path(__file__).resolve().parents[2] / "data"
EVALUATION_REPORT = EVALUATION_DATA / "generated/docs-v2/comparison-135q-koemb-gguf.json"


def _retrieval_outcomes() -> dict[str, dict]:
    """Published hybrid @5 outcomes used by the evaluation browser."""
    if not EVALUATION_REPORT.is_file():
        return {}
    report = json.loads(EVALUATION_REPORT.read_text(encoding="utf-8"))
    rows = report.get("modes", {}).get("hybrid", {}).get("queries", [])
    outcomes = {}
    for row in rows:
        returned = row.get("returned", [])[:5]
        gold = set(row.get("gold", []))
        rank = next((index for index, parent in enumerate(returned, 1) if parent in gold), None)
        offered = {chunk for document in row.get("returned_chunks", [])[:5] for chunk in document}
        evidence_groups = row.get("evidence_groups", [])
        evidence_found = bool(evidence_groups) and all(set(group) & offered for group in evidence_groups)
        outcomes[row["qid"]] = {
            "evaluation_status": "search_miss" if rank is None else
                "evidence_miss" if not evidence_found else "pass",
            "evaluation_rank": rank,
        }
    return outcomes


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


@app.get("/v1/evaluation/questions")
def evaluation_questions() -> dict:
    """Return the presentation question bank, including abstention cases."""
    groups = (
        ("answerable", EVALUATION_DATA / "queries_docs_v2.jsonl"),
        ("unanswerable", EVALUATION_DATA / "queries_docs_v2_unanswerable.jsonl"),
        ("out_of_domain", EVALUATION_DATA / "queries_docs_v2_out_of_domain.jsonl"),
    )
    questions = []
    outcomes = _retrieval_outcomes()
    for group, path in groups:
        with path.open(encoding="utf-8") as rows:
            for line in rows:
                if not line.strip():
                    continue
                row = json.loads(line)
                questions.append({
                    "id": row["qid"],
                    "group": group,
                    "category": row.get("category", ""),
                    "question": row["query"],
                    "answerable": row.get("answerable", bool(row.get("gold"))),
                    "reference_answer": row.get("reference_answer", ""),
                    "gold": row.get("gold", []),
                    "reason": row.get("reason", ""),
                    "expected_behavior": row.get("expected_behavior", ""),
                    **outcomes.get(row["qid"], {}),
                })
    return {"total": len(questions), "questions": questions}


@app.post("/v1/search")
def search(request: SearchRequest) -> SearchResults:
    settings = get_settings()
    try:
        return search_all(
            create_client(), settings.document_aliases, settings.search_hsk_alias,
            request.query, date.today(), 5,
        )
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="search unavailable") from exc


@app.post("/v1/search/compare")
def search_compare(request: SearchRequest) -> ModeComparison:
    """The same query through every mode at once, for comparing them by eye."""
    settings = get_settings()
    try:
        return search_modes(
            create_client(), settings.document_aliases, request.query, date.today(), 5,
        )
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="search unavailable") from exc


@app.post("/v1/callcenter/search")
def search_callcenter(request: SearchRequest) -> SearchResults:
    """Search past consultation cases only; never mix them into official RAG."""
    settings = get_settings()
    try:
        # Reuse the hybrid retriever, but the alias contains only the separate
        # call-centre corpus and is not part of Settings.document_aliases.
        return SearchResults(
            query=request.query,
            hits=search_all(
                create_client(), settings.search_callcenter_alias, "", request.query,
                date.today(), 10,
            ).hits,
        )
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="callcenter search unavailable") from exc


@app.get("/v1/callcenter/calls/{call_id}")
def read_callcenter_call(call_id: str) -> Document:
    """Return all indexed chunks for one past consultation case."""
    settings = get_settings()
    try:
        document = fetch_document(create_client(), settings.search_callcenter_alias, call_id)
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="callcenter search unavailable") from exc
    if document is None:
        raise HTTPException(status_code=404, detail="call not found")
    return document


@app.get("/v1/documents/{parent_id:path}")
def read_document(parent_id: str) -> Document:
    """The whole document a search hit came from, chunk by chunk in order."""
    settings = get_settings()
    try:
        document = fetch_document(create_client(), settings.document_aliases, parent_id)
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="search unavailable") from exc
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return document


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
