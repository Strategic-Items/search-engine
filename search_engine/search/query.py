from datetime import date
import logging
import re
from time import perf_counter
from collections.abc import Iterable

import httpx
from opensearchpy import OpenSearch, OpenSearchException

from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search.hsk import extract_hsk_code, retrieve_hsk
from search_engine.search.rewrite import rewrite_query
from search_engine.search.results import (
    ModeComparison,
    ModeResults,
    Passage,
    SearchHit,
    SearchResults,
)

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


def _cutoff(ranked: list[dict], ratio: float) -> float:
    """The score below which a hit is too far behind this search's best to show.

    Taken from the best score rather than a fixed number: the modes score on
    scales that share no unit, and a score's absolute value says nothing about
    whether the document answers the question -- on docs v2 the unanswerable
    questions' best hits outscored plenty of answerable ones. What a score does
    support is a comparison within one search, which is all this makes.
    """
    top = next((hit["_score"] for hit in ranked if hit.get("_score") is not None), None)
    # A negative or zero best score would make the ratio meaningless; keep everything.
    if not ratio or top is None or top <= 0:
        return float("-inf")
    return top * ratio


def _rrf(ranked_lists: Iterable[tuple[list[dict], float]], rrf_k: int) -> list[dict]:
    """Fuse weighted rank lists without comparing BM25 scores to cosine similarities.

    The weight is what keeps an unreliable list from outvoting a reliable one: a
    rewritten query contributes at a fraction of the original's, so a rewrite that
    went wrong can add a document but cannot push the original's best answer down.
    """
    fused: dict[str, tuple[float, dict]] = {}
    for hits, weight in ranked_lists:
        seen_in_list: set[str] = set()
        for rank, hit in enumerate(hits, 1):
            source = hit["_source"]
            parent_id = source.get("parent_id") or hit["_id"]
            if parent_id in seen_in_list:
                continue
            seen_in_list.add(parent_id)
            score, exemplar = fused.get(parent_id, (0.0, hit))
            fused[parent_id] = (score + weight / (rrf_k + rank), exemplar)
    return [
        {**hit, "_score": score}
        for score, hit in sorted(fused.values(), key=lambda pair: (-pair[0], pair[1]["_id"]))
    ]


def _candidates_by_parent(
    ranked_lists: Iterable[tuple[list[dict], float]],
) -> dict[str, list[dict]]:
    """Group every candidate chunk under its parent, best rank first.

    A retriever's own ranking orders the chunks within a parent; a hybrid search
    then appends whatever only the other retriever found. Which parents come back
    is already settled before this runs, so the ordering here only decides which
    chunks of a parent are shown, never which documents.
    """
    by_parent: dict[str, list[dict]] = {}
    seen: set[str] = set()
    for hits, _weight in ranked_lists:
        for hit in hits:
            if hit["_id"] in seen:
                continue
            seen.add(hit["_id"])
            parent = hit["_source"].get("parent_id") or hit["_id"]
            by_parent.setdefault(parent, []).append(hit)
    return by_parent


def _with_passages(
    hits: list[SearchHit], ranked_lists: Iterable[tuple[list[dict], float]],
    chunks_per_document: int,
) -> list[SearchHit]:
    """Carry the document's other matching chunks alongside the one that ranked it.

    One chunk per document is the right unit for ranking documents but the wrong
    unit for answering: on the docs v2 set the labelled evidence sat in a chunk
    the deduplication dropped for 23 of 40 questions, even though its document
    was already first. The extra chunks come out of the candidate pool the search
    already fetched, so this costs no further round trip.
    """
    if chunks_per_document < 2:
        return hits
    by_parent = _candidates_by_parent(ranked_lists)
    for hit in hits:
        others = [c for c in by_parent.get(hit.parent_id, []) if c["_id"] != hit.id]
        hit.passages = [
            Passage(id=c["_id"], body=c["_source"].get("body", ""), score=c.get("_score"))
            for c in others[:chunks_per_document - 1]
        ]
    return hits


def _rewritten_queries(query: str, strict: bool) -> list[str]:
    """The rewrite to search alongside the question, or nothing.

    A rewrite is an enrichment, not a dependency: if the model is down the
    original question still searches fine, so an outage narrows the result set
    rather than failing the request. `strict` evaluation runs refuse that
    silence, because a comparison that quietly dropped the rewrite would be
    measuring the wrong thing.
    """
    try:
        rewritten = rewrite_query(query)
    except httpx.HTTPError:
        if strict:
            raise
        log.warning("query rewrite unavailable; searching the original query only")
        return []
    return [rewritten] if rewritten else []


