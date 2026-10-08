"""정답 청크를 못 싣는 이유가 청킹인지 검색인지 가른다. 질문마다 정답 청크의 순위를 검색기별로 전체 청크 순위에서 읽는다.

    .venv/bin/python scripts/law/diagnose_misses.py SPLADE_JSON
"""

import json
import sys
from datetime import date
from pathlib import Path

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search.query import build_query, build_vector_query

from category import QUERIES, alias as category_alias, source as category_source  # noqa: E402
RRF_K = 60


def rank_of(ranked: list[str], gold: set[str]) -> int | None:
    return next((i for i, c in enumerate(ranked, 1) if c in gold), None)


def main(splade_file: str) -> None:
    sp = json.loads(Path(splade_file).read_text())
    rows = [json.loads(line) for line in QUERIES.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [q for q in rows if q.get("positive_review", {}).get("evaluation_eligible", True)]
    chunks = {json.loads(line)["id"]: json.loads(line) for line in
              Path(category_source(get_settings())).read_text(encoding="utf-8").splitlines() if line.strip()}
    settings = get_settings()
    client, embedder = create_client(settings), OllamaEmbedder(settings)
    alias = category_alias(settings)
    inverted: dict[str, list] = {}
    for cid, vec in sp["docs"].items():
        for token, weight in vec.items():
            inverted.setdefault(token, []).append((cid, weight))
    total = len(chunks)

    out = []
    for row in rows:
        gold = set(row["evidence_groups"][0])
        q = row["query"]
        bm = [h["_id"] for h in client.search(index=alias, body={"query": build_query(q, date.today())},
                                              size=total, _source=False)["hits"]["hits"]]
        de = [h["_id"] for h in client.search(index=alias, body={"query": build_vector_query(
            embedder.embed_query(q), date.today(), total, q)}, size=total, _source=False)["hits"]["hits"]]
        scores: dict[str, float] = {}
        for token, qw in sp["queries"][row["qid"]].items():
            for cid, dw in inverted.get(token, ()):
                scores[cid] = scores.get(cid, 0.0) + qw * dw
        sl = [c for c, _ in sorted(scores.items(), key=lambda x: -x[1])]
        fused: dict[str, float] = {}
        for ranked in (sl, de):
            for r, cid in enumerate(ranked, 1):
                fused[cid] = fused.get(cid, 0.0) + 1 / (RRF_K + r)
        fu = sorted(fused, key=lambda c: -fused[c])
        # 정답 문서 순위: 문서의 최고 청크 순위로 매긴다.
        def doc_rank(ranked):
            docs = []
            for c in ranked:
                p = c.split("#")[0]
                if p not in docs:
                    docs.append(p)
            return next((i for i, p in enumerate(docs, 1) if p in row["gold"]), None)
        best = min((chunks[c] for c in gold), key=lambda c: len(c["body"]))
        out.append({
            "qid": row["qid"], "query": q, "gold_chunks": len(gold),
            "len": len(best["body"]), "heading": " > ".join(best["heading_path"])[:40],
            "bm25": rank_of(bm, gold), "dense": rank_of(de, gold), "splade": rank_of(sl, gold),
            "fused": rank_of(fu, gold), "doc_rank_fused": doc_rank(fu), "doc_rank_dense": doc_rank(de),
            "body": best["body"][:140].replace("\n", " "),
        })
    print("| 질문 | 정답 청크 길이 | 정답 청크 수 | BM25 | dense | SPLADE | SPLADE+dense | 정답 문서 순위(SPLADE+dense) |\n|---|---|---|---|---|---|---|---|")
    for o in out:
        print(f"| {o['qid'][-3:]} {o['query'][:28]} | {o['len']} | {o['gold_chunks']} | {o['bm25'] or '-'} | {o['dense'] or '-'} | {o['splade'] or '-'} | {o['fused'] or '-'} | {o['doc_rank_fused'] or '-'} |")
    json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False) if len(sys.argv) > 2 else None


if __name__ == "__main__":
    main(sys.argv[1])
