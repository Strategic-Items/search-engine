"""Opt-in table packing using the actual sparse encoder input, without truncation."""

from dataclasses import dataclass
import json

from search_engine.chunking.postprocess import chunk_title, index_text
from search_engine.embeddings import embedding_text
from search_engine.indexing.law import law_embedding_body, law_embedding_title


@dataclass
class TableTokenBudget:
    tokenizer: object
    document_title: str
    limit: int = 512
    include_heading_path: bool = True

    def __post_init__(self):
        if self.limit < 1:
            raise ValueError("Table token limit must be positive")

    def count(self, chunk: dict) -> int:
        path = chunk.get("heading_path") or []
        source = {"title": chunk_title(self.document_title, path[-1] if path else ""),
                  "body": index_text(chunk["text"]), "heading_path": path}
        title = law_embedding_title(source) if self.include_heading_path else source["title"]
        body = law_embedding_body(source) if self.include_heading_path else source["body"]
        return len(self.tokenizer.encode(embedding_text(title, body), truncation=False))

    @staticmethod
    def cell_line(cell: dict) -> str:
        r, c = cell['r'] + 1, cell['c'] + 1
        rows = str(r) if cell['rs'] == 1 else f"{r}–{r + cell['rs'] - 1}"
        cols = str(c) if cell['cs'] == 1 else f"{c}–{c + cell['cs'] - 1}"
        kind = ' 머리글' if cell.get('header') else ''
        label = f"행{rows} 열{cols}{kind}"
        if 'ref' in cell:
            label += f" (병합 원점: 행{cell['ref'][0] + 1} 열{cell['ref'][1] + 1})"
        if 'text_start' in cell:
            label += f" (문자 {cell['text_start']}:{cell['text_end']})"
        value = json.dumps(cell['text'], ensure_ascii=False) if cell['text'] else '(빈칸)'
        return f"{label}: {value}"

    def grid_table(self, table, table_id, path, context, lead):
        """Serialize source coordinates, without header/caption/type inference."""
        cells = table.get('source_cells')
        if cells is None:
            raise ValueError('Structure-preserving table chunks require source cells')
        height, width = len(table['rows']), max(map(len, table['rows']), default=0)
        prefix = '\n'.join([*lead, *[f"표 {'설명' if key.endswith('before') else '주석'}: {value}"
                                     for key, value in context.items()], f"표 격자: {height}행 × {width}열"]) + '\n'
        base = {'table_id': table_id, 'heading_path': path, **context,
                'table_shape': [height, width], 'table_representation': 'grid-v1', 'row_count': height}
        def make(items):
            return {**base, 'text': prefix + '\n'.join(self.cell_line(c) for c in items),
                    'table_cells': items, 'page_start': min(c['page'] for c in items),
                    'page_end': max(c['page'] for c in items)}
        rows = []
        for r in range(height):
            items = []
            for cell in cells:
                if cell['r'] == r:
                    items.append(dict(cell))
                elif cell['r'] < r < cell['r'] + cell['rs']:
                    items.append({**cell, 'r': r, 'rs': 1, 'ref': [cell['r'], cell['c']]})
            items.sort(key=lambda c: c['c'])
            if not items:
                continue
            whole = make(items)
            if self.count(whole) <= self.limit:
                rows.append(whole)
                continue
            for cell in items:
                one = make([cell])
                if self.count(one) <= self.limit:
                    rows.append(one)
                    continue
                value, offset = cell['text'], 0
                while offset < len(value):
                    low, high = offset, len(value)
                    while low < high:
                        mid = (low + high + 1) // 2
                        part = {**cell, 'text': value[offset:mid], 'text_start': offset, 'text_end': mid}
                        if self.count(make([part])) <= self.limit:
                            low = mid
                        else:
                            high = mid - 1
                    if low == offset:
                        raise ValueError('Table coordinates/context exhaust token budget')
                    part = {**cell, 'text': value[offset:low], 'text_start': offset, 'text_end': low}
                    rows.append(make([part]))
                    offset = low
                if not value:
                    raise ValueError('Empty cell coordinates/context exhaust token budget')
        packed = []
        for row in rows:
            candidate = make(packed[-1]['table_cells'] + row['table_cells']) if packed else None
            if candidate and self.count(candidate) <= self.limit:
                packed[-1] = candidate
            else:
                packed.append(row)
        return [{**c, 'table_input_tokens': self.count(c), 'table_token_limit': self.limit} for c in packed]

    def split(self, chunk: dict) -> list[dict]:
        if self.count(chunk) <= self.limit:
            return [chunk]
        # Keep table context and short row identifiers on every continuation. Split
        # long values by original character offsets, never by decoding token IDs.
        lines = chunk["text"].splitlines(keepends=True)
        prefix = "".join(line for line in lines if line.startswith(("표:", "단위:", "표 설명:", "표 주석:")))
        body = "".join(line for line in lines if not line.startswith(("표:", "단위:", "표 설명:", "표 주석:")))
        identifiers = [line for line in body.splitlines(keepends=True)
                       if ": " in line and len(line.split(": ", 1)[1].strip()) <= 40]
        keyed_prefix = prefix + "".join(identifiers)
        if identifiers and self.count({**chunk, "text": keyed_prefix}) < self.limit // 2:
            prefix = keyed_prefix
            body = "".join(line for line in body.splitlines(keepends=True) if line not in identifiers)
        # The common oversized-cell case keeps its real column name on every piece.
        if "\n" not in body.rstrip("\n") and ": " in body:
            name, body = body.split(": ", 1)
            prefix += name + ": "
        if self.count({**chunk, "text": prefix}) >= self.limit:
            raise ValueError("Table title/context exhausts the token budget; refusing silent truncation")
        pieces = []
        while body:
            low, high = 0, len(body)
            while low < high:
                mid = (low + high + 1) // 2
                if self.count({**chunk, "text": prefix + body[:mid]}) <= self.limit:
                    low = mid
                else:
                    high = mid - 1
            if not low:
                raise ValueError("No table value fits the token budget")
            # Prefer a complete line/word when it does not create a tiny fragment.
            boundary = max(body.rfind("\n", 0, low), body.rfind(" ", 0, low)) + 1
            cut = boundary if boundary > low // 2 else low
            pieces.append({**chunk, "text": prefix + body[:cut]})
            body = body[cut:]
        return [{**p, "token_piece_index": i, "token_piece_count": len(pieces)} for i, p in enumerate(pieces)]

    def pack(self, chunks: list[dict]) -> list[dict]:
        result = []
        for chunk in chunks:
            for piece in self.split(chunk):
                # Only complete ordinary rows are grouped. Article pairs and cell
                # continuations retain their existing boundaries and provenance.
                previous = result[-1] if result else None
                can_join = (previous and "column" not in piece and "token_piece_index" not in piece
                            and "column" not in previous and "token_piece_index" not in previous
                            and previous.get("table_id") == piece.get("table_id")
                            and previous.get("heading_path") == piece.get("heading_path")
                            and previous.get("table_segment_index") == piece.get("table_segment_index"))
                candidate = {**previous, "text": previous["text"] + "\n\n" + piece["text"]} if can_join else None
                if candidate and self.count(candidate) <= self.limit:
                    members = previous.get("table_rows") or [self._row(previous)]
                    candidate["table_rows"] = members + [self._row(piece)]
                    candidate["page_start"] = min(previous["page_start"], piece["page_start"])
                    candidate["page_end"] = max(previous["page_end"], piece["page_end"])
                    for key in ("row_id", "row_index", "values", "table_segment_row_index"):
                        candidate.pop(key, None)
                    result[-1] = candidate
                else:
                    result.append(piece)
        return [{**c, "table_input_tokens": self.count(c), "table_token_limit": self.limit} for c in result]

    @staticmethod
    def _row(chunk):
        return {key: chunk[key] for key in ("row_id", "row_index", "values", "table_segment_row_index") if key in chunk}
