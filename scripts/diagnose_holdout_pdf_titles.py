"""PDF 재청킹 후 검색이 나빠진 원인이 청크 제목의 섹션 제목 접미사인지 가른다.

`compare_holdout_pdf_rechunk.py`의 new 색인과 **본문·벡터가 같고**, 검색용 `title` 필드에서만
` — 섹션 제목` 접미사를 뗀 변형(new_basetitle)을 만들어 old / new / new_basetitle을 같은 질의로 잰다.
벡터는 원래 제목이 들어간 임베딩 그대로라 어휘 검색(BM25 안의 제목 필드)만 바뀐다.
new_basetitle이 old 쪽으로 돌아오면 원인은 제목 오염이고, 그대로면 청크 크기·개수 쪽이다.
서비스 alias는 건드리지 않고 임시 색인은 끝에 지운다.
"""

import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from opensearchpy.helpers import scan, streaming_bulk

sys.path.insert(0, str(Path(__file__).parent))
from compare_holdout_pdf_rechunk import (  # noqa: E402
    BASE, CORE, MODES, QUERIES, K, FixedQueryEmbedder, available, grade, norm, read)
from search_engine.client import create_client  # noqa: E402
from search_engine.config import get_settings  # noqa: E402
from search_engine.embeddings import embedding_text  # noqa: E402
from search_engine.indexing.documents import SearchDocument  # noqa: E402
from search_engine.search.query import retrieve  # noqa: E402
import hashlib  # noqa: E402

OUT = BASE / "compare"


def main() -> None:
    settings = get_settings().model_copy(update={
        "search_chunk_filter": False, "search_answerability_judge": False,
        "search_rerank_chunks": False, "search_query_rewrite": False})
    client = create_client(settings)
    old_index = list(client.indices.get_alias(name="search-holdout"))[0]
    old_count = client.count(index=old_index)["count"]
    pdf_parents = {r["parent_id"] for r in read(CORE) if (r.get("source_path") or "").lower().endswith(".pdf")}
    model = settings.ollama_embedding_model
    vectors = {r["key"]: r["vector"] for r in read(OUT / "embedding_cache.jsonl")}

    def key(text):
        return hashlib.sha256((model + "\n" + text).encode()).hexdigest()

    keep, old_pdf = [], []
    for hit in scan(client, index=old_index, query={"query": {"match_all": {}}}, size=1000):
        (old_pdf if hit["_source"]["parent_id"] in pdf_parents else keep).append(hit)
    vectors.update({key(embedding_text(h["_source"]["title"], h["_source"]["body"])): h["_source"]["embedding"]
                    for h in old_pdf})
    new_docs = [SearchDocument.model_validate(r).index_source() for r in read(BASE / "new" / "pdf_chunks.jsonl")]
    for r in new_docs:
        r["embedding"] = vectors[key(embedding_text(r["title"], r["body"]))]
    base_title = {}
    for h in old_pdf:
        base_title.setdefault(h["_source"]["parent_id"], h["_source"]["title"].split(" — ")[0])
    stripped = [{**r, "title": base_title.get(r["parent_id"], r["title"].split(" — ")[0])} for r in new_docs]

    questions = read(QUERIES)
    q_vectors = {q["qid"]: vectors[key(q["query"])] for q in questions}
    source_settings = client.indices.get_settings(index=old_index)[old_index]["settings"]["index"]
    index_settings = {k: source_settings[k] for k in ["analysis", "number_of_shards", "number_of_replicas", "knn"]}
    mapping = client.indices.get_mapping(index=old_index)[old_index]["mappings"]
    created, results = [], []
    try:
        arms = {"old": old_index}
        for name, docs in (("new", new_docs), ("new_basetitle", stripped)):
            index = f"holdout-title-diag-{uuid4().hex[:10]}-{name.replace('_', '-')}"
            client.indices.create(index=index, body={"settings": index_settings, "mappings": mapping})
            created.append(index)
            actions = [{"_index": index, "_id": h["_id"], "_source": h["_source"]} for h in keep]
            actions += [{"_index": index, "_id": r["id"], "_source": r} for r in docs]
            for ok, _ in streaming_bulk(client, actions, chunk_size=500, raise_on_error=True):
                assert ok
            client.indices.refresh(index=index)
            arms[name] = index
            print(f"{name}: {index} 색인 완료", flush=True)
        for arm, index in arms.items():
            for mode in MODES:
                for q in questions:
                    with patch("search_engine.search.query.get_settings", return_value=settings):
                        hits = retrieve(client, index, q["query"], date.today(), K,
                                        embedder=FixedQueryEmbedder(q_vectors[q["qid"]]), mode=mode,
                                        strict=True, answerability=False, query_rewrite=False,
                                        rerank_chunks=False)
                    gold_parents = {c.split("#")[0] for g in q["evidence_groups"] for c in g}
                    results.append({"arm": arm, "mode": mode, "qid": q["qid"], **grade(q, hits, pdf_parents),
                                    "touches_pdf": bool({p for g in q["gold_groups"] for p in g} & pdf_parents
                                                        or gold_parents & pdf_parents),
                                    "pdf_only_evidence": gold_parents <= pdf_parents})
                print(f"{arm} {mode} 완료", flush=True)
    finally:
        for index in created:
            client.indices.delete(index=index)
        assert list(client.indices.get_alias(name="search-holdout")) == [old_index]
        assert client.count(index=old_index)["count"] == old_count
        print("임시 색인 삭제, alias·청크 수 그대로", flush=True)

    (OUT / "title_diag_results.json").write_text(json.dumps(results, ensure_ascii=False), encoding="utf-8")
    scopes = {"전체 69": lambda r: True, "PDF 관련": lambda r: r["touches_pdf"],
              "근거 전부 PDF": lambda r: r["pdf_only_evidence"]}
    lines = ["| 범위 | 검색 | 버전 | n | 근거 Recall@5 | 문서 P@1 | Hit@5 | MRR@5 |", "|---|---|---|---:|---:|---:|---:|---:|"]
    for scope, pred in scopes.items():
        for mode in MODES:
            for arm in arms:
                rows = [r for r in results if r["arm"] == arm and r["mode"] == mode and pred(r)]
                m = lambda f: sum(r[f] for r in rows) / len(rows)  # noqa: E731
                lines.append(f"| {scope} | {mode} | {arm} | {len(rows)} | {m('evidence_recall'):.3f} | "
                             f"{m('document_p1'):.3f} | {m('document_hit_at_5'):.3f} | {m('mrr_at_5'):.3f} |")
    (OUT / "title_diag.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
