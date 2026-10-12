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
      {label: "행정·업무", value: "30/30 유지", note: "서비스 컷오프 0.7 기준"}
    ],
    note: "이 단계에서는 서비스 별칭이나 운영 색인을 바꾸지 않았습니다. 청킹 소유권을 옮기고 비교 경로를 만든 단계입니다."
  },
  {
    id: "stage-02",
    mdPath: "../../evaluation/chunking-stages/stage-02-common-boundaries.md",
    number: 2,
    date: "2026-10-12",
    title: "청크 메타데이터와 표 문맥 보존",
    status: "법령 검색 측정 완료 · 표 설명/주석 연결",
    problem: "긴 본문 첫 조각의 제목 메타데이터가 빠질 수 있고, 표 행만 검색 청크에 남으면 표 바로 앞의 설명이나 뒤의 주석이 검색되지 않습니다.",
    change: "첫 조각의 페이지·원소 종류를 보정하고, 표를 명시적으로 가리키는 인접 설명과 바로 뒤의 주석을 행 청크에 붙여 별도 문맥 메타데이터로도 보존합니다.",
    result: "법령 149문항의 서비스 컷오프에서 정답 청크·문서·필수 구절 지표는 그대로였습니다. 표 주석 문구를 묻는 별도 확인 질의에서는 해당 주석이 붙은 표 행 청크가 상위 결과에 포함됐습니다.",
    before: "표 행만 본문에 포함 · 인접 설명/주석은 청크 본문과 메타데이터에서 빠짐",
    after: "행 단위 청킹 유지 · 명시적 표 설명/주석을 본문에 연결하고 table_context_before/after에 저장",
    metrics: [
      {label: "법령 · 서비스 컷오프 0.7", value: "정답 청크 143/149 유지", note: "문서 146/149, 필수 구절 139/149 유지; 평균 반환 청크 7.93 → 7.96"},
      {label: "표 주석 확인 질의", value: "수정 후 해당 표 행 노출", note: "‘상기 품목의 규격은 불문한다’ 질의에서 주석이 붙은 청크가 상위 결과에 포함"}
    ],
    exampleKey: "table-note-row",
    exampleKeys: ["table-intro-row", "table-note-row"],
    note: "149문항 비교는 서비스 컷오프만 사용하고 LLM 판정·리랭커·질문 재작성 없이 동일 hybrid(SPLADE+dense) 경로로 실행했습니다. 이 질문셋에서는 검색 지표가 유지됐으므로, 표 문맥이 필요한 질의의 이득은 별도 평가 문항으로 계속 확인해야 합니다. 기존 긴 본문 메타데이터 및 짧은 경계 실험 기록은 아래 Markdown에 보존합니다."
  },
  {
    "id": "stage-03",
    "mdPath": "../../evaluation/chunking-stages/stage-03-table-column-names.md",
    "number": 3,
    "date": "2026-10-12",
    "title": "열1·열2 대신 실제 표 열 이름 복구",
    "status": "법령 검색 측정 완료 · 임시 이름 감소",
    "problem": "빈 모서리 칸·병합 제목·페이지 경계 때문에 실제 머리글을 놓쳐 열1·열2로 검색에 들어갔습니다.",
    "change": "원문의 열 제목을 읽고 연속된 PDF 표에 전달합니다. 원문에 없는 열 제목은 열1 같은 위치 표시로 유지하며 숫자 패턴으로 이름을 추측하지 않습니다. 문서·품목별 예외나 LLM은 사용하지 않습니다.",
    "result": "임시 이름 포함 청크 1,251→650. 정답 문서 146/149 유지. 정답 청크 143→144는 열 이름 복구로 기존 정답 행을 평가가 인식한 효과이며, 새 정답 행을 찾은 사례는 아닙니다.",
    "before": "열1: 1 / 열2: 아세트산 / 열3: Acetic acid",
    "after": "열1: 1 / 국문: 아세트산 / 영문: Acetic acid",
    "metrics": [
      {
        "label": "임시 열 이름 포함 청크",
        "value": "1,251 → 650",
        "note": "임시 이름이 남은 표 187→94개. 650개 중 331개는 실제 제목을 일부 복구했고 빈 제목만 임시 표시로 남겼습니다. 제목을 추측해 채우지 않습니다."
      },
      {
        "label": "법령 · 서비스 컷오프 0.7",
        "value": "정답 청크 143 → 144 /149",
        "note": "정답 문서 146→146, 필수 구절 139→141. 증가한 1문항의 정답 행은 전후 모두 검색됐고 열 이름이 복구됐습니다."
      },
      {
        "label": "원문 셀 보존 검사",
        "value": "누락된 셀 0개",
        "note": "법령 150문서와 별도 행정 20문서의 표 구조 검사. 행정 검색은 실행하지 않았습니다."
      }
    ],
    "exampleKey": "table-header-row",
    "note": "문서명·ID·품목명·평가 질문에 맞춘 분기 없음. 행정 표의 흐름도 반례를 검토해 빈 내부 칸 판정을 강화했으므로, 행정 검사도 미사용 홀드아웃이라고 부르지 않습니다. 이번 검사는 과적합이 없음을 보장하지 않으며, 650개 임시 이름 포함 청크 목록과 실제 전후 데이터를 기록했습니다."
  }
];