def retrieve(
    client: OpenSearch, alias: str, query: str, as_of: date, k: int,
    embedder: OllamaEmbedder | None = None,
    *, mode: str | None = None, strict: bool = False,
    chunks_per_document: int | None = None, query_rewrite: bool | None = None,
    cutoff_ratio: float | None = None,
) -> list[SearchHit]:
    """Retrieve from `alias`, which may name several indexes, comma separated.

    Searches ignore an index that does not exist yet: a corpus that has never
    been indexed should narrow the results, not fail the request.
    """
    settings = get_settings()
    mode = mode or settings.search_mode
    if mode not in ("bm25", "vector", "hybrid"):
        raise ValueError(f"unknown search mode: {mode}")
    if k < 1:
        raise ValueError("k must be positive")
    ranked_lists: list[tuple[list[dict], float]] = []

    def add_response(response: dict, name: str, weight: float = 1.0) -> None:
        _warn_on_partial_results(response, name)
        if strict and (response.get("_shards", {}).get("failed", 0) or response.get("timed_out")):
            raise RuntimeError(f"incomplete {name} search: {response.get('_shards')}")
        ranked_lists.append((response["hits"]["hits"], weight))

    lexical_candidates = min(k * 5, 100)
    vector_candidates = min(max(k * 5, settings.search_vector_candidates), 1000)
    if mode in ("bm25", "hybrid"):
        lexical = client.search(
            index=alias, body={"query": build_query(query, as_of)},
            size=lexical_candidates, ignore_unavailable=not strict,
        )
        add_response(lexical, "lexical")
        if query_rewrite is None:
            query_rewrite = settings.search_query_rewrite
        if query_rewrite:
            for rewritten in _rewritten_queries(query, strict):
                add_response(client.search(
                    index=alias, body={"query": build_query(rewritten, as_of)},
                    size=lexical_candidates, ignore_unavailable=not strict,
                ), "rewrite", settings.search_query_rewrite_weight)
    try:
        if mode in ("vector", "hybrid"):
            vector = (embedder or OllamaEmbedder(settings)).embed_query(query.strip())
            semantic = client.search(
                index=alias,
                body={"query": build_vector_query(vector, as_of, vector_candidates)},
                size=vector_candidates,
                ignore_unavailable=not strict,
            )
            add_response(semantic, "vector")
    except httpx.HTTPError:
        if strict or mode == "vector":
            raise
        # Lexical search remains available during an embedding service outage.
        pass

    if len(ranked_lists) > 1:
        ranked = _rrf(ranked_lists, settings.search_hybrid_rrf_k)
    else:
        # Preserve the retriever's original scores, keeping its best chunk per parent.
        seen = set()
        ranked = []
        for hit in ranked_lists[0][0]:
            parent = hit["_source"].get("parent_id") or hit["_id"]
            if parent not in seen:
                seen.add(parent)
                ranked.append(hit)
    if cutoff_ratio is None:
        cutoff_ratio = settings.cutoff_ratio(mode if len(ranked_lists) == 1 else "hybrid")
    floor = _cutoff(ranked, cutoff_ratio)
    out = []
    for hit in ranked:
        source = hit["_source"]
        parent_id = source.get("parent_id") or hit["_id"]
        score = hit.get("_score")
        if score is not None and score < floor:
            break
        out.append(SearchHit.model_validate({
            **{key: value for key, value in source.items() if value is not None},
            "id": hit["_id"], "parent_id": parent_id, "score": score,
        }))
        if len(out) == k:
            break
    if chunks_per_document is None:
        chunks_per_document = settings.search_chunks_per_document
    return _with_passages(
        _with_current_editions(client, alias, out, k), ranked_lists, chunks_per_document,
    )


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


MODES = ("bm25", "vector", "hybrid")


class _SharedEmbedder:
    """Embed a query once and lend the vector to every mode that asks for it.

    Comparing modes should compare retrieval, not embedding: charging Ollama
    twice for one question doubles the slowest part of the request, and a model
    that is not bit-reproducible would hand `vector` and `hybrid` slightly
    different vectors, so they could disagree for a reason that is not the mode.
    """

    def __init__(self, embedder: OllamaEmbedder):
        self._embedder = embedder
        self._cache: dict[str, list[float]] = {}

    def embed_query(self, query: str) -> list[float]:
        if query not in self._cache:
            self._cache[query] = self._embedder.embed_query(query)
        return self._cache[query]


def search_modes(
    client: OpenSearch, alias: str, query: str, as_of: date, k: int = 5,
    modes: Iterable[str] = MODES,
) -> ModeComparison:
    """Run one query through every mode, so the modes can be read side by side.

    Switching SEARCH_MODE and searching again compares two different moments as
    much as it compares two modes -- the index may have been rebuilt, and nobody
    reads a rank list from memory accurately. One request removes both problems.
    """
    embedder = _SharedEmbedder(OllamaEmbedder(get_settings()))
    results = []
    for mode in modes:
        start = perf_counter()
        try:
            hits = retrieve(client, alias, query, as_of, k, embedder, mode=mode)
            error = ""
        except (OpenSearchException, httpx.HTTPError) as exc:
            hits, error = [], f"{type(exc).__name__}: {exc}"
        results.append(ModeResults(
            mode=mode, hits=hits, error=error,
            latency_ms=(perf_counter() - start) * 1000,
        ))
    return ModeComparison(query=query, modes=results)


def search_all(
    client: OpenSearch, alias: str, hsk_alias: str, query: str, as_of: date, k: int = 5,
) -> SearchResults:
    """One user search: documents, plus HSK linkage when the query names a code."""
    hits = retrieve(client, alias, query, as_of, k)
    hsk_code = extract_hsk_code(query)
    settings = get_settings()
    if not settings.search_hsk_enabled or settings.search_document_datasets == "docs":
        hsk_code = None
    linkage = retrieve_hsk(client, hsk_alias, hsk_code, None, k) if hsk_code else None
    return SearchResults(query=query, hits=hits, hsk=linkage)
