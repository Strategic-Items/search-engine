function ap(rows){ return '<dl class="an-p">'+rows.map(function(r){ return '<dt>'+r[0]+'</dt><dd>'+r[1]+'</dd>'; }).join("")+'</dl>'; }
function V(x){ return '<span class="v">'+x+'</span>'; }
function W(x){ return '<span class="w">'+x+'</span>'; }
var STGN={"13":"s13","14":"s16","15":"s16","16":"s16","18":"s18","19":"s19","20":"s20","21":"s21","22":"s22"};
function tag(nums,un){ return nums.map(function(n){ var k=stgKey(n), st=tagState(n,un), lab=stLabel(n), a=' class="an-s '+st+'" data-gn="'+n+'" data-st="'+st+'"'; return k?'<button type="button"'+a+' data-stage="'+k+'" title="이 단계의 변경 내용 보기">'+lab+'</button>':'<span'+a+'>'+lab+'</span>'; }).join(""); }
function an(cls,n,title,stg,desc,rows,un){ return '<div class="an '+cls+'"><div class="an-h"><span class="an-n">'+n+'</span><span class="an-t">'+title+'</span>'+tag(stg,un)+'</div>'+(rows?ap(rows):'')+'</div>'; }

var UNUSED={"38":1,"10":1,"17":1,"24":1,"35":1,"36":1,"1":1,"2":1,"3":1,"7":1,"9":1,"11":1,"26":1,"27":1,"29":1,"spl":1};
function tagState(n,un){ return (un&&un.indexOf(String(n))>=0)||UNUSED[n]?"un":"ap"; }
function stLabel(n){ return n==="spl"?"SPLADE":n+"단계"; }
function gtag(x,y,label,k,st,gn){ var w=label.length*9.2+16; st=st||tagState(parseInt(label,10)); gn=gn||parseInt(label,10); return '<g'+(k?' data-stage="'+k+'"':'')+' data-gn="'+gn+'" data-st="'+st+'"><rect class="gt '+st+'" x="'+(x-w)+'" y="'+y+'" width="'+w+'" height="24" rx="12"/><text class="gtt '+st+'" x="'+(x-w/2)+'" y="'+(y+17)+'" text-anchor="middle">'+label+'</text></g>'; }
function fnode(o){
  var nk=null; (o.g||[]).some(function(g){ if(STGN[g]){ nk=STGN[g]; return true; } });
  var s='<g class="'+(o.c||"")+(nk?' clk':'')+'"'+(nk?' data-stage="'+nk+'"':'')+(o.tip?' data-tip="'+o.tip+'"':'')+'><rect class="bx" x="'+o.x+'" y="'+o.y+'" width="'+o.w+'" height="'+o.h+'" rx="18"/>';
  s+='<g class="badge"><circle cx="'+(o.x+24)+'" cy="'+(o.y+28)+'" r="15"/><text x="'+(o.x+24)+'" y="'+(o.y+34)+'" text-anchor="middle">'+o.n+'</text></g>';
  s+='<text class="nt" x="'+(o.x+50)+'" y="'+(o.y+35)+'">'+o.t+'</text>';
  o.l.forEach(function(t,i){ s+='<text class="nl" x="'+(o.x+22)+'" y="'+(o.y+70+i*27)+'">'+t+'</text>'; });
  var right=o.x+o.w-14, tx=right, row=0, mx=o.mx||(o.x+o.w/2+20);
  (o.g||[]).slice().reverse().forEach(function(g){ var lab=stLabel(g), w=lab.length*9.2+16;
    if(tx<right&&tx-w<mx){ row++; tx=right; }
    s+=gtag(tx,o.y-13-row*28,lab,stgKey(g),tagState(g,o.un),g); tx-=w+6; });
  return s+'</g>';
}
function fline(d,cls,label,lx,ly,lcls,anchor,marker){ return '<path class="'+cls+'" d="'+d+'" marker-end="url(#'+(marker||"ah")+')"/>'+(label?'<text class="el '+(lcls||"")+'" x="'+lx+'" y="'+ly+'" text-anchor="'+(anchor||"middle")+'">'+label+'</text>':''); }
function archSvg(){
  var s='<svg class="flowsvg" id="flowsvg" viewBox="-520 0 1760 2455" style="width:100%" role="img" aria-label="검색부터 답변까지의 흐름도"><defs>';
  [["ah","--muted"],["ahk","--kw"],["ahv","--vec"],["ahr","--bad"],["ahs","--sp"]].forEach(function(m){ s+='<marker id="'+m[0]+'" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="11" markerHeight="11" orient="auto"><path d="M1,1 L11,6 L1,11 z" style="fill:var('+m[1]+')"/></marker>'; });
  s+='</defs>';
  // 입력
  s+=fnode({c:"end",tip:"in0",g:["37","27"],mx:130,x:110,y:20,w:380,h:104,n:"0",t:"질문 입력",l:["이용자가 쓴 문장 그대로","기준일 = 검색하는 날짜(오늘)"]});
  s+=fnode({c:"opt",tip:"opt_rewrite",g:["5","7"],un:["5"],mx:-260,x:-280,y:34,w:320,h:68,n:"·",t:"질의 재작성 (꺼짐)",l:[]}).replace('</g></g>','</g></g>');
  s+='<text class="nl" x="-236" y="92" style="font-size:14.5px;fill:var(--muted)">켜면 재작성 질문을 가중치 0.5로 합침</text>';
  s+='<path class="lnd" d="M40,68 H110"/>';
  s+=fline('M300,124 V170','ln','',0,0);
  s+=fnode({c:"end",x:-30,y:170,w:660,h:205,tip:"filter",n:"F",t:"필터 (키워드·dense 두 검색에 똑같이 적용)",l:["① 시행일이 오늘 이전인 문서 (시행일이 없으면 통과)","② 종료일이 오늘보다 뒤인 문서 (종료일이 없으면 통과)","→ 시행 전이거나 이미 만료된 문서는 후보가 되지 못함","③ 질문에 ‘제2026-598호’ 같은 공고번호가 있으면 제목·본문에 그 번호가 든 문서만","점수를 매기기 전에 걸러서 후보 자리부터 얻지 못함"]});
  s+=fnode({c:"opt",tip:"strip",g:["23","25","1","2","3","26","29"],mx:670,x:660,y:200,w:250,h:120,n:"·",t:"측정·검증 단계",l:["검색 기능이 아니라","재는 방법·기준선·검증 기록"]});
  s+='<g><rect class="gt ap" x="660" y="344" width="64" height="24" rx="12"/><text class="gtt ap" x="692" y="361" text-anchor="middle">적용</text><text class="el" x="732" y="361">초록 = 지금 쓰는 것</text></g>';
  s+='<g><rect class="gt un" x="660" y="376" width="64" height="24" rx="12"/><text class="gtt un" x="692" y="393" text-anchor="middle">미사용</text><text class="el" x="732" y="393">빨간 점선 = 안 쓰는 것</text></g>';
  s+='<g transform="translate(0,255)">';
  s+='<g>';
  s+='<text class="nt" x="-500" y="150" style="font-size:18px;fill:var(--sp)">SPLADE 길 · BM25 대신 시험 (현재 미사용)</text>';
  s+=fline('M300,172 H-260 V196','lns','',0,0,'','','ahs');
  s+=fnode({c:"spl",tip:"spl1",g:["24","35","38"],x:-500,y:200,w:480,h:170,n:"1",t:"질문을 어휘 가중치로 (SPLADE)",l:["telepix/PIXIE-Splade-v1.5","질문을 읽고 어휘 전체에 가중치를 매김","질문에 없는 연관어도 가중치를 받음","상위 256개 term만 남김"]});
  s+=fnode({c:"spl",tip:"spl2",g:["10","17"],x:-500,y:440,w:480,h:196,n:"2",t:"점곱으로 청크 점수 계산",l:["청크도 색인할 때 같은 방식으로 변환","(제목+본문 256토큰, 상위 256 term)","질문 가중치 × 청크 가중치의 합","OpenSearch rank_features · neural_sparse"]});
  s+=fnode({c:"spl",tip:"spl3",g:["24","36"],x:-500,y:706,w:480,h:170,n:"3",t:"후보 자르기",l:["1위 점수의 97% 미만은 버림","(점수 분포가 달라 BM25와 다른 비율)","문서 점수 = 부모별 최고 청크 점수"]});
  s+=fline('M-260,370 V440','lns','질문 가중치',-244,412,'els','start','ahs')+fline('M-260,636 V706','lns','청크별 점수',-244,678,'els','start','ahs');
  s+=fline('M-260,876 V1075 H58','lns','',0,0,'','','ahs');
  s+='<text class="el els" x="-244" y="1060">BM25 대신 SPLADE+dense를 합산하면 (36단계 비교 · 미사용)</text>';
  s+='</g>';
  s+=fline('M300,120 V196','ln','',0,0)+fline('M300,172 H900 V196','ln','같은 질문·같은 조건을 두 검색에 동시에 보냄',320,162,'','start');
  // 키워드 레인
  s+=fnode({c:"kw",tip:"k1",x:60,y:200,w:480,h:170,n:"1",t:"형태소로 쪼갬 (nori)",g:["12"],l:["어미·조사는 버리고 내용어만 남김","보조용언(VX) 제거 · 소문자","동의어 20그룹은 본문 검색에만 적용"]});
  s+=fnode({c:"kw",tip:"k2",x:60,y:440,w:480,h:196,n:"2",t:"BM25로 청크 점수 계산",g:["22","28","30","32","34"],l:["제목 ×1 + 본문 ×1 (필드 점수를 더함)","k1 1.2 · b 0.75 (OpenSearch 기본값)","현행판 +4 (모든 문서 동일)","질문에 연·월이 있으면 일치 문서 +6 / +4"]});
  s+=fnode({c:"kw",tip:"k3",x:60,y:706,w:480,h:170,n:"3",t:"후보 자르기",g:["14","21"],l:["① 하한 14.75 미만 청크는 버림","② 1위 점수의 90% 미만 청크는 버림","전부 버려져도 종료는 아님"]});
  s+=fline('M300,370 V440','lnk','질문 토큰',284,412,'elk','end','ahk')+fline('M300,636 V706','lnk','청크별 점수',316,678,'elk','start','ahk');
  // dense 레인
  s+=fnode({c:"vec",tip:"d1",x:660,y:200,w:480,h:170,n:"1",t:"질문을 벡터로 (임베딩)",g:["13","15","11"],l:["BGE-m3-ko (Ollama · GGUF F16)","질문 문장을 통째로 1번 · 어절 분해 없음","1024차원 벡터 1개"]});
  s+=fnode({c:"vec",tip:"d2",x:660,y:440,w:480,h:196,n:"2",t:"가까운 청크 찾기 (kNN)",g:["6","39"],l:["HNSW 색인 · 코사인 유사도","청크 벡터는 색인할 때 미리 계산","(제목: … 본문: … 형태로 임베딩)"]});
  s+=fnode({c:"vec",tip:"d3",x:660,y:706,w:480,h:170,n:"3",t:"후보 자르기",g:["14","16","21"],l:["① 하한 0.7063 미만 청크는 버림","② 1위 점수의 97% 미만 청크는 버림","전부 버려지면 → 검색 종료 (빨간 점선)"]});
  s+=fline('M900,370 V440','lnv','질문 벡터',916,412,'elv','start','ahv')+fline('M900,636 V706','lnv','청크별 유사도',916,678,'elv','start','ahv');
  // 합류
  s+=fline('M300,876 V930 H180 V976','lnk','',0,0,'','','ahk')+fline('M900,876 V930 H420 V976','lnv','',0,0,'','','ahv');
  s+='<text class="el" x="660" y="920" text-anchor="middle">키워드·dense 청크 → 문서 단위로</text>';
  s+=fnode({c:"end",tip:"rrf",x:60,y:980,w:480,h:190,n:"4",t:"문서 단위 RRF 합산",g:["21"],l:["문서마다 목록 안 첫 청크 자리만 셈","점수 = 목록별 1/(60+자리)의 합","키워드 1.0 : dense 1.0 (같은 무게)","동점이면 dense 자리가 앞"]});
  s+=fline('M300,1170 V1236','ln','문서 순위 목록',316,1210,'','start');
  s+=fnode({c:"end",tip:"cut",x:60,y:1240,w:480,h:170,n:"5",t:"컷오프",g:["21","9"],l:["1위 RRF 점수 × 0.90 미만은 제외","목록 1위 청크의 문서는 예외 유지","같은 문서 사본은 1개 · 최대 5문서"]});
  s+=fline('M300,1410 V1476','ln','문서 ≤5개',316,1450,'','start');
  s+=fnode({c:"end",tip:"pick",x:60,y:1480,w:480,h:170,n:"6",t:"문서 안 청크 고르기",g:["4","8","19","20"],l:["문서당 최대 6개 청크","첫 청크 = dense가 고른 청크","나머지 = 청크 단위 RRF 순서"]});
  s+=fline('M300,1650 V1716','ln','근거 = 문서 ≤5 × 청크 ≤6',316,1690,'','start');
  // 판정 다이아몬드
  s+='<g class="end" data-tip="judge"><polygon class="dia" points="300,1720 580,1846 300,1972 20,1846"/><g class="badge"><circle cx="300" cy="1758" r="15"/><text x="300" y="1764" text-anchor="middle">7</text></g><text class="nt" x="300" y="1826" text-anchor="middle" style="font-size:19px">판정 LLM (선택)</text><text class="nl" x="300" y="1852" text-anchor="middle" style="font-size:15.5px">근거에 질문이 요구하는</text><text class="nl" x="300" y="1874" text-anchor="middle" style="font-size:15.5px">사실이 적혀 있나?</text><text class="nl" x="300" y="1898" text-anchor="middle" style="font-size:14px;fill:var(--muted)">기본 꺼짐 · 순위는 안 바꿈</text>'+gtag(355,1712,"18단계","s18")+gtag(295,1712,"21단계","s21")+'</g>';
  // 분기
  s+=fline('M20,1846 H-20 V2000','ln','예',2,1836,'yes','end');
  s+=fline('M580,1846 H620 V2000','lnr','아니오',608,1836,'nop','start','ahr');
  s+=fline('M60,1565 H-300 V2090 H-260','lnd','',0,0);
  s+='<text class="el" x="-284" y="1600">판정이 꺼져 있으면</text><text class="el" x="-284" y="1620">이 단계를 건너뜀</text>';
  // 결과
  s+=fnode({c:"ans",tip:"ans",x:-260,y:2004,w:480,h:150,n:"8",t:"답변 LLM",l:["qwen3-vl-30b-a3b · temperature 0.4","근거 문서·청크를 프롬프트에 넣고 스트리밍"]});
  s+=fnode({c:"fix",tip:"fix",x:380,y:2004,w:480,h:150,n:"8",t:"고정 문구",l:["LLM을 부르지 않음","yesTrade 전문판정 신청 안내"]});
  // 조기 종료
  s+='<path class="lnr" d="M1140,790 H1204 V2080 H860" marker-end="url(#ahr)"/><text class="el elr" transform="translate(1225,1430) rotate(-90)" text-anchor="middle">dense 청크가 하나도 안 남으면 여기서 종료 (판정 LLM도 건너뜀)</text>';
  // 선택 기능
  s+=fnode({c:"opt",tip:"opt_chunkfirst",un:["33"],x:560,y:1010,w:280,h:80,n:"·",t:"청크 우선 파이프라인",g:["33"],l:[]});
  s+='<text class="el" x="580" y="1078" style="font-size:14px">꺼짐 (문서 대신 청크를 먼저 고름)</text><path class="lnd" d="M540,1075 H560"/>';
  s+=fnode({c:"opt",tip:"opt_chunkfilter",un:["31"],x:560,y:1480,w:280,h:80,n:"·",t:"청크 LLM 관련도 필터",g:["31"],l:[]});
  s+='<text class="el" x="580" y="1548" style="font-size:14px">기본 꺼짐 (.env는 켬)</text><path class="lnd" d="M540,1520 H560"/>';
  s+=fnode({c:"opt",tip:"opt_rerank",un:["19"],x:560,y:1580,w:280,h:80,n:"·",t:"cross-encoder 재정렬",g:["19"],l:[]});
  s+='<text class="el" x="900" y="1648" style="font-size:14px">꺼짐 (20단계가 대체)</text><path class="lnd" d="M860,1620 H880"/>';
  return s+'</g></svg>';
}
function panelArch(){
  var OFF='<span class="off">꺼짐</span>';
  var r0=an("","입력","질문 + 조건",["37","27","5","7"],"",[
    ["유효기간 필터","시행일 ≤ 기준일 &lt; 종료일"],["공고번호 필터","번호가 든 청크만"],["질의 재작성",OFF]],["5"]);
  var a1=an("kw","① · 1","형태소로 쪼개기",["12"],"",[["분석기",V("nori")],["동의어",V("20")+"그룹"]]);
  var a2=an("kw","① · 2","BM25 점수",["22","28","30","32","34"],"",[
    ["제목 : 본문",W("1 : 1")],["k1 / b",V("1.2 / 0.75")],["현행판 가산",W("+4")],["연·월 가산",W("+6 / +4")]]);
  var a3=an("kw","① · 3","후보 자르기",["14","21"],"",[
    ["후보 수",V("25")+"개"],["절대 하한",V("14.75")],["1위의",W("90%")+" 미만 제거"],["다 버려지면","종료 아님"]]);
  var b1=an("vec","② · 1","질문 → 벡터",["13","15","11"],"",[["모델",V("BGE-m3-ko")],["차원",V("1024")]]);
  var b2=an("vec","② · 2","가까운 청크 찾기",["6","39"],"",[["색인",V("HNSW")+" 코사인"],["후보 수",V("25")+"개"]]);
  var b3=an("vec","② · 3","후보 자르기",["14","16","21"],"",[
    ["절대 하한",V("0.7063")],["1위의",W("97%")+" 미만 제거"],["다 버려지면",'<span class="off">검색 종료</span>']]);
  var m1=an("mg","③","문서 단위 RRF 합산",["21"],"",[["점수",V("Σ 가중치 × 1/(60+자리)")],["자리","목록 안 <b>청크</b> 위치 (문서 순서가 아님)"],["키워드 : dense",W("1.0 : 1.0")],["기간 질문","제목이 맞는 후보로 3번째 목록 1.0 추가"],["최고점",V("2/61 = 0.0328")+" (두 목록 1위)"],["한 목록만",V("1/61 = 0.0164")+" (최고점의 정확히 절반)"],["동점","dense 자리 → 청크 ID 순"]]);
  var m2=an("mg","④","컷오프",["21","9"],"",[["컷오프 선","1위 RRF 점수 × "+W("0.90")],["선 아래라도 유지","어느 목록의 1위 청크인 문서 · 기간 일치 문서"],["절대 하한","RRF 점수에는 없음 (①에서 검색기별로 적용)"],["사본","같은 제목·발행일은 먼저 오른 1개만"],["문서 수",V("최대 5")+"개"]]);
  var m3=an("mg","⑤","문서 안 청크 고르기",["4","8","19","20"],"",[["문서당",V("최대 6")+"개"],["첫 청크","dense가 고른 것"],["나머지","청크 단위 RRF 점수 순 (문서 RRF와 별개)"],["후보 풀","① 비율 자르기 전 목록 (키워드 25 + dense 25, 하한 통과분)"]]);
  var m4=an("mg","⑥","판정 LLM (선택)",["18","21"],"",[["기본값",OFF+" (.env는 켬)"],["읽는 문서",V("3")+"개"],["temperature",V("0.0")]]);
  var m5=an("mg","⑦","답변",[],"",[["답변 LLM",V("qwen3-vl-30b-a3b")],["temperature",V("0.4")],["근거 없으면","고정 문구"]]);
  var o1=an("opt","선택","청크 LLM 필터",["31"],"",[["기본값",OFF+" (.env는 켬)"]],["31"]);
  var o2=an("opt","선택","cross-encoder 재정렬",["19"],"",[["기본값",OFF]],["19"]);
  var o3=an("opt","선택","청크 우선 파이프라인",["33"],"",[["기본값",OFF]],["33"]);
  var ms=an("opt","측정","측정·검증 단계",["23","25","1","2","3","26","29"],"",[["성격","검색 기능이 아니라 재는 방법·기준선·검증 기록"]]);
  var zoomBar='<div class="archbar"><span class="note">2026-10-02 설정 기준 · 초록 태그 = 지금 쓰는 단계, 빨간 점선 태그 = 안 쓰는 단계 · 태그를 올리면 설명, 누르면 그 단계로 이동</span><button type="button" class="zb" data-zoom="-1">− 작게</button><button type="button" class="zb" data-zoom="1">크게 +</button></div>';
  return '<div class="wrap" style="max-width:none"><div class="sv-h"><span class="sl">구조도</span><h2 class="big">질문이 답변이 되기까지 어떻게 흘러가나</h2></div>'+zoomBar+
   '<div id="ar-flow" style="overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--paper);padding:14px">'+archSvg()+'</div>'+
   '<h2 style="margin-top:14px">각 상자의 설정값</h2>'+
   '<div class="ps">'+
   '<div class="ps-col full" id="ar-in">'+r0+'</div>'+
   '<div class="ps-col"><div class="an-lane kw" id="ar-kw">키워드 경로 (BM25)</div>'+a1+a2+a3+'</div>'+
   '<div class="ps-col"><div class="an-lane vec" id="ar-vec">dense 경로</div>'+b1+b2+b3+'</div>'+
   '<div class="ps-col full"><div class="an-lane" id="ar-mg">합치고 자르고 답하기</div><div class="ps-g">'+m1+m2+m3+m4+m5+'</div></div>'+
   '<div class="ps-col full"><div class="an-lane" id="ar-opt">선택 기능 (기본 꺼짐)</div><div class="ps-g">'+o1+o2+o3+'</div></div>'+
   '<div class="ps-col full"><div class="an-lane" id="ar-ms">측정·검증 단계 (기능이 아님)</div><div class="ps-g">'+ms+'</div></div>'+
   '</div></div>';
}
function renderArch(){
  var nav=document.getElementById("stnav"), items=[["ar-flow","전체 흐름도"],["ar-in","상세: 입력·조건"],["ar-kw","키워드 경로"],["ar-vec","dense 경로"],["ar-mg","합산·컷오프·판정·답변"],["ar-opt","선택 기능과 예외"]];
  nav.innerHTML=items.map(function(x){ return '<button type="button" data-go2="'+x[0]+'"><span class="nl">구조도</span><span class="nt">'+x[1]+'</span></button>'; }).join("");
  var el=document.getElementById("detail"); el.innerHTML=panelArch(); el.scrollTop=0;
}
