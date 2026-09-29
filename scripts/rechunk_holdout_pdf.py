"""holdout-v1 core의 PDF 부모만 지정한 파서 소스로 다시 파싱·청킹한다.

holdout-v1 코퍼스는 `build_holdout_corpus.py`(holdout 복사본 저장소)가 만들었다. 이 스크립트는 그
빌더의 `units_from_yestrade`/`parse_unit`을 그대로 불러, **파서 소스(`--parser-src`)만 바꿔서**
기존 PDF 부모(568개)를 다시 만든다. 다른 부모(HTML·HWP·법령)는 건드리지 않는다.

- 파서 소스가 holdout 복사본의 `src`이면 기존 코퍼스를 그대로 재현해야 한다(대조군).
- 파서 소스가 `unstructured-doc-parser_ver2/src`이면 개선된 파서의 결과다.

원본 저장소에는 아무것도 쓰지 않는다. 산출물과 작업 파일은 `--out`에만 둔다. 파서 venv의 파이썬으로
돌린다(bs4·pymupdf 등이 거기에 있다):

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<pymupdf 경로> <parser-venv>/bin/python scripts/rechunk_holdout_pdf.py \\
        --parser-src <ver2>/src --out data/generated/holdout-pdf-rechunk-v1/new
"""

import argparse
import json
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def convert_unit(unit: dict) -> tuple[dict, list | None, str | None]:
    """파서 서버와 같은 경로(`docparser.convert.convert`, PDF는 pdfstruct)로 파일 하나를 청크로 바꾼다."""
    from docparser.convert import convert
    try:
        return unit, convert(Path(unit["path"]), document_id=unit["parent_id"]).chunks, None
    except Exception as exc:  # noqa: BLE001 - 한 파일의 실패로 전체를 잃지 않는다
        return unit, None, f"{type(exc).__name__}: {exc}"[:500]


def legacy_unit(unit: dict, cache: str) -> tuple[dict, list | None, str | None]:
    """빌더가 쓰던 옛 경로: `parse_to_markdown` -> `chunk_markdown`."""
    import build_holdout_corpus as builder
    from docparser.chunking.chunker import chunk_markdown
    unit, markdown, error = builder.parse_unit(unit, cache)
    return unit, (chunk_markdown(markdown) if not error else None), error


HOLDOUT_REPO = Path("/Users/jeongbin/git/unstructured-doc-parser_ver2-holdout")
CORE = Path("data/generated/holdout-v1/core.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--parser-src", type=Path, required=True)
    parser.add_argument("--holdout-repo", type=Path, default=HOLDOUT_REPO)
    parser.add_argument("--core", type=Path, default=CORE)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pipeline", choices=["legacy", "pdfstruct"], default="pdfstruct",
                        help="legacy = 빌더가 쓰던 parse_to_markdown+chunk_markdown, pdfstruct = 파서 서버의 convert()")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    args = parser.parse_args()

    core = args.core.resolve()
    out = args.out.resolve()
    sys.path.insert(0, str(args.parser_src.resolve()))
    sys.path.insert(0, str(args.holdout_repo / "scripts"))
    os.chdir(args.holdout_repo)  # 빌더가 쓰는 상대 경로(files/, data/raw/)가 여기 기준이다
    import docparser
    import build_holdout_corpus as builder
    from docparser.export.search_jsonl import chunks_to_documents
    from docparser.parsers import detect_format

    old = [json.loads(line) for line in core.read_text(encoding="utf-8").splitlines()]
    pdf_parents = {r["parent_id"] for r in old if (r.get("source_path") or "").lower().endswith(".pdf")}

    work = out / "_work"
    cache = work / "markdown"
    cache.mkdir(parents=True, exist_ok=True)
    units, _ = builder.units_from_yestrade(Path("data/raw/yestrade").resolve(), work)
    units = [u for u in units if u["parent_id"] in pdf_parents]
    missing = pdf_parents - {u["parent_id"] for u in units}
    print(f"parser {docparser.__file__}\nPDF 부모 {len(pdf_parents)}개, 작업 단위 {len(units)}개, 원본 못 찾음 {len(missing)}개",
          flush=True)

    documents, failed = [], []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(convert_unit, unit) if args.pipeline == "pdfstruct"
                   else pool.submit(legacy_unit, unit, str(cache)) for unit in units]
        for done, future in enumerate(as_completed(futures), 1):
            unit, chunks, error = future.result()
            if done % 50 == 0:
                print(f"  파싱 {done}/{len(units)}", flush=True)
            if not chunks:
                failed.append({"parent_id": unit["parent_id"], "source_path": unit["source_path"],
                               "reason": error or "청크 없음"})
                continue
            meta = {"parent_id": unit["parent_id"], "title": unit["title"] or unit["parent_id"],
                    "published_at": unit.get("published_at"), "source_type": unit["source_type"],
                    "source_path": unit["source_path"],
                    "source_format": detect_format(Path(unit["path"]))}
            for document in chunks_to_documents(chunks, meta):
                document["source_url"] = unit["source_url"]
                document["source_key"] = unit["source_key"]
                documents.append(document)

    documents.sort(key=lambda d: (d["parent_id"], d["chunk_index"]))
    with (out / "pdf_chunks.jsonl").open("w", encoding="utf-8") as handle:
        for document in documents:
            handle.write(json.dumps({k: v for k, v in document.items() if v is not None},
                                    ensure_ascii=False) + "\n")
    summary = {"parser": docparser.__file__, "pipeline": args.pipeline, "pdf_parents_expected": len(pdf_parents),
               "pdf_parents_built": len({d["parent_id"] for d in documents}),
               "chunks": len(documents), "missing_source": sorted(missing), "failed": failed,
               "reasons": dict(Counter(f["reason"][:60] for f in failed))}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("missing_source", "failed")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
