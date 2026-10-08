"""Markdown -> 정규화 원소 목록. 파서 `normalized_markdown.elements_to_markdown`의 역변환.

번들의 `text.markdown`은 원소를 빈 줄로 구분해 한 블록씩 쓴 것이다. 되돌릴 수 있는 것과 없는 것
([설계](../../docs/design/chunking_ownership_move.md) "번들에서 얼마나 되돌릴 수 있는가"):

- 제목: `#`의 개수가 수준. 쪽: `<!-- page: N -->`가 홀로 선 블록이면 쪽 바뀜.
- 표: `<table>…</table>`(병합 칸 있음) 또는 `|`로 시작하는 파이프 표. 표 한 원소가 여러 쪽에 걸치면(`parts`)
  쪽마다 `<!-- page: N -->` + 표가 한 블록으로 이어 붙어 나온다 -- 서로 다른 쪽의 연속된 표 블록 사이에
  홀로 선 쪽 표지가 없으면 한 원소로 합친다. 같은 쪽의 두 표는 다른 원소로 둔다(구분할 수 없어 보수적으로).
  표 안의 글자는 여기서 해석하지 않는다(`text` 그대로). 격자 복원은 `tables.py`.
- 그림: `![alt](<assets/…>)`(파일 있음), `<!-- image: file not saved -->`(파일 없음), `![page N image](#page-N)`(자리표시).
- 나머지는 전부 문단(`paragraph`). 목록 항목은 원래 표지가 글자에 접혀 있어 문단과 구분하지 않는다.

쪽 표지가 하나도 없는 문서(HWP 일부)는 `has_pages=False`다 -- 원소의 `page`는 1로 둘 뿐이고 청크에 쪽을 싣지 않아야 한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PAGE_ONLY = re.compile(r"^<!--\s*page:\s*(\d+)\s*-->$")
_PAGE_ANY = re.compile(r"<!--\s*page:\s*(\d+)\s*-->")
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.DOTALL)
_IMAGE_FILE = re.compile(r"^!\[([^\]]*)\]\(<?([^)>]+)>?\)$")
_IMAGE_PLACEHOLDER = re.compile(r"^!\[page \d+ image\]\(#page-\d+\)$")
_IMAGE_UNSAVED = "<!-- image: file not saved -->"
_TABLE_UNAVAILABLE = "<!-- table content unavailable -->"


@dataclass
class ParsedMarkdown:
    elements: list[dict]
    has_pages: bool


def _blocks(markdown: str) -> list[str]:
    """빈 줄로 나눈 블록. 단, `<table>`~`</table>`은 안에 빈 줄이 있어도 한 블록이다."""
    blocks: list[str] = []
    current: list[str] = []
    in_table = False
    for line in markdown.splitlines():
        if in_table:
            current.append(line)
            if "</table>" in line:
                in_table = False
            continue
        if not line.strip():
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        current.append(line)
        if "<table" in line and "</table>" not in line:
            in_table = True
    if current:
        blocks.append("\n".join(current).strip())
    return blocks


def _is_table(block: str) -> bool:
    body = _PAGE_ANY.sub("", block, count=1).lstrip() if _PAGE_ANY.match(block) else block
    return body.startswith("<table") or (body.startswith("|") and "\n" in body.strip() and "---" in body)


def _has_inline_page(block: str) -> bool:
    """쪽 표지로 시작하지만 표지만은 아닌 블록(표 한 부분)."""
    return bool(_PAGE_ANY.match(block)) and not _PAGE_ONLY.match(block)


def markdown_to_elements(markdown: str) -> ParsedMarkdown:
    elements: list[dict] = []
    page = 1
    has_pages = bool(_PAGE_ANY.search(markdown))
    pending_marker_between = True  # 직전 원소 이후 홀로 선 쪽 표지가 있었는가(표 부분 합치기 판단)

    def add(kind: str, text: str, **extra) -> dict:
        element = {"id": f"e{len(elements)}", "type": kind, "text": text, "page": page, **extra}
        elements.append(element)
        return element

    for block in _blocks(markdown):
        only = _PAGE_ONLY.match(block)
        if only:
            page = int(only.group(1))
            pending_marker_between = True
            continue
        if _is_table(block):
            first = _PAGE_ANY.match(block)
            block_page = int(first.group(1)) if first else page
            previous = elements[-1] if elements else None
            if (previous is not None and previous["type"] == "table" and not pending_marker_between
                    and _has_inline_page(block) and _has_inline_page(previous["text"])
                    and block_page != previous["page"]):
                previous["text"] = f"{previous['text']}\n\n{block}"  # 여러 쪽에 걸친 한 표
            else:
                add("table", block, **({"page": block_page} if first else {}))
            pending_marker_between = False
            continue
        pending_marker_between = False
        heading = _HEADING.match(block)
        if heading and "\n" not in heading.group(2):
            add("heading", heading.group(2).strip(), level=len(heading.group(1)))
        elif block == _TABLE_UNAVAILABLE:
            add("table", "")
        elif block == _IMAGE_UNSAVED:
            add("image", "")
        elif _IMAGE_PLACEHOLDER.match(block):
            add("image", "")
        elif (image := _IMAGE_FILE.match(block)):
            alt = image.group(1)
            add("image", "" if alt == "image" else alt, path=image.group(2))
        else:
            add("paragraph", block)
    return ParsedMarkdown(elements=elements, has_pages=has_pages)
