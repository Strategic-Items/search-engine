from datetime import date
import logging
import re
from collections.abc import Iterable

import httpx
from opensearchpy import OpenSearch

from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search.hsk import extract_hsk_code, retrieve_hsk
from search_engine.search.results import SearchHit, SearchResults

log = logging.getLogger(__name__)

PERIOD = re.compile(r"(20\d{2})\s*년(?:\s*(\d{1,2})\s*월)?")

# The request carries only a query, so the kind of document a user is asking for
# has to be read from the text. These lift a kind rather than filter to it: a
# misread costs some rank, never the answer itself.
GUIDE_TYPES = ("판정 안내", "허가 안내", "이용 안내")
FORM_TYPES = ("민원서식",)
INTENT_HINTS = (
    (GUIDE_TYPES, re.compile(r"절차|방법|순서|어떻게|하려면|무엇인가요|어디서|이용방법")),
    (FORM_TYPES, re.compile(r"서식|양식|신청서|서약서|진술서|별표|별지|내려받기|다운로드")),
)
SOURCE_TYPE_WEIGHT = 14
# A form that a newer edition replaced stays searchable -- people ask for an
# earlier edition by its year -- but the current one answers first by default.
CURRENT_EDITION_WEIGHT = 4


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


def _intent_boosts(query: str) -> list[dict]:
    """Boost the document kinds the query asks for, in the words users use."""
    return [
        {"filter": {"terms": {"source_type": list(types)}}, "weight": SOURCE_TYPE_WEIGHT}
        for types, hint in INTENT_HINTS if hint.search(query)
    ]


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
    functions = _intent_boosts(query)
    functions.append({
        "filter": {"bool": {"must_not": {"exists": {"field": "superseded_by"}}}},
        "weight": CURRENT_EDITION_WEIGHT,
    })
    period = _requested_period(query)
    if period:
        start, end = period
        functions += [
            {"filter": {"range": {field: {"gte": start, "lt": end}}}, "weight": 6}
            for field in ("published_at", "effective_from")
        ]
    if not functions:
        return base
    return {"function_score": {"query": base, "functions": functions,
                               "score_mode": "sum", "boost_mode": "sum"}}


def _validity_filters(as_of: date) -> list[dict]:
    """Filters duplicated for k-NN, whose query cannot use function_score."""
    return [
        {"bool": {"should": [
            {"range": {"effective_from": {"lte": as_of.isoformat()}}},
            {"bool": {"must_not": {"exists": {"field": "effective_from"}}}},
        ], "minimum_should_match": 1}},
        {"bool": {"should": [
            {"range": {"effective_to": {"gt": as_of.isoformat()}}},
            {"bool": {"must_not": {"exists": {"field": "effective_to"}}}},
        ], "minimum_should_match": 1}},
    ]


def build_vector_query(vector: list[float], as_of: date, candidates: int) -> dict:
    """Approximate HNSW cosine search, constrained to currently valid records."""
    return {"knn": {"embedding": {
        "vector": vector,
        "k": candidates,
        "filter": {"bool": {"filter": _validity_filters(as_of)}},
    }}}


def _warn_on_partial_results(response: dict, retriever: str) -> None:
    """Say so when an index drops out of a search instead of losing it quietly.

    Searching several indexes at once returns 200 even when a shard fails, so a
    whole index can vanish from a rank list with no visible error -- an index
    built before the vector mapping contributes nothing to k-NN, and RRF then
    buries every document in it. That is a reindex, not a query bug, and it is
    only actionable if it is visible.
    """
    shards = response.get("_shards", {})
    if not shards.get("failed"):
        return
    for failure in shards.get("failures", []):
        log.warning("%s search skipped index %s: %s", retriever, failure.get("index"),
                    failure.get("reason", {}).get("reason"))


def _rrf(hits_by_retriever: Iterable[list[dict]], rrf_k: int) -> list[dict]:
    """Fuse rank lists without comparing BM25 scores to cosine similarities."""
    fused: dict[str, tuple[float, dict]] = {}
    for hits in hits_by_retriever:
        seen_in_list: set[str] = set()
        for rank, hit in enumerate(hits, 1):
            source = hit["_source"]
            parent_id = source.get("parent_id") or hit["_id"]
            if parent_id in seen_in_list:
                continue
            seen_in_list.add(parent_id)
            score, exemplar = fused.get(parent_id, (0.0, hit))
            fused[parent_id] = (score + 1 / (rrf_k + rank), exemplar)
    return [
        {**hit, "_score": score}
        for score, hit in sorted(fused.values(), key=lambda pair: (-pair[0], pair[1]["_id"]))
    ]


