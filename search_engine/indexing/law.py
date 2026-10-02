"""법령·고시 카테고리: 파서가 부모 문서에 붙인 `document` 속성을 청크마다 펼친다."""

import re

NUMBER = re.compile(r"(\d{4})\s*-\s*(\d{1,4})\s*호")


def _joined(value) -> str | None:
    return ", ".join(value) if isinstance(value, list) else value


def law_source(source: dict) -> dict:
    """색인할 _source에 검색용 속성 필드를 더한다. 값이 없는 속성은 필드를 만들지 않는다.

    채움률이 낮은 속성(고시 번호 4/20, 시행일 4/20)은 필터가 아니라 있을 때만 맞는 신호로 쓴다.
    """
    attrs = source.get("document") or {}
    number = attrs.get("document_number")
    match = NUMBER.search(number) if number else None
    fields = {
        "doc_type": attrs.get("document_type"),
        "doc_status": attrs.get("status"),
        "doc_number": number,
        "doc_number_norm": f"{match.group(1)}-{int(match.group(2))}" if match else None,
        "issuer": attrs.get("source"),
        "revision_date": attrs.get("revision_date"),
        # 기존 검색 경로가 이미 읽는 유효 기간 필드에 연결한다.
        "effective_from": attrs.get("effective_date"),
        "effective_to": attrs.get("expiry_date"),
        # 파서는 대체한 고시 번호를 리스트로 준다. SearchHit은 문자열 하나만 받는다.
        "superseded_by": _joined(attrs.get("superseded_by")),
    }
    source.update({key: value for key, value in fields.items() if value})
    return source


def law_embedding_title(source: dict) -> str:
    """제목에 조문·별표 경로를 붙인다. 표 행 한 줄짜리 청크는 이 경로 없이는 무엇의 일부인지 알 수 없다."""
    path = " > ".join(source.get("heading_path") or [])
    title = source["title"]
    return f"{title} — {path}" if path else title
