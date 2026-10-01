"""카테고리 검색(법령·고시 `search-law`, 행정·업무 `search-admin`)을 청크 단위로 점검한다. CATEGORY=admin으로 행정·업무를 고른다.

질문마다 필수 구절(`phrases`)을 적어 두면, 그 구절을 모두 담은 청크가 정답 청크가 된다.
정답을 ID로 직접 적지 않아서 라벨이 실제 본문에 근거하는지 만들 때 검사되고, 청크를 다시 자르면 라벨도 따라온다.

    .venv/bin/python scripts/law/evaluate_law.py --build   # 질문 셋(data/queries_law_v1.jsonl) 생성·검증
    .venv/bin/python scripts/law/evaluate_law.py           # 모드별 채점
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.search.query import retrieve

from category import CATEGORY, QUERIES, alias as category_alias, source as category_source  # noqa: E402
_KEEP = re.compile(r"[^0-9A-Za-z가-힣]")
K = 5
MODES = ["bm25", "vector", "hybrid"]

# (유형, 질문, 필수 구절). 유형: natural=일상어 질문, identifier=고시 번호·통제번호, table=표 행, annex=별표.
SPECS = [
    ("natural", "전략물자 사전판정을 신청하면 센터에서 며칠 안에 판정해 줘?", ["15일 이내에 1종전략물자 해당여부를 판정"]),
    ("natural", "수출허가가 면제된 경우에도 따로 보고해야 하나요?", ["수출허가가 면제된 경우 7일 이내에 수출거래보고서 제출"]),
    ("natural", "개별수출허가 신청하면 처리 기간이 얼마나 걸리나요?", ["접수일 부터 15일 이내", "5일 이내"]),
    ("natural", "허가 없이 수출되려는 전략물자를 정부가 중간에 막을 수 있나요?", ["허가 없이 수출되거나", "이동중지명령"]),
    ("natural", "자율준수무역거래자로 지정되면 어떤 특례를 받나요?", ["자율준수무역거래자에 대한 특례", "특례를 부여할 수 있다"]),
    ("natural", "전략물자를 다른 업체에 넘길 때 상대방에게 알려야 하나요?", ["재판매시에도"]),
    ("natural", "수리하려고 되돌려 받은 전략물자를 다시 보낼 때도 수출허가가 필요한가요?", ["수리 후 다시 원수입자"]),
    ("natural", "전략물자관리원 직원이 업무상 알게 된 비밀은 어떻게 해야 하나요?", ["비밀준수의무"]),
    ("natural", "수출 상대국이 의심스러울 때 상황허가를 받아야 하는 경우는 어떤 거예요?", ["수송경로가 정상적이지 않은 경우"]),
    ("natural", "위반행위 점수는 어떻게 계산해서 처분 수위를 정하나요?", ["비중치", "각 점수를 합하여"]),
    ("natural", "이란에 투자하거나 교역할 때 받는 비금지 확인서는 신청서를 누가 검토하나요?", ["원장은 제4조의 신청서 접수시"]),
    ("identifier", "지식경제부 고시 제2011-276호는 언제부터 시행되나요?", ["이 고시는 고시한 날부터 시행한다"]),
    ("identifier", "산업통상자원부 고시 제2015-145호에서 중개허가 대상은 누구인가요?", ["제53조(중개허가의 대상)"]),
    ("identifier", "통제번호 2B352는 어느 국제수출통제체제에 속하나요?", ["오스트레일리아그룹 (AG)", "2B352"]),
    ("identifier", "8A001 통제번호는 무엇을 가리키나요?", ["8A001 잠수정"]),
    ("annex", "일본은 전략물자 수출지역 구분에서 어느 지역인가요?", ["가 지역", "일본"]),
    ("annex", "산 동물은 상황허가 면제 대상인가요?", ["상황허가 면제대상", "산 동물"]),
    ("annex", "통관절차상의 혜택을 받는 기준은 무엇인가요?", ["통관절차상의 혜택", "혜택 기준"]),
    ("table", "곡물은 전략물자 확인의무 제외대상에 들어가나요?", ["HS번호: 10류", "곡물"]),
    ("table", "제분공업 생산품은 확인의무 제외대상인가요?", ["제분공업의 생산품"]),
    ("natural", "관세통계통합품목분류표를 개정한 이유가 뭐예요?", ["로테르담협약", "수은화합물"]),
]


from admin_specs import SPECS as ADMIN_SPECS  # noqa: E402


def norm(text: str) -> str:
    return _KEEP.sub("", text).lower()


def read_chunks() -> list[dict]:
    path = Path(category_source(get_settings()))
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build() -> None:
    chunks = read_chunks()
    rows, bad = [], []
    for number, (kind, query, phrases) in enumerate(SPECS if CATEGORY == "law" else ADMIN_SPECS, 1):
        needles = [norm(p) for p in phrases]
        gold = [c for c in chunks if all(n in norm(c["body"] + " " + " ".join(c["heading_path"])) for n in needles)]
        if not gold:
            bad.append(query)
            continue
        rows.append({
            "qid": f"{CATEGORY}-v1-{number:03d}", "category": kind, "query": query, "phrases": phrases,
            "gold": sorted({c["parent_id"] for c in gold}),
            "evidence_groups": [[c["id"] for c in gold]],
        })
    if bad:
        sys.exit(f"정답 청크가 없는 질문: {bad}")
    QUERIES.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    sizes = [len(r["evidence_groups"][0]) for r in rows]
    print(f"{len(rows)}문항 -> {QUERIES} (질문당 정답 청크 중앙값 {sorted(sizes)[len(sizes) // 2]}, 최대 {max(sizes)})")


def evaluate() -> None:
    rows = [json.loads(line) for line in QUERIES.read_text(encoding="utf-8").splitlines() if line.strip()]
    settings = get_settings()
    client = create_client(settings)
    # 청크 필터는 LLM 호출이라 검색 자체의 품질과 섞인다. 끄고 검색기만 잰다.
    settings.search_chunk_filter = False
    alias = category_alias(settings)
    print(f"{len(rows)}문항, 상위 {K}문서 창 기준, alias={alias}\n")
    print("| 모드 | 근거 Recall(청크) | 근거 Precision(청크, 하한) | 그 창에서 가능한 최대 | 문서 Precision | 문서 Hit | 첫 근거 청크 순위 평균 | 평균 청크 수 |\n|---|---|---|---|---|---|---|---|")
    misses = {}
    for mode in MODES:
        found = doc_hit = 0
        ranks, sizes = [], []
        # 질문마다 구한 비율의 평균. 정답 청크는 필수 구절을 담은 것만 라벨이라, 라벨 밖의 관련 청크는
        # 오답으로 세어진다. 그래서 청크 Precision은 하한이다.
        chunk_precision, doc_precision, ceiling = [], [], []
        for row in rows:
            hits = retrieve(client, alias, row["query"], date.today(), K, mode=mode, score_floor=0.0,
                            answerability=False)
            window = [c for h in hits for c in h.chunk_ids]
            gold = set(row["evidence_groups"][0])
            sizes.append(len(window))
            chunk_precision.append(sum(c in gold for c in window) / len(window) if window else 0.0)
            ceiling.append(min(len(gold), len(window)) / len(window) if window else 0.0)
            doc_precision.append(sum(h.parent_id in row["gold"] for h in hits) / len(hits) if hits else 0.0)
            rank = next((i for i, c in enumerate(window, 1) if c in gold), None)
            found += rank is not None
            doc_hit += any(h.parent_id in row["gold"] for h in hits)
            if rank:
                ranks.append(rank)
            else:
                misses.setdefault(mode, []).append((row["qid"], row["query"], [h.parent_id[-22:] for h in hits][:3]))
        n = len(rows)
        print(f"| {mode} | {found}/{n} = {found / n:.3f} | {sum(chunk_precision) / n:.3f} | {sum(ceiling) / n:.3f} | {sum(doc_precision) / n:.3f} | {doc_hit}/{n} | {sum(ranks) / len(ranks):.1f} | {sum(sizes) / n:.1f} |")
    for mode, items in misses.items():
        print(f"\n[{mode}] 근거 청크를 못 찾은 질문")
        for qid, query, top in items:
            print(f"  {qid} {query}\n      상위 문서: {top}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--build", action="store_true")
    build() if parser.parse_args().build else evaluate()
