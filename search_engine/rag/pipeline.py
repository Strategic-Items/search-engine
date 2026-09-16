"""Compression, retrieval, guardrail construction, and answer streaming."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from search_engine.rag import guardrail, llm, query_transformer, retriever
from search_engine.rag.memory import DEFAULT_CONVERSATION_ID, chat_memory
from search_engine.rag.models import Message


@dataclass
class Turn:
    message: str
    session_id: str
    prompt: str | None


@dataclass
class StreamError:
    """A post-header failure that the SSE adapter renders as an error event."""

    message: str = "answer generation unavailable"


async def prepare_turn(message: str, session_id: str | None = None) -> Turn:
    resolved_session_id = session_id or DEFAULT_CONVERSATION_ID
    history = chat_memory.get(resolved_session_id)
    try:
        query_text = await query_transformer.compress(message, history)
    except httpx.HTTPError:
        query_text = message
    documents = await retriever.retrieve(query_text)
    return Turn(message=message, session_id=resolved_session_id,
                prompt=guardrail.build_prompt(query_text, documents))


async def stream_answer(turn: Turn) -> AsyncIterator[str | StreamError]:
    if turn.prompt is None:
        answer = guardrail.EMPTY_CONTEXT_ANSWER
        chat_memory.add(turn.session_id, Message(role="user", content=turn.message))
        chat_memory.add(turn.session_id, Message(role="assistant", content=answer))
        yield answer
        return

    answer_parts: list[str] = []
    try:
        async for chunk in llm.stream_chat(turn.prompt):
            answer_parts.append(chunk)
            yield chunk
    except httpx.HTTPError:
        yield StreamError()
        return
    chat_memory.add(turn.session_id, Message(role="user", content=turn.message))
    chat_memory.add(turn.session_id, Message(role="assistant", content="".join(answer_parts)))
