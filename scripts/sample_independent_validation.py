"""Freeze source parents for a new evaluation set before writing questions or searching.

The sample uses only source metadata and body length. Parents used to write the
previous holdout, previously labelled as gold, or inspected in the stage-28
top-five audit are excluded before sampling. No retrieval result is loaded.
"""

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

SEED = 20260925
MIN_PARENT_CHARS = 300
MIN_TARGET_CHARS = 180
MAX_TARGET_CHARS = 5000
STRATA = {
    "FAQ": 5,
    "공지사항": 5,
    "공지사항 첨부": 5,
    "알기쉬운 전략물자": 4,
    "알기쉬운 전략물자 첨부": 2,
    "동향자료": 2,
    "동향자료 첨부": 2,
    # The five standalone law parents were all used in the first holdout.
    # Preserve this stratum's two slots in unseen annex parents.
    "법령 별표": 5,
    "안내": 2,
    "국내외 소식": 2,
    "기타 게시판": 2,
}
OTHER_BOARDS = ("홍보자료", "전문가 칼럼", "CP공지사항", "대북제재 판정자료 도구")


def stratum(source_type: str) -> str:
    if source_type.removesuffix(" 첨부") in OTHER_BOARDS:
        return "기타 게시판"
    if source_type == "FAQ 첨부":
        return "FAQ"
    return source_type


def prior_parents(root: Path) -> set[str]:
    previous = root / "data/generated/holdout-v1"
    sampled = json.loads((previous / "sampled_parents.json").read_text())
    excluded = {row["parent_id"] for rows in sampled["picked"].values() for row in rows}
    for path in (root / "data/queries_holdout_v1_adjudicated.jsonl",
                 root / "data/queries_docs_v2.jsonl"):
        for line in path.open():
            if line.strip():
                excluded.update(json.loads(line)["gold"])
    audited = json.loads((previous / "title1_dfs_top5_audit.json").read_text())
    excluded.update(row["parent_id"] for row in audited["judgments"])
    return excluded


def sample(root: Path, corpus: Path) -> dict:
    excluded = prior_parents(root)
    parents: dict[str, dict] = {}
    with corpus.open(encoding="utf-8") as file:
        for line in file:
            row = json.loads(line)
            parent_id = row["parent_id"]
            if parent_id in excluded:
                continue
            parent = parents.setdefault(parent_id, {
                "parent_id": parent_id,
                "source_type": row["source_type"],
                "source_path": row["source_path"],
                "title": row["title"].split(" — ")[0],
                "chars": 0,
                "target_chunks": [],
            })
            body_chars = len(row["body"])
            parent["chars"] += body_chars
            if MIN_TARGET_CHARS <= body_chars <= MAX_TARGET_CHARS:
                parent["target_chunks"].append(row["id"])

    pools: dict[str, list[dict]] = defaultdict(list)
    for parent in parents.values():
        if parent["chars"] >= MIN_PARENT_CHARS and parent["target_chunks"]:
            pools[stratum(parent["source_type"])].append(parent)

    rng = random.Random(SEED)
    picked = []
    for name, count in STRATA.items():
        pool = sorted(pools[name], key=lambda p: p["parent_id"])
        if len(pool) < count:
            raise ValueError(f"stratum {name!r} has {len(pool)} eligible parents, needs {count}")
        for parent in rng.sample(pool, count):
            choices = sorted(parent["target_chunks"])
            picked.append({
                "stratum": name,
                "parent_id": parent["parent_id"],
                "source_type": parent["source_type"],
                "source_path": parent["source_path"],
                "title": parent["title"],
                "target_chunk_id": rng.choice(choices),
            })

    digest = hashlib.sha256()
    with corpus.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return {
        "status": "parents_frozen_before_query_authoring_or_search",
        "seed": SEED,
        "corpus": str(corpus.relative_to(root)),
        "corpus_sha256": digest.hexdigest(),
        "exclusion_rules": ["previous_holdout_sampled_parents", "previous_query_gold",
                            "stage28_inspected_top5_parents"],
        "excluded_parent_count": len(excluded),
        "min_parent_chars": MIN_PARENT_CHARS,
        "target_chunk_chars": [MIN_TARGET_CHARS, MAX_TARGET_CHARS],
        "strata": STRATA,
        "eligible_pool_sizes": dict(sorted((name, len(rows)) for name, rows in pools.items())),
        "sampled_counts": dict(Counter(row["stratum"] for row in picked)),
        "sampled": picked,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    corpus = root / "data/generated/holdout-v1/core.jsonl"
    result = sample(root, corpus)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"froze {len(result['sampled'])} parents; corpus {result['corpus_sha256']}")


if __name__ == "__main__":
    main()
