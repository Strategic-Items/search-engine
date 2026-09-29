"""holdout-v1 core의 PDF를 새 파서로 다시 청킹했을 때 검색이 달라지는지 잰다.

old  = 기존 `search-holdout` 색인(84,413청크) 그대로.
new  = 같은 색인에서 PDF 부모(568개)의 청크만 `rechunk_holdout_pdf.py` 산출물로 갈아 끼운 임시 색인.
       PDF가 아닌 부모(HTML·HWP·법령)는 벡터까지 그대로 복사한다. 본문이 같은 PDF 청크는 기존 벡터를
       재사용하고, 바뀐 청크만 새로 임베딩한다.

질의는 `queries_holdout_v1_adjudicated_combined.jsonl` 69문항. 근거 라벨이 청크 ID라서 PDF 청크를
다시 자르면 ID가 달라진다. 그래서 필수 구절(`evidence_requirements.phrases`) 기준으로 채점한다.
라벨이 만들어진 방식이 그 구절을 모두 담은 청크였으므로(build_holdout_queries.matches) old 색인에서는
ID 채점과 구절 채점이 같아야 하고, 이를 검사해 보고서에 적는다.

LLM 필터·답변 가능성 판정·재랭커·재작성은 끈 검색기 비교다. 서비스 alias는 건드리지 않고 임시 색인은
끝에 지운다.

    .venv/bin/python scripts/compare_holdout_pdf_rechunk.py
"""

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import random
import re
from unittest.mock import patch
from uuid import uuid4

import httpx
from opensearchpy.helpers import scan, streaming_bulk

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.indexing.documents import SearchDocument
from search_engine.search.query import retrieve

BASE = Path("data/generated/holdout-pdf-rechunk-v1")
CORE = Path("data/generated/holdout-v1/core.jsonl")
QUERIES = Path("data/generated/holdout-v1/queries_holdout_v1_adjudicated_combined.jsonl")
_KEEP = re.compile(r"[^0-9A-Za-z가-힣]")
K = 5
MODES = ["bm25", "hybrid"]
RESAMPLES = 5000


def norm(text: str) -> str:
    return _KEEP.sub("", text).lower()


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


class FixedQueryEmbedder:
    def __init__(self, vector):
        self.vector = vector

    def embed_query(self, query):
        return self.vector


def window(hits) -> list[tuple[str, str, str]]:
    """답변 모델이 받는 청크 전부: 문서 k개 × 그 문서가 딸고 온 청크."""
    seen, rows = set(), []
    for h in hits:
        for cid, body in [(h.id, h.body)] + [(p.id, p.body) for p in h.passages]:
            if cid not in seen:
                seen.add(cid)
                rows.append((cid, h.parent_id, body))
    return rows


def grade(q: dict, hits, pdf_parents: set[str]) -> dict:
    gold = {p for g in q["gold_groups"] for p in g}
    returned = [h.parent_id for h in hits]
    rank = next((i + 1 for i, p in enumerate(returned) if p in gold), None)
    chunks = window(hits)
    satisfied, id_satisfied = [], []
    for group, req in zip(q["evidence_groups"], q["evidence_requirements"]):
        plain = {c for c in group if c.split("#")[0] not in pdf_parents}
        pdf_group = {c.split("#")[0] for c in group if c.split("#")[0] in pdf_parents}
        phrases = [norm(p) for p in req["phrases"]]
        by_id = any(cid in group for cid, _, _ in chunks)
        by_phrase = any(cid in plain or (pid in pdf_group and all(ph in norm(body) for ph in phrases))
                        for cid, pid, body in chunks)
        satisfied.append(by_phrase)
        id_satisfied.append(by_id)
    return {"document_p1": bool(returned and returned[0] in gold), "document_hit_at_5": bool(rank),
            "mrr_at_5": 1 / rank if rank else 0.0, "evidence_found": satisfied,
            "evidence_found_by_id": id_satisfied,
            "evidence_recall": sum(satisfied) / len(satisfied),
            "evidence_all": all(satisfied), "window_chunks": len(chunks),
            "window_chars": sum(len(b) for _, _, b in chunks),
            "returned": returned, "window_ids": [c for c, _, _ in chunks]}


