from datetime import date
import logging
import re
from time import perf_counter
from collections.abc import Iterable

import httpx
from opensearchpy import OpenSearch, OpenSearchException

from search_engine.config import Settings, get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search.hsk import extract_hsk_code, retrieve_hsk
from search_engine.search.answerability import is_unanswerable
from search_engine.search.rerank import select_passages
from search_engine.search.rewrite import rewrite_query
from search_engine.search.results import (
    ModeComparison,
    ModeResults,
    Passage,
    SearchHit,
    SearchResults,
)

log = logging.getLogger(__name__)

# Marks a fused hit that was ranked first by one of the lists behind it.
LEADS_A_LIST = "_leads_a_list"

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


def _ratio_cut(hits: list[dict], ratio: float) -> list[dict]:
    """Drop the tail of one retriever's list, measured against its own best hit.

    This runs before fusion, and the ratio it takes is not the one that mode
    would use to cut its own final results. Its job here is to decide what
    each retriever is confident enough about to put into the fusion, which is
    why the two jobs are configured separately -- reusing the vector mode's
    own 0.99 narrows the dense list to a single chunk and throws away the
    ranking RRF is there to read.

    A ratio cannot do this job after fusion at all. RRF builds a score out of
    ranks -- `1/(k+rank)` summed over the lists that found the document -- so
    a document two retrievers found starts at twice the score of one only a
    single retriever found, whatever either of them believed. With k=60 the
    best a single-list document can reach is `1/61` against a dual-list
    leader's `2/61`: a ratio of 0.5. Any cutoff above that deletes every
    document the other retriever missed, which on docs v2 was three questions
    whose answer the dense retriever had ranked first. What such a ratio
    measures is not the rank gap it is meant to measure; it is how many lists
    found the document.
    """
    if not ratio or not hits:
        return hits
    top = next((hit["_score"] for hit in hits if hit.get("_score") is not None), None)
    if top is None or top <= 0:
        return hits
    kept = []
    for hit in hits:
        score = hit.get("_score")
        if score is not None and score < top * ratio:
            break
        kept.append(hit)
    return kept


def _rrf(ranked_lists: Iterable[tuple[list[dict], float, str]], rrf_k: int) -> list[dict]:
    """Fuse weighted rank lists without comparing BM25 scores to cosine similarities.

    The weight is what keeps an unreliable list from outvoting a reliable one: a
    rewritten query contributes at a fraction of the original's, so a rewrite that
    went wrong can add a document but cannot push the original's best answer down.

    Ties are broken on the dense retriever's rank. They are common rather than
    freakish once the lists are trimmed: a score is a sum of `1/(k+rank)`
    terms, so two documents each ranked first in a different list hold exactly
    the same score. Falling back on the chunk id, as sorting by `_id` did,
    decided those on a hash. The dense order is the one the rest of the
    pipeline already trusts for the same reason it trusts it inside a document
    (stage 20).
    """
    fused: dict[str, tuple[float, dict]] = {}
    dense_rank: dict[str, int] = {}
    # Documents that lead a list of their own. Marked here because after
    # fusion there is no way back to the fact: the ratio cutoff has to know
    # which hits it is not entitled to judge.
    leaders: set[str] = set()
    for hits, weight, retriever in ranked_lists:
        seen_in_list: set[str] = set()
        for rank, hit in enumerate(hits, 1):
            source = hit["_source"]
            parent_id = source.get("parent_id") or hit["_id"]
            if parent_id in seen_in_list:
                continue
            seen_in_list.add(parent_id)
            if retriever == "vector":
                dense_rank.setdefault(parent_id, rank)
            if rank == 1:
                leaders.add(parent_id)
            score, exemplar = fused.get(parent_id, (0.0, hit))
            fused[parent_id] = (score + weight / (rrf_k + rank), exemplar)

    def order(item: tuple[str, tuple[float, dict]]) -> tuple:
        parent_id, (score, hit) = item
        # A document the dense retriever never returned sorts after every one
        # it did, rather than ahead of them all at rank 0.
        return -score, dense_rank.get(parent_id, len(fused) + 1), hit["_id"]

    return [
        {**hit, "_score": score, LEADS_A_LIST: parent_id in leaders}
        for parent_id, (score, hit) in sorted(fused.items(), key=order)
    ]


def _candidates_by_parent(
    ranked_lists: Iterable[tuple[list[dict], float, str]],
) -> dict[str, list[dict]]:
    """Group every candidate chunk under its parent, the dense retriever's order first.

    Which parents come back is already settled before this runs, so the ordering
    here only decides which chunks of a parent are shown, never which documents.

    The dense retriever leads because it is the only one that orders chunks well.
    Fusion settles documents on ranks, and the within-document order it leaves
    behind is nobody's: on docs v2 the labelled evidence led its document for
    41.9% of requirements under hybrid against 66.5% under vector alone. Taking
    the chunk order from the dense list and keeping fusion for the documents
    closes that -- evidence recall goes to 65.2% at rank 1 and 90.3% by rank 6,
    which is where a cross-encoder over the same pool lands (67.7% / 90.3%) for
    1.5s more (docs/evaluation/stages/stage-19-chunk-rerank-within-document.md).

    Lexical candidates still follow, so a chunk only BM25 found is carried rather
    than dropped. Under bm25 or vector alone there is one list and nothing moves.
    """
    by_parent: dict[str, list[dict]] = {}
    seen: set[str] = set()
    ranked_lists = sorted(ranked_lists, key=lambda entry: entry[2] != "vector")
    for hits, *_ in ranked_lists:
        for hit in hits:
            if hit["_id"] in seen:
                continue
            seen.add(hit["_id"])
            parent = hit["_source"].get("parent_id") or hit["_id"]
            by_parent.setdefault(parent, []).append(hit)
    return by_parent


