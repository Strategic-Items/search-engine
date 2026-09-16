"""Follow-up question compression, ported from EgovCompressionQueryTransformer.java.

Rewrites a follow-up like "세 번째 사항의 예시를 알려 줘" into a standalone
question the retriever can actually search on, using session history.
"""

import re

from search_engine.rag.llm import complete
from search_engine.rag.models import Message

_WORD = re.compile(r"[0-9A-Za-z가-힣]{2,}")

_COMPRESSION_PROMPT = """You rewrite a follow-up question into a standalone search query.

RULES:
- Output ONLY the rewritten query, nothing else.
- NO explanations, NO thinking process, NO <think> tags, NO XML tags.
- Keep the same language as the follow-up question.
- The rewritten query MUST contain the main subject noun from the conversation below.
- Never introduce a topic that does not appear in the conversation.

Conversation:
{history}

Follow-up: {query}
Rewritten query:"""

# Worked examples were tried here and removed: with a 3B model they contaminate the
# rewrite, which comes back carrying the example's subject instead of the conversation's
# ("그거 연장은?" after a 자가판정 answer returned "도서관 회원증 연장 방법"). Stating the
# subject rule outright holds up where the examples did not.


def _is_incomplete(text: str) -> bool:
    stripped = text.strip()
    return len(stripped) < 5 or len(stripped.split()) < 2


def _looks_like_an_answer(text: str) -> bool:
    if any(marker in text for marker in ("```", "function", "const ", "return ", "class ")):
        return True
    if any(marker in text for marker in ("다음과 같습니다", "설명:", "코드는")):
        return True
    return len(text) > 200


def _words(text: str) -> set[str]:
    return {word.lower() for word in _WORD.findall(text)}


def _borrows_from(rewritten: str, history_text: str) -> bool:
    """A rewrite that shares no word with the history invented its subject.

    Small models copy a noun out of the few-shot examples when the real history
    runs long -- "그거 연장은?" after a 자가판정 answer came back as
    "도서관 회원증 연장 방법". Borrowing from the history is the only reason to
    compress at all, so a rewrite that borrows nothing is worse than the original.
    """
    return bool(_words(rewritten) & _words(history_text))


def _render_history(history: list[Message]) -> str:
    return "\n".join(f"{m.role}: {m.content}" for m in history)


async def compress(query_text: str, history: list[Message]) -> str:
    """Returns the original query unchanged whenever compression can't help:
    no history yet, no prior assistant turn to give context, or the question
    is too short to be a real follow-up."""
    if not history:
        return query_text
    if not any(m.role == "assistant" for m in history):
        return query_text
    if _is_incomplete(query_text):
        return query_text

    history_text = _render_history(history)
    prompt = _COMPRESSION_PROMPT.format(history=history_text, query=query_text)
    rewritten = (await complete(prompt, temperature=0.0)).strip()

    if "<think>" in rewritten:
        rewritten = rewritten.split("</think>")[-1].strip()

    if not rewritten or "<" in rewritten or _looks_like_an_answer(rewritten):
        return query_text
    if not _borrows_from(rewritten, history_text):
        return query_text
    return rewritten
