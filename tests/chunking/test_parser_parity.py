"""파서 저장소가 만든 `docs.jsonl`과 번들에서 새로 만든 청크를 대조한다(저장소가 옆에 없으면 건너뛴다).

HWP 계열(hwp5/hwpx/hwpml)은 전부 같아야 한다. PDF는 번들에 담기지 않는 정보(칸 안 줄바꿈, 머리글 배경색, 내보내지 않은
그림 자리, 목록 항목 구분) 때문에 일부가 어긋난다 -- 설계 문서 "동작 일치 비교" 참고. 그 수가 늘면 이 테스트가 잡는다.
"""

import json
from pathlib import Path

import pytest

from search_engine.chunking.bundle import read_bundle
from search_engine.chunking.pipeline import chunk_bundle

CORPUS = Path(__file__).resolve().parents[3] / "unstructured-doc-parser_ver2" / "data" / "category_chunks"
KNOWN_PDF_MISMATCHES = 13

pytestmark = pytest.mark.skipif(not CORPUS.exists(), reason="파서 저장소의 category_chunks가 없다")


def documents():
    for docs_dir in sorted(p for p in CORPUS.iterdir() if (p / "docs.jsonl").exists()):
        parents: dict[str, list[dict]] = {}
        for line in (docs_dir / "docs.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                parents.setdefault(row["parent_id"], []).append(row)
        for rows in parents.values():
            rows.sort(key=lambda r: r["chunk_index"])
            yield read_bundle(docs_dir / rows[0]["bundle_path"]), [r["body"] for r in rows]


def test_hwp_documents_are_identical_and_pdf_mismatches_do_not_grow():
    hwp_bad, pdf_bad = [], []
    for bundle, expected in documents():
        if [c["text"] for c in chunk_bundle(bundle)] != expected:
            (pdf_bad if bundle.source_format == "pdf" else hwp_bad).append(bundle.document_id)
    assert hwp_bad == []
    assert len(pdf_bad) <= KNOWN_PDF_MISMATCHES, pdf_bad
