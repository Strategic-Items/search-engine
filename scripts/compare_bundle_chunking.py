"""번들에서 검색엔진이 만든 청크를 파서가 만든 `docs.jsonl`과 대조한다(읽기 전용; 어느 쪽도 쓰지 않는다).

    .venv/bin/python scripts/compare_bundle_chunking.py <docs.jsonl이 있는 폴더들...> [--show 5] [--json out.json]

본문(`body`)이 같은 순서로 글자까지 같은지, 같지 않으면 어디서 갈리는지를 문서별로 센다. 설계:
docs/design/chunking_ownership_move.md.
"""

import argparse
import collections
import json
import sys
from pathlib import Path

from search_engine.chunking.bundle import read_bundle
from search_engine.chunking.pipeline import chunk_bundle


def load_expected(docs_dir: Path) -> dict[str, dict]:
    parents: dict[str, dict] = {}
    with (docs_dir / "docs.jsonl").open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                row = json.loads(line)
                parent = parents.setdefault(row["parent_id"], {"bundle_path": row.get("bundle_path"), "rows": []})
                parent["rows"].append(row)
    for parent in parents.values():
        parent["rows"].sort(key=lambda r: r.get("chunk_index", 0))
    return parents


def first_diff(expected: list[str], got: list[str]) -> dict:
    for i, (a, b) in enumerate(zip(expected, got)):
        if a != b:
            at = next((j for j, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            return {"chunk": i, "at": at, "expected": a[max(0, at - 40):at + 60], "got": b[max(0, at - 40):at + 60]}
    return {"chunk": min(len(expected), len(got)), "note": "접두는 같고 청크 수가 다르다"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("docs_dirs", nargs="+", type=Path)
    parser.add_argument("--show", type=int, default=0, help="어긋난 문서 중 처음 N개의 첫 차이를 출력")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    report = []
    for docs_dir in args.docs_dirs:
        for parent_id, parent in load_expected(docs_dir).items():
            if not parent["bundle_path"]:
                report.append({"parent_id": parent_id, "status": "no_bundle"})
                continue
            bundle = read_bundle(docs_dir / parent["bundle_path"])
            expected = [r["body"] for r in parent["rows"]]
            got = [c["text"] for c in chunk_bundle(bundle)]
            entry = {"parent_id": parent_id, "format": bundle.source_format, "dir": docs_dir.name, "bundle": str(bundle.path),
                     "expected": len(expected), "got": len(got)}
            if expected == got:
                entry["status"] = "same"
            else:
                entry["status"] = "same_count_diff_text" if len(expected) == len(got) else "count_diff"
                entry["diff"] = first_diff(expected, got)
                entry["chunks_equal"] = sum(a == b for a, b in zip(expected, got))
            report.append(entry)

    status = collections.Counter(e["status"] for e in report)
    by_format = collections.Counter((e.get("format"), e["status"]) for e in report)
    total_expected = sum(e.get("expected", 0) for e in report)
    equal = sum(e["expected"] if e["status"] == "same" else e.get("chunks_equal", 0) for e in report if "expected" in e)
    print(f"문서 {len(report)}개: {dict(status)}")
    print(f"문서 단위 일치율 {status['same'] / max(len(report), 1):.1%}; 위치별로 같은 청크 {equal}/{total_expected}")
    for (fmt, st), n in sorted(by_format.items(), key=str):
        print(f"  {fmt}\t{st}\t{n}")
    bad = [e for e in report if e["status"] not in ("same",)]
    for e in bad[: args.show]:
        print(json.dumps(e, ensure_ascii=False, indent=1))
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
