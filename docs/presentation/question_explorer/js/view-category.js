var CATSEL="law50";
var CINFO={
  law50:{id:"cat-law50",tab:"법령·고시",full:"법령·고시 (50건 · 50문항)",head:"법령·고시 50건 · 50문항",
    corpus:'파서의 <code>01_법령고시</code> <b>50건·2,138청크</b>입니다. 정답 청크는 50건 전체에서 필수 구절을 모두 담은 청크라서, 같은 문장이 다른 판에 있으면 그 청크도 정답입니다. 유형은 일상어 41, 식별자 5, 별표 2, 신구대비 2입니다. 질문 파일은 <code>data/queries_law50_v1.jsonl</code>입니다.'},
  admin30:{id:"cat-admin",tab:"행정·업무",full:"행정·업무 (20건 · 30문항)",head:"행정·업무 20건 · 30문항",
    corpus:'<code>02_행정업무</code> 20건·183청크(표 포함 청크 59%, hwp5에서 나온 청크 175개)입니다. 질문은 일상어 16, 식별정보 6, 표·서식 8입니다.'},
  faq30:{id:"cat-faq",tab:"민원FAQ",full:"민원FAQ (20건 · 30문항)",head:"민원FAQ 20건 · 30문항",
    corpus:'<code>03_민원FAQ</code> 20건·187청크입니다. 전략기술 무형이전 FAQ 78청크, 판정 FAQ 37청크, 상무부 세미나 Q&amp;A 28청크, 정기보고 FAQ 11청크, 주요 질의응답 11청크와 Q 번호 문서·서식입니다. 질문은 일상어 22, 식별자 4, 표 행 4이고, 질문 파일은 <code>data/queries_faq_v1.jsonl</code>, 필수 구절은 <code>scripts/law/faq_specs.py</code>에 있습니다.'}
};
var CNAME=["SPLADE","dense","hybrid"];
function catRank(r){ return r==null?'<span class="cc x">놓침</span>':'<span class="cc '+(r===1?'a':'b')+'">'+r+'위</span>'; }
function catRows(k){
  return CATD[k].map(function(x){
    var miss=x.r.some(function(r){return r==null;});
    return '<tr class="'+(miss?'m':'ok')+'"><td>'+x.i+'</td><td>'+esc(x.c)+'</td><td class="qq">'+esc(x.q)+'</td><td>'+x.n+'</td><td>'+catRank(x.r[0])+'</td><td>'+catRank(x.r[1])+'</td><td>'+catRank(x.r[2])+'</td></tr>';
  }).join("");
}
function catTable(k){
  return '<label class="onlym"><input type="checkbox" onchange="this.closest(\'.em\').classList.toggle(\'onlymiss\',this.checked)"> 한 모드라도 놓친 질문만 보기</label>'+
  '<table class="catq"><thead><tr><th>번호</th><th>유형</th><th>질문</th><th>정답<br>청크</th><th>SPLADE</th><th>dense</th><th>hybrid</th></tr></thead><tbody>'+catRows(k)+'</tbody></table>';
}
function pct(x){ return (x*100).toFixed(0)+"%"; }
function f3(x){ return x.toFixed(3); }
function catStats(k){
  var d=CATD[k], n=d.length, out={n:n, m:[], miss:[[],[],[]]};
  [0,1,2].forEach(function(m){
    var hit=0, top=0, mrr=0;
    d.forEach(function(x){ var r=x.r[m]; if(r!=null){ hit++; mrr+=1/r; if(r===1) top++; } else out.miss[m].push(x.i); });
    out.m.push({rec:hit/n, hit:hit, top:top, mrr:mrr/n});
  });
  // Precision: 반환 청크 중 Sonnet이 관련(판정 1 이상)으로 본 청크 비율의 질문 평균
  var rets=[ function(f){ return [].concat.apply([],f.sp.ret).map(function(c){return c[2]>=1;}); },
             function(f){ return [].concat.apply([],f.dn.ret).map(function(c){return c[2]>=1;}); },
             function(f){ return [].concat.apply([],f.ret.map(function(r){return r.ch;})).map(function(c){return c[4]>=1;}); } ];
  rets.forEach(function(fn,m){
    var ps=0; d.forEach(function(x){ var g=fn(CATH[k][x.i].fx); if(g.length) ps+=g.filter(function(v){return v;}).length/g.length; });
    out.m[m].prec=ps/n;
  });
  // 문서 지표: SPLADE는 원순위 상위 5문서, dense는 컷 통과 문서 상위 5개, hybrid는 컷오프 뒤 반환 문서
  var docs=[ function(f){ return f.sp.rows.slice(0,5).map(function(r){return r[4];}); },
             function(f){ return f.dn.rows.filter(function(r){return r[3]===1;}).slice(0,5).map(function(r){return r[4];}); },
             function(f){ return f.ret.map(function(r){return r.g;}); } ];
  docs.forEach(function(fn,m){
    var p1=0, hit=0, g=0, t=0;
    d.forEach(function(x){ var l=fn(CATH[k][x.i].fx); if(l[0]) p1++; if(l.some(function(v){return v;})) hit++; g+=l.filter(function(v){return v;}).length; t+=l.length; });
    var o=out.m[m]; o.p1=p1/n; o.dhit=hit/n; o.retp=t?g/t:0; o.ret=t/n;
  });
  out.fin=d.filter(function(x){ return cqRet(CATH[k][x.i]).chunk; }).length;
  return out;
}
function catList(a){ return a.length?a.join(", "):"없음"; }
function catTbl(st){
  var best=Math.max.apply(null,st.m.map(function(x){return x.rec;})), bm=Math.max.apply(null,st.m.map(function(x){return x.mrr;}));
  return '<table><thead><tr><th>방식</th><th>청크 Recall</th><th>1위 청크 적중</th><th>청크 MRR</th><th>Precision</th></tr></thead><tbody>'+
    [1,0,2].map(function(m){ var o=st.m[m]; var nm=["SPLADE","dense","hybrid (SPLADE + dense)"][m];
      return '<tr><td>'+nm+'</td><td>'+(o.rec===best?'<b>'+f3(o.rec)+'</b>':f3(o.rec))+'</td><td>'+o.top+'/'+st.n+'</td><td>'+(o.mrr===bm?'<b>'+f3(o.mrr)+'</b>':f3(o.mrr))+'</td><td>'+f3(o.prec)+'</td></tr>'; }).join("")+'</tbody></table>'+
    '<p class="cap">Precision은 반환한 청크 중 질문과 관련 있는 청크의 비율(질문 평균)입니다. 관련 여부는 정답 청크가 아니라 Sonnet이 청크마다 질문과 본문만 보고 매긴 판정(2 답을 담음, 1 일부 담음, 0 무관)의 1 이상입니다. 세 방식 모두 청크 단위 RRF 또는 청크 순위를 1위 점수 대비 비율로 자른 기준입니다(청크 최대 10개, 문서 최대 5개, 문서당 최대 6개): hybrid 95%, SPLADE 80%, dense 93%. 비율은 이 질문 110개에서 Recall을 지키며 Precision이 오르는 지점을 찾은 값이라 과적합 위험이 있습니다.</p>';
}
function catSummary(k){
  var st=catStats(k), M=st.m, info=CINFO[k], allFound=M.every(function(o){return o.hit===st.n;});
  var li=[];
  if(allFound){
    li.push('<li>세 방식 모두 질문 '+st.n+'개의 정답 청크를 상위 5청크 안에서 전부 찾았습니다. 이 질문셋으로는 청크 Recall로 방식을 가를 수 없습니다.</li>');
  } else {
    li.push('<li>상위 5청크 안에서 정답 청크를 찾은 비율은 SPLADE '+pct(M[0].rec)+', dense '+pct(M[1].rec)+', hybrid '+pct(M[2].rec)+'입니다. 놓친 질문은 SPLADE '+st.miss[0].length+'개, dense '+st.miss[1].length+'개, hybrid '+st.miss[2].length+'개입니다.</li>');
    var spOnly=st.miss[0].filter(function(i){return st.miss[1].indexOf(i)<0;}), dnOnly=st.miss[1].filter(function(i){return st.miss[0].indexOf(i)<0;}), both=st.miss[0].filter(function(i){return st.miss[1].indexOf(i)>=0;});
    if(spOnly.length||dnOnly.length) li.push('<li>SPLADE와 dense는 서로 다른 질문을 놓칩니다. SPLADE만 놓친 질문은 '+catList(spOnly)+', dense만 놓친 질문은 '+catList(dnOnly)+', 둘 다 놓친 질문은 '+catList(both)+'입니다.</li>');
    else li.push('<li>SPLADE와 dense가 놓친 질문이 같습니다('+catList(both)+').</li>');
  }
  li.push('<li>정답 청크를 1위에 올린 질문은 SPLADE '+M[0].top+'개, dense '+M[1].top+'개, hybrid '+M[2].top+'개이고, 청크 MRR은 '+f3(M[0].mrr)+' / '+f3(M[1].mrr)+' / '+f3(M[2].mrr)+'입니다.'+(M[2].mrr<Math.max(M[0].mrr,M[1].mrr)?' 이 묶음에서는 합쳤을 때 순위가 오히려 낮아졌습니다.':(M[2].mrr>Math.max(M[0].mrr,M[1].mrr)?' 합쳤을 때 순위가 가장 높습니다.':''))+'</li>');
  li.push('<li>컷오프를 거친 최종 반환에 정답 청크가 실린 질문은 '+st.fin+'/'+st.n+'개입니다.</li>');
  return '<div class="card"><h2 class="ch">'+info.full+'</h2>'+catTbl(st)+'<ul class="cl">'+li.join("")+'</ul></div>';
}
function catDetail(k){
  var st=catStats(k), M=st.m, info=CINFO[k];
  var row=function(m){ var o=M[m]; return '<tr><td>'+["SPLADE","dense","hybrid (SPLADE + dense)"][m]+'</td><td>'+f3(o.rec)+'</td><td>'+o.top+'/'+st.n+'</td><td>'+f3(o.mrr)+'</td><td>'+f3(o.prec)+'</td><td>'+f3(o.p1)+'</td><td>'+f3(o.dhit)+'</td><td>'+f3(o.retp)+'</td><td>'+o.ret.toFixed(2)+'</td></tr>'; };
  return '<h2 id="'+info.id+'">'+info.head+'</h2>'+
  '<p class="note"><b>코퍼스.</b> '+info.corpus+'</p>'+
  '<table><thead><tr><th>방식</th><th>청크 Recall</th><th>1위 청크 적중</th><th>청크 MRR</th><th>Precision</th><th>문서 P@1</th><th>문서 Hit@5</th><th>반환분 문서 Precision</th><th>평균 반환 문서</th></tr></thead><tbody>'+row(1)+row(0)+row(2)+'</tbody></table>'+
  '<p class="cap">문서 지표는 진단용입니다. SPLADE는 원순위 상위 5문서, dense는 1위의 97% 이상인 문서(최대 5), hybrid는 청크 컷오프 뒤 반환 청크가 딸린 문서 기준입니다. Precision은 Sonnet 판정 1 이상을 관련으로 셉니다(판정은 기존 정답 청크의 83%를 2로 봤습니다). 놓친 질문은 SPLADE '+catList(st.miss[0])+', dense '+catList(st.miss[1])+', hybrid '+catList(st.miss[2])+'입니다. 놓친 질문 하나하나의 원인은 읽어서 확인하지 않았습니다.</p>'+
  catTable(k);
}
function catRead(){
  var big=CQ.filter(function(x){return x.n>=10;}).map(function(x){return x.id+'('+x.n+'개)';});
  return '<h2 id="cat-read">읽는 법과 한계</h2><ul class="cl">'+
    '<li>질문 수가 30~50개라 <b>한 문항이 0.02~0.03</b>입니다. 방식 간 차이가 2~3문항 안쪽이면 순서를 단정하지 않습니다.</li>'+
    '<li>질문은 본문을 본 사람이 쓴 것이라 실제 이용자의 말투보다 본문과 가깝습니다. 사람 검수를 거치지 않았고, 필수 구절이 본문에 있는지만 코드가 확인했습니다.</li>'+
    (big.length?'<li>정답 청크가 10개 이상인 질문은 청크 Recall이 느슨하게 나옵니다: '+big.join(", ")+'.</li>':'')+
    '<li>모두 오프라인 측정이라 카테고리 경로의 운영 컷오프와 필터를 거치지 않았고, 순위는 상위 5청크 기준입니다. 서비스가 실제로 돌려주는 창과 다릅니다.</li>'+
    '<li>BM25는 이 탭에서 더 이상 재지 않습니다. 이전 BM25·dense·hybrid 측정과 직접 비교하지 마세요.</li>'+
    '<li>색인은 2026-10-06에 파서 산출물로 다시 만들었습니다. 법령·고시 코퍼스는 같은 날 파서에서 다시 올라와(2,151 → 2,138청크) 정답 청크를 현재 청크 기준으로 다시 붙여 재측정했습니다.</li>'+
  '</ul>';
}
function panelCat(){
  var k=CATSEL;
  return '<div class="em">'+
  '<p class="note">카테고리 검색은 법령·고시, 행정·업무, 민원FAQ를 각자 인덱스에서 따로 찾는 경로입니다. 질문마다 <b>필수 구절</b>을 적고 그 구절을 모두 담은 청크를 정답 청크로 코드가 찾아 붙였습니다. <b>질문은 정답을 아는 사람(Claude)이 본문을 보고 쓴 점검용이라 성능 판단에는 쓰지 않습니다.</b> 아래 수치는 모두 같은 오프라인 조건입니다: <b>SPLADE는 38단계에서 합성 질의 2,702개로 파인튜닝한 모델</b>, dense는 BGE-m3-ko, hybrid는 SPLADE와 dense를 <b>청크 단위 RRF(k=60)</b>로 합친 뒤 1위 점수의 95% 컷오프로 자른 것이고, 청크 Recall은 <b>상위 5청크</b> 안에서 정답 청크를 찾았는지로 셉니다. LLM 필터·답변 가능성 판정·리랭커 없음, 기준일 2026-10-06. 서비스 코드에는 SPLADE가 붙어 있지 않습니다.</p>'+
  '<h2 id="cat-sum">결론부터</h2>'+catSummary(k)+
  '<p class="cap">질문이 30~50개라 한 문항이 0.02~0.03입니다. 방식 간 차이가 1~2문항이면 순서를 단정하지 않습니다. 문서 단위 지표와 질문별 결과는 아래에 있습니다.</p>'+
  catDetail(k)+catRead()+
  '</div>';
}
function renderCat(){
  var nav=document.getElementById("stnav"), info=CINFO[CATSEL], det=[info.id,info.head];
  var items=[["cat-sum","결론부터"],det,["cat-read","읽는 법과 한계"]];
  nav.innerHTML=items.map(function(x){ return '<button type="button" data-go2="'+x[0]+'"><span class="nl">결과 요약</span><span class="nt">'+x[1]+'</span></button>'; }).join("");
  var el=document.getElementById("detail"); el.innerHTML=panelCat(); el.scrollTop=0;
}

