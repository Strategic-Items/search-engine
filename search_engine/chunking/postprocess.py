"""청크 목록을 색인용으로 다듬는다. 파서 `convert._element_chunks`의 본문 정리와 `export/search_jsonl.py`의
`merge_table_scaffolds`(내용 없는 표 조각을 앞 청크에 흡수)를 이식했다.

청크는 `{"text": ..., <구조 메타데이터>}` 사전이다.
"""

from __future__ import annotations

import re

_PAGE_MARKER_LINE = re.compile(r"^\s*<!--\s*page:\s*\d+\s*-->\s*$", re.MULTILINE)
_IMAGE_PLACEHOLDER_LINE = re.compile(r"^\s*!\[page \d+ image\]\(#page-\d+\)\s*$", re.MULTILINE)
# `chunk_elements()`가 셀 텍스트 없는 표 자리에 넣는 대체 문구. 색인할 내용이 아니다.
_EMPTY_TABLE_LINE = re.compile(r"^\s*\[표 셀 텍스트 없음\]\s*$", re.MULTILINE)
_BLANK_RUNS = re.compile(r"\n{3,}")

_TABLE_LINE = re.compile(r"^\s*\||\|\s*$")
_NOT_PROSE = re.compile(r"[|\-\s:*#_·.,()\[\]「」｢｣“”‘’\"'/]+")
_TABLE_SCAFFOLD_PROSE_CHARS = 40


def index_text(text: str) -> str:
    """색인 본문에서 페이지 주석, 내용 없는 이미지 자리표시, 빈 표 대체 문구를 걷어낸다."""
    text = _PAGE_MARKER_LINE.sub("", text)
    text = _IMAGE_PLACEHOLDER_LINE.sub("", text)
    text = _EMPTY_TABLE_LINE.sub("", text)
    return _BLANK_RUNS.sub("\n\n", text).strip()


def prose_length(text: str) -> int:
    """표 기호와 구두점을 걷어낸 뒤 남는 글자 수."""
    return len(_NOT_PROSE.sub("", text))


def is_table_scaffold(text: str) -> bool:
    """검색으로 꺼낼 내용 없이 표 구조만 남은 조각인지."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return True
    if not all(_TABLE_LINE.search(line) for line in lines):
        return False
    return prose_length(text) < _TABLE_SCAFFOLD_PROSE_CHARS


def _absorb_structure(into: dict, *, before: list[dict] = (), after: list[dict] = ()) -> dict:
    """흡수한 조각의 구조 메타데이터를 받는 청크에 합친다. 쪽 범위는 넓히고 `element_types`는 본문 순서의 합집합."""
    absorbed = [*before, *after]
    result = dict(into)
    spans = [m for m in absorbed if "page_start" in m and "page_end" in m]
    if spans and "page_start" in into:
        result["page_start"] = min(into["page_start"], *(m["page_start"] for m in spans))
        result["page_end"] = max(into["page_end"], *(m["page_end"] for m in spans))
    if "element_types" in into and any("element_types" in m for m in absorbed):
        ordered = [*before, into, *after]
        result["element_types"] = list(dict.fromkeys(t for m in ordered for t in m.get("element_types", [])))
    if any("image_ids" in m for m in absorbed):
        ordered = [*before, into, *after]
        result["image_ids"] = list(dict.fromkeys(i for m in ordered for i in m.get("image_ids", [])))
    return result


def merge_table_scaffolds(chunks: list[dict]) -> list[dict]:
    """내용 없는 표 조각을 앞선 본문 청크에 흡수시킨다. 앞 청크가 없는 선두 조각은 뒤따르는 첫 본문 청크 앞에 붙인다.
    문서 전체가 표 조각뿐이면 그대로 둔다."""
    if all(is_table_scaffold(chunk["text"]) for chunk in chunks):
        return list(chunks)

    merged: list[dict] = []
    leading: list[dict] = []
    for chunk in chunks:
        if is_table_scaffold(chunk["text"]):
            if merged:
                previous = merged[-1]
                merged[-1] = {**_absorb_structure(previous, after=[chunk]), "text": f"{previous['text']}\n\n{chunk['text']}"}
            else:
                leading.append(chunk)
            continue
        text = "\n\n".join([*(c["text"] for c in leading), chunk["text"]]) if leading else chunk["text"]
        merged.append({**_absorb_structure(chunk, before=list(leading)), "text": text})
        leading.clear()
    return merged
