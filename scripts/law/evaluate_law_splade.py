"""법령 질문 21개에서 SPLADE를 BM25 대신 써 본다. 서비스·API·인덱스는 건드리지 않는 오프라인 비교다.

SPLADE 벡터는 `scripts/splade_hybrid/encode_sparse.py`(torch 환경)로 미리 만든 파일을 읽는다.
어휘 쪽만 BM25 -> SPLADE로 바꾸고, 밀집 쪽은 서비스와 같은 `search-law` kNN을 그대로 쓴다.

창을 만드는 방식은 `evaluate_law.py`와 같다: 상위 5문서, 문서당 최대 6청크. 목록은 융합 전에 각 검색기의
1위 점수 대비 비율로 자른다(SPLADE 0.90 = 기존 BM25 트림, 밀집 0.97). 최종 컷오프는 두 방식 모두 쓰지 않는다.

    HF_HUB_OFFLINE=1 /Users/jeongbin/git/search-engine/venv/bin/python scripts/splade_hybrid/encode_sparse.py \\
        --corpus C --queries data/queries_law_v1.jsonl --out S
    .venv/bin/python scripts/law/evaluate_law_splade.py S
"""

import json
import sys
from datetime import date
from pathlib import Path

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search.query import build_vector_query, retrieve

QUERIES = Path("data/queries_law_v1.jsonl")
K, PER_DOC, RRF_K = 5, 6, 60
TRIM = {"splade": 0.90, "vector": 0.97}
CANDIDATES = {"splade": 100, "vector": 50}


def trim(ranked: list[tuple[str, float]], ratio: float) -> list[tuple[str, float]]:
    return [x for x in ranked if x[1] >= ranked[0][1] * ratio] if ranked else []


def window(lists: dict[str, list[tuple[str, float]]], parent: dict[str, str]) -> list[list[str]]:
    """검색기별(트림된) 청크 목록 -> 상위 K문서, 문서마다 청크 id 목록. 문서·청크 모두 순위 RRF."""
    docs: dict[str, float] = {}
    chunks: dict[str, float] = {}
    for ranked in lists.values():
        seen = set()
        for rank, (cid, _) in enumerate(ranked, 1):
            chunks[cid] = chunks.get(cid, 0.0) + 1 / (RRF_K + rank)
            if parent[cid] not in seen:
                seen.add(parent[cid])
                docs[parent[cid]] = docs.get(parent[cid], 0.0) + 1 / (RRF_K + len(seen))
    top = sorted(docs, key=lambda d: -docs[d])[:K]
    return [sorted((c for c in chunks if parent[c] == d), key=lambda c: -chunks[c])[:PER_DOC] for d in top]


def main(splade_file: str) -> None:
    sp = json.loads(Path(splade_file).read_text())
    rows = [json.loads(line) for line in QUERIES.read_text(encoding="utf-8").splitlines() if line.strip()]
    settings = get_settings()
    settings.search_chunk_filter = False
    client, embedder = create_client(settings), OllamaEmbedder(settings)
    alias = settings.search_law_alias
    parent = {cid: cid.split("#")[0] for cid in sp["docs"]}
    index = {}
    for cid, vec in sp["docs"].items():
        for token, weight in vec.items():
            index.setdefault(token, []).append((cid, weight))

    def splade(qid):
        scores: dict[str, float] = {}
        for token, qw in sp["queries"][qid].items():
            for cid, dw in index.get(token, ()):
                scores[cid] = scores.get(cid, 0.0) + qw * dw
        return sorted(scores.items(), key=lambda x: -x[1])[:CANDIDATES["splade"]]

    def dense(query):
        body = {"query": build_vector_query(embedder.embed_query(query), date.today(), CANDIDATES["vector"], query)}
        hits = client.search(index=alias, body=body, size=CANDIDATES["vector"], _source=False)["hits"]["hits"]
        return [(h["_id"], h["_score"]) for h in hits]

    systems = {
        "bm25": lambda r: [h.chunk_ids for h in retrieve(client, alias, r["query"], date.today(), K, mode="bm25", score_floor=0.0, answerability=False)],
        "vector": lambda r: [h.chunk_ids for h in retrieve(client, alias, r["query"], date.today(), K, mode="vector", score_floor=0.0, answerability=False)],
        "hybrid (BM25+벡터)": lambda r: [h.chunk_ids for h in retrieve(client, alias, r["query"], date.today(), K, mode="hybrid", score_floor=0.0, answerability=False)],
        "SPLADE": lambda r: window({"splade": trim(splade(r["qid"]), TRIM["splade"])}, parent),
        "SPLADE+벡터": lambda r: window({"splade": trim(splade(r["qid"]), TRIM["splade"]),
                                         "vector": trim(dense(r["query"]), TRIM["vector"])}, parent),
    }
    print(f"{len(rows)}문항, 상위 {K}문서 창, 문서당 최대 {PER_DOC}청크\n")
    print("| 방식 | 근거 Recall(청크) | 근거 Precision(청크, 하한) | 그 창의 최대 | 문서 Precision | 문서 Hit | 평균 청크 수 |\n|---|---|---|---|---|---|---|")
    misses = {}
    for name, run in systems.items():
        found = doc_hit = 0
        cp, dp, ceil, sizes = [], [], [], []
        for row in rows:
            groups = run(row)
            flat = [c for g in groups for c in g]
            gold = set(row["evidence_groups"][0])
            found += bool(gold & set(flat))
            docs = [g[0].split("#")[0] for g in groups if g]
            doc_hit += bool(set(docs) & set(row["gold"]))
            n = len(flat)
            sizes.append(n)
            cp.append(sum(c in gold for c in flat) / n if n else 0.0)
            ceil.append(min(len(gold), n) / n if n else 0.0)
            dp.append(sum(d in row["gold"] for d in docs) / len(docs) if docs else 0.0)
            if not gold & set(flat):
                misses.setdefault(name, []).append(f"{row['qid']} {row['query']}")
        n = len(rows)
        print(f"| {name} | {found}/{n} = {found / n:.3f} | {sum(cp) / n:.3f} | {sum(ceil) / n:.3f} | {sum(dp) / n:.3f} | {doc_hit}/{n} | {sum(sizes) / n:.1f} |")
    for name in ("SPLADE", "SPLADE+벡터"):
        print(f"\n[{name}] 근거 청크를 못 찾은 질문")
        for line in misses.get(name, []):
            print("  " + line)


if __name__ == "__main__":
    main(sys.argv[1])
