from opensearchpy import OpenSearch

from search_engine.codes import normalize_control


def build_hsk_query(hsk_code: str | None, control_number: str | None) -> dict:
    filters = []
    if hsk_code:
        if not (len(hsk_code) == 10 and hsk_code.isdigit()):
            raise ValueError("HSK code must be exactly 10 digits")
        filters.append({"term": {"hsk_code": hsk_code}})
    if control_number:
        normalized = normalize_control(control_number)
        if normalized:
            filters.append({"term": {"control_no_norm": normalized}})
    if not filters:
        raise ValueError("hsk_code or control_number is required")
    return {"bool": {"filter": filters}}


def retrieve_hsk(
    client: OpenSearch, alias: str, hsk_code: str | None,
    control_number: str | None, k: int,
) -> dict:
    response = client.search(
        index=alias,
        body={"query": build_hsk_query(hsk_code, control_number),
              "sort": [{"hsk_code": "asc"}, {"control_no_norm": "asc"}, {"id": "asc"}]},
        size=k,
        track_total_hits=True,
    )
    hits = []
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        hits.append({
            "id": hit["_id"],
            "hsk_code": source.get("hsk_code", ""),
            "control_number": source.get("control_number", ""),
            "name_ko": source.get("name_ko", ""),
            "name_en": source.get("name_en", ""),
            "source_url": source.get("source_url", ""),
            "retrieved_at": source.get("retrieved_at"),
            "linkage_notice": source.get("linkage_notice", ""),
        })
    total = response["hits"].get("total", 0)
    if isinstance(total, dict):
        total = total["value"]
    return {"total": total, "hits": hits}
