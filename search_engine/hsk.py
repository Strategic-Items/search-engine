import re

from opensearchpy import OpenSearch

from search_engine.codes import normalize_control
from search_engine.results import HskHit, HskResults

HSK_CODE = re.compile(r"(?<!\d)(?:\d[\s-]?){9}\d(?!\d)")


def extract_hsk_code(text: str) -> str | None:
    """Return the first 10-digit HSK code in text, allowing spaces or hyphens."""
    match = HSK_CODE.search(text)
    if not match:
        return None
    return re.sub(r"[\s-]", "", match.group())


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
) -> HskResults:
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
        hits.append(HskHit.model_validate({
            **{key: value for key, value in source.items() if value is not None},
            "id": hit["_id"],
        }))
    total = response["hits"].get("total", 0)
    if isinstance(total, dict):
        total = total["value"]
    return HskResults(total=total, hits=hits)
