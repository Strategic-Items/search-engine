var SRANK={none:0,doc:1,chunk:2};
function stRec(q,k){
  var r=(SG.rows[q.id]||{})[k];
  if(k==="now"){ r=Object.assign({},r||{}); if(q.j) r.j=(q.gate||q.jrej)?1:(q.j.a===true?0:null); }
  return r||null;
}
function stState(q,r){
  if(!r) return null;
  if(q.na) return r.j==null?null:(r.j?"chunk":"none");
  if(!r.hybrid||!r.hybrid.ev) return null;
  return r.hybrid.ev[0]>0?"chunk":(r.hybrid.r>0?"doc":"none");
}
Q.forEach(function(q){
  q.sg=[]; q.sgs={}; var prev=null;
  SG.nodes.forEach(function(n){
    var s=stState(q,stRec(q,n.k)); q.sgs[n.k]=s; if(s==null) return;
    if(prev!=null && SRANK[s]!==SRANK[prev]) q.sg.push({k:n.k,t:SRANK[s]>SRANK[prev]?"gain":"loss"});
    prev=s;
  });
});
function pass(q){
  if (st.stg!=="all" && !q.sg.some(function(e){return e.k+":"+e.t===st.stg;})) return false;
  if (st.hit==="hit" && !q.hit) return false; if (st.hit==="miss" && q.hit) return false;
  if (st.who!=="all" && q.who!==st.who) return false; if (st.cat!=="all" && q.cat!==st.cat) return false;
  if (st.txt && (q.q+" "+q.id).indexOf(st.txt)<0) return false; return true;
}
function vis(){ return Q.filter(pass); }
function renderList(){
  var v=vis(); document.getElementById("cnt").textContent=v.length+" / "+Q.length+"문항";
  document.getElementById("list").innerHTML = v.map(function(q){
    return '<button class="item" type="button" role="option" data-id="'+q.id+'"'+(q.id===st.id?' aria-current="true"':'')+'><span class="dot'+(q.hit?'':' miss')+'"></span><span><span class="meta">'+q.id.replace("docs-v2-","")+' · '+esc(q.cat)+(FEAT[q.id]?' · 사례 '+FEAT[q.id]:'')+'</span><span class="txt">'+esc(q.q)+'</span></span></button>';
  }).join("") || '<p class="note" style="padding:14px">조건에 맞는 문항이 없습니다.</p>';
}
function node(tab,cls,lb,big,sub,active){ return '<button type="button" class="node '+cls+'" data-tab="'+tab+'" aria-pressed="'+(active?'true':'false')+'"><span class="lb">'+lb+'</span><span class="big">'+big+'</span><span class="sub">'+sub+'</span></button>'; }
function cell(pos,html){ return '<div class="col '+pos+'">'+html+'</div>'; }
function inNodes(q){
  return cell("c1 r1",node("kw","kw","질문 → 키워드용","nori 토큰 "+q.tok.length+"개","형태소로 쪼갬",false))+
         cell("c1 r2",node("vec","vec","질문 → dense용","문장 통째로 1번","임베딩 1024차원 · 쪼개지 않음",false));
}
function ansNode(q){
  var j=q.j; if(!j) return "";
  var big, sub, cls;
  if(j.e){ big="빈 결과 → 무응답"; sub="검색 단계 절대 하한에서 종료"; cls=q.na?"ok":"lost"; }
  else if(j.a===false){ big="거절 → 무응답"; sub=q.na?"판정 LLM이 답 없음으로 봄":"답이 있는데 거절(오거절)"; cls=q.na?"ok":"lost"; }
  else if(j.a===true){ big="통과 → 답변 생성"; sub=q.na?"답이 없는데 통과":"근거를 답변 LLM에 전달"; cls=q.na?"lost":"ok"; }
  else { big="판정 실패"; sub="결과 유지"; cls=""; }
  return cell("c6 rs",node("ans",cls,"⑥ 판정 LLM · 답변",big,sub,st.tab==="ans"));
}
function flow(q){
  if(q.na) return flowNa(q);
  var kwG=q.kw.findIndex(function(h){return h.g;}), vcG=q.vec.findIndex(function(h){return h.g;}), gr=q.gi>=0?q.fz[q.gi]:null;
  var c=[inNodes(q)];
  c.push(cell("c2 r1",node("kw","kw","① 키워드(BM25)", kwG>=0?'<span class="pin">정답</span>'+(kwG+1)+'위':'상위 5 밖', "후보 25개 · 1위의 90% 미만은 트림", st.tab==="kw")));
  c.push(cell("c2 r2",node("vec","vec","② dense", vcG>=0?'<span class="pin">정답</span>'+(vcG+1)+'위':'상위 5 밖', "후보 50개 · 1위의 97% 미만은 트림", st.tab==="vec")));
  c.push(cell("c3 rs",node("rrf",gr?"":"lost","③ 문서로 묶어 합산", gr?'<span class="pin">정답</span>'+(q.gi+1)+'위':'상위 6 밖', gr?('BM25 '+(gr.b?gr.b+'위':'트림 제외')+' · dense '+(gr.v?gr.v+'위':'트림 제외')):'정답 문서가 후보에 없음', st.tab==="rrf")));
  c.push(cell("c4 rs",node("rrf",gr?(gr.k?"ok":"lost"):"lost","④ 컷오프", gr?(gr.k?'통과':'잘림'):'해당 없음', gr?(gr.k?'뒤처진 문서만 제외':'정답이 뒤처진 문서로 판정됨'):'—', false)));
  c.push(cell("c5 rs",node("out",q.hit?"ok":"lost","⑤ 반환", q.hit?'정답 청크 실음':(q.dhit?'정답 청크 못 실음':'정답 문서 못 실음'), "문서 "+q.out.length+"건", st.tab==="out")));
  c.push(ansNode(q));
  return c.join("");
}
function flowNa(q){
  var j=q.j||{};
  var c=[inNodes(q)];
  c.push(cell("c2 r1",node("kw","kw","① 키워드(BM25)",'1위 '+(j.bt!=null?j.bt:(q.kw[0]?q.kw[0].s:"없음")),'절대 하한 '+(j.bf||"없음"),st.tab==="kw")));
  c.push(cell("c2 r2",node("vec","vec","② dense",'1위 '+(j.vt!=null?j.vt:(q.vec[0]?q.vec[0].s:"없음")),'절대 하한 '+(j.vf||"없음")+(j.e?' · 미달':''),st.tab==="vec")));
  c.push(cell("c3 rs",node("rrf","","③ 문서로 묶어 합산",q.fx?'문서 '+q.fx.n+'개':'—','정답이 없는 질문',st.tab==="rrf")));
  c.push(cell("c4 rs",node("rrf","","④ 컷오프",'—','뒤처진 문서만 제외',false)));
  c.push(cell("c5 rs",node("out",q.out.length?"":"ok","⑤ 반환",q.out.length?'문서 '+q.out.length+'건':'빈 결과',q.out.length?'정답이 없는데 근거가 반환됨':'반환할 근거 없음',st.tab==="out")));
  c.push(ansNode(q));
  return c.join("");
}
function panelAns(q){
  var j=q.j;
  if(!j) return '<p class="note">이 질문의 판정 자료가 없습니다.</p>';
  var s1=j.e?'<div class="verdict rej"><b>판정 LLM 호출 전에 검색이 끝났습니다</b><p>dense 1위 점수 '+(j.vt!=null?j.vt:'없음')+'가 설정 파일의 절대 하한 '+j.vf+' 미만이라 "이 주제에 관한 문서가 없다"고 보고 빈 결과를 냈습니다. 판정할 근거가 없으므로 판정 LLM은 부르지 않습니다.</p></div>':'';
  var v = j.e ? '<p><b>판정 LLM은 호출되지 않았습니다.</b> 검색 결과가 비어 있어서 판정할 대상이 없습니다.</p>'
        : '<div class="verdict '+(j.a===false?'rej':j.a===true?'pas':'')+'"><b>'+(j.a===false?'답할 수 없음 (거절)':j.a===true?'답할 수 있음 (통과)':'판정 실패')+'</b>'+(j.r?'<p>모델의 이유: “'+esc(j.r)+'”</p>':'')+(j.c!=null?'<p class="note" style="margin:4px 0 0">신뢰도 '+j.c+' — 같은 질문도 실행마다 값이 달라져 코드는 이 값을 쓰지 않고 예/아니오만 씁니다.</p>':'')+'</div>';
  var ctxHtml=q.out.slice(0,5).map(function(d,i){ var cut=i>=3;
    var chunks=d.c.slice(0,6).map(function(c,k){ return '<div class="jc"><span class="jt">'+(k?'같은 문서의 다른 부분':'본문')+'</span>'+esc(tidy(c.b||""))+'</div>'; }).join("");
    return '<div class="jd'+(cut?' cutd':'')+'"><b>['+esc(d.full||d.t)+']</b>'+(cut?' <span class="tag t-bad">판정 LLM은 읽지 않음</span>':'')+chunks+'</div>'; }).join("");
  var jin = j.e ? '' : '<details class="jin"><summary>판정 LLM에 들어간 입력 보기 <span class="note" style="display:inline">(질문 1개 + 반환 문서 앞 3개의 본문·청크)</span></summary><div class="jbox"><div class="jq"><span class="jt">질문</span>'+esc(q.q)+'</div><div class="jt" style="margin:8px 0 4px">발췌문 (앞 '+Math.min(3,q.out.length)+'개 문서만 들어감'+(q.out.length>3?' · 나머지 '+(q.out.length-3)+'개 문서는 흐리게 표시':'')+')</div>'+ctxHtml+'<p class="note" style="margin:8px 0 0">판정 LLM은 문서당 본문 1개와 다른 부분 청크 최대 5개를 읽습니다(본문 1,500자·청크 1,200자까지). 반환 단계까지 이미 잘려 나간 청크(트림·컷오프)는 여기 없고 키워드·dense·합산 탭에서 볼 수 있습니다. 화면에는 저장된 본문(최대 1,200자)을 보여 줍니다.</p></div></details>';
  var s2='<h2>① 판정 LLM (켜져 있을 때만)</h2><p class="note">리랭커가 아닙니다. 순위를 바꾸지 않고, 반환할 근거의 앞 문서 3개를 읽고 "질문이 요구하는 사실이 적혀 있는가"를 예/아니오로 답합니다. 아니오면 결과를 통째로 비웁니다. 기본값은 꺼짐이며, 아래는 켰다고 가정하고 실제로 판정을 돌린 결과입니다.</p>'+jin+v;
  var A=q.a||{}, ctxN=q.out.reduce(function(x,d){return x+d.c.length;},0);
  var userQ='<div class="msg u"><span class="who">질문</span>'+esc(q.q)+'</div>';
  var reply;
  if(q.blocked) reply='<div class="msg a'+(q.na?' okb':' bad')+'"><span class="who">답변 (고정 문구)</span>'+esc(EMPTY_ANS).replace(/\n/g,"<br>")+'</div><p class="note" style="margin-top:6px">근거 자료가 비면 답변 LLM을 부르지 않고 이 문구를 그대로 돌려줍니다.</p>';
  else if(A.ans) reply='<div class="msg a'+(q.na?' bad':'')+'"><span class="who">답변 LLM이 만든 답'+(q.na?' · 문서에 답이 없는 질문인데 나간 답':'')+'</span>'+esc(A.ans).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>')+'</div><p class="note" style="margin-top:6px">근거 문서 '+q.out.length+'건·청크 '+ctxN+'개를 프롬프트에 넣고 온도 0으로 한 번 생성한 예시입니다(프롬프트 '+(A.plen||0).toLocaleString()+'자, '+(A.sec||"?")+'초). 실행마다 문장은 달라질 수 있습니다.</p>';
  else reply='<div class="msg a"><span class="who">답변 LLM</span>답변 예시가 저장되어 있지 않습니다. 근거 문서 '+q.out.length+'건·청크 '+ctxN+'개가 넘어갑니다.</div>';
  var refb=(A.ref&&!q.na)?'<details class="jin" style="margin-top:10px"><summary>평가용 정답 예시 보기</summary><div class="jbox">'+esc(A.ref)+'</div></details>':'';
  var s3='<h2 style="margin-top:20px">② 이용자에게 나가는 답</h2><div class="chat">'+userQ+reply+'</div>'+refb;
  var exp=q.exp?'<h2 style="margin-top:20px">기대 동작 (평가용 기록)</h2><p class="note">'+esc(q.exp)+'</p>'+(q.why?'<p class="note">이유: '+esc(q.why)+'</p>':''):'';
  var verdict = q.na ? (q.blocked?'<p class="okmsg">무응답이 정상인 질문이고, 실제로 무응답으로 처리됩니다.</p>':'<p class="warn">무응답이 정상인 질문인데 근거가 답변 LLM으로 넘어갑니다. 판정 LLM을 켜도 막지 못한 경우입니다.</p>') : (q.blocked?'<p class="warn">답이 있는 질문인데 무응답으로 처리됩니다(오거절).</p>':'');
  return (q.na?goldBar(q)+verdict:'')+s1+s2+s3+exp;
}
function panelKw(q){
  var chips=(q.idf||q.tok.map(function(t){return [t,null,null];})).map(function(x){
    var t=x[0], n=x[1], idf=x[2];
    if(idf==null) return '<span>'+esc(t)+'</span>';
    if(n===0) return '<span class="rare0" title="'+esc(t)+': 색인 어느 청크에도 없는 토큰이라 점수에 기여할 수 없음">'+esc(t)+'</span>';
    var a=Math.min(0.75,0.06+0.69*Math.min(1,idf/5.5));
    return '<span class="idfchip" style="--a:'+a.toFixed(2)+'" title="'+esc(t)+': 이 토큰이 들어 있는 청크 '+n+'개 / 전체 '+q.N+'개 · IDF '+idf+'">'+esc(t)+'</span>'; }).join("");
  var hits=q.kw.map(function(h,i){
    var tm=(h.tm||[]).map(function(x){return '<span class="tm"><b>'+esc(x[0])+'</b> '+x[1]+'</span>';}).join("");
    return '<details class="hit'+(h.g?' gold':'')+'"'+(h.g?' open':'')+'><summary class="hd"><span class="rk">'+(i+1)+'위</span><span class="ti">'+esc(h.t)+'</span>'+(h.g?'<span class="pin big">정답 청크</span>':'')+'<span class="sc">'+h.s+'</span><span class="more">본문 보기</span></summary>'+
     '<div class="sn">'+hl(tidy(h.b||h.h||""))+'</div>'+(tm?'<div class="tms"><span>단어별 BM25 기여</span>'+tm+'</div>':'')+'</details>'; }).join("");
  return goldBar(q)+'<div><h2>질문을 이렇게 쪼개서 찾았습니다 (nori)</h2><div class="chips" style="margin-top:8px">'+chips+'</div><p class="note" style="margin-top:6px">칩의 색이 진할수록 색인에서 드문 토큰이라 맞았을 때 점수를 많이 줍니다(BM25의 IDF). 취소선 칩은 어느 청크에도 없는 토큰입니다. 칩에 마우스를 올리면 그 토큰이 들어 있는 청크 수가 나옵니다. 노란 표시가 실제로 본문과 맞은 단어입니다. 각 줄을 누르면 청크 본문 전체가 열립니다.</p></div><h2>키워드 검색 상위 5 · BM25 점수</h2>'+hits;
}
function judgeText(q){ var j=q.j; if(!j) return "판정 자료 없음"; if(j.e) return "검색 단계에서 이미 빈 결과"; if(j.a===false) return "판정 LLM이 거절"; if(j.a===true) return "판정 LLM 통과"; return "판정 호출 실패"; }
function goldWhy(q){
  var g=q.gd; if(!g) return "";
  var body=esc(g.body);
  (g.mark||[]).forEach(function(m){ var e=esc(m); body=body.split(e).join("<mark>"+e+"</mark>"); });
  var rows=g.steps.map(function(s){ return '<div class="k">'+esc(s[0])+'</div><div class="v '+s[1]+'">'+esc(s[2])+'</div><div>'+esc(s[3])+'</div>'; }).join("");
  return '<div class="gd"><h2>정답 청크는 이렇게 생겼고, 이래서 안 나왔습니다</h2><div class="gch">'+esc(g.ch)+' · '+esc(g.note)+'</div><pre>'+body+'</pre><div class="gs">'+rows+'</div><div class="gw"><b>정리</b> '+esc(g.why)+'</div></div>';
}
function goldBar(q){
  if(q.na) return '<div class="goldbar na"><span class="pin big" style="background:var(--bad-soft);color:var(--bad);border-color:var(--bad)">정답 없음</span><span>이 질문은 문서에 답이 없어서 <b>무응답이 정상</b>입니다</span><span>'+judgeText(q)+'</span><span>'+(q.blocked?'<b>무응답 답변으로 처리됨</b>':'<b class="no2">답변 생성으로 넘어감</b>')+'</span></div>';
  function rk(l){ var i=l.findIndex(function(h){return h.g;}); return i<0?'<b class="no">상위 5 밖</b>':'<b>'+(i+1)+'위</b>'; }
  var gi=q.fz.findIndex(function(r){return r.g;});
  var oi=q.out.findIndex(function(o){return o.g;});
  return '<div class="goldbar"><span class="pin big">정답 청크</span><span>키워드 '+rk(q.kw)+'</span><span>dense '+rk(q.vec)+'</span><span>합산 문서 '+(gi<0?'<b class="no">후보 밖</b>':'<b>'+(gi+1)+'위</b>')+'</span><span>최종 반환 '+(oi<0?'<b class="no">없음</b>':'<b>'+(oi+1)+'위</b>')+'</span></div>'+goldWhy(q);
}
function panelVec(q){
  var idx = st.chunk==null ? Math.max(0,q.vec.findIndex(function(h){return h.g;})) : st.chunk;
  var pick=q.vec.map(function(h,i){ return '<button type="button" data-chunk="'+i+'" aria-pressed="'+(i===idx?'true':'false')+'"><span class="r">'+(i+1)+'위</span><span class="t">'+esc(h.t)+(h.g?' <span class="pin">정답</span>':'')+'</span><span class="s">'+h.s+'</span></button>'; }).join("");
  var o=q.occ, col=o.d.map(function(r){return r[idx];}), mx=Math.max.apply(null,col.concat([0.001]));
  var words=o.w.map(function(w,i){ var d=col[i], a=d>0.005?Math.min(0.9,0.12+0.78*d/mx):0; return '<span style="--a:'+a.toFixed(2)+'" title="'+esc(w)+': 빼면 유사도 '+(d>=0?'−':'+')+Math.abs(d).toFixed(3)+'">'+esc(w)+'</span>'; }).join("");
  var top=col.map(function(d,i){return [o.w[i],d];}).filter(function(x){return x[1]>0.01;}).sort(function(a,b){return b[1]-a[1];}).slice(0,4);
  var body=tidy(q.vec[idx].b||q.vec[idx].h||""), cs=q.vec[idx].cs, bodyHtml=esc(body), cTop="";
  if(cs&&cs.length){
    var cm=Math.max.apply(null,cs.map(function(x){return x[1];}).concat([0.0005]));
    bodyHtml=cs.map(function(x){ var d=x[1], a=d>0.001?Math.min(0.9,0.15+0.75*d/cm):0; return '<span class="cseg" style="--a:'+a.toFixed(2)+'" title="이 구간을 빼면 유사도 '+(d>=0?'−':'+')+Math.abs(d).toFixed(4)+'">'+esc(tidy(x[0]))+'</span>'; }).join(" ");
    var ct=cs.map(function(x){return x;}).sort(function(a,b){return b[1]-a[1];}).slice(0,2).filter(function(x){return x[1]>0.001;});
    cTop='<p style="margin:6px 0 0;font-size:13.5px">'+(ct.length?'영향이 큰 구간: '+ct.map(function(x){return '<b>“'+esc(tidy(x[0]))+'”</b> (−'+x[1].toFixed(4)+')';}).join(", "):'뚜렷하게 영향을 준 구간이 없습니다. 청크 전체 의미로 가까워진 경우입니다.')+'</p>';
  }
  return goldBar(q)+'<p class="note">dense 검색은 청크마다 미리 만들어 둔 임베딩과 질문 임베딩의 코사인 유사도로 순위를 냅니다. 청크를 통째로 임베딩했고 질문도 통째로 한 번 임베딩합니다.</p>'+
   '<div class="two"><div class="pick" role="group" aria-label="dense 상위 5 청크">'+pick+'</div>'+
   '<div style="display:flex;flex-direction:column;gap:12px;min-width:0"><div><h2>이 청크의 본문 — 질문과의 유사도에 기여한 부분 (근사)</h2><div class="body cbody" style="margin-top:6px">'+bodyHtml+'</div><div class="legend"><i></i>진할수록 그 구간을 빼면 질문과의 유사도가 더 떨어짐 (6어절 단위)</div>'+cTop+'</div>'+
   '<div><h2>질문의 어느 단어가 이 청크와 가깝게 만들었나 (근사)</h2><div class="attr" style="margin-top:4px">'+words+'</div>'+
   '<div class="legend"><i></i>진할수록 그 단어를 빼면 유사도가 더 떨어짐 · 이 청크와 질문의 코사인 '+o.base[idx]+'</div>'+
   '<p style="margin:6px 0 0;font-size:13.5px">'+(top.length?'기여가 큰 단어: '+top.map(function(x){return '<b>'+esc(x[0])+'</b> (−'+x[1].toFixed(3)+')';}).join(", "):'뚜렷하게 기여한 단어가 없습니다. 어느 한 단어를 빼도 유사도가 0.01 넘게 떨어지지 않았습니다.')+'</p>'+
   '<p class="warn" style="margin-top:8px">질문 어절이나 청크 구간을 하나씩 빼고 다시 임베딩해 잰 추정값입니다(어절 나누기는 이 설명용 계산에서만 쓴 단위이고, 실제 dense 검색은 질문 전체를 한 번에 임베딩합니다). 실제 검색은 단어별 계산을 하지 않으므로 "dense가 이 단어로 찾았다"는 근거로 쓰지 않습니다. ±0.01 안쪽 차이는 의미가 없습니다.</p></div></div></div>';
}
function panelRrf(q){
  var fx=q.fx, K=fx.rrfk;
  function listCol(name,cls,L,unit){
    var prevSt="keep", body="";
    L.rows.forEach(function(r,i){
      var st2 = (L.floor && r.s<L.floor) ? "floor" : (r.r>L.kept ? "trim" : "keep"), pct=L.top?(r.s/L.top*100).toFixed(1):"0";
      var prev=i>0?L.rows[i-1].r:0, gap=(prev && r.r-prev>1)?'<div class="gap">⋮</div>':'';
      var line="";
      if(st2!==prevSt && st2==="floor") line='<div class="cutline">─ ① 절대 하한 '+L.floor+' 미만: 이 아래 히트는 먼저 버림 ─</div>';
      else if(st2!==prevSt && st2==="trim") line='<div class="cutline">─ ② 1위 점수의 '+Math.round(L.ratio*100)+'% 미만(= '+(L.top*L.ratio).toFixed(unit)+' 미만): 합산에서 제외 ─</div>';
      prevSt=st2;
      body+=gap+line+'<div class="lrow'+(r.g?' g':'')+(st2!=="keep"?' out':'')+'"><span class="n">'+r.r+'</span><span class="t">'+esc(r.t)+' <span class="cid">#'+r.n+'</span>'+(r.g?' <span class="pin">정답 청크</span>':'')+'</span><span class="sc">'+r.s+'</span><span class="pc"><i style="width:'+Math.min(100,pct)+'%"></i></span><span class="pp">'+pct+'%</span></div>';
    });
    var flow2=(L.floor?'하한 통과 '+L.afterfloor+'개 → ':'')+'합산 대상 '+L.kept+'개';
    return '<div class="lcol '+cls+'"><h3>'+name+' <small>후보 '+L.total+'개 → '+flow2+'</small></h3>'+body+'</div>';
  }
  var gateBox=fx.gate?'<div class="verdict rej" style="margin-bottom:12px"><b>이 질문은 여기서 검색이 끝납니다.</b><p>dense 1위 점수 '+fx.vec.top+'가 절대 하한 '+fx.vec.floor+' 미만이라서 "이 주제에 관한 문서가 없다"고 보고 빈 결과를 냅니다. 키워드 목록도 함께 버려지므로 아래 ②의 합산 대상은 0개입니다.</p></div>':'';
  var step1='<h2>① 각 검색기가 자기 목록을 먼저 자릅니다</h2><p class="note">청크 단위 결과입니다. 두 번 자릅니다. 먼저 설정 파일의 절대 하한 미만을 버리고, 남은 것 중 1위 점수 대비 비율(BM25 90%, dense 97%) 미만을 뺍니다. 점수 단위가 서로 달라서 %로만 비교합니다. 위의 키워드·dense 탭은 자르기 전 상위 5개를 보여 줍니다.</p>'+gateBox+'<div class="lists">'+listCol("키워드(BM25)","kw",fx.kw,2)+listCol("dense","vec",fx.vec,3)+'</div>';
  function term(x){ return x?'1/('+K+'+'+x+') = '+(1/(K+x)).toFixed(4):'—'; }
  function frows(list,floor,ref){
    var mx=Math.max.apply(null,list.map(function(r){return r.s;}).concat([0.0001])), drawn=false;
    return list.map(function(r,i){
      var line="";
      if(!drawn && r.under){ drawn=true; line='<div class="cutline wide">─ 컷오프 선: 1위 RRF 점수 × '+Math.round(fx.cut*100)+'% = '+floor+' · 이 아래는 각 목록의 1위 문서만 살아남음 ─</div>'; }
      var res;
      if(!ref && q.gate) res='<span class="tag t-mut">빈 결과(절대 하한)</span>'; else if(ref) res=r.in?'<span class="tag t-ok">①을 통과</span>':'<span class="tag t-bad">①에서 제외</span>';
      else res=r.k?'<span class="tag t-ok">반환</span>':(r.under?(r.lead?'<span class="tag t-mut">선 아래·1위라 유지</span>':'<span class="tag t-bad">컷오프</span>'):'<span class="tag t-mut">문서 수 한도</span>');
      return line+'<div class="frow'+(r.g?' g':'')+((ref&&!r.in)?' dim':'')+'"><span class="n">'+(i+1)+'</span><span class="dc">'+esc(r.t)+(r.g?' <span class="pin">정답 문서</span>':'')+'</span><span class="calc"><span class="'+(r.b?'k':'no')+'">BM25 '+(r.b?r.b+'위 ':'없음 ')+term(r.b)+'</span> + <span class="'+(r.v?'v':'no')+'">dense '+(r.v?r.v+'위 ':'없음 ')+term(r.v)+'</span></span><span class="tot">'+r.s.toFixed(4)+'</span><span class="bar"><i style="width:'+(r.s/mx*100).toFixed(0)+'%"></i></span>'+res+'</div>';
    }).join("");
  }
  var gi=q.fz.findIndex(function(r){return r.g;}), gnote=(!q.na&&!fx.gate&&gi<0&&!fx.rows.some(function(r){return r.g;}))?'<p class="warn">정답 문서는 위 ① 단계에서 두 목록 모두 잘려 합산 대상에 들어오지 못했습니다.</p>':'';
  var step2='<h2 style="margin-top:22px">② ①을 통과한 청크만 문서로 묶어 RRF로 합칩니다 <small style="font-weight:400;color:var(--muted)">합산 대상 '+fx.n+'개 문서</small></h2><p class="note">점수 = 목록마다 <b>1/(60+자리)</b>를 더한 값입니다. 자리는 그 문서의 첫 청크가 ①을 통과한 목록에서 몇 번째 청크인지이고, 문서 순서가 아니라 청크 순서입니다. 한 문서의 청크가 여러 개여도 목록마다 첫 청크 하나만 셉니다. 두 목록 모두 1위이면 2/61 = 0.0328이 최고점이고, 한 목록에서만 1위이면 1/61 = 0.0164로 정확히 절반입니다. 그래서 컷오프 90%만 쓰면 한 검색기만 찾은 문서는 항상 잘리므로, 어느 목록의 1위 청크인 문서는 선 아래여도 남깁니다. 점수가 같으면 dense에서 자리가 앞선 쪽(dense에 없으면 맨 뒤), 그래도 같으면 청크 ID 순입니다. 질문에 연도·반기가 있고 제목이 맞는 후보가 있으면 세 번째 목록(가중치 1.0)이 더해지는데, 아래 표에는 이런 질문이 없습니다.'+(fx.n>0&&fx.n<=2?' 이 질문은 ①을 통과한 청크가 소수의 문서에 몰려서 합칠 문서가 적습니다.':'')+'</p>'+gnote+(fx.rows.length?'<div class="card frows">'+frows(fx.rows,fx.floor,false)+'</div>':'<p class="note">①에서 모두 걸러져 합칠 문서가 없습니다.</p>');
  var step3=q.fx0?'<h2 style="margin-top:22px">③ 참고: ①에서 자르지 않았다면 <small style="font-weight:400;color:var(--muted)">후보 전체(BM25 25개 + dense 50개)를 RRF로 합친 가정 결과 · 문서 '+q.fx0.n+'개 중 상위 '+q.fx0.rows.length+'개</small></h2><p class="note">실제 검색에는 쓰이지 않는 비교용 표입니다. 흐린 줄은 ①에서 잘려 실제 합산에 들어오지 못한 문서이고, 자르지 않았다면 이런 순위와 점수를 받았을 것이라는 뜻입니다.</p><div class="card frows">'+frows(q.fx0.rows,q.fx0.floor,true)+'</div>':'';
  return goldBar(q)+step1+step2+step3;
}
function panelOut(q){
  function r(x,l){ return x==null?'<span class="rn no">'+l+' 밖</span>':'<span class="rn"><i>'+l+'</i> '+x+'위</span>'; }
  var out=q.out.map(function(d,i){
    var rows=d.c.map(function(c,j){
      return '<details class="cdet'+(c.g?' g':'')+'"'+(c.g?' open':'')+'><summary><span class="ord">'+(j+1)+'번째</span><span class="cid">청크 #'+c.n+'</span>'+(c.g?'<span class="pin">정답 청크</span>':'<span></span>')+'<span class="prev">'+esc(tidy(c.b||"").slice(0,70))+'…</span>'+r(c.k,"키워드")+r(c.v,"dense")+'</summary><div class="cbody2">'+esc(tidy(c.b||""))+'</div></details>'; }).join("");
    return '<div class="dbox'+(d.g?' g':'')+'"><div class="dhead"><span class="dn">'+(i+1)+'위</span><span class="dt">'+esc(d.full||d.t)+'</span>'+(d.g?'<span class="pin">정답 문서</span>':'')+'<span class="dm">청크 '+d.c.length+'개 실림</span></div><div class="crows">'+rows+'</div></div>'; }).join("");
  return '<p class="note">답변 LLM에 넘어가는 근거입니다. 문서당 청크를 최대 6개까지 싣습니다. 첫 번째 청크는 dense로 고른 청크이고, 나머지는 청크 단위 RRF 순서입니다. 오른쪽 순위는 그 청크가 키워드(후보 25개)·dense(후보 50개) 목록에서 몇 위였는지이고, "밖"은 후보에 없었다는 뜻입니다. 각 줄을 누르면 청크 본문이 열립니다.</p>'+goldBar(q)+'<div class="dboxes">'+(out||'<p class="note" style="margin:0">반환된 문서가 없습니다. 검색 단계에서 결과가 비었습니다.</p>')+'</div>';
}

