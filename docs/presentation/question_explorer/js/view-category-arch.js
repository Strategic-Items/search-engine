function categoryArchSvg(){
  var s='<svg class="flowsvg" id="flowsvg" viewBox="0 0 1120 1540" style="width:100%" role="img" aria-label="카테고리 검색 공통 흐름">';
  s+='<defs><marker id="cah" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="11" markerHeight="11" orient="auto"><path d="M1,1 L11,6 L1,11 z" style="fill:var(--muted)"/></marker></defs>';
  function node(o){ return fnode(o); }
  function line(d){ return fline(d,"ln","",0,0,"","","cah"); }
  s+=node({c:"end",x:310,y:20,w:500,h:145,n:"1",t:"질문 + 카테고리",g:["37"],l:["선택한 카테고리의 인덱스에서 검색","법령·고시 / 행정·업무 / 민원FAQ","기준일·유효기간·질문의 공고번호로 필터"]});
  s+=line("M560,165 V200 H270 V250")+line("M560,200 H850 V250");
  s+=node({c:"spl",x:30,y:250,w:480,h:180,n:"2",t:"SPLADE로 후보 찾기",g:["38","46"],l:["파인튜닝한 설정 C 모델","어휘 가중치 내적 / 법령은 명시 근거 가산 +6씩","문서·질의 256토큰 / 최대 256 term","상위 25개 청크 후보"]});
  s+=node({c:"vec",x:610,y:250,w:480,h:180,n:"2",t:"dense로 후보 찾기",g:["39"],l:["BGE-m3-ko / 1024차원","질문 벡터와 청크 벡터의 코사인 유사도","HNSW 색인에서 검색","상위 25개 청크 후보"]});
  s+=line("M270,430 V485 H440 V530")+line("M850,430 V485 H680 V530");
  s+=node({c:"end",x:260,y:530,w:600,h:185,n:"3",t:"청크 단위 RRF 합산",g:["40"],l:["점수 = SPLADE 1/(60+순위) + dense 1/(60+순위)","법령: 두 목록 가중치 1 : 1 / BM25·추가 후보 조회 없음","절대 점수 하한 없음 / 검색기별 사전 트림 꺼짐","dense가 비어도 SPLADE 후보로 계속 검색"]});
  s+=line("M560,715 V775");
  s+=node({c:"end",x:260,y:775,w:600,h:210,n:"4",t:"합산 점수로 청크 고르기",g:["40"],l:["1위 합산 점수의 70% 미만은 제외","각 검색기의 1위 청크·기간 일치 근거는 예외 유지","최대 10청크 / 5문서 / 문서당 6청크","동점은 dense 순위 → 청크 ID 순","같은 문서 사본은 하나만 / 대체된 판은 점수 ×0.97"]});
  s+=line("M560,985 V1045");
  s+=node({c:"end",x:260,y:1045,w:600,h:170,n:"5",t:"선택한 청크를 원본 문서별로 묶어 반환",l:["문서 순위가 청크 선택을 먼저 제한하지 않음","답변 가능성 판정 꺼짐 / 청크 LLM 필터는 설정에 따름","두 검색기에 후보가 모두 없으면 빈 결과 반환"]});
  s+=line("M560,1215 V1275");
  s+=node({c:"ans",x:260,y:1275,w:600,h:170,n:"6",t:"질문별 결과에서 근거 확인",l:["SPLADE / dense / hybrid 결과를 나란히 비교","정답 요건이 여러 개면 모두 충족해야 적중","문서 발견과 정답 근거 충족을 구분해 표시"]});
  return s+'</svg>';
}

