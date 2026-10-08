"""법령·고시 질문별 검색 결과와 평가 trace를 탐색기에 반영한다.

법령 URL 키 law100은 기존 링크 호환을 위해 유지한다. QUERIES_FILE로
질문 파일을 지정할 수 있으며, 기본은 law150 질문 파일(없으면 기존 law100)이다.
행정·FAQ 데이터는 보존한다. 원순위는 SPLADE 100, dense 50, 합산은 각 25개
후보의 청크 RRF k=60이다. 모든 근거 요건을 충족한 순위를 기록한다.
이후 attribute_dense.py와 attribute_explorer_gold.py로 영향도를 채운다.
"""
import json
import os
import subprocess
from datetime import date
from pathlib import Path

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search import query as retrieval
from search_engine.search.query import build_splade_query, build_vector_query
from search_engine.sparse import SparseEncoder

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / "docs/presentation/question_explorer/data"
DEFAULT_QUERIES = ROOT / "data/queries_law150_v1.jsonl"
if not DEFAULT_QUERIES.exists():
    DEFAULT_QUERIES = ROOT / "data/generated/explorer-law100-2026-10-07/queries_law100_rechunk.jsonl"
QUERIES = Path(os.environ.get("QUERIES_FILE", DEFAULT_QUERIES))
SOURCE = Path(get_settings().search_law_source)
AS_OF = date.fromisoformat(os.environ.get("AS_OF", "2026-10-07" if "law150" in QUERIES.name else "2026-10-06"))
RRF_K = 60
CAT = {"natural": "일상어", "identifier": "식별자", "annex": "별표", "compare": "신구대비", "table": "표·서식"}
SP_RATIO, DN_RATIO, HY_RATIO = 0.80, 0.93, 0.95
MAX_CHUNKS, MAX_DOCS, PER_DOC = 10, 5, 6


def doc_title(chunk_title: str) -> str:
    return chunk_title.split(" — ")[0]


def single_window(hits: list[dict], ratio: float) -> dict[str, str]:
    """단독 모드의 청크 컷오프(1위 점수 대비 비율, 청크 10·문서 5·문서당 6)에서 청크마다 결과를 정한다."""
    top = hits[0]["_score"] if hits else 0
    status, docs, per, kept = {}, [], {}, 0
    for hit in hits:
        cid, parent = hit["_id"], hit["_source"]["parent_id"]
        if kept and hit["_score"] < top * ratio:
            status[cid] = "cut"
        elif parent not in docs and len(docs) == MAX_DOCS:
            status[cid] = "docs"
        elif per.get(parent, 0) == PER_DOC:
            status[cid] = "perdoc"
        elif kept == MAX_CHUNKS:
            status[cid] = "budget"
        else:
            status[cid] = "keep"
            kept += 1
            per[parent] = per.get(parent, 0) + 1
            if parent not in docs:
                docs.append(parent)
    return status


