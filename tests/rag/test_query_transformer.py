from unittest.mock import AsyncMock

from search_engine.rag.models import Message
from search_engine.rag import query_transformer


async def test_compression_is_skipped_without_history(monkeypatch):
    complete = AsyncMock()
    monkeypatch.setattr(query_transformer, "complete", complete)
    assert await query_transformer.compress("그거 연장은 어떻게 해?", []) == "그거 연장은 어떻게 해?"
    complete.assert_not_awaited()


async def test_compression_is_skipped_without_assistant_context(monkeypatch):
    complete = AsyncMock()
    monkeypatch.setattr(query_transformer, "complete", complete)
    history = [Message("user", "자가판정")]
    assert await query_transformer.compress("그거 연장은 어떻게 해?", history) == "그거 연장은 어떻게 해?"
    complete.assert_not_awaited()


async def test_compression_is_skipped_for_an_incomplete_question(monkeypatch):
    complete = AsyncMock()
    monkeypatch.setattr(query_transformer, "complete", complete)
    history = [Message("assistant", "자가판정 유효기간은 2년입니다.")]
    assert await query_transformer.compress("그거", history) == "그거"
    complete.assert_not_awaited()


async def test_compression_removes_thinking_and_rejects_answer_like_output(monkeypatch):
    history = [Message("assistant", "자가판정 유효기간을 설명했습니다.")]
    monkeypatch.setattr(query_transformer, "complete", AsyncMock(
        return_value="<think>reasoning</think>자가판정 유효기간 연장 방법"
    ))
    assert await query_transformer.compress("그거 연장은 어떻게 해?", history) == "자가판정 유효기간 연장 방법"

    monkeypatch.setattr(query_transformer, "complete", AsyncMock(return_value="설명: 다음과 같습니다"))
    assert await query_transformer.compress("그거 연장은 어떻게 해?", history) == "그거 연장은 어떻게 해?"


async def test_a_rewrite_that_borrows_nothing_from_the_history_is_discarded(monkeypatch):
    # Small models copy a noun out of the few-shot examples when the real history
    # runs long, inventing a subject the conversation never mentioned.
    history = [Message(role="user", content="자가판정 유효기간"),
               Message(role="assistant", content="자가판정 유효기간은 2026년 9월 1일부터 시행됩니다.")]

    async def invent(prompt, temperature=0.0):
        return "도서관 회원증 연장 방법"

    monkeypatch.setattr(query_transformer, "complete", invent)

    assert await query_transformer.compress("그거 연장은 어떻게 해?", history) == "그거 연장은 어떻게 해?"


async def test_a_rewrite_that_carries_the_subject_down_is_kept(monkeypatch):
    history = [Message(role="user", content="자가판정 유효기간"),
               Message(role="assistant", content="자가판정 유효기간은 2026년 9월 1일부터 시행됩니다.")]

    async def carry(prompt, temperature=0.0):
        return "자가판정 유효기간 연장 방법"

    monkeypatch.setattr(query_transformer, "complete", carry)

    assert await query_transformer.compress("그거 연장은 어떻게 해?", history) == "자가판정 유효기간 연장 방법"
