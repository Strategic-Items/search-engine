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
from search_engine.search.chunk_filter import filter_chunks
from search_engine.search.rewrite import rewrite_query
from search_engine.search.results import (
    ModeComparison,
    ModeResults,
    Passage,
    SearchHit,
    SearchResults,
)

log = logging.getLogger(__name__)

# 하나의 리스트 뒤에 있는 히트 중에서 가장 먼저 순위付け된 융합 히트를 나타냅니다.
LEADS_A_LIST = "_leads_a_list"

PERIOD = re.compile(r"(20\d{2})\s*년(?:\s*(\d{1,2})\s*월)?")
HALF_YEAR = re.compile(r"(?<!\d)(20\d{2}|\d{2})\s*(?:년(?:도)?)?\s*(상|하)\s*반기")
TOPIC_WORD = re.compile(r"[가-힣]{3,}|[A-Za-z]{2,}")

# 요청에는 쿼리만 포함되므로, 사용자가 요청하는 문서의 종류
# 텍스트에서 읽어야 한다. 이들은 필터가 아니라 종류를 들어 올리는 것이다: a
# 잘못 읽는 비용은 순위에 영향을 주지만, 결코 답 자체에는 영향을 주지 않는다.
GUIDE_TYPES = ("판정 안내", "허가 안내", "이용 안내")
FORM_TYPES = ("민원서식",)
INTENT_HINTS = (
    (GUIDE_TYPES, re.compile(r"절차|방법|순서|어떻게|하려면|무엇인가요|어디서|이용방법")),
    (FORM_TYPES, re.compile(r"서식|양식|신청서|서약서|진술서|별표|별지|내려받기|다운로드")),
)
SOURCE_TYPE_WEIGHT = 14
# 더 새로운 판본이 대체한 양식은 검색 가능해야 한다 -- 사람들이 요청한다
# 이전 판은 연도로 구분되지만, 기본적으로는 현재 판이 먼저 답변한다.
CURRENT_EDITION_WEIGHT = 4


def _requested_period(query: str) -> tuple[str, str] | None:
    """'2024년 3월' 형식의 질의가 요구하는 반개구간 날짜 범위를 반환한다."""
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


def _reporting_half(query: str) -> tuple[int, str] | None:
    """질문에 하나의 연도·반기만 명시됐을 때 그 기간을 읽는다."""
    matches = {(int(year) if len(year) == 4 else 2000 + int(year), half)
               for year, half in HALF_YEAR.findall(query)}
    return next(iter(matches)) if len(matches) == 1 else None


def _same_reporting_half(title: str, period: tuple[int, str]) -> bool:
    return any((int(year) if len(year) == 4 else 2000 + int(year), half) == period
               for year, half in HALF_YEAR.findall(title))


def _same_topic_in_title(query: str, title: str) -> bool:
    """연도·반기 외에 제목의 실제 주제어가 질문에도 등장하는지 확인한다."""
    return any(word not in ("상반기", "하반기") and word.casefold() in query.casefold()
               for word in TOPIC_WORD.findall(title))


def _intent_boosts(query: str) -> list[dict]:
    """쿼리가 요구하는 문서 종류를 사용자가 사용하는 단어로 강화한다."""
    return [
        {"filter": {"terms": {"source_type": list(types)}}, "weight": SOURCE_TYPE_WEIGHT}
        for types, hint in INTENT_HINTS if hint.search(query)
    ]


# 공고·고시 번호. `제2026-598호`처럼 연도와 일련번호가 붙은 형태만 센다.
# nori는 이를 `2026`,`598`,`호` 세 토큰으로 쪼개고 `most_fields`는 필드마다 점수를
# 더하므로, 번호를 못 맞춘 공고문이 `산업/통상/부/공고/2026/호`만으로 따라붙는다.
# 어휘 검색은 그래도 옳은 문서를 1위에 올리지만 -- 135질의에서 12건 모두 -- 그
# 우위가 2위와 11%밖에 안 벌어져 RRF에 넘어가면 순위 하나로 뭉개진다.
DOCKET = re.compile(r"제?\s*(\d{4})\s*-\s*(\d{2,4})\s*호")


