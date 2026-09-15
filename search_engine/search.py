from datetime import date

from opensearchpy import OpenSearch


def build_query(query: str, code: str | None, as_of: date, source_types: list[str]) -> dict:
    should = []
    if query.strip():
        should.append({"multi_match": {
            "query": query.strip(),
            "fields": ["title^3", "body", "title.standard^1.5", "body.standard^0.5"],
            "type": "best_fields",
        }})
    if code:
        normalized = "".join(code.upper().split())
        if normalized:
            should.append({"term": {"code_norm": {"value": normalized, "boost": 6}}})
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

    return {"bool": {"should": should, "minimum_should_match": 1, "filter": filters}}


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
        })
        if len(out) == k:
            break
    return out
