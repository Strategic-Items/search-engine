"""번들(TextBundle)에서 검색엔진 청커로 `docs.jsonl` 모양의 코퍼스를 만든다(원본은 쓰지 않는다).

문서 단위 사실(제목·게시일·문서 속성 등)은 파서의 기존 `docs.jsonl` 행에서 가져오고, 청크 단위(본문·제목·순번·구조)는
`search_engine.chunking`이 번들 마크다운에서 새로 만든다. 만든 파일은 `search-index --dataset law|admin`이 그대로 읽는다.

    .venv/bin/python scripts/chunking/build_corpus_from_bundles.py <카테고리 폴더> --out <출력 jsonl>
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from search_engine.chunking.bundle import read_bundle
from search_engine.chunking.params import ChunkPolicy
from search_engine.chunking.pipeline import chunk_bundle
from search_engine.chunking.postprocess import TITLE_SEPARATOR, section_label

# 청크마다 달라지는 필드 -- 문서 단위 행에서 가져오지 않고 새로 채운다
_CHUNK_FIELDS = {"id", "title", "body", "content_hash", "chunk_index", "chunk_count", "heading_path", "element_types",
                 "page_start", "page_end", "table_id", "caption", "unit", "columns", "row_count", "row_id", "row_index", "values",
                 "column", "piece_index", "piece_count", "article", "images", "table_context_before", "table_context_after",
                 "table_segment_index", "table_segment_count", "table_continued", "table_page_start", "table_page_end",
                 "table_row_offset", "table_segment_row_index"}
_STRUCTURE_KEYS = ("page_start", "page_end", "heading_path", "element_types", "table_id", "caption", "unit", "columns", "row_count",
                   "row_id", "row_index", "values", "column", "piece_index", "piece_count", "article", "table_context_before",
                   "table_context_after", "table_segment_index", "table_segment_count", "table_continued", "table_page_start",
                   "table_page_end", "table_row_offset", "table_segment_row_index")


def document_title(first_row: dict) -> str:
    """기존 행의 제목에서 문서 제목을 되찾는다(청크 제목 = 문서 제목 [— 절 표시])."""
    heading_path = first_row.get("heading_path") or []
    label = section_label(heading_path[-1]) if heading_path else ""
    suffix = f"{TITLE_SEPARATOR}{label}"
    title = first_row["title"]
    return title[: -len(suffix)] if label and title.endswith(suffix) else title


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("category_dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    parents: dict[str, list[dict]] = {}
    for line in (args.category_dir / "docs.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            parents.setdefault(row["parent_id"], []).append(row)
    policy = ChunkPolicy()
    total = 0
    with args.out.open("w", encoding="utf-8") as out:
        for parent_id, rows in parents.items():
            rows.sort(key=lambda r: r["chunk_index"])
            template = {k: v for k, v in rows[0].items() if k not in _CHUNK_FIELDS}
            doc_title = document_title(rows[0])
            chunks = chunk_bundle(read_bundle(args.category_dir / rows[0]["bundle_path"]), policy=policy)
            from search_engine.chunking.postprocess import chunk_title

            for index, chunk in enumerate(chunks):
                title = chunk_title(doc_title, chunk.get("heading", ""), policy)
                row = {"id": f"{parent_id}#{index:04d}", **template, "title": title, "body": chunk["text"],
                       "content_hash": hashlib.sha256(f"{title}\n{chunk['text']}\n".encode()).hexdigest(),
                       "chunk_index": index, "chunk_count": len(chunks),
                       **{k: chunk[k] for k in _STRUCTURE_KEYS if k in chunk}}
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                total += 1
    print(f"{len(parents)}개 문서, {total}개 청크 -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
