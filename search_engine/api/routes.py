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
EVALUATION_REPORT = EVALUATION_DATA / "generated/docs-v2/evaluation-135q-docs-only.json"
ANSWERABILITY_REPORT = EVALUATION_DATA / "generated/docs-v2/judge-most-fields.json"


def _retrieval_outcomes() -> dict[str, dict]:
    """평가 브라우저가 쓰는 공개된 @5 결과. 채점 단위는 문서가 아니라 청크다.

    답변 모델이 받는 것은 문서가 아니라 창(문서 5개 × 문서당 청크)에 실린 청크이므로,
    질문의 성패도 라벨된 근거 청크가 그 창에 실렸는지로 가른다. 문서 순위는 실패의
    원인을 "문서를 못 찾았다"와 "문서 안에서 잘못 골랐다"로 가르는 진단용으로만 남긴다.
    """
    if not EVALUATION_REPORT.is_file():
        return {}
    report = json.loads(EVALUATION_REPORT.read_text(encoding="utf-8"))
    outcomes = {}
    for row in report.get("queries", []):
        groups = [set(group) for group in row.get("evidence_groups", []) if group]
        if not groups:
            continue
        # 창은 문서 우선으로 편다. 컨텍스트에 실리는 순서 그대로다.
        window = [chunk for document in row.get("returned_chunks", [])[:5] for chunk in document]
        offered = set(window)
        found = [group for group in groups if group & offered]
        rank = next(
            (index for index, chunk in enumerate(window, 1)
             if any(chunk in group for group in groups)),
            None,
        )
        gold = set(row.get("gold", []))
        document_rank = next(
            (index for index, parent in enumerate(row.get("returned", [])[:5], 1) if parent in gold),
            None,
        )
        outcomes[row["qid"]] = {
            "evaluation_status": "search_miss" if not found else
                "evidence_miss" if len(found) < len(groups) else "pass",
            "evaluation_rank": rank,
            "evidence_found": len(found),
            "evidence_required": len(groups),
            "document_rank": document_rank,
        }
    return outcomes


def _answerability_outcomes() -> dict[str, dict]:
    """최신 무응답 판정 실행의 공개 결과를 평가 브라우저에 붙인다."""
    if not ANSWERABILITY_REPORT.is_file():
        return {}
    report = json.loads(ANSWERABILITY_REPORT.read_text(encoding="utf-8"))
    return {
        row["qid"]: {
            "evaluation_status": (
                "rejection_pass" if row.get("judge_rejected") else "answer_exposed"
            ),
        }
        for row in report.get("rows", [])
        if row.get("set") == "unanswerable"
    }


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
    """기권 사례를 포함한 프레젠테이션 질문 은행을 반환한다."""
    groups = (
        ("answerable", EVALUATION_DATA / "queries_docs_v2.jsonl"),
        ("unanswerable", EVALUATION_DATA / "queries_docs_v2_unanswerable.jsonl"),
        ("out_of_domain", EVALUATION_DATA / "queries_docs_v2_out_of_domain.jsonl"),
    )
    questions = []
    outcomes = {**_retrieval_outcomes(), **_answerability_outcomes()}
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
                    # 채점 단위인 근거 청크. `gold`(부모 문서)는 진단용으로 남긴다.
                    "evidence_groups": row.get("evidence_groups", []),
                    "evidence_gold": [
                        chunk for group in row.get("evidence_groups", []) for chunk in group
                    ],
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
    """모든 모드에서 동시에 동일한 쿼리를 수행하여 눈으로 비교한다."""
    settings = get_settings()
    try:
        return search_modes(
            create_client(), settings.document_aliases, request.query, date.today(), 5,
        )
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="search unavailable") from exc


# 사용자가 카테고리를 고르고 검색한다. 카테고리마다 인덱스를 따로 두므로 새 카테고리는 여기에 한 줄을 더하면 된다.
# (id, 표시 이름, 별칭을 읽을 설정 이름)
CATEGORIES = {
    "law": ("법령·고시", "search_law_alias"),
}
# .env의 절대 하한과 답변 가능성 판정은 docs v2 코퍼스에서 맞춘 값이다. BM25는 코퍼스 통계와 함께 움직여서
# 청크 673개짜리 법령 인덱스에서는 모든 결과를 자른다(21문항 중 10문항이 빈 결과). 카테고리별로 따로 재기 전까지 끈다.
CATEGORY_SCORE_FLOOR = 0.0


def _category_alias(category: str) -> str:
    if category not in CATEGORIES:
        raise HTTPException(status_code=404, detail="unknown category")
    return getattr(get_settings(), CATEGORIES[category][1])


@app.get("/v1/categories")
def list_categories() -> dict:
    client = create_client()
    categories = []
    for category_id, (label, alias_setting) in CATEGORIES.items():
        try:
            count = client.count(index=getattr(get_settings(), alias_setting), ignore_unavailable=True)["count"]
        except OpenSearchException:
            count = None
        categories.append({"id": category_id, "label": label, "chunks": count})
    return {"categories": categories}


@app.post("/v1/categories/{category}/search/compare")
def search_category_compare(category: str, request: SearchRequest) -> ModeComparison:
    alias = _category_alias(category)
    try:
        return search_modes(
            create_client(), alias, request.query, date.today(), 5,
            score_floor=CATEGORY_SCORE_FLOOR, answerability=False,
        )
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="category search unavailable") from exc


@app.get("/v1/categories/{category}/documents/{parent_id:path}")
def read_category_document(category: str, parent_id: str) -> Document:
    alias = _category_alias(category)
    try:
        document = fetch_document(create_client(), alias, parent_id)
    except OpenSearchException as exc:
        raise HTTPException(status_code=503, detail="category search unavailable") from exc
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    return document


@app.post("/v1/callcenter/search")
def search_callcenter(request: SearchRequest) -> SearchResults:
    """과거 상담 사례만 검색; 공식 RAG에 혼합하지 않는다."""
    settings = get_settings()
    try:
# 하이브리드 검색기를 재사용하지만, 별칭에는 별도의
# 콜센터 코퍼스만 포함되며 Settings.document_aliases의 일부가 아니다.
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
    """한 과거 상담 사례에 대한 모든 인덱싱된 청크를 반환한다."""
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
    """검색 결과가 나온 전체 문서를 청크별로 순서대로 제공한다."""
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
        # SSE는 각 물리 라인에 데이터 접두사를 포함해야 한다.
        payload = "\n".join(f"data: {line}" for line in chunk.splitlines() or [""])
        yield f"{payload}\n\n"
    yield "event: done\ndata: done\n\n"
