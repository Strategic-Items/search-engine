from datetime import date
import re

from opensearchpy import OpenSearch

from search_engine.hsk import extract_hsk_code, retrieve_hsk
from search_engine.results import SearchHit, SearchResults

PERIOD = re.compile(r"(20\d{2})\s*년(?:\s*(\d{1,2})\s*월)?")


def _requested_period(query: str) -> tuple[str, str] | None:
    """Return the half-open date range a "2024년 3월" style query asks for."""
    match = PERIOD.search(query)
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


def build_query(query: str, as_of: date) -> dict:
    should = []
    if query.strip():
        should.append({"multi_match": {
            "query": query.strip(),
            "fields": ["title^3", "body", "title.standard^1.5", "body.standard^0.5"],
            "type": "best_fields",
        }})
    if not should:
        raise ValueError("query is required")

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
    client: OpenSearch, alias: str, query: str, as_of: date, k: int,
) -> list[SearchHit]:
    body = {"query": build_query(query, as_of)}
    response = client.search(index=alias, body=body, size=min(k * 5, 100))
    seen = set()
    out = []
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        parent_id = source.get("parent_id") or hit["_id"]
        if parent_id in seen:
            continue
        seen.add(parent_id)
        out.append(SearchHit.model_validate({
            **{key: value for key, value in source.items() if value is not None},
            "id": hit["_id"], "parent_id": parent_id, "score": hit.get("_score"),
        }))
        if len(out) == k:
            break
    return out


def search_all(
    client: OpenSearch, alias: str, hsk_alias: str, query: str, as_of: date, k: int = 5,
) -> SearchResults:
    """One user search: documents, plus HSK linkage when the query names a code."""
    hits = retrieve(client, alias, query, as_of, k)
    hsk_code = extract_hsk_code(query)
    linkage = retrieve_hsk(client, hsk_alias, hsk_code, None, k) if hsk_code else None
    return SearchResults(query=query, hits=hits, hsk=linkage)
