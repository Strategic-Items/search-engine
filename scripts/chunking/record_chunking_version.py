"""청킹 버전 하나를 기록한다: `docs/evaluation/chunking_versions/v<N>.json`을 쓰고 `docs/evaluation/chunking_versions.md`를 다시 만든다.

청커나 정책을 바꾸고 `CHUNKER_VERSION`(`search_engine/chunking/params.py`)을 올린 뒤, 코퍼스를 만들어 색인·평가하고 이 스크립트로 남긴다.

    .venv/bin/python scripts/chunking/record_chunking_version.py --version 2 --label "표 서식 행 묶기" \\
        --notes "무엇을 왜 바꿨나" \\
        --corpus law=/path/law.jsonl --corpus admin=/path/admin.jsonl \\
        --eval law=result_law.json:port --eval admin=result_admin.json:port \\
        [--parity parity.txt] [--parser-commit def6caf]

- `--corpus 이름=jsonl`: 그 버전이 만든 코퍼스(`build_corpus_from_bundles.py` 출력 등)에서 청크 통계를 센다.
- `--eval 이름=평가.json:팔`: `eval_category_chunking.py --out`의 결과에서 그 팔(arm)의 지표를 가져온다.
- 같은 버전을 다시 기록하면 덮어쓴다. 다른 버전의 기록은 건드리지 않는다.
"""

import argparse
import dataclasses
import json
import statistics
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "docs/evaluation/chunking_versions"
INDEX = ROOT / "docs/evaluation/chunking_versions.md"
EVAL_FIELDS = ("evidence", "doc_hit", "phrase")


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout.strip()


def corpus_stats(path: Path) -> dict:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    lengths = [len(r["body"]) for r in rows]
    table = [r for r in rows if "table" in (r.get("element_types") or [])]
    return {
        "documents": len({r["parent_id"] for r in rows}),
        "chunks": len(rows),
        "chars_mean": round(statistics.mean(lengths), 1),
        "chars_median": statistics.median(lengths),
        "chars_max": max(lengths),
        "under_30_chars": sum(n < 30 for n in lengths),
        "text_over_1200": sum(len(r["body"]) > 1200 for r in rows if "table" not in (r.get("element_types") or [])),
        "table_chunks": len(table),
        "row_chunks": sum(1 for r in rows if r.get("row_id")),
        "text_without_heading_path": sum(1 for r in rows if "table" not in (r.get("element_types") or []) and not r.get("heading_path")),
    }


def eval_metrics(path: Path, arm: str) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    questions = result["questions"]
    per_question = result["arms"][arm]["per_question"]
    out = {"alias": result["arms"][arm]["alias"], "questions": questions,
           "gold_lost": sum(e["gold_lost"] for e in per_question.values()), "cutoffs": {}}
    for label in ("service", "0.95"):
        values = list(per_question.values())
        out["cutoffs"][label] = {
            **{field: sum(e[label][field] for e in values) for field in EVAL_FIELDS},
            # 공식 라벨을 이 청킹의 청크로 옮기지 못했지만(gold_lost) 필수 구절은 반환된 질문 -- 라벨 탓이지 검색 탓이 아니다
            "evidence_label_unmapped_phrase_returned": sum(1 for e in values if e["gold_lost"] and e[label]["phrase"] and not e[label]["evidence"]),
            "avg_returned": round(sum(e[label]["returned"] for e in values) / questions, 2),
        }
    out["service_cutoff"] = result["service_cutoff"]
    return out


