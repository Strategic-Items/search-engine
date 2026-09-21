"""후속 질문 압축, EgovCompressionQueryTransformer.java에서 포트됨.

세션 기록을 사용하여 "세 번째 사항의 예시를 알려 줘"와 같은 후속 질문을 검색기에서 실제로 검색할 수 있는 독립적인 질문으로 재작성한다."""

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

# 여기서 시도된 작업 예제는 제거됨: 3B 모델을 사용하면 오염된다
# 재작성은 대화의 주제가 아닌 예시의 주제를 유지하고 돌아온다.
# ("그거 연장은?" 이후 자가판정 응답이 "도서관 회원증 연장 방법"으로 돌아온 경우). 주제를 명시하는
# 주제 규칙을 명시적으로 제시하는 것은 예시들이 그러지 못했던 곳에서 성립한다.


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
    """역사와 단어를 공유하지 않는 재작성은 그 자체로 주제를 창조한다.

작은 모델들은 실제 역사가 길어질 때 few-shot 예시들에서 명사를 복사한다 -- "그거 연장은?" 이후 자가판정 응답이 "도서관 회원증 연장 방법"으로 돌아온 경우. 역사에서 빌려오는 것은 압축을 하는 유일한 이유이므로, 아무것도 빌리지 않는 재작성은 원본보다 나쁘다.
"""
    return bool(_words(rewritten) & _words(history_text))


def _render_history(history: list[Message]) -> str:
    return "\n".join(f"{m.role}: {m.content}" for m in history)


async def compress(query_text: str, history: list[Message]) -> str:
    """압축이 도움이 되지 않을 때는 원래 쿼리를 그대로 반환한다: 아직 역사가 없거나, 이전 어시스턴트 턴이 없어 맥락을 제공하지 않거나, 질문이 실제 후속 질문이 될 만큼 충분히 짧을 때.
"""
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
