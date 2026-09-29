"""Freeze source parents for questions that name their source, before any candidate rule.

Users often say where they read something ("2006년 신문 연재 기사에서는 ...").
Only dated board materials can be named that way, so the pool is limited to parents
with a publication date outside FAQ and law sources. Every parent that any earlier
query set used as gold, or that an earlier sample or audit already opened, is
excluded before sampling. No retrieval result is loaded.
"""

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

SEED = 20260929
MIN_PARENT_CHARS = 300
MIN_TARGET_CHARS = 180
MAX_TARGET_CHARS = 5000
STRATA = {
    "동향자료 첨부": 4,
    "공지사항 첨부": 4,
    "국내외 소식": 3,
    "알기쉬운 전략물자 첨부": 2,
    "기타 게시판": 3,
}
OTHER_BOARDS = ("홍보자료", "전문가 칼럼", "CP공지사항", "동향자료", "국내외 소식 첨부")
QUERY_SETS = (
    "data/queries_docs_v2.jsonl", "data/queries_holdout_v1_adjudicated.jsonl",
    "data/queries_validation_v2_combined.jsonl", "data/queries_date_validation_v1.jsonl",
    "data/queries_date_confirm_v1.jsonl", "data/queries_period_other_v1.jsonl",
    "data/queries_period_topic_v1.jsonl", "data/queries_v1.jsonl",
    "data/generated/validation-v2/queries_combined_returned_audited.jsonl",
    "data/generated/date-validation-v1/queries_returned_audited.jsonl",
    "data/generated/period-other-v1/queries_returned_audited.jsonl",
    "data/generated/period-topic-v1/queries_returned_audited.jsonl",
)


def stratum(source_type: str) -> str | None:
    if source_type in STRATA:
        return source_type
    if source_type in OTHER_BOARDS or source_type.removesuffix(" 첨부") in OTHER_BOARDS:
        return "기타 게시판"
    return None


def prior_parents(root: Path) -> set[str]:
    excluded: set[str] = set()
    for name in QUERY_SETS:
        for line in (root / name).open(encoding="utf-8"):
            if line.strip():
                row = json.loads(line)
                excluded.update(row.get("gold") or [])
                excluded.update(p for group in row.get("gold_groups") or [] for p in group)
    holdout = root / "data/generated/holdout-v1"
    sampled = json.loads((holdout / "sampled_parents.json").read_text())
    excluded.update(row["parent_id"] for rows in sampled["picked"].values() for row in rows)
    audited = json.loads((holdout / "title1_dfs_top5_audit.json").read_text())
    excluded.update(row["parent_id"] for row in audited["judgments"])
    frozen = json.loads((root / "data/generated/validation-v2/frozen_sample.json").read_text())
    excluded.update(row["parent_id"] for row in frozen["sampled"])
    return excluded


def sample(root: Path, corpus: Path) -> dict:
    excluded = prior_parents(root)
    parents: dict[str, dict] = {}
    with corpus.open(encoding="utf-8") as file:
        for line in file:
            row = json.loads(line)
            parent_id = row["parent_id"]
            name = stratum(row["source_type"])
            if parent_id in excluded or name is None or not row.get("published_at"):
                continue
            parent = parents.setdefault(parent_id, {
                "parent_id": parent_id,
                "stratum": name,
                "source_type": row["source_type"],
                "source_path": row["source_path"],
                "published_at": row["published_at"],
                "title": row["title"].split(" — ")[0],
                "chars": 0,
                "target_chunks": [],
            })
            parent["chars"] += len(row["body"])
            if MIN_TARGET_CHARS <= len(row["body"]) <= MAX_TARGET_CHARS:
                parent["target_chunks"].append(row["id"])

    pools: dict[str, list[dict]] = defaultdict(list)
    for parent in parents.values():
        if parent["chars"] >= MIN_PARENT_CHARS and parent["target_chunks"]:
            pools[parent["stratum"]].append(parent)

    rng = random.Random(SEED)
    picked = []
    for name, count in STRATA.items():
        pool = sorted(pools[name], key=lambda p: p["parent_id"])
        if len(pool) < count:
            raise ValueError(f"stratum {name!r} has {len(pool)} eligible parents, needs {count}")
        for parent in rng.sample(pool, count):
            picked.append({
                **{key: parent[key] for key in ("stratum", "parent_id", "source_type",
                                                "source_path", "published_at", "title")},
                "target_chunk_id": rng.choice(sorted(parent["target_chunks"])),
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
        "exclusion_rules": ["gold_of_every_earlier_query_set", "previous_holdout_sampled_parents",
                            "stage28_inspected_top5_parents", "validation_v2_sampled_parents",
                            "no_publication_date"],
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
    result = sample(root, root / "data/generated/holdout-v1/core.jsonl")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"froze {len(result['sampled'])} parents; corpus {result['corpus_sha256']}")


if __name__ == "__main__":
    main()
