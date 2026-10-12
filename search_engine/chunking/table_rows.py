# 이식 원본: unstructured-doc-parser_ver2 src/docparser/chunking/table_rows.py (def6caf, 규칙 20개 삭제 뒤) -- 본문은 그대로 두고 import만 바꿨다.
"""표 자료(`tabledata`) -> 행 청크용 논리 표.

`tabledata`의 격자는 PDF에 그려진 선을 따른 것이라 그대로 행 청크를 만들면 두 가지가 어긋난다(2026-09-29 코퍼스 실측,
행으로 나눈 표 164개 중 열 이름이 하나도 없던 표 45개를 원인별로 나눴다):

1. **표 제목이 격자 첫 행에 들어간다** -- `<표 2> 수출지역의 ...`이 가로 병합으로 여러 칸을 채운 행. 머리글로도 데이터로도
   쓰면 안 된다. 떼어서 `caption`으로 둔다.
2. **가로 병합된 머리글이 머리글로 인식되지 않는다** -- `tabledata`는 병합 칸의 글자를 칸마다 채워 주므로(`fill_merged`)
   `특례 | 특례 | 특례 | 등급 | 등급`처럼 같은 값이 이어진다. 머리글 판정에서 이어진 같은 값은 한 칸으로 본다.

표 종류를 가르던 판정(빈 서식·목록 같은 표·목록형 표), 표 첫 행 본문 분리, 붙은 표 나누기, 앞 행 키 물려받기는 특정 문서에서
나온 규칙이라 2026-10-08에 걷어냈다(`CHUNKING_RULES.md`). 여기 남은 것은 표 구조(제목·머리글·열 이름·단위·병합)를 읽는 일이다.

머리글은 배경색 감지(`tabledata.header_rows`)가 있으면 그걸 쓰고, 없으면 생김새로 짐작한다(`_header_like`). 숫자 칸·긴 칸이
있는 행은 데이터로 본다. 짐작이 틀려 데이터 행을 머리글로 쓰면 그 행 청크 하나가 빠지고 열 이름이 이상해진다 -- 대신 값과
열 순서는 `values`에 그대로 남는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from search_engine.chunking.params import DEFAULT_POLICY, ChunkPolicy

_HEADER_CELL_MAX_CHARS = 20
_CAPTION_MAX_CHARS = 100
# 번호·항목 표지로 시작하는 글(`1.`, `가.`, `1)`, `가)`, `(1)`, `예)`, `(예외)`, `*`, `※`) -- 표 제목·본문 행이 아니라 데이터 행
_LIST_MARKER = re.compile(r"^\s*(?:\d{1,2}\s*[.)]|[가-하]\s*[.)]|\(\d{1,2}\)|\([가-하]\)|예\)|\(예외\)|[*※])")
_NUMERIC_CELL = re.compile(r"^[\d\s.,:/\-~%()]+$")


@dataclass
class LogicalTable:
    columns: list[str]
    rows: list[list[str]]               # 데이터 행(병합 칸은 글자가 채워진 상태)
    row_pages: list[int]
    spill: list[set[int]] = field(default_factory=list)  # 행마다 가로 병합으로 채워진 칸(본문에 한 번만 쓴다)
    caption: str = ""
    degraded: bool = False
    unit: str = ""                      # 표 위 글의 `(단위: 만원)` -- 행 청크마다 싣는다(숫자만 든 행이 무슨 단위인지 알 수 있게)

    @property
    def splittable(self) -> bool:
        """행으로 나눌 수 있는 표: 격자가 있고 데이터 행이 둘 이상."""
        return not self.degraded and len(self.rows) >= 2

    def has_oversized_row(self, chunk_size: int) -> bool:
        """행 하나가 청크 크기를 넘는가 -- 칸 안에 문서 한 편이 든 표(신·구조문 대비표의 현행·개정안 칸)."""
        return not self.degraded and any(sum(len(v) for v in row) > chunk_size for row in self._own_cells())

    def _own_cells(self) -> list[list[str]]:
        """행마다 가로 병합으로 복사된 칸을 뺀 값 -- 길이를 잴 때 병합 칸 글자를 칸 수만큼 세지 않게."""
        return [[v for c, v in enumerate(row) if c not in (self.spill[i] if i < len(self.spill) else set())]
                for i, row in enumerate(self.rows)]


def logical_tables(table: dict) -> list[LogicalTable]:
    """표 자료 하나를 행 청크용 논리 표(들)로. 머리글이 다시 나오면 거기서 나눈다."""
    rows = [list(r) for r in table["rows"]]
    row_pages = list(table.get("row_pages") or [table["pages"][0]] * len(rows))
    if table.get("degraded"):
        return [LogicalTable(columns=[], rows=rows, row_pages=row_pages, degraded=True)]
    merges = table.get("merges", [])
    spill = [set() for _ in rows]
    continued = [set() for _ in rows]  # 행마다 윗줄에서 세로 병합이 이어져 내려온 칸
    for m in merges:
        for r in range(m["row"], min(m["row"] + m["rowspan"], len(rows))):
            spill[r].update(range(m["col"] + 1, m["col"] + m["colspan"]))
            if r > m["row"]:
                continued[r].update(range(m["col"], m["col"] + m["colspan"]))

    captions: list[str] = []
    # 표 맨 위의 제목 행을 걷어낸다. 번호·항목 표지로 시작하는 행(`가. 독성화학물질`, `예) 사린 …`)은 제목이 아니라 데이터다.
    while len(rows) > 2:
        top = _top_value(rows[0]) if any(c.strip() for c in rows[0]) else ""
        if _LIST_MARKER.match(top) or not _caption_like(rows[0]):
            break
        lines = top.splitlines()
        cut = next((i for i, line in enumerate(lines) if i and _LIST_MARKER.match(line)), None)
        if cut is not None:
            # 제목 칸에 첫 구역 줄이 붙어 있다(`특정화학물질(제2조제5호 관련)` + `1. 1종화학물질`): 제목 줄만 제목으로 쓰고 나머지는
            # 데이터로 돌려 둔다 -- 통째로 제목이 되면 첫 구역 이름이 모든 행 청크에 붙었다
            captions.append("\n".join(lines[:cut]).strip())
            rest = "\n".join(lines[cut:]).strip()
            rows = [[rest if c.strip() == top.strip() else c for c in rows[0]], *rows[1:]]
            break
        # 값이 두 개인 제목 행은 둘 다 남긴다 -- 한 값만 남기면 다른 칸 글자(화학물질 CAS 번호)가 통째로 사라졌다
        captions.append(" ".join(dict.fromkeys(c.strip() for c in rows[0] if c.strip())))
        rows, row_pages, spill, continued = rows[1:], row_pages[1:], spill[1:], continued[1:]
    caption = " ".join(captions)
    unit = _unit(caption)

    header_count = _header_count(rows, table.get("header_rows", 0) if not captions else 0,
                                 continued=continued if merges else None)
    columns = list(table.get("column_names") or _column_names(rows[:header_count], len(rows[0]) if rows else 0))
    return [LogicalTable(columns, rows[header_count:], row_pages[header_count:], spill[header_count:], caption, unit=unit)]


def _unit(text: str) -> str:
    """표 위 글의 마지막 `단위: …`(`(단위: 만원)`, `[단위 : 원]`, `<단위: 밀리시버트>`)."""
    found = re.findall(r"단\s*위\s*[:：]\s*([^)）\]>〉\n]{1,20}?)\s*[)）\]>〉]?\s*(?:$|\n)", text)
    return " ".join(found[-1].split()) if found else ""


def _caption_like(row: list[str]) -> bool:
    """표 제목 행: 한 값이 칸의 절반 이상을 차지하고(가로 병합) 다른 값은 많아야 하나. 숫자만인 값은 제목이 아니다."""
    cells = [c.strip() for c in row]
    filled = [c for c in cells if c]
    if len(cells) < 3 or not filled:
        return False
    top = max(dict.fromkeys(filled), key=filled.count)  # 동률이면 앞 칸 -- set 순서는 실행마다 바뀐다
    # 제목은 짧다. 도표 글자가 통째로 칸 하나에 든 행(실측 9,800자)을 제목으로 삼으면 모든 행 청크에 복제된다.
    if _NUMERIC_CELL.match(top) or len(top) > _CAPTION_MAX_CHARS:
        return False
    if len(filled) == 1:  # 칸 하나에만 글자가 있는 첫 행(병합을 못 읽은 제목 조각)
        return True
    return filled.count(top) * 2 >= len(cells) and len(set(filled)) <= 2


def _top_value(row: list[str]) -> str:
    filled = [c.strip() for c in row if c.strip()]
    return max(dict.fromkeys(filled), key=filled.count)  # 동률이면 앞 칸 -- set 순서는 실행마다 바뀐다


def _header_count(rows: list[list[str]], detected: int, *, continued: list[set[int]] | None = None) -> int:
    """머리글 행 수. `continued`는 행마다 세로 병합이 윗줄에서 이어진 칸(병합 정보가 없는 표는 None).

    두 줄짜리 표(머리글 + 데이터 한 행)는 첫 줄이 머리글처럼 생기고 둘째 줄은 아닐 때만 머리글로 본다 -- 둘 다 짧은
    값이면 어느 쪽이 머리글인지 알 수 없다.
    """
    if len(rows) == 2 and len(rows[0]) >= 2 and not detected:
        return 1 if _header_like(rows[0]) and not _header_like(rows[1]) else 0
    if len(rows) < 3 or len(rows[0]) < 2:
        return detected
    header = detected
    if not header and _header_like(rows[0]):
        header = 1
    # 두 줄 머리글: 윗줄이 가로 병합된 상위 머리글이라 빈 칸이 있어도(`한국 | | 세계`), 아랫줄이 온전한 머리글이면 둘 다 머리글.
    # 아랫줄은 그룹마다 같은 하위 머리글이 되풀이되므로(`수량 | 금액 | 수량 | 금액`) 서로 달라야 한다는 조건을 뺀다.
    if not header and _header_like(rows[0], allow_blanks=True) and _header_like(rows[1], distinct=False):
        header = 2
    # 세로 병합된 머리글(`구분`/`직위명`) 옆에 하위 머리글(`경력`)이 붙은 줄: 병합으로 채워진 칸이 윗줄과 같고
    # 나머지도 머리글처럼 생겼으면 머리글에 넣는다. 데이터가 최소 두 줄은 남게 한다.
    while 0 < header < len(rows) - 2 and _header_like(rows[header]) and _continues_header(rows, header, continued):
        header += 1
    return header


def _continues_header(rows: list[list[str]], r: int, continued: list[set[int]] | None) -> bool:
    """r행이 윗줄 머리글의 세로 병합을 이어받은 하위 머리글인지.

    값이 한 칸만 같아서는 부족하다 -- 분류값이 반복되는 데이터 행(`반도체 | 장비`, `반도체 | 소재`)도 그렇다. 병합 정보가
    있으면 실제 세로 병합이 윗줄 머리글에서 이어져 내려온 칸이 있어야 하고, 병합 정보가 없는 표(`merges: []`)는 두 칸
    이상이 윗줄과 같아야 한다.
    """
    if continued is not None:
        return bool(continued[r])
    same = sum(a.strip() == b.strip() and a.strip() != "" for a, b in zip(rows[r], rows[r - 1]))
    return same >= 2


def _header_like(row: list[str], *, allow_blanks: bool = False, distinct: bool = True) -> bool:
    """머리글처럼 생긴 행: 칸이 모두(또는 절반 이상) 채워져 있고, 짧고, 숫자만인 칸이 없고, 서로 다르다.

    가로 병합 칸은 같은 글자가 이어서 채워지므로 이어진 같은 값은 한 칸으로 본다(`특례 | 특례 | 등급`).
    """
    cells = [c.strip() for c in row]
    filled = [c for c in cells if c]
    if not filled or (len(filled) < len(cells) and not (allow_blanks and len(filled) * 2 >= len(cells))):
        return False
    if any(len(c) > _HEADER_CELL_MAX_CHARS or _NUMERIC_CELL.match(c) for c in filled):
        return False
    if any(_LIST_MARKER.match(c) for c in filled):  # 구역·항목 줄(`1. 1종화학물질`, `가. 원료물질`)은 머리글이 아니다
        return False
    runs = [c for i, c in enumerate(filled) if i == 0 or c != filled[i - 1]]
    return not distinct or len(set(runs)) == len(runs)


def _column_names(header: list[list[str]], width: int) -> list[str]:
    """열 이름. 머리글이 여러 줄이면(상위 머리글 + 하위 머리글) 위에서부터 잇는다."""
    names = []
    for col in range(width):
        parts = [row[col].strip() for row in header if col < len(row) and row[col].strip()]
        name = " ".join(" ".join(dict.fromkeys(parts)).split())
        names.append(name or f"열{col + 1}")
    return names


def table_fields(table: LogicalTable, table_id: str) -> dict:
    fields = {"table_id": table_id, "columns": table.columns, "row_count": len(table.rows)}
    if table.caption:
        fields["caption"] = table.caption
    if table.unit:
        fields["unit"] = table.unit
    return fields


def _named_lines(pairs: list[tuple[str, str]]) -> list[str]:
    """`열이름: 값` 줄. 이웃한 열이 이름이 같으면(머리글 칸 하나가 하위 단계 열 여럿에 걸친 것: `특례 | 특례 | 특례`) 한 줄로 잇는다
    -- `특례:`가 세 번 되풀이되면 어느 값이 상위 구분인지 안 보인다. 값은 왼쪽(상위)부터 ` > `로 잇는다."""
    merged: list[tuple[str, list[str]]] = []
    for name, value in pairs:
        value = " ".join(value.split())
        if merged and merged[-1][0] == name:
            merged[-1][1].append(value)
        else:
            merged.append((name, [value]))
    return [f"{name}: {' > '.join(values)}" for name, values in merged]


def row_chunks(table: LogicalTable, table_id: str, *, chunk_size: int | None = None,
               policy: ChunkPolicy = DEFAULT_POLICY) -> list[dict]:
    """데이터 행마다 `열이름: 값` 본문 + 행 메타데이터. 값이 하나도 없는 행은 건너뛴다.

    `chunk_size`를 주면 그보다 긴 행은 칸 단위로 나눈다(`_cell_pieces`): 칸 안의 글이 문서 한 편이면(대비표의 현행·개정안
    칸에 조문 수십 개) 행 하나를 청크 하나로 두면 수천~수만 자가 된다.
    """
    base = table_fields(table, table_id)
    # 표 제목은 행 청크 하나만 검색돼도 무슨 표인지 알 수 있게 본문 첫 줄에 둔다.
    prefix = ([f"표: {table.caption}"] if table.caption else []) + ([f"단위: {table.unit}"] if table.unit else [])
    out = []
    for index, values in enumerate(table.rows):
        if table.degraded:  # 격자가 없는 표: 열 이름을 붙일 수 없어 글자 그대로
            lines = [values[0].strip()] if values and values[0].strip() else []
        else:
            spill = table.spill[index] if index < len(table.spill) else set()
            pairs = [(name, value) for c, (name, value) in enumerate(zip(table.columns, values))
                     if value.strip() and c not in spill]
            lines = _named_lines(pairs)
        if not lines:
            continue
        if chunk_size and not table.degraded and len("\n".join(prefix + lines)) > chunk_size:
            out.extend(_cell_pieces(table, index, values, prefix, base, table_id, chunk_size, policy))
            continue
        # 행 칸이 조문으로 시작하면(대비표의 한 행 = 조문 한 쌍) 그 조문 표제를 경로로 -- 칸 조각과 같은 규칙(`_cell_sections`)
        own = [] if table.degraded else [v for c, v in enumerate(values) if c not in spill and v.strip()]
        section = next((sec for sec in (_cell_sections([v.strip()])[0] for v in own) if sec), [])
        out.append({
            **({"section_path": section} if section else {}),
            "text": "\n".join(prefix + lines),
            "page_start": table.row_pages[index],
            "page_end": table.row_pages[index],
            **base,
            "row_id": f"{table_id}#row{index}",
            "row_index": index,
            "values": list(values),
        })
    return out


# 행의 식별자로 볼 짧은 칸(통제번호·조문 번호·구분 등). 긴 칸을 나눈 조각마다 머리 줄로 붙여, 조각 하나만 검색돼도 어느
# 행인지 알게 한다. 이보다 긴 짧은 칸(비고 등)은 조각에 반복하지 않고 따로 한 청크로 둔다.


def _cell_pieces(table: LogicalTable, index: int, values: list[str], prefix: list[str], base: dict, table_id: str,
                 chunk_size: int, policy: ChunkPolicy) -> list[dict]:
    """청크 크기를 넘는 행: 긴 칸은 칸 안의 글을 문서처럼 그 구조(조문 -> 번호 -> 문단)로 나눈다.

    - 행의 식별자 칸(`policy.row_key_max_chars` 이하, 통제번호 `ML1` 등)은 조각마다 머리 줄로 붙는다 -- 따로 두면 `통제번호: ML1`만
      든 몇 글자짜리 청크가 생기고, 조각은 어느 행인지 모른다.
    - 그 밖의 짧은 칸(비고 등)은 한 청크로 모은다.
    조각마다 어느 표의 어느 행·열인지(`row_id`, `column`)와 칸 안 순서(`piece_index`/`piece_count`)를 남긴다. 행 전체 값
    (`values`)은 수만 자가 될 수 있어 조각에는 싣지 않는다.
    - 칸 안의 글이 조문이면 조각이 시작하는 자리의 편·장·절·조 표제를 `section_path`로 남긴다(`_cell_sections`) -- 조문
      중간에서 잘린 조각(`9. 해당 물품등의 최종 목적지가…`)은 본문만 봐서는 어느 조문의 호인지 모른다. 청커가 이 경로를
      `heading_path` 뒤에 붙이므로 같은 조문의 현행 조각과 개정안 조각이 같은 경로를 갖는다.
    """
    from search_engine.chunking.splitter import chunk_markdown

    spill = table.spill[index] if index < len(table.spill) else set()
    cells = [(name, value.strip()) for c, (name, value) in enumerate(zip(table.columns, values))
             if value.strip() and c not in spill]
    long_limit = int(chunk_size * policy.long_cell_ratio)  # 한 칸이 청크 절반을 넘으면 그 칸을 따로 나눈다
    keys = [f"{n}: {' '.join(v.split())}" for n, v in cells if len(v) <= policy.row_key_max_chars]
    others = [f"{n}: {' '.join(v.split())}" for n, v in cells if policy.row_key_max_chars < len(v) <= long_limit]
    row = {"page_start": table.row_pages[index], "page_end": table.row_pages[index], **base,
           "row_id": f"{table_id}#row{index}", "row_index": index}
    out = []
    if others:
        out.append({**row, "text": "\n".join(prefix + keys + others)})
    for name, value in cells:
        if len(value) <= long_limit:
            continue
        head = prefix + keys + [f"{name}:"]
        budget = max(chunk_size - len("\n".join(head)) - 1, long_limit)
        pieces = [piece.text for piece in chunk_markdown(value, budget, 0, min_chunk_chars=policy.min_chunk_chars)]
        for k, (piece, section) in enumerate(zip(pieces, _cell_sections(pieces))):
            extra = {"section_path": section} if section else {}
            out.append({**row, "text": "\n".join(head + [piece]), "column": name,
                        "piece_index": k, "piece_count": len(pieces), **extra})
    return out


# 칸 안 조문 구조의 단계(위에서부터). 조문 체계만 본다 -- 번호 목록(1. 가.)은 조문에 딸린 호·목이다.
_SECTION_TIERS = ("편", "장", "절", "조")
# 옛 법령의 한자 표기(`第21條(戰略物資의 輸出許可 등)`)는 판별할 때만 한글 표기로 읽는다(표제 글자는 원문 그대로 남긴다).
_HANJA_NUMBERING = str.maketrans({"第": "제", "條": "조", "章": "장", "節": "절", "編": "편"})
# 조각 첫머리에서 표제 앞에 올 수 있는 짧은 줄(법령명 `대외무역법`). 이보다 길면 본문 줄로 본다.
_LEAD_LINE_MAX_CHARS = 20
# 조문 번호 뒤 표제 없이 "<현행과 동일>", "<삭 제>"만 있는 줄: "제43조 <현행과 동일>"
_BARE_ARTICLE = re.compile(r"^\s*(제\s*\d+\s*조(?:의\s*\d+)?)\s*(?:<[^>]*>)?\s*$")


def _section_line(line: str) -> tuple[int, str] | None:
    """조문 구조 표제 줄이면 (단계, 표제). 조는 괄호 표제까지만(`제39조의3(상황허가)`), 편·장·절은 줄 전체."""
    from search_engine.chunking import patterns

    tiers = dict(patterns.HEADING_TIERS)
    read = line.translate(_HANJA_NUMBERING)  # 글자 수가 같아 잘라낸 위치를 원문에 그대로 쓸 수 있다
    for depth, tier in enumerate(_SECTION_TIERS):
        pattern = tiers.get(tier)
        if pattern is None or not pattern.match(read):
            continue
        if tier != "조":
            return depth, " ".join(line.split())[:60]
        title = patterns.ARTICLE_TITLE.match(read)
        if title:
            return depth, " ".join(line[title.start(1):title.end(1)].split())
        bare = _BARE_ARTICLE.match(read)
        # 괄호 표제도 "<현행과 동일>"도 없는 "제21조 …"는 본문 속 인용일 수 있어 표제로 보지 않는다
        return (depth, " ".join(line[bare.start(1):bare.end(1)].split())) if bare else None
    return None


def _cell_sections(pieces: list[str]) -> list[list[str]]:
    """조각마다 그 조각이 시작하는 자리에서 열려 있는 편·장·절·조 표제(위에서부터).

    조각이 표제 줄로 시작하면 그 표제가 경로가 된다. 표제 앞의 짧은 줄(법령명 `대외무역법`)은 건너뛰고 본다.
    칸 안에 조문 구조가 없으면 모두 빈 목록.
    """
    stack: list[tuple[int, str]] = []
    out = []
    for piece in pieces:
        lines = [line for line in piece.splitlines() if line.strip()]
        # 조각 첫머리의 표제 줄들(`제4절 …` 다음 `제39조(…)`)은 이 조각이 여는 것이라 경로에 먼저 넣는다
        article = len(_SECTION_TIERS) - 1
        for line in lines:
            found = _section_line(line)
            if found:
                _push(stack, found)
                if found[0] == article:
                    break  # 조문 하나를 열었다 -- 이 조각의 경로는 첫 조문까지(뒤 조문은 아래에서 다음 조각용으로 센다)
            elif len(line.strip()) > _LEAD_LINE_MAX_CHARS or stack and stack[-1][0] == article:
                break  # 본문 줄, 또는 조까지 열린 뒤의 줄 -- 여기부터는 조문 내용
        out.append([title for _, title in stack])
        for line in lines:
            found = _section_line(line)
            if found:
                _push(stack, found)
    return out


def _push(stack: list[tuple[int, str]], found: tuple[int, str]) -> None:
    while stack and stack[-1][0] >= found[0]:
        stack.pop()
    stack.append(found)


# ---- 신·구조문 대비표 (#115) -----------------------------------------------------------------------------------------
# 대비표는 같은 조문의 현행·개정안을 나란히 싣는다. 칸을 글자 수로 자르면(`_cell_pieces`) 조각이 조문 중간에서 시작하고 현행과
# 개정안이 다른 청크로 갈려, 검색 단위("제39조의3 상황허가가 어떻게 바뀌었나")와 맞지 않는다. 열 이름으로 대비표를 알아보고
# 칸을 조문 단위로 잘라 같은 조문의 현행·개정안을 한 청크로 묶는다.
_CURRENT_COLUMN = re.compile(r"현\s*행|개\s*정\s*전")
_REASON_COLUMN = re.compile(r"사\s*유|비\s*고")
_REVISED_COLUMN = re.compile(r"개\s*정")
# 개정안 칸의 "현행과 같음" 표시: 바뀌지 않은 글자 자리를 줄표로 채운다(`① -------- 제21조에 따른 …`). 내용이 아니라 표시라
# 줄표 덩어리를 말줄임 하나로 줄인다(원문의 "같음" 뜻은 남는다). 쪽 번호(`- 1 -`)처럼 줄표가 두 개 이하인 것은 건드리지 않는다.
_SAME_AS_CURRENT = re.compile(r"[-‐－–—](?:\s*[-‐－–—]){2,}")


def comparison_columns(columns: list[str]) -> tuple[int, int, int | None] | None:
    """대비표 열이면 (현행 열, 개정안 열, 사유·비고 열 또는 None). 아니면 None."""
    current = next((i for i, c in enumerate(columns) if _CURRENT_COLUMN.search(c)), None)
    reason = next((i for i, c in enumerate(columns) if _REASON_COLUMN.search(c) and i != current), None)
    revised = next((i for i, c in enumerate(columns)
                    if i not in (current, reason) and _REVISED_COLUMN.search(c)), None)
    if current is None or revised is None:
        return None
    return current, revised, reason


def same_as_current(text: str) -> str:
    """개정안 칸의 줄표("현행과 같음" 자리)를 `…`로."""
    return _SAME_AS_CURRENT.sub("…", text)


def _article_segments(text: str) -> list[tuple[str | None, str]]:
    """칸 글을 조문 단위로 자른다: [(조문 키 또는 None, 글)]. 첫 조문 앞의 줄(법령명·장 제목)은 첫 조문 글에 붙인다."""
    segments: list[list] = []
    lead: list[str] = []
    for line in text.splitlines():
        found = _section_line(line)
        if found and found[0] == len(_SECTION_TIERS) - 1:  # 조
            key = re.sub(r"\s", "", line.translate(_HANJA_NUMBERING))
            key = re.match(r"제\d+조(?:의\d+)?", key).group(0)
            segments.append([key, lead + [line]])
            lead = []
        elif found:  # 편·장·절 줄은 다음 조문을 여는 줄이다(앞 조문 끝에 붙이지 않는다)
            lead.append(line)
        elif segments and not lead:
            segments[-1][1].append(line)
        else:
            lead.append(line)
    if not segments:
        return [(None, text)] if text.strip() else []
    segments[-1][1].extend(lead)  # 마지막 조문 뒤에 남은 줄(뒤따르는 조문 없음)도 잃지 않는다
    return [(key, "\n".join(lines).strip()) for key, lines in segments]


def _align(current: list[tuple[str | None, str]], revised: list[tuple[str | None, str]]) -> list[tuple[str | None, str, str]]:
    """같은 조문끼리 짝짓는다. 순서는 현행 순서, 개정안에만 있는 조문(신설)은 앞 조문 바로 뒤에 둔다."""
    by_revised = {key: text for key, text in revised if key}
    pairs = [[key, text, by_revised.get(key, "") if key else ""] for key, text in current]
    known = {key for key, _ in current if key}
    for position, (key, text) in enumerate(revised):
        if key and key in known:
            continue
        if key is None and any(k is None for k, _, _ in pairs):  # 조문이 없는 칸끼리
            next(p for p in pairs if p[0] is None)[2] = text
            continue
        previous = next((revised[i][0] for i in range(position - 1, -1, -1) if revised[i][0] in known), None)
        at = next((i + 1 for i, p in enumerate(pairs) if previous and p[0] == previous), 0 if previous is None and pairs else len(pairs))
        pairs.insert(at, [key, "", text])
        if key:
            known.add(key)
    return [(key, cur, rev) for key, cur, rev in pairs if cur.strip() or rev.strip()]


def _opens_section(text: str) -> bool:
    """칸 글이 조문·장·절 줄로 시작하는가(비어 있으면 아니다)."""
    first = next((line for line in text.splitlines() if line.strip()), "")
    return _section_line(first) is not None


def _continued_rows(table: LogicalTable, cur_col: int, rev_col: int):
    """대비표 행을 조문 경계로 다시 묶는다: 현행·개정안 칸이 모두 조문 첫 줄로 시작하지 않는 행은 앞 행의 이어짐이다(쪽을 넘어
    이어지는 대비표는 쪽마다 한 행이라 조문이 쪽 경계에서 잘린다). -> (첫 행 번호, 칸 값들, 시작 쪽, 끝 쪽)."""
    merged: list[list] = []
    keys = [i for i in range(len(table.columns)) if i not in (cur_col, rev_col) and not _REASON_COLUMN.search(table.columns[i])]
    # 이어 붙이기는 조문으로 된 대비표에서만(행마다 통제번호·항목이 다른 표는 행이 곧 단위다)
    articles = any(_section_line(line) for row in table.rows for i in (cur_col, rev_col) if i < len(row)
                   for line in (row[i] or "").splitlines())
    keyed_rows = [any(i < len(row) and (row[i] or "").strip() for i in keys) for row in table.rows]
    for index, values in enumerate(table.rows):
        page = table.row_pages[index]
        cells = [v or "" for v in values]
        keyed = keyed_rows[index]
        if merged and articles and not keyed:
            # 열마다 따로: 첫 조문·장 줄 앞의 글은 앞 행 같은 열의 이어짐이다(현행 열은 앞 조문이 이어지고 개정안 열은 새 조문으로
            # 시작하는 쪽도 있다)
            prev = merged[-1]
            for i in (cur_col, rev_col):
                if i >= len(cells):
                    continue
                lines = cells[i].splitlines()
                cut = next((k for k, line in enumerate(lines) if _section_line(line)), len(lines))
                carried = "\n".join(lines[:cut]).strip()
                if carried:
                    prev[1][i] = f"{prev[1][i]}\n{carried}".strip()
                    prev[3] = page
                cells[i] = "\n".join(lines[cut:])
            if not any(cells[i].strip() for i in (cur_col, rev_col) if i < len(cells)):
                for i, value in enumerate(cells):  # 다른 열(사유 등)도 앞 행에 붙인다
                    if i not in (cur_col, rev_col) and value.strip() and i < len(prev[1]):
                        prev[1][i] = f"{prev[1][i]}\n{value}".strip()
                continue
        merged.append([index, cells, page, page])
    return [tuple(m) for m in merged]


def comparison_chunks(table: LogicalTable, table_id: str, *, chunk_size: int,
                      policy: ChunkPolicy = DEFAULT_POLICY) -> list[dict]:
    """대비표 -> 조문 쌍 청크. 청크 글은 `현행 열 이름:` / `개정안 열 이름:` 두 단락(+ 조문 쌍이 하나뿐인 행은 사유). 줄표 표시는
    `…`로 줄인다. 쌍 하나가 청크 크기의 1.5배를 넘으면 현행·개정안을 각각 조각으로 나누되 조문 경로는 유지한다.
    조문 쌍이 여럿인 행의 사유·비고 칸은 조문에 맞출 수 없어 따로 한 청크로 둔다."""
    from search_engine.chunking.splitter import chunk_markdown

    cur_col, rev_col, reason_col = comparison_columns(table.columns)
    cur_name, rev_name = (" ".join(table.columns[i].split()) for i in (cur_col, rev_col))
    base = table_fields(table, table_id)
    prefix = ([f"표: {table.caption}"] if table.caption else []) + ([f"단위: {table.unit}"] if table.unit else [])
    out: list[dict] = []
    carry = ("", "")  # 조문 없는 짧은 쌍(법령명 줄, `<신설>`/`<삭제>` 자리표시)은 다음 조문 쌍 앞에 붙인다
    for index, values, page_start, page_end in _continued_rows(table, cur_col, rev_col):
        cell = lambda i: (values[i] if i is not None and i < len(values) else "").strip()  # noqa: E731
        pairs = _align(_article_segments(cell(cur_col)), _article_segments(same_as_current(cell(rev_col))))
        kept = []
        # 행 식별 칸(통제번호 등)이 있는 행은 짧아도 다음 쌍에 붙이지 않는다 -- 붙이면 그 행의 키가 사라진다
        row_keyed = any(cell(i) for i in range(len(table.columns)) if i not in (cur_col, rev_col, reason_col))
        for key, cur, rev in pairs:
            if key is None and not row_keyed and len(cur) + len(rev) < policy.carry_max_chars:
                carry = (f"{carry[0]}\n{cur}".strip(), f"{carry[1]}\n{rev}".strip())
                continue
            if any(carry):
                cur, rev = f"{carry[0]}\n{cur}".strip(), f"{carry[1]}\n{rev}".strip()
                carry = ("", "")
            kept.append((key, cur, rev))
        pairs = kept
        reason = " ".join(cell(reason_col).split())
        row = {"page_start": page_start, "page_end": page_end, **base,
               "row_id": f"{table_id}#row{index}", "row_index": index}
        if reason and len(pairs) != 1:
            out.append({**row, "text": "\n".join(prefix + [f"{table.columns[reason_col]}: {reason}"]), "column": table.columns[reason_col]})
        # 행 식별 칸(조항·통제기준 등 현행·개정안·사유가 아닌 열)은 쌍마다 머리 줄로 단다
        heads = [f"{' '.join(table.columns[i].split())}: {' '.join(cell(i).split())}"
                 for i in range(len(table.columns)) if i not in (cur_col, rev_col, reason_col) and cell(i)]
        for key, cur, rev in pairs:
            texts = [*prefix, *heads, f"{cur_name}:", cur or "<신설>", "", f"{rev_name}:", rev or "<삭제>"]
            if reason and len(pairs) == 1:
                texts += ["", f"{' '.join(table.columns[reason_col].split())}: {reason}"]
            section = _cell_sections([cur or rev])[0] if key else []
            extra = {"article": key, **({"section_path": section} if section else {})}
            text = "\n".join(texts)
            if len(text) <= chunk_size * policy.pair_oversize_ratio:
                out.append({**row, "text": text, "column": f"{cur_name}+{rev_name}", **extra})
                continue
            for name, side in ((cur_name, cur), (rev_name, rev)):
                if not side.strip():
                    continue
                head = prefix + heads + [f"{name}:"]  # 조각에도 행 식별 칸(통제번호 등)을 -- 없으면 어느 품목인지 모른다
                budget = max(chunk_size - len("\n".join(head)) - 1, policy.long_cell_chars)
                pieces = [p.text for p in chunk_markdown(side, budget, 0, min_chunk_chars=policy.min_chunk_chars)]
                for k, piece in enumerate(pieces):
                    out.append({**row, "text": "\n".join(head + [piece]), "column": name,
                                "piece_index": k, "piece_count": len(pieces), **extra})
            if reason and len(pairs) == 1:  # 조각으로 나눈 쌍에도 사유를 잃지 않는다(짧은 쌍은 위에서 본문 끝에 붙였다)
                reason_name = " ".join(table.columns[reason_col].split())
                out.append({**row, "text": "\n".join(prefix + heads + [f"{reason_name}: {reason}"]),
                            "column": table.columns[reason_col], **extra})
    if any(carry):  # 뒤에 붙일 조문이 없으면 마지막 청크에 덧붙인다(글자를 잃지 않는다)
        tail = "\n".join(t for t in (f"{cur_name}: {carry[0]}" if carry[0] else "",
                                       f"{rev_name}: {carry[1]}" if carry[1] else "") if t)
        if out:
            out[-1] = {**out[-1], "text": f"{out[-1]['text']}\n\n{tail}"}
        else:
            out.append({**base, "page_start": table.row_pages[0] if table.row_pages else 1,
                        "page_end": table.row_pages[-1] if table.row_pages else 1, "text": "\n".join(prefix + [tail])})
    return out