window.CATEGORY_CHUNKING_EXAMPLES = {
  "table-note-row": {
    sourceTable: {"title": "[별표3] 전략물자 확인의무 제외대상 목록(영 제40조의2)", "columns": ["HS번호", "품 명"], "rows": [["1류", "산동물"], ["2류", "육과 식용설육"], ["3류", "어류․갑각류․연체동물 및 기타 수생무척추동물"], ["4류", "낙농품․조란․천연꿀 및 다른 류에 분류되지 아니한 식용의 동물성 생산품"], ["5류", "다른 류에 분류되지 아니한 동물성 생산품"], ["6류", "산 수목과 기타의 식물, 인경․뿌리와 이와 유사한 물품 및 절화와 장식 용의 잎"], ["7류", "식용의 채소․뿌리 및 괴경"], ["8류", "식용의 과실 및 견과류와 감귤류 또는 멜론의 껍질"], ["9류", "커피․차․마태 및 향신료"], ["10류", "곡물"], ["11류", "제분공업의 생산품과 맥아․전분․이눌린 및 밀의 글루텐"], ["12류", "채유용에 적합한 종자와 과실, 각종의 종자와 과실, 공업용 또는 의약용의 식물, 짚과 사료용 식물"], ["13류", "락․검․수지 및 기타의 식물성 액즙과 엑스"], ["14류", "식물성 편조물용 재료와 다른 류에 분류되지 아니한 식물성 생산품"], ["15류", "동식물성 유지 및 이들의 분해생산물, 조제식용지와 동식물성의 납"], ["16류", "육류․어류․갑각류․연체동물 또는 기타 수생무척추동물의 조제품"], ["17류", "당류와 설탕과자"], ["18류", "코코아와 그 조제품"], ["19류", "곡물․분․전분 또는 밀크의 조제품과 베이커리 제품"], ["20류", "채소․과실․견과류 또는 식물의 기타 부분의 조제품"], ["21류", "각종의 조제식료품"], ["22류", "음료․알콜 및 식초"], ["23류", "식품 공업에서 생기는 잔재물 및 웨이스트와 조제사료"], ["24류", "담배와 제조한 담배대용물"]], "note": "※ 상기 품목의 규격은 불문한다."},
    summary: "바뀐 부분: 표 뒤의 주석을 각 행 청크에 추가했습니다. 아래 초록색 부분이 실제 추가된 내용입니다.",
    before: {
      id: "01_법령고시-138-2392283-대외무역법시행령_부처협의안-05ba7156#0035",
      heading_path: ["[별표3]", "전략물자 확인의무 제외대상 목록(영 제40조의2)"],
      body: "HS번호: 1류\n품 명: 산동물",
      table_id: "01_법령고시-138-2392283-대외무역법시행령_부처협의안-05ba7156#table0",
      table_example: true, table_number: 1, columns: ["HS번호", "품 명"], row_values: ["1류", "산동물"], row_index: 0, row_count: 24,
      table_context_after: null
    },
    after: [{
      id: "01_법령고시-138-2392283-대외무역법시행령_부처협의안-05ba7156#0035",
      heading_path: ["[별표3]", "전략물자 확인의무 제외대상 목록(영 제40조의2)"],
      body: "표 주석: ※ 상기 품목의 규격은 불문한다.\nHS번호: 1류\n품 명: 산동물",
      table_id: "01_법령고시-138-2392283-대외무역법시행령_부처협의안-05ba7156#table0",
      table_example: true, table_number: 1, columns: ["HS번호", "품 명"], row_values: ["1류", "산동물"], row_index: 0, row_count: 24,
      table_context_after: "※ 상기 품목의 규격은 불문한다."
    }]
  }
};