function panelStg(q){
  var prevM={}, prevS=null, prevJ=null, cards=[], rib=[], evs=q.sg;
  var goodTxt=q.na?"무응답 처리(정상)":"정답 청크 실림", badTxt=q.na?"답변으로 넘어감":"못 찾음";
  SG.nodes.forEach(function(n){
    var r=stRec(q,n.k), s=q.sgs[n.k], cls=s||"", lines=[], badge="", chg=false;
    var hasAny=!!r && (r.hybrid||r.bm25||r.vector||r.pr||r.j!=null);
    if(!hasAny){ rib.push('<button type="button" class="nd" data-go="tl-'+n.k+'" disabled><span class="rl">'+esc(n.l)+'</span><span class="rs">자료 없음</span></button>'); return; }
    var modes='';
    if(r.bm25||r.vector||r.hybrid){
      function mc(name,cl,cur,prev){
        if(!cur) return '';
        var t=cur.r>0?'<b>'+cur.r+'위</b>':'<b class="no">반환 밖</b>', d='';
        if(prev && prev.r!==cur.r){ var up=cur.r>0&&(prev.r===0||cur.r<prev.r); d='<span class="dl '+(up?'up':'dn')+'">'+(prev.r>0?prev.r+'위':'밖')+' → '+(cur.r>0?cur.r+'위':'밖')+'</span>'; }
        return '<div class="mc '+cl+'"><span class="ml">'+name+'</span>'+t+d+'</div>';
      }
      if(!q.na) modes='<div class="tl-modes">'+mc("키워드만","kw",r.bm25,prevM.bm25)+mc("dense만","vec",r.vector,prevM.vector)+mc("합친 결과","hy",r.hybrid,prevM.hybrid)+'</div>';
      ["bm25","vector","hybrid"].forEach(function(m){ if(r[m]) prevM[m]=r[m]; });
    }
    if(!q.na && r.hybrid && r.hybrid.ev){
      var e=r.hybrid.ev;
      lines.push(e[0]>0?'<b class="g">정답 청크가 실렸습니다</b>'+(e[2]?' (문서 안 '+e[2]+'번째 청크)':''):(r.hybrid.r>0?'<b class="r">정답 문서는 잡았지만 정답 청크는 싣지 못했습니다</b>':'<b class="r">정답 문서를 못 찾았습니다</b>'));
    } else if(!q.na && r.hybrid){
      lines.push(r.hybrid.r>0?'정답 문서가 최종 '+r.hybrid.r+'위로 반환됐습니다':'<b class="r">정답 문서가 반환되지 않았습니다</b>');
    }
    if(r.pr){
      var pr=r.pr, bad=pr.some(function(x){return x>6;}), none=pr.every(function(x){return x===0;});
      lines.push(none?'정답 문서를 가져오지 못해 청크 순서를 잴 수 없습니다':'정답 청크의 문서 안 후보 순서: '+pr.map(function(x){return x?x+'번째':'문서 없음';}).join(", ")+(bad?' — <b class="r">6번째까지만 싣는 설정이라 7번째 이후는 밖으로 밀립니다</b>':' — 6번째까지 싣는 범위 안입니다'));
    }
    if(r.j!=null){
      var jt=q.na?(r.j?'<b class="g">판정 LLM이 거절 → 무응답으로 처리(정상)</b>':'<b class="r">판정 LLM이 통과시켜 답변 생성으로 넘어갑니다</b>'):(r.j?'<b class="r">판정 LLM이 거절 → 답이 있는데 무응답(오거절)</b>':'판정 LLM 통과');
      lines.push('판정 LLM을 켰을 때: '+jt);
      if(prevJ!=null && prevJ!==r.j){ var better=q.na?r.j===1:r.j===0; lines.push('<span class="dl '+(better?'up':'dn')+'">이전 측정과 판정이 달라졌습니다('+(prevJ?'거절':'통과')+' → '+(r.j?'거절':'통과')+'). 판정 LLM은 실행마다 1~2건 흔들리므로 한 번의 차이로 원인을 단정하지 않습니다.</span>'); }
      prevJ=r.j;
    }
    if(s!=null && prevS!=null && SRANK[s]!==SRANK[prevS]){
      var up=SRANK[s]>SRANK[prevS]; chg=true;
      badge='<span class="tl-b '+(up?'up':'dn')+'">'+(up?'이 단계에서 나아짐':'이 단계에서 나빠짐')+'</span>';
    } else if(s!=null && prevS!=null){
      badge='<span class="tl-b same">변화 없음</span>';
    }
    if(s!=null) prevS=s;
    var docs='';
    var top=(r.hybrid&&r.hybrid.top)||[];
    if(top.length&&!q.na) docs='<details class="tl-docs"><summary>이 단계에서 반환된 문서 '+top.length+'건 보기</summary><ol>'+top.map(function(x){return '<li'+(x[1]?' class="g"':'')+'>'+esc(x[0])+(x[1]?' — 정답 문서':'')+'</li>';}).join("")+'</ol></details>';
    rib.push('<button type="button" class="'+(s||"nd")+'" data-go="tl-'+n.k+'"><span class="rl">'+esc(n.l)+'</span><span class="rs">'+(s?(s==="chunk"?goodTxt:s==="doc"?"문서만":badTxt):(r.j!=null?(q.na?(r.j?"거절":"통과"):(r.j?"오거절":"통과")):"진단"))+'</span></button>');
    cards.push('<div class="tl-card '+cls+(chg?' chg':'')+'" id="tl-'+n.k+'"><div class="tl-box"><div class="tl-h"><span class="sl">'+esc(n.l)+'</span><span class="st">'+esc(n.t)+'</span>'+badge+'</div><p class="note" style="margin:0">'+esc(n.d)+'</p>'+modes+lines.map(function(x){return '<div class="tl-line">'+x+'</div>';}).join("")+docs+'</div></div>');
  });
  var lbl={};SG.nodes.forEach(function(n){lbl[n.k]=n.l;});
  var sum;
  if(!evs.length){
    var any=Object.keys(q.sgs).some(function(k){return q.sgs[k]!=null;});
    sum=any?(q.na?'<b>단계가 바뀌어도 판정 결과가 그대로였던 질문입니다.</b>':(Object.keys(q.sgs).every(function(k){return q.sgs[k]!=="chunk"&&q.sgs[k]!=null;})?'<b>어느 단계에서도 정답 청크를 싣지 못한 질문입니다.</b>':'<b>어느 단계에서 방법을 더해도 결과가 변하지 않은 질문입니다.</b> 정답 청크가 처음부터 끝까지 실렸습니다.')):'단계별 기록이 없는 질문입니다.';
  } else sum='<b>결과가 바뀐 단계:</b> '+evs.map(function(e){return esc(lbl[e.k])+(e.t==="gain"?' <b class="g" style="color:var(--vec)">나아짐</b>':' <b style="color:var(--bad)">나빠짐</b>');}).join(" · ");
  var note='<p class="note">13~22단계, 즉 core 문서를 섞기 전까지 각 단계가 끝난 시점에 저장해 둔 실제 검색 결과입니다. 단계마다 색인·설정이 달라서, 순위 숫자는 같은 조건의 비교가 아니라 "그 시점에 이 질문이 어떻게 나왔나"로 읽어 주세요. "키워드만·dense만"은 그 검색기 하나로 검색했을 때 컷오프까지 거친 반환 목록에서의 정답 문서 순위이고, "반환 밖"은 그 목록에 없었다는 뜻입니다.'+(q.na?' 이 질문은 정답이 없어서 판정 LLM 기록만 있고, 판정 LLM은 기본값이 꺼짐이라 켰다고 가정한 결과입니다.':'')+'</p>';
  if(!cards.length) return goldBar(q)+'<p class="note">이 질문은 단계별 검색 기록이 없습니다. 도메인 밖 질문은 현재 설정의 검색 경로 탭에서 확인할 수 있습니다.</p>';
  return goldBar(q)+'<div class="tl-line">'+sum+'</div><div class="tl-rib" role="group" aria-label="단계 요약">'+rib.join("")+'</div>'+note+'<div class="tl">'+cards.join("")+'</div>';
}

