"""개발 5문항: 출처 설명을 어떻게 다루면 정답의 BM25·벡터 부모 순위가 어떻게 바뀌는가."""
import json, re, sys, copy
from datetime import date

sys.path.insert(0, "/Users/jeongbin/git/searchEngine")
from opensearchpy import OpenSearch
from search_engine.config import get_settings
from search_engine.search import query as Q
from search_engine.embeddings import OllamaEmbedder

S = get_settings()
c = OpenSearch(S.opensearch_url)
emb = OllamaEmbedder(S)
AS = date(2026, 9, 25)
SOURCE = re.compile(
    r"^\s*((?:19|20)\d{2}년[^?]{0,40}?(?:자료|세미나|기사|문답|보고서|발표|설명|공지|공고|안내|뉴스레터|기고|교육"
    r"|책자|원문|서식|양식|신청서|확약서|조서|보도자료|명단|사례|토론|워크숍|설명회|연재|요령|기준|목차)"
    r"[^?]{0,20}?에서(?:는)?)[,\s]+(.+)$")


def split(q):
    m = SOURCE.match(q)
    return (m.group(1), m.group(2)) if m else (None, q)


def lexical(query, variant):
    body = Q.build_query(query, AS)
    source, content = split(query)
    if not source or variant == "base":
        return body
    inner = body["function_score"]["query"]["bool"]
    mm = inner["should"][0]["multi_match"]
    content_mm = {"multi_match": {**mm, "query": content}}
    if variant == "drop":
        inner["should"] = [content_mm]
    elif variant == "body":
        inner["should"] = [content_mm, {"multi_match": {"query": source, "type": "most_fields",
                                                        "fields": ["body", "body.standard^0.5"]}}]
    elif variant.startswith("w"):
        w = float(variant[1:])
        inner["should"] = [content_mm, {"multi_match": {**mm, "query": source, "boost": w}}]
    return body


def prank(hits, gp):
    seen = []
    for h in hits:
        p = h["_source"]["parent_id"]
        if p not in seen:
            seen.append(p)
        if p in gp:
            return len(seen)
    return None


if __name__ == "__main__":
    R = "/Users/jeongbin/git/searchEngine/data/generated/holdout-v1/results/"
    qs = {q["qid"]: q for f in ["mixed-title1-dfs-top5-audited.json", "holdout-title1-dfs-top5-audited.json"]
          for q in json.load(open(R + f))["queries"]}
    for t in ["docs-v2-097", "docs-v2-101", "docs-v2-103", "docs-v2-104", "docs-v2-106", "holdout-v1-037"]:
        q = qs[t]
        alias = "search-holdout" if t.startswith("holdout") else "search-holdout,search-docs-only"
        opts = {"search_type": "dfs_query_then_fetch"} if "," in alias else {}
        gp = {x.split("#")[0] for g in q["evidence_groups"] for x in g}
        src, content = split(q["query"])
        print("=====", t, "| source:", src)
        row = []
        for v in ("base", "drop", "body", "w0.5", "w0.3"):
            hits = c.search(index=alias, body={"query": lexical(q["query"], v)}, size=300, **opts)["hits"]["hits"]
            row.append(f"{v}={prank(hits, gp)}")
        for name, text in (("vec-full", q["query"]), ("vec-content", content)):
            hits = c.search(index=alias, body={"query": Q.build_vector_query(emb.embed_query(text), AS, 300, text)},
                            size=300)["hits"]["hits"]
            row.append(f"{name}={prank(hits, gp)}")
        print("   bm25 parent rank:", " ".join(row))
