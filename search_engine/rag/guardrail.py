"""Grounded-answer prompt and the no-context response."""

from search_engine.results import SearchHit

ANSWER_TEMPLATE = """당신은 전략물자 수출통제 상담을 지원하는 도우미다.
아래 '근거 자료'에 있는 내용만 사용해 답한다.

반드시 지킬 것:
1. 근거 자료에 없는 내용은 답하지 않는다. 추측하거나 일반 상식으로 메우지 마라.
2. 답변에 사용한 조문·별표를 그대로 인용하고, 해당 고시의 시행일을 함께 밝힌다.
3. 특정 품목의 통제 해당 여부를 확정적으로 단정하지 마라.
   "해당한다" / "해당하지 않는다" 로 끝내지 말고, 근거와 함께 확인이 필요한 지점을 밝힌다.
4. 답변 말미에 다음을 항상 덧붙인다:
   "최종 판정은 전략물자관리시스템(yesTrade)의 전문판정 신청을 통해 확인하시기 바랍니다."

근거 자료:
---------------------
{context}
---------------------

질문: {query}

답변:
"""

EMPTY_CONTEXT_ANSWER = (
    "문의하신 내용에 대해 확인 가능한 근거 자료를 찾지 못했습니다.\n"
    "정확한 확인을 위해 전략물자관리시스템(yesTrade)의 전문판정 신청을 이용해 주시기 바랍니다."
)


def format_documents(documents: list[SearchHit]) -> str:
    parts = []
    for doc in documents:
        effective = doc.effective_from or "확인 필요"
        source = f" · 출처 {doc.source_url}" if doc.source_url else ""
        superseded = f" · 대체됨: {doc.superseded_by}" if doc.superseded_by else ""
        body = doc.body or doc.title
        parts.append(
            f"[{doc.source_type} · {doc.title} · 시행일 {effective}{source}{superseded}]\n{body}"
        )
    return "\n\n".join(parts)


def build_prompt(query_text: str, documents: list[SearchHit]) -> str | None:
    if not documents:
        return None
    return ANSWER_TEMPLATE.format(context=format_documents(documents), query=query_text)
