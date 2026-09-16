"""Extract structured control numbers and legal references consistently."""

import re

CODE = re.compile(
    r"(?<![0-9A-Za-z])(?:\d[A-E]\d{3}(?:\.[a-z0-9]+)*|ML\d+)(?![0-9A-Za-z])"
    r"|제\d+조(?:의\d+)?(?:제\d+항)?(?:제\d+호)?"
    r"|별표\s?\d+(?:의\d+)?|별지\s?제\d+호(?:의\d+)?",
    re.IGNORECASE,
)


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
    """Keep internal hierarchy dots while ignoring casing, spaces and final dot."""
    return normalize(value).rstrip(".")
