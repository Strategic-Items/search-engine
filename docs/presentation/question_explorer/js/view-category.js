var CATSEL="law100";
var CINFO={
  law100:{id:"cat-law100",tab:"법령·고시",full:"법령·고시 (150건 · 150문항)",head:"법령·고시 150건 · 150문항",
    corpus:'파서의 <code>01_법령고시</code> <b>150건·6,288청크</b>입니다(2026-10-07). 기존 100문항의 근거를 다시 연결하고, 추가된 49개 파일을 읽어 질문 50개를 작성했습니다. 일상어 80, 식별자 33, 별표 34, 신구대비 3문항이며, 근거 불완전 1문항은 평가에서 제외합니다. 새 문항은 지정한 법령·별표 범위에서 필수 답 구절을 모두 담은 청크를 정답으로 삼았습니다. 질문은 <code>data/queries_law150_v1.jsonl</code>, 원본·근거 검증·평가 결과는 <code>data/generated/law150-2026-10-07/</code>에 있습니다.'},
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
var CWHY={};
function catMissed(k){
  var D=CATD[k], docM=[], chM=[];
  D.forEach(function(x){ var rt=cqRet(CATH[k][x.i]); if(!rt.chunk) (rt.doc?chM:docM).push(x); });
  function rows(a){ return a.map(function(x){ var g=CATH[k][x.i].gr;
    return '<tr><td>'+x.i+'</td><td>'+esc(x.c)+'</td><td class="qq">'+esc(x.q)+'</td><td>'+x.n+'</td><td>SPLADE '+(g[0]||'밖')+' · dense '+(g[1]||'밖')+' · 합산 '+(g[2]||'밖')+'</td><td class="qq">'+esc((CATH[k][x.i].positive_review||{}).reason||CATH[k][x.i].diagnosis||CATH[k][x.i].scope_note||CWHY[x.i]||'원인을 확인하지 않았습니다.')+'</td></tr>'; }).join(""); }
  function tbl(t,a,note){ return '<h3>'+t+' ('+a.length+'개)</h3><p class="cap">'+note+'</p><table class="catq"><thead><tr><th>번호</th><th>유형</th><th>질문</th><th>정답<br>청크</th><th>정답 청크의 순위</th><th>왜 틀렸나</th></tr></thead><tbody>'+rows(a)+'</tbody></table>'; }
  return '<h3 style="margin-top:16px">최종 반환에서 정답 라벨을 충족하지 못한 질문 '+(docM.length+chM.length)+'개 / '+D.length+'개</h3>'+
    '<p class="cap">hybrid가 컷오프(1위 점수의 95%)를 거쳐 최종 반환한 청크에 정답 청크가 없는 질문만 적었습니다. 순위는 SPLADE 상위 100, dense 상위 50, 합산 후보(각 25개) 안에서 정답 근거 요건을 모두 충족한 자리입니다. 원인 설명은 저장된 후보 순위와 최종 반환 청크를 비교한 진단입니다.</p>'+
    tbl('정답 라벨 문서 미반환',docM.filter(function(x){return !CATH[k][x.i].scope_note&&x.eligible!==false;}),'반환된 원본 문서 ID가 정답 라벨의 원본 문서 ID와 일치하지 않습니다. 비슷한 제목의 다른 판도 별개 문서로 셉니다.')+
    tbl('정답 청크 미반환',chM.filter(function(x){return !CATH[k][x.i].scope_note&&x.eligible!==false;}),'정답 문서는 반환됐지만 정답 청크가 반환 청크에 없습니다.')+
    tbl('질문 범위 확인 필요',docM.concat(chM).filter(function(x){return CATH[k][x.i].scope_note&&x.eligible!==false;}),'일부 답의 근거 또는 다른 판의 답이 있어 라벨 미적중을 검색 오답으로 단정하지 않습니다.')+tbl('평가 제외',D.filter(function(x){return x.eligible===false;}),'질문의 통제번호 또는 원본 근거가 불완전해 성능 지표에 포함하지 않습니다.');
}
function catTable(k){
  if(k==="law100") return catMissed(k);
  return '<label class="onlym"><input type="checkbox" onchange="this.closest(\'.em\').classList.toggle(\'onlymiss\',this.checked)"> 한 모드라도 놓친 질문만 보기</label>'+
  '<table class="catq"><thead><tr><th>번호</th><th>유형</th><th>질문</th><th>정답<br>청크</th><th>SPLADE</th><th>dense</th><th>hybrid</th></tr></thead><tbody>'+catRows(k)+'</tbody></table>';
}
function pct(x){ return (x*100).toFixed(0)+"%"; }
function f3(x){ return x.toFixed(3); }
function catStats(k){
  var d=CATD[k].filter(function(x){return x.eligible!==false;}), n=d.length, out={k:k, n:n, excluded:CATD[k].length-n, m:[], miss:[[],[],[]]};
  [0,1,2].forEach(function(m){
    var hit=0, top=0, mrr=0;
    d.forEach(function(x){ var r=x.r[m]; if(r!=null){ hit++; mrr+=1/r; if(r===1) top++; } else out.miss[m].push(x.i); });
    out.m.push({rec:hit/n, hit:hit, top:top, mrr:mrr/n});
  });
  if(CATD[k][0].dr) [0,1,2].forEach(function(m){
    var hit=0, top=0, mrr=0, ps=0;
    d.forEach(function(x){ var r=x.dr[m]; if(r!=null){ hit++; mrr+=1/r; if(r===1) top++; } ps+=x.dq[m]; });
    var o=out.m[m]; o.drec=hit/n; o.dtop=top; o.dmrr=mrr/n; o.dprec=ps/n;
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
function catDocTbl(st){
  if(!CATD[st.k][0].dr) return "";
  var best=Math.max.apply(null,st.m.map(function(x){return x.drec;})), bm=Math.max.apply(null,st.m.map(function(x){return x.dmrr;}));
  return '<table class="doct"><thead><tr><th>방식</th><th>문서 Recall</th><th>1위 문서 적중</th><th>문서 MRR</th><th>Precision</th></tr></thead><tbody>'+
    [1,0,2].map(function(m){ var o=st.m[m]; var nm=["SPLADE","dense","hybrid (SPLADE + dense)"][m];
      return '<tr><td>'+nm+'</td><td>'+(o.drec===best?'<b>'+f3(o.drec)+'</b>':f3(o.drec))+'</td><td>'+o.dtop+'/'+st.n+'</td><td>'+(o.dmrr===bm?'<b>'+f3(o.dmrr)+'</b>':f3(o.dmrr))+'</td><td>'+f3(o.dprec)+'</td></tr>'; }).join("")+'</tbody></table>'+
    '<p class="cap">위 표의 청크를 문서로 바꿔 센 것입니다. 문서 순위는 청크 순위에서 같은 문서가 처음 나온 자리를 따라 매기고, 상위 5문서 안에서 모든 근거 요건의 문서가 충족되는 질문을 Recall로 셉니다. 1위 문서 적중과 MRR도 같은 규칙입니다. Precision은 컷오프를 거쳐 반환한 문서 중 <b>정답 라벨 문서</b>(Sonnet 판정이 아니라 정답 청크가 속한 문서)의 비율(질문 평균)입니다. 정답이 아닌 문서에도 관련 내용이 있을 수 있습니다.</p>';
}
function catTbl(st){
  var law=st.k==="law100";
  var best=Math.max.apply(null,st.m.map(function(x){return x.rec;})), bm=Math.max.apply(null,st.m.map(function(x){return x.mrr;}));
  return '<table><thead><tr><th>방식</th><th>청크 Recall</th><th>1위 청크 적중</th><th>청크 MRR</th><th>Precision</th></tr></thead><tbody>'+
    [1,0,2].map(function(m){ var o=st.m[m]; var nm=["SPLADE","dense","hybrid (SPLADE + dense)"][m];
      return '<tr><td>'+nm+'</td><td>'+(o.rec===best?'<b>'+f3(o.rec)+'</b>':f3(o.rec))+'</td><td>'+o.top+'/'+st.n+'</td><td>'+(o.mrr===bm?'<b>'+f3(o.mrr)+'</b>':f3(o.mrr))+'</td><td>'+f3(o.prec)+'</td></tr>'; }).join("")+'</tbody></table>'+catDocTbl(st)+
    (law?'<p class="cap">Precision은 반환한 청크 중 <b>정답 청크</b>의 비율(질문 평균)입니다. 라벨 밖에 있는 관련 청크도 오답으로 셉니다. 법령 150문항은 Sonnet 판정을 하지 않았습니다. 세 방식 모두 청크 순위를 1위 점수 대비 비율로 자른 기준입니다(청크 최대 10개, 문서 최대 5개, 문서당 최대 6개): hybrid 95%(서비스와 같이 SPLADE 25 + dense 25 후보), SPLADE 80%, dense 93%.</p>':'<p class="cap">Precision은 반환한 청크 중 질문과 관련 있는 청크의 비율(질문 평균)입니다. 관련 여부는 정답 청크가 아니라 Sonnet이 청크마다 질문과 본문만 보고 매긴 판정(2 답을 담음, 1 일부 담음, 0 무관)의 1 이상입니다. 세 방식 모두 청크 단위 RRF 또는 청크 순위를 1위 점수 대비 비율로 자른 기준입니다(청크 최대 10개, 문서 최대 5개, 문서당 최대 6개): hybrid 95%, SPLADE 80%, dense 93%. 비율은 이 질문 110개에서 Recall을 지키며 Precision이 오르는 지점을 찾은 값이라 과적합 위험이 있습니다.</p>');
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
  if(st.excluded) li.push('<li>질문·근거 오류로 '+st.excluded+'문항을 지표에서 제외했습니다. 질문별 화면에서 사유를 확인할 수 있습니다.</li>');
  li.push('<li>컷오프를 거친 최종 반환에 정답 청크가 실린 질문은 '+st.fin+'/'+st.n+'개입니다.</li>');
  return '<div class="card"><h2 class="ch">'+info.full+'</h2>'+catTbl(st)+'<ul class="cl">'+li.join("")+'</ul></div>';
}
function catDetail(k){
  var st=catStats(k), M=st.m, info=CINFO[k];
  var row=function(m){ var o=M[m]; return '<tr><td>'+["SPLADE","dense","hybrid (SPLADE + dense)"][m]+'</td><td>'+f3(o.rec)+'</td><td>'+o.top+'/'+st.n+'</td><td>'+f3(o.mrr)+'</td><td>'+f3(o.prec)+'</td><td>'+f3(o.p1)+'</td><td>'+f3(o.dhit)+'</td><td>'+f3(o.retp)+'</td><td>'+o.ret.toFixed(2)+'</td></tr>'; };
  return '<h2 id="'+info.id+'">'+info.head+'</h2>'+
  '<p class="note"><b>코퍼스.</b> '+info.corpus+'</p>'+
  '<p class="cap">놓친 질문은 SPLADE '+catList(st.miss[0])+', dense '+catList(st.miss[1])+', hybrid '+catList(st.miss[2])+'입니다. '+(k==="law100"?'놓친 질문의 원인은 아래 표에 적었습니다.':'놓친 질문 하나하나의 원인은 읽어서 확인하지 않았습니다.')+'</p>'+
  cqChunkCatalog(k)+catTable(k);
}
function catRead(){
  var big=CQ.filter(function(x){return x.n>=10;}).map(function(x){return x.id+'('+x.n+'개)';});
  return '<h2 id="cat-read">읽는 법과 한계</h2><ul class="cl">'+
    '<li>질문 수가 30~150개라 한 문항이 약 <b>0.7~3.3%p</b>입니다. 방식 간 차이가 2~3문항 안쪽이면 순서를 단정하지 않습니다.</li>'+
    '<li>질문은 본문을 본 사람이 쓴 것이라 실제 이용자의 말투보다 본문과 가깝습니다. 사람 검수를 거치지 않았고, 필수 구절이 본문에 있는지만 코드가 확인했습니다.</li>'+
    (big.length?'<li>정답 청크가 10개 이상인 질문은 청크 Recall이 느슨하게 나옵니다: '+big.join(", ")+'.</li>':'')+
    '<li>모두 오프라인 측정이라 카테고리 경로의 운영 컷오프와 필터를 거치지 않았고, 순위는 상위 5청크 기준입니다. 서비스가 실제로 돌려주는 창과 다릅니다.</li>'+
    '<li>BM25는 이 탭에서 더 이상 재지 않습니다. 이전 BM25·dense·hybrid 측정과 직접 비교하지 마세요.</li>'+
    '<li>법령·고시는 2026-10-07의 150문서·6,288청크 색인에서 150문항을 다시 쟀으며, 근거 불완전 1문항을 제외한 149문항으로 집계합니다. 코퍼스·청킹·질문 수가 달라 과거 100문항 수치와 직접 비교하지 않습니다. 행정·민원FAQ는 2026-10-06 색인 그대로입니다.</li>'+
  '</ul>';
}
function panelCat(){
  var k=CATSEL;
  return '<div class="em">'+
  '<p class="note">카테고리 검색은 법령·고시, 행정·업무, 민원FAQ를 각자 인덱스에서 따로 찾는 경로입니다. 질문마다 <b>필수 구절</b>을 적고 그 구절을 모두 담은 청크를 정답 청크로 코드가 찾아 붙였습니다. <b>질문은 본문을 보고 작성한 점검용이며 새 질문에 대한 일반화 성능을 뜻하지 않습니다.</b> 아래 수치는 모두 같은 오프라인 조건입니다: <b>SPLADE는 38단계에서 합성 질의 2,702개로 파인튜닝한 모델</b>, dense는 BGE-m3-ko, hybrid는 SPLADE와 dense를 <b>청크 단위 RRF(k=60)</b>로 합친 뒤 1위 점수의 95% 컷오프로 자른 것이고, 청크 Recall은 <b>상위 5청크</b> 안에서 정답 청크를 찾았는지로 셉니다. LLM 필터·답변 가능성 판정·리랭커 없음, 기준일은 법령 2026-10-07, 나머지 자료 2026-10-06입니다.</p>'+
  '<h2 id="cat-sum">결론부터</h2>'+catSummary(k)+
  '<p class="cap">질문이 30~150개라 한 문항이 0.007~0.033입니다. 방식 간 차이가 1~2문항이면 순서를 단정하지 않습니다. 질문별 결과는 아래에 있습니다.</p>'+
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
  sw.style.gridTemplateColumns="repeat(4,1fr)";
  sw.innerHTML=["common"].concat(Object.keys(CINFO)).map(function(o){ return '<button type="button" data-catsel="'+o+'" aria-pressed="'+(CATSEL===o)+'">'+(o==="common"?"공통":CINFO[o].tab)+'</button>'; }).join("");
  sw.onclick=function(e){
    var b=e.target.closest("button[data-catsel]");
    if(!b||b.dataset.catsel===CATSEL) return;
    CATSEL=b.dataset.catsel;
    if(st.view==="cq"&&CATSEL!=="common"){
      CQS.set=CATSEL;
      var first=CQ.filter(function(x){return x.set===CATSEL;})[0];
      if(first) CQS.id=first.id;
    }
    // 공통 <-> 카테고리로 옮길 때 같은 성격의 보기를 이어 준다(메타데이터 <-> 공통 메타데이터).
    var view=st.view;
    if(CATSEL==="common") view=(st.view==="cm"?"cmc":(st.view==="cs"||st.view==="ca"?st.view:"cs"));
    else view=(st.view==="cmc"?"cm":(st.view==="cs"||st.view==="ca"?"cq":st.view));
    if(view==="ck"&&CATSEL!=="law100") view="cq";
    setView(view);
  };
}

var CMETA={
  law100:{docs:150,chunks:6288,heading:145,type:91,status:53,number:33,effective:38,expiry:0,revision:20,issuer:46,published:42,superseded:23,
    intro:"법령·고시 문서에는 유형·상태·기관 정보가 비교적 많이 들어 있고, 고시 번호·시행일은 일부 문서에만 있습니다."},
  admin30:{docs:20,chunks:183,heading:17,type:5,status:4,number:0,effective:0,expiry:0,revision:0,issuer:2,published:3,superseded:0,
    intro:"행정·업무 문서는 대부분 일반 안내·서식입니다. 문서 유형·상태·기관·게시일은 소수만 채워져 있고, 시행일·고시 번호는 없습니다."},
  faq30:{docs:19,chunks:187,heading:15,type:12,status:0,number:0,effective:0,expiry:0,revision:0,issuer:4,published:2,superseded:0,
    intro:"민원FAQ 문서는 유형(주로 FAQ)과 일부 출처 정보가 있습니다. 상태·번호·유효기간 정보는 현재 자료에서 확인되지 않았습니다."}
};
/* 카테고리별 메타데이터: 카테고리마다 다른 채움 현황만 보여준다.
   파서 → 검색엔진 적용과 검색에서 쓰는 곳은 세 카테고리가 같아 공통 보기로 옮겼다. */
function renderCategoryMeta(){
  var k=CATSEL, info=CINFO[k], m=CMETA[k], nav=document.getElementById("stnav");
  var rows=[
    ["문서 유형",m.type,"document.document_type","규정·지침·FAQ 등"],
    ["상태",m.status,"document.status","안·현행 등 문서 상태"],
    ["문서 번호",m.number,"document.document_number","질문에 적힌 고시·공고 번호와 대조하는 필터에 사용"],
    ["시행일",m.effective,"document.effective_date","기준일 유효기간 필터에 사용"],
    ["종료일",m.expiry,"document.expiry_date","현재 세 카테고리 자료에는 값 없음"],
    ["개정일",m.revision,"document.revision_date","메타데이터로 보관; 검색 점수에는 미사용"],
    ["발행 기관",m.issuer,"document.source","메타데이터로 보관; 검색 점수에는 미사용"],
    ["게시일",m.published,"published_at","메타데이터로 보관; 카테고리 검색 점수에는 미사용"],
    ["제목 경로",m.heading,"heading_path","청크 제목·SPLADE·dense 입력에 함께 반영"],
    ["문서 대체 관계",m.superseded,"document.superseded_by","파서가 연결한 새 판의 식별값. 법령은 22문서 중 6문서만 문서 ID, 16문서는 고시·대통령령 번호를 가리킴"]
  ];
  nav.innerHTML=[["cm-overview","요약"],["cm-fields","필드별 채움"]].map(function(x){return '<button type="button" data-go2="'+x[0]+'"><span class="nl">메타데이터</span><span class="nt">'+x[1]+'</span></button>';}).join("");
  var table='<table><thead><tr><th>항목</th><th>채워진 문서</th><th>파서 원본 필드</th><th>설명</th></tr></thead><tbody>'+rows.map(function(r){return '<tr><td>'+r[0]+'</td><td>'+(r[1]===null?'미집계':'<b>'+r[1]+' / '+m.docs+'</b> ('+Math.round(r[1]*100/m.docs)+'%)')+'</td><td><code>'+r[2]+'</code></td><td>'+r[3]+'</td></tr>';}).join("")+'</tbody></table>';
  document.getElementById("detail").innerHTML='<div class="em">'+
    '<h2 id="cm-overview">'+info.tab+' 메타데이터</h2><p class="note">'+m.intro+'</p><div class="tiles">'+
    '<div class="tile"><span class="tl1">문서</span><span class="tv">'+m.docs+'<small>건</small></span></div><div class="tile"><span class="tl1">청크</span><span class="tv">'+m.chunks.toLocaleString()+'<small>개</small></span></div><div class="tile"><span class="tl1">heading_path</span><span class="tv">'+m.heading+'<small>건</small></span></div></div>'+
    (k==="faq30"?'<p class="warn">민원FAQ는 이 탐색기의 오프라인 평가 코퍼스입니다. 현재 API 카테고리 검색 경로에는 법령·고시와 행정·업무만 등록돼 있습니다.</p>':'')+
    '<h2 id="cm-fields">파서 산출물 · 채움 현황</h2><p class="cap">문서별 중복을 제거해 세었습니다. 각 청크의 반복 메타데이터가 아니라 부모 문서 기준입니다. 원본은 <code>'+info.corpus.match(/<code>([^<]+)/)[1]+'</code> 파서 산출물입니다.</p>'+table+
    '<p class="note">각 필드가 어떤 검색 필드로 넘어가고 검색에서 어디에 쓰이는지는 세 카테고리가 같습니다. <b>공통 · 메타데이터</b> 보기에서 봅니다.</p>'+
    '<p class="note">수치는 현재 파서 산출물 기준(법령 2026-10-07, 나머지 2026-10-06)입니다. 파서 재실행에 따라 문서·청크 수와 채움률이 바뀔 수 있습니다.</p></div>';
  document.getElementById("detail").scrollTop=0;
}

/* 카테고리별 검색: 질문별 보기(목록과 상세). */
var CSETS=[["law100","법령·고시 150건 · 150문항","법령·고시"],["admin30","행정·업무 30문항","행정·업무"],["faq30","민원FAQ 30문항","민원FAQ"]];
var CMODES=["SPLADE","dense","hybrid"];
var CQ=[];
var CFLT=[["all","전체"],["ok","모두 맞음"],["chunk","청크 틀림"],["doc","문서 틀림"]];
function cqStatus(rt){ return rt.excluded?"x":(rt.chunk?"ok":(rt.doc?"chunk":"doc")); }
CSETS.forEach(function(s){ CATD[s[0]].forEach(function(x){ CQ.push({id:s[0]+"-"+x.i, set:s[0], i:x.i, c:x.c, q:x.q, n:x.n, r:x.r, eligible:x.eligible, miss:x.r.some(function(r){return r==null;}), hmiss:!cqRet(CATH[s[0]][x.i]).chunk, st:cqStatus(cqRet(CATH[s[0]][x.i]))}); }); });
var CQS={set:"all", id:CQ[0].id, tab:"sp", chunk:null, flt:"all"};
function cqSet(k){ return CSETS.filter(function(s){return s[0]===k;})[0]; }
function cqVis(){ return CQ.filter(function(x){ return x.set===CATSEL; }); }
function cqList(){
  var all=cqVis(), v=all.filter(function(x){ return CQS.flt==="all"||x.st===CQS.flt; });
  var bar='<div class="seg cqflt" role="group" aria-label="결과 필터">'+CFLT.map(function(f){ var n=f[0]==="all"?all.length:all.filter(function(x){return x.st===f[0];}).length; return '<button type="button" data-cqflt="'+f[0]+'" aria-pressed="'+(CQS.flt===f[0])+'">'+f[1]+'<span class="n">'+n+'</span></button>'; }).join("")+'</div>';
  document.getElementById("list").innerHTML=bar+v.map(function(x){
    return '<button class="item" type="button" role="option" data-cq="'+x.id+'"'+(x.id===CQS.id?' aria-current="true"':'')+'><span class="dot'+(x.hmiss?' miss':'')+'"></span><span><span class="meta">'+esc(cqSet(x.set)[2])+' · '+x.i+' · '+esc(x.c)+'</span><span class="txt">'+esc(x.q)+'</span></span></button>';
  }).join("")||'<p class="note" style="padding:14px">조건에 맞는 문항이 없습니다.</p>';
}
function cqWho(x){ if(x.eligible===false) return "평가 제외"; var N=["SPLADE","dense","hybrid"];
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
  var ranks=(d.gold_ranks||{})[c]||d.gr;
  return '<div class="gd"><h2>놓친 방식이 있는 질문입니다. 정답 청크는 이렇게 생겼습니다</h2><div class="gch">'+esc(cqTitle(c))+' · 정답 청크 '+x.n+'개 중 하나'+' · '+((d.gold_ranks||{})[c]?'이 청크':'정답 근거')+': SPLADE '+cqOut(ranks[0],0)+' · dense '+cqOut(ranks[1],1)+'</div><pre style="white-space:pre-wrap">'+esc(tidy(CATB[c][1]).slice(0,900))+'</pre></div>';
}
function cqHits(list,kind,terms,d){
  return list.map(function(h,i){
    var b=tidy(CATB[h.c][1]), body=esc(b);
    if(terms&&terms.length){
      var patterns=Array.from(new Set(terms.filter(function(t){return t.length>0;}))).sort(function(a,b){return b.length-a.length;}).map(function(t){return t.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");});
      if(patterns.length) body=b.split(new RegExp("("+patterns.join("|")+")","g")).map(function(part,i){return i%2?"<mark>"+esc(part)+"</mark>":esc(part);}).join("");
    }
    var tm=(h.t||[]).map(function(x){return '<span class="tm"><b>'+esc(x[0])+'</b> '+x[1]+'</span>';}).join("");
    var from=kind==="hy"?'<span class="sc" style="flex:none">SPLADE '+(h.a?h.a+'위':'—')+' · dense '+(h.b?h.b+'위':'—')+'</span>':'';
    return '<details class="hit'+(h.g?' gold':'')+'"'+(h.g?' open':'')+'><summary class="hd"><span class="rk">'+(h.comparison?(h.rank?h.rank+'위 · 비교':'정답 비교'):(i+1)+'위')+'</span><span class="ti">'+esc(cqTitle(h.c))+'</span>'+(h.g?'<span class="pin big">근거 요건 청크</span>':'')+cqExtraLabel(d,h.c)+from+'<span class="sc">'+h.s+'</span><span class="more">본문 보기</span></summary>'+
      '<div class="sn">'+body+'</div>'+(tm?'<div class="tms"><span>단어별 기여</span>'+tm+'</div>':'')+'</details>'; }).join("");
}
function cqPanelDn(d,x){
  var hits=d.dn.concat(d.dn_gold||[]);
  var idx = CQS.chunk==null ? Math.max(0,hits.findIndex(function(h){return h.g;})) : CQS.chunk;
  if(idx<0||idx>=hits.length) idx=0;
  var pick=hits.map(function(h,i){ return '<button type="button" data-chunk="'+i+'" aria-pressed="'+(i===idx?'true':'false')+'"><span class="r">'+(h.comparison?'비교':(i+1)+'위')+'</span><span class="t">'+esc(cqTitle(h.c))+(h.g?' <span class="pin">정답'+(h.comparison?' · '+(h.rank?h.rank+'위':'상위 5 밖'):'')+'</span>':'')+'</span><span class="s">'+h.s+'</span></button>'; }).join("");
  var selected=hits[idx], o=selected.attr?{w:selected.attr.w,base:hits.map(function(h,i){return h.attr?h.attr.base:(d.occ?d.occ.base[i]:null);}),d:selected.attr.d.map(function(v){var row=[];row[idx]=v;return row;})}:d.occ;
  if(!o) return cqBar2(d)+'<p class="note">dense 검색은 청크마다 미리 만들어 둔 임베딩과 질문 임베딩의 코사인 유사도로 순위를 냅니다. 청크를 통째로 임베딩했고 질문도 통째로 한 번 임베딩합니다.</p><h2>dense 검색 상위 5 · 코사인 유사도</h2>'+cqHits(d.dn,"dn",null,d);
  var col=o.d.map(function(r){return r[idx];}), mx=Math.max.apply(null,col.concat([0.001]));
  var words=o.w.map(function(w,i){ var dd=col[i], a=dd>0.005?Math.min(0.9,0.12+0.78*dd/mx):0; return '<span style="--a:'+a.toFixed(2)+'" title="'+esc(w)+': 빼면 유사도 '+(dd>=0?'−':'+')+Math.abs(dd).toFixed(3)+'">'+esc(w)+'</span>'; }).join("");
  var top=col.map(function(dd,i){return [o.w[i],dd];}).filter(function(z){return z[1]>0.01;}).sort(function(a,b){return b[1]-a[1];}).slice(0,4);
  var hit=hits[idx], cs=hit.cs, bodyHtml=esc(tidy(CATB[hit.c][1])), cTop="";
  if(cs&&cs.length){
    var cm=Math.max.apply(null,cs.map(function(z){return z[1];}).concat([0.0005]));
    bodyHtml=cs.map(function(z){ var dd=z[1], a=dd>0.001?Math.min(0.9,0.15+0.75*dd/cm):0; return '<span class="cseg" style="--a:'+a.toFixed(2)+'" title="이 구간을 빼면 유사도 '+(dd>=0?'−':'+')+Math.abs(dd).toFixed(4)+'">'+esc(z[0])+'</span>'; }).join(" ");
    var ct=cs.slice().sort(function(a,b){return b[1]-a[1];}).slice(0,2).filter(function(z){return z[1]>0.001;});
    cTop='<p style="margin:6px 0 0;font-size:13.5px">'+(ct.length?'영향이 큰 구간: '+ct.map(function(z){return '<b>“'+esc(z[0])+'”</b> (−'+z[1].toFixed(4)+')';}).join(", "):'뚜렷하게 영향을 준 구간이 없습니다. 청크 전체 의미로 가까워진 경우입니다.')+'</p>';
  }
  return cqBar2(d)+'<p class="note">dense 검색은 청크마다 미리 만들어 둔 임베딩과 질문 임베딩의 코사인 유사도로 순위를 냅니다. 청크를 통째로 임베딩했고 질문도 통째로 한 번 임베딩합니다.</p>'+
   '<p class="note">상위 5 밖 정답 청크는 비교용입니다. 실제 검색 순위·합산·반환 결과에는 포함하지 않습니다. 비교 청크의 dense 점수는 재임베딩한 근사값입니다.</p><div class="two"><div class="pick" role="group" aria-label="dense 상위 5 및 정답 비교 청크">'+pick+'</div>'+
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
  var qt=d.qt.filter(function(t){return t[0]!=="?";});
  var mx=Math.max.apply(null,qt.map(function(t){return t[1];}).concat([0.001]));
  var chips=qt.map(function(t){ var al=Math.min(0.75,0.08+0.67*t[1]/mx); return '<span class="spchip" style="--a:'+al.toFixed(2)+'" title="질문 가중치 '+t[1]+'">'+esc(t[0])+'</span>'; }).join("");
  var terms=[]; d.sp.concat(d.sp_gold||[]).forEach(function(h){ (h.t||[]).forEach(function(x2){ if(terms.indexOf(x2[0])<0) terms.push(x2[0]); }); });
  return cqBar2(d)+'<div><h2>질문을 이렇게 바꿔서 찾았습니다 (SPLADE)</h2><div class="chips" style="margin-top:8px">'+chips+'</div></div><h2>SPLADE 검색 상위 5 · 점수</h2>'+cqHits(d.sp,"sp",terms,d)+(d.sp_gold&&d.sp_gold.length?'<h2>상위 5 밖 정답 청크 · 단어별 기여 비교</h2><p class="note">비교용 정답 청크입니다. 실제 검색 순위·합산·반환 결과에는 포함하지 않습니다. 점수는 SPLADE 벡터와 질문 벡터의 내적입니다(현재 색인에 없는 청크는 저장 본문을 다시 인코딩한 근사값).</p>'+cqHits(d.sp_gold,"sp",terms,d):'');
}
function cqDocId(c){ return c.split("#")[0]; }
function cqDocGold(d,r){ var gold=new Set(d.gc.map(cqDocId)); return r.ch.some(function(c){return gold.has(cqDocId(c[0]));}); }
function cqRet(d){
  var ids=new Set(d.fx.ret.reduce(function(a,r){return a.concat(r.ch.map(function(c){return c[0];}));},[]));
  var groups=d.evidence_groups||[d.gc], eligible=!(d.positive_review&&d.positive_review.evaluation_eligible===false);
  return {doc:d.fx.ret.some(function(r){return cqDocGold(d,r);}), chunk:eligible&&groups.length>0&&groups.every(function(g){return g.some(function(c){return ids.has(c);});}), partial:d.gc.some(function(c){return ids.has(c);}), excluded:!eligible};
}
function cqReturnLabel(rt){ return rt.excluded?'평가 제외 · 근거 확인 필요':(rt.chunk?'정답 근거 충족':(rt.partial?'일부 근거 반환 · 요건 미충족':(rt.doc?'정답 문서 반환 · 청크 누락':'정답 라벨 문서 미반환'))); }
function cqDocEvidence(d){
  var seen=new Set(), rows=d.gc.filter(function(c){var id=cqDocId(c); if(seen.has(id)) return false; seen.add(id); return true;}).map(function(c){
    var id=cqDocId(c), returned=d.fx.ret.some(function(r){return r.ch.some(function(ch){return cqDocId(ch[0])===id;});});
    return '<li>'+esc(CATB[c][0])+' — <b>'+(returned?'문서 반환':'문서 미반환')+'</b><br><code>'+esc(id)+'</code></li>';
  }).join("");
  return '<details class="note"><summary>정답 라벨의 원본 문서 '+seen.size+'건 확인</summary><p>문서 적중은 정답 청크의 원본 문서 ID로 판별합니다. 제목이나 조항이 비슷해도 개정안·신구대조표·현행 별표가 다른 파일이면 별개 문서입니다. 청크 적중은 반환 청크가 정답 라벨에 포함되는지로 따로 판별합니다.</p><ul>'+rows+'</ul></details>';
}
function cqExtraLabel(d,c){
  d=d||{};
  if(d.supporting_chunks&&d.supporting_chunks.indexOf(c)>=0) return '<span class="tag t-mut">내용 일치 · 출처 다름</span>';
  if(d.evidence_groups&&d.evidence_groups.length>1&&d.evidence_groups[0].indexOf(c)>=0) return '<span class="tag t-mut">질문 맥락 근거</span>';
  return '';
}
function cqReviewNote(d){
  var note=d.scope_note?'<p class="warn"><b>질문 범위 확인 필요:</b> '+esc(d.scope_note)+'</p>':'';
  if(d.label_review) note+='<p class="note"><b>동등한 정답 근거 반영:</b> '+esc(d.label_review.reason)+' (추가 '+d.label_review.added_chunks.length+'청크 · '+d.label_review.date+')</p>';
  if(d.supporting_chunks&&d.supporting_chunks.length) note+='<p class="note">같은 답의 내용을 담지만 질문이 지정한 출처를 충족하지 않는 '+d.supporting_chunks.length+'청크는 보조 근거로 구분했습니다.</p>';
  if(d.positive_review){
    note+='<p class="warn"><b>정답 근거 재검증:</b> '+esc(d.positive_review.reason)+' (제외 '+Object.keys(d.positive_review.removed_chunks).length+'청크)'+(d.positive_review.evaluation_eligible===false?' · 이 질문은 결과 요약 지표에서 제외합니다.':'')+'</p>';
    if(d.positive_review.suggested_query) note+='<p class="note">수정 제안: '+esc(d.positive_review.suggested_query)+'</p>';
  }
  if(d.evidence_groups&&d.evidence_groups.length>1) note+='<p class="note">정답 근거는 '+d.evidence_groups.length+'개 요건을 모두 충족해야 합니다. 한 요건의 청크만 반환되면 일부 근거로 표시합니다.</p>';
  if(d.rank_incomplete&&d.rank_incomplete.some(Boolean)) note+='<p class="note">라벨 제외 뒤 남은 근거의 후보 전체 순위는 저장되지 않았습니다. 확인 가능한 순위만 표시하며 미확인 순위는 기록 없음으로 표시합니다.</p>';
  return note;
}
function cqBar2(d){
  var f=d.fx, gr=d.gr, rt=cqRet(d);
  return '<div class="goldbar'+(rt.chunk?'':' miss')+'"><span class="pin big">정답 청크</span><span>SPLADE '+(gr[0]!=null&&gr[0]<=5?'<b>'+gr[0]+'위</b>':'<b class="no">상위 5 밖</b>')+'</span><span>dense '+(gr[1]!=null&&gr[1]<=5?'<b>'+gr[1]+'위</b>':'<b class="no">상위 5 밖</b>')+'</span><span>합산 청크 '+(f.gd?'<b>'+f.gd+'위</b>':'<b class="no">후보 밖</b>')+'</span><span>최종 반환 '+'<b'+(rt.chunk?'':' class="no"')+'>'+cqReturnLabel(rt)+'</b>'+'</span></div>'+cqReviewNote(d)+cqGold(d,CQ.filter(function(o){return o.id===CQS.id;})[0]);
}
function cqSingleCut(name,cls,fx,unit){
  var body="", shown={}, kept=0;
  var ST={keep:"keep",cut:"out",docs:"out",perdoc:"out",budget:"out"};
  var WHY={cut:function(){return '1위 점수의 '+(fx.ratio*100)+'% 미만(= '+(fx.ctop*fx.ratio).toFixed(unit)+' 미만): 제외';}, docs:function(){return '문서 5개 한도: 이미 5개 문서가 찼습니다. 아래부터 새 문서의 청크는 제외하고, 담긴 문서의 청크만 반환';}, perdoc:function(){return '문서당 6개 한도';}, budget:function(){return '청크 10개 한도';}};
  fx.cr.forEach(function(r,i){
    var stt=ST[r[3]], pct=fx.ctop?(r[2]/fx.ctop*100).toFixed(1):"0";
    var line=(stt==="out"&&!shown[r[3]])?'<div class="cutline">─ '+WHY[r[3]]()+' ─</div>':"";
    if(stt==="out") shown[r[3]]=1; else kept++;
    body+=line+'<div class="lrow'+(r[4]?' g':'')+(stt==="keep"?'':' out')+'"><span class="n">'+r[1]+'</span><span class="t">'+esc(cqTitle(r[0]))+(r[4]?' <span class="pin">정답 청크</span>':'')+'</span><span class="sc">'+r[2]+'</span><span class="pc"><i style="width:'+Math.min(100,pct)+'%"></i></span><span class="pp">'+pct+'%</span></div>';
  });
  return '<div class="lcol '+cls+'"><h3>'+name+' <small>청크 '+kept+'개 반환(비율 '+fx.ratio+')</small></h3>'+body+'</div>';
}
function cqLab(l,law){ if(law) return '<span class="tag '+(l===2?'t-ok':'t-mut')+'" title="정답 청크 라벨">'+(l===2?'정답 청크':'라벨 밖')+'</span>'; return '<span class="tag '+(l===2?'t-ok':(l===1?'t-mut':'t-bad'))+'" title="Sonnet 관련도 판정">판정 '+l+'</span>'; }
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
  var step2='<h2 style="margin-top:22px">② 청크 단위 RRF와 컷오프 <small style="font-weight:400;color:var(--muted)">합산 대상 '+f.nf+'개 청크 · 위에서 '+f.cr.length+'개만 표시</small></h2><p class="note">문서로 묶지 않고 청크마다 <b>1/(60+자리)</b>를 더합니다. 두 목록 모두 1위이면 2/61 = 0.0328이 최고점입니다. 1위 점수의 <b>95%</b> 미만은 버리되 어느 목록의 1위 청크는 남깁니다. 남은 청크를 위에서부터 싣는데, 청크는 최대 10개, 문서는 최대 5개, 한 문서의 청크는 최대 6개입니다. 점수가 같으면 dense에서 자리가 앞선 쪽, 그래도 같으면 청크 ID 순입니다. 결과 요약의 hybrid 청크 Recall·MRR은 이 순서의 상위 5청크로 셉니다.'+(x.set==="law100"?' 법령 150문항은 서비스 경로와 같게 SPLADE 상위 25개와 dense 상위 25개만 합산합니다(위 단독 순위는 100·50까지 봅니다).':'')+'</p>'+'<div class="card frows">'+frows+'</div>'+(f.gd?'':'<p class="warn">정답 근거 요건을 모두 충족하는 청크가 합산 후보에 들어오지 못했습니다.</p>');
  return cqBar2(d)+step1+step2;
}
function cqOutP(d,x){
  function r(n,l,lim){ return n?'<span class="rn"><i>'+l+'</i> '+n+'위</span>':'<span class="rn no">'+l+' 상위 '+lim+' 밖</span>'; }
  var out=d.fx.ret.map(function(doc,i){
    var rows=doc.ch.map(function(c,j){ var b=tidy(CATB[c[0]][1]);
      return '<details class="cdet cq-outchunk'+(c[3]?' g':'')+'"'+(c[3]?' open':'')+'><summary><span class="cq-chunk-id"><span class="ord">'+(j+1)+'번째</span><span class="cid">#'+c[0].split("#")[1]+'</span></span><span class="cq-ranks">'+r(c[1],"SPLADE",100)+r(c[2],"dense",50)+'</span><span class="prev">'+esc(b.slice(0,90))+'…</span><span class="cq-markers">'+(c[3]?'<span class="pin">근거 요건 청크</span>':'')+cqExtraLabel(d,c[0])+cqLab(c[4],x.set==="law100")+'</span></summary><div class="cbody2">'+esc(b)+'</div></details>'; }).join("");
    return '<div class="dbox cq-outdoc'+(cqDocGold(d,doc)?' g':'')+'"><div class="dhead cq-outhead"><span class="dn">'+(i+1)+'위</span><span class="dt">'+esc(doc.t)+'</span>'+(cqDocGold(d,doc)?'<span class="pin">정답 라벨 문서</span>':'<span class="tag t-mut">정답 문서 라벨 밖</span>')+'<span class="dm">'+doc.ch.length+'개 청크</span></div><div class="cq-docid"><span>원본 문서 ID</span><code>'+esc(cqDocId(doc.ch[0][0]))+'</code></div><div class="crows">'+rows+'</div></div>'; }).join("");
  return '<p class="note">청크 단위 RRF에서 컷오프(1위 점수의 95%)를 통과한 청크를 문서별로 묶었습니다(청크 최대 10개, 문서 최대 5개, 문서당 최대 6개). 순서는 합산 탭 ②의 순서입니다. '+(x.set==="law100"?'오른쪽 표시는 그 청크가 정답 청크 라벨에 있는지입니다(Sonnet 판정은 하지 않았습니다). 오른쪽 순위는':'오른쪽 "판정"은 Sonnet이 질문과 청크 본문만 보고 매긴 관련도(2 답을 담음, 1 일부 담음, 0 무관)이고, Precision은 판정 1 이상을 관련으로 셉니다. 오른쪽 순위는')+' 그 청크가 SPLADE(상위 100)·dense(상위 50) 목록에서 몇 위였는지이고, "밖"은 그 목록에 없었다는 뜻입니다. <b>이 창은 결과 요약의 청크 Recall(상위 5청크)과 다릅니다.</b> 각 줄을 누르면 청크 본문이 열립니다.</p>'+cqBar2(d)+cqDocEvidence(d)+'<div class="dboxes">'+(out||'<p class="note" style="margin:0">반환된 문서가 없습니다.</p>')+'</div>';
}
function cqAns(d,x){
  var n=d.fx.ret.length, m=d.fx.ret.reduce(function(a,doc){return a+doc.ch.length;},0);
  return cqBar2(d)+'<div class="verdict"><b>이 질문의 판정·답변은 측정하지 않았습니다</b><p>이 탭의 수치는 검색 단계(SPLADE, dense, 합산, 컷오프)만 오프라인으로 잰 것입니다. 판정 LLM과 답변 LLM은 돌리지 않았고, SPLADE는 서비스 검색에 붙어 있지 않습니다. 그래서 판정 결과와 답변 예시는 없습니다.</p></div>'+
  '<p class="note" style="margin-top:12px">서비스 구조대로라면 최종 반환의 <b>문서 '+n+'건·청크 '+m+'개</b>가 답변 LLM에 근거로 넘어갑니다. 판정 LLM은 기본값이 꺼짐이고, 켜면 앞 문서 3개를 읽고 질문이 요구하는 사실이 적혀 있는지 예/아니오로 답해 아니오이면 결과를 비웁니다. 카테고리 검색 경로는 판정을 끈 상태로 둡니다.</p>';
}
function cqChunkImpact(x,e){
  var all=window.CATEGORY_CHUNKING_IMPACT||{}, m=((all.measurements||{})[x.set+'-'+x.i]||{})[e.commit];
  if(!m) return '';
  function num(n){return n.toFixed(4);}
  function signed(n){return (n>0?'+':'')+num(n);}
  function rank(n){return n==null?'근거 미충족':n+'위';}
  function row(name,a,b){return '<tr><td>'+name+'</td><td>'+num(a)+'</td><td>'+num(b)+'</td><td>'+signed(b-a)+'</td></tr>';}
  function ranks(label,field,before,after){before=before||m.before;after=after||m.after;return '<tr><td>'+label+'</td>'+[0,1,2].map(function(i){return '<td>'+rank(before[field][i])+' → '+rank(after[field][i])+'</td>';}).join('')+'</tr>';}
  function contributions(title,entries,unit){
    return '<details class="chunk-impact-terms"><summary>'+title+'</summary><p class="cap">'+unit+'</p><table class="catq"><thead><tr><th>질문 어절·토큰</th><th>이전 기여</th><th>이후 기여</th><th>변화</th></tr></thead><tbody>'+entries.slice(0,10).map(function(t){return '<tr><td>'+esc(t.word||t.token)+'</td><td>'+num(t.before)+'</td><td>'+num(t.after)+'</td><td>'+signed(t.after-t.before)+'</td></tr>';}).join('')+'</tbody></table></details>';
  }
  return '<section class="chunk-impact"><h3>'+esc(x.i)+'번 · 파서·청킹 결과를 교체한 추가 측정</h3><p class="note">모델과 배경 문서를 고정하고, 이 문서의 청크만 Git 수정 전·후로 교체했습니다. 아래 점수는 위에서 비교한 청크, 순위는 대상 문서에서 필수 답 구절을 포함한 첫 청크 기준입니다.</p>'+
    '<table class="catq"><thead><tr><th>비교 청크 점수</th><th>이전</th><th>이후</th><th>변화</th></tr></thead><tbody>'+row('dense 코사인',m.before.denseCosine,m.after.denseCosine)+row('SPLADE 내적',m.before.spladeScore,m.after.spladeScore)+'</tbody></table>'+
    '<table class="catq"><thead><tr><th>대상 문서의 완전한 답 근거</th><th>SPLADE</th><th>dense</th><th>Hybrid</th></tr></thead><tbody>'+ranks('후보 순위', 'candidateRanks')+ranks('컷오프 뒤 반환 순위','returnedRanks')+'</tbody></table>'+
    (m.globalBefore?'<table class="catq"><thead><tr><th>질문 전체의 필수 근거</th><th>SPLADE</th><th>dense</th><th>Hybrid</th></tr></thead><tbody>'+ranks('컷오프 뒤 반환 순위','returnedRanks',m.globalBefore,m.globalAfter)+'</tbody></table><p class="cap">질문 전체 비교에서는 이 커밋으로 모델 입력이 바뀐 문서 '+m.globalChangedParents+'개를 함께 교체했습니다. 허용된 정답 문서들의 반환 청크를 함께 읽어 필수 구절·단위 충족을 셉니다. 다른 문서가 이미 답을 반환한 경우 대상 문서가 좋아져도 질문 전체는 그대로일 수 있습니다.</p>':'')+
    (m.changedSegment?'<details class="chunk-impact-terms"><summary>수정한 본문 구간의 영향도</summary><p class="cap">추가·교체된 줄을 수정 후 청크에서 제거했을 때의 점수 감소량입니다. 양수는 그 구간이 점수를 높였다는 뜻입니다. 문맥 상호작용이 포함된 삭제 실험입니다.</p><p>dense 코사인 감소: <b>'+signed(m.changedSegment.denseDrop)+'</b> · SPLADE 점수 감소: <b>'+signed(m.changedSegment.spladeDrop)+'</b></p><pre>'+esc(m.changedSegment.text||'본문 줄 변화 없음 · 제목 경로 변경')+'</pre></details>':'')+
    contributions('dense: 질문 어절별 영향도 전후',m.denseWords,'어절 하나를 지웠을 때 감소하는 코사인 값입니다. 음수는 해당 어절을 지우면 점수가 오름을 뜻합니다. 기여도 변화가 큰 순서로 표시합니다.')+
    contributions('SPLADE: 질문 토큰별 점수 기여 전후',m.spladeTokens,'질문 토큰 가중치 × 청크 토큰 가중치입니다. 확장 토큰도 포함하며, 점수 기여 변화가 큰 순서로 표시합니다.')+
    '<p class="cap">dense 점수가 오르더라도 경쟁 청크·컷오프 때문에 반환 순위는 그대로일 수 있습니다. 정확한 코사인·희소 내적으로 계산한 오프라인 비교이며 실제 ANN 재색인 결과는 아닙니다. 단위 질문(111·125·143)은 단위까지 있어야 근거 충족으로 셌습니다.</p></section>';
}
function cqChunkMeasuredSummary(x,e){
  var m=((((window.CATEGORY_CHUNKING_IMPACT||{}).measurements)||{})[x.set+'-'+x.i]||{})[e.commit];
  if(!m||!m.globalBefore) return '';
  var a=m.globalBefore.returnedRanks[2], b=m.globalAfter.returnedRanks[2], status;
  if(a==null&&b!=null) status='질문 전체: 완전한 근거 미반환 → Hybrid '+b+'위 반환';
  else if(a!=null&&b==null) status='질문 전체: Hybrid '+a+'위 → 완전한 근거 미반환';
  else if(a==null) status='질문 전체: 수정 전후 모두 완전한 근거 미충족';
  else status='질문 전체: Hybrid '+a+'위 → '+b+'위'+(a===b?' (반환 순위 동일)':'');
  return '<br><b>'+esc(status)+'</b><br>비교 청크: dense '+m.before.denseCosine.toFixed(4)+' → '+m.after.denseCosine.toFixed(4)+' · SPLADE '+m.before.spladeScore.toFixed(4)+' → '+m.after.spladeScore.toFixed(4);
}
function cqChunkEntries(x){ return (window.CATEGORY_CHUNKING_HISTORY||{})[x.set+'-'+x.i]||[]; }
function cqChunkStory(d,x,phase){
  var entries=cqChunkEntries(x).filter(function(e){return !phase||e.phase===phase;});
  function excerpt(body){ return body.length>650?body.slice(0,650)+'…':body; }
  function path(e){return e.path.length?e.path.join(' → '):'제목 경로 없음';}
  return entries.map(function(e){
    var before=excerpt(e.before.body), after=excerpt(e.after.body);
    if(e.commit==='e1749ca'&&e.beforeFootnote) before+='\n\n[별도 각주 #0022]\n'+e.beforeFootnote.slice(e.beforeFootnote.indexOf('※※'));
    var ranks=e.beforeRanks?'<p class="chunk-story-label">이전 후보: SPLADE '+e.beforeRanks[0]+'위 · dense '+e.beforeRanks[1]+'위 · 합산 '+e.beforeRanks[2]+'위<br>이후 41단계 반환: SPLADE '+e.afterRanks[0]+'위 · dense '+e.afterRanks[1]+'위 · Hybrid '+e.afterRanks[2]+'위</p>':'';
    var source='<a href="'+e.url+'" target="_blank" rel="noopener">파서 '+e.commit+'</a>'+(e.searchUrl?' · <a href="'+e.searchUrl+'" target="_blank" rel="noopener">이전 검색 기록</a>':'');
    return '<section class="chunk-story"><div class="chunk-story-kicker">청킹 변경 · '+esc(e.date.slice(0,10))+' · '+esc(e.commit)+'</div><h2>'+esc(e.title)+'</h2><p class="chunk-story-question">질문: '+esc(x.q)+'</p>'+
      '<span class="tag '+(e.kind==='retrieval'?'t-ok':'t-mut')+'">'+esc(e.rankNote.replace('수정 전후 검색 재측정 기록 없음','당시 검색 전후 기록 없음'))+'</span>'+ranks+
      '<div class="chunk-story-grid"><article class="chunk-story-before"><h3>① 이전 문제</h3><p>'+esc(e.problem)+'</p><p class="chunk-story-label">'+esc(e.before.id.split('#').pop())+' · '+esc(path(e.before))+'</p><pre>'+esc(before)+'</pre></article>'+
      '<article class="chunk-story-after"><h3>② 청킹 수정 후</h3><p>'+esc(e.change)+'</p><p class="chunk-story-label">'+esc(e.after.id.split('#').pop())+' · '+esc(path(e.after))+'</p><pre>'+esc(after)+'</pre></article></div>'+
      '<div class="chunk-story-result"><b>무엇이 개선됐나</b>'+esc(e.benefit)+cqChunkMeasuredSummary(x,e)+(e.kind==='retrieval'?'<br><b>'+esc(e.rankNote)+'</b>':'')+'</div>'+
      cqChunkImpact(x,e)+'<details class="chunk-story-evidence"><summary>Git 전후 본문 전체와 근거 보기</summary><p>'+source+'</p><p>수정 전</p><pre>'+esc(e.before.body)+'</pre><p>수정 후</p><pre>'+esc(e.after.body)+'</pre></details>'+
      '<p class="chunk-story-evidence">'+esc(e.comparisonNote||'관련 근거 청크의 구조 변경을 Git에서 확인했습니다. 당시 저장된 검색 전후 평가가 없는 경우 구조 개선 기록으로 표시합니다. 추가 통제 측정은 dense·SPLADE 영향도 표에서 확인합니다.')+'</p></section>';
  }).join('');
}
function cqChunkPhase(d,x,phase){
  var titles={before37:'청킹 · 37단계 이전',before41:'청킹 · 41단계 평가 전',after45:'청킹 · 45단계 이후 추가 기록'};
  var body=cqChunkStory(d,x,phase);
  return body?'<div class="tl-card chunk" id="cq-chunk-'+phase+'"><div class="tl-box"><div class="tl-h"><span class="sl">청킹</span><span class="st">'+titles[phase]+'</span></div>'+body+'</div></div>':'';
}
function cqChunkCatalog(k){
  var entries=Object.keys(window.CATEGORY_CHUNKING_HISTORY||{}).filter(function(id){return id.indexOf(k+'-')===0;});
  if(!entries.length) return '';
  function measurements(id){return Object.values(((window.CATEGORY_CHUNKING_IMPACT||{}).measurements||{})[id]||{});}
  function outcome(m){var a=(m.globalBefore||m.before).returnedRanks[2], b=(m.globalAfter||m.after).returnedRanks[2];return a==null?(b==null?0:1):(b==null?-1:(a>b?1:(a<b?-1:0)));}
  entries.sort(function(a,b){return measurements(b).filter(function(m){return outcome(m)>0;}).length-measurements(a).filter(function(m){return outcome(m)>0;}).length||a.localeCompare(b);});
  return '<details class="card"><summary><b>청킹 변경·영향도 기록 · 질문 '+entries.length+'개</b></summary><p class="note">질문 번호를 누르면 단계별 변화의 청킹 전후 기록을 엽니다. 점수·기여도·고정 배경 반환 순위 비교를 함께 보여줍니다.</p><table class="catq"><thead><tr><th>질문</th><th>청킹 변경</th><th>추가 통제 측정</th></tr></thead><tbody>'+entries.map(function(id){
    var es=window.CATEGORY_CHUNKING_HISTORY[id], ms=measurements(id);
    var description=ms.length?'dense 점수 상승 '+ms.filter(function(m){return m.delta.denseCosine>0.00001;}).length+'건 · SPLADE 상승 '+ms.filter(function(m){return m.delta.spladeScore>0.0001;}).length+'건<br>질문 전체 Hybrid 근거 반환: 개선 '+ms.filter(function(m){return outcome(m)>0;}).length+' · 악화 '+ms.filter(function(m){return outcome(m)<0;}).length+' · 동일 '+ms.filter(function(m){return outcome(m)===0;}).length:'추가 측정 기록 없음';
    return '<tr><td><button type="button" class="sidebtn" data-chunk-q="'+id+'">'+id.split('-').pop()+'</button></td><td>'+es.map(function(e){return esc(e.title);}).join('<br>')+'</td><td>'+description+'</td></tr>';
  }).join('')+'</tbody></table></details>';
}
function cqStg(d,x){
  var H=window.CATEGORY_STAGE_HISTORY||{}, h=x.set==="law100"&&H[x.i];
  if(!h) return '<div class="tl">'+['before37','before41','after45'].map(function(p){return cqChunkPhase(d,x,p);}).join('')+'</div><p class="note">'+(x.set==="law100"?'이 질문은 법령 150문서로 늘릴 때 추가되어, 45단계까지의 질문별 기록이 없습니다.':'이 카테고리는 45단계까지 같은 질문을 단계별로 다시 잰 기록이 없습니다.')+' 현재 검색 결과는 다른 탭에서 확인할 수 있습니다.</p>';
  function rank(r){ return r==null?'<b class="no">정답 청크 미반환</b>':'<b>정답 청크 '+r+'위 반환</b>'; }
  function change(before,after){
    if(before==null&&after!=null) return '<span class="tl-b up">못 찾음 → 찾음</span>';
    if(before!=null&&after==null) return '<span class="tl-b dn">찾음 → 못 찾음</span>';
    if(before!=null&&after!=null&&before!==after) return '<span class="tl-b same">'+before+'위 → '+after+'위</span>';
    return '<span class="tl-b same">반환 여부 변화 없음</span>';
  }
  function mode(name,cls,before,after){
    return '<div class="mc '+cls+'"><span class="ml">'+name+'</span>'+(after===undefined?rank(before):rank(after))+(after===undefined?'':'<span class="dl">기준 '+(before==null?'미반환':before+'위')+' → 실험 '+(after==null?'미반환':after+'위')+'</span>')+'</div>';
  }
  var baseline=h.s41[2], note={
    37:'이 질문은 37단계의 법령 21문항에 없었습니다. 이 단계의 결과를 이 질문에 옮겨 적지 않습니다.',
    38:'38단계의 설정 비교도 앞선 법령 21문항을 사용했습니다. 현재 질문의 당시 순위 기록은 없습니다.',
    39:'후보 수 스윕은 docs 질문으로 측정했습니다. 이 법령 질문의 단계별 결과는 없습니다.',
    40:'RRF 방식 비교의 법령 100문항 질문별 결과는 저장되지 않았습니다.',
    43:'메타데이터 입력 실험의 SPLADE 결과는 부분 갱신 오류로 오염됐습니다. 이 질문의 성공·실패 변화로 사용하지 않습니다.'
  };
  var cards=[], rib=[];
  function addChunk(phase){var html=cqChunkPhase(d,x,phase); if(html){cards.push(html);rib.push('<button type="button" class="chunk" data-go="cq-chunk-'+phase+'"><span class="rl">청킹</span><span class="rs">'+({before37:'37단계 전',before41:'41단계 전',after45:'45단계 이후'})[phase]+'</span></button>');}}
  addChunk('before37');
  for(var n=37;n<=45;n++){
    if(n===41) addChunk('before41');
    var info=stageInfo('d'+n), lines='', cls='nd', label='기록 없음', badge='';
    if(n===37){
      lines='<p class="note">'+note[n]+'</p>';
    } else if(n===41){
      cls=baseline==null?'none':'chunk'; label=baseline==null?'정답 미반환':'정답 '+baseline+'위';
      lines='<p class="note">법령 100문서·100문항으로 늘려 측정한 기준선입니다. 아래 순위는 컷오프 뒤 반환 목록에서 모든 근거 요건을 충족한 첫 청크의 자리입니다.</p>'+
        '<div class="tl-modes">'+mode('SPLADE', 'kw',h.s41[0])+mode('dense','vec',h.s41[1])+mode('hybrid','hy',baseline)+'</div>';
    } else if(n===42){
      cls=h.s42[1]==null?'none':'chunk'; label=h.s42[1]==null?'실험: 미반환':'실험: '+h.s42[1]+'위';
      badge=change(baseline,h.s42[1]);
      lines='<p class="note">같은 100문서·100문항에서 SPLADE 입력에 제목 경로를 추가한 비교 실험입니다. 제목 경로 입력은 이후 채택됐지만, 이 순위는 재색인 전의 통제 실험 결과입니다.</p>'+
        '<div class="tl-modes">'+mode('SPLADE','kw',h.s41[0],h.s42[0])+mode('hybrid','hy',baseline,h.s42[1])+'</div>'+
        '<div class="tl-line">'+(h.s41[0]==null&&h.s42[0]!=null&&baseline!=null?'SPLADE 단독은 새로 찾았지만, hybrid는 기준선에서도 정답을 반환했습니다.':(h.s41[0]==null&&h.s42[0]!=null&&h.s42[1]==null?'SPLADE 단독은 새로 찾았지만, hybrid 컷오프 뒤에는 정답이 없습니다.':''))+'</div>';
    } else if(n===44){
      cls=h.s44==null?'none':'chunk'; label=h.s44==null?'실험: 미반환':'실험: '+h.s44+'위';
      badge=change(baseline,h.s44);
      lines='<p class="note">같은 100문서에서 판본을 지정하지 않은 질문의 대체된 문서 점수를 0.97배로 낮춘 실험입니다. 선택 기능으로 구현됐고 기본값은 1.0이라 운영 기본 결과는 기준선과 같습니다.</p>'+
        '<div class="tl-modes">'+mode('hybrid · 선택 기능','hy',baseline,h.s44)+'</div>';
    } else if(n===45){
      cls=h.s45==null?'none':'chunk'; label=h.s45==null?'실험: 미반환':'실험: '+h.s45+'위';
      badge=change(baseline,h.s45);
      lines='<p class="note">번호로 적힌 대체 관계를 문서 ID로 풀어 새 판을 붙인 실험입니다. 전체 100문항에서 새로 찾은 정답은 없고 한 질문은 잃어 적용하지 않았습니다.</p>'+
        '<div class="tl-modes">'+mode('hybrid · 미적용 실험','hy',baseline,h.s45)+'</div>';
    } else lines='<p class="note">'+note[n]+'</p>';
    rib.push('<button type="button" class="'+cls+'" data-go="cq-stage-'+n+'"><span class="rl">'+n+'단계</span><span class="rs">'+label+'</span></button>');
    cards.push('<div class="tl-card '+cls+'" id="cq-stage-'+n+'"><div class="tl-box"><div class="tl-h"><span class="sl">'+n+'단계</span><span class="st">'+esc(info.t)+'</span>'+badge+'</div>'+lines+'</div></div>');
  }
  addChunk('after45');
  var findings=[];
  var chunkEntries=cqChunkEntries(x);
  if(chunkEntries.length) findings.push('청킹 변경 '+chunkEntries.length+'건을 아래 청킹 카드에 기록했습니다. '+(chunkEntries.some(function(e){return e.kind==='retrieval';})?'수정 전 검색 실패와 이후 정답 반환 기록이 있습니다.':(((window.CATEGORY_CHUNKING_IMPACT||{}).measurements||{})[x.set+'-'+x.i]?'추가 통제 측정에서 dense·SPLADE 점수, 토큰 기여도, 대상 문서의 근거 반환 순위를 비교했습니다.':'근거 구조 변경은 확인됐으며 추가 검색 효과 측정은 진행 중입니다.')));
  var measured=((window.CATEGORY_CHUNKING_IMPACT||{}).measurements||{})[x.set+'-'+x.i]||{};
  var improvements=chunkEntries.filter(function(e){var m=measured[e.commit];return m&&m.globalAfter&&m.globalAfter.returnedRanks[2]!=null&&(m.globalBefore.returnedRanks[2]==null||m.globalAfter.returnedRanks[2]<m.globalBefore.returnedRanks[2]);});
  if(improvements.length) findings.push('질문 전체의 근거 반환 개선: '+improvements.map(function(e){var m=measured[e.commit];return e.title+' ('+(m.globalBefore.returnedRanks[2]==null?'근거 미반환':m.globalBefore.returnedRanks[2]+'위')+' → '+m.globalAfter.returnedRanks[2]+'위)';}).join(', ')+'.');
  if(x.i==='033') findings.push('Git의 수정 전 50문항 평가에서 SPLADE·dense·Hybrid 모두 정답 상위 5 밖이었습니다. 분리된 각주를 표 행에 연결한 뒤, 41단계 100문항 평가에서 Hybrid 정답 '+baseline+'위로 반환됐습니다. 코퍼스와 검색 설정 변화도 포함된 전후 기록입니다.');
  if(x.i==='038') findings.push('2017 세부지침의 쪽 단위 표를 행으로 나누었습니다. 이전 2위→이후 1위 기록에는 정답 라벨 재작성도 포함됩니다.');
  if(h.s41[0]==null&&h.s42[0]!=null) findings.push('42단계 제목 경로 실험에서 SPLADE 단독은 정답을 새로 찾았습니다'+(baseline!=null?'(hybrid는 이미 반환)':'(hybrid는 여전히 미반환)')+'.');
  if(baseline!=null&&h.s42[1]==null) findings.push('42단계 제목 경로 실험에서는 hybrid가 기준선의 정답을 잃었습니다.');
  if(baseline==null&&h.s44!=null) findings.push('44단계 판본 가중치 실험에서 hybrid가 정답을 '+h.s44+'위로 새로 반환했습니다. 이 기능은 기본 꺼짐입니다.');
  if(baseline!=null&&h.s45==null) findings.push('45단계 새 판 연결 실험에서는 기준선의 정답을 잃었습니다. 이 실험은 적용하지 않았습니다.');
  if(!findings.length) findings.push('기록된 실험에서 이 질문의 정답 반환 여부가 새로 개선된 사례는 없습니다.');
  var labelNote=(d.positive_review||d.label_review||d.scope_note)?'<p class="warn">이 질문은 이후 정답 근거나 질문 범위를 재검토했습니다. 아래 과거 순위는 당시 라벨 기준이며, 현재 판정은 질문 상세의 근거 검토를 함께 확인해야 합니다.</p>':'';
  return '<div class="tl-line"><b>발표용 관찰:</b> '+findings.map(esc).join(' ')+'</div>'+labelNote+
    '<div class="tl-rib" role="group" aria-label="37~45단계 질문별 결과">'+rib.join('')+'</div>'+
    '<p class="note">41·42·44·45단계 순위는 법령 100문서·100문항 시점의 저장된 결과입니다. 각 실험은 41단계 기준선과 따로 비교했습니다. 37·38단계는 다른 질문셋, 39·40단계는 이 질문의 기록이 없고 43단계 SPLADE 실험은 결과 오염으로 제외했습니다. 현재 다른 탭의 150문서 결과와 직접 비교하지 않습니다.</p>'+
    '<div class="tl">'+cards.join('')+'</div>';
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
    cell("c4 rs",cqNode("fx",kept?"ok":"lost","④ 컷오프 95%",kept?'정답 청크 유지':(f.gd?'정답 청크 제외':'정답 청크 후보 없음'),"청크 "+nret+"개 남음",false))+
    cell("c5 rs",cqNode("out",rt.chunk?"ok":"lost","⑤ 반환",cqReturnLabel(rt),"문서 "+f.ret.length+"건 · 청크 "+nret+"개",CQS.tab==="out"))+
    cell("c6 rs",cqNode("ans","","⑥ 판정·답변",'측정 안 함',"오프라인 측정에 없음",CQS.tab==="ans"));
}
function cqDetail(){
  var x=CQ.filter(function(o){return o.id===CQS.id;})[0]||CQ[0], s=cqSet(x.set), d=CATH[x.set][x.i], el=document.getElementById("detail");
  var rt=cqRet(d);
  el.innerHTML='<div class="wrap"><div><div class="kicker"><span>'+esc(s[2])+' · '+x.i+'</span><span>'+esc(x.c)+'</span><span class="tag '+(rt.chunk?'t-ok':'t-bad')+'">'+cqReturnLabel(rt)+'</span><span class="tag t-mut">상위 5청크: '+esc(cqWho(x))+'</span><span class="tag t-mut">정답 청크 '+x.n+'개</span></div><p class="q">'+esc(x.q)+'</p></div>'+
  '<section aria-label="단계별 경로"><div class="flow">'+cqFlow(d,x)+'</div></section>'+
  '<div><div class="tabs" role="tablist">'+CTABS.map(function(t){return '<button type="button" role="tab" data-ctab="'+t[0]+'" aria-selected="'+(CQS.tab===t[0]?'true':'false')+'">'+t[1]+'</button>';}).join("")+'</div><div class="panel" role="tabpanel">'+cqPanel(d,x)+'</div></div>'+
  '<p class="note"><button type="button" class="sidebtn" data-cqgo="'+CINFO[x.set].id+'">결과 요약에서 보기</button></p>'+
  '<p class="cap">질문은 정답을 아는 사람이 본문을 보고 쓴 점검용이라 성능 판단에는 쓰지 않습니다. 오프라인 측정이라 LLM 필터·판정을 거치지 않았습니다. "정답 근거 충족"은 청크 단위 RRF와 95% 컷오프 뒤 반환한 청크가 모든 근거 요건을 충족하는지이고, 위 청크 Recall은 상위 5청크 기준입니다.</p></div>';
  el.scrollTop=0;
}
function cqSelect(id,nohash){ CQS.id=id; CQS.chunk=null; cqList(); cqDetail(); if(!nohash) location.hash="cat-q-"+id; var c=document.querySelector('#list [aria-current="true"]'); if(c&&c.scrollIntoView) c.scrollIntoView({block:"nearest"}); }
function cqMove(d){ var v=cqVis(); if(!v.length) return; var i=v.findIndex(function(x){return x.id===CQS.id;}); cqSelect(v[Math.max(0,Math.min(v.length-1,i<0?0:i+d))].id); }
function cqInit(){
  document.getElementById("list").addEventListener("click",function(e){ var fb=e.target.closest("button[data-cqflt]"); if(fb){ CQS.flt=fb.dataset.cqflt; cqList(); return; } var b=e.target.closest("button[data-cq]"); if(b) cqSelect(b.dataset.cq); });
  document.getElementById("detail").addEventListener("click",function(e){ var link=e.target.closest('[data-chunk-q]'); if(link){var question=CQ.filter(function(q){return q.id===link.dataset.chunkQ;})[0]; if(question){CQS.id=question.id; CQS.set=question.set; CATSEL=question.set; CQS.tab='stg';setView('cq');}return;} var ct=e.target.closest("[data-ctab]"); if(ct&&st.view==="cq"){ CQS.tab=ct.dataset.ctab; var y=this.scrollTop; cqDetail(); this.scrollTop=y; return; } var g=e.target.closest("button[data-cqgo]"); if(g){ CATSEL=Object.keys(CINFO).filter(function(o){return CINFO[o].id===g.dataset.cqgo;})[0]||"law100"; setView("c"); setTimeout(function(){ var el=document.getElementById(g.dataset.cqgo); if(el) el.scrollIntoView({block:"start"}); },0); return; } var c=e.target.closest("button[data-chunk]"); if(c&&st.view==="cq"){ CQS.chunk=+c.dataset.chunk; var y2=this.scrollTop; cqDetail(); this.scrollTop=y2; } });
}
function renderCq(){ cqList(); cqDetail(); }

/* 카테고리별 검색 탭의 38단계: 설정별 결과(문서 stage-38 기록의 카테고리 표). */
var C38={
 head:"학습한 SPLADE 설정을 새 카테고리 코퍼스에서 하나씩 쟀고, 이 탭의 SPLADE는 설정 C를 씁니다",
 what:["합성 질의 2,702개로 SPLADE를 다시 학습한 설정 A, C, D, E를 법령·고시 21문항과 행정·업무 30문항에서 기준(학습 안 한 PIXIE-Splade-v1.5), dense와 같은 조건으로 비교했습니다. 설정 B는 학습 도중 메모리 부족으로 실패해 다시 돌리지 않았습니다.","표와 발표의 SPLADE는 설정 C를 씁니다. 카테고리 검색 코드에 적용했으며, docs·core 검색은 기존 BM25를 유지합니다."],
 why:["법령에서 C는 SPLADE 단독 문서 P@1이 0.810에서 0.952로 올라 가장 높았고(+3문항), 행정·업무에서는 네 설정이 모두 0.900(+1문항)으로 같았습니다.","청크 Hit는 오르지 않았습니다(법령 0.762에서 0.810, 행정·업무 0.967에서 0.933). 1위로 올리지만 더 많이 건지지는 못합니다.","질문이 21~30개이고 점검용이라 한 문항이 3~5p입니다. 설정 네 개 중 좋아 보이는 것을 고른 것이라 선택 편향이 있어 확정하지 못합니다."],
 cfg:[["기준(학습 안 함)","-","-",""],["A","1e-5","1e-6",""],["C","1e-5","5e-6","이 탭의 SPLADE"],["D","0","5e-6",""],["E","0","3e-6",""]],
 hd:["구성","문서 P@1","문서 Hit@5","문서 MRR","청크 Hit","청크 MRR","1위 청크 적중"],
 law:[["dense(BGE)만","0.810","1.000","0.897","0.905","0.710","0.571"],["SPLADE 기준","0.810","1.000","0.885","0.762","0.683","0.619"],["SPLADE A","0.857","1.000","0.914","0.810","0.738","0.667"],["SPLADE","0.952","0.952","0.952","0.810","0.762","0.714"],["SPLADE D","0.905","0.952","0.917","0.810","0.754","0.714"],["SPLADE E","0.857","0.952","0.897","0.810","0.738","0.667"],["기준 + dense","0.857","0.952","0.897","0.857","0.750","0.667"],["A + dense","0.810","0.952","0.873","0.857","0.750","0.667"],["C + dense","0.905","1.000","0.944","0.857","0.730","0.619"],["D + dense","0.905","0.952","0.921","0.857","0.750","0.667"],["E + dense","0.810","0.952","0.873","0.857","0.750","0.667"]],
 adm:[["dense(BGE)만","0.800","0.933","0.867","0.933","0.696","0.533"],["SPLADE 기준","0.867","1.000","0.933","0.967","0.744","0.567"],["SPLADE A","0.900","1.000","0.944","0.967","0.751","0.600"],["SPLADE","0.900","1.000","0.950","0.933","0.751","0.600"],["SPLADE D","0.900","1.000","0.950","0.933","0.783","0.667"],["SPLADE E","0.900","1.000","0.950","0.933","0.736","0.600"],["기준 + dense","0.833","0.900","0.867","0.967","0.676","0.467"],["A + dense","0.867","0.900","0.883","0.933","0.686","0.500"],["C + dense","0.900","0.900","0.900","0.933","0.701","0.500"],["D + dense","0.900","0.900","0.900","0.933","0.717","0.533"],["E + dense","0.867","0.900","0.883","0.933","0.694","0.500"]]
};
function c38Table(h,rows){
  return '<table><thead><tr>'+h.map(function(x){return '<th>'+x+'</th>';}).join("")+'</tr></thead><tbody>'+rows.map(function(r){ var c=/ C( |$)/.test(" "+r[0]+" ")||r[0]==="C"; return '<tr'+(c?' class="hl"':'')+'>'+r.map(function(x){return '<td>'+esc(x)+'</td>';}).join("")+'</tr>'; }).join("")+'</tbody></table>';
}
function panelC38(){
  return '<div class="card"><h2 class="ch">설정별 학습 조건</h2>'+c38Table(["설정","정규화 λ","학습률","비고"],C38.cfg)+'</div>'+
  '<div class="card"><h2 class="ch">법령·고시 (21문항, 청크 673)</h2>'+c38Table(C38.hd,C38.law)+'</div>'+
  '<div class="card"><h2 class="ch">행정·업무 (30문항, 청크 183)</h2>'+c38Table(C38.hd,C38.adm)+'</div>'+
  '<p class="cap">SPLADE 단독은 상위 5문서 전부를 반환한 값이고, hybrid는 BGE-m3-ko와 RRF(k=60, 사전 컷 0.97, 최종 컷 0.97)로 합쳤습니다. 질문은 정답을 아는 사람이 본문을 보고 쓴 점검용이고, 평가는 오프라인이라 카테고리 경로의 운영 컷오프와 필터를 거치지 않았습니다. dense와 합치면 법령에서 C 단독(0.952)보다 낮아지고(0.905), 행정·업무의 문서 Hit@5는 모든 hybrid가 0.900으로 SPLADE 단독(1.000)보다 낮습니다.</p>';
}