window.CATEGORY_CHUNKING_EXAMPLES["table-header-row"] = {"headerChange": true, "summary": "원문에 있는 국문·영문만 복구합니다. 첫 열의 제목은 원문에도 없으므로 열1로 유지합니다.", "sourceTable": {"title": "북한 맞춤형 감시대상품목(watch-list) · 1 핵 관련 89개 품목", "columns": ["", "국문", "영문"], "rows": [["1", "아세트산", "Acetic acid"], ["2", "알루미늄", "Aluminium"], ["3", "질산알루미늄", "Aluminium nitrate"], ["4", "수산화암모늄", "Ammonium hydroxide"], ["5", "아르곤 가스", "Argon gas"], ["6", "아스코르브산", "Ascorbic acid"], ["7", "축상 또는 방사상 모터 고정자", "Axial or radial motor stators"], ["8", "염화바륨", "Barium chloride"], ["9", "플루오르화바륨", "Barium fluoride"], ["10", "비스-(2-에틸헥실) 인산", "Bis (2-ethylhexyl) phosphoric acid (HDEHP or D2HPA)"], ["11", "카드뮴", "Cadmium"], ["12", "염화칼슘", "Calcium chloride"], ["13", "플루오르화칼슘", "Calcium fluoride"], ["14", "사염화탄소", "Carbon tetrachloride"], ["15", "팔라듐 촉매 또는 로듐 촉매", "Catalysts containing palladium or rhodium"], ["16", "세라믹 디스크", "Ceramic discs"], ["17", "세륨", "Cerium"], ["18", "임계 안전용기", "Criticality safe containers"], ["19", "사이클로트론", "Cyclotrons"], ["20", "밀도 계측계 또는 지시계", "Density meters or indicators"], ["21", "뇌관 및 다분기점 발화시스템", "Detonators and multipoint initiation systems"], ["22", "중수소", "Deuterium"], ["23", "가열코일이 내장된 용해로", "Dissolution vessels with built-in heating coil"], ["24", "도데칸", "Dodecane, n-Dodecane"], ["25", "전자빔 용접기", "Electron beam welding machines"], ["26", "내폭성 점화챔버", "Explosive firing chambers"], ["27", "고폭물 생산시설", "Facilities for the production of high explosives"], ["28", "뇌관 케이블용 플랫리본", "Flat ribbon (i.e. low inductance) detonator cables"], ["29", "플루오린(불소)", "Fluorine"], ["30", "퓸 후드(배출 후드)", "Fume hoods"], ["31", "가돌리늄", "Gadolinium"], ["32", "산화가돌리늄", "Gadolinium oxide"], ["33", "갈륨", "Gallium"], ["34", "글로브 박스", "Glove boxes"], ["35", "중수", "Heavy water"], ["36", "헬륨-4", "Helium-4"], ["37", "헤파필터", "HEPA filters"], ["38", "고성능 필터 및 환기 시스템", "High efficiency filter and ventilation system"], ["39", "고폭발물", "High explosives"], ["40", "고성능 컴퓨터", "High speed computers"], ["41", "고밀도 방사선 차폐창", "High-density radiation shielding windows"], ["42", "핫셀", "Hot cells"], ["43", "유체동역학 코드", "Hydrodynamic codes"], ["44", "염화히드록실 암모늄", "Hydroxylamine hydrochloride"], ["45", "내식성 재질로 만들어진 산업용 및 실험용 원심분리기", "Industrial or experimental centrifugal separators made of corrosion resistance materials"], ["46", "물리 및 화학 분석기기와 그 부속품", "Instruments and apparatus for physical or chemical analysis, and parts there of"], ["47", "이온 교환 수지", "Ion exchange resins"], ["48", "납", "Lead"], ["49", "누설감지기", "Leak detector"], ["50", "수위 측정기 또는 지시기", "Level meters or indicators"], ["51", "리튬", "Lithium"], ["52", "염화리튬", "Lithium chloride"], ["53", "플루오르화리튬", "Lithium fluoride"], ["54", "수산화리튬", "Lithium hydroxide"], ["55", "질산리튬", "Lithium nitrate"], ["56", "산화마그네슘", "Magnesium oxide"], ["57", "기계식 회전 거울 카메라", "Mechanical rotating mirror cameras"], ["58", "메틸 이소부틸 케톤", "Methyl isobutyl keton"], ["59", "다단 믹서 세틀러", "Multi stage mixer settler"], ["60", "중성자 수송 코드", "Neutron transport codes"], ["61", "질산", "Nitric acid"], ["62", "삼산화이질소", "Nitrogen trioxide"], ["63", "아질산", "Nitrous acid"], ["64", "파라핀", "n-Paraffin, Paraffin"], ["65", "오실로스코프 및 천이 기록계", "Oscilloscopes and transient recorders"], ["66", "옥살산", "Oxalic acid"], ["67", "개인선량계", "Personal dosimeter"], ["68", "내식성 재질로 만들어진 관 또는 배관, 플랜지, 피팅류", "Pipes, piping, flanges, fittings made of corrosion resistance materials"], ["69", "브롬산 칼륨", "Potassium bromate"], ["70", "아질산 칼륨", "Potassium nitrite"], ["71", "맥동탑", "Pulsed columns"], ["72", "방사선 측정기 및 감시시스템", "Radiation detector and monitoring equipment"], ["73", "방사선 유동해석코드", "Radiation hydrodynamic codes"], ["74", "방사선, 임계 및 폭발 방호 장치", "Radiation, criticality and explosion protection controls"], ["75", "원격조정기", "Remote manipulators"], ["76", "로터리 킬른", "Rotary kilns"], ["77", "신틸레이터 및 신틸레이션 측정기", "Scintillators/Scintillation detectors"], ["78", "수산화나트륨", "Sodium hydroxide"], ["79", "질산나트륨", "Sodium nitrate"], ["80", "아질산나트륨", "Sodium nitrite"], ["81", "디오황산나트륨", "Sodium thiosulphate"], ["82", "스테인리스 강", "Stainless steel"], ["83", "스위칭 기기", "Switching devices"], ["84", "탄탈륨", "Tantalum"], ["85", "온도 지시기", "Temperature indicators"], ["86", "트리부틸인산", "Tributyl phosphate, Tri-butyl-phosphate"], ["87", "와류젯 기술", "Vortex jet technology"], ["88", "용접 장비", "Welding units"], ["89", "브롬화 아연", "Zinc bromide"]], "note": "첫 열 머리글은 원문에서도 빈칸입니다. 데이터가 1·2·3…이어도 이름을 추측하지 않고 열1로 유지합니다."}, "before": {"id": "01_법령고시-admrul-2100000251134-b0006-00-cb1ff0c0#0002", "heading_path": ["< 별표 6 >", "1 핵 관련 89개 품목"], "body": "열1: 1\n열2: 아세트산\n열3: Acetic acid", "table_id": "01_법령고시-admrul-2100000251134-b0006-00-cb1ff0c0#table0", "columns": ["열1", "열2", "열3"], "row_index": 1, "row_count": 90, "table_context_after": null, "table_example": true, "table_number": 1, "row_values": ["1", "아세트산", "Acetic acid"]}, "after": [{"id": "01_법령고시-admrul-2100000251134-b0006-00-cb1ff0c0#0001", "heading_path": ["< 별표 6 >", "1 핵 관련 89개 품목"], "body": "열1: 1\n국문: 아세트산\n영문: Acetic acid", "table_id": "01_법령고시-admrul-2100000251134-b0006-00-cb1ff0c0#table0", "columns": ["열1", "국문", "영문"], "row_index": 0, "row_count": 89, "table_context_after": null, "table_example": true, "table_number": 1, "row_values": ["1", "아세트산", "Acetic acid"]}]};

