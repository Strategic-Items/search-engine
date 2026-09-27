"""Offline, document-grouped out-of-fold recall-gain routing experiment.

Pure Python; no serving changes or new runtime dependencies. Settings are fixed
in data/generated/routing-v1/protocol.md before inspecting experiment results.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import re

from scripts.evaluate_mode_oracle import per_query

MODES = ("hybrid", "bm25", "vector")


def features(rows: dict, results: bool) -> dict[str, float]:
    text = rows["hybrid"]["query"]
    out = {
        "chars": len(text), "words": len(text.split()),
        "digit_count": len(re.findall(r"\d", text)),
        "latin_count": len(re.findall(r"[A-Za-z]", text)),
        "article": int(bool(re.search(r"제\s*\d+\s*조", text))),
        "year": int(bool(re.search(r"(?:19|20)\d{2}", text))),
        "quoted": int(bool(re.search(r"[\"'‘’“”]", text))),
        "question_terms": len(re.findall(r"어떻게|무엇|어떤|언제|어디|누가|얼마|왜", text)),
    }
    if not results:
        return out
    parents = {m: rows[m]["returned"][:5] for m in MODES}
    chunks = {m: {c for group in rows[m]["returned_chunks"][:5] for c in group}
              for m in MODES}
    for mode in MODES:
        out[f"{mode}_parents"] = len(parents[mode])
        out[f"{mode}_chunks"] = len(chunks[mode])
    for a, b in (("bm25", "vector"), ("bm25", "hybrid"), ("vector", "hybrid")):
        for name, left, right in (("parents", set(parents[a]), set(parents[b])),
                                  ("chunks", chunks[a], chunks[b])):
            out[f"{a}_{b}_{name}_jaccard"] = len(left & right) / max(1, len(left | right))
        out[f"{a}_{b}_top1_equal"] = int(bool(parents[a] and parents[b])
                                                    and parents[a][0] == parents[b][0])
    return out


def fit(x: list[dict], y: list[float], depth: int = 2) -> dict:
    mean = sum(y) / len(y)
    leaf = {"prediction": mean, "samples": len(y)}
    if depth == 0 or len(y) < 16:
        return leaf
    base = sum((v - mean) ** 2 for v in y)
    best = None
    for name in sorted(x[0]):
        values = sorted({row[name] for row in x})
        for low, high in zip(values, values[1:]):
            threshold = (low + high) / 2
            left = [i for i, row in enumerate(x) if row[name] <= threshold]
            right = [i for i, row in enumerate(x) if row[name] > threshold]
            if min(len(left), len(right)) < 8:
                continue
            error = 0.0
            for indices in (left, right):
                avg = sum(y[i] for i in indices) / len(indices)
                error += sum((y[i] - avg) ** 2 for i in indices)
            if error < base - 1e-12 and (best is None or error < best[0] - 1e-12):
                best = (error, name, threshold, left, right)
    if best is None:
        return leaf
    _, name, threshold, left, right = best
    return {**leaf, "feature": name, "threshold": threshold,
            "left": fit([x[i] for i in left], [y[i] for i in left], depth - 1),
            "right": fit([x[i] for i in right], [y[i] for i in right], depth - 1)}


def predict(tree: dict, x: dict) -> float:
    while "feature" in tree:
        tree = tree["left" if x[tree["feature"]] <= tree["threshold"] else "right"]
    return tree["prediction"]


def document_groups(rows: dict) -> list[list[str]]:
    parent = {qid: qid for qid in rows}
    def root(qid):
        while parent[qid] != qid:
            parent[qid] = parent[parent[qid]]
            qid = parent[qid]
        return qid
    owners = {}
    for qid, row in rows.items():
        for doc in row["gold"]:
            if doc in owners:
                parent[root(qid)] = root(owners[doc])
            owners[doc] = qid
    groups = {}
    for qid in rows:
        groups.setdefault(root(qid), []).append(qid)
    return [sorted(group) for group in groups.values()]


def bootstrap(deltas: dict, groups: list[list[str]]) -> list[float]:
    rng = random.Random(44)
    samples = []
    for _ in range(5000):
        picked = [rng.choice(groups) for _ in groups]
        samples.append(sum(deltas[qid] for group in picked for qid in group)
                       / sum(map(len, picked)))
    samples.sort()
    return [samples[124], samples[4874]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    by_mode = {m: {r["qid"]: r for r in report["modes"][m]["queries"]
                   if r.get("evidence_groups")} for m in MODES}
    qids = sorted(by_mode["hybrid"])
    assert all(set(by_mode[m]) == set(qids) for m in MODES)
    rows = {qid: {m: by_mode[m][qid] for m in MODES} for qid in qids}
    assert all(len({r["query"] for r in row.values()}) == 1 for row in rows.values())
    assert all(len({json.dumps(r["evidence_groups"], sort_keys=True) for r in row.values()}) == 1
               for row in rows.values())
    scores = {qid: {m: per_query(rows[qid][m], 5) for m in MODES} for qid in qids}
    groups = document_groups(by_mode["hybrid"])
    rng = random.Random(44)
    rng.shuffle(groups)
    groups.sort(key=len, reverse=True)
    folds = [[] for _ in range(5)]
    for group in groups:
        min(folds, key=len).extend(group)
    assert all(folds) and sorted(q for fold in folds for q in fold) == qids
    choices = {m: {q: m for q in qids} for m in MODES}
    choices["oracle"] = {q: max(MODES, key=lambda m: scores[q][m]) for q in qids}
    models = {}
    predicted = {}
    for results in (False, True):
        name = "query_and_results" if results else "query_only"
        x = {q: features(rows[q], results) for q in qids}
        choices[name], predicted[name], models[name] = {}, {}, []
        for fold in folds:
            train = sorted(set(qids) - set(fold))
            train_docs = {p for q in train for p in rows[q]["hybrid"]["gold"]}
            test_docs = {p for q in fold for p in rows[q]["hybrid"]["gold"]}
            assert not train_docs & test_docs, "shared gold document across train/test"
            trees = {m: fit([x[q] for q in train],
                            [scores[q][m][0] - scores[q]["hybrid"][0] for q in train])
                     for m in MODES[1:]}
            models[name].append({"test_qids": fold, "train_count": len(train), "trees": trees})
            for q in fold:
                gain = {m: predict(trees[m], x[q]) for m in MODES[1:]}
                winner = max(gain, key=gain.get)
                choices[name][q] = winner if gain[winner] > 0.02 else "hybrid"
                predicted[name][q] = gain
    summary = {}
    for name, pick in choices.items():
        deltas = {q: scores[q][pick[q]][0] - scores[q]["hybrid"][0] for q in qids}
        summary[name] = {
            "evidence_recall_at_5": sum(scores[q][pick[q]][0] for q in qids) / len(qids),
            "evidence_mrr_at_5": sum(scores[q][pick[q]][1] for q in qids) / len(qids),
            "choices": dict(Counter(pick.values())),
            "recall_improved_queries": sum(d > 1e-12 for d in deltas.values()),
            "recall_harmed_queries": sum(d < -1e-12 for d in deltas.values()),
            "recall_delta_ci95_group_bootstrap": bootstrap(deltas, groups),
        }
    output = {"source": str(args.report),
              "source_sha256": hashlib.sha256(args.report.read_bytes()).hexdigest(),
              "protocol": "data/generated/routing-v1/protocol.md", "queries": len(qids),
              "document_groups": groups, "folds": folds, "summary": summary,
              "models": models, "oof_predictions": predicted,
              "per_query": [{"qid": q, "query": rows[q]["hybrid"]["query"],
                             "scores": scores[q], "choices": {n: p[q] for n, p in choices.items()}}
                            for q in qids]}
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"queries": len(qids), "groups": len(groups),
                      "fold_sizes": list(map(len, folds)), "summary": summary},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
