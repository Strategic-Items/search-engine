"""구조화된 제어 번호와 법적 참조를 일관되게 추출한다."""

import re

CODE = re.compile(
    r"(?<![0-9A-Za-z])(?:\d[A-E]\d{3}(?:\.[a-z0-9]+)*|ML\d+)(?![0-9A-Za-z])"
    r"|제\d+조(?:의\d+)?(?:제\d+항)?(?:제\d+호)?"
    r"|별표\s?\d+(?:의\d+)?|별지\s?제\d+호(?:의\d+)?",
    re.IGNORECASE,
)


CONTROL = re.compile(r"(?<![0-9A-Za-z])(?:\d[A-E]\d{3}(?:\.[a-z0-9]+)*|ML\d+)(?![0-9A-Za-z])", re.IGNORECASE)


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def extract(text: str) -> list[str]:
    seen = set()
    out = []
    for match in CODE.findall(text):
        value = normalize(match)
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def normalize_control(value: str) -> str:
    """내부 계층 구조의 점을 유지하면서 대소문자, 공백 및 마지막 점은 무시한다."""
    return normalize(value).rstrip(".")


def extract_control_numbers(text: str) -> list[str]:
    """질문 속 통제번호(`3A002.d.1`, `ML8`)만 뽑는다. 조·별표·별지는 너무 흔해 제외한다."""
    seen: dict[str, None] = {}
    for match in CONTROL.findall(text):
        seen.setdefault(match, None)
    return list(seen)