window.CATEGORY_CHUNKING_EXAMPLES["table-intro-row"] = {"title": "예시 1 · 표 앞 설명 연결", "contextPosition": "before", "summary": "표 앞의 설명 문장을 각 행 청크의 맨 앞에 추가했습니다. 초록색 설명이 추가된 부분이며, 표의 행 값은 그대로입니다.", "sourceTable": {"title": "[별표 6] 전략물자 수출지역 구분", "columns": [], "noHeader": true, "rows": [["“가”지", "아르헨티나, 호주, 오스트리아, 불가리아, 벨기에, 캐나다, 체코, 덴마크, 핀란드, 프랑스, 독일, 그리스, 헝가리, 아일랜드, 이탈리아, 일본, 룩셈부르크, 네덜란드, 뉴질랜드, 노르웨이, 우크라이나, 폴란드, 포르투갈, 스페인, 스웨덴, 스위스, 터키, 영국, 미국(29개국)\n* 상기 국가들은 바세나르체제(Wassenaar Arrangement : WA), 핵공급국그룹(Nuclear Suppliers Group : NSG), 오스트레일리아그룹(Australia Group : AG) 및 미사일기술통제체제(Missile Technology Control Regime : MTCR) 등 4개 다자간 수출통제체제에 모두 가입한 국가"]], "beforeNote": "제1조 전략물자 수출지역은 아래 표와 같이 가지와 나지로 구분한다.", "hint": "원본 표에는 열 제목 행이 없습니다. 아래 청크의 열1·열2는 위치 표시입니다. 첫 데이터 행을 비교합니다."}, "before": {"id": "01_법령고시-1406-2394253-첨부5-별표_4-별표_18_01-15dea616#0029", "heading_path": ["[별표 6]"], "body": "열1: “가”지\n열2: 아르헨티나, 호주, 오스트리아, 불가리아, 벨기에, 캐나다, 체코, 덴마크, 핀란드, 프랑스, 독일, 그리스, 헝가리, 아일랜드, 이탈리아, 일본, 룩셈부르크, 네덜란드, 뉴질랜드, 노르웨이, 우크라이나, 폴란드, 포르투갈, 스페인, 스웨덴, 스위스, 터키, 영국, 미국(29개국) * 상기 국가들은 바세나르체제(Wassenaar Arrangement : WA), 핵공급국그룹(Nuclear Suppliers Group : NSG), 오스트레일리아그룹(Australia Group : AG) 및 미사일기술통제체제(Missile Technology Control Regime : MTCR) 등 4개 다자간 수출통제체제에 모두 가입한 국가", "table_id": "01_법령고시-1406-2394253-첨부5-별표_4-별표_18_01-15dea616#table3", "columns": ["열1", "열2"], "row_index": 0, "row_count": 2, "table_context_before": null, "table_context_after": null, "table_example": true, "row_values": ["“가”지", "아르헨티나, 호주, 오스트리아, 불가리아, 벨기에, 캐나다, 체코, 덴마크, 핀란드, 프랑스, 독일, 그리스, 헝가리, 아일랜드, 이탈리아, 일본, 룩셈부르크, 네덜란드, 뉴질랜드, 노르웨이, 우크라이나, 폴란드, 포르투갈, 스페인, 스웨덴, 스위스, 터키, 영국, 미국(29개국)\n* 상기 국가들은 바세나르체제(Wassenaar Arrangement : WA), 핵공급국그룹(Nuclear Suppliers Group : NSG), 오스트레일리아그룹(Australia Group : AG) 및 미사일기술통제체제(Missile Technology Control Regime : MTCR) 등 4개 다자간 수출통제체제에 모두 가입한 국가"]}, "after": [{"id": "01_법령고시-1406-2394253-첨부5-별표_4-별표_18_01-15dea616#0029", "heading_path": ["[별표 6]"], "body": "표 설명: 제1조 전략물자 수출지역은 아래 표와 같이 가지와 나지로 구분한다.\n열1: “가”지\n열2: 아르헨티나, 호주, 오스트리아, 불가리아, 벨기에, 캐나다, 체코, 덴마크, 핀란드, 프랑스, 독일, 그리스, 헝가리, 아일랜드, 이탈리아, 일본, 룩셈부르크, 네덜란드, 뉴질랜드, 노르웨이, 우크라이나, 폴란드, 포르투갈, 스페인, 스웨덴, 스위스, 터키, 영국, 미국(29개국) * 상기 국가들은 바세나르체제(Wassenaar Arrangement : WA), 핵공급국그룹(Nuclear Suppliers Group : NSG), 오스트레일리아그룹(Australia Group : AG) 및 미사일기술통제체제(Missile Technology Control Regime : MTCR) 등 4개 다자간 수출통제체제에 모두 가입한 국가", "table_id": "01_법령고시-1406-2394253-첨부5-별표_4-별표_18_01-15dea616#table3", "columns": ["열1", "열2"], "row_index": 0, "row_count": 2, "table_context_before": "제1조 전략물자 수출지역은 아래 표와 같이 가지와 나지로 구분한다.", "table_context_after": null, "table_example": true, "row_values": ["“가”지", "아르헨티나, 호주, 오스트리아, 불가리아, 벨기에, 캐나다, 체코, 덴마크, 핀란드, 프랑스, 독일, 그리스, 헝가리, 아일랜드, 이탈리아, 일본, 룩셈부르크, 네덜란드, 뉴질랜드, 노르웨이, 우크라이나, 폴란드, 포르투갈, 스페인, 스웨덴, 스위스, 터키, 영국, 미국(29개국)\n* 상기 국가들은 바세나르체제(Wassenaar Arrangement : WA), 핵공급국그룹(Nuclear Suppliers Group : NSG), 오스트레일리아그룹(Australia Group : AG) 및 미사일기술통제체제(Missile Technology Control Regime : MTCR) 등 4개 다자간 수출통제체제에 모두 가입한 국가"]}]};
window.CATEGORY_CHUNKING_EXAMPLES["table-note-row"].title = "예시 2 · 표 뒤 주석 연결";
