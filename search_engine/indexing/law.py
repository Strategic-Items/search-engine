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


LAW_NUMBER = re.compile(r"제\s*(\d{4,6})\s*호")


def _number_key(value: str | None) -> str | None:
    """고시 `2015-145`, 법령 `30418`처럼 같은 문서 번호를 같은 문자열로 만든다."""
    if not value:
        return None
    match = NUMBER.search(value)
    if match:
        return f"{match.group(1)}-{int(match.group(2))}"
    match = LAW_NUMBER.search(value)
    return match.group(1) if match else None


def resolve_superseded(parents: dict[str, dict]) -> dict[str, str]:
    """`superseded_by`가 번호로 적힌 문서의 대체 문서를 부모 문서 ID로 푼다.

    파서는 대체 관계를 고시·법령 번호로 주는 경우가 많은데 새 판을 붙이는 검색은 부모 ID만 읽는다.
    `parents`는 부모 ID마다 `superseded_by`, `doc_number`, `doc_status`, `chunks`를 가진 사전이다.
    번호 하나가 본문·신구대비표·개정문 같은 여러 문서에 걸리므로 시행된 판(`개정`)을 안(案)보다,
    청크가 많은 문서를 적은 문서보다 먼저 고른다. 번호를 가진 문서가 없으면 풀지 않는다(키를 두지 않는다).
    """
    by_number: dict[str, list[str]] = {}
    for parent_id, info in parents.items():
        key = _number_key(info.get("doc_number"))
        if key:
            by_number.setdefault(key, []).append(parent_id)
    resolved: dict[str, str] = {}
    for parent_id, info in parents.items():
        target = info.get("superseded_by")
        if not target or target in parents:
            continue
        candidates = [c for c in by_number.get(_number_key(target) or "", []) if c != parent_id]
        if candidates:
            resolved[parent_id] = min(candidates, key=lambda c: (
                parents[c].get("doc_status") != "개정", -parents[c].get("chunks", 0), c))
    return resolved
