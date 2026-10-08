"""카테고리 검색(hybrid: SPLADE + dense, 청크 RRF)을 여러 청킹의 인덱스에서 같은 질문으로 돌려 비교한다.

정답 청크는 청킹이 달라지면 ID도 달라지므로, 질문의 필수 구절(`phrases`)로 *각 인덱스에서 다시 정한다*: 정답 문서(`gold`)의 청크 중
필수 구절을 모두 담은 청크(검토된 범위 제약 `evidence_validation` 적용). 질문 라벨이 청크를 따라오는 방식은 `evaluate_law.py`와 같다.
서비스 경로(`retrieve`, chunk_first)를 그대로 쓰고 컷오프는 서비스 설정과 이전 기준(0.95)을 함께 낸다.

    .venv/bin/python scripts/chunking/eval_category_chunking.py --queries data/queries_law150_v1.jsonl \\
        --arm old=exp-chk-law-old --arm port=exp-chk-law-port --arm slim=exp-chk-law-slim --out result.json
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from opensearchpy.helpers import scan

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "law"))
from evidence_validation import norm, policies, validate  # noqa: E402

from search_engine.client import create_client  # noqa: E402
from search_engine.config import get_settings  # noqa: E402
from search_engine.embeddings import OllamaEmbedder  # noqa: E402
from search_engine.search import query as retrieval  # noqa: E402
from search_engine.sparse import SparseEncoder  # noqa: E402


def load_chunks(client, alias: str) -> list[dict]:
    rows = [{"id": h["_id"], **h["_source"]} for h in scan(
        client, index=alias, query={"query": {"match_all": {}}, "_source": {"excludes": ["embedding", "splade"]}})]
    return sorted(rows, key=lambda r: r["id"])


def derive_gold(question: dict, chunks: list[dict], rules: dict) -> list[list[str]]:
    """이 인덱스의 청크에서 질문의 정답 근거 그룹을 다시 정한다. 그룹이 비면 그 라벨은 이 청킹에서 찾을 수 없다."""
    parents = set(question["gold"])
    groups = []
    for phrases, scope in ((question["phrases"], parents), (question.get("additional_phrases"), None)):
        if not phrases:
            continue
        needles = [norm(p) for p in phrases]
        if scope is None:
            source = question.get("question_source_parent")
            scope = {source} if source else parents
        groups.append([c["id"] for c in chunks if c["parent_id"] in scope and all(n in norm(c["body"]) for n in needles)
                       and validate(rules.get(question["query"]), c) is None])
    return groups


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--arm", action="append", required=True, help="이름=별칭")
    parser.add_argument("--as-of", default="2026-10-07")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of)

    settings = get_settings()
    settings.search_chunk_filter = False
    settings.search_answerability_judge = False
    client = create_client(settings)
    questions = [json.loads(line) for line in args.queries.read_text(encoding="utf-8").splitlines() if line.strip()]
    questions = [q for q in questions if q.get("positive_review", {}).get("evaluation_eligible", True)]
    texts = [q["query"].strip() for q in questions]
    vectors = dict(zip(texts, OllamaEmbedder(settings).embed(texts)))
    sparse = dict(zip(texts, SparseEncoder(settings).encode(texts, settings.search_splade_query_max_length)))
    retrieval.encode_sparse_query = lambda q: sparse[q]

    class Frozen:
        def embed_query(self, q):
            return vectors[q.strip()]

    rules = policies()
    ratios = {"service": settings.search_category_cutoff_ratio, "0.95": 0.95}
    result = {"questions": len(questions), "service_cutoff": settings.search_category_cutoff_ratio, "arms": {}}
    for spec in args.arm:
        name, alias = spec.split("=", 1)
        chunks = load_chunks(client, alias)
        parent_of = {c["id"]: c["parent_id"] for c in chunks}
        body_norm = {c["id"]: norm(c["body"]) for c in chunks}
        per_question = {}
        for q in questions:
            groups = derive_gold(q, chunks, rules)
            entry = {"gold_groups": [len(g) for g in groups], "gold_lost": any(not g for g in groups) or not groups}
            for label, ratio in ratios.items():
                hits = retrieval.retrieve(client, alias, q["query"], as_of, 5, Frozen(), mode="hybrid", lexical="splade",
                                          chunk_first=True, chunk_first_cutoff_ratio=ratio, score_floor=0.0,
                                          answerability=False, rerank_chunks=False, query_rewrite=False, strict=True)
                returned = [cid for h in hits for cid in h.chunk_ids]
                parents = {parent_of.get(cid) for cid in returned}
                entry[label] = {
                    "evidence": bool(groups) and all(set(g) & set(returned) for g in groups),
                    "doc_hit": bool(set(q["gold"]) & parents),
                    # 라벨과 무관한 지표: 필수 구절을 모두 담은 청크가 (어느 문서든) 반환됐는가
                    "phrase": any(all(norm(p) in body_norm[cid] for p in q["phrases"]) for cid in returned if cid in body_norm),
                    "top_parent": next(iter(h.parent_id for h in hits[:1]), None) if hits and hasattr(hits[0], "parent_id") else None,
                    "returned": len(returned),
                }
            per_question[q["qid"]] = entry
        result["arms"][name] = {"alias": alias, "chunks": len(chunks), "documents": len({c["parent_id"] for c in chunks}),
                                "per_question": per_question}

    names = list(result["arms"])
    print(f"질문 {len(questions)}개, 서비스 컷오프 {result['service_cutoff']}")
    for label in ratios:
        print(f"\n[컷오프 {label}]  (정답 청크 반환 / 정답 문서 적중 / 필수 구절 반환(라벨 무관) / 평균 반환 청크 / 정답 라벨이 청크에서 사라진 질문)")
        for name in names:
            pq = result["arms"][name]["per_question"].values()
            n = len(questions)
            print(f"  {name:6s} 청크 {result['arms'][name]['chunks']:5d}  "
                  f"{sum(e[label]['evidence'] for e in pq):3d}/{n}  {sum(e[label]['doc_hit'] for e in pq):3d}/{n}  "
                  f"{sum(e[label]['phrase'] for e in pq):3d}/{n}  "
                  f"{sum(e[label]['returned'] for e in pq) / n:5.2f}  {sum(e['gold_lost'] for e in pq)}")
    base = names[0]
    for name in names[1:]:
        for label in ratios:
            gained = [qid for qid, e in result["arms"][name]["per_question"].items()
                      if e[label]["evidence"] and not result["arms"][base]["per_question"][qid][label]["evidence"]]
            lost = [qid for qid, e in result["arms"][name]["per_question"].items()
                    if not e[label]["evidence"] and result["arms"][base]["per_question"][qid][label]["evidence"]]
            same_top = sum(e[label]["top_parent"] == result["arms"][base]["per_question"][qid][label]["top_parent"]
                           for qid, e in result["arms"][name]["per_question"].items())
            print(f"\n{base} -> {name} [컷오프 {label}] 1위 문서 같은 질문 {same_top}/{len(questions)}")
            print(f"{base} -> {name} [컷오프 {label}] 새로 반환 {len(gained)}: {gained}  놓침 {len(lost)}: {lost}")
    if args.out:
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
