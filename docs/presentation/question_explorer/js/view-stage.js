(function(){
  var NUM={s13:13,s16:14,s18:18,s19:19,s20:20,s21:21,s22:22};
  STG.forEach(function(x){ x.num=NUM[x.k]; });
  DSTG.forEach(function(x){ SG.nodes.push({k:x.k,l:x.l,t:x.t}); STG.push({k:x.k,num:x.num,metrics:"doc",doc:x,head:x.head,what:x.what,why:x.why}); });
  STG.sort(function(a,b){ return a.num-b.num; });
})();
function stgKey(n){ return STGN[n]||(DSTG.some(function(x){return String(x.num)===String(n);})?"d"+n:null); }

var DFIG={
 1:[{t:"질문 유형 v1(키워드) 50개에서 첫 문서 적중",u:"%",max:100,rows:[["BM25",[90.0]],["dense",[38.0]],["하이브리드",[68.0]]]}],
 2:[{t:"자연어 40개로 바꾸자 첫 문서 적중이 이렇게 갈렸습니다",u:"%",max:100,rows:[["BM25",[72.5]],["dense",[12.5]],["하이브리드",[45.0]]]}],
 3:[{t:"파서를 새로 돌려도 지표는 그대로입니다 (하이브리드 1위의 차이는 1문항)",u:"%",max:100,s:["2단계","3단계"],rows:[["BM25 첫 문서 적중",[72.5,72.5]],["dense 첫 문서 적중",[12.5,12.5]],["하이브리드 첫 문서 적중",[45.0,42.5]],["하이브리드 Recall@5",[67.9,67.9]]]}],
 4:[{t:"문서당 반환 청크 수에 따른 근거 Recall@5 (문서 Recall은 87.5%로 고정)",u:"%",max:100,hl:3,rows:[["1개 (종전)",[32.5]],["2개",[42.5]],["3개",[55.0]],["4개 (채택)",[72.5]],["5개",[83.8]]]}],
 5:[{t:"재작성으로 오른 정도",u:"%",max:100,s:["4단계","5단계"],rows:[["BM25 첫 문서 적중",[72.5,77.5]],["하이브리드 문서 Recall@5",[67.9,77.9]]]},{t:"대신 검색 시간(p50)이 38배가 됐습니다",u:"ms",max:650,s:["4단계","5단계"],rows:[["BM25 p50",[15.8,605.5]]]}],
 6:[{t:"dense 문서 Recall@5",u:"%",max:100,hl:2,rows:[["nomic (종전)",[23.8]],["nomic + 접두사 교정",[30.0]],["bge-m3",[100.0]]]}],
 7:[{t:"품질은 그대로, 검색 시간(p50)만 늘었습니다",u:"ms",max:700,s:["재작성 없음","재작성"],rows:[["BM25",[18.8,529.3]],["dense",[73.3,98.2]],["하이브리드",[95.3,687.4]]]}],
 8:[{t:"문서당 청크 수에 따른 dense 근거 Recall@5",u:"%",max:100,hl:1,rows:[["4개",[92.5]],["6개 (채택)",[95.4]],["8개",[96.7]],["16개",[99.2]]]}],
 9:[{t:"식별자 질문 MRR@5: 공고번호는 BM25가 앞섭니다",u:"",max:1,s:["BM25","dense","하이브리드"],rows:[["공고번호 (6)",[0.917,0.556,0.778]],["조문번호 (4)",[0.417,0.300,0.362]],["혼합 (5)",[1.000,0.900,1.000]],["의역 (34)",[0.860,0.957,0.924]]]}],
 10:[{t:"반환분 정밀도를 맞춰 비교하면 sparse와 dense는 동률입니다",u:"%",max:100,rows:[["dense (0.99)",[89.1]],["sparse (0.95)",[89.4]],["hybrid (0.99)",[89.3]],["BM25 (0.97)",[80.3]]]}],
 11:[{t:"MRR@5: 접두사를 줘도 bge-m3를 넘지 못했습니다",u:"",max:1,hl:0,rows:[["bge-m3 (현행)",[0.9074]],["Qwen3, 접두사 없음",[0.8778]],["Qwen3, 접두사 적용",[0.9037]]]}],
 12:[{t:"BM25 MRR@5: 수정 후 구어체가 정식 질문과 같아졌습니다",u:"",max:1,s:["수정 전","수정 후"],rows:[["정식 질문",[0.8265,0.8438]],["구어체 질문",[0.7898,0.8438]]]}],
 17:[{t:"어휘 검색기를 sparse로 바꾸면",u:"",max:100,s:["BM25","sparse"],rows:[["어휘 단독 1위 적중 (%)",[82.2,90.4]],["하이브리드 MRR (×100)",[91.2,92.6]]]}],
 23:[{t:"질문당 전달된 정답 아닌 청크(무관 청크) 수",u:"개",max:130,s:["이전","이후"],rows:[["135문항 합계",[124,71]]]}],
 24:[{t:"SPLADE+dense가 현재 BM25+dense보다 앞선 지표",u:"%",max:100,s:["BM25+dense","SPLADE+dense"],rows:[["문서 P@1",[94.8,97.8]],["청크 근거 Recall",[91.1,94.1]],["직접 답 Precision",[31.4,38.1]]]}],
 25:[{t:"맞힌 문항 수 (135문항)",u:"",max:135,s:["인덱스마다 따로 계산","전역 통계"],rows:[["BM25",[63,92]],["하이브리드",[109,114]]]}],
 26:[{t:"문서 1위 적중: 처음 보는 데이터일수록 떨어졌습니다",u:"",max:1,rows:[["docs (튜닝 세트)",[0.948]],["같은 규모의 새 데이터",[0.841]],["전체 규모 (84k청크)",[0.754]]]}],
 28:[{t:"반환 문서 Precision@5 (docs)",u:"",max:1,s:["제목 3배","제목 1배+전역 통계"],rows:[["docs 135문항",[0.596,0.755]]]}],
 29:[{t:"검색 전에 고정한 새 질문 36개",u:"문항",max:36,rows:[["1위 적중",[34]]]}],
 30:[{t:"연도·반기 구별 진단 (5위 안에 든 문항)",u:"문항",s:["이전","이후"],rows:[["날짜 진단 (14문항)",[10,14],14],["CP 확인 (8문항)",[4,8],8]]}],
 31:[{t:"청크를 자를수록 Precision은 오르지만 Recall도 같이 떨어집니다",u:"%",max:100,s:["Precision","Recall"],rows:[["기준 (끔)",[25.1,96.3]],["LLM 필터",[37.8,96.3]],["점수 컷오프 0.98",[60.0,85.2]],["점수 컷오프 최고",[68.9,68.9]]]}],
 32:[{t:"기간 가산점 하나만 반영한 효과",u:"",max:1,s:["이전","이후"],rows:[["문서 1위 적중",[0.837,0.844]],["반환 문서 Precision",[0.757,0.773]]]}],
 33:[{t:"문서 안 청크 순서는 올랐지만, 청크 우선 파이프라인은 정밀도가 떨어졌습니다",u:"",max:1,s:["이전","이후"],rows:[["근거 회수 (문서 안 순서)",[0.844,0.863]],["문서 정밀도 (청크 우선)",[0.667,0.467]]]}],
 34:[{t:"장치를 걷어낸 뒤 식별자 15문항 Hit (127 한 문항 차이)",u:"",max:1,s:["이전","이후"],rows:[["식별자 15문항 Hit",[0.933,0.867]]]}],
 35:[{t:"SPLADE 단독 문서 P@1 (135문항 중): 학습한 모델이 기준을 넘지 못했습니다",u:"",max:135,hl:0,rows:[["기준 (학습 안 함)",[130]],["a2",[127]],["b2 (최고)",[129]],["c2",[128]]]}],
 36:[{t:"SPLADE+dense가 처음 보는 문서에서 더 크게 앞섰습니다",u:"%",max:100,s:["현재 hybrid","SPLADE+dense"],rows:[["P@1 (docs)",[96.3,98.5]],["P@1 (holdout)",[85.5,89.9]],["Hit@5 (holdout)",[92.8,97.1]],["반환분 정밀도 (holdout)",[65.7,80.4]]]}],
 37:[{t:"카테고리 인덱스의 근거 Recall·Precision (청크 컷오프 0.9, 본문을 보고 쓴 점검용 질문)",u:"",max:1,s:["dense","dense+BM25","BM25","SPLADE 학습","SPLADE 학습+dense"],rows:[["법령·고시 Recall (21문항)",[1.0,0.905,0.571,0.762,0.952]],["행정·업무 Recall (30문항)",[1.0,0.967,0.6,0.767,0.967]],["법령·고시 Precision",[0.149,0.214,0.395,0.487,0.219]],["행정·업무 Precision",[0.224,0.204,0.401,0.583,0.176]]]}],
 38:[{t:"학습 문서군에서는 내려가고 처음 보는 문서에서는 올랐습니다 (문항 수)",u:"",s:["기준","설정 C"],rows:[["docs_v2 (135)",[130,125],135],["holdout-small (69)",[61,63],69],["검증 (36)",[30,33],36]]}],
 39:[{t:"후보 수를 25개 이상으로 두면 결과가 같습니다",u:"%",max:100,s:["문서 P@1","근거 Recall"],rows:[["BM25 5 · dense 10",[96.3,95.9]],["BM25 25 · dense 50 (이전)",[95.6,95.6]],["BM25 25 · dense 25 (현행)",[95.6,95.6]],["BM25 100 · dense 200",[95.6,95.6]]]}]
};

