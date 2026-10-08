"""탐색기 법령 표의 문서 단위 지표를 results.json에서 구해 categories.js 질문 행에 붙인다.

청크 지표와 같은 규칙을 문서에 옮긴 것이다.
- dr: 원순위(청크 순위에서 같은 문서를 처음 나온 자리로 합친 문서 순위) 안에서 모든 근거 요건의 문서가 충족되는 순위. 상위 5문서 밖이면 null.
- dq: 컷오프를 거친 반환 청크가 속한 문서 중 정답 라벨 문서의 비율.
순서는 [SPLADE, dense, hybrid]. build_explorer_law100.py로 데이터를 다시 만들면 이 스크립트를 이어서 돌린다.
법령은 results.json에서, 행정·민원FAQ는 같은 검색(SPLADE 100, dense 50, 후보 각 25개 청크 RRF k=60, 서비스 반환)을
클러스터에서 다시 돌려 구한다. 청크 순위가 탐색기의 r과 하나라도 다르면 멈춘다.
"""
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(os.environ.get("RESULTS_FILE", ROOT / "data/generated/law150-2026-10-07/results.json"))
CAT = ROOT / "docs/presentation/question_explorer/data/categories.js"
MODES = ("splade", "dense", "hybrid")


def parent(chunk_id: str) -> str:
    return chunk_id.split("#")[0]


def first(rank_of: dict, groups) -> int | None:
    ranks = [min((rank_of[x] for x in g if x in rank_of), default=None) for g in groups]
    return max(ranks) if ranks and all(r is not None for r in ranks) else None


LIVE = {"admin30": ("data/queries_admin_v1.jsonl", "search_admin_alias"), "faq30": ("data/queries_faq_v2.jsonl", "search_faqexp_alias")}
AS_OF = date.fromisoformat(os.environ.get("AS_OF", "2026-10-06"))
MISMATCH: list = []
RATIOS = {"splade": 0.80, "dense": 0.93}


def live_rows(key: str, rows: list[dict]) -> None:
    sys.path.insert(0, str(ROOT / "scripts/law"))
    from build_explorer_law100 import RRF_K, single_window  # noqa: E402
    from search_engine.client import create_client
    from search_engine.config import get_settings
    from search_engine.embeddings import OllamaEmbedder
    from search_engine.search import query as retrieval
    from search_engine.search.query import build_splade_query, build_vector_query
    from search_engine.sparse import SparseEncoder

    qfile, alias_setting = LIVE[key]
    qfile = os.environ.get(f"QUERIES_{key.upper()}", qfile)  # 탐색기가 만들어진 뒤 질문 파일이 바뀌었으면 그때 판을 지정한다
    settings = get_settings()
    settings.search_chunk_filter = False
    settings.search_answerability_judge = False
    object.__setattr__(settings, "search_faqexp_alias", "exp-faq-splade")  # build_faq_experiment_index.py가 만든 색인
    client = create_client(settings)
    index = list(client.indices.get_alias(name=getattr(settings, alias_setting)))[0]
    questions = {json.loads(l)["qid"][-3:]: json.loads(l) for l in (ROOT / qfile).read_text().splitlines() if l.strip()}
    texts = [q["query"].strip() for q in questions.values()]
    vectors = dict(zip(texts, OllamaEmbedder(settings).embed(texts)))
    encoder = SparseEncoder(settings)
    sparse = dict(zip(texts, encoder.encode(texts, settings.search_splade_query_max_length)))
    retrieval.encode_sparse_query = lambda q: sparse[q]

    class Frozen:
        def embed_query(self, q):
            return vectors[q.strip()]

    for row in rows:
        q = questions[row["i"]]
        text = q["query"].strip()
        assert q["query"] == row["q"], row["i"]
        gold = set(q["gold"])
        chunk_groups = q["evidence_groups"]
        doc_groups = [{parent(c) for c in g} for g in chunk_groups]
        sp = client.search(index=index, body={"query": build_splade_query(sparse[text], AS_OF, text)}, size=100,
                           _source=["title", "parent_id", "splade"])["hits"]["hits"]
        dn = client.search(index=index, body={"query": build_vector_query(vectors[text], AS_OF, 50, text)}, size=50,
                           _source=["title", "parent_id"])["hits"]["hits"]
        sp_rank = {h["_id"]: i for i, h in enumerate(sp, 1)}
        dn_rank = {h["_id"]: i for i, h in enumerate(dn, 1)}
        fused: dict[str, float] = {}
        for ranks in (sp_rank, dn_rank):
            for cid, r in ranks.items():
                if r <= 25:
                    fused[cid] = fused.get(cid, 0.0) + 1 / (RRF_K + r)
        order = sorted(fused, key=lambda c: (-fused[c], dn_rank[c] if dn_rank.get(c, 10**6) <= 25 else 10**6, c))
        rankings = [[h["_id"] for h in sp], [h["_id"] for h in dn], order]
        hits = retrieval.retrieve(client, index, q["query"], AS_OF, 5, Frozen(), mode="hybrid", lexical="splade",
                                  chunk_first=True, chunk_first_cutoff_ratio=settings.search_category_cutoff_ratio,
                                  score_floor=0.0, answerability=False, rerank_chunks=False, query_rewrite=False, strict=True)
        windows = []
        for hits_, ratio in ((sp, RATIOS["splade"]), (dn, RATIOS["dense"])):
            status = single_window(hits_, ratio)
            windows.append([h["_source"]["parent_id"] for h in hits_ if status[h["_id"]] == "keep"])
        windows.append([h.parent_id for h in hits])
        dr, dq = [], []
        for i, ranking in enumerate(rankings):
            r = first({c: n for n, c in enumerate(ranking, 1)}, chunk_groups)
            if (r if r is not None and r <= 5 else None) != row["r"][i]:
                MISMATCH.append((key, row["i"], ("splade", "dense", "hybrid")[i], r, row["r"][i]))
            docs = list(dict.fromkeys(parent(c) for c in ranking))
            d = first({x: n for n, x in enumerate(docs, 1)}, doc_groups)
            dr.append(d if d is not None and d <= 5 else None)
            returned = list(dict.fromkeys(windows[i]))
            dq.append(round(sum(x in gold for x in returned) / len(returned), 4) if returned else 0.0)
        row["dr"], row["dq"] = dr, dq


