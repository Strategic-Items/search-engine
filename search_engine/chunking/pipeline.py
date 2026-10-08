"""번들 하나 -> 색인용 청크 목록. 파서의 `convert._element_chunks` + `chunks_to_documents`의 청킹 부분과 같은 순서다:
원소 복원 -> 표 자료 복원 -> `chunk_elements` -> 본문 정리 -> 내용 없는 표 조각 흡수.
"""

from __future__ import annotations

from search_engine.chunking.bundle import Bundle
from search_engine.chunking.elements import markdown_to_elements
from search_engine.chunking.params import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, DEFAULT_MIN_CHUNK_CHARS
from search_engine.chunking.postprocess import index_text, merge_table_scaffolds
from search_engine.chunking.structured import chunk_elements
from search_engine.chunking.tables import element_tables

_TABLE_KEYS = ("table_id", "caption", "unit", "columns", "row_count", "row_id", "row_index", "values",
               "column", "piece_index", "piece_count", "article", "image_ids")


def chunk_bundle(bundle: Bundle, *, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
                 min_chunk_chars: int = DEFAULT_MIN_CHUNK_CHARS) -> list[dict]:
    parsed = markdown_to_elements(bundle.markdown)
    tables = element_tables(parsed.elements, hard_breaks=bundle.source_format != "pdf")
    chunks: list[dict] = []
    for raw in chunk_elements(parsed.elements, document_id=bundle.document_id, chunk_size=chunk_size,
                              chunk_overlap=chunk_overlap, tables=tables, min_chunk_chars=min_chunk_chars):
        text = index_text(raw["text"])
        if not text:
            continue
        titles = list(raw.get("heading_path") or [])
        chunks.append({
            "text": text,
            "heading": titles[-1] if titles else "",
            "heading_path": titles,
            **({"page_start": raw["page_start"], "page_end": raw["page_end"]} if parsed.has_pages else {}),
            "element_types": raw["element_types"],
            **{key: raw[key] for key in _TABLE_KEYS if key in raw},
        })
    return merge_table_scaffolds(chunks)