function renderCategoryArch(){
  var items=[["cat-flow","공통 검색 흐름"],["cat-flow-settings","현재 코드의 설정"],["cat-flow-stage46","46단계 · 현재 법령"],["cat-flow-update","2026-10-08 · 과거 기록"],["cat-flow-evaluation","화면의 평가 결과와 비교"]];
  document.getElementById("stnav").innerHTML=items.map(function(x){return '<button type="button" data-go2="'+x[0]+'"><span class="nl">공통 · 구조도</span><span class="nt">'+x[1]+'</span></button>';}).join("");
  document.getElementById("detail").innerHTML='<div class="wrap" style="max-width:none"><div class="sv-h"><span class="sl">카테고리별 검색 · 공통</span><h2 class="big">SPLADE + dense 검색 흐름</h2></div>'+
    '<p class="note">카테고리마다 다른 인덱스를 쓰고, 후보 검색·청크 합산·반환 방식은 함께 씁니다. 현재 SPLADE 모델이 설정된 카테고리 API 경로를 기준으로 그렸습니다. 민원FAQ 결과는 오프라인 평가이며, 현재 카테고리 API에는 법령·고시와 행정·업무가 등록돼 있습니다.</p>'+
    '<div class="archbar"><span class="note">상자에서 단계 번호를 누르면 공통 단계별 설명으로 이동합니다.</span><button type="button" class="zb" data-zoom="-1">− 작게</button><button type="button" class="zb" data-zoom="1">크게 +</button></div>'+
    '<div id="cat-flow" style="overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--paper);padding:14px">'+categoryArchSvg()+'</div>'+
    '<h2 id="cat-flow-settings">현재 코드의 설정</h2><table><thead><tr><th>항목</th><th>카테고리 SPLADE + dense</th></tr></thead><tbody>'+[
      ["후보 수","SPLADE 25개 + dense 25개 (상위 5문서 요청 기준)"],
      ["절대 하한","0.0 · 꺼짐"],
      ["dense 하한에서 모두 탈락할 때 조기 종료","카테고리 검색에서는 적용되지 않음"],
      ["합산","청크 단위 RRF · k=60 · SPLADE : dense 가중치 1 : 1"],
      ["법령 조회 가산 (46단계)","SPLADE 내적 + 제목 경로의 조문·별표·별지 일치 6 + 본문의 통제번호 일치 6 + 근거 범위·대상 항목 일치 6. 상위 25개를 고르기 전에 적용하며 BM25·추가 후보 조회 없음. 행정은 기존 경로 유지"],
      ["최신 판 우대","질문이 판본을 지정하지 않으면 대체된 문서(superseded_by)의 청크 점수 × 0.97"],
      ["색인 입력","SPLADE·dense 모두 제목 + 제목 경로 + 본문 (재색인 완료: 2026-10-08)"],
      ["컷오프","최고 합산 점수의 70% (2026-10-08에 95%에서 변경) · 검색기 1위/기간 일치 근거 예외 유지"],
      ["반환 상한","10청크 · 5문서 · 문서당 6청크"],
      ["LLM 판정","답변 가능성 판정 꺼짐 · 청크 LLM 필터는 서비스 설정에 따름 (현재 켬)"]
    ].map(function(r){return '<tr><td>'+r[0]+'</td><td>'+r[1]+'</td></tr>';}).join("")+'</tbody></table>'+
    '<h2 id="cat-flow-stage46">2026-10-12 · 46단계</h2>'+cqStage46Overview()+'<p class="cap">현재 질문별 법령 화면은 46단계 결과입니다. 아래 2026-10-08 기록은 당시의 보조 식별자 조회가 있던 과거 실험입니다.</p><h2 id="cat-flow-update">2026-10-08 변경과 측정 · 과거 기록</h2><p class="note">법령 150문서·6,288청크, 질문 149문항(law150)을 컷오프 70%로 다시 쟀습니다. 표의 수치는 <b>정답 청크가 하나라도 반환된 질문 수</b>(/149)이고, 청크 최대 10 · 문서 5 · 문서당 6은 그대로입니다. 변화 폭이 한두 문항이라 잡음 범위를 넘는다고 단정하지 않습니다.</p><table><thead><tr><th>단계</th><th>단독 SPLADE</th><th>단독 dense</th><th>hybrid</th><th>평균 청크</th></tr></thead><tbody>'+[
      ["기준 (재색인 전)","140","141","143","8.2"],
      ["제목 경로 재색인 (SPLADE·dense 모두)","142","143","144","8.0"],
      ["+ 식별자 가산 (가중치 0.5, 상위 5청크)","–","–","145","7.9"],
      ["+ 048번 라벨 보정, 최신 판 우대 ×0.97","–","–","146","7.9"]
    ].map(function(r){return '<tr><td>'+r.join('</td><td>')+'</td></tr>';}).join("")+'</tbody></table>'+
    '<p class="note"><b>식별자 가산</b>: 가중치 1.0·상위 25개로 시험했을 때는 ML8처럼 흔한 번호(79청크)에서 컷오프가 정답을 잘라 078번을 잃었습니다. 상위 5개·가중치 0.5로 줄이자 잃은 질문 없이 075번(3A002.d.1)을 구제했습니다. <b>제목 경로</b>: 022번(소말리아)은 정답 청크 본문에 "소말리아"가 없고 장 제목에만 있어, 경로를 넣기 전에는 다른 나라 장의 같은 조항에 밀렸습니다. 경로를 넣자 정답 3개를 모두 찾았습니다. 단독 검색은 좋아졌지만 hybrid는 얻는 만큼 잃는 질문도 있어 효과가 작습니다. <b>최신 판 우대</b>: 048번은 현행 고시(제2026-101호)가 5문서 한도 밖 6번째 문서라 잘렸습니다. 최신 판이 앞에 와야 한다는 기준으로 라벨에 현행 판을 정답으로 더하고 대체된 문서 점수를 ×0.97로 깎아 구제했으며, 잃은 질문은 없었습니다.</p>'+
    '<table><thead><tr><th>2026-10-08 당시 미해결 질문</th><th>원인</th><th>방향</th></tr></thead><tbody>'+[
      ["037 제85조 서류보관의무","질문의 조 번호(제85조)가 정답 청크 제목에 있는데 SPLADE 후보에 아예 없고, 본문이 비슷한 제88조(서류의 보관)가 위로 올라옵니다.","조 번호를 제목에서 일치시키는 가산(질문 4개에서만 시험, 037 구제) — 표본이 작아 보류"],
      ["043 농축·재처리 시설 수출","상위 청크는 \"엄격히 제한한다\"이고 정답은 \"허가할 수 없다\"는 별표 13입니다. 비슷하지만 같은 내용은 아닙니다.","상위 청크가 질문에 충분히 답하는지 라벨 판단이 먼저 필요"],
      ["076 별지 제4호 주의사항","주의사항 문구가 서식의 마지막 조각 청크에 있고, 그 청크에는 서식 이름(전문판정(신청)서)이 없습니다. 제목 경로는 \"[별지 제4호 서식]\"뿐입니다.","청킹 쪽: 서식 조각 청크에 서식 이름을 붙이는 방안"]
    ].map(function(r){return '<tr><td>'+r.join('</td><td>')+'</td></tr>';}).join("")+'</tbody></table>'+
    '<h2 id="cat-flow-evaluation">화면의 평가 결과와 비교</h2><p class="note">메타데이터가 검색 필드로 넘어가 쓰이는 길은 공통 · 메타데이터 보기에 있고, 각 카테고리의 질문별·결과 요약·메타데이터 채움 현황은 해당 카테고리 탭에서 봅니다. 공통의 단계별 기록에는 적용한 변경과 비교 실험을 함께 담았습니다. 저장된 평가 결과는 서비스의 청크 LLM 필터를 끄고 측정했으며, 리랭커도 사용하지 않았습니다. SPLADE 단독 80%, dense 단독 93%는 저장된 오프라인 평가의 컷오프이며, 이 구조도의 hybrid 70% 경로와 구분해 읽습니다. 서비스 hybrid 컷오프는 2026-10-08에 95%에서 70%로 바꿨고, 법령 질문별 결과는 2026-10-12에 46단계·70% 컷오프로 갱신했습니다. 행정·FAQ의 저장 결과는 hybrid 95%입니다. LLM 필터를 끈 기록이므로 실행 중인 서버의 답변 품질을 뜻하지 않습니다.</p></div>';
  document.getElementById("detail").scrollTop=0;
}

