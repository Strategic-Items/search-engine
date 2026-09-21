""" colloquial question를 문서에서 사용하는 단어로 재작성한다.

docs v2 세트는 BM25가 도달할 수 없는 여섯 개의 질문을 남긴다. 이 모든 질문은 paraphrase이다: 사용자가 "업체의 약속 문서"라고 말하는 반면, 공지문은 "수출자 서약서"라고 하고, "관청에 알리는 서류"는 양식에서 "지위승계 통지서"라고 한다.
동의어 사전은 이 갭을 메울 수 없다. 이들은 용어가 아니라 구절이기 때문이다. 따라서 재작성은 챗 모델을 통해 진행된다.

재작성은 질문을 대체하지 않는다. 원본과 재작성된 질문 모두 검색되며, 그 순위는 융합되며, 원본은 더 높은 가중치를 받는다. 작은 모델의 재작성은 단독으로 신뢰할 만할 정도로 신뢰할 수 없기 때문이다. 자체적으로 측정했을 때, 재작성된 질문은 원본보다 *더 나쁜* 결과를 도출한다(see docs/evaluation/stages/stage-05-query-rewrite.md).
"""

import logging
import re

from search_engine.config import Settings, get_settings
from search_engine.rag.llm import generate

log = logging.getLogger(__name__)

PROMPT = """다음 질문을 한국 산업통상·무역안보 분야 공고·법령 문서 검색에 쓸 검색어로 다시 써라.

규칙:
- 검색어만 출력한다. 설명, 사고과정, 태그, 따옴표를 쓰지 마라.
- 일상적인 표현을 행정 문서가 쓰는 공식 용어로 바꾼다.
  (예: 사고파는 일 → 거래, 관청에 알리는 서류 → 신고서, 약속 문서 → 서약서)
- 질문에 없는 새로운 주제를 만들어 넣지 마라. 확실하지 않으면 원래 낱말을 그대로 둔다.
- 핵심 명사 위주로 15어절 이내.

질문: {query}
검색어:"""

# 첫 번째 패스 결과 제목에 프롬프트를 기반화하는 것은 시도되었으나 폐기되었다: 모델은 후보 제목을 그대로 복사했으며, 잘못된 제목도 포함하여, 첫 번째 패스의 실수를 고정시켰고, 문서 Recall@5를 85.0%에서 80.0%로 낮췄다.
# 첫 번째 패스 결과 제목에 프롬프트를 기반화하는 것은 시도되었으나 폐기되었다: 모델은 후보 제목을 그대로 복사했으며, 잘못된 제목도 포함하여, 첫 번째 패스의 실수를 고정시켰고, 문서 Recall@5를 85.0%에서 80.0%로 낮췄다.
# 첫 번째 패스 결과 제목에 프롬프트를 기반화하는 것은 시도되었으나 폐기되었다: 모델은 후보 제목을 그대로 복사했으며, 잘못된 제목도 포함하여, 첫 번째 패스의 실수를 고정시켰고, 문서 Recall@5를 85.0%에서 80.0%로 낮췄다.

MAX_REWRITE_CHARS = 200
_HANGUL_OR_WORD = re.compile(r"[0-9A-Za-z가-힣]")


def _is_usable(rewritten: str) -> bool:
    """작은 모델이 실패하는 방식을 거부하라. 검색에 전달하지 말라.

    빈 값이거나 통제되지 않은 답변, 모델에게 발행하지 말라고 지시된 마크업, 또는
    검색 가능한 단어를 전혀 포함하지 않는 응답: 각각의 경우 원래 질문이
    더 나은 쿼리이므로 융합할 것이 없다.
    """
    if not rewritten or len(rewritten) > MAX_REWRITE_CHARS:
        return False
    if "<" in rewritten or "```" in rewritten:
        return False
    return bool(_HANGUL_OR_WORD.search(rewritten))


def rewrite_query(query: str, settings: Settings | None = None) -> str | None:
    """재작성된 쿼리, 또는 두 번 검색할 만한 것이 없을 때 None.

    모델에 접근할 수 없을 경우 httpx.HTTPError을 발생시킨다; 호출자는
    재작성 장애가 검색을 저하시켜야 하는지 아니면 실패시켜야 하는지를 결정한다.
    """
    settings = settings or get_settings()
    if not query.strip():
        return None
    rewritten = generate(
        PROMPT.format(query=query.strip()),
        temperature=0.0,
        # 검색 쿼리, 답변이 아님: 모델이 시작할 때 제한
        # 설명 자체가 완전히 지불되기보다는 잘려진다.
        max_tokens=64,
        settings=settings,
    ).strip()
    if "<think>" in rewritten:
        rewritten = rewritten.split("</think>")[-1].strip()
    if not _is_usable(rewritten):
        log.info("discarded unusable query rewrite for %r", query[:40])
        return None
    if rewritten == query.strip():
        return None
    return rewritten