function renderCategorySelector(){
  var sw=document.getElementById("catsw");
  sw.style.gridTemplateColumns="repeat(3,1fr)";
  sw.innerHTML=Object.keys(CINFO).map(function(o){ return '<button type="button" data-catsel="'+o+'" aria-pressed="'+(CATSEL===o)+'">'+CINFO[o].tab+'</button>'; }).join("");
  sw.onclick=function(e){
    var b=e.target.closest("button[data-catsel]");
    if(!b||b.dataset.catsel===CATSEL) return;
    CATSEL=b.dataset.catsel;
    if(st.view==="cq"){
      CQS.set=CATSEL;
      var first=CQ.filter(function(x){return x.set===CATSEL;})[0];
      if(first) CQS.id=first.id;
    }
    setView(st.view);
  };
}

var CMETA={
  law50:{docs:50,chunks:2160,heading:33,type:38,status:21,number:12,effective:18,expiry:0,revision:10,issuer:20,published:17,
    intro:"법령·고시 문서에는 유형·상태·기관 정보가 비교적 많이 들어 있고, 고시 번호·시행일은 일부 문서에만 있습니다."},
  admin30:{docs:20,chunks:183,heading:17,type:5,status:4,number:0,effective:0,expiry:0,revision:0,issuer:2,published:3,
    intro:"행정·업무 문서는 대부분 일반 안내·서식입니다. 문서 유형·상태·기관·게시일은 소수만 채워져 있고, 시행일·고시 번호는 없습니다."},
  faq30:{docs:19,chunks:187,heading:15,type:12,status:0,number:0,effective:0,expiry:0,revision:0,issuer:4,published:2,
    intro:"민원FAQ 문서는 유형(주로 FAQ)과 일부 출처 정보가 있습니다. 상태·번호·유효기간 정보는 현재 자료에서 확인되지 않았습니다."}
};
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
    date_basis:["date_basis / 유효기간·게시일","시행일 있음 / 게시일만 있음 / 날짜 없음","effective / publication_only / undated","파서 출력값을 보존하거나 core 준비 경로에서 날짜 필드로 계산","보존 또는 생성"],
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
      ["date_basis","날짜 판단 근거","effective / publication_only / undated","유효기간 있음 / 게시일만 있음 / 날짜 없음의 구분입니다. 준비 과정에서 생성하고 응답에 보존합니다."]
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
  var retained=["source_path","source_format","chunk_count","published_at_source","published_at_precision","page_start / page_end","element_types","table_id / caption","columns / row_count","row_id / row_index / values","column / piece_index / piece_count","article"];
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
function renderCategoryMeta(){
  var k=CATSEL, info=CINFO[k], m=CMETA[k], nav=document.getElementById("stnav");
  var rows=[
    ["문서 유형",m.type,"document.document_type","규정·지침·FAQ 등"],
    ["상태",m.status,"document.status","안·현행 등 문서 상태"],
    ["문서 번호",m.number,"document.document_number","고시·공고 식별 번호"],
    ["시행일",m.effective,"document.effective_date","시행일이 있으면 기준일 필터·기간 가산에 사용"],
    ["종료일",m.expiry,"document.expiry_date","현재 세 카테고리 자료에는 값 없음"],
    ["개정일",m.revision,"document.revision_date","메타데이터로 보관; 검색 점수에는 미사용"],
    ["발행 기관",m.issuer,"document.source","메타데이터로 보관; 검색 점수에는 미사용"],
    ["게시일",m.published,"published_at","기간을 묻는 검색의 가산 신호"],
    ["제목 경로",m.heading,"heading_path","청크 제목·dense 임베딩에 함께 반영"],
    ["문서 대체 관계",null,"document.superseded_by","파서가 연결한 새 판의 식별값. 현재 채움률은 미집계"]
  ];
  nav.innerHTML=[["cm-overview","요약"],["cm-fields","필드별 채움"],["cm-catalog","파서 → 검색엔진 적용"],["cm-use","검색에서 쓰는 곳"],["cm-superseded","옛 판과 새 판"]].map(function(x){return '<button type="button" data-go2="'+x[0]+'"><span class="nl">메타데이터</span><span class="nt">'+x[1]+'</span></button>';}).join("");
  var table='<table><thead><tr><th>항목</th><th>채워진 문서</th><th>파서 원본 필드</th><th>설명</th></tr></thead><tbody>'+rows.map(function(r){return '<tr><td>'+r[0]+'</td><td>'+(r[1]===null?'미집계':'<b>'+r[1]+' / '+m.docs+'</b> ('+Math.round(r[1]*100/m.docs)+'%)')+'</td><td><code>'+r[2]+'</code></td><td>'+r[3]+'</td></tr>';}).join("")+'</tbody></table>';
  document.getElementById("detail").innerHTML='<div class="em">'+
    '<h2 id="cm-overview">'+info.tab+' 메타데이터</h2><p class="note">'+m.intro+'</p><div class="tiles">'+
    '<div class="tile"><span class="tl1">문서</span><span class="tv">'+m.docs+'<small>건</small></span></div><div class="tile"><span class="tl1">청크</span><span class="tv">'+m.chunks.toLocaleString()+'<small>개</small></span></div><div class="tile"><span class="tl1">heading_path</span><span class="tv">'+m.heading+'<small>건</small></span></div></div>'+ 
    '<h2 id="cm-fields">파서 산출물 · 채움 현황</h2><p class="cap">문서별 중복을 제거해 세었습니다. 각 청크의 반복 메타데이터가 아니라 부모 문서 기준입니다. 원본은 <code>'+info.corpus.match(/<code>([^<]+)/)[1]+'</code> 파서 산출물입니다.</p>'+table+categoryMetadataCatalog()+
    '<h2 id="cm-use">검색 과정 · 동작 예시</h2>'+(k==="faq30"?'<p class="warn">민원FAQ는 이 탐색기의 오프라인 평가 코퍼스입니다. 현재 API 카테고리 검색 경로에는 법령·고시와 행정·업무만 등록돼 있습니다.</p>':'')+'<p class="cap">정보마다 역할이 다릅니다. 아래 그림은 각 정보가 검색에 쓰이는 방식을 보여주는 예시입니다.</p><div class="meta-use-grid">'+
    '<article class="meta-use-card"><span class="meta-role">검색 대상 판단</span><h3>기간 필터</h3><p>기준일에 유효한 문서인지 확인합니다.</p><div class="meta-demo"><div class="meta-demo-label">유효기간이 있는 문서</div><div class="meta-period"><div class="meta-date"><span>시행일</span><strong>2025.01</strong></div><div class="meta-date meta-date-now"><span>기준일</span><strong>2026.06</strong></div><div class="meta-date"><span>종료일</span><strong>2027.01</strong></div></div><div class="meta-outcome"><span class="meta-check" aria-hidden="true">✓</span>기간 안에 있음 <span aria-hidden="true">→</span> 검색 대상</div><div class="meta-demo-foot">날짜 정보가 없는 문서도 통과합니다.</div></div><p class="meta-use-note">시행일·종료일 값이 있을 때 유효기간을 확인합니다.</p></article>'+
    '<article class="meta-use-card"><span class="meta-role">검색 점수에 반영</span><h3>기간 가산</h3><p>질문 속 연·월을 문서 날짜와 비교합니다.</p><div class="meta-demo"><div class="meta-query"><span aria-hidden="true">“</span><strong>2025년</strong> 수출허가 안내는?<span aria-hidden="true">”</span></div><div class="meta-score-row"><span class="meta-doc-symbol" aria-hidden="true"></span><div><strong>2025년에 게시된 안내</strong><span>질문의 연도와 일치</span></div><span class="meta-score-plus">+ 가산</span></div><div class="meta-score-row meta-score-neutral"><span class="meta-doc-symbol" aria-hidden="true"></span><div><strong>2023년에 게시된 안내</strong><span>질문의 연도와 다름</span></div></div><div class="meta-demo-foot">게시일·시행일이 점수 신호가 될 수 있습니다.</div></div><p class="meta-use-note">날짜 외에도 본문 관련성 등이 최종 순위에 함께 작용합니다.</p></article>'+
    '<article class="meta-use-card meta-use-green"><span class="meta-role">본문에 맥락 추가</span><h3>제목 경로</h3><p>본문이 문서의 어느 부분인지 함께 알려줍니다.</p><div class="meta-demo"><div class="meta-demo-label">문서 안의 위치</div><div class="meta-breadcrumb"><span>수출허가</span><span aria-hidden="true">›</span><span>신청 절차</span><span aria-hidden="true">›</span><strong>제출 서류</strong></div><div class="meta-down" aria-hidden="true">↓</div><div class="meta-chunk"><div class="meta-chunk-heading">수출허가 / 신청 절차 / 제출 서류</div><div class="meta-chunk-body">신청서와 최종 사용자 확인서를 제출합니다.</div></div><div class="meta-demo-foot">제목 경로 + 본문 <span aria-hidden="true">→</span> 본문 검색 · 의미 검색</div></div><p class="meta-use-note">조문·절 경로를 청크 제목과 dense 임베딩에 함께 반영합니다.</p></article>'+
    '<article class="meta-use-card meta-use-muted"><span class="meta-role">문서 정보 보관</span><h3>나머지 속성</h3><p>문서의 출처와 식별 정보를 보관합니다.</p><div class="meta-demo"><div class="meta-property-tags"><span>유형</span><span>상태</span><span>번호</span><span>기관</span><span>개정일</span></div><div class="meta-down" aria-hidden="true">↓</div><div class="meta-storage"><span class="meta-doc-symbol" aria-hidden="true"></span><div><strong>인덱스 · 검색 결과</strong><span>문서 정보로 보존</span></div><span class="meta-check" aria-hidden="true">✓</span></div><div class="meta-unused">필터 · 가산점에는 현재 미사용</div></div><p class="meta-use-note">현재 카테고리 검색에서는 이 속성으로 문서를 거르거나 점수를 더하지 않습니다.</p></article>'+
    '<article class="meta-use-card meta-use-green meta-supersession" id="cm-superseded"><span class="meta-role">옛 판과 새 판 연결</span><h3>문서 대체 관계 <code>superseded_by</code></h3><p>이 문서를 대체하는 새 판이 확인되면, 그 문서의 ID를 옛 판에 기록합니다.</p><div class="meta-supersession-examples"><div class="meta-demo"><div class="meta-demo-label">연결 구조 · 설명용 예시</div><div class="meta-storage"><span class="meta-doc-symbol" aria-hidden="true"></span><div><strong>2021년 전문판정 신청서 · 옛 판</strong><span>문서 ID: form-2021</span></div></div><div class="meta-replacement-link"><code>superseded_by = form-2026</code><span aria-hidden="true">↓</span></div><div class="meta-storage"><span class="meta-doc-symbol" aria-hidden="true"></span><div><strong>2026년 개정 전문판정 신청서 · 새 판</strong><span>문서 ID: form-2026</span></div></div><div class="meta-demo-foot">단순히 나중에 올라온 문서가 아니라, 같은 문서를 대체하는 판을 연결합니다.</div></div><div class="meta-demo"><div class="meta-demo-label">검색 결과에 쓰이는 방식</div><div class="meta-query">“2021년 전문판정 신청서 찾아줘”</div><ol class="meta-edition-results"><li><strong>2021년 전문판정 신청서</strong><span>찾던 옛 판 · 대체된 문서</span></li><li><strong>2026년 개정 전문판정 신청서</strong><span>연결된 새 판을 바로 뒤에 추가</span></li></ol><div class="meta-demo-foot">새 판이 이미 결과에 있으면 중복 추가하지 않으며, 반환 문서 수 상한 안에서 처리합니다.</div></div></div><p class="meta-use-note">BM25는 <code>superseded_by</code>가 없는 문서에 +4를 줍니다. 값이 비어 있다는 것은 대체 관계가 기록되지 않았다는 뜻이며, 새 판이 없다는 보장은 아닙니다. 위 그림은 동작 설명용으로, 현재 카테고리 자료의 실제 검색 결과가 아닙니다.</p></article>'+
    '</div><p class="note">수치는 현재 파서 산출물 기준(2026-10-06)입니다. 파서 재실행에 따라 문서·청크 수와 채움률이 바뀔 수 있습니다.</p></div>';
  document.getElementById("detail").scrollTop=0;
}

