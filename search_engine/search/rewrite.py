"""Rewrite a colloquial question into the words the documents use.

The docs v2 set leaves BM25 six questions it cannot reach, all of them
paraphrases: the asker says "업체의 약속 문서" where the notice says
"수출자 서약서", "관청에 알리는 서류" where the form says "지위승계 통지서".
A synonym dictionary cannot close that gap -- these are phrases, not terms --
so the rewrite goes through the chat model.

The rewrite never replaces the question. Both the original and the rewrite are
searched and their rankings fused, with the original weighted higher, because a
small model's rewrite is not reliable enough to be trusted alone: measured on
its own it retrieves *worse* than the untouched question (see
docs/performance_history.md).
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

# Grounding the prompt in first-pass result titles was tried and dropped: the
# model copied a candidate title verbatim, including the wrong one, which locked
# in the first pass's mistake and took document Recall@5 from 85.0% to 80.0%.

MAX_REWRITE_CHARS = 200
_HANGUL_OR_WORD = re.compile(r"[0-9A-Za-z가-힣]")


def _is_usable(rewritten: str) -> bool:
    """Reject the ways a small model fails rather than passing them to search.

    An empty or runaway answer, markup it was told not to emit, or a reply that
    carries no searchable word at all: in each case the original question is
    already the better query, so there is nothing to fuse.
    """
    if not rewritten or len(rewritten) > MAX_REWRITE_CHARS:
        return False
    if "<" in rewritten or "```" in rewritten:
        return False
    return bool(_HANGUL_OR_WORD.search(rewritten))


def rewrite_query(query: str, settings: Settings | None = None) -> str | None:
    """The rewritten query, or None when there is nothing worth searching twice.

    Raises httpx.HTTPError if the model is unreachable; the caller decides
    whether a rewrite outage should degrade the search or fail it.
    """
    settings = settings or get_settings()
    if not query.strip():
        return None
    rewritten = generate(
        PROMPT.format(query=query.strip()),
        temperature=0.0,
        # A search query, not an answer: cap it so a model that starts
        # explaining itself is cut off rather than paid for in full.
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