def main() -> None:
    results = json.loads(RESULTS.read_text(encoding="utf-8"))["results"]
    text = CAT.read_text(encoding="utf-8")
    m = re.search(r"var CATD=(\{.*\});\s*$", text, re.S)
    catd = json.loads(m.group(1))
    for row in catd["law100"]:
        res = results[row["i"]]
        q = res["question"]
        gold = set(q["gold"])
        chunk_groups = q["evidence_groups"]
        doc_groups = [{parent(c) for c in g} for g in chunk_groups]
        dr, dq = [], []
        for mode in MODES:
            raw = [c[0] for c in res[mode]["raw"]]
            chunk_rank = {c: i for i, c in enumerate(raw, 1)}
            # 청크 규칙 재현 확인: 탐색기의 r과 같아야 한다
            r = first(chunk_rank, chunk_groups)
            assert (r if r is not None and r <= 5 else None) == row["r"][MODES.index(mode)], (row["i"], mode)
            docs = list(dict.fromkeys(parent(c) for c in raw))
            doc_rank = {d: i for i, d in enumerate(docs, 1)}
            d = first(doc_rank, doc_groups)
            dr.append(d if d is not None and d <= 5 else None)
            returned = list(dict.fromkeys(parent(c) for c in res[mode]["window"]))
            dq.append(round(sum(d in gold for d in returned) / len(returned), 4) if returned else 0.0)
        row["dr"], row["dq"] = dr, dq
    for key in os.environ.get("LIVE_KEYS", ",".join(LIVE)).split(","):
        live_rows(key, catd[key])
        print(key, "rows:", len(catd[key]))
    print("청크 순위 불일치(키, 질문, 방식, 지금, 탐색기):", MISMATCH)
    head = text[: m.start()]
    CAT.write_text(f"{head}var CATD={json.dumps(catd, ensure_ascii=False, separators=(',', ':'))};\n", encoding="utf-8")
    print("law rows:", len(catd["law100"]))


if __name__ == "__main__":
    main()
