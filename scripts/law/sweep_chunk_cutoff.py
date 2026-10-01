"""법령 질문 21개에서 청크 컷오프 비율별 Recall·Precision 곡선을 잰다. 서비스·인덱스는 건드리지 않는다.

컷오프는 창에 실린 청크 중 최고 점수의 비율에 못 미치는 청크를 뺀다. 문서 컷오프는 쓰지 않고(0), 상위 5문서·문서당 6청크
안에서 청크만 자른다. 비율 1.0은 1위 청크 하나만 남긴다.
 - bm25·dense: retrieve가 돌려준 창의 청크 점수(검색기 자체 점수)에 비율을 건다.
 - hybrid: 서비스에 이미 있는 청크 우선 경로(청크 RRF + 비율 컷오프, 예산 10청크)를 비율만 바꿔 쓴다.
 - SPLADE·SPLADE+dense: 오프라인 점수에 같은 방식으로 건다(SPLADE+dense는 청크 RRF 점수).

    .venv/bin/python scripts/law/sweep_chunk_cutoff.py SPLADE_JSON [방식 이름 일부 ...]

CUTOFF_UNIT=doc이면 문서 단위로 자른다: 문서 점수는 그 문서의 최고 청크 점수이고, 1위 문서 점수의 비율에 못 미치는 문서를
뺀다(상위 5문서 안). 이때 청크 열은 문서 최고 청크 하나씩이라 청크 지표는 뜻이 없고 문서 Precision·Recall·Hit·평균 문서 수만 읽는다.
청크 우선 hybrid는 문서 단위가 없어 빠진다.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search.query import build_query, build_vector_query, retrieve

from category import QUERIES, alias as category_alias, source as category_source  # noqa: E402
K, PER_DOC, RRF_K = 5, 6, 60
UNIT = os.environ.get("CUTOFF_UNIT", "chunk")
RATIOS = [0.0, 0.5, 0.7, 0.8, 0.9, 0.95, 0.99] + ([1.0] if UNIT == "doc" else [])


def windows_by_score(chunks: list[tuple[str, float]], parent: dict[str, str], ratio: float) -> list[str]:
    """점수 내림차순 청크 -> 상위 K문서·문서당 PER_DOC 안에서 최고 점수의 ratio 미만을 뺀 청크 id들."""
    if not chunks:
        return []
    floor = chunks[0][1] * ratio
    docs, out = [], []
    for cid, score in chunks:
        if score < floor:
            break
        doc = parent[cid]
        if doc not in docs:
            if len(docs) == K:
                continue
            docs.append(doc)
        if sum(parent[c] == doc for c in out) < PER_DOC:
            out.append(cid)
    return out


def docs_by_score(chunks: list[tuple[str, float]], parent: dict[str, str], ratio: float) -> list[str]:
    """점수 내림차순 청크 -> 문서 최고 점수가 1위 문서의 ratio 이상인 상위 K문서의 최고 청크 id들."""
    best: dict[str, tuple[str, float]] = {}
    for cid, score in chunks:
        best.setdefault(parent[cid], (cid, score))
    ranked = list(best.values())[:K]
    if not ranked:
        return []
    return [cid for cid, score in ranked if score >= ranked[0][1] * ratio]


if UNIT == "doc":
    windows_by_score = docs_by_score


def rrf_chunks(lists: list[list[tuple[str, float]]]) -> list[tuple[str, float]]:
    fused: dict[str, float] = {}
    for ranked in lists:
        for rank, (cid, _) in enumerate(ranked, 1):
            fused[cid] = fused.get(cid, 0.0) + 1 / (RRF_K + rank)
    return sorted(fused.items(), key=lambda x: -x[1])


def main(splade_file: str, only: list[str]) -> None:
    sp = json.loads(Path(splade_file).read_text())
    rows = [json.loads(line) for line in QUERIES.read_text(encoding="utf-8").splitlines() if line.strip()]
    settings = get_settings()
    settings.search_chunk_filter = False
    client, embedder = create_client(settings), OllamaEmbedder(settings)
    alias = category_alias(settings)
    parent = {cid: cid.split("#")[0] for cid in sp["docs"]}
    inverted: dict[str, list] = {}
    for cid, vec in sp["docs"].items():
        for token, weight in vec.items():
            inverted.setdefault(token, []).append((cid, weight))

    cache = {}

    def splade(row):
        scores: dict[str, float] = {}
        for token, qw in sp["queries"][row["qid"]].items():
            for cid, dw in inverted.get(token, ()):
                scores[cid] = scores.get(cid, 0.0) + qw * dw
        return sorted(scores.items(), key=lambda x: -x[1])[:100]

    def dense_chunks(row):
        body = {"query": build_vector_query(embedder.embed_query(row["query"]), date.today(), 50, row["query"])}
        hits = client.search(index=alias, body=body, size=50, _source=False)["hits"]["hits"]
        return [(h["_id"], h["_score"]) for h in hits]

    def bm25_chunks(row):
        body = {"query": build_query(row["query"], date.today())}
        hits = client.search(index=alias, body=body, size=100, _source=False)["hits"]["hits"]
        return [(h["_id"], h["_score"]) for h in hits]

    def served(row, mode):
        """retrieve의 창(문서 컷오프 없음)을 (청크 id, 점수) 목록으로."""
        key = (row["qid"], mode)
        if key not in cache:
            hits = retrieve(client, alias, row["query"], date.today(), K, mode=mode, cutoff_ratio=0.0,
                            score_floor=0.0, answerability=False)
            chunks = [(h.id, h.score or 0.0) for h in hits] + [(p.id, p.score or 0.0) for h in hits for p in h.passages]
            cache[key] = sorted(chunks, key=lambda x: -x[1])
        return cache[key]

    def hybrid_chunk_first(row, ratio):
        settings.search_chunk_first, settings.search_chunk_first_cutoff_ratio = True, ratio
        settings.search_chunk_first_max_chunks, settings.search_chunk_first_max_documents = 10, K
        try:
            hits = retrieve(client, alias, row["query"], date.today(), K, mode="hybrid", cutoff_ratio=0.0,
                            score_floor=0.0, answerability=False)
        finally:
            settings.search_chunk_first = False
        return [c for h in hits for c in h.chunk_ids]

    systems = {
        "bm25": lambda r, x: windows_by_score(served(r, "bm25"), parent, x),
        "dense": lambda r, x: windows_by_score(served(r, "vector"), parent, x),
        "hybrid (BM25+dense, 청크 우선)": hybrid_chunk_first,
        "SPLADE": lambda r, x: windows_by_score(splade(r), parent, x),
        "SPLADE+dense (청크 RRF)": lambda r, x: windows_by_score(rrf_chunks([splade(r), dense_chunks(r)]), parent, x),
        "BM25+SPLADE (청크 RRF)": lambda r, x: windows_by_score(rrf_chunks([bm25_chunks(r), splade(r)]), parent, x),
        "BM25+SPLADE+dense (청크 RRF)": lambda r, x: windows_by_score(
            rrf_chunks([bm25_chunks(r), splade(r), dense_chunks(r)]), parent, x),
        "BM25+dense (청크 RRF)": lambda r, x: windows_by_score(rrf_chunks([bm25_chunks(r), dense_chunks(r)]), parent, x),
    }
    if UNIT == "doc":
        systems.pop("hybrid (BM25+dense, 청크 우선)")
    systems = {k: v for k, v in systems.items() if not only or any(o in k for o in only)}
    print(f"{len(rows)}문항, 상위 {K}문서·문서당 최대 {PER_DOC}청크, 청크 컷오프 비율별\n")
    for name, run in systems.items():
        print(f"### {name}\n| 비율 | 근거 Recall(청크) | Precision(하한) | 그 창의 최대 | 평균 청크 수 | 문서 Precision | 문서 Recall | 평균 문서 수 | 1위 문서 정답 |\n|---|---|---|---|---|---|---|---|---|")
        for ratio in RATIOS:
            found = 0
            precision, ceiling, sizes = [], [], []
            doc_precision, doc_recall, doc_counts, top1 = [], [], [], 0
            for row in rows:
                window = run(row, ratio)
                gold = set(row["evidence_groups"][0])
                found += bool(gold & set(window))
                n = len(window)
                sizes.append(n)
                precision.append(sum(c in gold for c in window) / n if n else 0.0)
                ceiling.append(min(len(gold), n) / n if n else 0.0)
                docs = {c.split("#")[0] for c in window}
                doc_counts.append(len(docs))
                top1 += bool(window) and window[0].split("#")[0] in row["gold"]
                doc_precision.append(len(docs & set(row["gold"])) / len(docs) if docs else 0.0)
                doc_recall.append(len(docs & set(row["gold"])) / len(row["gold"]))
            m = len(rows)
            print(f"| {ratio} | {found}/{m} = {found / m:.3f} | {sum(precision) / m:.3f} | {sum(ceiling) / m:.3f} | {sum(sizes) / m:.1f} | {sum(doc_precision) / m:.3f} | {sum(doc_recall) / m:.3f} | {sum(doc_counts) / m:.1f} | {top1}/{m} |")
        print()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
