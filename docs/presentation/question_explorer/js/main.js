var VIEWS={d:[["q","질문별"],["s","단계별"],["a","구조도"],["e","메타데이터"]], c:[["cq","질문별"],["cs","단계별"],["c","결과 요약"]]};
var BRAND={d:["질문별 검색 경로 탐색기","docs 정답형 135문항과 무응답 대상 38문항을 지금 운영 설정(문서 우선, 판정 LLM 끔)으로 다시 돌린 결과입니다."],c:["카테고리별 검색 탐색기","법령·고시, 행정·업무, 민원FAQ를 각자 인덱스에서 따로 찾는 경로(37단계부터)를 점검한 결과입니다."]};
function modeOf(v){ return v==="cq"||v==="cs"||v==="c"?"c":"d"; }
function setView(v,nohash){
  var m=modeOf(v), prev=st.mode||"d"; st.view=v;
  if(st.mode!==m||!document.getElementById("viewsw").children.length){
    st.mode=m;
    document.getElementById("viewsw").innerHTML=VIEWS[m].map(function(x){ return '<button type="button" data-view="'+x[0]+'" aria-pressed="false">'+x[1]+'</button>'; }).join("");
    document.getElementById("viewsw").style.gridTemplateColumns="repeat("+VIEWS[m].length+",1fr)";
    document.getElementById("bh").textContent=BRAND[m][0]; document.getElementById("bp").textContent=BRAND[m][1];
    document.title=BRAND[m][0];
    if(m==="c"&&!/^d3[789]$/.test(st.stage)) st.stage="d37";
    if(m==="d"&&prev==="c"&&/^d3[789]$/.test(st.stage)) st.stage="s13";
  }
  document.getElementById("modesw").querySelectorAll("button").forEach(function(b){ b.setAttribute("aria-pressed",b.dataset.mode===m?"true":"false"); });
  document.getElementById("viewsw").querySelectorAll("button").forEach(function(b){ b.setAttribute("aria-pressed",b.dataset.view===v?"true":"false"); });
  var q=v==="q", cq=v==="cq", lst=q||cq;
  document.getElementById("tools").hidden=!q; document.getElementById("ctools").hidden=!cq; document.getElementById("list").hidden=!lst; document.getElementById("stnav").hidden=lst; document.getElementById("catsw").hidden=(v!=="c");
  document.getElementById("side").classList.toggle("sv",!lst);
  if(q){ renderList(); renderDetail(); } else if(cq) renderCq(); else if(v==="s"||v==="cs") renderStage(); else if(v==="e") renderMeta(); else if(v==="c") renderCat(); else renderArch();
  if(!nohash){ if(v==="s") location.hash="stage-"+st.stage; else if(v==="cs") location.hash="cat-stage-"+st.stage; else if(v==="a") location.hash="arch"; else if(v==="e") location.hash="meta"; else if(v==="c") location.hash="cat"; else if(v==="cq") location.hash="cat-q-"+CQS.id; else if(st.id) location.hash=st.id; }
}
(function(){
  var seg=document.getElementById("seg");
  [["all","전체",Q.length],["hit","적중",Q.filter(function(q){return q.hit;}).length],["miss","미적중",Q.filter(function(q){return !q.hit;}).length]].forEach(function(x){
    var b=document.createElement("button"); b.type="button"; b.innerHTML=x[1]+'<span class="n">'+x[2]+'</span>'; b.setAttribute("aria-pressed",x[0]==="all"?"true":"false");
    b.onclick=function(){ st.hit=x[0]; seg.querySelectorAll("button").forEach(function(o){o.setAttribute("aria-pressed",o===b?"true":"false");}); renderList(); }; seg.appendChild(b); });
  var who=document.getElementById("who");
  who.innerHTML='<option value="all">누가 찾았나: 전체</option>'+["both","kw","vec","none","na"].map(function(k){return '<option value="'+k+'">'+WHO[k]+' ('+Q.filter(function(q){return q.who===k;}).length+')</option>';}).join("");
  who.onchange=function(){ st.who=who.value; renderList(); };
  var cats=Array.from(new Set(Q.map(function(q){return q.cat;}))), cat=document.getElementById("cat");
  cat.innerHTML='<option value="all">모든 유형</option>'+cats.map(function(c){return '<option>'+esc(c)+'</option>';}).join("");
  cat.onchange=function(){ st.cat=cat.value; renderList(); };
  var stgSel=document.getElementById("stg"), opts='<option value="all">단계별 변화: 전체</option>';
  SG.nodes.forEach(function(n){ ["gain","loss"].forEach(function(t){ var c=Q.filter(function(q){return q.sg.some(function(e){return e.k===n.k&&e.t===t;});}).length; if(c) opts+='<option value="'+n.k+':'+t+'">'+esc(n.l)+'에서 '+(t==="gain"?'나아진':'나빠진')+' 질문 ('+c+')</option>'; }); });
  stgSel.innerHTML=opts; stgSel.onchange=function(){ st.stg=stgSel.value; renderList(); };
  document.getElementById("viewsw").addEventListener("click",function(e){ var b=e.target.closest("button[data-view]"); if(b) setView(b.dataset.view); });
  document.getElementById("modesw").addEventListener("click",function(e){ var b=e.target.closest("button[data-mode]"); if(b&&b.dataset.mode!==st.mode) setView(b.dataset.mode==="c"?"cq":"q"); });
  cqInit();
  (function(){ var app=document.querySelector(".app");
    function set(c){ app.classList.toggle("side-closed",c); try{ localStorage.setItem("qeSideClosed",c?"1":"0"); }catch(e){} }
    try{ if(localStorage.getItem("qeSideClosed")==="1") app.classList.add("side-closed"); }catch(e){}
    document.getElementById("sideclose").addEventListener("click",function(){ set(true); });
    document.getElementById("sideopen").addEventListener("click",function(){ set(false); });
  })();
  (function(){ var tip=document.createElement("div"); tip.id="flowtip"; document.body.appendChild(tip);
    var HI="var(--gold)";
    function sv(h,body){ return '<svg viewBox="0 0 320 '+h+'" width="100%" style="display:block;margin-top:8px;font-family:inherit" fill="none" stroke="currentColor" stroke-width="1.5">'+body+'</svg>'; }
    function bx(x,y,w,h,hi,dim){ return '<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" rx="5"'+(hi?' fill="'+HI+'" stroke="'+HI+'"':'')+(dim?' opacity=".4" stroke-dasharray="4 3"':'')+'/>'; }
    function tx(x,y,t,o){ o=o||{}; return '<text x="'+x+'" y="'+y+'" font-size="'+(o.f||11)+'" text-anchor="'+(o.a||"start")+'" fill="'+(o.c||"currentColor")+'" stroke="none"'+(o.b?' font-weight="700"':'')+'>'+t+'</text>'; }
    function ar(x1,y1,x2,y2){ return '<path d="M'+x1+','+y1+' L'+x2+','+y2+'" marker-end="url(#tipah)"/>'; }
    var DEF='<defs><marker id="tipah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M1,1 L9,5 L1,9 z" fill="currentColor" stroke="none"/></marker></defs>';
    function slots(x,y,n,hiIdx,w){ var o=""; for(var i=0;i<n;i++) o+=bx(x+i*(w+4),y,w,20,i===hiIdx); return o; }
    var X={
     s13:{ex:'질문 “수출 허가 어떻게 받아요?” → 문서에는 “승인 신청 절차”라고 적혀 있어도, 한국어로 더 학습한 모델이 같은 뜻으로 가깝게 봅니다.',
       svg:sv(86,DEF+bx(8,10,110,26)+tx(63,28,"다국어 bge-m3",{a:"middle"})+ar(122,23,168,23)+bx(172,10,140,26,true)+tx(242,28,"BGE-m3-ko",{a:"middle",c:"var(--ink)",b:1})+tx(160,62,"임베딩 모델만 교체 · 키워드(BM25)는 그대로",{a:"middle",f:10.5}))},
     s16:{ex:'질문 “전략물자 알려줘”에서 무관한 문서가 1위가 되어 컷오프 기준선을 끌어올리면 정답이 잘렸습니다. 하한 미만을 먼저 버리면 이 일이 사라집니다.',
       svg:sv(96,DEF+'<path d="M12,52 H308"/>'+'<path d="M170,28 V76" stroke="'+HI+'" stroke-width="2.5"/>'+tx(170,22,"하한",{a:"middle",c:HI,b:1})+'<circle cx="50" cy="52" r="6" opacity=".4"/><circle cx="95" cy="52" r="6" opacity=".4"/><circle cx="130" cy="52" r="6" opacity=".4"/>'+'<circle cx="215" cy="52" r="6" fill="'+HI+'" stroke="'+HI+'"/><circle cx="255" cy="52" r="6" fill="'+HI+'" stroke="'+HI+'"/>'+tx(90,76,"버림",{a:"middle",f:10.5})+tx(240,76,"통과",{a:"middle",f:10.5})+tx(160,92,"점수 →",{a:"middle",f:10}))},
     s18:{ex:'질문 “이 공고의 지난해 낙찰 실적은?” → 주제는 맞지만 문서에 실적이 없으면 판정 LLM이 “아니오”를 내고 결과를 비웁니다.',
       svg:sv(100,DEF+bx(6,10,92,30)+tx(52,29,"근거 앞 3문서",{a:"middle",f:10.5})+ar(100,25,128,25)+bx(130,10,76,30,true)+tx(168,29,"판정 LLM",{a:"middle",c:"var(--ink)",b:1,f:10.5})+ar(208,20,238,10)+ar(208,32,238,56)+tx(240,14,"예 → 답변",{f:10.5})+tx(240,62,"아니오 → 비움",{f:10.5})+tx(160,92,"순위는 바꾸지 않고 남길지 비울지만 정함",{a:"middle",f:10}))},
     s19:{ex:'정답 청크가 문서 안 7번째 이후로 밀리면 문서당 6개 제한 때문에 판정 LLM도 답변 LLM도 그 청크를 보지 못합니다.',
       svg:sv(92,slots(8,20,6,-1,38)+bx(8+6*42,20,38,20,true)+bx(8+7*42,20,38,20,false,true)+tx(8,14,"문서 안 후보 순서",{f:10.5})+'<path d="M258,48 V58 H8 V48" stroke-dasharray="3 3"/>'+tx(133,72,"여기까지만 전달 (6개)",{a:"middle",f:10.5})+tx(276,72,"정답",{a:"middle",f:10.5,c:HI,b:1})+tx(160,88,"▲ 7번째라 아무도 못 봄",{a:"middle",f:10}))},
     s20:{ex:'같은 문서 안에서 RRF 순서로는 정답 청크가 뒤로 밀렸지만, 같은 임베딩이 매긴 dense 순서로는 맨 앞으로 옵니다.',
       svg:sv(100,tx(8,14,"RRF 순서",{f:10.5})+slots(8,20,6,-1,38)+bx(8+6*42,20,38,20,true)+tx(8,62,"dense 순서",{f:10.5})+bx(8,68,38,20,true)+slots(8+42,68,5,-1,38).replace(/<rect/g,'<rect opacity=".5"')+tx(258,38,"정답 ↑",{c:HI,b:1,f:10.5,a:"middle"}))},
     s21:{ex:'문서 B는 dense 목록에서만 1위여서 RRF 점수가 문서 A의 절반 정도입니다. 컷오프 0.95에서는 항상 잘렸지만, 각 목록의 1위는 살리게 바꿨습니다.',
       svg:sv(104,DEF+tx(8,16,"RRF 점수",{f:10.5})+bx(40,24,200,16,true)+tx(8,37,"A",{b:1})+bx(40,50,100,16,false,false)+tx(8,63,"B",{b:1})+'<path d="M230,20 V72" stroke="'+HI+'" stroke-width="2" stroke-dasharray="4 3"/>'+tx(230,84,"컷오프",{a:"middle",f:10.5,c:HI})+tx(150,63,"→ 이전: 잘림",{f:10.5})+tx(8,99,"변경 후: 각 목록의 1위 문서는 예외로 유지",{f:10.5}))},
     s22:{ex:'정답 문서는 본문에서 여러 토큰이 조금씩 맞고, 다른 문서는 제목에서 한 토큰만 크게 맞았다면: 이전에는 큰 한 점수만 봐서 뒤 문서가 1위였습니다.',
       svg:sv(110,tx(8,14,"이전 (best_fields): 한 필드만",{f:10.5})+bx(8,20,40,14,false,true)+bx(52,20,0,14)+tx(60,31,"본문 점수 버림",{f:10})+bx(8,38,140,14,true)+tx(154,49,"다른 문서",{f:10})+tx(8,72,"이후 (most_fields): 합산",{f:10.5})+bx(8,78,30,14,true)+bx(40,78,30,14,true)+bx(72,78,30,14,true)+bx(104,78,30,14,true)+bx(136,78,30,14,true)+tx(172,89,"정답 문서",{f:10}))}
    };
    var E={
     "6":{l:"6단계",t:"임베딩 모델 교체",d:"dense가 약했던 이유를 따져 보니 영어 중심 모델(nomic-embed-text)을 한국어 코퍼스에 쓴 것이 원인이었습니다. 다국어 bge-m3로 바꾸자 같은 코퍼스에서 문서 Recall@5가 23.8%에서 100%가 됐습니다.",
       ex:'문서가 36개뿐인 개발용 평가라서 100%를 그대로 믿으면 안 됩니다. 말할 수 있는 것은 “1~5단계 dense의 약세는 모델 선택의 결과였다”까지입니다.',
       svg:sv(96,tx(8,14,"문서 Recall@5",{f:10.5})+tx(8,38,"nomic",{f:10.5})+bx(52,26,60,16,false,true)+tx(118,38,"23.8%",{f:10.5})+tx(8,64,"bge-m3",{f:10.5})+bx(52,52,252,16,true)+tx(250,64,"100%",{f:10.5,c:"var(--ink)",b:1})+tx(160,90,"대가: 1024차원 · 전체 재색인",{a:"middle",f:10}))},
     "12":{l:"12단계",t:"구어체 어미 때문에 노이즈 문서가 1위",d:"nori가 “알려줘”를 알리·어·주·어로 쪼개면 어미(EC)는 버려지지만 보조용언 “주”(VX)는 남습니다. 이 한 글자가 엉뚱한 문서의 제목에 걸렸습니다. 보조용언(VX)을 제거하도록 고쳤습니다.",
       ex:'질문 “전략물자 알려줘” → “주 : NPT” 각주 문서가 14.37점으로 1위가 되어 컷오프 기준선이 12.94로 올라갔고, 정답 4건이 모두 잘려 화면에 1건만 떴습니다.',
       svg:sv(116,tx(8,14,"알려줘 →",{f:10.5})+bx(62,3,34,16)+tx(79,15,"알리",{a:"middle",f:10})+bx(100,3,28,16,false,true)+tx(114,15,"어",{a:"middle",f:10})+bx(132,3,34,16,true)+tx(149,15,"주",{a:"middle",f:10,c:"var(--ink)",b:1})+bx(170,3,28,16,false,true)+tx(184,15,"어",{a:"middle",f:10})+tx(204,15,"← 주(VX)가 남음",{f:10,c:HI})+tx(8,44,"노이즈",{f:10})+bx(46,34,250,14,true)+tx(8,64,"정답 ×4",{f:10})+bx(46,54,212,14)+'<path d="M258,28 V74" stroke="'+HI+'" stroke-width="2" stroke-dasharray="4 3"/>'+tx(258,86,"기준선 12.94",{a:"middle",f:10,c:HI})+tx(160,108,"정답 점수가 전부 기준선 아래로 깔림",{a:"middle",f:10}))},
     "28":{l:"28단계",t:"제목 가중치를 낮추고 인덱스 간 BM25를 맞춤",d:"제목 가중치를 title^3에서 title^1로 낮추고, 서로 다른 인덱스를 함께 검색할 때 BM25 통계를 전역으로 맞추는 dfs_query_then_fetch를 쓰게 했습니다.",
       ex:'docs 135문항에서 반환 문서 Precision@5가 0.596에서 0.755로, holdout 69문항에서도 +7.0p 올랐습니다. 근거를 잃은 문항은 holdout-v1-004 하나였습니다.',
       svg:sv(94,tx(8,14,"제목 가중치",{f:10.5})+bx(8,20,90,14,true)+tx(104,31,"title^3",{f:10})+ar(150,27,176,27)+bx(180,20,30,14,true)+tx(216,31,"title^1",{f:10})+tx(8,62,"반환 문서 Precision@5",{f:10.5})+bx(8,68,120,12,false,true)+tx(134,78,"0.596",{f:10})+bx(8,84,152,12,true)+tx(166,94,"0.755",{f:10}))},
     "31":{l:"31단계",t:"청크 LLM 관련도 필터",d:"문서 컷오프 뒤에도 정답 문서의 다른 절이 함께 전달됩니다. LLM이 청크를 0(무관)·1(조건·맥락)·2(직접 근거)로 평가해 0점만 걸러 냅니다. 기본값은 꺼짐입니다.",
       ex:'135문항에서 청크 Precision이 25.14%에서 37.78%로 올랐고 Recall은 96.30% 그대로였습니다. 질문당 전달 청크는 6.87개에서 5.32개가 됐습니다.',
       svg:sv(70,slots(8,10,6,-1,38)+'<rect x="8" y="10" width="38" height="20" rx="5" fill="'+HI+'" stroke="'+HI+'"/>'+tx(27,24,"2",{a:"middle",c:"var(--ink)",b:1})+tx(69,24,"1",{a:"middle"})+tx(111,24,"0",{a:"middle"})+tx(153,24,"2",{a:"middle"})+tx(195,24,"0",{a:"middle"})+tx(237,24,"1",{a:"middle"})+'<path d="M92,34 L122,6 M134,34 L164,6" stroke-width="2" stroke="'+HI+'"/>'.replace("M92,34 L122,6 M134,34 L164,6","M92,34 L122,6")+tx(160,58,"0점(무관) 청크만 제거 · 순서는 보존",{a:"middle",f:10.5}))},
     "33":{l:"33단계",t:"청크 우선 파이프라인(시험)",d:"문서를 먼저 고르고 그 안에서 청크를 고르던 순서를 뒤집어, 청크를 먼저 고르는 파이프라인을 만들어 비교했습니다. 같은 Recall에서 문서 우선과 같은 정밀도를 내지 못해 기본으로 켜지 않았고, 문서 안 청크 순서만 반영했습니다.",
       ex:'청크 우선의 이득은 근거가 여러 개인 질문의 Recall(0.776에서 0.81~0.86)뿐이었고, 정밀도를 맞추면 그 이득도 사라졌습니다.',
       svg:sv(86,DEF+tx(8,14,"문서 우선(현행)",{f:10.5})+bx(8,20,70,22,true)+tx(43,35,"문서",{a:"middle",c:"var(--ink)",f:10.5})+ar(80,31,104,31)+bx(106,20,70,22)+tx(141,35,"청크",{a:"middle",f:10.5})+tx(8,62,"청크 우선(꺼짐)",{f:10.5})+bx(8,68,70,18,false,true)+tx(43,81,"청크",{a:"middle",f:10})+ar(80,77,104,77)+bx(106,68,70,18,false,true)+tx(141,81,"문서",{a:"middle",f:10}))}
    };
    var TF={filter:{l:"필터",t:"검색 요청에 조건을 같이 보냄",d:"가져온 뒤에 거르는 것이 아니라, 두 검색 요청에 조건을 함께 실어 보냅니다. 조건에 맞는 청크만 점수를 계산하므로 만료된 문서가 후보 자리를 차지하지 않습니다. 질문 문장은 바뀌지 않습니다.",
       ex:'질문 “제2026-598호 공고 내용 알려줘”, 오늘 2026-10-02. 질문에서 번호 2026 598을 뽑아 조건을 만들고, 키워드·dense 요청에 똑같이 붙입니다. (문서·날짜는 설명용 가상 값)',
       svg:'<table class="ft"><tr><th>청크의 문서</th><th>시행일</th><th>종료일</th><th>번호</th><th>결과</th></tr><tr class="ok"><td>공고 598호</td><td>2026-01-01</td><td>없음</td><td>598</td><td>통과: 시행일이 오늘 이전이고, 종료일이 없으며, 번호가 맞음</td></tr><tr><td>공고 598호 구판</td><td>2025-01-01</td><td>2026-06-30</td><td>598</td><td>탈락: 종료일이 오늘보다 앞</td></tr><tr><td>공고 598호 개정안</td><td>2027-01-01</td><td>없음</td><td>598</td><td>탈락: 시행일이 아직 안 옴</td></tr><tr><td>공고 590호</td><td>2026-01-01</td><td>없음</td><td>590</td><td>탈락: 번호가 다름</td></tr><tr><td>일반 안내 문서</td><td>비어 있음</td><td>비어 있음</td><td>없음</td><td>탈락: 날짜는 통과하지만 번호가 없음</td></tr></table>'}};
    function T(head,rows,hi){ hi=hi||[]; return '<table class="ft"><tr>'+head.map(function(h){return '<th>'+h+'</th>';}).join("")+'</tr>'+rows.map(function(r,i){ return '<tr'+(hi.indexOf(i)>=0?' class="ok"':'')+'>'+r.map(function(c){return '<td>'+c+'</td>';}).join("")+'</tr>'; }).join("")+'</table>'; }
    TF.in0={l:"0 · 질문 입력",t:"문장을 그대로 두 검색에 보냄",d:"이용자가 쓴 문장은 편집하지 않고 키워드 검색과 dense 검색에 똑같이 들어갑니다. 기준일은 검색하는 날짜(오늘)입니다. 질문 재작성은 기본으로 꺼져 있습니다.",
      ex:'질문 “제2026-598호 공고 내용 알려줘”는 한 글자도 바뀌지 않고 아래 필터와 두 검색으로 갑니다.',
      svg:T(["항목","값"],[["질문 문장","제2026-598호 공고 내용 알려줘 (그대로)"],["기준일","오늘 (예: 2026-10-02)"],["질문 재작성","꺼짐"]])};
    TF.k1={l:"키워드 ① · 형태소로 쪼갬 (nori)",t:"어미·조사는 버리고 내용어만 남김",d:"질문을 형태소로 나눠 검색어를 만듭니다. 어미·조사와 보조용언(VX)은 버리고 소문자로 맞춥니다. 동의어 20그룹은 본문 검색에만 적용되고 제목에는 적용되지 않습니다.",
      ex:'질문 “전략물자 알려줘”가 이렇게 나뉩니다. 보조용언 “주”를 버리지 않으면 표 각주 “주 :”에 걸려 엉뚱한 문서가 1위가 됩니다(12단계).',
      svg:T(["형태소","품사","결과"],[["전략","명사","검색어로 사용"],["물자","명사","검색어로 사용"],["알리","동사","검색어로 사용"],["어","연결어미 EC","버림"],["주","보조용언 VX","버림"],["어","연결어미 EC","버림"]],[0,1,2])};
    TF.k2={l:"키워드 ② · BM25로 청크 점수 계산",t:"필드별 점수를 더하고 가산점을 붙임",d:"제목과 본문에서 각각 BM25 점수를 계산해 더합니다(k1 1.2, b 0.75). 거기에 현행판 가산점 +4를 모두에게 똑같이 더하고, 질문에 연·월이 있으면 발행일·시행일이 맞는 문서에 +6, 추정 날짜가 맞으면 +4를 더합니다.",
      ex:'질문 “2024년 3월 수출 허가 절차”에서 문서 A는 본문 점수가 높고 3월 문서라 가산점까지 받아 앞섭니다. (점수는 설명용 가상 값)',
      svg:T(["문서","본문","제목","현행판","연·월","합계"],[["A (2024-03 발행)","9.1","2.0","+4","+6","21.1"],["B (2023 발행)","7.4","3.1","+4","0","14.5"]],[0])+'<span class="ex"><em>k1 · b</em>필드 하나의 점수를 만드는 두 조절 값입니다. OpenSearch 기본값을 그대로 씁니다.</span>'+T(["값","설명"],[["k1 1.2","같은 단어가 여러 번 나올 때 점수를 얼마나 더 줄지(어느 정도에서 포화). 낮추면 반복을 덜, 높이면 더 반영"],["b 0.75","긴 청크일수록 점수를 얼마나 깎을지. 0이면 길이를 무시, 1이면 완전히 반영"]])};
    TF.k3={l:"키워드 ③ · 후보 자르기",t:"하한과 1위 대비 비율로 자름",d:"후보 청크를 두 번 거릅니다. ① 점수가 하한 14.75 미만이면 버리고, ② 1위 점수의 90% 미만이면 거기서부터 버립니다. 전부 버려져도 검색은 끝나지 않고 dense 결과로 계속 갑니다.",
      ex:'1위 30.0점이면 기준선은 27.0점입니다. (점수는 설명용 가상 값)',
      svg:T(["순위","점수","하한 14.75","90% 기준 27.0","결과"],[["1","30.0","통과","통과","남김"],["2","28.5","통과","통과","남김"],["3","26.0","통과","미만","버림"],["4","20.1","통과","미만","버림"],["5","14.0","미만","미만","버림"]],[0,1])};
    TF.d1={l:"dense ① · 질문을 벡터로 (임베딩)",t:"문장을 통째로 숫자 1024개로",d:"BGE-m3-ko 모델이 질문 문장을 통째로 한 번 읽고 1024차원 벡터 하나로 바꿉니다. 어절 분해도, 어미·조사 제거도 없고 동의어 사전도 쓰지 않습니다. 표현이 달라도 뜻이 가까우면 가까운 벡터가 됩니다.",
      ex:'키워드 검색은 단어가 겹쳐야 찾지만, dense는 뜻이 같으면 찾습니다.',
      svg:T(["","키워드 쪽","dense 쪽"],[["입력 단위","형태소(내용어)","문장 통째로"],["어미·조사","버림","그대로 모델이 읽음"],["동의어 사전","본문에 적용","쓰지 않음"],["출력","검색어 목록","1024차원 벡터 1개"]])};
    TF.d2={l:"dense ② · 가까운 청크 찾기 (kNN)",t:"질문 벡터와 가까운 청크",d:"색인할 때 미리 계산해 둔 청크 벡터(제목: … 본문: … 형태로 임베딩) 중에서 코사인 유사도가 높은 청크를 HNSW 색인으로 찾습니다. 유효기간·공고번호 필터가 이 검색 안에서 함께 적용됩니다.",
      ex:'질문 “수출 허가 어떻게 받아요?”에 문서 쪽 표현이 “승인 신청 절차”여도 가깝게 찾아옵니다. (점수는 설명용 가상 값)',
      svg:T(["순위","청크","코사인 유사도"],[["1","승인 신청 절차 (제23조)","0.84"],["2","허가 대상 물품의 범위","0.82"],["3","수출허가 면제 대상","0.80"],["…","…","…"]])};
    TF.d3={l:"dense ③ · 후보 자르기",t:"하한 미만이면 도메인 밖으로 보고 종료",d:"후보를 ① 코사인 하한 0.7063 미만, ② 1위의 97% 미만으로 거릅니다. 후보가 전부 하한 아래이면 이 질문은 도메인 밖으로 보고 검색을 끝냅니다(키워드 결과가 있어도 빈 결과). BM25는 질문 길이에 점수가 흔들려서 이 판단은 dense가 맡습니다.",
      ex:'1위 0.84이면 기준선은 0.8148입니다. 1위조차 0.7063 미만이면 검색이 끝납니다. (점수는 설명용 가상 값)',
      svg:T(["순위","유사도","하한 0.7063","97% 기준 0.8148","결과"],[["1","0.84","통과","통과","남김"],["2","0.82","통과","통과","남김"],["3","0.80","통과","미만","버림"],["4","0.75","통과","미만","버림"],["5","0.69","미만","미만","버림"]],[0,1])};
    TF.rrf={l:"④ · 문서 단위 RRF 합산",t:"순위만으로 두 목록을 합침",d:"BM25 점수와 코사인 점수는 단위가 달라 직접 더할 수 없어서, 점수 대신 자리(순위)를 씁니다. 문서마다 목록 안 첫 청크의 자리만 세고, 점수는 목록별 1/(60+자리)의 합입니다. 키워드와 dense는 같은 무게이고, 동점이면 dense 자리가 앞섭니다.",
      ex:'두 목록에서 모두 상위인 문서 A·C가 앞서고, dense 1위뿐인 B는 그 절반입니다.',
      svg:T(["문서","키워드","dense","계산","RRF 점수"],[["A","1위","2위","1/61 + 1/62","0.03252"],["C","2위","3위","1/62 + 1/63","0.03200"],["B","-","1위","1/61","0.01639"],["D","3위","-","1/63","0.01587"]],[0,1])};
    TF.cut={l:"⑤ · 컷오프",t:"1위의 90% 미만은 제외",d:"합산 점수가 1위의 0.90배 미만인 문서는 뺍니다. 단 어느 한 목록에서 1위였던 문서는 예외로 남깁니다. 같은 문서의 사본은 1개만 두고 최대 5문서까지 받습니다.",
      ex:'위 예시에서 기준선은 0.03252 × 0.90 = 0.02927입니다. B는 점수가 낮아도 dense 1위여서 살아남습니다. 이 예외가 없으면 한쪽 검색기만 찾은 문서는 항상 잘립니다(21단계).',
      svg:T(["문서","RRF 점수","기준선 0.02927","목록 1위","결과"],[["A","0.03252","통과","키워드 1위","남김"],["C","0.03200","통과","-","남김"],["B","0.01639","미만","dense 1위","예외로 남김"],["D","0.01587","미만","-","버림"]],[0,1,2])};
    TF.pick={l:"⑥ · 문서 안 청크 고르기",t:"문서당 최대 6개, 첫 청크는 dense가 고름",d:"남은 문서마다 최대 6개 청크를 근거로 보냅니다. 첫 청크는 dense가 고른 청크이고, 나머지는 청크 단위 RRF 순서입니다. 7번째부터는 판정 LLM도 답변 LLM도 보지 못합니다.",
      ex:'문서 A의 청크들입니다. dense가 고른 c7이 먼저 오고, 나머지는 두 목록 점수를 합친 순서로 이어집니다. (자리는 설명용 가상 값)',
      svg:T(["청크","키워드","dense","전달 순서"],[["c7","-","1위","1 (dense가 고른 첫 청크)"],["c3","1위","3위","2 (RRF 0.03227)"],["c9","2위","5위","3 (RRF 0.03151)"],["c4","-","2위","4"],["c1","4위","-","5"],["…","…","…","최대 6개까지"]],[0])};
    TF.judge={l:"⑦ · 판정 LLM (선택)",t:"이 근거에 질문이 요구하는 사실이 있나",d:"기본으로 꺼져 있습니다. 켜면 근거의 앞 문서 3개(본문 1500자, 청크 5개)를 읽고 “질문이 요구하는 사실이 적혀 있는가”를 예/아니오로 묻습니다. 아니오이면 결과를 통째로 비우고, 순위는 바꾸지 않습니다. 판정 모델에 연결이 안 되면 결과를 그대로 둡니다.",
      ex:'주제는 맞지만 문서에 사실이 없는 질문은 걸러집니다. 질문의 전제를 부정하는 근거도 근거라서 “예”입니다. (질문은 설명용 가상 값)',
      svg:T(["질문","근거에 있는 것","판정"],[["수출 허가 신청 기한은?","고시: 신청 후 15일 이내","예 → 답변으로"],["작년 A사의 허가 건수는?","허가 절차 안내만 있음","아니오 → 결과 비움"],["이 사양도 미국 허가가 필요한가?","허가가 필요 없다는 규정","예 → 답변으로"]],[0,2])};
    TF.ans={l:"⑧ · 답변 LLM",t:"근거 자료 안의 내용으로만 답함",d:"qwen3-vl-30b-a3b(temperature 0.4)가 근거 문서·청크를 프롬프트에 넣고 답을 스트리밍합니다. 근거에 없는 내용은 답하지 않도록 지시합니다.",
      ex:'프롬프트에 들어 있는 네 가지 규칙입니다.',
      svg:T(["규칙","내용"],[["1","근거 자료에 없는 내용은 답하지 않음 (추측·상식 금지)"],["2","사용한 조문·별표를 인용하고 시행일을 함께 밝힘"],["3","통제 해당 여부를 확정적으로 단정하지 않음"],["4","끝에 yesTrade 확인 안내 문구를 덧붙임"]])};
    TF.fix={l:"⑧ · 고정 문구",t:"LLM을 부르지 않고 안내 문구만 보냄",d:"보낼 근거가 하나도 없으면 답변 LLM을 부르지 않고 정해 둔 문구를 보냅니다. 지어낸 답변을 막고 비용도 들지 않습니다.",
      ex:'아래 경우가 여기로 옵니다. 문구: “문의하신 내용에 대해 확인 가능한 근거 자료를 찾지 못했습니다. 정확한 확인을 위해 전략물자관리시스템(yesTrade)의 전문판정 신청을 이용해 주시기 바랍니다.”',
      svg:T(["상황","결과"],[["dense 후보가 전부 하한 미만 (검색 종료)","고정 문구"],["판정 LLM이 “아니오”로 결과를 비움","고정 문구"],["근거가 남아 있음","답변 LLM"]],[0,1])};
    TF.opt_rewrite={l:"· 질의 재작성 (꺼짐)",t:"일상 표현을 문서 용어로 바꿔 한 번 더 검색",d:"켜면 채팅 모델이 질문을 문서가 쓰는 공식 용어로 다시 써서 키워드 검색을 한 번 더 합니다. 원본 질문은 가중치 1.0, 재작성은 0.5로 합쳐서, 재작성이 틀려도 원래 1위를 밀어내지 못합니다.",
      ex:'사용자 표현과 문서 표현이 구절 수준으로 다를 때 동의어 사전이 못 메우는 틈을 채우려는 장치입니다.',
      svg:T(["사용자 표현","재작성"],[["업체의 약속 문서","수출자 서약서"],["관청에 알리는 서류","지위승계 통지서"]])};
    TF.opt_chunkfirst={l:"· 청크 우선 파이프라인 (꺼짐)",t:"문서를 먼저 고르지 않고 청크를 먼저 고름",d:"현행은 문서를 먼저 고르고 그 안에서 청크를 고릅니다. 이 방식은 반대로 청크를 먼저 고르고 문서는 그 청크의 부모로 정합니다. 같은 Recall에서 문서 우선만큼 정밀하지 못해 기본으로 켜지 않았습니다(33단계).",
      ex:'청크 우선의 이득은 근거가 여러 개인 질문의 Recall뿐이었고, 정밀도를 맞추면 그 이득도 사라졌습니다.',
      svg:T(["","문서 우선 (현행)","청크 우선 (꺼짐)"],[["1단계","문서를 RRF로 고름","청크를 RRF로 고름"],["2단계","문서 안에서 청크 선택","청크의 부모를 문서로 묶음"],["컷오프","문서 점수 기준","청크 점수 기준"]])};
    TF.opt_chunkfilter={l:"· 청크 LLM 관련도 필터 (기본 꺼짐)",t:"무관한 청크만 걸러냄",d:"LLM이 전달될 청크를 0(무관)·1(조건·맥락)·2(직접 근거)로 평가해 0점만 제거합니다. 남은 문서와 청크의 순서는 그대로입니다. 형식 오류나 연결 실패가 나면 원래 후보를 모두 보존합니다. 배포 기본은 꺼짐이고 .env는 켭니다.",
      ex:'135문항에서 청크 Precision이 25.14%에서 37.78%로 올랐고 Recall은 96.30% 그대로였습니다(31단계).',
      svg:T(["등급","뜻","처리"],[["2","직접 근거","남김"],["1","필요한 조건·맥락","남김"],["0","무관","제거"]],[0,1])};
    TF.opt_rerank={l:"· cross-encoder 재정렬 (꺼짐)",t:"문서 안 청크를 모델로 다시 매김",d:"문서 안 후보 청크를 cross-encoder 모델로 다시 점수 매겨 정렬합니다. 효과는 있었지만 지연이 커서, 같은 문제를 지연 없이 푸는 20단계(dense 순서 사용)가 대신하므로 꺼져 있습니다.",
      ex:'문서 안 청크 순서를 정하는 세 방법입니다.',
      svg:T(["방식","순서 기준","추가 지연"],[["RRF 순서","두 목록을 섞음","없음 (정답 청크가 밀림)"],["dense 순서 (현행)","dense가 매긴 순서","없음"],["cross-encoder (꺼짐)","재정렬 모델","큼"]],[1])};
    E["4"]={l:"4단계",t:"문서당 청크 여러 개 반환",d:"문서 순위는 그대로 두고 반환 단위만 넓혀, 문서마다 청크를 여러 개 돌려줍니다. 문서 지표는 청크 수와 무관하게 같고 근거 Recall만 오릅니다. 처음에 4개를 채택했고 8단계에서 6개로 늘렸습니다.",
      ex:'docs-v2-023·024는 정답 문서가 1위인데 근거 청크가 원본 순위 5위여서, 문서당 청크를 1개만 남기던 중복 제거가 그 청크를 버렸습니다.',
      svg:T(["문서당 청크","문서 Recall@5","근거 Recall@5"],[["1 (종전)","87.5%","32.5%"],["2","87.5%","42.5%"],["3","87.5%","55.0%"],["4 (채택)","87.5%","72.5%"],["5","87.5%","83.8%"]],[3])};
    E["5"]={l:"5단계",t:"질의 재작성 융합",d:"채팅 모델이 질문을 문서가 쓰는 말로 다시 써서, 원본과 재작성을 모두 검색하고 순위를 가중 RRF로 합칩니다. 재작성이 원본을 대체하지 않는 것이 핵심입니다. 7단계 이후 이득이 없어 기본값은 꺼짐입니다.",
      ex:'구(句) 단위로 표현이 다른 경우는 동의어 사전으로 닿지 않아 이 방식을 썼습니다.',
      svg:T(["사용자 표현","문서 표현"],[["업체의 약속 문서","수출자 서약서"],["관청에 알리는 서류","지위승계 통지서"]])};
    E["7"]={l:"7단계",t:"모델 교체 후에도 재작성은 남는가",d:"5단계에서 재작성은 BM25 문서 Recall@5를 85.0%에서 87.5%로 올렸습니다. 그런데 6단계에서 임베딩 모델을 바꾸자, 재작성이 고치던 표현 변경 질문 6개를 dense가 이미 모두 상위 5에 넣었습니다. 기능은 설정으로 남기고 꺼 둡니다.",
      ex:'하이브리드는 품질이 같은데 지연만 95.3ms에서 687.4ms로 늘었습니다.',
      svg:T(["검색","재작성 없음","재작성"],[["BM25","85.0% · 18.8ms","87.5% · 529.3ms"],["dense","100.0% · 73.3ms","100.0% · 98.2ms"],["하이브리드","92.5% · 95.3ms","92.5% · 687.4ms"]])};
    E["8"]={l:"8단계",t:"120문항 평가셋과 문서당 청크 6개",d:"평가셋을 40문항에서 120문항으로, 코퍼스를 52개 문서·1,198청크로 바꿨습니다. 이 평가셋에서 문서당 청크 수를 비교해 6개로 정했습니다(문서 지표는 청크 수와 무관). 리랭킹은 채택하지 않았습니다.",
      ex:'그래서 문서 안 7번째 청크부터는 판정 LLM도 답변 LLM도 보지 못합니다.',
      svg:T(["항목","값"],[["평가셋","40문항 → 120문항"],["코퍼스","부모 52개 · 1,198청크"],["문서당 청크","6개 (채택)"]],[2])};
    E["15"]={l:"15단계",t:"BGE-m3-ko 채택",d:"13단계에서 한국어 모델의 우위를 확인한 뒤, 채택에 필요한 나머지를 정리해 기본 임베딩 모델로 올렸습니다. 모델이 Ollama 공식 라이브러리에 없어서 GGUF F16 변환본을 Ollama가 서빙합니다.",
      ex:'별도 PyTorch 서버를 두지 않아도 되어 다른 모델과 똑같이 서빙됩니다.',
      svg:T(["필요했던 것","처리"],[["서빙 경로","GGUF F16 변환본을 Ollama가 서빙"],["재색인","1024차원으로 전체 재색인"],["절대 하한","새 모델 기준으로 다시 잼 (0.7063)"]])};
    E["23"]={l:"23단계",t:"채점 단위를 청크로",d:"검색을 바꾼 단계가 아니라 재는 자를 바꾼 단계입니다. 22단계까지는 문서(부모) 단위로 Recall·Precision을 셌는데, 청크 단위로 바꾸자 문서는 만점이어도 정답이 아닌 청크가 많이 섞여 있다는 것이 드러났습니다. 이후 무관한 청크를 좇아 검색을 몇 군데 고쳤습니다.",
      ex:'문서 단위로는 만점인 질의가, 청크 단위로 보면 정답 청크를 놓친 경우가 있었습니다.',
      svg:T(["고친 곳","내용"],[["공고번호 필터","번호를 대면 그 번호가 든 문서만"],["내려받기 사본 제거","같은 문서의 사본은 1개만"],["시점 힌트","본문 앞머리의 연·월을 가산점에 사용"]])};
    E["25"]={l:"25단계",t:"core와 docs를 섞으면 왜 깎이나",d:"운영은 두 코퍼스를 함께 검색하는데, 인덱스 별칭 두 개를 한 질의로 던지면 IDF와 평균 문서 길이가 인덱스마다 따로 계산되어 서로 다른 자로 채점된 채 한 순위표에 섞입니다. 코퍼스의 성질이 아니라 합치는 방식이 원인이었습니다.",
      ex:'이 문제를 고친 것이 28단계의 dfs_query_then_fetch입니다.',
      svg:T(["상태","채점"],[["문제 (25단계)","인덱스마다 IDF·평균 길이를 따로 계산"],["해결 (28단계)","여러 인덱스를 함께 검색할 때 전역 통계로 계산"]],[1])};
    E["30"]={l:"30단계",t:"연도·반기가 비슷한 문서를 구별",d:"질문에 보고 반기가 적혀 있으면(예: 2026 상반기), 후보 중 제목이 같은 반기이고 주제어도 맞는 문서에 세 번째 순위 목록을 더합니다. 새 문서를 끌어오거나 다른 연도를 지우지는 않습니다.",
      ex:'질문셋이 작고 특정 유형에 치우쳐 있어 일반화는 주장하지 않습니다.',
      svg:T(["질문셋","이전","이후"],[["날짜 진단 14문항","10","14"],["CP 확인 8문항","4","8"],["docs 135 · holdout 69","-","변화 없음"]],[0,1])};
    E["32"]={l:"32단계",t:"정답이 1위에 오지 않는 이유",d:"정답 문서는 대부분 이미 후보 안에 있었고(놓친 19문항 모두 한 검색기 상위 약 20위 안), 여섯 가지 처방 중 반영한 것은 하나입니다. 연도를 대는 질의에서 날짜를 모르는 문서도 가산점(+4)을 받게 했습니다.",
      ex:'날짜가 비어 있는 문서가 연도 질의에서 날짜가 붙은 다른 코퍼스의 문서에 밀리지 않게 하려는 장치입니다.',
      svg:T(["지표","이전","이후"],[["문서 1위 적중","0.837","0.844"],["반환 문서 Precision","0.757","0.773"]],[0,1])};
    E["34"]={l:"34단계",t:"효과 없는 장치를 걷어냄",d:"어휘 검색에 처음 넣고 한 번도 빼 보지 않은 장치들을 하나씩 빼고 재검색해 비교했습니다. 영향이 없는 것은 걷어냈고, 정확성이나 안정성에 필요한 것은 남겼습니다.",
      ex:'동의어는 있고 없고의 차이가 잡음 수준이지만, 지우려면 색인 설정을 바꿔 다시 만들어야 해서 남겼습니다.',
      svg:T(["장치","판정"],[[".standard 부속 필드","쿼리에서 뺌"],["문서 종류 부스트","지움"],["현행판 우대 +4","유지"],["period_hint 가산점 +4","유지"],["시행일 필터","유지"],["동의어 20그룹","유지"]],[0,1])};
    E["37"]={l:"37단계",t:"카테고리를 먼저 고르고 검색",d:"지금까지는 어느 코퍼스에서 찾을지 가리지 않는 통합 검색이었습니다. 사용자가 카테고리를 먼저 고르고 그 안에서만 검색하는 경로를 새로 만들었습니다. 통합 인덱스(core, docs)는 건드리지 않았습니다.",
      ex:'행정·업무 카테고리도 같은 경로로 붙였습니다.',
      svg:T(["항목","내용"],[["첫 카테고리","법령·고시 (문서 20건 · 청크 673개)"],["인덱스","카테고리별 (search-law)"],["API","카테고리 ID를 받는 범용 API + 별도 탭"]])};
    E["1"]={l:"1단계",t:"초기 기준선",d:"v1 키워드 성향 질문 50개를 초기 파서 스냅샷에 던진 첫 측정입니다. 이후 단계의 기준점이지만 2단계에서 평가셋이 바뀌어 직접 비교하지 않습니다. 검색 기능이 아니라 측정 기록입니다.",
      ex:'제목·공고번호·키워드가 질문에 그대로 들어 있어 BM25가 특히 유리한 세트였습니다.',
      svg:T(["검색","Hit@1","Recall@5"],[["BM25","90.0%","98.0%"],["dense","38.0%","58.0%"],["하이브리드","68.0%","87.0%"]])};
    E["2"]={l:"2단계",t:"자연어 기준선",d:"코퍼스는 1단계와 같고 평가셋만 자연어 질문 40개로 바꿨습니다. 바뀐 것이 질문뿐이라 1단계와의 차이는 성능 하락이 아니라 난이도 변화입니다. 측정 기록이라 적용된 기능은 없습니다.",
      ex:'표현 변경형·상황형 질문을 넣자 dense와 하이브리드의 약점이 드러났습니다.',
      svg:T(["항목","1단계","2단계"],[["평가셋","v1 키워드 성향 50개","v2 자연어 40개"],["코퍼스","같은 스냅샷","같은 스냅샷"]])};
    E["3"]={l:"3단계",t:"최신 파서 재추출·재색인",d:"파서를 최신 산출물로 바꿔 재색인하고 2단계와 같은 질문 40개로 다시 쟀습니다. 청크가 ID까지 같고 본문도 거의 같아서 Recall 변화가 거의 없었습니다.",
      ex:'2개 청크에 이미지 마크다운만 추가됐습니다.',
      svg:T(["항목","값"],[["청크 수","1,041개 (2·3단계 동일)"],["본문이 같은 청크","1,039개"],["달라진 것","2개에 이미지 마크다운 추가"]])};
    E["9"]={l:"9단계",t:"식별자 질의 15문항 추가",d:"기존 120문항에는 공고번호·조문번호·HSK 코드로 찾는 질의가 한 건도 없어서, BM25가 잘하는 질문을 평가셋이 물어본 적이 없었습니다. 실제 번호로 15문항을 추가해 측정했습니다. 평가를 늘린 단계라 적용된 검색 기능은 없습니다.",
      ex:'정답 추세를 기존 카테고리와 섞어 읽으면 안 되어 manifest에 예외로 명시했습니다.',
      svg:T(["카테고리","문항"],[["identifier_number","6"],["identifier_article","4"],["identifier_mixed","5"]])};
    E["11"]={l:"11단계",t:"Qwen3-Embedding-0.6B",d:"6단계의 모델 교체가 가장 컸으므로, 더 최신 모델로 한 번 더 같은 이득이 나는지 봤습니다. 속도는 20ms쯤 빨랐지만 품질을 내주고 얻은 속도였고, 전체 재색인의 대가를 치를 근거가 없어 채택하지 않았습니다.",
      ex:'검색 접두사를 빠뜨리면 모델 비교 결론이 뒤집히는 함정도 이 단계에서 확인했습니다.',
      svg:T(["항목","결과"],[["속도","p50 약 20ms 빠름"],["품질","bge-m3보다 낮음"],["재색인","전체 데이터셋 필요"],["판정","채택 안 함"]],[3])};
    E["26"]={l:"26단계",t:"튜닝이 docs에 과적합됐는가",d:"1~25단계의 튜닝값은 모두 docs 한 세트를 보고 골랐습니다. core를 새로 수집해 만든 홀드아웃에서 재 보니 과적합이 있었습니다. 기능이 아니라 검증이라 적용된 것은 없지만, 이 결과로 제목 가중치를 title^1로 낮췄습니다(28단계).",
      ex:'하이브리드 자체는 새 데이터에서도 가장 낫다는 점은 확인됐습니다.',
      svg:T(["지표","값"],[["문서 1위 적중 (같은 규모의 새 데이터)","0.948 → 0.841"],["전체 규모","0.754"],["제목 가중치를 1로 낮추면","+5.8p"]])};
    E["27"]={l:"27단계",t:"질의마다 검색 방식을 고르면 얻을 게 있는가",d:"질문 성격에 따라 키워드만, dense만, 하이브리드를 고르는 라우터를 시험했습니다. 세 번 모두 채택하지 않았고, 모든 질의가 하이브리드(BM25+dense RRF)를 타도록 고정해 두었습니다.",
      ex:'회수 가능한 손실은 방식 선택이 아니라 문서 안 청크 선택 문제였습니다(20단계로 이어짐).',
      svg:T(["시험","결과"],[["오라클 상한","여지는 3문항분"],["학습 라우터","hybrid를 넘지 못함 (−0.74%p, +0.49%p)"],["판정","hybrid 고정 유지"]],[2])};
    E["29"]={l:"29단계",t:"새 검증 질문을 동결하고 평가",d:"출처 36개 문서를 검색 전에 무작위로 뽑고 질문과 정답을 검색 전에 고정한 뒤, 설정을 바꾸지 않고 평가했습니다. 검증 기록이라 적용된 기능은 없습니다.",
      ex:'남은 실패 두 건이 연도·보고 기간 혼동이어서 30단계로 이어졌습니다.',
      svg:T(["항목","결과"],[["core+docs 1위 적중","34 / 36"],["남은 실패","007 · 036 (연도·기간 혼동)"]])};
    E.spl={l:"SPLADE·sparse 시도",t:"BM25 자리에 학습형 어휘 검색을 넣어 봄",d:"BM25 대신 학습형 sparse·SPLADE를 어휘 검색으로 쓰는 시도를 여러 번 했지만 모두 채택하지 않았습니다. 지금 키워드 검색은 BM25입니다.",
      ex:'표의 단계들은 각각 따로 측정한 시도입니다.',
      svg:T(["단계","시도","결과"],[["10","bge-m3 sparse","정밀도 이득 없음(89.4% 대 89.1%), 별도 서빙 필요"],["17","sparse 융합","고정 융합에서는 강점이 안 살아남아 경로 제거"],["24","SPLADE 비교","가능성은 보였으나 전체 채택은 안 함"],["35","파인튜닝","좋아지지 않음 (이긴 1문항, 진 2문항)"],["36","SPLADE+dense","새 문서 P@1 85.5→89.9%지만 신뢰구간이 0에 걸려 기본값 유지"]])};
    E["10"]={l:"10단계",t:"학습형 sparse(bge-m3 sparse head)",d:"bge-m3의 sparse 헤드로 질문·문서를 인코딩해 점곱으로 검색하는 어휘 경로를 시험했습니다. 식별자 질의에서는 강했지만 정밀도 이득이 없고 별도 서빙·재색인이 필요해 채택하지 않았습니다.",
      ex:'우위를 만든 식별자 구간이 n=6, n=4뿐이라서, 0.917 대 1.000도 한 질의의 순위 차이였습니다.',
      svg:T(["항목","결과"],[["정밀도","89.4% 대 89.1%로 동률"],["서빙","Ollama가 서빙하지 않아 SPARSE_ENCODER_URL로 분리"],["재색인","모든 문서에 sparse 벡터 필요"],["판정","채택 안 함"]],[3])};
    E["17"]={l:"17단계",t:"BM25 대신 sparse를 섞으면",d:"16단계에서 어휘 바닥값을 걷자 하이브리드 MRR이 0.9259에서 0.9123으로 내려가서, 어휘 절반을 더 나은 검색기로 바꿔 봤습니다. sparse는 BM25보다 낫지만 고정 융합으로는 그 강점이 살아남지 못해 경로 전체를 제거했습니다.",
      ex:'이 단계는 dense 단독이 모든 융합 조합을 이긴다는 불편한 질문도 남겼습니다.',
      svg:T(["항목","결과"],[["sparse vs BM25","sparse가 더 나은 어휘 검색기"],["고정 융합(RRF)","강점이 살아남지 못함"],["판정","sparse 경로 제거"]],[2])};
    E["24"]={l:"24단계",t:"SPLADE를 현재 검색기와 같은 135문항에 세움",d:"고빈도 일반어에 끌리는 문제를 학습형 sparse가 메우는지, 지금까지의 후보 검색기들과 같은 135문항에서 비교했습니다. SPLADE는 첫 문서 정확도가 가장 높았지만 어느 하나가 모든 지표를 이기지 않아 기본값은 바꾸지 않았습니다.",
      ex:'SPLADE는 telepix/PIXIE-Splade-v1.5이고, 문서 256토큰·상위 256 term으로 인코딩했습니다(ratio 0.97).',
      svg:T(["검색기","P@1","Hit@5"],[["BM25","90.4%","91.9%"],["BGE-M3 sparse","90.4%","91.9%"],["dense","94.1%","94.1%"],["SPLADE","95.6%","96.3%"],["hybrid (현행)","94.1%","99.3%"]],[3])};
    E["35"]={l:"35단계",t:"전략물자 도메인으로 SPLADE 파인튜닝",d:"전략물자 수출입고시 주변에 비슷한 문서가 촘촘히 겹치는 구간(019·127·128)을 고치려고 SPLADE를 도메인 데이터로 파인튜닝했습니다. 좋아지지 않아 채택하지 않았습니다.",
      ex:'가장 나은 설정도 기준 대비 1문항 낮았고, 겨냥한 세 문항은 하나도 고쳐지지 않았습니다.',
      svg:T(["항목","결과"],[["이긴 문항","1개 (006)"],["진 문항","2개 (040, 083)"],["겨냥한 019·127·128","하나도 안 고쳐짐"],["판정","채택 안 함"]],[3])};
    E["36"]={l:"36단계",t:"SPLADE+dense를 현재 hybrid와 같은 조건에서 비교",d:"24단계의 신호가 튜닝 세트 한 곳에서만 나온 것이라, 현재 운영 hybrid를 다시 재서 처음 보는 문서와 질의에서 비교했습니다. SPLADE+dense가 여러 지표에서 앞섰지만 P@1 신뢰구간이 0에 걸쳐 운영 기본값은 바꾸지 않았습니다.",
      ex:'검색 지연은 5~15ms로 작았지만, SPLADE 인코딩이 오래 걸려(약 2.4시간) 일부 세트는 재지 못했습니다.',
      svg:T(["지표 (처음 보는 문서)","현재 hybrid","SPLADE+dense"],[["문서 P@1","85.5%","89.9%"],["Hit@5","92.8%","97.1%"],["반환분 정밀도","65.7%","80.4%"]],[0,1,2])};
    E["38"]={l:"38단계",t:"합성 질의 2,702개로 SPLADE 재파인튜닝",d:"35단계는 학습 신호가 약했다고 보고, 30B 모델이 만든 질의 중 기준 SPLADE가 어려워하는 것만 골라 25배로 늘려 다시 학습했습니다(오답 후보에서 평가 정답 청크는 제외). 사전에 정한 채택 기준을 통과한 설정이 없어 채택하지 않았습니다.",
      ex:'처음 보는 문서에서는 조금 오르고(청크 1위 적중 0.710 → 0.783) 학습 문서군(docs_v2)에서는 내려갔습니다(130 → 125~126). 상위 5청크 회수는 그대로여서 문서 단위 이득이 상쇄됐습니다.',
      svg:T(["문서 1위 (SPLADE 단독)","기준","최고 설정 C"],[["docs_v2 135","130","125"],["holdout-small 69","61","63"],["검증 36","30","33"]],[1,2])};
    E["39"]={l:"39단계",t:"BM25·dense 후보 수를 바꿔 보고 dense를 25개로",d:"hybrid가 BM25에서 25개, dense에서 50개 청크를 가져오던 값이 성능에 미치는 영향을 BM25 5~100개 × dense 10~200개 25조합으로 쟀습니다. 25개 이상이면 지표가 같아서 dense 후보만 50에서 25로 낮췄습니다.",
      ex:'개발 셋(docs_v2 135문항) 한 곳만 썼고 지연은 재지 않았습니다. 이 탐색기에 담긴 질문별 결과는 50개일 때 실행한 값입니다.',
      svg:T(["BM25","dense","문서 P@1","근거 Recall"],[["5","10","96.3","95.9"],["25","50 (이전)","95.6","95.6"],["25","25 (현행)","95.6","95.6"],["100","200","95.6","95.6"]],[2])};
    TF.spl1={l:"SPLADE ① · 질문을 어휘 가중치로",t:"질문에 없는 연관어까지 가중치를 줌",d:"telepix/PIXIE-Splade-v1.5가 질문을 읽고 어휘 전체에 대한 가중치를 매깁니다. 가중치가 큰 상위 256개 term만 남깁니다. 질문에 없는 연관 단어도 가중치를 받아서 표현이 달라도 닿을 수 있고, 자주 나오는 일반어의 영향은 학습으로 줄어듭니다.",
      ex:'docs-v2-001에서 BM25는 질문의 핵심인 에너지·특허보다 제목의 일반어(기술·사업화·공고)에 끌렸습니다. 이 구멍을 메우는지 보려고 시험한 길입니다.',
      svg:T(["","BM25 길","SPLADE 길"],[["질문 처리","형태소로 쪼갠 내용어","어휘 전체에 가중치"],["연관어","동의어 사전 20그룹","학습으로 확장"],["일반어 영향","IDF로 보정","학습으로 낮춤"],["서빙","OpenSearch만","인코더 서버 필요"]])};
    TF.spl2={l:"SPLADE ② · 점곱으로 청크 점수 계산",t:"질문 가중치 × 청크 가중치",d:"청크도 색인할 때 같은 방식(제목+본문 256토큰, 상위 256 term)으로 변환해 OpenSearch의 rank_features 필드에 저장합니다. 검색은 neural_sparse 질의로 질문 가중치와 청크 가중치를 곱해 더한 값이 점수입니다.",
      ex:'문서당 term이 평균 1,458개(docs)라 인덱스가 작고, 검색 지연은 5~15ms로 작았습니다.',
      svg:T(["항목","내용"],[["색인","제목+본문 256토큰 → sparse 벡터"],["저장","rank_features 필드"],["검색","neural_sparse 질의 (점곱)"],["지연","검색 5~15ms"]])};
    TF.spl3={l:"SPLADE ③ · 후보 자르기",t:"1위의 97% 미만은 버림",d:"모델마다 점수 분포가 달라 BM25와 같은 숫자를 쓰지 않고, SPLADE는 1위 점수의 97%(ratio 0.97)를 기준으로 자릅니다. 청크 점수를 먼저 구한 뒤 부모 문서별 최고 청크 점수를 문서 점수로 씁니다.",
      ex:'이 결과를 BM25 대신 dense와 RRF로 합산한 것이 36단계의 SPLADE+dense 비교입니다. 지금 운영에는 쓰지 않습니다.',
      svg:T(["","BM25 길","SPLADE 길"],[["자르는 기준","하한 14.75 + 1위의 90%","1위의 97%"],["문서 점수","목록 안 첫 청크 자리(RRF)","부모별 최고 청크 점수"]])};
    TF.strip={l:"측정·검증 단계",t:"검색 기능이 아니라 재는 방법과 검증",d:"아래 단계들은 검색 동작을 바꾼 것이 아니라 평가 방법·기준선·검증을 다룬 기록입니다. 각 태그를 올리면 그 단계의 내용이 나옵니다.",ex:'초록은 이 기록이 지금의 평가 방식에 쓰이는 단계, 빨간 점선은 기준선이나 검증처럼 적용 대상이 없는 단계입니다.',svg:T(["단계","내용"],[["1·2·3","초기 기준선, 자연어 기준선, 파서 재추출"],["23","채점 단위를 청크로"],["25","core+docs 합쳐 검색할 때 깎이는 원인"],["26","홀드아웃으로 과적합 확인"],["29","동결한 새 질문으로 독립 검증"]])};
    var SEL=".flowsvg g[data-gn], .flowsvg g[data-tip], .an-s[data-gn]";
    function place(e){ var x=e.clientX+14, y=e.clientY+16, w=tip.offsetWidth, h=tip.offsetHeight; if(x+w>innerWidth-8) x=e.clientX-w-14; if(y+h>innerHeight-8) y=e.clientY-h-14; tip.style.left=Math.max(8,x)+"px"; tip.style.top=Math.max(8,y)+"px"; }
    document.addEventListener("mouseover",function(e){ var g=e.target.closest&&e.target.closest(SEL); if(!g){ tip.style.display="none"; return; }
      var k=g.dataset.stage, n=g.dataset.gn, ex=g.dataset.tip?TF[g.dataset.tip]:E[n], i=ex||(k&&stageInfo(k)); if(!i){ tip.style.display="none"; return; }
      var x=ex||X[k];
      var stt=g.dataset.st, pill=stt?'<span class="stp '+stt+'">'+(stt==="un"?"현재 사용 안 함":"현재 적용 중")+'</span>':"";
      tip.innerHTML=pill+"<b>"+esc(i.l)+" · "+esc(i.t)+"</b>"+esc(i.d)+(x?'<span class="ex"><em>예시</em>'+esc(x.ex)+'</span>'+x.svg:'')+"<i>"+(g.dataset.tip?(g.dataset.tip.indexOf("spl")===0?"수치는 24·36단계 측정 기록입니다":"예시는 설명용 가상 값입니다"):"클릭하면 이 단계의 변경 내용을 봅니다 · 도식은 개념도입니다")+"</i>"; tip.style.display="block"; place(e); });
    document.addEventListener("mousemove",function(e){ if(tip.style.display==="block") place(e); });
    document.addEventListener("mouseout",function(e){ if(!e.relatedTarget||!e.relatedTarget.closest||!e.relatedTarget.closest(SEL)) tip.style.display="none"; });
  })();
  document.getElementById("stnav").addEventListener("click",function(e){ var b=e.target.closest("button[data-stage]"); if(b){ st.stage=b.dataset.stage; renderStage(); location.hash=(st.mode==="c"?"cat-stage-":"stage-")+st.stage; return; } var g2=e.target.closest("button[data-go2]"); if(g2){ var t2=document.getElementById(g2.dataset.go2); if(t2) t2.scrollIntoView({block:"start",behavior:"smooth"}); } });
  document.getElementById("txt").oninput=function(e){ st.txt=e.target.value.trim(); renderList(); };
  document.getElementById("list").addEventListener("click",function(e){ var b=e.target.closest("button[data-id]"); if(b) select(b.dataset.id); });
  document.getElementById("detail").addEventListener("click",function(e){
    var t=e.target.closest("[data-tab]"); if(t){ st.tab=t.dataset.tab; var y=document.getElementById("detail").scrollTop; renderDetail(); document.getElementById("detail").scrollTop=y; return; }
    var zb=e.target.closest("[data-zoom]"); if(zb){ var sv=document.getElementById("flowsvg"), cur=parseFloat(sv.style.width)||100; sv.style.width=Math.max(60,Math.min(240,cur+(+zb.dataset.zoom)*20))+"%"; return; }
    var stb=e.target.closest("[data-stage]"); if(stb){ st.stage=stb.dataset.stage; if(st.view!=="s") setView("s"); else { renderStage(); location.hash="stage-"+st.stage; } return; }
    var op=e.target.closest("button[data-open]"); if(op){ var pp=op.dataset.open.split("|"); st.tab="stg"; select(pp[0]); var tg=document.getElementById("tl-"+pp[1]); if(tg) tg.scrollIntoView({block:"start"}); return; }
    var go=e.target.closest("button[data-go]"); if(go&&!go.disabled){ var el=document.getElementById(go.dataset.go); if(el) el.scrollIntoView({block:"start",behavior:"smooth"}); return; }
    var c=e.target.closest("button[data-chunk]"); if(c&&st.view==="q"){ st.chunk=+c.dataset.chunk; var y2=document.getElementById("detail").scrollTop; renderDetail(); document.getElementById("detail").scrollTop=y2; }
  });
  document.addEventListener("keydown",function(e){ if(e.target.closest&&e.target.closest("input,select,textarea")) return;
    var mv=st.view==="cq"?cqMove:st.view==="q"?move:null; if(!mv) return;
    if(e.key==="ArrowDown"||e.key==="j"){ e.preventDefault(); mv(1); } else if(e.key==="ArrowUp"||e.key==="k"){ e.preventDefault(); mv(-1); } });
  window.addEventListener("hashchange",function(){ var id=location.hash.slice(1);
    if(id==="arch"){ if(st.view!=="a") setView("a",true); return; }
    if(id==="meta"){ if(st.view!=="e") setView("e",true); return; }
    if(id==="cat"){ if(st.view!=="c") setView("c",true); return; }
    if(id.indexOf("cat-q-")===0){ var cid=id.slice(6); if(CQ.some(function(x){return x.id===cid;})){ CQS.id=cid; if(st.view!=="cq") setView("cq",true); else renderCq(); } return; }
    if(id.indexOf("cat-stage-")===0){ var ck=id.slice(10); if(/^d3[789]$/.test(ck)){ st.stage=ck; setView("cs",true); } return; }
    if(id.indexOf("stage-")===0){ var sk=id.slice(6); if(STG.some(function(x){return x.k===sk;})){ if(st.view==="s"&&st.stage===sk) return; st.stage=sk; setView("s",true); } return; }
    if(Q.some(function(q){return q.id===id;})) select(id,true); });
  var start=location.hash.slice(1); if(!Q.some(function(q){return q.id===start;})) start="docs-v2-001";
  select(start,true);
  var h0=location.hash.slice(1); if(h0==="arch") setView("a",true); else if(h0==="meta") setView("e",true); else if(h0==="cat") setView("c",true); else if(h0.indexOf("cat-q-")===0&&CQ.some(function(x){return x.id===h0.slice(6);})){ CQS.id=h0.slice(6); setView("cq",true); } else if(/^cat-stage-d3[789]$/.test(h0)){ st.stage=h0.slice(10); setView("cs",true); } else if(h0.indexOf("stage-")===0 && STG.some(function(x){return x.k===h0.slice(6);})){ st.stage=h0.slice(6); setView("s",true); }
})();