def render(records: list[dict]) -> str:
    lines = ["# 청킹 버전 기록", "",
             "청커나 정책을 바꿀 때마다 한 줄씩 남긴다. 각 버전의 JSON은 `chunking_versions/v<N>.json`, 만드는 법은",
             "`scripts/chunking/record_chunking_version.py`. 정답 청크 반환은 서비스 인덱스의 공식 라벨(청크 ID)을 각 청킹의 청크로 옮기고 필수 구절을 담은 청크를 더하는 규칙을 모든 버전에 똑같이 적용해 센 값이고",
             "(`scripts/chunking/eval_category_chunking.py --reference`; 글이 80% 이상 겹치는 같은 문서의 청크를 같은 근거로 본다; 기준 인덱스에도 같은 규칙), **서비스 컷오프**는 기록 시점의 서비스 설정, 0.95는 이전 기준이다.",
             "법령 150문항 중 평가 대상 149문항(정답 근거가 불완전한 053 제외) 기준이고 149는 질문 수다.", "",
             "| 버전 | 날짜 | 요약 | 법령 청크 | 법령 정답 청크 반환 (서비스 / 0.95) |",
             "|---|---|---|---:|---|"]

    def cell(record: dict, name: str) -> tuple[str, str]:
        stats = record.get("corpus", {}).get(name)
        found = record.get("search", {}).get(name)
        chunks = f"{stats['chunks']:,}" if stats else "-"
        if not found:
            return chunks, "-"
        c = found["cutoffs"]
        return chunks, f"{c['service']['evidence']} / {c['0.95']['evidence']} (/{found['questions']})"

    for r in records:
        law = cell(r, "law")
        lines.append(f"| v{r['version']} | {r['date']} | {r['label']} | {law[0]} | {law[1]} |")
    for r in records:
        lines += ["", f"## v{r['version']} — {r['label']} ({r['date']})", "", r.get("notes", "").strip(), ""]
        lines.append(f"- 검색엔진 커밋 `{r['search_engine_commit']}`{' (작업 트리에 미커밋 변경 있음)' if r.get('dirty') else ''}"
                     + (f", 파서 커밋 `{r['parser_commit']}`" if r.get("parser_commit") else ""))
        lines.append("- 정책: " + ", ".join(f"{k}={v}" for k, v in r["policy"].items()))
        if r.get("parity"):
            lines.append(f"- 파서와의 일치: {r['parity']}")
        for name, stats in r.get("corpus", {}).items():
            lines.append(f"- {name} 코퍼스: 문서 {stats['documents']}, 청크 {stats['chunks']:,} (평균 {stats['chars_mean']}자, 중앙 {stats['chars_median']}, "
                         f"최대 {stats['chars_max']}), 30자 미만 {stats['under_30_chars']}, 표 아닌 1,200자 초과 {stats['text_over_1200']}, "
                         f"표 청크 {stats['table_chunks']}(행 청크 {stats['row_chunks']}), 표 아닌 청크 중 제목 경로 없음 {stats['text_without_heading_path']}")
        for name, found in r.get("search", {}).items():
            lines += ["", f"### {name} 검색 ({found['questions']}문항, 서비스 컷오프 {found['service_cutoff']}, 정답 라벨이 청크에서 사라진 질문 {found['gold_lost']})", "",
                      "| 컷오프 | 정답 청크 반환 | 라벨을 못 옮겼지만 필수 구절은 반환 | 정답 문서 적중 | 필수 구절 반환 | 평균 반환 청크 |", "|---|---:|---:|---:|---:|---:|"]
            for label, c in found["cutoffs"].items():
                lines.append(f"| {label} | {c['evidence']} | {c.get('evidence_label_unmapped_phrase_returned', '-')} | {c['doc_hit']} | {c['phrase']} | {c['avg_returned']} |")
            lines.append(f"\n색인 별칭: `{found['alias']}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--corpus", action="append", default=[], help="이름=jsonl")
    parser.add_argument("--eval", action="append", default=[], help="이름=평가.json:팔")
    parser.add_argument("--parity", default="", help="파서와의 일치 결과 한 줄")
    parser.add_argument("--parser-commit", default="")
    parser.add_argument("--policy-json", help="v0처럼 이 저장소 코드가 아닌 정책이면 값을 직접 준다")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from search_engine.chunking.params import CHUNKER_VERSION, ChunkPolicy

    policy = json.loads(args.policy_json) if args.policy_json else dataclasses.asdict(ChunkPolicy())
    if not args.policy_json and args.version != CHUNKER_VERSION:
        print(f"경고: 기록하는 버전 {args.version}과 코드의 CHUNKER_VERSION {CHUNKER_VERSION}이 다르다", file=sys.stderr)
    record = {
        "version": args.version, "label": args.label, "notes": args.notes, "date": date.today().isoformat(),
        "search_engine_commit": git("rev-parse", "--short", "HEAD"), "dirty": bool(git("status", "--porcelain", "--", "search_engine/chunking")),
        "parser_commit": args.parser_commit, "policy": policy, "parity": args.parity,
        "corpus": {n: corpus_stats(Path(p)) for n, p in (s.split("=", 1) for s in args.corpus)},
        "search": {n: eval_metrics(Path(p.rsplit(":", 1)[0]), p.rsplit(":", 1)[1]) for n, p in (s.split("=", 1) for s in args.eval)},
    }
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"v{args.version}.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(DIR.glob("v*.json"), key=lambda p: int(p.stem[1:]))]
    INDEX.write_text(render(records), encoding="utf-8")
    print(f"v{args.version} 기록 -> {DIR / f'v{args.version}.json'}, {INDEX}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