def available(q: dict, rows_by_parent: dict[str, list[dict]], pdf_parents: set[str]) -> list[bool]:
    """이 색인에 필수 구절을 통째로 담은 청크가 정답 PDF 부모 안에 있는가(없으면 청킹이 근거를 잃은 것)."""
    out = []
    for group, req in zip(q["evidence_groups"], q["evidence_requirements"]):
        if any(c.split("#")[0] not in pdf_parents for c in group):
            out.append(True)
            continue
        phrases = [norm(p) for p in req["phrases"]]
        parents = {c.split("#")[0] for c in group}
        out.append(any(all(ph in norm(r["body"]) for ph in phrases)
                       for p in parents for r in rows_by_parent.get(p, [])))
    return out


def interval(deltas: list[float], rng: random.Random) -> tuple[float, float]:
    n = len(deltas)
    means = sorted(sum(deltas[rng.randrange(n)] for _ in range(n)) / n for _ in range(RESAMPLES))
    return means[int(0.025 * RESAMPLES)], means[int(0.975 * RESAMPLES) - 1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--new", type=Path, default=BASE / "new" / "pdf_chunks.jsonl")
    parser.add_argument("--out", type=Path, default=BASE / "compare")
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    settings = get_settings().model_copy(update={
        "search_chunk_filter": False, "search_answerability_judge": False,
        "search_rerank_chunks": False, "search_query_rewrite": False})
    client = create_client(settings)
    aliases = list(client.indices.get_alias(name="search-holdout"))
    assert len(aliases) == 1
    old_index = aliases[0]
    old_count = client.count(index=old_index)["count"]

    core = read(CORE)
    pdf_parents = {r["parent_id"] for r in core if (r.get("source_path") or "").lower().endswith(".pdf")}
    new_rows = read(args.new)
    new_docs = [SearchDocument.model_validate(r).index_source() for r in new_rows]
    new_parents = {r["parent_id"] for r in new_docs}
    print(f"old {old_index} {old_count}청크 / PDF 부모 {len(pdf_parents)} → 새 청크 {len(new_docs)} ({len(new_parents)}부모)",
          flush=True)

    keep, old_pdf = [], []
    for hit in scan(client, index=old_index, query={"query": {"match_all": {}}}, size=1000):
        (old_pdf if hit["_source"]["parent_id"] in pdf_parents else keep).append(hit)
    assert len(keep) + len(old_pdf) == old_count
    embedder = OllamaEmbedder(settings)
    model = settings.ollama_embedding_model

    def key(text):
        return hashlib.sha256((model + "\n" + text).encode()).hexdigest()

    vectors = {key(embedding_text(h["_source"]["title"], h["_source"]["body"])): h["_source"]["embedding"]
               for h in old_pdf}
    cache_path = out / "embedding_cache.jsonl"
    if cache_path.exists():
        vectors.update({r["key"]: r["vector"] for r in read(cache_path)})

    def embed_all(texts, label):
        pending = list(dict.fromkeys(t for t in texts if key(t) not in vectors))
        print(f"{label}: 새로 임베딩 {len(pending)} / {len(texts)}", flush=True)
        with cache_path.open("a") as file:
            for start in range(0, len(pending), 16):
                batch = pending[start:start + 16]
                try:
                    got = embedder.embed(batch)
                except httpx.HTTPStatusError as error:
                    if error.response.status_code != 400 or "context length" not in error.response.text:
                        raise
                    got = []
                    for text in batch:
                        used = text
                        while True:
                            try:
                                got.append(embedder.embed([used])[0])
                                break
                            except httpx.HTTPStatusError as single:
                                if single.response.status_code != 400 or "context length" not in single.response.text \
                                        or len(used) < 256:
                                    raise
                                used = used[:len(used) // 2]
                        if used != text:
                            with (out / "embedding_overflows.jsonl").open("a") as flow:
                                flow.write(json.dumps({"key": key(text), "chars": len(text),
                                                       "prefix": len(used)}) + "\n")
                for text, vector in zip(batch, got):
                    vectors[key(text)] = vector
                    file.write(json.dumps({"key": key(text), "vector": vector}) + "\n")
                file.flush()
                if (start // 16) % 50 == 0:
                    print(f"  {label} {min(start + 16, len(pending))}/{len(pending)}", flush=True)
        return [vectors[key(t)] for t in texts]

    questions = read(QUERIES)
    assert len(questions) == 69
    q_vectors = dict(zip([q["qid"] for q in questions],
                         embed_all([q["query"] for q in questions], "질의")))
    old_keys = {key(embedding_text(h["_source"]["title"], h["_source"]["body"])) for h in old_pdf}
    reused = sum(key(embedding_text(r["title"], r["body"])) in old_keys for r in new_docs)
    doc_vectors = embed_all([embedding_text(r["title"], r["body"]) for r in new_docs], "새 PDF 청크")
    for r, vector in zip(new_docs, doc_vectors):
        r["embedding"] = vector

    source_settings = client.indices.get_settings(index=old_index)[old_index]["settings"]["index"]
    index_settings = {k: source_settings[k] for k in ["analysis", "number_of_shards", "number_of_replicas", "knn"]}
    mapping = client.indices.get_mapping(index=old_index)[old_index]["mappings"]
    temp = f"holdout-pdf-rechunk-{uuid4().hex[:12]}"
    created = False
    results = []
    try:
        client.indices.create(index=temp, body={"settings": index_settings, "mappings": mapping})
        created = True
        actions = [{"_index": temp, "_id": h["_id"], "_source": h["_source"]} for h in keep]
        actions += [{"_index": temp, "_id": r["id"], "_source": r} for r in new_docs]
        for ok, _ in streaming_bulk(client, actions, chunk_size=500, raise_on_error=True):
            assert ok
        client.indices.refresh(index=temp)
        assert client.count(index=temp)["count"] == len(keep) + len(new_docs)
        print(f"임시 색인 {temp}: {len(keep)} 유지 + {len(new_docs)} 새 PDF 청크", flush=True)

        corpora = {"old": {}, "new": {}}
        for h in old_pdf:
            corpora["old"].setdefault(h["_source"]["parent_id"], []).append(h["_source"])
        for r in new_docs:
            corpora["new"].setdefault(r["parent_id"], []).append(r)
        arms = {"old": old_index, "new": temp}
        for arm, index in arms.items():
            for mode in MODES:
                for i, q in enumerate(questions, 1):
                    with patch("search_engine.search.query.get_settings", return_value=settings):
                        hits = retrieve(client, index, q["query"], date.today(), K,
                                        embedder=FixedQueryEmbedder(q_vectors[q["qid"]]), mode=mode,
                                        strict=True, answerability=False, query_rewrite=False,
                                        rerank_chunks=False)
                    row = {"arm": arm, "mode": mode, "qid": q["qid"], "category": q["category"],
                           "query": q["query"], **grade(q, hits, pdf_parents),
                           "evidence_available": available(q, corpora[arm], pdf_parents)}
                    gold_parents = {c.split("#")[0] for g in q["evidence_groups"] for c in g}
                    row["touches_pdf"] = bool({p for g in q["gold_groups"] for p in g} & pdf_parents
                                              or gold_parents & pdf_parents)
                    row["pdf_only_evidence"] = gold_parents <= pdf_parents
                    results.append(row)
                print(f"{arm} {mode} 완료", flush=True)
    finally:
        if created:
            client.indices.delete(index=temp)
        assert list(client.indices.get_alias(name="search-holdout")) == [old_index]
        assert client.count(index=old_index)["count"] == old_count
        print("임시 색인 삭제, search-holdout alias·청크 수 그대로", flush=True)

    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    write_report(out, results, questions, new_docs, old_pdf, reused, pdf_parents, temp)


def write_report(out, results, questions, new_docs, old_pdf, reused, pdf_parents, temp):
    scopes = {"전체 69": lambda r: True,
              "PDF를 건드리는 질의": lambda r: r["touches_pdf"],
              "근거가 전부 PDF인 질의": lambda r: r["pdf_only_evidence"]}
    fields = ["document_p1", "document_hit_at_5", "mrr_at_5", "evidence_recall", "evidence_all"]

    def mean(rows, f):
        return sum(r[f] for r in rows) / len(rows) if rows else float("nan")

    summary = []
    lines = ["# holdout-v1 PDF 재청킹 전후 비교", ""]
    lines += [f"old = 기존 색인. new = PDF 부모 {len(pdf_parents)}개의 청크를 새 파서 결과로 교체 "
              f"(청크 {len(old_pdf)} → {len(new_docs)}). 나머지 부모는 그대로.", ""]
    for scope, pred in scopes.items():
        lines += [f"## {scope}", "",
                  "| 검색 | 버전 | n | 근거 Recall@5 | 근거 전부 | 문서 P@1 | Hit@5 | MRR@5 | 필수 구절 가용 | 창 청크 | 창 글자 |",
                  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for mode in MODES:
            for arm in ("old", "new"):
                rows = [r for r in results if r["arm"] == arm and r["mode"] == mode and pred(r)]
                avail = sum(sum(r["evidence_available"]) for r in rows) / max(1, sum(len(r["evidence_available"]) for r in rows))
                s = {"scope": scope, "mode": mode, "arm": arm, "n": len(rows),
                     **{f: mean(rows, f) for f in fields}, "available": avail,
                     "window_chunks": mean(rows, "window_chunks"), "window_chars": mean(rows, "window_chars")}
                summary.append(s)
                lines.append(f"| {mode} | {arm} | {s['n']} | {s['evidence_recall']:.3f} | {s['evidence_all']:.3f} | "
                             f"{s['document_p1']:.3f} | {s['document_hit_at_5']:.3f} | {s['mrr_at_5']:.3f} | "
                             f"{avail:.3f} | {s['window_chunks']:.1f} | {s['window_chars']:.0f} |")
        lines.append("")
    lines += ["## 전후 차이와 95% 부트스트랩 구간 (new − old, 질의 재표집 5,000회)", "",
              "| 범위 | 검색 | 지표 | 차이 | 95% 구간 | 좋아진 질의 | 나빠진 질의 |", "|---|---|---|---:|---|---:|---:|"]
    rng = random.Random(44)
    by = {(r["arm"], r["mode"], r["qid"]): r for r in results}
    for scope, pred in scopes.items():
        for mode in MODES:
            qids = [q["qid"] for q in questions if pred(by["old", mode, q["qid"]])]
            for f in ["evidence_recall", "document_p1"]:
                d = [float(by["new", mode, q][f]) - float(by["old", mode, q][f]) for q in qids]
                lo, hi = interval(d, rng)
                lines.append(f"| {scope} | {mode} | {f} | {sum(d) / len(d):+.3f} | [{lo:+.3f}, {hi:+.3f}] | "
                             f"{sum(x > 0 for x in d)} | {sum(x < 0 for x in d)} |")
    mismatch = [(r["arm"], r["mode"], r["qid"]) for r in results
                if r["arm"] == "old" and r["evidence_found"] != r["evidence_found_by_id"]]
    lines += ["", f"검증: old 색인에서 구절 채점과 청크 ID 채점이 다른 (검색, 질의) {len(mismatch)}건 / "
                  f"{sum(1 for r in results if r['arm'] == 'old')}건.",
              f"기존 벡터를 재사용한 새 청크 {reused}/{len(new_docs)}개. 임시 색인 `{temp}`는 삭제했다."]
    changes = []
    for mode in MODES:
        for q in questions:
            a, b = by["old", mode, q["qid"]], by["new", mode, q["qid"]]
            if a["evidence_found"] != b["evidence_found"] or a["document_p1"] != b["document_p1"]:
                changes.append({"mode": mode, "qid": q["qid"], "query": q["query"],
                                "old_found": a["evidence_found"], "new_found": b["evidence_found"],
                                "old_avail": a["evidence_available"], "new_avail": b["evidence_available"],
                                "old_p1": a["document_p1"], "new_p1": b["document_p1"]})
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "changes.json").write_text(json.dumps(changes, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)


if __name__ == "__main__":
    main()