var DFLOW={
 4:{b:["질문",["BM25","dense"],"문서 순위(RRF)","문서당 청크 1개 반환"],a:["질문",["BM25","dense"],"문서 순위(RRF)","*후보 풀에서 문서당 청크 최대 4개"],n:"문서 순위는 그대로이고 반환 단위만 넓어졌습니다. 추가 질의는 없습니다."},
 5:{b:["질문",["BM25","dense"],"RRF","결과"],a:["질문",["원본으로 검색","*LLM 재작성으로 검색 (가중치 0.5)"],"*가중 RRF","결과"],n:"기본값은 꺼짐입니다. 재작성은 문서를 추가할 수는 있어도 원본의 1위를 밀어내지 못합니다."},
 6:{b:["질문","nomic-embed-text (768차원)","kNN 검색"],a:["질문","*bge-m3 (1024차원)","kNN 검색"],n:"차원이 달라 모든 데이터셋을 다시 색인해야 했습니다."},
 8:{b:["문서 순위","문서당 청크 4개"],a:["문서 순위","*문서당 청크 6개"],n:"평가셋도 40문항에서 120문항으로 바뀌었습니다."},
 10:{b:["질문",["BM25","dense"],"RRF"],a:["질문",["~학습형 sparse (실험)","dense"],"RRF"],n:"정밀도를 맞추면 dense와 동률이라 채택하지 않았고 코드를 제거했습니다."},
 11:{b:["질문","bge-m3","kNN 검색"],a:["질문","~Instruct 접두사 + Qwen3-Embedding (실험)","kNN 검색"],n:"질의에만 접두사가 붙는 비대칭 모델입니다. 채택하지 않았습니다."},
 12:{b:["질문","nori 분석 (알리 + 어 + 주 + 어)","토큰 [알리, 주]","BM25"],a:["질문","nori 분석","*보조용언(VX) 제거","토큰 [알리]","BM25"],n:"\"주\" 한 토큰이 각주 \"주 :\"에 걸려 엉뚱한 문서가 1위가 되던 경로를 막았습니다."},
 17:{b:["질문",["BM25","dense"],"RRF"],a:["질문",["~sparse (실험)","dense"],"RRF"],n:"융합하면 sparse의 강점이 평균으로 묻혀 채택하지 않았습니다."},
 23:{b:["질문","검색","문서 단위 채점"],a:["질문","*공고번호 필터","검색","*내려받기 사본 병합","*청크 단위 채점"],n:"검색 결과가 아니라 재는 자가 바뀌었고, 무관 청크를 줄이는 필터가 따라 붙었습니다."},
 24:{b:["질문",["BM25","dense"],"RRF"],a:["질문",["~SPLADE (비교)","dense"],"RRF"],n:"비교 실험이라 운영 경로는 바뀌지 않았습니다."},
 25:{b:["질문","별칭 2개(docs·core)","*인덱스마다 따로 IDF 계산","한 순위표"],a:["질문","별칭 2개(docs·core)","*전역 통계로 IDF 계산 (DFS)","한 순위표"],n:"원인은 코퍼스가 아니라 합치는 방식이었습니다."},
 27:{b:["질문",["BM25","dense"],"RRF(항상 하이브리드)"],a:["질문","~라우터가 방식 선택",["~BM25만","~dense만","~하이브리드"]],n:"어떤 라우터도 하이브리드를 넘지 못해 채택하지 않았습니다."},
 28:{b:["질문","BM25 (제목 ×3)","인덱스마다 통계"],a:["질문","BM25 (*제목 ×1)","*전역 통계 (dfs_query_then_fetch)"],n:"제목 가중치를 낮추고 인덱스 간 통계를 맞췄습니다."},
 30:{b:["질문",["BM25","dense"],"RRF (목록 2개)","컷오프"],a:["질문",["BM25","dense","*연도·반기·주제어가 제목과 맞는 후보"],"*RRF (목록 3개)","*일치 후보는 컷오프에서 보존"],n:"질문에 연도·반기가 있을 때만 세 번째 목록이 생깁니다."},
 31:{b:["문서 컷오프","문서 안 청크 선택","프롬프트"],a:["문서 컷오프","문서 안 청크 선택","*LLM 관련도 필터 (0점 제거, 기본 꺼짐)","프롬프트"],n:"지연 p50이 15초라 기본 꺼짐입니다."},
 32:{b:["연도를 대는 질문",["발행일·시행일이 그 해에 듦 → +6","추정 날짜(period_hint)가 그 해에 듦 → +4","추정 날짜가 다른 해임 → 0","날짜 필드가 하나도 없음 → 0"]],a:["연도를 대는 질문",["발행일·시행일이 그 해에 듦 → +6","추정 날짜(period_hint)가 그 해에 듦 → +4","추정 날짜가 다른 해임 → 0","*날짜 필드가 하나도 없음 → 질문의 해와 상관없이 +4"]],n:"날짜를 아예 모르는 문서는 그 해가 아니라고 말할 근거가 없어서 추정 날짜 일치(+4)와 같은 점수를 받습니다. 확인된 날짜 일치(+6)보다는 뒤에 섭니다. 문서에 날짜가 채워지면 이 규칙에서 빠져 +6/+4/0 중 하나로 옮겨 갑니다. docs 인덱스는 대부분 날짜가 비어 있어서, 이전에는 그 해 날짜가 붙은 core의 방해 문서만 가산점을 받았습니다."},
 33:{b:["문서 RRF","컷오프","문서 안 청크 선택"],a:["~청크 RRF","~청크 컷오프","~부모 문서로 묶기"],bl:"현행(문서 우선)",al:"청크 우선 (기본 꺼짐)",n:"문서 안 청크 순서(첫 청크는 dense, 나머지는 청크 RRF)만 반영했습니다."},
 34:{b:["질문","BM25 쿼리: 제목 · 본문 · .standard 부속 필드","문서 종류 부스트","현행판 우대 +4"],a:["질문","BM25 쿼리: 제목 · 본문","~문서 종류 부스트 삭제","현행판 우대 +4"],n:"종류값이 색인에 0개라 부스트는 작동하지 않던 코드였습니다."},
 35:{b:["PIXIE-Splade 기준 모델","평가"],a:["PIXIE-Splade 기준 모델","~도메인 합성 질의 108개 + 어려운 오답으로 파인튜닝","평가"],n:"채택하지 않았습니다."},
 36:{b:["질문",["BM25","dense"],"RRF"],a:["질문",["~SPLADE","dense"],"RRF"],bl:"현행 하이브리드",al:"비교 대상",n:"운영 경로에는 붙이지 않았습니다."},
 37:{b:["질문","통합 검색(core + docs)","답변"],a:["질문","*카테고리 선택","*카테고리 인덱스 (search-law · search-admin)","BM25 하한·판정 끔","답변"],n:"통합 인덱스는 건드리지 않고 새 경로를 하나 더 붙였습니다."},
 38:{b:["PIXIE-Splade 기준 모델","평가"],a:["PIXIE-Splade 기준 모델","~어려운 합성 질의 2,702개로 재파인튜닝","평가"],n:"채택 기준을 통과하지 못했습니다."},
 39:{b:["BM25 후보 25개","dense 후보 50개","RRF"],a:["BM25 후보 25개","*dense 후보 25개","RRF"],n:"성능이 같아 후보 수만 줄였습니다."}
};
function flowDoc(n){
  var f=DFLOW[n]; if(!f) return "";
  function box(x){ if(Array.isArray(x)) return '<div class="xs">'+x.map(box).join("")+'</div>';
    var c=x[0]==="*"?"ch":(x[0]==="~"?"off":""), t=(c?x.slice(1):x);
    return '<div class="xb '+c+'">'+esc(t).replace(/\*/g,"")+'</div>'; }
  function row(l,a){ return '<div class="xrow"><span class="xl">'+esc(l)+'</span>'+a.map(function(x,i){ return (i?'<span class="xa">→</span>':'')+box(x); }).join("")+'</div>'; }
  return '<div class="fig"><div class="fh"><b>처리 흐름이 어떻게 바뀌었나</b><span class="lg"><i class="xch"></i>바뀐 곳</span><span class="lg"><i class="xoff"></i>시험만 했거나 꺼짐</span></div>'+row(f.bl||"이전",f.b)+row(f.al||"이후",f.a)+(f.n?'<p class="note" style="margin:6px 0 0">'+esc(f.n)+'</p>':'')+'</div>';
}
function figDoc(f){
  var sc=f.s||[], lg=sc.length>1?'<div class="fh" style="margin:2px 0 6px">'+sc.map(function(x,i){return '<span class="lg"><i class="bs'+i+'"></i>'+esc(x)+'</span>';}).join("")+'</div>':'';
  var body=f.rows.map(function(r,ri){
    var mx=r[2]||f.max;
    return '<div class="brow"><div class="bl">'+esc(r[0])+'</div><div class="bcol">'+r[1].map(function(v,i){
      var w=Math.max(1,Math.min(100,v/mx*100)), c=(sc.length>1?'bs'+i:(f.hl===ri?'bs1':'bs0'));
      return '<div class="bline"><div class="btr"><div class="bbar '+c+'" style="width:'+w+'%"></div></div><b class="bv">'+v+(f.u||"")+'</b></div>';
    }).join("")+'</div></div>';
  }).join("");
  return '<div class="fig"><div class="fh"><b>'+esc(f.t)+'</b></div>'+lg+body+'</div>';
}
function panelDoc(S){
  var d=S.doc, cls=(d.status==="적용"||d.status==="일부 적용")?"ap":"un";
  var figs=flowDoc(d.num)+(DFIG[d.num]||[]).map(figDoc).join("");
  return figs+'<p class="note"><span class="an-s '+cls+'">'+esc(d.status)+'</span> &nbsp;'+esc(d.cond)+'</p>'+
   '<table class="tbl"><thead><tr>'+d.hd.map(function(h){return '<th>'+esc(h)+'</th>';}).join("")+'</tr></thead><tbody>'+
   d.rows.map(function(r){ return '<tr>'+r.map(function(c){return '<td>'+esc(c)+'</td>';}).join("")+'</tr>'; }).join("")+'</tbody></table>'+
   (d.note?'<p class="note">'+esc(d.note)+'</p>':'')+
   '<p class="note">이 단계는 질문별로 다시 돌린 자료가 없어서 단계 문서(docs/evaluation/stages)의 수치를 옮겼습니다. 단계마다 평가셋과 코퍼스가 달라 다른 단계의 수치와 바로 비교하지 않습니다.</p>';
}
function stageInfo(k){ return SG.nodes.filter(function(n){return n.k===k;})[0]; }
function prevRetKey(k){ var ks=["s0","s13","s16","s21","s22"], i=ks.indexOf(k); return i>0?ks[i-1]:null; }
function prevJudgeKey(k){ var ks=["s18","s20","s21","s22"], i=ks.indexOf(k); return i>0?ks[i-1]:null; }
function qNum(q){ return q.id.replace("docs-v2-",""); }
function qchip(q,k,extra){ return '<button type="button" class="qchip" data-open="'+q.id+'|'+k+'"><span class="qn">'+qNum(q)+'</span>'+esc(q.q.length>46?q.q.slice(0,46)+"…":q.q)+(extra?'<span class="qc">'+extra+'</span>':'')+'</button>'; }
function tile(l,a,b,cls,unit){ return '<div class="tile '+(cls||"")+'"><span class="tl1">'+l+'</span><span class="tv">'+(a==null?'':a+'<i>→</i>')+b+(unit?'<small> '+unit+'</small>':'')+'</span></div>'; }
function retStats(k){
  var pk=prevRetKey(k), A=Q.filter(function(q){return !q.na;}), s={n:A.length,gain:[],loss:[],same:0,pc:0,nc:0,pt:0,nt:0,pd:0,nd:0,m:{bm25:[0,0],vector:[0,0],hybrid:[0,0]}};
  A.forEach(function(q){
    var r=stRec(q,k), p=stRec(q,pk); if(!r||!p||!r.hybrid) return;
    var a=q.sgs[pk], b=q.sgs[k];
    if(a==="chunk") s.pc++; if(b==="chunk") s.nc++;
    if(p.hybrid.r===1) s.pt++; if(r.hybrid.r===1) s.nt++; if(p.hybrid.r>0) s.pd++; if(r.hybrid.r>0) s.nd++;
    ["bm25","vector","hybrid"].forEach(function(m){ if(p[m]&&r[m]){ if(p[m].r>0) s.m[m][0]++; if(r[m].r>0) s.m[m][1]++; } });
    var ev=q.sg.filter(function(e){return e.k===k;})[0];
    if(ev) (ev.t==="gain"?s.gain:s.loss).push(q); else s.same++;
  });
  return s;
}
function judgeStats(k){
  var pk=prevJudgeKey(k), s={caught:0,pcaught:null,fr:0,pfr:null,gain:[],loss:[]};
  function cnt(kk){ var c=0,f=0; Q.forEach(function(q){ var r=stRec(q,kk); if(!r||r.j==null) return; if(q.cat==="unanswerable"&&r.j===1) c++; if(!q.na&&r.j===1&&r.gr===1) f++; }); return [c,f]; }
  var now=cnt(k); s.caught=now[0]; s.fr=now[1];
  if(pk){ var pv=cnt(pk); s.pcaught=pv[0]; s.pfr=pv[1]; }
  Q.forEach(function(q){
    if(q.cat==="out_of_domain") return; var r=stRec(q,k); if(!r||r.j==null) return; var p=pk?stRec(q,pk):null;
    function rj(x){ return q.na?x.j===1:(x.j===1&&x.gr===1); }
    if(!pk){ if(rj(r)) (q.na?s.gain:s.loss).push(q); return; }
    if(q.na||!p||p.j==null) return; var a=rj(p), b=rj(r); if(a===b) return;
    (q.na?b:!b?true:false)?s.gain.push(q):s.loss.push(q);
  });
  return s;
}
function delta(q,k,pk){ var r=stRec(q,k), p=pk?stRec(q,pk):null; if(!r||!r.hybrid||!p||!p.hybrid) return ""; var a=p.hybrid.r,b=r.hybrid.r; return "정답 문서 "+(a>0?a+"위":"반환 밖")+" → "+(b>0?b+"위":"반환 밖"); }

