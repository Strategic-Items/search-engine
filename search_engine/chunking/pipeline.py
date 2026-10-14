"""번들 하나 -> 색인용 청크 목록. 파서의 `convert._element_chunks` + `chunks_to_documents`의 청킹 부분과 같은 순서다:
원소 복원 -> 표 자료 복원 -> `chunk_elements` -> 본문 정리 -> 내용 없는 표 조각 흡수.
"""

from __future__ import annotations

from search_engine.chunking.bundle import Bundle
from search_engine.chunking.elements import markdown_to_elements
from search_engine.chunking.params import DEFAULT_POLICY, ChunkPolicy
from search_engine.chunking.postprocess import index_text, merge_table_scaffolds
from search_engine.chunking.structured import chunk_elements
from search_engine.chunking.tables import element_tables

_TABLE_KEYS = ("table_id", "caption", "unit", "columns", "row_count", "row_id", "row_index", "values",
               "table_segment_index", "table_segment_count", "table_continued", "table_page_start",
               "table_page_end", "table_row_offset", "table_segment_row_index",
               "table_context_before", "table_context_after",
               "table_cells", "table_shape", "table_representation", "table_rows", "table_input_tokens", "table_token_limit", "token_piece_index", "token_piece_count",
               "column", "piece_index", "piece_count", "article", "image_ids",
               "llm_chunked", "table_title", "summary")


def chunk_bundle(bundle: Bundle, *, policy: ChunkPolicy | None = None, table_token_budget=None) -> list[dict]:
    if policy is None:
        try:
            from search_engine.config import get_settings
            settings = get_settings()
            policy = ChunkPolicy(
                use_llm_tables=settings.chunking_use_llm_tables,
                llm_table_endpoint=settings.chunking_llm_endpoint,
                llm_table_model=settings.chunking_llm_model,
            )
        except Exception:
            policy = DEFAULT_POLICY
    parsed = markdown_to_elements(bundle.markdown)
    tables = element_tables(parsed.elements, hard_breaks=bundle.source_format != "pdf")
    chunks: list[dict] = []
    for raw in chunk_elements(parsed.elements, document_id=bundle.document_id, tables=tables, policy=policy, table_token_budget=table_token_budget):
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
