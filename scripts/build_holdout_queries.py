"""질의 초안(spec)에서 홀드아웃 질의셋을 만든다. 검색엔진은 부르지 않는다.

질의 작성자는 무작위로 뽑힌 문서의 지정 청크만 읽고 질의와 요구사항을 쓴다. 요구사항마다
**핵심 문구**를 적어 두면, 이 스크립트가 코퍼스 전체에서 그 문구를 모두 담은 청크를 찾아
`evidence_groups`와 `gold_groups`를 채운다. 사본(개정판마다 같은 조문, FAQ의 html과 PDF)을
사람이 손으로 찾으면 반드시 빠뜨리고, 빠진 사본이 1위를 하면 정답을 오답으로 채점한다.

매칭은 한글·영숫자만 남기고 비교한다(띄어쓰기, 줄바꿈, 괄호, 기호 무시). PDF 두 단 편집이
섞인 청크도 문구가 연속으로 남아 있으면 잡힌다.

- 정답 문서: 지정 부모 + **모든 요구사항**을 만족하는 다른 부모. `source_specific`이면
  지정 부모만 정답이다(예: "2011년 9월 과정"을 묻는데 다른 해 공지가 같은 문장을 가진 경우).
- 근거 청크: 요구사항마다, 정답 문서 안에서 그 요구사항의 문구를 모두 담은 청크.
- docs 코퍼스(고정)에서 같은 문구를 찾으면 `docs_equivalent_*`에 따로 남긴다. 홀드아웃만
  색인한 조건에서는 정답이 될 수 없지만 docs를 함께 읽는 조건에서는 정답이다.

    python scripts/build_holdout_queries.py data/generated/holdout-v1/queries_spec.json \\
        --corpus data/generated/holdout-v1/core.jsonl \\
        --docs data/generated/docs-v2/review-corpus/docs.jsonl \\
        --out data/queries_holdout_v1.jsonl
"""

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

_KEEP = re.compile(r"[^0-9A-Za-z가-힣]")


def norm(text: str) -> str:
    return _KEEP.sub("", text).lower()


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def matches(chunks: list[dict], phrases: list[str]) -> list[dict]:
    wanted = [norm(p) for p in phrases]
    if not all(wanted):
        raise ValueError(f"문구가 정규화 후 비었다: {phrases}")
    return [c for c in chunks if all(w in c["_norm"] for w in wanted)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--docs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--negatives-out", type=Path)
    args = parser.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    corpus, docs = load(args.corpus), load(args.docs)
    for chunk in corpus + docs:
        chunk["_norm"] = norm(chunk["body"])
    by_id = {c["id"]: c for c in corpus}

    rows, problems = [], []
    for q in spec["queries"]:
        parent = q["parent_id"]
        per_req = [matches(corpus, r["phrases"]) for r in q["requirements"]]
        # 지정 부모 안에서 요구사항이 안 잡히면 문구를 잘못 적은 것이다.
        for req, found in zip(q["requirements"], per_req):
            if not any(c["parent_id"] == parent for c in found):
                problems.append(f"{q['qid']}: 지정 문서에서 '{req['label']}' 문구가 안 잡힘")
        parents_all = set.intersection(*[{c["parent_id"] for c in f} for f in per_req])
        gold = [parent] if q.get("source_specific") else sorted(parents_all | {parent})
        gold = [parent] + [p for p in gold if p != parent]
        evidence_groups, requirements = [], []
        for req, found in zip(q["requirements"], per_req):
            ids = sorted(c["id"] for c in found if c["parent_id"] in gold)
            evidence_groups.append(ids)
            requirements.append({"label": req["label"], "phrases": req["phrases"],
                                 "acceptable_chunk_ids": ids})
        docs_per_req = [matches(docs, r["phrases"]) for r in q["requirements"]]
        docs_parents = sorted(set.intersection(*[{c["parent_id"] for c in f} for f in docs_per_req]))
        docs_chunks = [sorted(c["id"] for c in f if c["parent_id"] in docs_parents)
                       for f in docs_per_req]
        rows.append({
            "qid": q["qid"], "category": q["category"], "query": q["query"],
            "reference_answer": q["reference_answer"],
            "gold": gold, "gold_groups": [gold], "gold_unit": "parent_id",
            "evidence_groups": evidence_groups, "evidence_requirements": requirements,
            "sampled_parent": parent, "sampled_chunks": q.get("sampled_chunks", []),
            "source_specific": bool(q.get("source_specific")),
            "docs_equivalent_parents": docs_parents,
            "docs_equivalent_chunks": docs_chunks if docs_parents else [],
            "review_status": "assistant_source_reviewed", "human_review": "pending",
            "answerable": True,
        })

    for problem in problems:
        print("문제:", problem)
    if problems:
        raise SystemExit(f"{len(problems)}건 -- 질의셋을 쓰지 않았다")

    with args.out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    if args.negatives_out and spec.get("negatives"):
        with args.negatives_out.open("w", encoding="utf-8") as handle:
            for neg in spec["negatives"]:
                handle.write(json.dumps({**neg, "gold": [], "gold_unit": "parent_id",
                                         "answerable": False,
                                         "review_status": "assistant_source_reviewed",
                                         "human_review": "pending"}, ensure_ascii=False) + "\n")

    print(f"{len(rows)}문항 -> {args.out}")
    for row in rows:
        sizes = [len(g) for g in row["evidence_groups"]]
        extra = f" docs {len(row['docs_equivalent_parents'])}" if row["docs_equivalent_parents"] else ""
        print(f"  {row['qid']} {row['category']:<20} 정답 {len(row['gold']):>3}  근거 {sizes}{extra}")
    digest = hashlib.sha256(args.out.read_bytes()).hexdigest()
    print("sha256", digest)


if __name__ == "__main__":
    main()
