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
  return '<table><thead><tr><th>방식</th><th>청크 Recall</th><th>1위 청크 적중</th><th>청크 MRR</th></tr></thead><tbody>'+
    [1,0,2].map(function(m){ var o=st.m[m]; var nm=["SPLADE","dense","hybrid (SPLADE + dense)"][m];
      return '<tr><td>'+nm+'</td><td>'+(o.rec===best?'<b>'+f3(o.rec)+'</b>':f3(o.rec))+'</td><td>'+o.top+'/'+st.n+'</td><td>'+(o.mrr===bm?'<b>'+f3(o.mrr)+'</b>':f3(o.mrr))+'</td></tr>'; }).join("")+'</tbody></table>';
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
  var row=function(m){ var o=M[m]; return '<tr><td>'+["SPLADE","dense","hybrid (SPLADE + dense)"][m]+'</td><td>'+f3(o.rec)+'</td><td>'+o.top+'/'+st.n+'</td><td>'+f3(o.mrr)+'</td><td>'+f3(o.p1)+'</td><td>'+f3(o.dhit)+'</td><td>'+f3(o.retp)+'</td><td>'+o.ret.toFixed(2)+'</td></tr>'; };
  return '<h2 id="'+info.id+'">'+info.head+'</h2>'+
  '<p class="note"><b>코퍼스.</b> '+info.corpus+'</p>'+
  '<table><thead><tr><th>방식</th><th>청크 Recall</th><th>1위 청크 적중</th><th>청크 MRR</th><th>문서 P@1</th><th>문서 Hit@5</th><th>반환분 문서 Precision</th><th>평균 반환 문서</th></tr></thead><tbody>'+row(1)+row(0)+row(2)+'</tbody></table>'+
  '<p class="cap">문서 지표는 진단용입니다. SPLADE는 원순위 상위 5문서, dense는 1위의 97% 이상인 문서(최대 5), hybrid는 컷오프 뒤 반환 문서 기준입니다. 정답 청크가 1~2개인 질문이 많아 정답 밖 관련 청크도 오답으로 세는 청크 Precision은 하한이라 싣지 않았습니다. 놓친 질문은 SPLADE '+catList(st.miss[0])+', dense '+catList(st.miss[1])+', hybrid '+catList(st.miss[2])+'입니다. 놓친 질문 하나하나의 원인은 읽어서 확인하지 않았습니다.</p>'+
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
  '<p class="note">카테고리 검색은 법령·고시, 행정·업무, 민원FAQ를 각자 인덱스에서 따로 찾는 경로입니다. 질문마다 <b>필수 구절</b>을 적고 그 구절을 모두 담은 청크를 정답 청크로 코드가 찾아 붙였습니다. <b>질문은 정답을 아는 사람(Claude)이 본문을 보고 쓴 점검용이라 성능 판단에는 쓰지 않습니다.</b> 아래 수치는 모두 같은 오프라인 조건입니다: <b>SPLADE는 38단계에서 합성 질의 2,702개로 파인튜닝한 모델</b>, dense는 BGE-m3-ko, hybrid는 SPLADE와 dense를 합친 것이고, 청크 Recall은 <b>상위 5청크</b> 안에서 정답 청크를 찾았는지로 셉니다. LLM 필터·답변 가능성 판정·리랭커 없음, 기준일 2026-10-06. 서비스 코드에는 SPLADE가 붙어 있지 않습니다.</p>'+
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
  var sw=document.getElementById("catsw"); sw.style.gridTemplateColumns="repeat(3,1fr)";
  sw.innerHTML=Object.keys(CINFO).map(function(o){ return '<button type="button" data-catsel="'+o+'" aria-pressed="'+(CATSEL===o)+'">'+CINFO[o].tab+'</button>'; }).join("");
  sw.onclick=function(e){ var b=e.target.closest("button[data-catsel]"); if(b){ CATSEL=b.dataset.catsel; renderCat(); } };
}