/* 문서·법령 카테고리의 전체 색인 필드와 검색에서 생성되는 응답 필드. */
function categorySearchFieldTransform(field, example){
  var transforms={
    parent_id:["parent_id (없으면 id)","parent_id 없음 · id = form-2026","form-2026","부모 ID가 없으면 입력 id로 보완","보완"],
    doc_type:["document.document_type","고시","고시","document 객체에서 최상위 검색 필드로 복사","이름 변경"],
    doc_status:["document.status","안","안","document 객체에서 최상위 검색 필드로 복사","이름 변경"],
    doc_number:["document.document_number","제2026-0598호","제2026-0598호","원문 번호를 보존하며 필드 이름만 변경","이름 변경"],
    doc_number_norm:["document.document_number","제2026-0598호","2026-598","연도·일련번호 추출, 제·호와 앞자리 0 제거","정규화"],
    issuer:["document.source","산업통상부","산업통상부","기관 값을 issuer로 복사","이름 변경"],
    revision_date:["document.revision_date","2026-08-15","2026-08-15","document 객체에서 최상위 검색 필드로 복사","이름 변경"],
    effective_from:["document.effective_date","2026-09-01","2026-09-01","시행일을 기존 유효기간 검색 필드로 복사","이름 변경"],
    effective_to:["document.expiry_date","2027-01-01","2027-01-01","종료일을 기존 유효기간 검색 필드로 복사","이름 변경"],
    published_at:["published_at","20260904 또는 2026-09-04","2026-09-04","8자리 숫자 날짜도 ISO 날짜 문자열로 정규화","날짜 정리"],
    superseded_by:["document.superseded_by / 준비 과정의 대체 관계","[고시 번호 A, 고시 번호 B]","고시 번호 A, 고시 번호 B","법령 경로는 목록을 쉼표로 합칩니다. 번호를 문서 ID로 해소하는 변환은 현재 없습니다. core 준비 경로는 대상 문서 ID를 생성합니다.","목록 → 문자열"],
    period_hint:["첫 청크 body + published_at 없음","본문 앞머리: 2025. 3. 8.","2025-03-08","게시일이 없을 때 앞머리 날짜에서 생성","검색 준비에서 생성"],
    date_basis:["date_basis","게시일 있음 / 게시일 없음","publication_only / undated","파서가 적어 준 값을 그대로 보존합니다. 카테고리 색인은 이 값을 다시 계산하지 않습니다.","원본 보관"],
    codes_exact:["code","4A102 · 제26조제1항제5호","[4a102, 제26조제1항제5호]","코드·조문 추출, 소문자·공백 정리, 중복 제거","추출"],
    code_norm:["code","4A102. ","4a102","소문자 변환, 공백과 마지막 점 제거","정규화"],
    content_hash:["content_hash / title + body + code","파서 해시 있음 / 해시 없음","기존 해시 / 계산한 SHA-256","기존 해시를 보존하며 core 준비 경로는 결측일 때 생성","보존 또는 생성"],
    embedding:["title + heading_path + body","전문판정 안내 + 제출 서류 + 본문","[0.12, -0.08, …]","법령·행정은 제목에 경로를 붙인 후 본문과 함께 임베딩. 숫자는 형식 예시입니다.","색인에서 생성"],
    splade:["title + body","전문판정 안내 + 본문","{토큰: 가중치, …}","모델이 설정돼 있을 때 희소 벡터 생성. 현재 heading_path를 별도로 덧붙이지 않습니다.","색인에서 생성"],
    "title.standard / body.standard":["title / body","제목·본문 텍스트","standard 분석기로 나눈 토큰","검색엔진 분석기가 만드는 보조 필드","색인에서 생성"],
    score:["파서 필드 없음 · 질문과 검색 결과","질문과 후보 청크","검색기 점수 / 융합 점수","검색 실행·순위 융합에서 생성","검색에서 생성"],
    passages:["파서 필드 없음 · 같은 parent_id의 청크","청크 id · body · 검색 점수","[{id, body, score, relevance}, …]","같은 문서에서 추가 근거를 선택해 묶음","검색에서 생성"],
    chunk_relevance:["파서 필드 없음 · 질문 + 대표 청크 body","질문과 대표 청크 본문","0 / 1 / 2 또는 비어 있음","관련성 판정을 실행했을 때 생성","판정에서 생성"],
    "passages[].relevance":["파서 필드 없음 · 질문 + 추가 청크 body","질문과 추가 청크 본문","0 / 1 / 2 또는 비어 있음","추가 근거별 관련성 판정을 실행했을 때 생성","판정에서 생성"]
  };
  return transforms[field]||[field,example,example,"필드 이름과 원본 값을 그대로 보존","그대로 유지"];
}
function categoryMetadataCatalog(){
  var groups=[
    ["문서 식별 · 출처",[
      ["id","청크 ID","form-2026#0000","청크를 식별하고 검색 결과·근거를 연결합니다."],
      ["parent_id","부모 문서 ID","form-2026","같은 문서의 청크를 묶고 문서 전체를 조회합니다."],
      ["source_type","자료 종류","공지사항 · 민원서식","검색 결과와 답변 근거 머리말에 표시합니다."],
      ["source_url","원문 주소","https://www.yestrade.go.kr/…","검색 결과와 답변 근거의 출처 링크입니다."],
      ["source_path","원본 파일 경로","자료/신청서.hwp","입력 자료에서 내려받기 사본을 확인합니다. 전용 검색 필드로 매핑하지 않습니다."],
      ["content_hash","내용 해시","SHA-256 문자열","내용 식별용으로 보관합니다. 현재 사본 정리는 파일 경로 또는 제목·게시일을 사용합니다."]
    ]],
    ["문서 속성 · 법령 구조",[
      ["doc_type","문서 유형","고시 · 규정 · FAQ","document.document_type에서 가져옵니다. 결과에 보존하며 필터·가산점에는 미사용입니다."],
      ["doc_status","문서 상태","현행 · 안","document.status에서 가져옵니다. 결과에 보존하며 필터·가산점에는 미사용입니다."],
      ["doc_number","문서 번호 원문","제2026-598호","document.document_number를 보관하고 검색 결과에 싣습니다."],
      ["doc_number_norm","정규화 문서 번호","2026-598","번호 표기를 통일해 색인합니다. 현재 이 필드로 필터·가산점을 주지 않습니다."],
      ["issuer","발행 기관","산업통상자원부","document.source에서 가져옵니다. 결과에 보존하며 필터·가산점에는 미사용입니다."],
      ["legal_structure","법령 구조","조문 · 별표 등의 구조 정보","파서가 조문 구조를 복원했는지 regulation / general로 기록합니다. 법령 카테고리에 색인하지만 현재 필터·점수에는 미사용입니다."],
      ["heading_path","제목·조문 경로","수출허가 > 신청 절차 > 제출 서류","청크가 속한 위치입니다. 경로를 붙인 제목과 본문으로 dense 임베딩을 만들고 결과에도 보존합니다."]
    ]],
    ["날짜 · 시점",[
      ["published_at","게시일","2026-09-04","질문의 연·월과 일치하면 BM25 +6 신호이며 제목과 함께 사본 정리에 사용합니다."],
      ["effective_from","시행일","2026-09-01","document.effective_date에 대응합니다. 기준일 이하이면 통과하며 연·월 가산점과 답변 머리말에도 사용합니다."],
      ["effective_to","종료일","2027-01-01","document.expiry_date에 대응합니다. 기준일이 종료일보다 앞서야 통과하며, 종료일 당일부터 제외합니다."],
      ["revision_date","개정일","2026-08-15","document.revision_date를 색인에 보관합니다. 현재 필터·가산점과 SearchHit 응답에는 미사용입니다."],
      ["period_hint","본문에서 추정한 시점","본문 앞머리의 2025. 3. 8.","게시일이 없을 때 계산합니다. 연·월 가산점 +4에만 사용하며 사본·대체 판단에는 사용하지 않습니다."],
      ["date_basis","날짜 판단 근거","publication_only / undated","유효기간을 모르는 문서를 게시일만으로 판단한다는 표시입니다. 파서는 게시일 유무만 보므로 시행일이 있는 문서도 publication_only로 적힙니다(법령 2,134청크). 검색 필터·점수에는 사용하지 않습니다. docs·core 인덱스는 준비 과정에서 시행일 기준으로 다시 계산해 effective 값도 쓰지만, 카테고리 색인은 그 경로를 거치지 않습니다."]
    ]],
    ["문서 관계 · 청크 구성",[
      ["superseded_by","이 문서를 대체하는 판","form-2026","대체한 문서의 ID를 따라 새 판을 결과에 추가합니다. 파서 속성 또는 준비 과정에서 채웁니다. 파서가 고시 번호로 준 값은 문서 ID와 동일한지 확인이 필요합니다."],
      ["chunk_index","문서 안 청크 순서","0, 1, 2, …","첫 청크와 문서 내부 순서를 식별합니다. 앞머리 시점 추정은 첫 청크를 사용합니다."],
      ["code","원본 품목·통제 번호","4A102","입력 코드를 보관하며 검색 결과에도 싣습니다."],
      ["codes_exact","추출한 정확한 코드","[4A102]","code에서 추출해 색인합니다. 현재 문서 검색에서 이 필드를 이용한 필터·가산점은 없습니다."],
      ["code_norm","정규화 코드","표기 차이를 정리한 코드","code에서 생성해 색인합니다. 현재 문서 검색에서 이 필드를 이용한 필터·가산점은 없습니다."]
    ]],
    ["검색 대상 본문 · 벡터",[
      ["title","문서 제목","전문판정 신청 안내","BM25 검색과 임베딩 입력, 사본 정리, 결과 및 답변 머리말에 사용합니다."],
      ["body","청크 본문","신청서와 확인서를 제출합니다.","BM25 검색과 임베딩 입력, 근거 선택 및 답변 생성에 사용합니다."],
      ["embedding","dense 벡터","제목·본문의 의미 벡터","의미가 가까운 청크를 찾습니다. 법령·행정은 제목 경로도 입력에 포함합니다."],
      ["splade","희소 벡터","검색 토큰 → 가중치","SPLADE 모델이 설정된 카테고리 색인에서 생성합니다. 토큰 가중치로 청크를 검색합니다."],
      ["title.standard / body.standard","보조 분석 필드","standard 분석기로 나눈 제목·본문","매핑에는 남아 있지만 현재 검색 쿼리에서는 사용하지 않습니다."]
    ]],
    ["파서 원본 · 추출 근거",[
      ["source_format","원본 파일 형식","pdf · hwp · hwpx","원본 형식을 보존합니다. 검색 필터·가산점과 SearchHit에는 미사용입니다."],
      ["chunk_count","문서의 전체 청크 수","12","문서가 몇 조각으로 나뉘었는지 보존합니다. 검색 필터·가산점에는 미사용입니다."],
      ["published_at_source","게시일 추출 출처","filename · body:<단서> · pdf_created","날짜를 어디서 찾았는지 기록합니다. PDF 생성일은 실제 게시일과 다를 수 있습니다. 현재 점수에서 신뢰도를 구분하지 않습니다."],
      ["published_at_precision","게시일 정밀도","day · month","날짜를 일 또는 월 단위까지 아는지 보존합니다. 현재 검색 필터·가산점에는 미사용입니다."],
      ["document.category","문서 분류","법령·고시 · 민원·FAQ","파서가 판단한 분류입니다. 선택한 카테고리 검색 경로와는 별개의 원본 속성입니다."],
      ["document.document_type / document.status","원본 유형 · 상태","고시 / 개정","법령 매핑에서는 doc_type / doc_status로 펼칩니다."],
      ["document.document_number / document.source","원본 번호 · 기관","제2026-598호 / 발행 기관","법령 매핑에서는 doc_number / issuer로 펼칩니다."],
      ["document.effective_date / document.expiry_date","원본 시행일 · 종료일","2026-09-01 / 종료 날짜","법령 매핑에서는 effective_from / effective_to로 펼칩니다."],
      ["document.revision_date / document.published_date","원본 개정일 · 게시일","개정일 / 파서가 읽은 게시일","개정일은 revision_date로 펼칩니다. published_date는 원본 객체에 보존하며 검색은 최상위 published_at을 읽습니다."],
      ["document.supersedes","이 문서가 대체하는 옛 판","이전 고시 번호 목록","새 판에서 옛 판을 가리키는 반대 방향 관계입니다. 원본에 보존하며 현재 직접 검색에 사용하지 않습니다."],
      ["document.superseded_by","이 문서를 대체하는 새 판","다음 판 고시 번호 또는 ID 목록","법령 매핑에서는 목록을 문자열로 합쳐 superseded_by에 넣습니다. 문서 ID로 연결 가능한 값인지 확인이 필요합니다."],
      ["document.parent_document","별표·서식의 부모 규정","부모 규정의 식별값","별표나 서식이 속한 규정의 연결 정보입니다. 원본에 보존하며 현재 검색·응답에는 미사용입니다."],
      ["document.inherited","부모 규정에서 상속한 속성","부모의 시행일·기관 등","상속한 값을 별도로 보존합니다. 현재 law_source가 이 객체를 검색 필드로 펼치지 않습니다."],
      ["document.evidence","속성 추출·추론 근거","addenda · corpus_link · inferred:same_title","본문 단서, 코퍼스 연결 또는 추론으로 얻은 값인지 기록합니다. 검색 필터·점수에는 미사용입니다."]
    ]],
    ["파서의 페이지 · 표 위치",[
      ["page_start / page_end","페이지 범위","3쪽 ~ 4쪽","청크가 나온 페이지입니다. 원본 _source에 보존하며 현재 SearchHit에는 포함하지 않습니다."],
      ["element_types","청크의 원소 종류","paragraph · table","문단·표 등의 구성을 보존합니다. 검색 필터·가산점에는 미사용입니다."],
      ["table_id / caption","표 ID · 표 제목","table-01 / 제출 서류","표를 식별하고 같은 표의 청크를 연결할 수 있는 원본 정보입니다."],
      ["columns / row_count","표의 열 · 행 수","[서류명, 제출 대상] / 5","표 구조를 보존합니다. 검색은 이 속성보다 청크 본문을 사용합니다."],
      ["row_id / row_index / values","표 행의 ID · 순서 · 값","row-01 / 0 / 행의 셀 값","표의 특정 행을 복원할 수 있는 정보입니다. 현재 별도 검색 필드로 사용하지 않습니다."],
      ["column / piece_index / piece_count","긴 표 칸의 분할 정보","열 이름 / 조각 순서 / 총 조각 수","긴 셀을 나눈 조각들의 위치를 보존합니다. 현재 검색 결과 모델에는 포함하지 않습니다."],
      ["article","대비표 조문 번호","제39조의3","같은 조문의 현행·개정안 조각을 연결하는 원본 정보입니다. 현재 필터·가산점에는 미사용입니다."]
    ]],
    ["검색 뒤에 생성되는 결과 정보",[
      ["score","검색 점수","검색기별 점수 또는 융합 점수","검색 순위에 사용합니다. 서로 다른 검색기의 점수는 같은 척도가 아닙니다."],
      ["passages","같은 문서의 추가 근거","id · body · score · relevance","선택한 문서 안의 다른 청크를 함께 반환합니다. 답변에는 구분자를 넣어 전달합니다."],
      ["chunk_relevance","대표 청크 관련성 판정","0 무관 / 1 일부 / 2 답 포함","관련성 판정을 실행한 경우 채워지는 결과 값입니다. 실행하지 않으면 비어 있습니다."],
      ["passages[].relevance","추가 청크 관련성 판정","0 / 1 / 2","추가 근거 청크별 판정 결과입니다. 판정을 실행하지 않으면 비어 있습니다."]
    ]]
  ];
  // 이름을 바꿔 검색 필드로 옮기는 속성은 해당 검색 필드 행에서 한 번만 설명합니다.
  var copiedInputs=["document.document_type / document.status","document.document_number / document.source","document.effective_date / document.expiry_date","document.superseded_by"];
  var raw=groups[5][1].filter(function(r){return copiedInputs.indexOf(r[0])===-1;}).map(function(r){
    return r[0]==="document.revision_date / document.published_date"?["document.published_date","원본 객체의 게시일","2026-09-04","원본 객체에 보관합니다. 검색 가산점·사본 정리는 최상위 published_at을 사용합니다."]:r;
  });
  var selected=[groups[1],groups[2],groups[3],groups[0],groups[4],["파서 추출 근거 · 원본 보관",raw],groups[6],groups[7]];
  var retained=["date_basis","source_path","source_format","chunk_count","published_at_source","published_at_precision","page_start / page_end","element_types","table_id / caption","columns / row_count","row_id / row_index / values","column / piece_index / piece_count","article"];
  return '<section class="meta-catalog meta-lineage" aria-labelledby="cm-catalog"><h2 id="cm-catalog">파서 메타데이터 → 검색엔진 적용</h2><p class="cap">각 행에서 파서가 만든 정보가 어떤 검색 필드로 넘어가고, 필터·순위·근거·답변에 어떻게 쓰이는지 확인할 수 있습니다.</p>'+selected.map(function(g){
    return '<h3>'+g[0]+'</h3><div class="meta-field-scroll meta-lineage-table"><table><thead><tr><th>파서·입력 → 검색엔진</th><th>적용 방식</th><th>검색·답변에서 하는 일</th></tr></thead><tbody>'+g[1].map(function(r){
      var t=categorySearchFieldTransform(r[0],r[2]);
      var keep=r[0].indexOf("document.")===0||retained.indexOf(r[0])!==-1;
      var output=keep?'원본 _source에 보관':r[0];
      var detail='<div class="meta-lineage-detail"><div class="meta-lineage-values"><div><span>입력</span><code>'+esc(t[1])+'</code></div><div><span>결과</span><code>'+esc(t[2])+'</code></div></div></div>';
      return '<tr><td data-label="파서·입력 → 검색엔진"><strong class="meta-lineage-name">'+esc(r[1])+'</strong><div class="meta-field-link"><code>'+esc(t[0])+'</code><span aria-hidden="true">↓</span><code>'+esc(output)+'</code></div></td><td data-label="적용 방식"><span class="meta-transform-kind">'+esc(keep?'원본 보관':t[4])+'</span><p class="meta-lineage-rule">'+esc(t[3])+'</p>'+detail+'</td><td data-label="검색·답변에서 하는 일">'+esc(r[3])+'</td></tr>';
    }).join('')+'</tbody></table></div>';
  }).join('')+'<p class="cap">예시는 설명용입니다. 원본에 보관된 필드는 검색 전용 필드나 응답에 자동으로 추가되지 않습니다. 빈 문서 속성은 검색 필드로 펼치지 않으며, 현재 사용하지 않는 값도 각 행에 표시했습니다.</p></section>';

}