def _docket_filter(query: str) -> list[dict]:
    """질의가 공고 번호를 대면, 그 번호를 담지 않은 문서는 답이 아니다.

    부스트가 아니라 필터인 이유는 번호가 관련도를 말하는 것이 아니라 문서를
    지목하기 때문이다. 제2026-598호를 물었다면 590호 문서는 아무리 비슷해도
    답이 아니다. 제목과 본문 둘 다 보는 것은 번호가 본문에 없고 제목에만
    남은 문서가 있기 때문이다(docs-v2-126).
    """
    match = DOCKET.search(query)
    if not match:
        return []
    phrase = f"{match.group(1)} {int(match.group(2))}"
    return [{"bool": {"should": [{"match_phrase": {field: phrase}}
                                 for field in ("body", "title")],
                      "minimum_should_match": 1}}]


def build_query(query: str, as_of: date) -> dict:
    should = []
    if query.strip():
        should.append({"multi_match": {
            "query": query.strip(),
            # `most_fields`는 `best_fields`가 아니라, 파서가 각 청크의 제목에 섹션 제목을 추가하기 때문
            # 섹션 제목을 각 청크의 제목에 추가하기 때문에 -- "대외무역법 시행령 — 1.
            # 수출허가를 받은 물품등의 최종..." -- 이는 제목을 짧은
            # 두 번째 본문으로 만들어 content words를 담는다. `best_fields`는
            # 문서를 단일 최고 필드로 평가하므로, 그
            # 짧은 제목에 있는 두 개의 일반적인 단어가 본문에 있는 다섯 개의 구체적인 단어보다 높은 점수를 받는다
            # 그리고 본문의 증거는 추가되지 않고 버려진다:
            # 받(7.03) + 허가(4.43) = 11.46 outscored 의견 + 러시아 + 보내 +
            # 허가 + 있 = 7.80, 그리고 러시아는 이 코퍼스에서 가장 차별적인 용어이다. 필드를 합산하면 두 용어가 어휘적 하한선의 같은 쪽에 있게 된다.
            # 이 코퍼스에서. 필드를 합산하면 두 용어가 어휘적 하한선의 같은 쪽에 있게 된다.
            # 제목은 모든 청크에 반복된다. 여러 코퍼스를 함께 검색할 때 ^3은
            # 제목이 비슷한 새 문서를 과하게 올리므로 본문과 같은 가중치를 준다.
            "fields": ["title^1", "body", "title.standard^1.5", "body.standard^0.5"],
            "type": "most_fields",
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
    filters += _docket_filter(query)
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
        # `period_hint`는 발행일이 비어 있는 문서에만 붙는다. 파서가 파일명에서만
        # 날짜를 읽어 docs-v2 52문서 중 43문서가 그 자리에 있고, 그 문서들은 연도를
        # 대는 질의에 대해 이 부스트를 아예 받지 못했다. 힌트는 연·월 눈금에서만
        # 믿을 만하므로(9문서 중 8문서) 같은 눈금을 묻는 이 부스트에만 쓰고,
        # 대체 판정이나 사본 병합에는 쓰지 않는다. 가중치를 발행일보다 낮게 두는
        # 것은 힌트가 추정이기 때문이다.
        functions.append({"filter": {"range": {"period_hint": {"gte": start, "lt": end}}},
                          "weight": 4})
    if not functions:
        return base
    return {"function_score": {"query": base, "functions": functions,
                               "score_mode": "sum", "boost_mode": "sum"}}


def _validity_filters(as_of: date) -> list[dict]:
    """k-NN에서 중복된 필터링, 쿼리가 function_score를 사용할 수 없기 때문에."""
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


def build_vector_query(vector: list[float], as_of: date, candidates: int,
                      query: str = "") -> dict:
    """근사적 HNSW 코사인 검색, 현재 유효한 레코드에 제한됨.

    공고 번호는 여기에도 걸린다. 번호는 관련도가 아니라 어느 문서인지를 말하므로
    두 검색기에 똑같이 해당한다. 어휘 쪽에만 걸면 아무 일도 일어나지 않는다 --
    번호를 못 맞춘 공고문은 애초에 밀집 목록이 데려온 것들이고, 임베딩에 네 자리
    일련번호는 사실상 실리지 않아 코사인으로는 590호와 598호가 구별되지 않는다.
    """
    return {"knn": {"embedding": {
        "vector": vector,
        "k": candidates,
        "filter": {"bool": {"filter": _validity_filters(as_of) + _docket_filter(query)}},
    }}}


def _warn_on_partial_results(response: dict, retriever: str) -> None:
    """색인 하나가 검색에서 제외될 때 조용히 사라지기보다는 이를 명시적으로 알림.

    여러 샤드를 동시에 검색할 때 샤드가 실패하더라도 200을 반환하므로, 색인이 순위 목록에서 완전히 사라질 수 있으며 이는 눈에 띄는 오류 없이 발생할 수 있다. 벡터 매핑보다 먼저 생성된 색인은 k-NN에 아무런 기여도 하지 않으며, RRF는 그 안의 모든 문서를 묻어버린다. 이것은 재색인 문제이며, 쿼리 버그가 아니라, 이를 확인할 수 있어야만 조치할 수 있다.
    """
    shards = response.get("_shards", {})
    if not shards.get("failed"):
        return
    for failure in shards.get("failures", []):
        log.warning("%s search skipped index %s: %s", retriever, failure.get("index"),
                    failure.get("reason", {}).get("reason"))


def _cutoff(ranked: list[dict], ratio: float) -> float:
    """이 검색의 최고 점수보다 너무 뒤처져서 보여주기 어려운 히트의 점수 이하.

단위가 공유되지 않는 스케일에서 모드의 점수를 기준으로 최고 점수를 취한다. 점수의 절대값은 문서가 질문에 답하는지에 대해 아무런 정보를 주지 않는다. 문서 v2에서는 답할 수 없는 질문의 최고 히트가 많은 답할 수 있는 질문의 점수를 초과했다. 점수는 한 검색 내에서의 비교를 지원할 뿐이며, 이는 이 코드가 하는 일에만 해당한다.
"""
    top = next((hit["_score"] for hit in ranked if hit.get("_score") is not None), None)
    # 음수 또는 0인 최고 점수는 비율을 의미 없게 만든다. 모든 것을 유지한다.
    if not ratio or top is None or top <= 0:
        return float("-inf")
    return top * ratio


def _ratio_cut(hits: list[dict], ratio: float) -> list[dict]:
    """한 리트리버의 목록 끝을 자신의 최고 히트에 비추어 잘라낸다.

이것은 퓨전 이전에 실행되며, 이 비율은 모드가 자신의 최종 결과를 잘라내는 데 사용하는 비율이 아니다. 여기서의 임무는 각 리트리버가 퓨전에 넣기에 충분히 자신감을 갖고 있는지를 결정하는 것이다. 이것이 두 작업이 별도로 구성된 이유이다. 벡터 모드의 0.99를 재사용하면 디ensa 목록이 단일 청크로 좁혀지고 RRF가 읽어야 할 랭킹 정보를 버리게 된다.

비율은 퓨전 이후에는 이 작업을 전혀 수행할 수 없다. RRF는 순위에서 점수를 구성한다. 즉, 문서를 찾은 리스트들에 대해 `1/(k+rank)`를 합산한다. 따라서 두 리트리버가 발견한 문서는 단일 리트리버만 발견한 문서보다 점수가 두 배가 된다. 이 둘 중 어느 쪽이 믿었든 상관없이 말이다. k=60일 때 단일 리스트 문서가 도달할 수 있는 최고 점수는 `1/61`이고, 이중 리스트 리더의 점수는 `2/61`이다. 즉, 비율은 0.5이다. 이보다 높은 컷오프는 다른 리트리버가 놓친 모든 문서를 삭제한다. 문서 v2에서는 디ensa 리트리버가 첫 번째로 랭크한 세 개의 질문이 이에 해당했다. 이러한 비율이 측정하는 것은 그 비율이 측정하려는 순위 갭이 아니라, 문서를 발견한 리스트의 수이다.
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
    """BM25 점수를 코사인 유사도와 비교하지 않고 가중된 랭크 목록을 퓨전한다.

가중치는 신뢰할 수 없는 목록이 신뢰할 수 있는 목록을 압도하지 못하게 하는 역할을 한다. 재작성된 쿼리는 원래 쿼리의 일부만 기여하므로, 잘못된 재작성은 문서를 추가할 수는 있지만 원래 최고 답변을 밀어내지는 못한다.

동점은 디ensa 리트리버의 랭크로 처리한다. 목록이 잘려나간 후에는 동점이 드문 일이 아니라 흔한 일이다. 점수는 `1/(k+rank)` 항들의 합이므로, 두 문서가 각각 다른 목록에서 1위로 랭크되면 정확히 동일한 점수를 갖는다. `_id`로 정렬하던 것처럼 청크 ID로 되돌아가면 해시에 따라 결정된다. 디ensa 순서는 파이프라인의 나머지 부분이 이미 같은 이유로 신뢰하는 순서이며, 문서 내부(단계 20)에서도 신뢰하는 순서이다.
"""
    fused: dict[str, tuple[float, dict]] = {}
    dense_rank: dict[str, int] = {}
    # 자신의 목록을 이끄는 문서들. 퓨전 이후에는 그 사실로 돌아갈 수 없기 때문에 여기에 표시한다.
    # 퓨전 이후에는 비율 컷오프가 판단할 자격이 없는 히트를 알 수 있어야 한다.
    # 디ensa 리트리버가 반환하지 않은 문서는 모든 문서보다 뒤에 정렬된다.
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
        # 밀집 검색기가 반환하지 않은 문서는 모든 문서 뒤에 정렬된다
        # 그것이 일어났지, rank 0에서 모두보다 앞서서가 아니라.
        return -score, dense_rank.get(parent_id, len(fused) + 1), hit["_id"]

    return [
        {**hit, "_score": score, LEADS_A_LIST: parent_id in leaders}
        for parent_id, (score, hit) in sorted(fused.items(), key=order)
    ]


def _edition_key(source: dict) -> tuple[str, str] | None:
    """같은 문서의 사본을 한데 묶는 열쇠. 묶을 수 없으면 None.

    코퍼스에는 내려받기가 남긴 사본이 있다 -- `... (1).hwp`와 `....hwp`는 본문이
    글자까지 같다 -- 그리고 같은 법령이 hwp/pdf/hwpx로 세 번 들어온 경우가 있다.
    후자는 파서가 저마다 다르게 끊어 본문이 일치하지 않으므로 `content_hash`로는
    묶이지 않는다. 제목은 셋 다 같으므로 제목과 발행일로 묶는다.

    청크 제목은 섹션 이름을 뒤에 달고 다니므로(`... — 제2조(정의)`) 앞부분만 쓴다.
    """
    title = (source.get("title") or "").split(" — ")[0].strip()
    if not title:
        return None
    return title, source.get("published_at") or ""


def _candidates_by_parent(
    ranked_lists: Iterable[tuple[list[dict], float, str]],
) -> dict[str, list[dict]]:
    """각 후보 청크를 그 부모 아래에 그룹화한다. 밀집 검색기의 순서가 먼저다.

어떤 부모가 돌아오는지는 이 실행 전에 이미 결정되어 있으므로, 여기서의 순서는
부모의 청크 중 어떤 것이 표시되는지를 결정할 뿐, 어떤 문서를 보여주는지를 결정하지 않는다.

밀집 검색기가 선도하는 이유는 그것이 유일하게 청크를 잘 정렬하기 때문이다.
퓨전은 문서를 랭크로 결정하고, 그 안에서 문서 내 순서를 남긴다. 이 순서는 누구의 것도 아니다: docs v2에서 레이블링된 증거는 하이브리드 기준으로 41.9%의 요구사항에서 문서를 이끌었고, 벡터만 사용할 때는 66.5%였다. 밀집 리스트의 청크 순서를 가져와서 문서에 대해 퓨전을 유지하면 이 차이를 좁힐 수 있다. 증거 재발견률은 랭크 1에서 65.2%로 올라가고, 랭크 6까지는 90.3%에 도달한다. 이는 같은 풀에 대해 크로스엔코더가 도달하는 수준(67.7% / 90.3%)과 비슷하며, 1.5초 더 오래 걸린다 (docs/evaluation/stages/applied/stage-19-chunk-rerank-within-document.md).

어휘적 후보는 여전히 뒤따르므로, 청크 하나만 BM25가 찾은 경우 버려지지 않고 유지된다. bm25 또는 벡터만 사용할 때는 하나의 리스트가 있고, 아무것도 움직이지 않는다.
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
    """문서의 최고 청크를 `by_parent`가 정한 순서대로 유지한다.

문서를 랭킹하는 데에는 문서당 하나의 청크가 적절한 단위이지만, 답변하는 데에는 부적절하다: docs v2 세트에서 레이블링된 증거는 40개 질문 중 23개에서 중복 제거로 인해 버려진 청크에 있었고, 그 문서는 이미 1위였음에도 불구하고. 이 추가 청크들은 이미 검색이 가져온 후보 풀에서 나온 것이므로, 이는 추가적인 라운드 트립 비용을 들이지 않는다.

주도 청크는 그 순서에서 오기도 하며, 퓨전이 문서를 랭킹한 청크가 그대로 유지되는 것이 아니라. 이는 독자가 처음 보는 청크이자 생성기가 가장 많이 가중치를 주는 청크이며, 퓨전에 맡기면 랭크 1 증거 재발견률이 41.9%에 머물고, 그 외의 선택은 그 주변에서 개선된다 (docs/evaluation/stages/applied/stage-20-dense-order-inside-documents.md).
"""
    if chunks_per_document < 2:
        return hits
    for hit in hits:
        pool = list(by_parent.get(hit.parent_id, []))
        # 문서를 랭크한 청크는 아무것도 없더라도 풀에 포함되어야 한다.
        # 검색기 리스트가 그것을 여기로 가져오지 않더라도; 단지 더 이상 기본적으로 선도하지 않을 뿐이다.
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
    """질문과 함께 검색하거나, 아무것도 하지 않도록 재작성한다.

재작성은 부가적인 정보이며, 의존성은 아니다: 모델이 다운되면 원래 질문은 여전히 잘 검색되므로, 장애는 결과 집합을 좁히는 것으로, 요청을 실패시키는 것이 아니다. `strict` 평가 실행은 이 침묵을 거부한다. 왜냐하면, 조용히 재작성을 버린 비교는 잘못된 것을 측정하고 있기 때문이다.
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
    """`alias`에서 검색한다. 이는 여러 인덱스를 쉼표로 구분하여 명명할 수 있다.

검색은 존재하지 않는 인덱스를 무시한다: 아직 인덱싱되지 않은 코퍼스는 결과를 좁히는 것이지, 요청을 실패시키는 것이 아니다.
"""
    settings = get_settings()
    mode = mode or settings.search_mode
    if mode not in MODES:
        raise ValueError(f"unknown search mode: {mode}")
    if k < 1:
        raise ValueError("k must be positive")
    # (hits, weight, retriever): 검색기 정보는 유지되어야 하므로, 검색에서
    # 한 개의 리스트만 남아 있으면 해당 리트리버의 캘리브레이션에서 잘릴 수 있다.
    ranked_lists: list[tuple[list[dict], float, str]] = []
    # 밀집형 리트리버가 실행되었을 때, 그 바닥값이 모든 것을 거부했을 때 설정됨.
    # 코사인은 이 스케일들 중에서 짧지만 실제 쿼리와 주제와 관련 없는 쿼리가 구분되는 유일한 스케일이다. -- BM25는 각 항목별 기여도를 합산하므로, 두 단어 질문은 주제 외의 문장보다 낮은 점수를 받고, 단어적 바닥값은 이들을 구분할 수 없다.
    # 코사인은 이 스케일들 중에서 짧지만 실제 쿼리와 주제와 관련 없는 쿼리가 구분되는 유일한 스케일이다. -- BM25는 각 항목별 기여도를 합산하므로, 두 단어 질문은 주제 외의 문장보다 낮은 점수를 받고, 단어적 바닥값은 이들을 구분할 수 없다.
    # 코사인은 이 스케일들 중에서 짧지만 실제 쿼리와 주제와 관련 없는 쿼리가 구분되는 유일한 스케일이다. -- BM25는 각 항목별 기여도를 합산하므로, 두 단어 질문은 주제 외의 문장보다 낮은 점수를 받고, 단어적 바닥값은 이들을 구분할 수 없다.
    # 코사인은 이 스케일들 중에서 짧지만 실제 쿼리와 주제와 관련 없는 쿼리가 구분되는 유일한 스케일이다. -- BM25는 각 항목별 기여도를 합산하므로, 두 단어 질문은 주제 외의 문장보다 낮은 점수를 받고, 단어적 바닥값은 이들을 구분할 수 없다.
    # 밀집형 리트리버는 여기에 주제와 관련된 것이 있는지 결정하고, 단어적 리트리버는 그 안에서만 순위를 매긴다. 벡터 바닥값이 구성될 때까지 비활성 상태이다.
    # 밀집형 리트리버는 여기에 주제와 관련된 것이 있는지 결정하고, 단어적 리트리버는 그 안에서만 순위를 매긴다. 벡터 바닥값이 구성될 때까지 비활성 상태이다.
    # bool이 아닌 one-slot 리스트인 이유는 add_response가 이를 클로저로 사용하기 때문입니다.
    off_topic: list[bool] = []

    def add_response(response: dict, name: str, retriever: str, weight: float = 1.0) -> None:
        _warn_on_partial_results(response, name)
        if strict and (response.get("_shards", {}).get("failed", 0) or response.get("timed_out")):
            raise RuntimeError(f"incomplete {name} search: {response.get('_shards')}")
        hits = response["hits"]["hits"]
        # 각 검색기를 융합하기 전에 개별 스케일에서 게이트를 적용합니다. RRF 점수는 순위에서 구성되므로, 리스트가 융합된 후에는 절대값이 남아 있지 않습니다.
        # 테스트를 위해 -- 단 하나의 검색기만 신뢰하는 문서는 여기서 버려야 하거나 아예 버려야 합니다.
        # 점수가 없는 히트는 바닥선과 비교할 수 없으므로 유지됩니다. 아래의 비율 컷오프가 적용되는 동일한 규칙입니다.
        # 임베딩 서비스 장애 중에도 어휘 검색은 계속 사용 가능합니다.
        gate = settings.score_floor(retriever) if score_floor is None else 0.0
        if gate:
            # 점수가 없는 히트는 바닥과 비교할 수 없으므로
            # 유지됨 -- 동일한 규칙, 아래의 비율 컷오프가 적용됨.
            kept = [hit for hit in hits
                    if hit.get("_score") is None or hit["_score"] >= gate]
            if retriever == "vector" and hits and not kept:
                off_topic.append(True)
            hits = kept
        ranked_lists.append((hits, weight, retriever))

    lexical_candidates = min(k * 5, 100)
    vector_candidates = min(max(k * 5, settings.search_vector_candidates), 1000)
    if mode in ("bm25", "hybrid"):
        lexical_options = {"search_type": "dfs_query_then_fetch"} if "," in alias else {}
        lexical = client.search(
            index=alias, body={"query": build_query(query, as_of)},
            size=lexical_candidates, ignore_unavailable=not strict,
            **lexical_options,
        )
        add_response(lexical, "lexical", "bm25")
        if query_rewrite is None:
            query_rewrite = settings.search_query_rewrite
        if query_rewrite:
            for rewritten in _rewritten_queries(query, strict):
                add_response(client.search(
                    index=alias, body={"query": build_query(rewritten, as_of)},
                    size=lexical_candidates, ignore_unavailable=not strict,
                    **lexical_options,
                ), "rewrite", "bm25", settings.search_query_rewrite_weight)
    try:
        if mode in ("vector", "hybrid"):
            vector = (embedder or OllamaEmbedder(settings)).embed_query(query.strip())
            semantic = client.search(
                index=alias,
                body={"query": build_vector_query(vector, as_of, vector_candidates,
                                                 query.strip())},
                size=vector_candidates,
                ignore_unavailable=not strict,
            )
            add_response(semantic, "vector", "vector")
    except httpx.HTTPError:
        if strict or mode == "vector":
            raise
        # 텍스트 검색은 임베딩 서비스 장애 중에도 계속 사용 가능하다.
        pass

    # 밀집 검색기가 주제에 대해 아무것도 찾지 못했으므로, 여기에는 질문에 답하는 것이 없다.
    # 어쨌든 어휘 반쪽이 찾아낸 것은 무엇이든.
    if off_topic:
        return []
    ranked_lists = [entry for entry in ranked_lists if entry[0]] or [([], 1.0, mode)]
    period_supported: set[str] = set()
    if len(ranked_lists) > 1:
        # 각 목록을 각각의 검색기의 교정된 비율로 먼저 자른다. 명시적인 `cutoff_ratio`는 전체 절단 정책을 덮어쓴다 -- 0을 전달하여 절단되지 않은 순위를 보려면 그것을 가져와야 하므로, 이 또한 건너뛴다.
        # `ranked_lists` 자체는 그대로 남는다: 그것이 문서별 패스워드가 선택되는 풀이기도 하며, 그것을 줄이면 반환되는 문서에서 조각을 제거하게 된다.
        # 0을 전달하여 잘린 순위를 보지 않도록 하려면 이를 가져와야 하므로 이 부분을 건너뛴다
        # too. `ranked_lists` 자체는 그대로 유지됨: 또한 이는
        # 문서별 패스aggio는 선택되며, 이 과정에서 잘라내기 작업이 수행된다
        # 문서에서 반환되지 않는 청크들로부터의 거리.
        fusable = ranked_lists if cutoff_ratio is not None else [
            (_ratio_cut(hits, settings.fusion_trim_ratio(retriever)), weight, retriever)
            for hits, weight, retriever in ranked_lists
        ]
        # 날짜를 적시한 질문에서는 대상 반기가 발행 연도와 다를 수 있다.
        # 제목에 같은 보고 기간이 적힌 기존 후보에만 세 번째 순위 신호를 준다.
        # 주제 검색의 후보 밖 문서를 새로 끌어오거나 다른 연도를 지우지 않는다.
        reporting_half = _reporting_half(query) if mode == "hybrid" else None
        if reporting_half:
            period_hits = [hit for hits, _, _ in ranked_lists for hit in hits
                           if _same_reporting_half(hit["_source"].get("title", ""), reporting_half)
                           and _same_topic_in_title(query, hit["_source"].get("title", ""))]
            if period_hits:
                fusable = [*fusable, (period_hits, 1.0, "period")]
                by_retriever = {
                    name: {hit["_source"].get("parent_id") or hit["_id"] for hit in hits
                           if _same_reporting_half(hit["_source"].get("title", ""), reporting_half)
                           and _same_topic_in_title(query, hit["_source"].get("title", ""))}
                    for hits, _, name in ranked_lists if name in ("bm25", "vector")
                }
                period_supported = by_retriever.get("bm25", set()) & by_retriever.get("vector", set())
        ranked = _rrf(fusable, settings.search_hybrid_rrf_k)
    else:
        # 리트리버의 원래 점수를 유지하고, 각 부모에 대해 최고의 청크만 유지한다.
        seen = set()
        ranked = []
        for hit in ranked_lists[0][0]:
            parent = hit["_source"].get("parent_id") or hit["_id"]
            if parent not in seen:
                seen.add(parent)
                ranked.append(hit)
    # 한 개의 리스트만 남아 있다는 것은 융합이 일어나지 않았음을 의미하므로, 점수는 그대로이다.
    # 리트리버 자신의 점수는 요청된 방식이 아닌, 그 자체의 비율과 바닥값으로 잘라낸다.
    # 그렇지 않으면 어두운 부분이 차단된 하이브리드 검색은
    # RRF에 맞게 조정된 비율에 대해 원시 코사인 점수를 읽고,
    # 같은 리트리버가 단독으로 반환했을 때보다 더 긴 리스트를 반환한다.
    fused = ranked_lists[0][2] if len(ranked_lists) == 1 else "hybrid"
    if cutoff_ratio is None:
        cutoff_ratio = settings.cutoff_ratio(fused)
    if score_floor is None:
        score_floor = settings.score_floor(fused)
    # 절대 바닥값은 두 가지 중에서 리스트를 비울 수 있는 유일한 값이다:
    # 비율은 모든 히트를 최고 히트와 비교하여 측정하므로, 최고 히트는 항상
    # 지운다. 두 값 중 더 큰 값을 취하면 더 깊게 잘라내는 것을 적용한다.
    floor = max(_cutoff(ranked, cutoff_ratio), score_floor)
    out = []
    # 이미 실은 문서의 사본을 두 번 싣지 않는다. 사본은 같은 청크를 다시 데려오므로
    # 창만 좁히고 새 근거는 주지 않는다. 가장 높이 올라온 사본을 남긴다:
    # 그것이 이 검색이 고른 사본이다.
    editions: set[tuple[str, str]] = set()
    for hit in ranked:
        source = hit["_source"]
        parent_id = source.get("parent_id") or hit["_id"]
        score = hit.get("_score")

        # 어떤 검색기에서 첫 번째로 순위付け된 문서는 비율에 관계없이 유지된다.
        # 리더에 대해 두 목록 모두에서 발견된 경우, 한 번 발견된 것에 대해 점수를 반으로 줄인다.
        # 순위가 더 낮기 때문이 아니라 발견된 횟수 때문이며, 융합 후에는 어떤 비율도 이를 구분할 수 없다.
        # `break`보다는 `continue`를 사용한다. 왜냐하면 그러한 문서는 비율이 잘라내는 것보다 아래로 정렬되기 때문이다.
        # 절대적인 하한은 비율이 아니며 여전히 적용된다.
        if score is not None and score < floor:
            if score < score_floor:
                continue
            if not hit.get(LEADS_A_LIST) and parent_id not in period_supported:
                continue
        # 잘라낸 뒤에 센다. 바닥값이 떨어뜨릴 히트가 사본 자리를 먼저 차지하면
        # 살아남았을 사본까지 같이 사라진다.
        edition = _edition_key(source)
        if edition is not None:
            if edition in editions:
                continue
            editions.add(edition)
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
    # 선택과 순서는 하나의 결정이므로, 이는 _with_passages를 대체한다
    # 그것을 추적하는 대신. 풀을 처음에 여섯 개로 줄이고 재정렬한다.
    # 그 여섯 개를 복구하면 아무것도 복구되지 않는다: 재랭커가 복구하는 모든 요구사항은
    # 문서의 순위 7에서 21 사이에 있었다. 또한 판사보다 먼저 실행되므로 판사는
    # 독자가 읽을 것과 같은 방식으로 조각을 읽는다 -- 판사가 거부한 반의 질문들 중
    # 증거가 여기에 묻혀 있었던 것들이다.
    if not (rerank_chunks
            and chunks_per_document >= 2
            and select_passages(query, hits, by_parent, chunks_per_document, settings)):
        hits = _with_passages(hits, by_parent, chunks_per_document)
    if settings.search_chunk_filter:
        hits = filter_chunks(query, hits, settings)
    if answerability is None:
        answerability = settings.search_answerability_judge
    # 실제로 독자에게 전달될 문장들에 대해 마지막으로 판단한다:
    # 더 일찍 묻는다면 검색이 반환하는 텍스트와 다른 텍스트에 질문을 던지게 된다.
    #
    if answerability and is_unanswerable(query, hits, settings):
        return []
    return hits


def _current_editions(
    client: OpenSearch, alias: str, hits: list[SearchHit],
) -> dict[str, SearchHit]:
    """수정된 히트를 대체한 에디션들, 대체한 것에 따라 키가 지정됨.

    퇴역한 형태는 이전 제목을 유지하지만, 현재 형태는 이름이 변경될 수 있음 -- 38번째 개정판은 여러 개를 영어로 재작성함 -- 따라서 이전 단어로 검색하면 퇴역한 문서에만 도달함. 포인터를 따라가야만 이 단어들이 현재 유효한 형태에 도달할 수 있음.
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
    """각 대체 항목을 그 이름을 가진 퇴역 문서 바로 뒤에 배치하라."""
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
    """한 번만 쿼리를 임베딩하고, 이를 요청하는 모든 모드에 벡터를 빌려주라.

    모드 간 비교는 검색을 비교해야 함, embedding을 비교하면 안 됨: Ollama를 한 질문에 두 번 호출하면 요청에서 가장 느린 부분이 두 배가 되고, 비트 재현성이 없는 모델은 `vector`와 `hybrid`에 약간 다른 벡터를 제공할 수 있으므로, 모드가 아닌 이유로 의견이 다를 수 있음.
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
    """모든 모드를 통해 한 번의 쿼리를 실행하라, 그래서 모드들을 나란히 읽을 수 있게 하라.

    SEARCH_MODE를 전환하고 다시 검색하면 두 가지 모드를 비교하는 것만큼 두 시점을 비교함 -- 인덱스가 재구축되었을 수 있고, 누구도 메모리에서 순위 목록을 정확하게 읽지 않음. 한 요청이 두 문제를 모두 제거함.
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
    """한 사용자 검색: 문서들, 그리고 쿼리가 코드를 명명할 때 HSK 연결 정보."""
    hits = retrieve(client, alias, query, as_of, k)
    hsk_code = extract_hsk_code(query)
    settings = get_settings()
    if not settings.search_hsk_enabled or settings.search_document_datasets == "docs":
        hsk_code = None
    linkage = retrieve_hsk(client, hsk_alias, hsk_code, None, k) if hsk_code else None
    return SearchResults(query=query, hits=hits, hsk=linkage)