/* 카테고리별 검색: 질문별 보기(목록과 상세). */
var CSETS=[["law50","법령·고시 50건 · 50문항","법령·고시"],["admin30","행정·업무 30문항","행정·업무"],["faq30","민원FAQ 30문항","민원FAQ"]];
var CMODES=["SPLADE","dense","hybrid"];
var CQ=[];
CSETS.forEach(function(s){ CATD[s[0]].forEach(function(x){ CQ.push({id:s[0]+"-"+x.i, set:s[0], i:x.i, c:x.c, q:x.q, n:x.n, r:x.r, miss:x.r.some(function(r){return r==null;}), hmiss:!cqRet(CATH[s[0]][x.i]).chunk}); }); });
var CQS={set:"all", hit:"all", txt:"", id:CQ[0].id, tab:"sp", chunk:null};
function cqSet(k){ return CSETS.filter(function(s){return s[0]===k;})[0]; }
function cqVis(){ return CQ.filter(function(x){
  if(CQS.set!=="all"&&x.set!==CQS.set) return false;
  if(CQS.hit==="miss"&&!x.miss) return false;
  if(CQS.hit==="hmiss"&&!x.hmiss) return false;
  if(CQS.txt&&(x.q+" "+x.i+" "+x.c).indexOf(CQS.txt)<0) return false;
  return true; }); }
