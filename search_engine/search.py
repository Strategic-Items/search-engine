from datetime import date
import re

from opensearchpy import OpenSearch

from search_engine.codes import extract


def _requested_period(query: str) -> tuple[str, str] | None:
    match = re.search(r"(20\d{2})\s*년(?:\s*(\d{1,2})\s*월)?", query)
    if not match:
        return None
    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else None
    if month is not None and not 1 <= month <= 12:
        return None
    if month is None:
        return f"{year}-01-01", f"{year + 1}-01-01"
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    return f"{year}-{month:02d}-01", f"{next_year}-{next_month:02d}-01"


def build_query(query: str, code: str | None, as_of: date, source_types: list[str]) -> dict:
    should = []
    if query.strip():
        should.append({"multi_match": {
            "query": query.strip(),
            "fields": ["title^3", "body", "title.standard^1.5", "body.standard^0.5"],
            "type": "best_fields",
        }})
    if code:
        for normalized in extract(code):
            should.append({"term": {"codes_exact": {"value": normalized, "boost": 6}}})
    if not should:
        raise ValueError("query or code is required")

    filters = [
        {"bool": {"should": [
            {"range": {"effective_from": {"lte": as_of.isoformat()}}},
            {"bool": {"must_not": {"exists": {"field": "effective_from"}}}},
        ], "minimum_should_match": 1}},
        {"bool": {"should": [
            {"range": {"effective_to": {"gt": as_of.isoformat()}}},
            {"bool": {"must_not": {"exists": {"field": "effective_to"}}}},
        ], "minimum_should_match": 1}},
    ]
    if source_types:
        filters.append({"terms": {"source_type": source_types}})

    base = {"bool": {"should": should, "minimum_should_match": 1, "filter": filters}}
    period = _requested_period(query)
    if not period:
        return base
    start, end = period
    functions = [
        {"filter": {"range": {field: {"gte": start, "lt": end}}}, "weight": 6}
        for field in ("published_at", "effective_from")
    ]
    return {"function_score": {"query": base, "functions": functions,
                               "score_mode": "sum", "boost_mode": "sum"}}


def retrieve(
    client: OpenSearch, alias: str, query: str, code: str | None,
    as_of: date, source_types: list[str], k: int,
) -> list[dict]:
    body = {"query": build_query(query, code, as_of, source_types)}
    response = client.search(index=alias, body=body, size=min(k * 5, 100))
    seen = set()
    out = []
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        parent_id = source.get("parent_id") or hit["_id"]
        if parent_id in seen:
            continue
        seen.add(parent_id)
        out.append({
            "id": hit["_id"],
            "parent_id": parent_id,
            "score": hit.get("_score"),
            "title": source.get("title", ""),
            "body": source.get("body", ""),
            "code": source.get("code", ""),
            "source_type": source.get("source_type", "unknown"),
            "source_url": source.get("source_url", ""),
            "published_at": source.get("published_at"),
            "effective_from": source.get("effective_from"),
            "effective_to": source.get("effective_to"),
            "date_basis": source.get("date_basis", "unknown"),
        })
        if len(out) == k:
            break
    return out