def retrieve(
    client: OpenSearch, alias: str, query: str, as_of: date, k: int,
    embedder: OllamaEmbedder | None = None,
) -> list[SearchHit]:
    """Retrieve from `alias`, which may name several indexes, comma separated.

    Searches ignore an index that does not exist yet: a corpus that has never
    been indexed should narrow the results, not fail the request.
    """
    settings = get_settings()
    lexical_candidates = min(k * 5, 100)
    vector_candidates = min(max(k * 5, settings.search_vector_candidates), 1000)
    lexical = client.search(
        index=alias, body={"query": build_query(query, as_of)},
        size=lexical_candidates, ignore_unavailable=True,
    )
    _warn_on_partial_results(lexical, "lexical")
    ranked_lists = [lexical["hits"]["hits"]]
    try:
        vector = (embedder or OllamaEmbedder(settings)).embed_query(query.strip())
        semantic = client.search(
            index=alias,
            body={"query": build_vector_query(vector, as_of, vector_candidates)},
            size=vector_candidates,
            ignore_unavailable=True,
        )
        _warn_on_partial_results(semantic, "vector")
        ranked_lists.append(semantic["hits"]["hits"])
    except httpx.HTTPError:
        # Lexical search remains available during an embedding service outage.
        pass

    out = []
    for hit in _rrf(ranked_lists, settings.search_hybrid_rrf_k):
        source = hit["_source"]
        parent_id = source.get("parent_id") or hit["_id"]
        out.append(SearchHit.model_validate({
            **{key: value for key, value in source.items() if value is not None},
            "id": hit["_id"], "parent_id": parent_id, "score": hit.get("_score"),
        }))
        if len(out) == k:
            break
    return _with_current_editions(client, alias, out, k)


def _current_editions(
    client: OpenSearch, alias: str, hits: list[SearchHit],
) -> dict[str, SearchHit]:
    """The editions that replaced any superseded hit, keyed by what they replace.

    A retired form keeps its old title while the current one may have been
    renamed -- the 38th revision rewrote several into English -- so a query in
    the old words reaches only the retired document. Following the pointer is
    the only way those words reach the form now in force.
    """
    wanted = {hit.superseded_by for hit in hits if hit.superseded_by}
    wanted -= {hit.parent_id for hit in hits}
    if not wanted:
        return {}
    response = client.search(
        index=alias,
        body={"query": {"bool": {"filter": [{"terms": {"parent_id": sorted(wanted)}}]}},
              "sort": [{"id": "asc"}]},
        size=len(wanted) * 2,
        ignore_unavailable=True,
    )
    editions = {}
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        parent_id = source.get("parent_id") or hit["_id"]
        if parent_id in editions:
            continue
        editions[parent_id] = SearchHit.model_validate({
            **{key: value for key, value in source.items() if value is not None},
            "id": hit["_id"], "parent_id": parent_id, "score": None,
        })
    return editions


def _with_current_editions(
    client: OpenSearch, alias: str, hits: list[SearchHit], k: int,
) -> list[SearchHit]:
    """Put each replacement right behind the retired document that names it."""
    editions = _current_editions(client, alias, hits)
    if not editions:
        return hits
    merged: list[SearchHit] = []
    present = {hit.parent_id for hit in hits}
    for hit in hits:
        merged.append(hit)
        replacement = editions.get(hit.superseded_by)
        if replacement and replacement.parent_id not in present:
            merged.append(replacement)
            present.add(replacement.parent_id)
    return merged[:k]


def search_all(
    client: OpenSearch, alias: str, hsk_alias: str, query: str, as_of: date, k: int = 5,
) -> SearchResults:
    """One user search: documents, plus HSK linkage when the query names a code."""
    hits = retrieve(client, alias, query, as_of, k)
    hsk_code = extract_hsk_code(query)
    linkage = retrieve_hsk(client, hsk_alias, hsk_code, None, k) if hsk_code else None
    return SearchResults(query=query, hits=hits, hsk=linkage)