function cqList(){
  var v=cqVis(); document.getElementById("ccnt").textContent=v.length+" / "+CQ.length+"문항";
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
  return '<div class="goldbar'+(rt.chunk?'':' miss')+'"><span class="pin big">정답 청크</span><span>SPLADE '+(gr[0]!=null&&gr[0]<=5?'<b>'+gr[0]+'위</b>':'<b class="no">상위 5 밖</b>')+'</span><span>dense '+(gr[1]!=null&&gr[1]<=5?'<b>'+gr[1]+'위</b>':'<b class="no">상위 5 밖</b>')+'</span><span>합산 문서 '+(f.gd?'<b>'+f.gd+'위</b>':'<b class="no">후보 밖</b>')+'</span><span>최종 반환 '+(rt.chunk?'<b>정답 청크 실음</b>':(rt.doc?'<b class="no">정답 문서만</b>':'<b class="no">없음</b>'))+'</span></div>'+cqGold(d,CQ.filter(function(o){return o.id===CQS.id;})[0]);
}
function cqLcol(name,cls,L,unit){
  var body="", prev="keep";
  L.rows.forEach(function(r,i){
    var kept=r[3]===1, stt=kept?"keep":"trim", pct=L.top?(r[2]/L.top*100).toFixed(1):"0";
    var line=(stt!==prev&&stt==="trim")?'<div class="cutline">─ 1위 점수의 97% 미만(= '+(L.top*0.97).toFixed(unit)+' 미만): 합산에서 제외 ─</div>':"";
    prev=stt;
    body+=line+'<div class="lrow'+(r[4]?' g':'')+(kept?'':' out')+'"><span class="n">'+r[1]+'</span><span class="t">'+esc(r[0])+(r[4]?' <span class="pin">정답 문서</span>':'')+'</span><span class="sc">'+r[2]+'</span><span class="pc"><i style="width:'+Math.min(100,pct)+'%"></i></span><span class="pp">'+pct+'%</span></div>';
  });
  return '<div class="lcol '+cls+'"><h3>'+name+' <small>문서 후보 '+L.tot+'개 → 합산 대상 '+L.n+'개</small></h3>'+body+'</div>';
}
function cqFx(d,x){
  var f=d.fx, K=60;
  function term(r){ return r?'1/('+K+'+'+r+') = '+(1/(K+r)).toFixed(4):'—'; }
  var drawn=false;
  var frows=f.rows.map(function(r,i){
    var line="";
    if(!drawn&&r[5]){ drawn=true; line='<div class="cutline wide">─ 컷오프 선: 1위 RRF 점수 × 97% = '+f.floor+' · 이 아래는 각 목록의 1위 문서만 살아남음 ─</div>'; }
    var res=r[6]?'<span class="tag t-ok">반환</span>':(r[5]?(r[4]?'<span class="tag t-mut">선 아래·1위라 유지</span>':'<span class="tag t-bad">컷오프</span>'):'<span class="tag t-mut">문서 수 한도</span>');
    return line+'<div class="frow'+(r[7]?' g':'')+'"><span class="n">'+(i+1)+'</span><span class="dc">'+esc(r[0])+(r[7]?' <span class="pin">정답 문서</span>':'')+'</span><span class="calc"><span class="'+(r[1]?'sp':'no')+'">SPLADE '+(r[1]?r[1]+'위 ':'없음 ')+term(r[1])+'</span> + <span class="'+(r[2]?'v':'no')+'">dense '+(r[2]?r[2]+'위 ':'없음 ')+term(r[2])+'</span></span><span class="tot">'+r[3].toFixed(4)+'</span><span class="bar"><i style="width:'+(f.top?(r[3]/f.top*100).toFixed(0):0)+'%"></i></span>'+res+'</div>';
  }).join("");
  var step1='<h2>① 각 검색기가 자기 목록을 먼저 자릅니다</h2><p class="note">문서 단위 결과입니다(문서 점수는 그 문서의 가장 높은 청크 점수). 1위 점수 대비 97% 미만인 문서를 뺍니다. 점수 단위가 서로 달라서 %로만 비교합니다. dense 점수는 코사인을 0~1로 옮긴 값 (1+코사인)/2입니다. 위의 SPLADE·dense 탭은 자르기 전 상위 5청크를 보여 줍니다.</p><div class="lists">'+cqLcol("SPLADE","spl",f.sp,2)+cqLcol("dense","vec",f.dn,3)+'</div>';
  var step2='<h2 style="margin-top:22px">② ①을 통과한 문서를 RRF로 합칩니다 <small style="font-weight:400;color:var(--muted)">합산 대상 '+f.nf+'개 문서</small></h2><p class="note">점수 = 목록마다 <b>1/(60+자리)</b>를 더한 값입니다. 자리는 ①을 통과한 목록 안에서 그 문서의 순서입니다. 두 목록 모두 1위이면 2/61 = 0.0328이 최고점이고, 한 목록에서만 1위이면 절반입니다. 그래서 컷오프(1위 점수의 97%)만 쓰면 한 검색기만 찾은 문서는 항상 잘리므로, 어느 목록의 1위인 문서는 선 아래여도 남깁니다. 점수가 같으면 dense에서 자리가 앞선 쪽, 그래도 같으면 문서 ID 순입니다.</p>'+(f.nf?'<div class="card frows">'+frows+'</div>':'<p class="note">①에서 모두 걸러져 합칠 문서가 없습니다.</p>')+(f.gd||x.n===0?'':'<p class="warn">정답 문서는 ①에서 두 목록 모두 잘려 합산 대상에 들어오지 못했습니다.</p>');
  var step3='<h2 style="margin-top:22px">③ 참고: 청크 단위로 합치면 <small style="font-weight:400;color:var(--muted)">상위 5청크 · 결과 요약의 청크 Recall은 이 목록으로 셉니다</small></h2><p class="note">같은 SPLADE 순위와 dense 순위를 문서가 아니라 청크 단위로 RRF(k=60)해서 상위 5청크를 잘랐습니다. 컷오프는 없습니다. 아래 줄의 "SPLADE n위 · dense n위"는 그 청크가 각 목록에서 차지한 순위입니다(SPLADE는 상위 100, dense는 상위 50까지 씁니다).</p>'+cqHits(d.hy,"hy");
  return cqBar2(d)+step1+step2+step3;
}
function cqOutP(d,x){
  function r(n,l,lim){ return n?'<span class="rn"><i>'+l+'</i> '+n+'위</span>':'<span class="rn no">'+l+' 상위 '+lim+' 밖</span>'; }
  var out=d.fx.ret.map(function(doc,i){
    var rows=doc.ch.map(function(c,j){ var b=tidy(CATB[c[0]][1]);
      return '<details class="cdet'+(c[3]?' g':'')+'"'+(c[3]?' open':'')+'><summary><span class="ord">'+(j+1)+'번째</span><span class="cid">청크 #'+c[0].split("#")[1]+'</span>'+(c[3]?'<span class="pin">정답 청크</span>':'<span></span>')+'<span class="prev">'+esc(b.slice(0,70))+'…</span>'+r(c[1],"SPLADE",100)+r(c[2],"dense",50)+'</summary><div class="cbody2">'+esc(b)+'</div></details>'; }).join("");
    return '<div class="dbox'+(doc.g?' g':'')+'"><div class="dhead"><span class="dn">'+(i+1)+'위</span><span class="dt">'+esc(doc.t)+'</span>'+(doc.g?'<span class="pin">정답 문서</span>':'')+'<span class="dm">청크 '+doc.ch.length+'개 실림</span></div><div class="crows">'+rows+'</div></div>'; }).join("");
  return '<p class="note">컷오프를 통과한 문서와, 서비스처럼 문서마다 싣는 청크입니다. 문서당 청크는 최대 6개이고 청크 단위 RRF 순서입니다(위 합산 탭 ③의 순서). 오른쪽 순위는 그 청크가 SPLADE(상위 100)·dense(상위 50) 목록에서 몇 위였는지이고, "밖"은 그 목록에 없었다는 뜻입니다. <b>이 창은 결과 요약의 청크 Recall(상위 5청크)과 다릅니다.</b> 각 줄을 누르면 청크 본문이 열립니다.</p>'+cqBar2(d)+'<div class="dboxes">'+(out||'<p class="note" style="margin:0">반환된 문서가 없습니다.</p>')+'</div>';
}
function cqAns(d,x){
  var n=d.fx.ret.length, m=d.fx.ret.reduce(function(a,doc){return a+doc.ch.length;},0);
  return cqBar2(d)+'<div class="verdict"><b>이 질문의 판정·답변은 측정하지 않았습니다</b><p>이 탭의 수치는 검색 단계(SPLADE, dense, 합산, 컷오프)만 오프라인으로 잰 것입니다. 판정 LLM과 답변 LLM은 돌리지 않았고, SPLADE는 서비스 검색에 붙어 있지 않습니다. 그래서 판정 결과와 답변 예시는 없습니다.</p></div>'+
  '<p class="note" style="margin-top:12px">서비스 구조대로라면 최종 반환의 <b>문서 '+n+'건·청크 '+m+'개</b>가 답변 LLM에 근거로 넘어갑니다. 판정 LLM은 기본값이 꺼짐이고, 켜면 앞 문서 3개를 읽고 질문이 요구하는 사실이 적혀 있는지 예/아니오로 답해 아니오이면 결과를 비웁니다. 카테고리 검색 경로는 판정을 끈 상태로 둡니다.</p>';
}
function cqStg(d,x){
  var N=["SPLADE","dense","hybrid(상위 5청크)"];
  var rows=x.r.map(function(r,k){ return '<tr><td>'+N[k]+'</td><td>'+(r==null?'상위 5 밖':r+'위')+'</td></tr>'; }).join("");
  var rt=cqRet(d);
  return '<p class="note">카테고리 질문은 37단계에서 만들었고, 38단계에서 SPLADE를 학습했습니다. 이 화면의 순위는 BM25를 뺀 오프라인 측정 한 번의 결과라서, 질문 하나가 단계마다 어떻게 바뀌었는지는 기록하지 않았습니다.</p>'+
  '<table><thead><tr><th>방식</th><th>첫 정답 청크 순위</th></tr></thead><tbody>'+rows+'<tr><td>컷오프 뒤 반환</td><td>'+(rt.chunk?'정답 청크 실음':(rt.doc?'정답 문서만 실음':'정답 문서 못 실음'))+'</td></tr></tbody></table>'+
  '<p class="note">묶음 전체의 지표는 결과 요약에서 볼 수 있습니다.</p>';
}
function cqNode(tab,cls,lb,big,sub,active){ return '<button type="button" class="node '+cls+'" data-ctab="'+tab+'" aria-pressed="'+(active?'true':'false')+'"><span class="lb">'+lb+'</span><span class="big">'+big+'</span><span class="sub">'+sub+'</span></button>'; }
function cqFlow(d,x){
  var gr=d.gr, f=d.fx, rt=cqRet(d), h=function(r){ return r!=null&&r<=5?'<span class="pin">정답</span>'+r+'위':'상위 5 밖'; };
  var gdoc=f.gd?'<span class="pin">정답</span>'+f.gd+'위':'후보 밖', kept=f.rows.some(function(r){return r[7]&&r[6];});
  return cell("c1 r1",cqNode("sp","spl","질문 → SPLADE용","토큰 "+d.nq+"개","어휘 가중치로 바꿈 · 확장 포함",false))+
    cell("c1 r2",cqNode("dn","vec","질문 → dense용","문장 통째로 1번","임베딩 1024차원 · 쪼개지 않음",false))+
    cell("c2 r1",cqNode("sp","spl","① SPLADE",h(gr[0]),"문서 후보 "+f.sp.tot+"개 · 1위의 97% 미만은 트림",CQS.tab==="sp"))+
    cell("c2 r2",cqNode("dn","vec","② dense",h(gr[1]),"문서 후보 "+f.dn.tot+"개 · 1위의 97% 미만은 트림",CQS.tab==="dn"))+
    cell("c3 rs",cqNode("fx",f.gd?"":"lost","③ 문서로 묶어 합산",gdoc,"합산 대상 문서 "+f.nf+"개",CQS.tab==="fx"))+
    cell("c4 rs",cqNode("fx",f.gd?(kept?"ok":"lost"):"lost","④ 컷오프",f.gd?(kept?'통과':'잘림'):'해당 없음',f.gd?'뒤처진 문서만 제외':'—',false))+
    cell("c5 rs",cqNode("out",rt.chunk?"ok":"lost","⑤ 반환",rt.chunk?'정답 청크 실음':(rt.doc?'정답 청크 못 실음':'정답 문서 못 실음'),"문서 "+f.ret.length+"건",CQS.tab==="out"))+
    cell("c6 rs",cqNode("ans","","⑥ 판정·답변",'측정 안 함',"오프라인 측정에 없음",CQS.tab==="ans"));
}
function cqDetail(){
  var x=CQ.filter(function(o){return o.id===CQS.id;})[0]||CQ[0], s=cqSet(x.set), d=CATH[x.set][x.i], el=document.getElementById("detail");
  var rt=cqRet(d);
  el.innerHTML='<div class="wrap"><div><div class="kicker"><span>'+esc(s[2])+' · '+x.i+'</span><span>'+esc(x.c)+'</span><span class="tag '+(rt.chunk?'t-ok':'t-bad')+'">'+(rt.chunk?'정답 청크 반환':'정답 청크 미반환')+'</span><span class="tag t-mut">상위 5청크: '+esc(cqWho(x))+'</span><span class="tag t-mut">정답 청크 '+x.n+'개</span></div><p class="q">'+esc(x.q)+'</p></div>'+
  '<section aria-label="단계별 경로"><div class="flow">'+cqFlow(d,x)+'</div></section>'+
  '<div><div class="tabs" role="tablist">'+CTABS.map(function(t){return '<button type="button" role="tab" data-ctab="'+t[0]+'" aria-selected="'+(CQS.tab===t[0]?'true':'false')+'">'+t[1]+'</button>';}).join("")+'</div><div class="panel" role="tabpanel">'+cqPanel(d,x)+'</div></div>'+
  '<p class="note"><button type="button" class="sidebtn" data-cqgo="'+CINFO[x.set].id+'">결과 요약에서 보기</button></p>'+
  '<p class="cap">질문은 정답을 아는 사람이 본문을 보고 쓴 점검용이라 성능 판단에는 쓰지 않습니다. 오프라인 측정이라 LLM 필터·판정을 거치지 않았습니다. "정답 청크 반환"은 컷오프 뒤 반환 문서의 청크(문서당 최대 6개)에 정답 청크가 있는지이고, 위 청크 Recall은 상위 5청크 기준입니다.</p></div>';
  el.scrollTop=0;
}
function cqSelect(id,nohash){ CQS.id=id; CQS.chunk=null; cqList(); cqDetail(); if(!nohash) location.hash="cat-q-"+id; var c=document.querySelector('#list [aria-current="true"]'); if(c&&c.scrollIntoView) c.scrollIntoView({block:"nearest"}); }
function cqMove(d){ var v=cqVis(); if(!v.length) return; var i=v.findIndex(function(x){return x.id===CQS.id;}); cqSelect(v[Math.max(0,Math.min(v.length-1,i<0?0:i+d))].id); }
function cqInit(){
  var t=document.getElementById("ctools");
  t.innerHTML='<div class="seg" id="cseg" role="group" aria-label="결과">'+[["all","전체",CQ.length],["miss","일부 놓침",CQ.filter(function(x){return x.miss;}).length],["hmiss","정답 청크 미반환",CQ.filter(function(x){return x.hmiss;}).length]].map(function(o){ return '<button type="button" data-chit="'+o[0]+'" aria-pressed="'+(o[0]==="all")+'">'+o[1]+'<span class="n">'+o[2]+'</span></button>'; }).join("")+'</div>'+
  '<select id="cset" aria-label="묶음"><option value="all">모든 묶음</option>'+CSETS.map(function(s){return '<option value="'+s[0]+'">'+esc(s[1])+'</option>';}).join("")+'</select>'+
  '<input id="ctxt" type="search" placeholder="질문이나 번호로 찾기" aria-label="질문 검색"><div class="cnt" id="ccnt"></div>';
  t.addEventListener("click",function(e){ var b=e.target.closest("button[data-chit]"); if(!b) return; CQS.hit=b.dataset.chit; t.querySelectorAll("#cseg button").forEach(function(o){o.setAttribute("aria-pressed",o===b?"true":"false");}); cqList(); });
  document.getElementById("cset").onchange=function(e){ CQS.set=e.target.value; cqList(); };
  document.getElementById("ctxt").oninput=function(e){ CQS.txt=e.target.value.trim(); cqList(); };
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