var TABS=[["kw","키워드 검색"],["vec","dense 검색"],["rrf","합산과 컷오프"],["out","최종 반환"],["ans","판정·답변"],["stg","단계별 변화"]];
function renderDetail(){
  var q=Q.filter(function(x){return x.id===st.id;})[0], el=document.getElementById("detail");
  if(!q){ el.innerHTML='<p class="note">왼쪽에서 질문을 고르세요.</p>'; return; }
  var panel = st.tab==="vec"?panelVec(q):st.tab==="rrf"?panelRrf(q):st.tab==="out"?panelOut(q):st.tab==="ans"?panelAns(q):st.tab==="stg"?panelStg(q):panelKw(q);
  el.innerHTML='<div class="wrap"><div><div class="kicker"><span>'+q.id+'</span><span>'+esc(q.cat)+'</span><span class="tag '+(q.hit?'t-ok':'t-bad')+'">'+(q.na?(q.hit?'무응답 처리됨':'답을 만들어냄'):(q.hit?'정답 청크 반환':'정답 청크 미반환'))+'</span><span class="tag t-mut">'+WHO[q.who]+'</span>'+(q.na?'':(q.blocked?'<span class="tag t-bad">판정 시 오거절</span>':''))+''+(FEAT[q.id]?'<span class="tag t-kw">대표 사례 '+FEAT[q.id]+'</span>':'')+'</div><p class="q">'+esc(q.q)+'</p></div>'+
   '<section aria-label="단계별 경로"><div class="flow">'+flow(q)+'</div></section>'+
   '<div><div class="tabs" role="tablist">'+TABS.map(function(t){return '<button type="button" role="tab" data-tab="'+t[0]+'" aria-selected="'+(st.tab===t[0]?'true':'false')+'">'+t[1]+'</button>';}).join("")+'</div><div class="panel" role="tabpanel">'+panel+'</div></div></div>';
}
function select(id, keep){
  if(st.view!=="q") setView("q",true);
  st.id=id; st.chunk=null; if(!keep) location.hash=id; renderList(); renderDetail();
  var cur=document.querySelector('.item[aria-current="true"]'); if(cur) cur.scrollIntoView({block:"nearest"});
  document.getElementById("detail").scrollTop=0;
}
function move(d){ var v=vis(); if(!v.length) return; var i=v.findIndex(function(q){return q.id===st.id;}); select(v[Math.max(0,Math.min(v.length-1,i<0?0:i+d))].id); }
