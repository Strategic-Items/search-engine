"""문서의 청크 중 어떤 것을 유지할지 선택하기 위해 크로스엔코더를 사용한다.

문서의 순위가 가장 높은 청크는 문서 내에서 절반 미만의 시간 동안 올바른 청크이다. Docs v2에서 배포된 하이브리드 검색을 사용할 때, 레이블이 붙은 증거는 요구사항의 45.1%에서 순위 1을 차지했으며, 후보 풀은 100%에서 그것을 보유하고 있었다. 즉, 증거는 가져오긴 했지만 이후 묻혔던 것이다. 후보 풀을 쿼리에 대해 점수 매기면, 순위 1에서 73.6%로, 순위 6까지는 97.2%로 증거 회수율이 향상된다 (docs/evaluation/stages/applied/stage-19-chunk-rerank-within-document.md).

**이 작업은 풀이 자르기 전에 수행된다.** 이 작업이 회복하는 모든 요구사항은 문서 내에서 순위 7에서 21 사이에 있었다. 따라서 자르기 후 살아남는 여섯 개의 청크를 재정렬하면 그 중 어떤 것도 회복할 수 없으며, 대신 지연 시간만 증가한다. 선택과 정렬은 하나의 결정이며 함께 일어나야 한다.

이 갭이 존재하는 이유는 RRF 때문이다. 벡터 검색만으로는 이 작업이 필요하지 않다. 동일한 임베딩이 청크를 선택했기 때문에 문서 내 청크의 순서는 이미 올바르며, 재순위 매기기는 증거 회수율@6에 0.0p의 영향을 미친다. 하이브리드 검색은 순위를 융합하며, 융합은 상속받은 문서 내 순서를 혼란스럽게 만든다: 융합의 순위 1 증거 회수율은 벡터 검색보다 24.6p 낮다. 이는 융합이 비용으로 지불하는 것을 되찾는 것이며, 이 때문에 하이브리드 검색에서는 지연 시간을 감수할 가치가 있고, 벡터 검색에서는 가치가 없다.

기본 모델이 사용되며, 한국어에 맞춤 조정된 모델은 사용되지 않는다. `bge-reranker-v2-m3-ko`는 순위 1에서 13개의 요구사항에서 9.0p 더 나쁘고, 순위 6에서 1개의 요구사항에서 0.7p 더 좋다. 이는 한국어에 맞춤 조정된 임베딩이 스테이지 13에서 밀집 검색에 대해 한 것과 반대이다.

기본적으로 비활성화되어 있다: 검색에 모델이 하나도 없는 상황에 두 번째 모델을 경로에 추가하기 때문이다."""

import logging
from typing import Sequence

import httpx

from search_engine.config import Settings, get_settings
from search_engine.search.results import Passage, SearchHit

log = logging.getLogger(__name__)


def _score(query: str, passages: Sequence[str], settings: Settings) -> list[float] | None:
    """reranker sidecar에 각 패스에 대한 하나의 관련성 점수를 요청합니다.

    모든 문서의 모든 청크에 대해 하나의 요청을 수행합니다. 문서별로 하나씩 요청하는 것이 아니라요: 쌍은 독립적이므로, 문서별로 루프를 돌리는 것은 k번의 왕복만을 가져올 뿐입니다.

    예외를 발생시키기보다는 None을 반환합니다. 이미 문서를 찾은 검색은 선택적인 재정렬이 사용 불가능했기 때문에 실패해서는 안 됩니다.
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
# TEI 형식([{'index', 'score'}, ...])과 일반 점수 리스트 둘 다 허용한다.
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
    """ reranked 풀에서 각 히트의 청크를 채운다. 어떤 문서가 돌아왔는지는 절대 변하지 않는다.

    최고 점수를 받은 청크가 RRF가 넣어 둔 것을 대체하여 히트 자신의 `id`/`body`가 된다. 그렇지 않으면
    선두 청크 -- 독자가 가장 먼저 보는 청크이자 생성기가 가장 많이 가중치를 주는 청크 -- 는 퓨전이 선택한 그대로 유지되며,
    위의 랭크-1 측정은 발생할 수 없다.

    사이드카에 도달할 수 없을 경우 False를 반환하여 모든 히트를 그대로 두어 호출자가
    순위를 매기지 않은 선택으로 돌아갈 수 있게 한다.
    """
    settings = settings or get_settings()
    depth = settings.search_rerank_depth
    pools = []
    for hit in hits:
        # 문서를 순위 매긴 청크는 나머지 청크들과 동등한 조건에서 경쟁한다.
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