/* 카테고리별 검색: 질문별 보기(목록과 상세). */
var CSETS=[["law50","법령·고시 50건 · 50문항","법령·고시"],["admin30","행정·업무 30문항","행정·업무"],["faq30","민원FAQ 30문항","민원FAQ"]];
var CMODES=["SPLADE","dense","hybrid"];
var CQ=[];
CSETS.forEach(function(s){ CATD[s[0]].forEach(function(x){ CQ.push({id:s[0]+"-"+x.i, set:s[0], i:x.i, c:x.c, q:x.q, n:x.n, r:x.r, miss:x.r.some(function(r){return r==null;}), hmiss:!cqRet(CATH[s[0]][x.i]).chunk}); }); });
var CQS={set:"all", id:CQ[0].id, tab:"sp", chunk:null};
function cqSet(k){ return CSETS.filter(function(s){return s[0]===k;})[0]; }
function cqVis(){ return CQ.filter(function(x){ return x.set===CATSEL; }); }
function cqList(){
  var v=cqVis();
  document.getElementById("list").innerHTML=v.map(function(x){
    return '<button class="item" type="button" role="option" data-cq="'+x.id+'"'+(x.id===CQS.id?' aria-current="true"':'')+'><span class="dot'+(x.hmiss?' miss':'')+'"></span><span><span class="meta">'+esc(cqSet(x.set)[2])+' · '+x.i+' · '+esc(x.c)+'</span><span class="txt">'+esc(x.q)+'</span></span></button>';
  }).join("")||'<p class="note" style="padding:14px">조건에 맞는 문항이 없습니다.</p>';
}
function cqWho(x){ var N=["SPLADE","dense","hybrid"];
  var m=[0,1,2].filter(function(k){return x.r[k]==null;}).map(function(k){return N[k];});
  if(!m.length) return "세 모드 모두 정답 청크를 찾았습니다.";
  if(m.length===3) return "세 모드 모두 정답 청크를 놓쳤습니다.";
  return m.join("·")+"만 놓쳤고, "+N.filter(function(_,k){return x.r[k]!=null;}).join("·")+"는 찾았습니다.";
}
var CTABS=[["sp","SPLADE 검색"],["dn","dense 검색"],["fx","합산과 컷오프"],["out","최종 반환"],["ans","판정·답변"],["stg","단계별 변화"]];
function cqTitle(c){ return CATB[c][0]+" #"+c.split("#")[1]; }
function cqRk(h,i){ var j=h.findIndex(function(x){return x.g;}); return j<0?'<b class="no">상위 5 밖</b>':'<b>'+(j+1)+'위</b>'; }
function cqOut(r,m){ return r==null?(m===0?'상위 100 밖':'후보 밖'):r+'위'; }
function cqGold(d,x){
  if(d.gr[0]!=null&&d.gr[0]<=5&&d.gr[1]!=null&&d.gr[1]<=5) return "";
  var c=d.gc[0]; if(!c||!CATB[c]) return "";
  return '<div class="gd"><h2>놓친 방식이 있는 질문입니다. 정답 청크는 이렇게 생겼습니다</h2><div class="gch">'+esc(cqTitle(c))+' · 정답 청크 '+x.n+'개 중 하나'+(d.gr[0]==null||d.gr[0]>5?' · SPLADE '+cqOut(d.gr[0],0):'')+(d.gr[1]==null||d.gr[1]>5?' · dense '+cqOut(d.gr[1],1):'')+'</div><pre style="white-space:pre-wrap">'+esc(tidy(CATB[c][1]).slice(0,900))+'</pre></div>';
}
function cqHits(list,kind,terms){
  return list.map(function(h,i){
    var b=tidy(CATB[h.c][1]), body=esc(b);
    if(terms) terms.filter(function(t){return t.length>=2;}).forEach(function(t){ var e=esc(t); body=body.split(e).join("<mark>"+e+"</mark>"); });
    var tm=(h.t||[]).map(function(x){return '<span class="tm"><b>'+esc(x[0])+'</b> '+x[1]+'</span>';}).join("");
    var from=kind==="hy"?'<span class="sc" style="flex:none">SPLADE '+(h.a?h.a+'위':'—')+' · dense '+(h.b?h.b+'위':'—')+'</span>':'';
    return '<details class="hit'+(h.g?' gold':'')+'"'+(h.g?' open':'')+'><summary class="hd"><span class="rk">'+(i+1)+'위</span><span class="ti">'+esc(cqTitle(h.c))+'</span>'+(h.g?'<span class="pin big">정답 청크</span>':'')+from+'<span class="sc">'+h.s+'</span><span class="more">본문 보기</span></summary>'+
      '<div class="sn">'+body+'</div>'+(tm?'<div class="tms"><span>단어별 기여</span>'+tm+'</div>':'')+'</details>'; }).join("");
}
function cqPanelDn(d,x){
  var idx = CQS.chunk==null ? Math.max(0,d.dn.findIndex(function(h){return h.g;})) : CQS.chunk;
  if(idx<0) idx=0;
  var pick=d.dn.map(function(h,i){ return '<button type="button" data-chunk="'+i+'" aria-pressed="'+(i===idx?'true':'false')+'"><span class="r">'+(i+1)+'위</span><span class="t">'+esc(cqTitle(h.c))+(h.g?' <span class="pin">정답</span>':'')+'</span><span class="s">'+h.s+'</span></button>'; }).join("");
  var o=d.occ;
  if(!o) return cqBar2(d)+'<p class="note">dense 검색은 청크마다 미리 만들어 둔 임베딩과 질문 임베딩의 코사인 유사도로 순위를 냅니다. 청크를 통째로 임베딩했고 질문도 통째로 한 번 임베딩합니다.</p><h2>dense 검색 상위 5 · 코사인 유사도</h2>'+cqHits(d.dn,"dn");
  var col=o.d.map(function(r){return r[idx];}), mx=Math.max.apply(null,col.concat([0.001]));
  var words=o.w.map(function(w,i){ var dd=col[i], a=dd>0.005?Math.min(0.9,0.12+0.78*dd/mx):0; return '<span style="--a:'+a.toFixed(2)+'" title="'+esc(w)+': 빼면 유사도 '+(dd>=0?'−':'+')+Math.abs(dd).toFixed(3)+'">'+esc(w)+'</span>'; }).join("");
  var top=col.map(function(dd,i){return [o.w[i],dd];}).filter(function(z){return z[1]>0.01;}).sort(function(a,b){return b[1]-a[1];}).slice(0,4);
  var hit=d.dn[idx], cs=hit.cs, bodyHtml=esc(tidy(CATB[hit.c][1])), cTop="";
  if(cs&&cs.length){
    var cm=Math.max.apply(null,cs.map(function(z){return z[1];}).concat([0.0005]));
    bodyHtml=cs.map(function(z){ var dd=z[1], a=dd>0.001?Math.min(0.9,0.15+0.75*dd/cm):0; return '<span class="cseg" style="--a:'+a.toFixed(2)+'" title="이 구간을 빼면 유사도 '+(dd>=0?'−':'+')+Math.abs(dd).toFixed(4)+'">'+esc(z[0])+'</span>'; }).join(" ");
    var ct=cs.slice().sort(function(a,b){return b[1]-a[1];}).slice(0,2).filter(function(z){return z[1]>0.001;});
    cTop='<p style="margin:6px 0 0;font-size:13.5px">'+(ct.length?'영향이 큰 구간: '+ct.map(function(z){return '<b>“'+esc(z[0])+'”</b> (−'+z[1].toFixed(4)+')';}).join(", "):'뚜렷하게 영향을 준 구간이 없습니다. 청크 전체 의미로 가까워진 경우입니다.')+'</p>';
  }
  return cqBar2(d)+'<p class="note">dense 검색은 청크마다 미리 만들어 둔 임베딩과 질문 임베딩의 코사인 유사도로 순위를 냅니다. 청크를 통째로 임베딩했고 질문도 통째로 한 번 임베딩합니다.</p>'+
   '<div class="two"><div class="pick" role="group" aria-label="dense 상위 5 청크">'+pick+'</div>'+
   '<div style="display:flex;flex-direction:column;gap:12px;min-width:0"><div><h2>이 청크의 본문 — 질문과의 유사도에 기여한 부분 (근사)</h2><div class="body cbody" style="margin-top:6px">'+bodyHtml+'</div><div class="legend"><i></i>진할수록 그 구간을 빼면 질문과의 유사도가 더 떨어짐 (6어절 단위)</div>'+cTop+'</div>'+
   '<div><h2>질문의 어느 단어가 이 청크와 가깝게 만들었나 (근사)</h2><div class="attr" style="margin-top:4px">'+words+'</div>'+
   '<div class="legend"><i></i>진할수록 그 단어를 빼면 유사도가 더 떨어짐 · 이 청크와 질문의 코사인 '+o.base[idx]+'</div>'+
   '<p style="margin:6px 0 0;font-size:13.5px">'+(top.length?'기여가 큰 단어: '+top.map(function(z){return '<b>'+esc(z[0])+'</b> (−'+z[1].toFixed(3)+')';}).join(", "):'뚜렷하게 기여한 단어가 없습니다. 어느 한 단어를 빼도 유사도가 0.01 넘게 떨어지지 않았습니다.')+'</p>'+
   '<p class="warn" style="margin-top:8px">질문 어절이나 청크 구간을 하나씩 빼고 다시 임베딩해 잰 추정값입니다(어절 나누기는 이 설명용 계산에서만 쓴 단위이고, 실제 dense 검색은 질문 전체를 한 번에 임베딩합니다). 실제 검색은 단어별 계산을 하지 않으므로 "dense가 이 단어로 찾았다"는 근거로 쓰지 않습니다. ±0.01 안쪽 차이는 의미가 없습니다.</p></div></div></div>';
}
function cqPanel(d,x){
  var tab=CQS.tab;
  if(tab==="dn") return cqPanelDn(d,x);
  if(tab==="fx") return cqFx(d,x);
  if(tab==="out") return cqOutP(d,x);
  if(tab==="ans") return cqAns(d,x);
  if(tab==="stg") return cqStg(d,x);
  var mx=Math.max.apply(null,d.qt.map(function(t){return t[1];}).concat([0.001]));
  var chips=d.qt.map(function(t){ var al=Math.min(0.75,0.08+0.67*t[1]/mx); return '<span class="spchip" style="--a:'+al.toFixed(2)+'" title="질문 가중치 '+t[1]+'">'+esc(t[0])+'</span>'; }).join("");
  var terms=[]; d.sp.forEach(function(h){ (h.t||[]).forEach(function(x2){ if(terms.indexOf(x2[0])<0) terms.push(x2[0]); }); });
  return cqBar2(d)+'<div><h2>질문을 이렇게 바꿔서 찾았습니다 (SPLADE)</h2><div class="chips" style="margin-top:8px">'+chips+'</div></div><h2>SPLADE 검색 상위 5 · 점수</h2>'+cqHits(d.sp,"sp",terms);
}
function cqRet(d){ var f=d.fx; return { doc:f.ret.some(function(r){return r.g;}), chunk:f.ret.some(function(r){return r.ch.some(function(c){return c[3];});}) }; }
function cqBar2(d){
  var f=d.fx, gr=d.gr, rt=cqRet(d);
  return '<div class="goldbar'+(rt.chunk?'':' miss')+'"><span class="pin big">정답 청크</span><span>SPLADE '+(gr[0]!=null&&gr[0]<=5?'<b>'+gr[0]+'위</b>':'<b class="no">상위 5 밖</b>')+'</span><span>dense '+(gr[1]!=null&&gr[1]<=5?'<b>'+gr[1]+'위</b>':'<b class="no">상위 5 밖</b>')+'</span><span>합산 청크 '+(f.gd?'<b>'+f.gd+'위</b>':'<b class="no">후보 밖</b>')+'</span><span>최종 반환 '+(rt.chunk?'<b>정답 청크 실음</b>':(rt.doc?'<b class="no">정답 문서만</b>':'<b class="no">없음</b>'))+'</span></div>'+cqGold(d,CQ.filter(function(o){return o.id===CQS.id;})[0]);
}
function cqSingleCut(name,cls,fx,unit){
  var body="", prev="keep", kept=0;
  var ST={keep:"keep",cut:"out",docs:"out",perdoc:"out",budget:"out"};
  fx.cr.forEach(function(r,i){
    var stt=ST[r[3]], pct=fx.ctop?(r[2]/fx.ctop*100).toFixed(1):"0";
    var line=(stt!==prev&&stt==="out")?'<div class="cutline">─ 1위 점수의 '+(fx.ratio*100)+'% 미만(= '+(fx.ctop*fx.ratio).toFixed(unit)+' 미만): 제외 ─</div>':"";
    prev=stt; if(stt==="keep") kept++;
    body+=line+'<div class="lrow'+(r[4]?' g':'')+(stt==="keep"?'':' out')+'"><span class="n">'+r[1]+'</span><span class="t">'+esc(cqTitle(r[0]))+(r[4]?' <span class="pin">정답 청크</span>':'')+'</span><span class="sc">'+r[2]+'</span><span class="pc"><i style="width:'+Math.min(100,pct)+'%"></i></span><span class="pp">'+pct+'%</span></div>';
  });
  return '<div class="lcol '+cls+'"><h3>'+name+' <small>청크 '+kept+'개 반환(비율 '+fx.ratio+')</small></h3>'+body+'</div>';
}
function cqLab(l){ return '<span class="tag '+(l===2?'t-ok':(l===1?'t-mut':'t-bad'))+'" title="Sonnet 관련도 판정">판정 '+l+'</span>'; }
function cqFx(d,x){
  var f=d.fx, K=60, ST={keep:'<span class="tag t-ok">반환</span>',cut:'<span class="tag t-bad">컷오프</span>',docs:'<span class="tag t-mut">문서 수 한도</span>',perdoc:'<span class="tag t-mut">문서당 한도</span>',budget:'<span class="tag t-mut">청크 예산 끝</span>'};
  function term(r){ return r?'1/('+K+'+'+r+') = '+(1/(K+r)).toFixed(4):'—'; }
  var drawn=false;
  var frows=f.cr.map(function(r,i){
    var line="";
    if(!drawn&&r[5]){ drawn=true; line='<div class="cutline wide">─ 컷오프 선: 1위 RRF 점수 × 95% = '+f.floor+' · 이 아래는 각 목록의 1위 청크만 살아남음 ─</div>'; }
    var res=(r[6]==="keep"&&r[5])?'<span class="tag t-mut">선 아래·1위라 유지</span>':ST[r[6]];
    return line+'<div class="frow'+(r[7]?' g':'')+'"><span class="n">'+(i+1)+'</span><span class="dc">'+esc(cqTitle(r[0]))+(r[7]?' <span class="pin">정답 청크</span>':'')+'</span><span class="calc"><span class="'+(r[1]?'sp':'no')+'">SPLADE '+(r[1]?r[1]+'위 ':'없음 ')+term(r[1])+'</span> + <span class="'+(r[2]?'v':'no')+'">dense '+(r[2]?r[2]+'위 ':'없음 ')+term(r[2])+'</span></span><span class="tot">'+r[3].toFixed(4)+'</span><span class="bar"><i style="width:'+(f.top?(r[3]/f.top*100).toFixed(0):0)+'%"></i></span>'+res+'</div>';
  }).join("");
  var step1='<h2>① SPLADE·dense를 <b>단독으로</b> 쓸 때의 청크 컷오프 <small style="font-weight:400;color:var(--muted)">hybrid는 이 컷을 쓰지 않습니다</small></h2><p class="note">각 검색기의 청크 순위(SPLADE 상위 100, dense 상위 50)를 1위 점수 대비 비율로 자릅니다. 두 방식의 Precision이 너무 낮게 나와서(관련 없는 청크를 너무 많이 실어서) 결과 요약 수치를 이 컷오프로 다시 쟀습니다. 비율은 질문 110개에서 Recall을 지키면서 Precision이 오르는 지점을 찾은 값(SPLADE 80%, dense 93%)이라 이 질문셋에 맞춰져 있습니다. 1위 청크는 비율과 무관하게 항상 남고, 그 뒤로 청크 최대 10개·문서 최대 5개·문서당 최대 6개까지 싣습니다. 결과 요약의 SPLADE·dense Precision은 이 컷을 쓴 기준입니다. dense 점수는 코사인을 0~1로 옮긴 값 (1+코사인)/2입니다.</p><div class="lists">'+cqSingleCut("SPLADE","spl",f.sp,2)+cqSingleCut("dense","vec",f.dn,3)+'</div>';
  var step2='<h2 style="margin-top:22px">② 청크 단위 RRF와 컷오프 <small style="font-weight:400;color:var(--muted)">합산 대상 '+f.nf+'개 청크 · 위에서 '+f.cr.length+'개만 표시</small></h2><p class="note">문서로 묶지 않고 청크마다 <b>1/(60+자리)</b>를 더합니다. 두 목록 모두 1위이면 2/61 = 0.0328이 최고점입니다. 1위 점수의 <b>95%</b> 미만은 버리되 어느 목록의 1위 청크는 남깁니다. 남은 청크를 위에서부터 싣는데, 청크는 최대 10개, 문서는 최대 5개, 한 문서의 청크는 최대 6개입니다. 점수가 같으면 dense에서 자리가 앞선 쪽, 그래도 같으면 청크 ID 순입니다. 결과 요약의 hybrid 청크 Recall·MRR은 이 순서의 상위 5청크로 셉니다.</p>'+'<div class="card frows">'+frows+'</div>'+(f.gd?'':'<p class="warn">정답 청크가 두 목록 어디에도 없어 합산 대상에 들어오지 못했습니다.</p>');
  return cqBar2(d)+step1+step2;
}
function cqOutP(d,x){
  function r(n,l,lim){ return n?'<span class="rn"><i>'+l+'</i> '+n+'위</span>':'<span class="rn no">'+l+' 상위 '+lim+' 밖</span>'; }
  var out=d.fx.ret.map(function(doc,i){
    var rows=doc.ch.map(function(c,j){ var b=tidy(CATB[c[0]][1]);
      return '<details class="cdet'+(c[3]?' g':'')+'"'+(c[3]?' open':'')+'><summary><span class="ord">'+(j+1)+'번째</span><span class="cid">청크 #'+c[0].split("#")[1]+'</span>'+(c[3]?'<span class="pin">정답 청크</span>':'<span></span>')+'<span class="prev">'+esc(b.slice(0,70))+'…</span>'+r(c[1],"SPLADE",100)+r(c[2],"dense",50)+cqLab(c[4])+'</summary><div class="cbody2">'+esc(b)+'</div></details>'; }).join("");
    return '<div class="dbox'+(doc.g?' g':'')+'"><div class="dhead"><span class="dn">'+(i+1)+'위</span><span class="dt">'+esc(doc.t)+'</span>'+(doc.g?'<span class="pin">정답 문서</span>':'')+'<span class="dm">청크 '+doc.ch.length+'개 실림</span></div><div class="crows">'+rows+'</div></div>'; }).join("");
  return '<p class="note">청크 단위 RRF에서 컷오프(1위 점수의 95%)를 통과한 청크를 문서별로 묶었습니다(청크 최대 10개, 문서 최대 5개, 문서당 최대 6개). 순서는 합산 탭 ②의 순서입니다. 오른쪽 "판정"은 Sonnet이 질문과 청크 본문만 보고 매긴 관련도(2 답을 담음, 1 일부 담음, 0 무관)이고, Precision은 판정 1 이상을 관련으로 셉니다. 오른쪽 순위는 그 청크가 SPLADE(상위 100)·dense(상위 50) 목록에서 몇 위였는지이고, "밖"은 그 목록에 없었다는 뜻입니다. <b>이 창은 결과 요약의 청크 Recall(상위 5청크)과 다릅니다.</b> 각 줄을 누르면 청크 본문이 열립니다.</p>'+cqBar2(d)+'<div class="dboxes">'+(out||'<p class="note" style="margin:0">반환된 문서가 없습니다.</p>')+'</div>';
}
function cqAns(d,x){
  var n=d.fx.ret.length, m=d.fx.ret.reduce(function(a,doc){return a+doc.ch.length;},0);
  return cqBar2(d)+'<div class="verdict"><b>이 질문의 판정·답변은 측정하지 않았습니다</b><p>이 탭의 수치는 검색 단계(SPLADE, dense, 합산, 컷오프)만 오프라인으로 잰 것입니다. 판정 LLM과 답변 LLM은 돌리지 않았고, SPLADE는 서비스 검색에 붙어 있지 않습니다. 그래서 판정 결과와 답변 예시는 없습니다.</p></div>'+
  '<p class="note" style="margin-top:12px">서비스 구조대로라면 최종 반환의 <b>문서 '+n+'건·청크 '+m+'개</b>가 답변 LLM에 근거로 넘어갑니다. 판정 LLM은 기본값이 꺼짐이고, 켜면 앞 문서 3개를 읽고 질문이 요구하는 사실이 적혀 있는지 예/아니오로 답해 아니오이면 결과를 비웁니다. 카테고리 검색 경로는 판정을 끈 상태로 둡니다.</p>';
}
function cqStg(d,x){
  var N=["SPLADE","dense","hybrid(청크 RRF 상위 5청크)"];
  var rows=x.r.map(function(r,k){ return '<tr><td>'+N[k]+'</td><td>'+(r==null?'상위 5 밖':r+'위')+'</td></tr>'; }).join("");
  var rt=cqRet(d);
  return '<p class="note">카테고리 질문은 37단계에서 만들었고, 38단계에서 SPLADE를 학습했습니다. 이 화면의 순위는 BM25를 뺀 오프라인 측정 한 번의 결과라서, 질문 하나가 단계마다 어떻게 바뀌었는지는 기록하지 않았습니다.</p>'+
  '<table><thead><tr><th>방식</th><th>첫 정답 청크 순위</th></tr></thead><tbody>'+rows+'<tr><td>컷오프 뒤 반환</td><td>'+(rt.chunk?'정답 청크 실음':(rt.doc?'정답 문서만 실음':'정답 문서 못 실음'))+'</td></tr></tbody></table>'+
  '<p class="note">묶음 전체의 지표는 결과 요약에서 볼 수 있습니다.</p>';
}
function cqNode(tab,cls,lb,big,sub,active){ return '<button type="button" class="node '+cls+'" data-ctab="'+tab+'" aria-pressed="'+(active?'true':'false')+'"><span class="lb">'+lb+'</span><span class="big">'+big+'</span><span class="sub">'+sub+'</span></button>'; }
function cqFlow(d,x){
  var gr=d.gr, f=d.fx, rt=cqRet(d), h=function(r){ return r!=null&&r<=5?'<span class="pin">정답</span>'+r+'위':'상위 5 밖'; };
  var gdoc=f.gd?'<span class="pin">정답</span>'+f.gd+'위':'후보 밖', kept=rt.chunk, nret=f.ret.reduce(function(a,o){return a+o.ch.length;},0);
  return cell("c1 r1",cqNode("sp","spl","질문 → SPLADE용","토큰 "+d.nq+"개","어휘 가중치로 바꿈 · 확장 포함",false))+
    cell("c1 r2",cqNode("dn","vec","질문 → dense용","문장 통째로 1번","임베딩 1024차원 · 쪼개지 않음",false))+
    cell("c2 r1",cqNode("sp","spl","① SPLADE",h(gr[0]),"청크 상위 100 · hybrid는 트림 없이 합산",CQS.tab==="sp"))+
    cell("c2 r2",cqNode("dn","vec","② dense",h(gr[1]),"청크 상위 50 · hybrid는 트림 없이 합산",CQS.tab==="dn"))+
    cell("c3 rs",cqNode("fx",f.gd?"":"lost","③ 청크 단위 RRF",gdoc,"합산 대상 청크 "+f.nf+"개",CQS.tab==="fx"))+
    cell("c4 rs",cqNode("fx",kept?"ok":"lost","④ 컷오프 95%",kept?'정답 통과':'정답 잘림',"청크 "+nret+"개 남음",false))+
    cell("c5 rs",cqNode("out",rt.chunk?"ok":"lost","⑤ 반환",rt.chunk?'정답 청크 실음':(rt.doc?'정답 청크 못 실음':'정답 문서 못 실음'),"문서 "+f.ret.length+"건 · 청크 "+nret+"개",CQS.tab==="out"))+
    cell("c6 rs",cqNode("ans","","⑥ 판정·답변",'측정 안 함',"오프라인 측정에 없음",CQS.tab==="ans"));
}
function cqDetail(){
  var x=CQ.filter(function(o){return o.id===CQS.id;})[0]||CQ[0], s=cqSet(x.set), d=CATH[x.set][x.i], el=document.getElementById("detail");
  var rt=cqRet(d);
  el.innerHTML='<div class="wrap"><div><div class="kicker"><span>'+esc(s[2])+' · '+x.i+'</span><span>'+esc(x.c)+'</span><span class="tag '+(rt.chunk?'t-ok':'t-bad')+'">'+(rt.chunk?'정답 청크 반환':'정답 청크 미반환')+'</span><span class="tag t-mut">상위 5청크: '+esc(cqWho(x))+'</span><span class="tag t-mut">정답 청크 '+x.n+'개</span></div><p class="q">'+esc(x.q)+'</p></div>'+
  '<section aria-label="단계별 경로"><div class="flow">'+cqFlow(d,x)+'</div></section>'+
  '<div><div class="tabs" role="tablist">'+CTABS.map(function(t){return '<button type="button" role="tab" data-ctab="'+t[0]+'" aria-selected="'+(CQS.tab===t[0]?'true':'false')+'">'+t[1]+'</button>';}).join("")+'</div><div class="panel" role="tabpanel">'+cqPanel(d,x)+'</div></div>'+
  '<p class="note"><button type="button" class="sidebtn" data-cqgo="'+CINFO[x.set].id+'">결과 요약에서 보기</button></p>'+
  '<p class="cap">질문은 정답을 아는 사람이 본문을 보고 쓴 점검용이라 성능 판단에는 쓰지 않습니다. 오프라인 측정이라 LLM 필터·판정을 거치지 않았습니다. "정답 청크 반환"은 청크 단위 RRF와 95% 컷오프 뒤 반환한 청크에 정답 청크가 있는지이고, 위 청크 Recall은 상위 5청크 기준입니다.</p></div>';
  el.scrollTop=0;
}
function cqSelect(id,nohash){ CQS.id=id; CQS.chunk=null; cqList(); cqDetail(); if(!nohash) location.hash="cat-q-"+id; var c=document.querySelector('#list [aria-current="true"]'); if(c&&c.scrollIntoView) c.scrollIntoView({block:"nearest"}); }
function cqMove(d){ var v=cqVis(); if(!v.length) return; var i=v.findIndex(function(x){return x.id===CQS.id;}); cqSelect(v[Math.max(0,Math.min(v.length-1,i<0?0:i+d))].id); }
function cqInit(){
  document.getElementById("list").addEventListener("click",function(e){ var b=e.target.closest("button[data-cq]"); if(b) cqSelect(b.dataset.cq); });
  document.getElementById("detail").addEventListener("click",function(e){ var ct=e.target.closest("[data-ctab]"); if(ct&&st.view==="cq"){ CQS.tab=ct.dataset.ctab; var y=this.scrollTop; cqDetail(); this.scrollTop=y; return; } var g=e.target.closest("button[data-cqgo]"); if(g){ CATSEL=Object.keys(CINFO).filter(function(o){return CINFO[o].id===g.dataset.cqgo;})[0]||"law50"; setView("c"); setTimeout(function(){ var el=document.getElementById(g.dataset.cqgo); if(el) el.scrollIntoView({block:"start"}); },0); return; } var c=e.target.closest("button[data-chunk]"); if(c&&st.view==="cq"){ CQS.chunk=+c.dataset.chunk; var y2=this.scrollTop; cqDetail(); this.scrollTop=y2; } });
}
function renderCq(){ cqList(); cqDetail(); }