def main() -> None:
    settings = get_settings()
    settings.search_chunk_filter = False
    settings.search_answerability_judge = False
    client = create_client(settings)
    index = list(client.indices.get_alias(name="search-law"))[0]
    questions = [json.loads(line) for line in QUERIES.read_text().splitlines() if line.strip()]
    texts = [q["query"].strip() for q in questions]
    embedder = OllamaEmbedder(settings)
    encoder = SparseEncoder(settings)
    vectors = dict(zip(texts, embedder.embed(texts)))
    sparse = dict(zip(texts, encoder.encode(texts, settings.search_splade_query_max_length)))
    retrieval.encode_sparse_query = lambda q: sparse[q]
    tok = encoder._tokenizer

    def word(term: str) -> str:
        return tok.convert_ids_to_tokens(int(term[1:])).replace("##", "").replace("▁", "")

    class Frozen:
        def embed_query(self, q):
            return vectors[q.strip()]

    detail, rows, bodies, evaluations = {}, [], {}, {}
    for q in questions:
        text = q["query"].strip()
        gold = {c for g in q["evidence_groups"] for c in g}
        gold_docs = set(q["gold"])
        terms = sparse[text]
        sp = client.search(index=index, body={"query": build_splade_query(terms, AS_OF, text)},
                           size=100, _source=["title", "parent_id", "splade"])["hits"]["hits"]
        dn = client.search(index=index, body={"query": build_vector_query(vectors[text], AS_OF, 50, text)},
                           size=50, _source=["title", "parent_id"])["hits"]["hits"]
        sp_rank = {h["_id"]: i for i, h in enumerate(sp, 1)}
        dn_rank = {h["_id"]: i for i, h in enumerate(dn, 1)}
        info = {h["_id"]: h["_source"] for h in sp + dn}

        # 합산: 서비스 경로의 후보 수(각 25)
        fused: dict[str, float] = {}
        for ranks in (sp_rank, dn_rank):
            for cid, r in ranks.items():
                if r <= 25:
                    fused[cid] = fused.get(cid, 0.0) + 1 / (RRF_K + r)
        order = sorted(fused, key=lambda c: (-fused[c], dn_rank.get(c, 10**6) if dn_rank.get(c, 10**6) <= 25 else 10**6, c))
        ftop = fused[order[0]]
        floor = ftop * HY_RATIO
        fused_rank = {c: i for i, c in enumerate(order, 1)}

        def first(rank_map):
            ranks = [min((rank_map[c] for c in group if c in rank_map), default=None) for group in q["evidence_groups"]]
            return max(ranks) if ranks and all(r is not None for r in ranks) else None
        gr = [first(sp_rank), first(dn_rank), first(fused_rank)]

        # 서비스 반환
        hits = retrieval.retrieve(client, index, q["query"], AS_OF, 5, Frozen(), mode="hybrid", lexical="splade",
                                  chunk_first=True, chunk_first_cutoff_ratio=settings.search_category_cutoff_ratio,
                                  score_floor=0.0, answerability=False, rerank_chunks=False, query_rewrite=False, strict=True)
        returned = [(h, list(h.chunk_ids)) for h in hits]
        kept_ids = {c for _, ids in returned for c in ids}
        need = [c for c in kept_ids if c not in info]
        if need:
            for h in client.search(index=index, body={"query": {"ids": {"values": need}}}, size=len(need),
                                   _source=["title", "parent_id"])["hits"]["hits"]:
                info[h["_id"]] = h["_source"]

        leaders = {sp[0]["_id"] if sp else None, dn[0]["_id"] if dn else None}
        kept_docs = {info[c]["parent_id"] for c in kept_ids}
        cr = []
        for cid in order[:max(8, min(len(order), len(kept_ids) + 4))]:
            below = fused[cid] < floor
            if cid in kept_ids:
                st = "keep"
            elif below and cid not in leaders:
                st = "cut"
            elif info[cid]["parent_id"] not in kept_docs and len(kept_docs) >= MAX_DOCS:
                st = "docs"
            elif sum(info[c]["parent_id"] == info[cid]["parent_id"] for c in kept_ids) >= PER_DOC:
                st = "perdoc"
            else:
                st = "budget"
            cr.append([cid, sp_rank.get(cid, 0) if sp_rank.get(cid, 101) <= 25 else 0,
                       dn_rank.get(cid, 0) if dn_rank.get(cid, 51) <= 25 else 0,
                       round(fused[cid], 4), int(cid in leaders), int(below), st, int(cid in gold)])
        ret = [{"t": doc_title(h.title), "g": int(h.parent_id in gold_docs),
                "ch": [[c, sp_rank.get(c, 0), dn_rank.get(c, 0), int(c in gold), 2 if c in gold else 0] for c in ids]}
               for h, ids in returned]

        def side(hits_, ratio, unit):
            status = single_window(hits_, ratio)
            top = hits_[0]["_score"] if hits_ else 0
            docs, seen = [], {}
            for h in hits_:
                p = h["_source"]["parent_id"]
                if p not in seen:
                    seen[p] = len(docs)
                    docs.append([doc_title(h["_source"]["title"]), len(docs) + 1, round(h["_score"], 4), 0, int(p in gold_docs)])
            for r in docs:
                r[3] = int(r[1] <= 5) if unit == 2 else int(r[2] >= 0.97 * docs[0][2])
            kept = [h["_id"] for h in hits_ if status[h["_id"]] == "keep"]
            groups: dict[str, list] = {}
            for c in kept:
                groups.setdefault(info[c]["parent_id"], []).append([c, int(c in gold), 2 if c in gold else 0])
            shown = max(6, min(len(hits_), len(kept) + 3, 15))
            crs = [[h["_id"], i, round(h["_score"], unit + 2), status[h["_id"]], int(h["_id"] in gold)]
                   for i, h in enumerate(hits_[:shown], 1)]
            return {"rows": docs[:6], "top": round(docs[0][2], 4) if docs else 0, "n": len(gold),
                    "tot": len(kept), "ret": list(groups.values()), "cr": crs, "ratio": ratio,
                    "ctop": round(top, unit + 2)}

        # 단독 모드 컷오프는 청크 점수에 건다. SPLADE는 소수 둘째, dense는 소수 셋째 자리까지 보인다.
        fx = {"sp": side(sp, SP_RATIO, 2), "dn": side(dn, DN_RATIO, 3), "floor": round(floor, 4),
              "top": round(ftop, 4), "nf": len(fused), "ret": ret, "gd": gr[2] or 0, "cr": cr}

        def contrib(h):
            dw = h["_source"].get("splade") or {}
            t = sorted(((word(k), round(w * dw[k], 2)) for k, w in terms.items() if k in dw), key=lambda x: -x[1])
            return [list(x) for x in t[:5]]
        top5 = lambda lst: lst[:5]
        d = {
            "qt": [[word(k), round(w, 2)] for k, w in sorted(terms.items(), key=lambda x: -x[1])[:24]],
            "nq": len(terms),
            "sp": [{"c": h["_id"], "s": round(h["_score"], 2), "t": contrib(h), **({"g": 1} if h["_id"] in gold else {})} for h in top5(sp)],
            "dn": [{"c": h["_id"], "s": round(h["_score"], 4), **({"g": 1} if h["_id"] in gold else {})} for h in top5(dn)],
            "hy": [{"c": c, "s": round(fused[c], 4), "a": sp_rank.get(c, 0) if sp_rank.get(c, 101) <= 25 else 0,
                    "b": dn_rank.get(c, 0) if dn_rank.get(c, 51) <= 25 else 0, **({"g": 1} if c in gold else {})} for c in top5(order)],
            "gr": gr,
            "gc": sorted(gold, key=lambda c: (min(sp_rank.get(c, 10**6), dn_rank.get(c, 10**6)), c)),
            "fx": fx,
            "gold_ranks": {c: [sp_rank.get(c), dn_rank.get(c), fused_rank.get(c)] for c in gold},
            "evidence_groups": q["evidence_groups"],
        }
        if q.get("label_review"):
            d["label_review"] = q["label_review"]
        if q.get("positive_review"):
            d["positive_review"] = q["positive_review"]
        qid = q["qid"][-3:]
        detail[qid] = d
        rows.append({"i": qid, "c": CAT[q["category"]], "q": q["query"], "n": len(gold),
                     "eligible": q.get("positive_review", {}).get("evaluation_eligible", True),
                     "r": [g if g is not None and g <= 5 else None for g in gr]})
        for c in {x["c"] for k in ("sp", "dn", "hy") for x in d[k]} | set(d["gc"]) | {c for c in kept_ids} | \
                {r[0] for r in fx["sp"]["cr"]} | {r[0] for r in fx["dn"]["cr"]} | {r[0] for r in cr}:
            bodies[c] = None
        evaluations[qid] = {"question": q,
            "splade": {"raw": [[h["_id"], h["_score"]] for h in sp], "window": [h["_id"] for h in sp if single_window(sp, SP_RATIO)[h["_id"]] == "keep"]},
            "dense": {"raw": [[h["_id"], h["_score"]] for h in dn], "window": [h["_id"] for h in dn if single_window(dn, DN_RATIO)[h["_id"]] == "keep"]},
            "hybrid": {"raw": [[c, fused[c]] for c in order], "window": [c for _, ids in returned for c in ids]}}
        print(qid, gr, flush=True)

    # 청크 본문
    for line in SOURCE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec["id"] in bodies:
                bodies[rec["id"]] = [rec["title"], rec["body"]]
    missing = [c for c, v in bodies.items() if v is None]
    assert not missing, missing[:3]

    if os.environ.get("RESULTS_FILE"):
        result = {"index": index, "as_of": AS_OF.isoformat(), "questions_file": str(QUERIES),
                  "settings": {"splade_model": settings.search_splade_model, "dense_model": settings.ollama_embedding_model,
                  "splade_heading_path": settings.search_splade_include_heading_path, "dense_heading_path": settings.search_dense_include_heading_path,
                  "ratios": [SP_RATIO, DN_RATIO, settings.search_category_cutoff_ratio], "rrf_k": RRF_K,
                  "candidates": [25,25], "max_chunks": MAX_CHUNKS, "max_docs": MAX_DOCS, "per_doc": PER_DOC},
                  "results": evaluations}
        Path(os.environ["RESULTS_FILE"]).write_text(json.dumps(result, ensure_ascii=False, indent=2))

    # 기존 파일을 읽어 법령 항목만 바꾼다
    js = ("const fs=require('fs'),vm=require('vm');const c={};vm.createContext(c);"
          "for(const f of ['categories','category-detail'])vm.runInContext(fs.readFileSync('%s/'+f+'.js','utf8'),c);"
          "console.log(JSON.stringify({CATD:vm.runInContext('CATD',c),CATH:vm.runInContext('CATH',c),CATB:vm.runInContext('CATB',c)}))") % EXP
    old = json.loads(subprocess.check_output(["node", "-e", js]))
    catd = {"law100": rows, **{k: v for k, v in old["CATD"].items() if k not in ("law50", "law100")}}
    cath = {"law100": detail, **{k: v for k, v in old["CATH"].items() if k not in ("law50", "law100")}}
    catb = {**{k: v for k, v in old["CATB"].items() if not k.startswith("01_")}, **bodies}
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    cat_head = f"/* 카테고리 질문: 법령 {len(rows)}문항·행정 30·FAQ 30. r은 상위 5청크에서 모든 근거 요건을 충족하는 순위. 법령 기준일 {AS_OF.isoformat()}. */"
    det_head = f"/* 검색 후보·컷오프·반환·근거 그룹·영향도. 법령 라벨 Precision 하한, 행정·FAQ Sonnet 판정. 법령 기준일 {AS_OF.isoformat()}, 나머지 2026-10-06. */"
    (EXP / "categories.js").write_text(f"{cat_head}\nvar CATD={dump(catd)};\n", encoding="utf-8")
    (EXP / "category-detail.js").write_text(f"{det_head}\nvar CATH={dump(cath)};\nvar CATB={dump(catb)};\n", encoding="utf-8")
    print("law questions:", len(rows), "chunks in CATB:", len(catb))


if __name__ == "__main__":
    main()
