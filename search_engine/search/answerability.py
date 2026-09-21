"""Ask the chat model whether the retrieved text actually answers the question.

The score cutoffs cannot do this. A question the corpus has no answer for still
retrieves the document it is about, and scores it inside the range answered
questions occupy -- on docs v2 the eight in-domain unanswerable questions were
rejected 0 of 8 by an absolute floor, 0 of 8 by a cross-encoder reranker, and
were indistinguishable from answered ones by score margin or result count. What
separates them is not relevance, which they have, but whether the fact being
asked for is written down in the passages. Only a reader can tell.

So the question put to the model is not "is this relevant" but "is the fact this
question asks for present in this text". Measured that way it rejected 7 of the
8, at the cost of refusing 14.8% of questions the corpus can answer
(docs/evaluation/stages/stage-18-llm-answerability-judge.md).

Off by default. It puts the chat model in the path of a search that otherwise
has no model dependency, and costs about two seconds against a search that takes
a tenth of one -- the same trade that keeps query rewrite off.
"""

import json
import logging

from search_engine.config import Settings, get_settings
from search_engine.rag.llm import generate
from search_engine.search.results import SearchHit

log = logging.getLogger(__name__)

# The rules go in their own turn. Folded into the user turn instead, the same
# model rejected 20.7% of answerable questions against 14.8% here.
#
# The second rule is about polarity. Without it the judge refused questions
# whose answer it had just quoted: asked whether identical specifications
# oblige a US licence, it answered that no such statement was present "and in
# fact the text says a licence need not be applied for on those grounds" --
# and returned answerable: false. Asking "is the fact this question asks for
# written down" invites reading the question's premise as that fact, so a
# document that denies the premise looks like a document that is silent on
# it. Every question this lost was a yes/no one whose answer is no.
SYSTEM = """당신은 검색 결과를 검수한다. 주어진 발췌문만 보고, 질문이 요구하는 사실이 그 안에 실제로 적혀 있는지 판단한다.
- 주제가 같아도 요구된 사실이 없으면 답할 수 없는 것이다.
- 질문이 어떤 내용의 성립 여부를 묻고 발췌문이 그것을 부정하고 있으면, 답할 수 있는 것이다. 질문의 전제를 뒤집는 근거도 근거다.
- 집계 결과, 실시간 현황, 개인별 처리 상태처럼 문서가 담지 않는 종류는 답할 수 없다.
- 추측하거나 상식으로 보충하지 않는다.
JSON만 출력한다: {"answerable": true|false, "confidence": 0.0~1.0, "reason": "한 문장"}"""

PROMPT = """질문: {query}

발췌문:
{context}"""

# How much of each document the judge sees. Trimming this is not a neutral
# knob: cutting the context to a third raised false rejections from 26 to 51
# of 135, because the evidence a document was labelled for often sits outside
# its first chunks -- the same reason the pipeline carries six per document.
DOCUMENTS_JUDGED = 3
BODY_CHARS = 1500
PASSAGES_PER_DOCUMENT = 5
PASSAGE_CHARS = 1200


def _context(hits: list[SearchHit]) -> str:
    blocks = []
    for hit in hits[:DOCUMENTS_JUDGED]:
        parts = [f"[{hit.title}]"]
        if hit.body:
            parts.append(hit.body[:BODY_CHARS])
        parts += [p.body[:PASSAGE_CHARS] for p in hit.passages[:PASSAGES_PER_DOCUMENT] if p.body]
        blocks.append("\n".join(parts))
    return "\n\n---\n\n".join(blocks)


def is_unanswerable(
    query: str, hits: list[SearchHit], settings: Settings | None = None,
) -> bool:
    """True when the model says nothing in the retrieved text answers the question.

    The verdict is taken as it comes. The model also rates its own confidence,
    and in one run those numbers looked usable -- correct refusals near 0.10,
    mistaken ones near 0.85, and honouring only the low ones would have cut
    false rejections from 14.8% to 2.2%. It did not reproduce: the same query
    against the same passages came back 0.10 in one run and 0.85 in the next,
    because the served model's output shifts with how requests are batched. The
    verdict itself was stable across every repeat. So the boolean is used and
    the number is ignored.

    Never raises. A judge that cannot be reached is not a verdict, and a search
    that already found something should not fail because a second opinion was
    unavailable.
    """
    settings = settings or get_settings()
    if not hits:
        return False
    try:
        raw = generate(PROMPT.format(query=query.strip(), context=_context(hits)),
                       temperature=0.0, max_tokens=200, settings=settings,
                       system=SYSTEM, json_object=True)
        answerable = json.loads(raw)["answerable"]
    except Exception as exc:
        log.warning("answerability judge unavailable, keeping results: %s", exc)
        return False
    return answerable is False
