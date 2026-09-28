"""Read-only current-code mode comparison on frozen combined indexes."""
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.evaluation.compare import compare
from search_engine.evaluation.evaluate import quality_metrics
from search_engine.search.query import retrieve

DEST = Path("data/generated/routing-combined-v1")
SOURCES = (
    Path("data/generated/period-topic-v1/results/docs135-candidate.json"),
    Path("data/generated/period-topic-v1/results/holdout69-candidate.json"),
)
FIELDS = ("qid", "category", "query", "reference_answer", "gold", "gold_groups",
          "gold_unit", "evidence_groups", "evidence_requirements", "review_status",
          "human_review", "answerable", "evidence", "adjudication")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(queries, client, index, provenance, name):
    collected = {m: [] for m in ("bm25", "vector", "hybrid")}
    for i, row in enumerate(queries):
        report = compare([row], client, index, ks=(1, 5), repeats=1, warmup=0,
                         as_of=date(2026, 9, 25))
        for mode in collected:
            collected[mode].extend(report["modes"][mode]["queries"])
        if (i + 1) % 10 == 0 or i + 1 == len(queries):
            print(f"{name}: {i + 1}/{len(queries)}", flush=True)
    report["modes"] = {m: {"queries": rows, "metrics": quality_metrics(rows, 5)}
                       for m, rows in collected.items()}
    report.update(provenance)
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    (DEST / f"{name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    queries = [{k: row[k] for k in FIELDS if k in row}
               for p in SOURCES for row in json.loads(p.read_text())["queries"]]
    validation_path = Path("data/generated/validation-v2/queries_combined_returned_audited.jsonl")
    validation = [json.loads(line) for line in validation_path.read_text().splitlines()]
    for name, rows in (("queries", queries), ("validation", validation)):
        (DEST / f"{name}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    assert len(queries) == 204 and len({q["qid"] for q in queries}) == 204
    settings = get_settings()
    client = create_client(settings)
    indexes = sorted(client.indices.get(index="search-holdout,search-docs-only"))
    index = ",".join(indexes)
    corpus = {i: {"count": client.count(index=i)["count"],
                  "embedding_count": client.count(index=i, body={"query": {
                      "exists": {"field": "embedding"}}})["count"]} for i in indexes}
    assert sorted(v["count"] for v in corpus.values()) == [1198, 84413]
    assert all(v["count"] == v["embedding_count"] for v in corpus.values())
    for mapping in client.indices.get_mapping(index=index).values():
        assert mapping["mappings"]["properties"]["embedding"]["dimension"] == settings.search_embedding_dimensions
    wanted = {c for q in queries + validation for group in q["evidence_groups"] for c in group}
    docs = client.mget(index=indexes[0], body={"docs": [
        {"_index": i, "_id": c} for c in sorted(wanted) for i in indexes]})["docs"]
    found = {r["_id"]: r["_source"] for r in docs if r.get("found")}
    missing = sorted(wanted - set(found))
    # Legacy core aliases contributed two obsolete alternatives to docs gold.
    # Keep every indexed alternative, and fail if a whole requirement vanishes.
    for q in queries + validation:
        q["evidence_groups"] = [[c for c in group if c in found] for group in q["evidence_groups"]]
        assert all(q["evidence_groups"]), f"whole evidence requirement absent: {q['qid']}"
        absent_parents = {c.rsplit("#", 1)[0] for c in missing}
        q["gold"] = [p for p in q["gold"] if p not in absent_parents]
        if "gold_groups" in q:
            q["gold_groups"] = [[p for p in g if p not in absent_parents] for g in q["gold_groups"]]
            assert all(q["gold_groups"])
        q["evidence"] = [e for e in q.get("evidence", []) if e["chunk_id"] in found]
        for requirement in q.get("evidence_requirements", []):
            if "acceptable_chunk_ids" in requirement:
                requirement["acceptable_chunk_ids"] = [c for c in requirement["acceptable_chunk_ids"] if c in found]
    for name, rows in (("queries", queries), ("validation", validation)):
        (DEST / f"{name}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    for q in queries + validation:
        for group in q["evidence_groups"]:
            assert all(found[c]["parent_id"] == c.rsplit("#", 1)[0] for c in group)
        for evidence in q.get("evidence", []):
            assert evidence["quote"] in found[evidence["chunk_id"]]["body"]
    provenance = {
        "corpus": corpus, "index": index, "settings": {
            k: v for k, v in settings.model_dump().items()
            if k.startswith("search_") or k == "ollama_embedding_model"},
        "sources": {str(p): sha(p) for p in (*SOURCES, validation_path)},
        "excluded_unindexed_legacy_alternatives": missing,
        "code_sha256": sha(Path(retrieve.__code__.co_filename)),
        "label_validation": "All evidence chunks present, parent membership and recorded quotes checked; no full corpus content scan.",
    }
    (DEST / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    print(f"Frozen {len(queries)} training/OOF and {len(validation)} separate evaluation questions; {sum(v['count'] for v in corpus.values())} chunks", flush=True)
    run(queries, client, index, provenance, "comparison204")
    run(validation, client, index, provenance, "comparison36")


if __name__ == "__main__":
    main()