function figRows(rows,total,hasPrev,prevLabel,nowLabel){
  var head='<div class="fh"><b>전체 '+total+'개 중 몇 개가 이 관문을 통과했나</b>'+''+'</div>';
  var body=rows.map(function(r,i){
    var t=r.t||total, d=r.p==null?0:r.n-r.p;
    var good=r.good===false?(d<0):(d>0), cls=d===0?"same":(good?"up":"dn");
    var chip=r.p==null?'':'<span class="dchip '+cls+'">'+(d===0?'변화 없음':(good?'▲ +':'▼ -')+Math.abs(d))+'</span>';
    var prev=r.p!=null?'<span class="pv0">'+r.p+'</span><span class="arr">→</span>':'';
    return '<div class="fr"><div class="fl"><span class="st">'+(i+1)+'</span>'+esc(r.l)+'</div><div class="fb"><div class="nums">'+prev+'<b class="nn">'+r.n+'</b>'+chip+'</div></div></div>';
  }).join("");
  return '<div class="fig">'+head+body+'</div>';
}
function retFigure(k){
  var pk=prevRetKey(k), A=Q.filter(function(q){return !q.na;}), c={};
  function cnt(key,mode,fn){ var v=0, ok=true; A.forEach(function(q){ var r=stRec(q,key); if(!r||!r[mode]){ ok=false; return; } if(fn(r[mode],q,key)) v++; }); return ok?v:null; }
  var defs=[
   ["키워드 검색이 정답 문서를 반환","kw","bm25",function(m){return m.r>0;}],
   ["dense 검색이 정답 문서를 반환","vec","vector",function(m){return m.r>0;}],
   ["두 검색을 합친 결과에 정답 문서가 반환","hy","hybrid",function(m){return m.r>0;}],
   ["그 정답 문서가 1위","hy","hybrid",function(m){return m.r===1;}],
   ["정답 청크가 답변 LLM에 넘어갈 근거에 실림","ok","hybrid",function(m){return !!(m.ev&&m.ev[0]>0);}]
  ];
  var rows=[]; defs.forEach(function(d){ var p=cnt(pk,d[2],d[3]), n=cnt(k,d[2],d[3]); if(p==null||n==null) return; rows.push({l:d[0],c:d[1],p:p,n:n,lost:(A.length-n)+"개 질문에서는 여기서 놓침"}); });
  return figRows(rows,A.length,true,stageInfo(pk).l,stageInfo(k).l+" (이 단계)");
}
function judgeFigure(k,S){
  var pk=prevJudgeKey(k), A=Q.filter(function(q){return !q.na;}), U=Q.filter(function(q){return q.cat==="unanswerable";});
  function c1(key,fn,arr){ var v=0, ok=false; arr.forEach(function(q){ var r=stRec(q,key); if(!r||r.j==null) return; ok=true; if(fn(r,q)) v++; }); return ok?v:null; }
  var rows=[];
  var a1=function(r){return r.gr===1;}, a2=function(r){return r.gr===1&&r.j===0;}, u1=function(r){return r.j===1;};
  var rowsA=[["정답 문서를 가져옴(답이 있는 질문)",a1,"hy",A],["판정 LLM을 통과해 답변 생성으로 넘어감",a2,"ok",A]];
  var ra=rowsA.map(function(d){ return {l:d[0],c:d[2],p:pk?c1(pk,d[1],d[3]):null,n:c1(k,d[1],d[3]),lost:null}; });
  ra[1].lost="정답 문서를 가져오고도 거절된 질문(오거절)이 "+(ra[0].n-ra[1].n)+"개";
  var figA=figRows(ra,A.length,!!pk,pk?stageInfo(pk).l:"",stageInfo(k).l+" (이 단계)").replace('<div class="fh"><b>전체 '+A.length+'개 중 몇 개가 이 관문을 통과했나</b>','<div class="fh"><b>답이 있는 질문 '+A.length+'개가 판정 LLM을 통과하는 과정</b>');
  var ru=[{l:"판정 LLM이 거절해 무응답으로 걸러짐",c:"vec",p:pk?c1(pk,u1,U):null,n:c1(k,u1,U),good:true,t:U.length,lost:null}];
  ru[0].lost="통과해 답변 생성으로 넘어간 무응답 질문이 "+(U.length-ru[0].n)+"개";
  var figU=figRows(ru,U.length,!!pk,pk?stageInfo(pk).l:"",stageInfo(k).l+" (이 단계)").replace('<div class="fh"><b>전체 '+U.length+'개 중 몇 개가 이 관문을 통과했나</b>','<div class="fh"><b>답이 없는 질문 '+U.length+'개가 걸러지는 과정</b>');
  return figA+figU;
}
function diagFigure(k){
  var b={one:0,mid:0,late:0,none:0,tot:0}; Q.forEach(function(q){ var r=stRec(q,k); if(!r||!r.pr) return; r.pr.forEach(function(x){ b.tot++; if(x===0) b.none++; else if(x===1) b.one++; else if(x<=6) b.mid++; else b.late++; }); });
  function seg(c,v,l){ return v?'<div class="'+c+'" style="flex:'+v+' 1 0" title="'+esc(l)+' '+v+'개">'+v+'</div>':''; }
  return '<div class="fig"><div class="fh"><b>정답 청크 '+b.tot+'개가 문서 안에서 놓인 자리</b></div><div class="stackbar">'+seg("s1",b.one,"1번째")+seg("s2",b.mid,"2~6번째")+seg("s3",b.late,"7번째 이후")+seg("s4",b.none,"문서를 못 가져옴")+'</div><div class="fh" style="margin:8px 0 6px"><span class="lg"><i style="background:var(--gc)"></i>1번째</span><span class="lg"><i style="background:var(--vec-soft)"></i>2~6번째(싣는 범위)</span><span class="lg"><i style="background:var(--bad-soft)"></i>7번째 이후(밖으로 밀림 → 판정 LLM도 못 봄)</span><span class="lg"><i style="background:var(--tint);border:1px solid var(--line)"></i>문서를 못 가져옴</span></div></div>';
}
function oodFigure(){
  var O=Q.filter(function(q){return q.cat==="out_of_domain";}), g=O.filter(function(q){return q.gate;}).length;
  return '<div class="fig">'+figRows([{l:"dense 절대 하한(0.7063) 미만이라 검색이 끝나고 빈 결과가 됨",c:"vec",n:g,t:O.length,good:true,lost:"판정 LLM은 호출되지 않음 · 현재 설정에서 측정한 도메인 밖 질문 "+O.length+"개 기준"}],O.length,false,"","이 단계").replace('<div class="fig">','').replace(/<\/div>$/,'').replace('<b>전체 '+O.length+'개 중 몇 개가 이 관문을 통과했나</b>','<b>도메인 밖 질문 '+O.length+'개가 걸러지는 과정</b>')+'</div>';
}
function panelStageBody(S){
  var k=S.k, n=stageInfo(k), out='', tiles='', gain=[], loss=[], lg="나아진 질문", ll="나빠진 질문", pk=null, note=S.note?'<p class="note">'+esc(S.note)+'</p>':'';
  if(S.metrics.indexOf("ret")===0){
    var s=retStats(k); pk=prevRetKey(k); gain=s.gain; loss=s.loss;
    var pn=stageInfo(pk).l;
    tiles+=tile("결과가 바뀐 질문",null,'<span style="color:var(--vec)">▲ '+gain.length+'</span> &nbsp; <span style="color:var(--bad)">▼ '+loss.length+'</span>','','');
    out+='<h3 class="fgt">질문이 걸러지는 과정</h3>'+retFigure(k)+(S.ood?oodFigure():'')+'<div class="tiles">'+tiles+'</div>'+note;
  } else if(S.metrics==="diag"){
    var b={one:0,mid:0,late:0,none:0,tot:0}; Q.forEach(function(q){ var r=stRec(q,k); if(!r||!r.pr) return; r.pr.forEach(function(x){ b.tot++; if(x===0) b.none++; else if(x===1) b.one++; else if(x<=6) b.mid++; else b.late++; }); if(r.pr.some(function(x){return x>6;})) loss.push(q); });
    out+='<h3 class="fgt">정답 청크는 문서 안에서 어디에 놓였나</h3>'+diagFigure(k)+'<p class="note">정답 청크(근거 요건) 단위로 셉니다. 한 질문에 정답 청크가 여러 개일 수 있어서 질문 수와 다릅니다.</p>';
    ll="정답 청크가 문서 안 7번째 이후에 있던 질문";
  } else {}
  if(S.metrics.indexOf("judge")>=0){
    var j=judgeStats(k); pk=prevJudgeKey(k); if(S.metrics==="judge"){ gain=j.gain; loss=j.loss; lg=S.lg; ll=S.ll; }
    var jt='<h3 class="fgt">판정 LLM 관문을 지나며 걸러지는 과정</h3>'+judgeFigure(k,S)+'<p class="note">판정 LLM은 기본값이 꺼짐입니다. 켰다고 가정하고 돌린 기록이며, 같은 코드로 다시 재도 1~2건 흔들립니다. 한두 건 차이로 원인을 단정하지 않습니다.</p>';
    out+=jt;
  }
  var qsec='';
  function list(title,arr,cls){ if(!arr.length) return ''; var top=arr.slice(0,S.kind==="ret"?2:0);
    var cases=top.map(function(q){ return '<button type="button" class="case'+(cls||"")+'" data-open="'+q.id+'|'+k+'"><span class="cn">대표 사례 · '+qNum(q)+'</span><span class="cq">'+esc(q.q)+'</span><span class="cc2">'+esc(delta(q,k,pk))+'</span></button>'; }).join("");
    var rest=arr.slice(top.length).map(function(q){ return qchip(q,k,S.kind==="ret"?esc(delta(q,k,pk)):""); }).join("");
    return '<div class="sv-sec"><h2>'+title+' ('+arr.length+')</h2>'+(cases?'<div class="cases">'+cases+'</div>':'')+(rest?'<div class="qchips">'+rest+'</div>':'')+'</div>'; }
  qsec+=list(lg,gain,"")+list(ll,loss," bad");
  if(!gain.length&&!loss.length&&S.metrics!=="diag") qsec+='<p class="note">이 단계에서 결과가 바뀐 질문이 없습니다.</p>';
  out+=qsec;
  return out;
}
function stgList(){ return st.mode==="c"?STG.filter(function(x){return x.num>=37;}):STG; }
function renderStage(){
  var L=stgList(), S=L.filter(function(x){return x.k===st.stage;})[0]||L[0], c38=st.mode==="c"&&S.k==="d38", n=stageInfo(S.k);
  var nav=document.getElementById("stnav");
  nav.innerHTML='<div class="stlg"><span class="ap">● 코드에 들어감</span><span class="un">● 안 들어감(기본 꺼짐·미적용·측정)</span></div>'+L.map(function(x){ var i=stageInfo(x.k), a=x.doc?(x.doc.status==="적용"||x.doc.status==="일부 적용"):x.k!=="s19"; return '<button type="button" class="'+(a?'ap':'un')+'" data-stage="'+x.k+'"'+(x.k===S.k?' aria-current="true"':'')+'><span class="nl">'+esc(i.l)+(a?' · 적용':' · 안 들어감')+'</span><span class="nt">'+esc(i.t)+'</span></button>'; }).join("");
  var el=document.getElementById("detail");
  el.innerHTML='<div class="wrap"><div class="sv-h"><span class="sl">'+esc(n.l)+' · '+esc(n.t)+'</span><h2 class="big">'+esc(c38?C38.head:S.head)+'</h2></div><div class="panel" role="tabpanel"><div class="sv-two"><div class="sv-sec"><h2>무엇을 고쳤나</h2><ul>'+(c38?C38.what:S.what).map(function(t){return '<li>'+esc(t)+'</li>';}).join("")+'</ul></div><div class="sv-sec"><h2>왜 고쳤나</h2><ul>'+(c38?C38.why:S.why).map(function(t){return '<li>'+esc(t)+'</li>';}).join("")+'</ul></div></div>'+(c38?panelC38():S.doc?'<h2 style="margin-top:6px">단계 기록의 측정값</h2>'+panelDoc(S):'<h2 style="margin-top:6px">얼마나 나아졌나 (docs 정답형 135문항·무응답 26문항 기준)</h2>'+panelStageBody(S))+'</div></div>';
  el.scrollTop=0;
}
