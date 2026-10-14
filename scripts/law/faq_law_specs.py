"""민원FAQ 질문 중 법령·고시 본문으로 답할 수 있는 질문만 골랐다. 법령 카테고리 정답 청크를 찾는 데 쓴다.

FAQ 원문의 정답은 민원FAQ 문서에 있어서 법령 카테고리 정답이 되지 않는다. 그래서 질문 문장은 그대로 두고,
법령·고시 본문에서 답을 담은 구절(필수 구절)만 새로 적었다. 복합 질문은 EVIDENCE_SPECS의
각 근거 그룹을 모두 찾아야 한다. 그룹 안의 구절 묶음은 대체 근거이며, 한 묶음의 구절은 모두 필요하다.
유형: natural=일상어 질문, table=별표·서식 항목.
"""

SPECS = [
    ("natural", "자가판정 하기 전에 들어야 하는 강의가 의무예요? 안 들으면 어떻게 돼요?", ["자가판정을 하려는 경우에는", "교육을 이수하여야"]),
    ("natural", "AA등급부터 사후보고 같은 특례를 쓸 수 있고 A등급은 안 되는 이유가 뭔가요?", ["등급 A: -", "등급 AA: 허가면제"]),
    ("table", "자율준수무역거래자 지정 신청서의 처리기간은 며칠인가요?", ["40일 이내에 자율준수무역거래자 지정여부를 신청인에게 통보"]),
]

# FAQ의 정책 취지 설명을 정답으로 복사하지 않는다. 법령으로 확인되는 적용범위와
# 심사기준 차이를 설명하고, 'A는 사후보고를 전혀 할 수 없다'는 전제를 바로잡는 근거다.
EVIDENCE_SPECS = {
    SPECS[1][1]: [
        {
            "role": "일부 허가면제 특례의 A·AA 적용범위 차이",
            "title_contains": "[별표 19]",
            "alternatives": [
                ["계약 체결 없이", "허가대상 기술", "등급 A: -", "등급 AA: 허가면제"],
                ["중개허가", "고시 제54조제1항", "등급 A: -", "등급 AA: 허가면제"],
            ],
        },
        {
            "role": "허가면제 적용자격과 사후거래보고 주기의 구분",
            "title_contains": "[별표 19]",
            "alternatives": [["사후거래보고", "등급 A: 3개월", "등급 AA: 반기", "등급 AAA: 연간"]],
        },
        {
            "role": "A·AA의 교육·관리 역량 심사기준 차이",
            "title_contains": "[별표 20]",
            "alternatives": [
                ["담당자 인적요건", "A: 등급평가일 기준", "AA: 아래 사항 모두 만족", "워크숍 참석 실적"],
                ["내부 교육 실적", "A: 전략물자 교육 실적 있음", "AA: 교육 계획에 따른 실적이 있음"],
            ],
        },
    ],
}


def grouped_evidence(query, chunks, normalize):
    """청크 ID 대신 본문·문서 조건으로 복합 질문의 라벨을 재생성한다."""
    specs = EVIDENCE_SPECS.get(query)
    if specs is None:
        return None
    groups = []
    for spec in specs:
        alternatives = [[normalize(p) for p in phrases] for phrases in spec["alternatives"]]
        groups.append([
            chunk for chunk in chunks
            if spec["title_contains"] in chunk["title"]
            and any(all(p in normalize(chunk["body"]) for p in phrases) for phrases in alternatives)
        ])
    return groups
