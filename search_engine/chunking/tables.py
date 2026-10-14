"""번들의 표 원소(HTML 또는 파이프 표) -> `table_rows.logical_tables`가 받는 표 자료.

파서는 표를 두 번 쓴다: 격자 -> Markdown(`pdfstruct.normalize.table_markdown`, 번들에 남는 것)과 격자 -> 표 자료
(`pdfstruct.tabledata`, 청커가 받는 것). 여기서는 앞의 것에서 뒤의 것을 되만든다. 되살릴 수 있는 것: 행·열·병합 범위·
칸 글자·쪽. 되살릴 수 없는 것(설계 문서 "번들에서 얼마나 되돌릴 수 있는가"): 머리글 행의 배경색 표시(`header_rows`),
쪽마다 되풀이되는 머리글의 제거, PDF 칸 안의 목록 줄바꿈(Markdown 표는 공백으로 이었다), 격자 없는 표(`degraded`).
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from search_engine.chunking import patterns

_PAGE_PART = re.compile(r"(?m)^<!--\s*page:\s*(\d+)\s*-->\n")
_PIPE_SEPARATOR = re.compile(r"^\|(?:\s*:?-{3,}:?\s*\|)+$|^\|(?:---\|)+$")


class _HtmlGrid(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[dict]] = []
        self._cell: dict | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.rows.append([])
        elif tag in ("td", "th"):
            attrs = dict(attrs)
            self._cell = {"rs": int(attrs.get("rowspan") or 1), "cs": int(attrs.get("colspan") or 1),
                          "text": "", "header": tag == "th"}
        elif tag == "br" and self._cell is not None:
            self._cell["text"] += "\n"

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self.rows[-1].append(self._cell)
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["text"] += data


def _html_cells(html: str) -> list[dict]:
    parser = _HtmlGrid()
    parser.feed(html)
    taken: set[tuple[int, int]] = set()
    cells = []
    for r, row in enumerate(parser.rows):
        c = 0
        for cell in row:
            while (r, c) in taken:
                c += 1
            cells.append({"r": r, "c": c, "rs": cell["rs"], "cs": cell["cs"],
                          "text": cell["text"], "header": cell["header"]})
            for rr in range(r, r + cell["rs"]):
                for cc in range(c, c + cell["cs"]):
                    taken.add((rr, cc))
            c += cell["cs"]
    return cells


def _split_pipe_row(line: str) -> list[str]:
    """`| a | b |` -> ["a", "b"]. 칸 글자의 `\\|`와 `\\\\`는 되돌린다(`table_markdown`이 이스케이프한 것)."""
    body = line.strip()
    body = body[1:] if body.startswith("|") else body
    body = body[:-1] if body.endswith("|") and not body.endswith("\\|") else body
    cells, current, i = [], [], 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body) and body[i + 1] in "\\|":
            current.append(body[i + 1])
            i += 2
            continue
        if ch == "|":
            cells.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    cells.append("".join(current))
    # `"| " + " | ".join(…) + " |"`가 칸마다 앞뒤에 공백 하나씩 붙였다 -- 칸 글자의 공백은 건드리지 않는다
    return [(c[1:] if c.startswith(" ") else c)[:-1 if c.endswith(" ") else None].replace("<br>", "\n") for c in cells]


def _pipe_cells(text: str) -> list[dict]:
    lines = [line for line in text.splitlines() if line.strip()]
    rows = [_split_pipe_row(line) for i, line in enumerate(lines) if not (i == 1 and _PIPE_SEPARATOR.match(line.strip()))]
    return [{"r": r, "c": c, "rs": 1, "cs": 1, "text": value,
             "source_header": bool(r == 0 and len(lines) > 1 and _PIPE_SEPARATOR.match(lines[1].strip()))} for r, row in enumerate(rows) for c, value in enumerate(row)]


def _part_cells(text: str) -> list[dict] | None:
    stripped = text.strip()
    if stripped.startswith("<table"):
        return _html_cells(stripped)
    if stripped.startswith("|"):
        return _pipe_cells(stripped)
    return None


_ONE_SYLLABLE = re.compile(r"^[가-힣]$")
_HYPHEN_END = re.compile(r"[A-Za-z]-$")


def _tier_of(text: str) -> str | None:
    for name, pattern in patterns.HEADING_TIERS:
        if pattern.match(text):
            return name
    return None


def _join_syllable_runs(lines: list[str]) -> list[str]:
    out: list[str] = []
    run: list[str] = []

    def flush() -> None:
        out.append("".join(run)) if len(run) >= 2 else out.extend(run)
        run.clear()

    for ln in lines:
        if _ONE_SYLLABLE.match(ln):
            run.append(ln)
        else:
            flush()
            out.append(ln)
    flush()
    return out


def clean_cell(text: str) -> str:
    """PDF 칸 글자 정리(파서 `pdfstruct.tabledata.clean_cell`과 같다): 칸 폭 때문에 갈린 줄은 이어 붙이고 목록 표식 줄은
    줄바꿈을 남긴다. HWP 칸은 이 정리를 거치지 않는다(문단 경계가 그대로 남는다)."""
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    if not lines:
        return ""
    lines = _join_syllable_runs(lines)
    out = lines[0]
    for ln in lines[1:]:
        if patterns.BULLET_START.match(ln) or _tier_of(ln) is not None:
            out += "\n" + ln
        elif _HYPHEN_END.search(out):
            out = out[:-1] + ln
        else:
            out += " " + ln
    return out


def _matrix(cells: list[dict], *, hard_breaks: bool) -> tuple[list[list[str]], list[dict]]:
    rows = max(c["r"] + c["rs"] for c in cells)
    cols = max(c["c"] + c["cs"] for c in cells)
    matrix = [["" for _ in range(cols)] for _ in range(rows)]
    merges = []
    for cell in cells:
        matrix[cell["r"]][cell["c"]] = cell["text"] if hard_breaks else clean_cell(cell["text"])
        if cell["rs"] > 1 or cell["cs"] > 1:
            merges.append({"row": cell["r"], "col": cell["c"], "rowspan": cell["rs"], "colspan": cell["cs"]})
    return matrix, merges


def table_objects(text: str, page: int, *, hard_breaks: bool) -> list[dict]:
    """표 원소 하나의 글자 -> 논리 표 자료 목록(`tabledata.node_tables(fill_merged=True)` 모양).

    쪽 표지로 갈린 부분(`parts`)은 열 수가 같으면 앞 표에 잇고(행별 쪽을 `row_pages`로 남긴다), 다르면 별도 표로 둔다.
    """
    pieces = _PAGE_PART.split(text)
    parts = [(int(pieces[i]), pieces[i + 1]) for i in range(1, len(pieces) - 1, 2)] if len(pieces) > 1 else [(page, text)]
    tables: list[dict] = []
    for part_page, part_text in parts:
        cells = _part_cells(part_text)
        if not cells:
            continue
        matrix, merges = _matrix(cells, hard_breaks=hard_breaks)
        header_rows = 0
        for row_index in range(len(matrix)):
            row_cells = [cell for cell in cells if cell["r"] == row_index]
            if (row_cells and any(cell.get("header") for cell in row_cells)
                    and all(cell.get("header") or not cell["text"].strip() for cell in row_cells)):
                header_rows += 1
            else:
                break
        if tables and len(tables[-1]["rows"][0]) == len(matrix[0]):
            table = tables[-1]
            base = len(table["rows"])
            table["source_cells"] += [{**c, "header": c.get("header", c.get("source_header", False)), "r": c["r"] + base, "page": part_page} for c in cells]
            table["rows"] += matrix
            table["merges"] += [{**m, "row": m["row"] + base} for m in merges]
            table["_row_pages"] += [part_page] * len(matrix)
            if part_page not in table["pages"]:
                table["pages"].append(part_page)
            continue
        tables.append({"type": "table", "rows": matrix, "header_rows": header_rows, "header_cols": 0, "merges": merges,
                       "source_cells": [{**c, "header": c.get("header", c.get("source_header", False)), "page": part_page} for c in cells],
                       "pages": [part_page], "_row_pages": [part_page] * len(matrix),
                       **({"hard_breaks": True} if hard_breaks else {})})
    for table in tables:
        for m in table["merges"]:
            value = table["rows"][m["row"]][m["col"]]
            for r in range(m["row"], min(m["row"] + m["rowspan"], len(table["rows"]))):
                for c in range(m["col"], min(m["col"] + m["colspan"], len(table["rows"][r]))):
                    table["rows"][r][c] = value
        row_pages = table.pop("_row_pages")
        if len(set(row_pages)) > 1:
            table["row_pages"] = row_pages
    return tables


def element_tables(elements: list[dict], *, hard_breaks: bool) -> list[list[dict]]:
    """`chunk_elements(tables=...)`용 표 자료. 인접 페이지에서 이어지는 표 조각에는 앞 구간의 열 이름을 물려준다."""
    from search_engine.chunking.table_rows import comparison_columns, logical_tables

    table_elements = [(i, element) for i, element in enumerate(elements) if element["type"] == "table"]
    result: list[list[dict]] = []
    previous: dict | None = None
    for table_index, (element_position, element) in enumerate(table_elements):
        objects = table_objects(element["text"], element.get("page", 1), hard_breaks=hard_breaks) if element["text"].strip() else []
        result.append(objects)
        if not objects:
            continue

        first_page = min(page for obj in objects for page in obj["pages"])
        last_page = max(page for obj in objects for page in obj["pages"])
        logical = [table for obj in objects for table in logical_tables(obj)]
        named_comparison = next((table.columns for table in logical
                                 if comparison_columns(table.columns)
                                 and not all(name == f"열{i + 1}" for i, name in enumerate(table.columns))), None)
        continuation = False
        if previous is not None:
            previous_position = table_elements[previous["last_index"]][0]
            bridge = elements[previous_position + 1:element_position]
            generic_columns = all(name == f"열{i + 1}" for i, name in enumerate(logical[0].columns))
            schema_matches = logical[0].columns == previous["columns"] or generic_columns
            connected = (first_page == previous["last_page"] + 1
                         and len(previous["columns"]) == len(logical[0].columns)
                         and all(item["type"] == "paragraph" and len(" ".join(item.get("text", "").split())) <= 12
                                 for item in bridge))
            first_values = [row[0].strip() for row in logical[0].rows if row and row[0].strip()]
            identifiers = sum(bool(re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z .,/_-]{0,35}", value))
                              and bool(re.search(r"\d", value)) for value in first_values)
            continuation = (connected and schema_matches and len(first_values) >= 3
                            and identifiers / len(first_values) >= 0.6)

        if continuation:
            columns = previous["columns"]
            for obj in objects:
                obj["column_names"] = columns
            segment_index = len(previous["segments"])
            row_offset = previous["row_count"]
            segment_rows = sum(len(table.rows) for table in logical)
            previous["segments"].append(objects)
            previous["row_count"] += segment_rows
            previous["last_page"] = last_page
            previous["last_index"] = table_index
            for index, segment in enumerate(previous["segments"]):
                segment_offset = sum(previous["segment_rows"][:index])
                for obj in segment:
                    obj["table_continuation"] = {
                        "group": previous["group"], "segment": index,
                        "segment_count": len(previous["segments"]),
                        "page_start": previous["page_start"], "page_end": previous["last_page"],
                        "row_offset": segment_offset, "row_count": previous["row_count"],
                    }
            previous["segment_rows"].append(segment_rows)
            continue

        if named_comparison:
            previous = {"group": table_index, "last_index": table_index, "last_page": last_page,
                        "page_start": first_page, "columns": named_comparison, "segments": [objects],
                        "segment_rows": [sum(len(table.rows) for table in logical)],
                        "row_count": sum(len(table.rows) for table in logical)}
        else:
            previous = None
    if not hard_breaks:
        _inherit_column_names(elements, table_elements, result)
    return result


def _inherit_column_names(elements: list[dict], table_elements: list[tuple[int, dict]],
                          tables: list[list[dict]]) -> None:
    """페이지 경계에서 빠진 머리글만 복구한다. 표 ID·행 경계는 변경하지 않는다.

    같은 문서의 연속 페이지와 같은 열 수가 필요하다. 새 제목·별표·서식에서 끊고,
    열 수가 깨진 구간에는 이름을 붙이지 않는다. 번호 목록을 제목으로 파싱한 PDF는 이어진 본문이다.
    """
    from search_engine.chunking.table_rows import logical_tables

    anchor: dict | None = None
    for (position, element), objects in zip(table_elements, tables):
        if not objects:
            anchor = None
            continue
        logical = [lt for obj in objects for lt in logical_tables(obj)]
        first_page = min(page for obj in objects for page in obj["pages"])
        last_page = max(page for obj in objects for page in obj["pages"])
        if anchor:
            bridge = elements[anchor["position"] + 1:position]
            boundary = any(
                (item["type"] == "heading" and not re.match(r"^\d+[.)]\s", item["text"]))
                or re.match(r"^\s*(?:[\[【〔〈<■]\s*)?(?:별표|별지|붙임|부록)\s*\d", item["text"])
                for item in bridge
            )
            if boundary or first_page != anchor["last_page"] + 1:
                anchor = None
        columns = logical[0].columns
        generic = bool(columns) and all(name == f"열{i + 1}" for i, name in enumerate(columns))
        if anchor and generic:
            if len(columns) == len(anchor["columns"]):
                for obj, lt in zip(objects, logical):
                    if all(name == f"열{i + 1}" for i, name in enumerate(lt.columns)):
                        obj["column_names"] = list(anchor["columns"])
            anchor.update(position=position, last_page=last_page)
        elif columns and not any(re.fullmatch(r"열\d+", name) for name in columns):
            anchor = {"columns": list(columns), "position": position, "last_page": last_page}
        else:
            anchor = None
