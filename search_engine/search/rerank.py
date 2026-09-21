"""Re-order a document's own chunks against the query. Document order is untouched.

The chunk that ranks a document is the right chunk less than half the time. On
docs v2, with the deployed hybrid search, the labelled evidence sat at rank 1 for
45.1% of requirements while the candidate pool held it for 100% -- it was fetched
and then buried. Re-ranking a document's own candidates against the query moves
that to 73.6% at rank 1 and 97.2% by rank 6
(docs/evaluation/stages/stage-19-chunk-rerank-within-document.md).

Why the gap exists at all is RRF. Vector search alone needs none of this -- the
same embedding chose the chunks, so their order inside a document is already
right, and re-ranking moves evidence recall@6 by 0.0p. Hybrid fuses on ranks, and
fusion scrambles the within-document order it inherits: its rank-1 evidence
recall is 24.6p below vector's. This buys back what fusion costs, which is why it
is worth its latency under hybrid and worth nothing under vector.

The base model is used, not the Korean-tuned one. `bge-reranker-v2-m3-ko` is 9.0p
worse at rank 1 (13 requirements) and 0.7p better at rank 6 (one), the opposite of
what the Korean-tuned embedding did for dense retrieval in stage 13.

Off by default. It adds about 1.2s to a search that takes a tenth of one, on the
same grounds as query rewrite and the answerability judge.
"""

import logging
from typing import Sequence

import httpx

from search_engine.config import Settings, get_settings
from search_engine.search.results import SearchHit

log = logging.getLogger(__name__)


def _score(query: str, passages: Sequence[str], settings: Settings) -> list[float] | None:
    """Ask the reranker sidecar for one relevance score per passage.

    Returns None rather than raising: a search that already found its documents
    should not fail because the optional re-ordering was unavailable.
    """
    try:
        response = httpx.post(
            f"{settings.search_rerank_base_url.rstrip('/')}/rerank",
            json={"model": settings.search_rerank_model, "query": query,
                  "documents": list(passages)},
            timeout=settings.search_rerank_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        # Accept both the TEI shape ([{index, score}, ...]) and a plain score list.
        if isinstance(payload, dict):
            payload = payload.get("results", payload.get("scores", []))
        if payload and isinstance(payload[0], dict):
            scores = [0.0] * len(passages)
            for row in payload:
                scores[int(row["index"])] = float(row["score"])
            return scores
        scores = [float(value) for value in payload]
    except Exception as exc:
        log.warning("reranker unavailable, keeping chunk order: %s", exc)
        return None
    if len(scores) != len(passages):
        log.warning("reranker returned %d scores for %d passages, keeping chunk order",
                    len(scores), len(passages))
        return None
    return scores


def rerank_passages(
    query: str, hits: list[SearchHit], settings: Settings | None = None,
) -> list[SearchHit]:
    """Re-order each hit's passages in place. Which documents came back never changes.

    Only the first `search_rerank_depth` candidates of a document are scored and
    the tail keeps its order. That is a ceiling on the worst case, not a latency
    knob: a document carries 8 candidates at the median, so the cap touches about
    1% of them and leaves p50 where it was while cutting p95 by a quarter.
    """
    settings = settings or get_settings()
    if not hits:
        return hits
    depth = settings.search_rerank_depth
    for hit in hits:
        # The chunk that ranked the document competes with the rest on equal terms.
        bodies = [hit.body or ""] + [passage.body for passage in hit.passages]
        if len(bodies) < 2:
            continue
        scores = _score(query, bodies[:depth], settings)
        if scores is None:
            continue
        head = sorted(range(len(scores)), key=lambda index: -scores[index])
        # Index 0 is the hit's own body, which has no Passage to move; keep it
        # in place when it wins and otherwise let the passages reorder around it.
        hit.passages = tuple(
            [hit.passages[index - 1] for index in head if index > 0]
            + list(hit.passages[depth - 1:])
        )
    return hits
