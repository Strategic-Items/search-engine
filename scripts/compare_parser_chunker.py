"""이식한 청커(`search_engine/chunking`)를 파서의 청커와 대조한다(읽기 전용; 둘 다 파일을 쓰지 않는다).

파서가 원본 파일에서 만든 *원래 원소·표 자료*와 번들의 `text.markdown`에서 되살린 것을 각각 이식한 청커에 넣고, 파서 자신이
낸 청크와 글자 단위로 비교한다.

    PYTHONPATH=<파서>/src <PDF 파싱이 되는 파이썬> scripts/compare_parser_chunker.py \\
        --parser-root ../unstructured-doc-parser_ver2 [--only pdf]

- `port_on_elements`: 이식이 정확한가. 아니면 이식 버그다.
- `port_on_markdown`: 번들 마크다운만으로 같은 청크가 나오는가. 아니면 번들에 안 담긴 정보 탓이다.

파서 쪽 PDF 파싱에 PyMuPDF가 필요하다(AGPL: 개발 중 비교용으로만 쓰고 이 저장소 의존성에 넣지 않는다). 설계:
docs/design/chunking_ownership_move.md.
"""

import argparse
import collections
import copy
import sys
from pathlib import Path

from search_engine.chunking.bundle import iter_bundles
from search_engine.chunking.pipeline import chunk_bundle
from search_engine.chunking.postprocess import index_text, merge_table_scaffolds
from search_engine.chunking.structured import chunk_elements


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parser-root", type=Path, required=True, help="unstructured-doc-parser_ver2 저장소")
    parser.add_argument("--only", help="source_format 하나만(pdf, hwp5, hwpx, hwpml)")
    parser.add_argument("--show", type=int, default=5, help="어긋난 문서 이름을 몇 개 출력할지")
    args = parser.parse_args()
    sys.path.insert(0, str(args.parser_root / "src"))

    from docparser.convert import convert
    from docparser.export.search_jsonl import merge_table_scaffolds as parser_merge
    from docparser.parsers.pua_symbols import normalize_pua_symbols

    result = collections.Counter()
    bad: dict[str, list[str]] = collections.defaultdict(list)
    for bundle in iter_bundles(args.parser_root / "data" / "category_chunks"):
        if args.only and bundle.source_format != args.only:
            continue
        converted = convert(args.parser_root / "corpus_rules" / bundle.source_path, document_id=bundle.document_id)
        expected = [c.text for c in parser_merge(converted.chunks)]
        elements = converted.extra["markdown_elements"]
        tables = converted.extra.get("tables")
        if tables is None:
            from docparser.pdfstruct.normalize import element_tables
            tables = element_tables(converted.extra["parsed"].tree)
        chunks = []
        for raw in chunk_elements(copy.deepcopy(elements), document_id=bundle.document_id, tables=copy.deepcopy(tables)):
            text = index_text(normalize_pua_symbols(raw["text"]))
            if text:
                chunks.append({"text": text, "element_types": raw["element_types"]})
        for name, got in (("port_on_elements", [c["text"] for c in merge_table_scaffolds(chunks)]),
                          ("port_on_markdown", [c["text"] for c in chunk_bundle(bundle)])):
            same = got == expected
            result[(bundle.source_format, name, same)] += 1
            if not same:
                bad[name].append(bundle.document_id)
    for key, count in sorted(result.items(), key=str):
        print(*key, count, sep="\t")
    for name, ids in bad.items():
        print(f"{name} 어긋남 {len(ids)}개: {ids[: args.show]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
