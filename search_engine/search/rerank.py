"""Choose which of a document's chunks to carry, by asking a cross-encoder.

The chunk that ranks a document is the right chunk less than half the time. On
docs v2, with the deployed hybrid search, the labelled evidence sat at rank 1 for
45.1% of requirements while the candidate pool held it for 100% -- it was fetched
and then buried. Scoring the pool against the query moves that to 73.6% at rank 1
and 97.2% by rank 6
(docs/evaluation/stages/stage-19-chunk-rerank-within-document.md).

**This runs before the pool is cut, not after.** Every requirement it recovers sat
at rank 7 to 21 of its document, so re-ordering the six chunks that survive the
cut would recover none of them and cost the latency anyway. The selection and the
ordering are one decision and have to happen together.

Why the gap exists at all is RRF. Vector search alone needs none of this -- the
same embedding chose the chunks, so their order inside a document is already
right, and re-ranking moves evidence recall@6 by 0.0p. Hybrid fuses on ranks, and
fusion scrambles the within-document order it inherits: its rank-1 evidence
recall is 24.6p below vector's. This buys back what fusion costs, which is why it
is worth its latency under hybrid and worth nothing under vector.

The base model is used, not the Korean-tuned one. `bge-reranker-v2-m3-ko` is 9.0p
worse at rank 1 (13 requirements) and 0.7p better at rank 6 (one), the opposite of
what the Korean-tuned embedding did for dense retrieval in stage 13.

Off by default: it puts a second model in the path of a search that has none.
"""

import logging
from typing import Sequence

import httpx

from search_engine.config import Settings, get_settings
from search_engine.search.results import Passage, SearchHit

log = logging.getLogger(__name__)


def _score(query: str, passages: Sequence[str], settings: Settings) -> list[float] | None:
    """Ask the reranker sidecar for one relevance score per passage.

    One request for every chunk of every document, not one per document: the
    pairs are independent, so a per-document loop would buy nothing but k round
    trips.

    Returns None rather than raising: a search that already found its documents
    should not fail because an optional re-ordering was unavailable.
    """
    if not passages:
        return []
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


def select_passages(
    query: str, hits: list[SearchHit], candidates: dict[str, list[dict]],
    chunks_per_document: int, settings: Settings | None = None,
) -> bool:
    """Fill each hit's chunks from the reranked pool. Which documents came back never changes.

    The best-scoring chunk becomes the hit's own `id`/`body`, displacing the one
    RRF put there. Without that the leading chunk -- the one a reader sees first
    and the one a generator weights most -- stays whatever fusion chose, and the
    rank-1 measurement above cannot happen.

    Returns False when the sidecar could not be reached, leaving every hit
    untouched so the caller can fall back to the unranked selection.
    """
    settings = settings or get_settings()
    depth = settings.search_rerank_depth
    pools = []
    for hit in hits:
        # The chunk that ranked the document competes with the rest on equal terms.
        pool = [{"_id": hit.id, "_source": {"body": hit.body}, "_score": hit.score}]
        pool += [c for c in candidates.get(hit.parent_id, []) if c["_id"] != hit.id]
        pools.append(pool[:depth])

    flat = [c["_source"].get("body", "") for pool in pools for c in pool]
    scores = _score(query, flat, settings)
    if scores is None:
        return False

    offset = 0
    for hit, pool in zip(hits, pools):
        ranked = sorted(zip(pool, scores[offset:offset + len(pool)]),
                        key=lambda pair: -pair[1])[:chunks_per_document]
        offset += len(pool)
        if not ranked:
            continue
        lead, _ = ranked[0]
        hit.id = lead["_id"]
        hit.body = lead["_source"].get("body", "")
        hit.passages = [
            Passage(id=c["_id"], body=c["_source"].get("body", ""), score=c.get("_score"))
            for c, _ in ranked[1:]
        ]
    return True