/* 카테고리별 검색 탭의 38단계: 설정별 결과(문서 stage-38 기록의 카테고리 표). */
var C38={
 head:"학습한 SPLADE 설정을 새 카테고리 코퍼스에서 하나씩 쟀고, 이 탭의 SPLADE는 설정 C를 씁니다",
 what:["합성 질의 2,702개로 SPLADE를 다시 학습한 설정 A, C, D, E를 법령·고시 21문항과 행정·업무 30문항에서 기준(학습 안 한 PIXIE-Splade-v1.5), dense와 같은 조건으로 비교했습니다. 설정 B는 학습 도중 메모리 부족으로 실패해 다시 돌리지 않았습니다.","표와 발표의 SPLADE는 설정 C를 씁니다. 오프라인 측정이며 서비스 코드에는 붙어 있지 않습니다."],
 why:["법령에서 C는 SPLADE 단독 문서 P@1이 0.810에서 0.952로 올라 가장 높았고(+3문항), 행정·업무에서는 네 설정이 모두 0.900(+1문항)으로 같았습니다.","청크 Hit는 오르지 않았습니다(법령 0.762에서 0.810, 행정·업무 0.967에서 0.933). 1위로 올리지만 더 많이 건지지는 못합니다.","질문이 21~30개이고 점검용이라 한 문항이 3~5p입니다. 설정 네 개 중 좋아 보이는 것을 고른 것이라 선택 편향이 있어 확정하지 못합니다."],
 cfg:[["기준(학습 안 함)","-","-","1,465 / 1,689",""],["A","1e-5","1e-6","940 / 1,091",""],["B","1e-5","2e-6 (2에폭)","-","학습 도중 메모리 부족으로 실패"],["C","1e-5","5e-6","475 / 447","이 탭의 SPLADE"],["D","0","5e-6","614 / 688",""],["E","0","3e-6","786 / 892",""]],
 hd:["구성","문서 P@1","문서 Hit@5","문서 MRR","청크 Hit","청크 MRR","1위 청크 적중"],
 law:[["dense(BGE)만","0.810","1.000","0.897","0.905","0.710","0.571"],["SPLADE 기준","0.810","1.000","0.885","0.762","0.683","0.619"],["SPLADE A","0.857","1.000","0.914","0.810","0.738","0.667"],["SPLADE","0.952","0.952","0.952","0.810","0.762","0.714"],["SPLADE D","0.905","0.952","0.917","0.810","0.754","0.714"],["SPLADE E","0.857","0.952","0.897","0.810","0.738","0.667"],["기준 + dense","0.857","0.952","0.897","0.857","0.750","0.667"],["A + dense","0.810","0.952","0.873","0.857","0.750","0.667"],["C + dense","0.905","1.000","0.944","0.857","0.730","0.619"],["D + dense","0.905","0.952","0.921","0.857","0.750","0.667"],["E + dense","0.810","0.952","0.873","0.857","0.750","0.667"]],
 adm:[["dense(BGE)만","0.800","0.933","0.867","0.933","0.696","0.533"],["SPLADE 기준","0.867","1.000","0.933","0.967","0.744","0.567"],["SPLADE A","0.900","1.000","0.944","0.967","0.751","0.600"],["SPLADE","0.900","1.000","0.950","0.933","0.751","0.600"],["SPLADE D","0.900","1.000","0.950","0.933","0.783","0.667"],["SPLADE E","0.900","1.000","0.950","0.933","0.736","0.600"],["기준 + dense","0.833","0.900","0.867","0.967","0.676","0.467"],["A + dense","0.867","0.900","0.883","0.933","0.686","0.500"],["C + dense","0.900","0.900","0.900","0.933","0.701","0.500"],["D + dense","0.900","0.900","0.900","0.933","0.717","0.533"],["E + dense","0.867","0.900","0.883","0.933","0.694","0.500"]]
};
function c38Table(h,rows){
  return '<table><thead><tr>'+h.map(function(x){return '<th>'+x+'</th>';}).join("")+'</tr></thead><tbody>'+rows.map(function(r){ var c=/ C( |$)/.test(" "+r[0]+" ")||r[0]==="C"; return '<tr'+(c?' class="hl"':'')+'>'+r.map(function(x){return '<td>'+esc(x)+'</td>';}).join("")+'</tr>'; }).join("")+'</tbody></table>';
}
function panelC38(){
  return '<div class="card"><h2 class="ch">설정별 학습 조건</h2>'+c38Table(["설정","정규화 λ","학습률","문서당 term (법령 / 행정·업무)","비고"],C38.cfg)+'</div>'+
  '<div class="card"><h2 class="ch">법령·고시 (21문항, 청크 673)</h2>'+c38Table(C38.hd,C38.law)+'</div>'+
  '<div class="card"><h2 class="ch">행정·업무 (30문항, 청크 183)</h2>'+c38Table(C38.hd,C38.adm)+'</div>'+
  '<p class="cap">SPLADE 단독은 상위 5문서 전부를 반환한 값이고, hybrid는 BGE-m3-ko와 RRF(k=60, 사전 컷 0.97, 최종 컷 0.97)로 합쳤습니다. 질문은 정답을 아는 사람이 본문을 보고 쓴 점검용이고, 평가는 오프라인이라 카테고리 경로의 운영 컷오프와 필터를 거치지 않았습니다. dense와 합치면 법령에서 C 단독(0.952)보다 낮아지고(0.905), 행정·업무의 문서 Hit@5는 모든 hybrid가 0.900으로 SPLADE 단독(1.000)보다 낮습니다.</p>';
}