/* 공통 메타데이터: 파서 산출물이 검색 필드로 넘어가는 경로와, 카테고리 검색(SPLADE + dense)이
   그 값을 실제로 쓰는 지점. 세 카테고리가 같은 코드 경로를 쓰므로 공통으로 둔다.
   카테고리마다 다른 채움 현황은 각 카테고리 탭의 메타데이터 보기에 있다. */
function categoryMetadataUse(){
  return '<h2 id="cm-use">카테고리 검색이 메타데이터를 쓰는 곳</h2>'+
    '<p class="cap">카테고리 검색은 SPLADE와 dense만 씁니다. 법령 SPLADE는 46단계에서 <code>function_score</code>로 제목 경로의 명시 근거와 본문의 통제번호·대상 항목 일치에 가산점을 줍니다. 유효기간·문서 번호 필터와 사본·판본 정리도 적용합니다. docs 검색에는 별도의 BM25 가산점이 있습니다.</p><div class="meta-use-grid">'+
    '<article class="meta-use-card"><span class="meta-role">후보 거르기</span><h3>기간 필터</h3><p>기준일에 유효한 문서인지 확인합니다.</p><div class="meta-fields-used"><span class="meta-fields-label">쓰는 필드</span><div class="meta-fields-chips"><code>effective_from</code><code>effective_to</code></div><p class="meta-fields-note">파서의 <code>document.effective_date</code>·<code>document.expiry_date</code>를 이름만 바꿔 받은 청크 필드입니다. 기준일은 메타데이터가 아니라 검색하는 날짜입니다.</p></div><div class="meta-demo"><div class="meta-demo-label">유효기간이 있는 문서</div><div class="meta-period"><div class="meta-date"><span>시행일</span><strong>2025.01</strong></div><div class="meta-date meta-date-now"><span>기준일</span><strong>2026.06</strong></div><div class="meta-date"><span>종료일</span><strong>2027.01</strong></div></div><div class="meta-outcome"><span class="meta-check" aria-hidden="true">✓</span>기간 안에 있음 <span aria-hidden="true">→</span> 검색 대상</div><div class="meta-demo-foot">날짜 정보가 없는 문서도 통과합니다.</div></div><p class="meta-use-note">시행일 ≤ 기준일 &lt; 종료일. SPLADE와 dense에 똑같은 조건을 겁니다. 현재 세 카테고리 자료에는 종료일 값이 없어 실제로는 시행일만 거릅니다.</p></article>'+
    '<article class="meta-use-card"><span class="meta-role">후보 거르기</span><h3>고시·공고 번호 필터</h3><p>질문에 번호가 적혀 있으면 그 번호가 든 청크만 남깁니다.</p><div class="meta-fields-used"><span class="meta-fields-label">쓰는 필드</span><div class="meta-fields-chips"><code>doc_number_norm</code><code>title</code><code>body</code></div><p class="meta-fields-note">질문에서 읽어 낸 번호를 제목·본문 구절과 맞추거나, 정규화한 문서 번호 <code>doc_number_norm</code>(파서 <code>document.document_number</code>에서 연도-일련번호만 남긴 값)과 맞춥니다. 셋 중 하나만 맞으면 통과합니다.</p></div><div class="meta-demo"><div class="meta-query"><span aria-hidden="true">“</span><strong>제2026-598호</strong> 개정 내용 알려줘<span aria-hidden="true">”</span></div><div class="meta-score-row"><span class="meta-doc-symbol" aria-hidden="true"></span><div><strong>제2026-598호 고시</strong><span>제목·본문에 번호 있음</span></div><span class="meta-check" aria-hidden="true">✓</span></div><div class="meta-score-row meta-score-neutral"><span class="meta-doc-symbol" aria-hidden="true"></span><div><strong>제2026-590호 고시</strong><span>번호가 다름 <span aria-hidden="true">→</span> 후보에서 제외</span></div></div><div class="meta-demo-foot">질문에 번호가 없으면 이 필터를 걸지 않습니다.</div></div><p class="meta-use-note">번호는 관련도가 아니라 어느 문서인지를 가리키므로 가산점이 아니라 필터로 둡니다. dense는 네 자리 일련번호를 거의 구별하지 못해(590호와 598호가 코사인으로 갈리지 않음) 같은 필터를 함께 겁니다. 번호가 머리말 청크에만 남은 문서 때문에 제목·본문 구절뿐 아니라 문서 번호 필드로도 지목합니다. 원문 표기 그대로인 <code>doc_number</code>는 색인하지 않아(<code>index: false</code>) 대조에 쓰지 않습니다.</p></article>'+
    '<article class="meta-use-card meta-use-green"><span class="meta-role">검색 입력에 포함</span><h3>제목 경로</h3><p>본문이 문서의 어느 부분인지 함께 알려줍니다.</p><div class="meta-fields-used"><span class="meta-fields-label">쓰는 필드</span><div class="meta-fields-chips"><code>heading_path</code><code>title</code><code>body</code></div><p class="meta-fields-note">파서가 조문·절 경로를 배열로 준 것을 법령·행정 인덱스에만 두는 필드입니다. 질의가 직접 찾는 필드는 <code>title</code>·<code>body</code>뿐이고, 경로는 색인할 때 제목 앞에 붙여 검색기 입력으로 들어갑니다.</p></div><div class="meta-demo"><div class="meta-demo-label">문서 안의 위치</div><div class="meta-breadcrumb"><span>수출허가</span><span aria-hidden="true">›</span><span>신청 절차</span><span aria-hidden="true">›</span><strong>제출 서류</strong></div><div class="meta-down" aria-hidden="true">↓</div><div class="meta-chunk"><div class="meta-chunk-heading">수출허가 / 신청 절차 / 제출 서류</div><div class="meta-chunk-body">신청서와 최종 사용자 확인서를 제출합니다.</div></div><div class="meta-demo-foot">제목 경로 + 본문 <span aria-hidden="true">→</span> SPLADE · dense 입력</div></div><p class="meta-use-note">메타데이터 중 유일하게 검색 점수 자체에 닿을 수 있는 값입니다. 다만 경로를 입력에 넣을지는 색인 옵션(<code>SEARCH_DENSE_INCLUDE_HEADING_PATH</code>·<code>SEARCH_SPLADE_INCLUDE_HEADING_PATH</code>)이고, 현재 코드 기본값은 둘 다 꺼짐입니다. 42단계 비교 결과와 재색인 이력은 단계별 기록에서 봅니다.</p></article>'+
    '<article class="meta-use-card meta-use-green meta-supersession" id="cm-superseded"><span class="meta-role">결과 정리</span><h3>문서 대체 관계 <code>superseded_by</code></h3><p>이 문서를 대체하는 새 판이 확인되면, 그 문서의 ID를 옛 판에 기록합니다.</p><div class="meta-fields-used"><span class="meta-fields-label">쓰는 필드</span><div class="meta-fields-chips"><code>superseded_by</code><code>parent_id</code></div><p class="meta-fields-note">옛 판의 <code>superseded_by</code> 값으로 새 판을 <code>parent_id</code>로 한 번 더 조회해 결과에 끼워 넣습니다. 문서 ID로 연결된 값에만 이 동작이 적용됩니다. 법령의 고시·대통령령 번호를 문서 ID로 푸는 45단계 실험은 적용하지 않았습니다.</p></div><div class="meta-supersession-examples"><div class="meta-demo"><div class="meta-demo-label">연결 구조 · 설명용 예시</div><div class="meta-storage"><span class="meta-doc-symbol" aria-hidden="true"></span><div><strong>2021년 전문판정 신청서 · 옛 판</strong><span>문서 ID: form-2021</span></div></div><div class="meta-replacement-link"><code>superseded_by = form-2026</code><span aria-hidden="true">↓</span></div><div class="meta-storage"><span class="meta-doc-symbol" aria-hidden="true"></span><div><strong>2026년 개정 전문판정 신청서 · 새 판</strong><span>문서 ID: form-2026</span></div></div><div class="meta-demo-foot">단순히 나중에 올라온 문서가 아니라, 같은 문서를 대체하는 판을 연결합니다.</div></div><div class="meta-demo"><div class="meta-demo-label">검색 결과에 쓰이는 방식</div><div class="meta-query">“2021년 전문판정 신청서 찾아줘”</div><ol class="meta-edition-results"><li><strong>2021년 전문판정 신청서</strong><span>찾던 옛 판 · 대체된 문서</span></li><li><strong>2026년 개정 전문판정 신청서</strong><span>연결된 새 판을 바로 뒤에 추가</span></li></ol><div class="meta-demo-foot">새 판이 이미 결과에 있으면 중복 추가하지 않으며, 반환 문서 수 상한(5문서) 안에서 처리합니다.</div></div></div><p class="meta-use-note">순위를 바꾸지 않고, 고른 결과 뒤에 새 판을 덧붙이기만 합니다. 대체된 문서의 청크 점수를 낮추는 가중치는 있지만 현재 0.97입니다(판본을 지정한 질문은 감점하지 않음). 값이 비어 있다는 것은 대체 관계가 기록되지 않았다는 뜻이며, 새 판이 없다는 보장은 아닙니다. 위 그림은 동작 설명용으로, 현재 카테고리 자료의 실제 검색 결과가 아닙니다.</p></article>'+
    '</div>';
}
function renderCategoryCommonMeta(){
  var items=[["cm-catalog","파서 → 검색엔진 적용"],["cm-use","검색에서 쓰는 곳"],["cm-superseded","옛 판과 새 판"]];
  document.getElementById("stnav").innerHTML=items.map(function(x){return '<button type="button" data-go2="'+x[0]+'"><span class="nl">공통 · 메타데이터</span><span class="nt">'+x[1]+'</span></button>';}).join("");
  document.getElementById("detail").innerHTML='<div class="em"><div class="sv-h"><span class="sl">카테고리별 검색 · 공통</span><h2 class="big">메타데이터가 검색에 들어가는 길</h2></div>'+
    '<p class="note">파서가 뽑은 문서 속성이 어떤 검색 필드가 되고, 카테고리 검색이 그중 무엇을 실제로 쓰는지 정리했습니다. 세 카테고리가 같은 색인 규칙·같은 검색 경로를 쓰므로 공통으로 둡니다. 카테고리마다 다른 <b>채움 현황</b>은 각 카테고리 탭의 메타데이터 보기에 있습니다.</p>'+
    categoryMetadataCatalog()+categoryMetadataUse()+'</div>';
  document.getElementById("detail").scrollTop=0;
}
