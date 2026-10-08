"""Saved law100 experiments through stage 45 for the question explorer."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "data/generated"
OUTPUT = ROOT / "docs/presentation/question_explorer/data/category-stage-history.js"


def results(path: Path, *keys: str) -> dict[str, dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    for key in keys:
        value = value[key]
    return {row["qid"].rsplit("-", 1)[-1]: row for row in value}


def load_groups() -> dict[str, list[set[str]]]:
    rows = (json.loads(line) for line in
            (ROOT / "data/queries_law100_v1.jsonl").read_text(encoding="utf-8").splitlines())
    return {r["qid"].rsplit("-", 1)[-1]: [set(g) for g in r["evidence_groups"]] for r in rows}


GROUPS = load_groups()


def rank(rows: dict[str, dict], qid: str) -> int | None:
    """Window position where every evidence group is met; minus that of the first gold chunk if only some are."""
    window = rows[qid]["window"]
    groups = GROUPS[qid]
    for pos in range(1, len(window) + 1):
        if all(g & set(window[:pos]) for g in groups):
            return pos
    first = next((pos for pos, c in enumerate(window, 1) if any(c in g for g in groups)), None)
    return -first if first else None


def main() -> None:
    path = GENERATED / "splade-heading-path-2026-10-06/results.json"
    splade_before = results(path, "outcomes", "baseline", "splade", "results")
    splade_after = results(path, "outcomes", "heading_path", "splade", "results")
    hybrid_before = results(path, "outcomes", "baseline", "hybrid", "results")
    hybrid_after = results(path, "outcomes", "heading_path", "hybrid", "results")

    path = GENERATED / "dense-heading-path-2026-10-06/results.json"
    dense_before = results(path, "outcomes", "service_baseline", "vector", "results")

    path = GENERATED / "superseded-weight-2026-10-07/search-law.json"
    weight_before = results(path, "weights", "1.0", "results")
    weight_after = results(path, "weights", "0.97", "results")

    path = GENERATED / "resolved-editions-2026-10-07/results.json"
    edition_before = results(path, "arms", "original/w1.0/shipped", "results")
    edition_after = results(path, "arms", "resolved/w1.0/shipped", "results")

    qids = sorted(hybrid_before)
    if len(qids) != 100 or any(set(rows) != set(qids) for rows in (
        splade_before, splade_after, hybrid_after, dense_before,
        weight_before, weight_after, edition_before, edition_after,
    )):
        raise ValueError("the saved stage experiments do not cover the same 100 questions")
    if any(hybrid_before[qid]["window"] != weight_before[qid]["window"]
           for qid in qids):
        raise ValueError("stage 41 and stage 44 baselines differ")

    history = {}
    for qid in qids:
        history[qid] = {
            "s41": [rank(splade_before, qid), rank(dense_before, qid), rank(hybrid_before, qid)],
            "s42": [rank(splade_after, qid), rank(hybrid_after, qid)],
            "s44": rank(weight_after, qid),
            "s45": rank(edition_after, qid),
        }
    OUTPUT.write_text(
        "/* Saved law100 question results. Each rank is the position of the first complete evidence "
        "in the returned window; null means absent. Stages 42, 44, and 45 are experiment arms. */\n"
        "window.CATEGORY_STAGE_HISTORY="
        + json.dumps(history, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
