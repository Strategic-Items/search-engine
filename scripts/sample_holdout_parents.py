"""홀드아웃 질의를 쓸 부모 문서를 무작위로 고른다.

질의 작성자가 문서를 직접 고르면 답하기 쉬운 문서, 제목이 또렷한 문서로 쏠린다.
그러면 새 질의셋이 튜닝 세트보다 쉬워져 과적합이 가려진다. 그래서 출처별로 층을
나눠 고정 시드로 뽑고, 작성자는 뽑힌 문서에만 질의를 쓴다.

본문이 너무 짧아 질문거리가 없는 문서(`MIN_CHARS` 미만)만 후보에서 뺀다. 이 기준은
문서를 읽기 전에 정한 것이다.

    python scripts/sample_holdout_parents.py data/generated/holdout-v1/core.jsonl \\
        --out data/generated/holdout-v1/sampled_parents.json
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

SEED = 20260923
MIN_CHARS = 300

# 층 -> 뽑을 부모 수. v2 질의 135문항이 52부모에 걸쳐 있었던 밀도(부모당 약 2.6문항)보다
# 넓게 퍼뜨려, 소수 문서의 성질이 결과를 좌우하지 않게 한다.
STRATA = {
    "FAQ": 10,
    "공지사항": 8,
    "공지사항 첨부": 6,
    "민원서식 첨부": 4,
    "알기쉬운 전략물자": 7,
    "동향자료": 3,
    "동향자료 첨부": 4,
    "국내외 소식": 5,
    "국내외 소식 첨부": 2,
    "알기쉬운 전략물자 첨부": 3,
    "기타 게시판": 5,   # 홍보자료·전문가 칼럼·CP공지사항·대북제재 (본문·첨부)
    "법령": 5,          # 법령 본문 5건 전부
    "법령 별표": 5,
    "안내": 4,
}
OTHER_BOARDS = ("홍보자료", "전문가 칼럼", "CP공지사항", "대북제재 판정자료 도구")


def stratum(source_type: str) -> str:
    base = source_type.removesuffix(" 첨부")
    if base in OTHER_BOARDS:
        return "기타 게시판"
    if source_type == "FAQ 첨부":
        return "FAQ"
    return source_type


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    parents: dict[str, dict] = {}
    for line in args.corpus.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        parent = parents.setdefault(row["parent_id"], {
            "parent_id": row["parent_id"], "title": row["title"].split(" — ")[0],
            "source_type": row["source_type"], "chars": 0, "chunks": 0})
        parent["chars"] += len(row["body"])
        parent["chunks"] += 1

    pools: dict[str, list[dict]] = defaultdict(list)
    for parent in sorted(parents.values(), key=lambda p: p["parent_id"]):
        if parent["chars"] >= MIN_CHARS:
            pools[stratum(parent["source_type"])].append(parent)

    rng = random.Random(SEED)
    picked = {}
    for name, count in STRATA.items():
        pool = pools.get(name, [])
        picked[name] = rng.sample(pool, min(count, len(pool)))
    unassigned = sorted(set(pools) - set(STRATA))

    args.out.write_text(json.dumps({
        "seed": SEED, "min_chars": MIN_CHARS, "corpus": str(args.corpus),
        "pool_sizes": {name: len(pool) for name, pool in sorted(pools.items())},
        "unassigned_strata": unassigned, "picked": picked,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, items in picked.items():
        print(f"{name}: {len(items)} / {len(pools.get(name, []))}")
    if unassigned:
        print("층이 정해지지 않은 출처:", unassigned)


if __name__ == "__main__":
    main()
