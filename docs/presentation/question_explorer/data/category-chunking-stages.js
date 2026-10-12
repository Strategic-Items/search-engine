/* 청킹 변경을 세부 커밋 이력이 아니라 검증된 단계 단위로 보여준다. */
window.CATEGORY_CHUNKING_STAGES = [
  {
    id: "stage-01",
    mdPath: "../../evaluation/chunking-stages/stage-01-move-chunking-to-search-engine.md",
    number: 1,
    date: "2026-10-08",
    title: "청킹을 파서에서 검색엔진으로 옮김",
    status: "측정 완료",
    problem: "검색엔진에서 청킹 규칙을 직접 고치고 같은 검색 경로로 검증할 수 없었습니다.",
    change: "파서 청커를 search_engine/chunking으로 이식하고 TextBundle의 마크다운에서 문단·제목·표를 복원해 별도 인덱스로 평가했습니다.",
    result: "파서 원본 원소·표를 입력한 189문서는 파서 결과와 청크 글자까지 같았습니다. 번들 마크다운 입력은 PDF 28개 중 13개에서 구조가 달랐습니다.",
    before: "파서가 청킹한 결과를 검색엔진이 소비",
    after: "검색엔진 안에서 청킹하고 별도 인덱스로 평가",
    metrics: [
      {label: "통제 비교 · 파서 슬림판 → 이식 청커", value: "정답 청크 139/149 → 139/149", note: "검색 결과 변화 없음"},
      {label: "서비스 기준선 → v1", value: "145/149 → 139/149", note: "청커 이식만의 효과가 아님: 파서 규칙 20개 삭제와 코퍼스 차이가 함께 반영됨"},
      {label: "행정·업무", value: "30/30 유지", note: "컷오프 0.7 기준; 0.95에서는 27/30"}
    ],
    note: "이 단계에서는 서비스 별칭이나 운영 색인을 바꾸지 않았습니다. 청킹 소유권을 옮기고 비교 경로를 만든 단계입니다."
  },
  {
    id: "stage-02",
    mdPath: "../../evaluation/chunking-stages/stage-02-common-boundaries.md",
    number: 2,
    date: "2026-10-12",
    title: "긴 본문 첫 조각의 제목 메타데이터 보존",
    status: "메타데이터 회귀 테스트",
    problem: "긴 문단을 나눌 때 첫 청크 본문에는 앞 제목이 포함되지만 페이지 범위와 원소 종류에는 제목이 빠질 수 있습니다.",
    change: "첫 청크의 page_start·page_end·element_types에 본문과 함께 들어간 제목 원소도 포함합니다.",
    result: "평가 코퍼스에서는 이 메타데이터 누락 사례가 발견되지 않았습니다. 검색 개선으로 보지 않고 회귀 테스트로만 유지합니다.",
    before: "첫 청크 본문: 제목 + 긴 문단 일부 · 메타데이터: 본문 문단의 페이지와 paragraph만 기록",
    after: "첫 청크 본문: 동일 · 메타데이터: 제목과 본문의 페이지 범위, heading·paragraph 기록",
    metrics: [
      {label: "실제 코퍼스에서 수정 대상", value: "0문서", note: "이번 평가 코퍼스에서 메타데이터만 바뀐 문서 없음"},
      {label: "검색 성능 효과", value: "측정 불가", note: "실제 코퍼스에서 수정 대상이 없어 검색 결과 변화 없음"},
      {label: "검증 방식", value: "회귀 테스트", note: "여러 페이지의 제목 + 긴 문단 분할을 테스트로 확인"}
    ],
    note: "짧은 절을 다음 제목과 강제로 분리하던 규칙은 v5 실험에서만 사용했고 현재 코드에서는 제거했습니다. v5의 전체 검색 수치는 별도 평가 기록에 보관합니다."
  }
];