def _with_passages(
    hits: list[SearchHit], by_parent: dict[str, list[dict]], chunks_per_document: int,
) -> list[SearchHit]:
    """Carry a document's best chunks, in the order `by_parent` put them.

    One chunk per document is the right unit for ranking documents but the wrong
    unit for answering: on the docs v2 set the labelled evidence sat in a chunk
    the deduplication dropped for 23 of 40 questions, even though its document
    was already first. The extra chunks come out of the candidate pool the search
    already fetched, so this costs no further round trip.

    The leading chunk comes from that order too, rather than staying whichever
    chunk fusion happened to rank the document by. It is the chunk a reader sees
    first and the one a generator weights most, and leaving it to fusion pins
    rank-1 evidence recall at 41.9% while the rest of the selection improves
    around it (docs/evaluation/stages/stage-20-dense-order-inside-documents.md).
    """
    if chunks_per_document < 2:
        return hits
    for hit in hits:
        pool = list(by_parent.get(hit.parent_id, []))
        # The chunk that ranked the document belongs in the pool even if no
        # retriever list carried it here; it just no longer leads by default.
        if not any(c["_id"] == hit.id for c in pool):
            pool.insert(0, {"_id": hit.id, "_source": {"body": hit.body}, "_score": hit.score})
        chosen = pool[:chunks_per_document]
        lead = chosen[0]
        hit.id = lead["_id"]
        hit.body = lead["_source"].get("body", "")
        hit.passages = [
            Passage(id=c["_id"], body=c["_source"].get("body", ""), score=c.get("_score"))
            for c in chosen[1:]
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


MODES = ("bm25", "vector", "hybrid")


def retrieve(
    client: OpenSearch, alias: str, query: str, as_of: date, k: int,
    embedder: OllamaEmbedder | None = None,
    *, mode: str | None = None, strict: bool = False,
    chunks_per_document: int | None = None, query_rewrite: bool | None = None,
    cutoff_ratio: float | None = None,
    score_floor: float | None = None, answerability: bool | None = None,
    rerank_chunks: bool | None = None,
) -> list[SearchHit]:
    """Retrieve from `alias`, which may name several indexes, comma separated.

    Searches ignore an index that does not exist yet: a corpus that has never
    been indexed should narrow the results, not fail the request.
    """
    settings = get_settings()
    mode = mode or settings.search_mode
    if mode not in MODES:
        raise ValueError(f"unknown search mode: {mode}")
    if k < 1:
        raise ValueError("k must be positive")
    # (hits, weight, retriever): the retriever is carried so that a search
    # left with one list can be cut on that retriever's own calibration.
    ranked_lists: list[tuple[list[dict], float, str]] = []
    # Set when the dense retriever ran and its floor rejected everything it
    # found. Cosine is the only one of these scales on which a short but
    # real query and an off-topic one separate -- BM25 sums per-term
    # contributions, so a two-word question scores under an out-of-domain
    # sentence and no lexical floor can tell them apart. So the dense
    # retriever decides whether anything here is on topic, and the lexical
    # one only ranks within that. Inert until a vector floor is configured.
    # A one-slot list rather than a bool because add_response closes over it.
    off_topic: list[bool] = []

    def add_response(response: dict, name: str, retriever: str, weight: float = 1.0) -> None:
        _warn_on_partial_results(response, name)
        if strict and (response.get("_shards", {}).get("failed", 0) or response.get("timed_out")):
            raise RuntimeError(f"incomplete {name} search: {response.get('_shards')}")
        hits = response["hits"]["hits"]
        # Gate each retriever on its own scale before fusion. RRF scores are
        # built from ranks, so once the lists are fused no absolute value
        # survives to test -- a document only a single retriever believes in
        # has to be dropped here or not at all.
        gate = settings.score_floor(retriever) if score_floor is None else 0.0
        if gate:
            # A hit without a score cannot be judged against a floor, so it is
            # kept -- the same rule the ratio cutoff below applies.
            kept = [hit for hit in hits
                    if hit.get("_score") is None or hit["_score"] >= gate]
            if retriever == "vector" and hits and not kept:
                off_topic.append(True)
            hits = kept
        ranked_lists.append((hits, weight, retriever))

    lexical_candidates = min(k * 5, 100)
    vector_candidates = min(max(k * 5, settings.search_vector_candidates), 1000)
    if mode in ("bm25", "hybrid"):
        lexical = client.search(
            index=alias, body={"query": build_query(query, as_of)},
            size=lexical_candidates, ignore_unavailable=not strict,
        )
        add_response(lexical, "lexical", "bm25")
        if query_rewrite is None:
            query_rewrite = settings.search_query_rewrite
        if query_rewrite:
            for rewritten in _rewritten_queries(query, strict):
                add_response(client.search(
                    index=alias, body={"query": build_query(rewritten, as_of)},
                    size=lexical_candidates, ignore_unavailable=not strict,
                ), "rewrite", "bm25", settings.search_query_rewrite_weight)
    try:
        if mode in ("vector", "hybrid"):
            vector = (embedder or OllamaEmbedder(settings)).embed_query(query.strip())
            semantic = client.search(
                index=alias,
                body={"query": build_vector_query(vector, as_of, vector_candidates)},
                size=vector_candidates,
                ignore_unavailable=not strict,
            )
            add_response(semantic, "vector", "vector")
    except httpx.HTTPError:
        if strict or mode == "vector":
            raise
        # Lexical search remains available during an embedding service outage.
        pass

    # The dense retriever found nothing on topic, so nothing here answers the
    # question, whatever the lexical half turned up.
    if off_topic:
        return []
    ranked_lists = [entry for entry in ranked_lists if entry[0]] or [([], 1.0, mode)]
    if len(ranked_lists) > 1:
        # Cut each list on its own retriever's calibrated ratio first. An
        # explicit `cutoff_ratio` overrides the whole cutoff policy -- a sweep
        # passing 0 to see the uncut ranking must get it -- so it skips this
        # too. `ranked_lists` itself is left whole: it is also the pool the
        # per-document passages are chosen from, and trimming that would take
        # chunks away from documents that do get returned.
        fusable = ranked_lists if cutoff_ratio is not None else [
            (_ratio_cut(hits, settings.fusion_trim_ratio(retriever)), weight, retriever)
            for hits, weight, retriever in ranked_lists
        ]
        ranked = _rrf(fusable, settings.search_hybrid_rrf_k)
    else:
        # Preserve the retriever's original scores, keeping its best chunk per parent.
        seen = set()
        ranked = []
        for hit in ranked_lists[0][0]:
            parent = hit["_source"].get("parent_id") or hit["_id"]
            if parent not in seen:
                seen.add(parent)
                ranked.append(hit)
    # One list left means no fusion happened, so the scores are that
    # retriever's own -- cut them on its ratio and floor, not on the requested
    # mode's. A hybrid search whose lexical half was gated away otherwise reads
    # raw cosine scores against a ratio calibrated for RRF, and returns a
    # longer list than the same retriever would have returned alone.
    fused = ranked_lists[0][2] if len(ranked_lists) == 1 else "hybrid"
    if cutoff_ratio is None:
        cutoff_ratio = settings.cutoff_ratio(fused)
    if score_floor is None:
        score_floor = settings.score_floor(fused)
    # The absolute floor is the only one of the two that can empty the list:
    # the ratio measures every hit against the best hit, so the best hit always
    # clears it. Taking the larger of the two applies whichever cuts deeper.
    floor = max(_cutoff(ranked, cutoff_ratio), score_floor)
    out = []
    for hit in ranked:
        source = hit["_source"]
        parent_id = source.get("parent_id") or hit["_id"]
        score = hit.get("_score")
        # A document some retriever ranked first is kept whatever the ratio
        # says. Against a leader both lists found it scores half as much for
        # having been found once, not for ranking worse, and no ratio can tell
        # those apart after fusion. `continue` rather than `break`, because
        # such a document sorts below hits the ratio does cut.
        if score is not None and score < floor:
            if not hit.get(LEADS_A_LIST):
                continue
            # The absolute floor is not the ratio and still binds.
            if score < score_floor:
                continue
        out.append(SearchHit.model_validate({
            **{key: value for key, value in source.items() if value is not None},
            "id": hit["_id"], "parent_id": parent_id, "score": score,
        }))
        if len(out) == k:
            break
    if chunks_per_document is None:
        chunks_per_document = settings.search_chunks_per_document
    hits = _with_current_editions(client, alias, out, k)
    by_parent = _candidates_by_parent(ranked_lists)
    if rerank_chunks is None:
        rerank_chunks = settings.search_rerank_chunks
    # Selection and ordering are one decision, so this replaces _with_passages
    # rather than running after it. Cutting the pool to six first and re-ordering
    # those six recovers nothing: every requirement the reranker recovers sat at
    # rank 7 to 21 of its document. It also runs before the judge, so the judge
    # reads the chunks a reader would -- half the answerable questions it refused
    # were ones whose evidence had been buried here.
    if not (rerank_chunks
            and chunks_per_document >= 2
            and select_passages(query, hits, by_parent, chunks_per_document, settings)):
        hits = _with_passages(hits, by_parent, chunks_per_document)
    if answerability is None:
        answerability = settings.search_answerability_judge
    # Judged last, on the passages that would actually be handed to a reader:
    # asking earlier would put the question to a different text than the one
    # the search returns.
    if answerability and is_unanswerable(query, hits, settings):
        return []
    return hits


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
