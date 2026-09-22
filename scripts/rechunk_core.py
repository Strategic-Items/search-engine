"""core 코퍼스를 docs와 같은 청킹 규약으로 다시 자른다.

core는 yestrade 크롤링 단계에서 이미 2,400자 고정 슬라이스(겹침 ~180자)로
잘린 채로 들어온다. docs는 `unstructured-doc-parser_ver2`의 구조 기반
청커(800자/100자 겹침)로 자르고 청크마다 절 표시를 제목에 붙인다. 두
코퍼스를 한 인덱스에서 같이 읽는 이상 청크가 같은 단위여야 하므로
(docs/evaluation/stages/stage-26-align-core-chunking.md), core를 docs 쪽에
맞춘다.

원문은 따로 보관돼 있지 않다. 고정 슬라이스는 연속이므로 겹침을 걷어내
되붙이면 원문이 복원된다. 그 위에 docs와 같은 청커를 다시 건다.

청커는 파서 저장소가 소유한다. 이 저장소는 그쪽을 import하지 않는 것이
원칙이지만(export/search_jsonl.py의 "연결 지점은 파일이다"), 규약을 베껴
두 벌로 두면 반드시 갈라진다. 그래서 이 일회성 스크립트만 파서 소스를
경로로 빌려 쓴다 -- `--parser-src`로 위치를 받는다.
"""

import argparse
import collections
import json
import sys
from pathlib import Path

HSK_TYPE = "HSK 연계표"
# 겹침은 ~180자로 관측된다. 짧은 우연 일치를 겹침으로 오인해 글자를 잃지
# 않도록 하한을 둔다.
MIN_OVERLAP = 20
MAX_OVERLAP = 400
# 부모 단위의 사실이라 첫 청크 것을 모든 청크가 물려받는다.
PARENT_FIELDS = ("title", "source_type", "source_url", "source_id", "published_at",
                 "effective_from", "effective_to", "retrieved_at", "version", "source")


def overlap(left: str, right: str) -> int:
    """앞 조각의 꼬리와 뒤 조각의 머리가 겹치는 길이."""
    limit = min(len(left), len(right), MAX_OVERLAP)
    for size in range(limit, MIN_OVERLAP - 1, -1):
        if left[-size:] == right[:size]:
            return size
    return 0


def stitch(chunks: list[dict]) -> tuple[str, list[tuple[int, int, str]]]:
    """고정 슬라이스를 원문으로 되붙이고, 조문번호(`code`)가 걸린 구간을 남긴다.

    `code`는 청크마다 달릴 수 있는데(부모 55건) 다시 자르면 경계가 달라지므로,
    새 청크가 어느 구간에 놓이는지로 물려받게 하려고 구간을 들고 다닌다.
    """
    text = chunks[0].get("body") or ""
    spans = [(0, len(text), chunks[0].get("code") or "")]
    for chunk in chunks[1:]:
        body = chunk.get("body") or ""
        start = len(text)
        text += body[overlap(text, body):]
        spans.append((start, len(text), chunk.get("code") or ""))
    return text, spans


def code_for(start: int, end: int, spans: list[tuple[int, int, str]]) -> str:
    """새 청크가 가장 많이 걸쳐 있는 원본 구간의 조문번호."""
    best, best_overlap = "", 0
    for span_start, span_end, code in spans:
        shared = min(end, span_end) - max(start, span_start)
        if code and shared > best_overlap:
            best, best_overlap = code, shared
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="corpus_project_v1.jsonl")
    parser.add_argument("out", type=Path, help="재청킹한 코퍼스를 쓸 경로")
    parser.add_argument("--parser-src", type=Path, required=True,
                        help="unstructured-doc-parser_ver2/src")
    parser.add_argument("--chunk-size", type=int, default=800)
    parser.add_argument("--chunk-overlap", type=int, default=100)
    parser.add_argument("--min-chunk-chars", type=int, default=30)
    args = parser.parse_args()

    sys.path.insert(0, str(args.parser_src))
    from docparser.chunking.chunker import chunk_markdown
    from docparser.export.search_jsonl import _section_label, merge_table_scaffolds

    rows = [json.loads(line) for line in args.source.open(encoding="utf-8") if line.strip()]
    parents: dict[str, list[dict]] = collections.defaultdict(list)
    hsk: list[dict] = []
    for row in rows:
        if row.get("source_type") == HSK_TYPE:
            hsk.append(row)
            continue
        parents[row.get("parent_id") or row["id"]].append(row)

    stats = {"parents": len(parents), "chunks_in": sum(len(v) for v in parents.values()),
             "chunks_out": 0, "titled": 0, "hsk": len(hsk)}
    out_rows: list[dict] = []
    for parent_id, chunks in parents.items():
        chunks.sort(key=lambda row: row.get("chunk_index") or 0)
        text, spans = stitch(chunks)
        pieces = merge_table_scaffolds(chunk_markdown(
            text, chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap,
            min_chunk_chars=args.min_chunk_chars))
        head = chunks[0]
        inherited = {key: head[key] for key in PARENT_FIELDS if key in head}
        doc_title = head.get("title") or ""
        cursor = 0
        for order, piece in enumerate(pieces):
            # 원문에서의 자리를 따라가야 조문번호를 물려받을 수 있다. 청커가
            # 앞뒤 공백을 떼므로 앞머리로 찾고, 못 찾으면 커서를 그대로 쓴다.
            found = text.find(piece.text[:60], cursor)
            start = found if found >= 0 else cursor
            cursor = start + len(piece.text)
            heading = _section_label(piece.metadata.get("heading", ""))
            title = f"{doc_title} — {heading}" if heading else doc_title
            stats["titled"] += bool(heading)
            row = {**inherited, "id": f"{parent_id}#{order:04d}", "parent_id": parent_id,
                   "title": title, "body": piece.text,
                   "code": code_for(start, cursor, spans),
                   "chunk_index": order, "chunk_count": len(pieces)}
            out_rows.append(row)
        stats["chunks_out"] += len(pieces)

    # HSK는 부모마다 한 청크뿐이라 다시 자를 것이 없다. 번호 기점만 맞춘다.
    for row in hsk:
        out_rows.append({**row, "chunk_index": 0, "chunk_count": 1})

    with args.out.open("w", encoding="utf-8") as file:
        for row in out_rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
