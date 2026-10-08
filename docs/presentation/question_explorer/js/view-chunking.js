/* 법령 청킹 결과: 기존 Git 전후 기록과 통제 측정을 변경 유형별로 모아 본다. */
var CK={group:null,qid:'033',tab:'sp',filter:'gain',search:''};
function ckHash(s){var h=0;for(var i=0;i<s.length;i++) h=Math.imul(h,31)+s.charCodeAt(i)|0;return (h>>>0).toString(36);}
function ckRank(n){return n==null?'근거 미충족':n+'위';}
function ckChange(a,b){return ckRank(a)+' → '+ckRank(b);}
function ckEffect(row){var m=row.m,a=m.globalBefore.returnedRanks[2],b=m.globalAfter.returnedRanks[2];return a==null?(b==null?0:1):(b==null?-1:(a>b?1:(a<b?-1:0)));}
var CK_PINNED_TITLES=['표 행에 단위·머리글 포함','품목 키·이어지는 표·일반기준 분리'];
function ckGroups(){
  var groups={},history=window.CATEGORY_CHUNKING_HISTORY||{},impact=(window.CATEGORY_CHUNKING_IMPACT||{}).measurements||{};
  Object.keys(history).filter(function(id){return id.indexOf('law100-')===0;}).forEach(function(id){
    var x=CQ.find(function(q){return q.id===id;});
    history[id].forEach(function(e){var m=(impact[id]||{})[e.commit];if(!x||!m||!m.globalBefore) return;
      var key=e.commit+'-'+ckHash(e.title);
      if(!groups[key]) groups[key]={id:key,title:e.title,date:e.date,commit:e.commit,rows:[]};
      groups[key].rows.push({x:x,e:e,m:m});
    });
  });
  return Object.values(groups).map(function(g){g.gain=g.rows.filter(function(r){return ckEffect(r)>0;}).length;g.loss=g.rows.filter(function(r){return ckEffect(r)<0;}).length;g.fresh=g.rows.filter(function(r){return r.m.globalBefore.returnedRanks[2]==null&&r.m.globalAfter.returnedRanks[2]!=null;}).length;return g;}).sort(function(a,b){var ap=CK_PINNED_TITLES.indexOf(a.title),bp=CK_PINNED_TITLES.indexOf(b.title);ap=ap<0?CK_PINNED_TITLES.length:ap;bp=bp<0?CK_PINNED_TITLES.length:bp;return ap-bp||b.gain-a.gain||b.fresh-a.fresh||a.date.localeCompare(b.date)||a.title.localeCompare(b.title);});
}
function ckVisibleGroups(){return ckGroups().filter(function(g){return g.loss<=g.gain&&(CK.filter!=='gain'||g.gain>0)&&(CK.filter!=='loss'||g.loss>0)&&(!CK.search||(g.title+' '+g.commit+' '+g.rows.map(function(r){return r.x.i+' '+r.x.q;}).join(' ')).toLowerCase().replace(/\s/g,'').includes(CK.search.toLowerCase().replace(/\s/g,'')));});}
function ckSelected(){
  var groups=ckVisibleGroups(),g=groups.find(function(o){return o.id===CK.group;});
  if(!g) g=groups.find(function(o){return o.commit==='e1749ca'&&o.rows.some(function(r){return r.x.i==='033';});})||groups[0];
  if(!g) return null;
  CK.group=g.id;
  var row=g.rows.find(function(r){return r.x.i===CK.qid;})||g.rows.find(function(r){return ckEffect(r)>0;})||g.rows[0];
  CK.qid=row.x.i;return {g:g,row:row};
}
function ckSetHash(){location.hash='cat-chunking-'+CK.group+'-'+CK.qid;}
function ckReadHash(hash){
  if(hash==='cat-chunking') return true;
  if(hash.indexOf('cat-chunking-')!==0) return false;
  var match=hash.slice(13).match(/^(.*)-(\d{3})$/),g=match&&ckGroups().find(function(o){return o.id===match[1]&&o.rows.some(function(r){return r.x.i===match[2];});});
  if(g){if(CK.group!==g.id||CK.qid!==match[2])CK.search='';CK.group=g.id;CK.qid=match[2];if(CK.filter==='gain'&&!g.gain||CK.filter==='loss'&&!g.loss) CK.filter='all';}
  return true;
}
function ckList(){
  var groups=ckVisibleGroups();
  document.getElementById('list').innerHTML='<div class="ck-controls"><div class="seg" aria-label="청킹 결과 필터">'+[['gain','개선 있음'],['all','전체'],['loss','악화 있음']].map(function(f){return '<button type="button" data-ck-filter="'+f[0]+'" aria-pressed="'+(CK.filter===f[0])+'">'+f[1]+'</button>';}).join('')+'</div><input type="search" id="ck-search" aria-label="청킹 변경 또는 질문 검색" placeholder="청킹 변경·질문 번호 검색"><p class="cap">청킹 변경 '+groups.length+'개 · 법령·고시만</p></div>'+groups.map(function(g){return '<button type="button" class="item ck-group" role="option" data-ck-group="'+g.id+'"'+(g.id===CK.group?' aria-current="true"':'')+'><span class="dot'+(g.gain?'':' miss')+'"></span><span><span class="meta">'+'질문 '+g.rows.length+'개</span><span class="txt">'+esc(g.title)+'</span><span class="ck-group-count">개선 '+g.gain+' · 동일 '+(g.rows.length-g.gain-g.loss)+' · 악화 '+g.loss+'</span></span></button>';}).join('');
  document.getElementById('ck-search').value=CK.search;
}
function ckStats(){var groups=ckGroups(),rows=groups.flatMap(function(g){return g.rows;});return '<div class="ck-stats">'+[['측정 질문',new Set(rows.map(function(r){return r.x.i;})).size+'개'],['청킹 비교',rows.length+'건'],['Hybrid 개선',rows.filter(function(r){return ckEffect(r)>0;}).length+'건'],['새 근거 반환',new Set(rows.filter(function(r){return r.m.globalBefore.returnedRanks[2]==null&&r.m.globalAfter.returnedRanks[2]!=null;}).map(function(r){return r.x.i;})).size+'개 질문']].map(function(t){return '<div><span>'+t[0]+'</span><b>'+t[1]+'</b></div>';}).join('')+'</div>';}
function ckScoreCards(row,kind){var m=row.m,field=kind==='sp'?'spladeScore':'denseCosine',a=m.before[field],b=m.after[field],delta=b-a;return '<div class="ck-scores '+kind+'"><div><span>수정 전 '+(kind==='sp'?'SPLADE 점수':'dense 코사인')+'</span><b>'+a.toFixed(4)+'</b></div><div><span>수정 후</span><b>'+b.toFixed(4)+'</b></div><div><span>점수 변화</span><b class="'+(delta>0?'positive':delta<0?'negative':'')+'">'+(delta>0?'+':'')+delta.toFixed(4)+'</b></div></div>';}
function ckHeat(row,kind){
  var terms=kind==='sp'?row.m.spladeTokens:row.m.denseWords;
  var max=Math.max.apply(null,terms.flatMap(function(t){return [Math.abs(t.before),Math.abs(t.after)];}).concat([.0001]));
  var ordered=terms.slice().sort(function(a,b){return Math.max(Math.abs(b.before),Math.abs(b.after))-Math.max(Math.abs(a.before),Math.abs(a.after));});
  return '<div class="ck-two">'+['before','after'].map(function(arm){return '<article><h3>'+(arm==='before'?'수정 전':'수정 후')+' · 질문 '+(kind==='sp'?'토큰':'어절')+'의 기여</h3><div class="ck-heat '+kind+'">'+ordered.map(function(t){var v=t[arm],alpha=Math.min(.85,.12+.73*Math.abs(v)/max);return '<span class="'+(v<0?'negative':'')+'" style="--heat-alpha:'+alpha.toFixed(3)+'" title="기여 '+v.toFixed(4)+'">'+esc(t.token||t.word)+'<small>'+v.toFixed(3)+'</small></span>';}).join('')+'</div></article>';}).join('')+'</div><p class="ck-legend">같은 색 눈금으로 비교합니다. 진할수록 기여가 큽니다.'+(kind==='sp'?' 확장 토큰도 포함합니다.':' 빨간색은 어절을 지우면 유사도가 오르는 경우입니다.')+'</p>';
}
function ckBars(row,kind){
  var terms=(kind==='sp'?row.m.spladeTokens:row.m.denseWords).slice().sort(function(a,b){return Math.abs(b.after-b.before)-Math.abs(a.after-a.before);}).slice(0,8);
  var max=Math.max.apply(null,terms.flatMap(function(t){return [Math.abs(t.before),Math.abs(t.after)];}).concat([.0001]));
  return '<div class="ck-bars '+kind+'"><h3>청킹 수정으로 기여가 가장 달라진 '+(kind==='sp'?'토큰':'어절')+'</h3><p class="ck-legend"><i class="before"></i>수정 전 <i class="after"></i>수정 후 · '+(kind==='sp'?'질문 가중치 × 청크 가중치':'해당 어절 삭제 시 코사인 감소량')+'</p>'+terms.map(function(t){return '<div class="ck-bar-row"><b>'+esc(t.token||t.word)+'</b><div>'+['before','after'].map(function(arm){return '<div class="ck-track"><i class="'+arm+(t[arm]<0?' negative':'')+'" style="width:'+(Math.abs(t[arm])/max*100).toFixed(1)+'%"></i></div>';}).join('')+'</div><span>'+t.before.toFixed(4)+' → '+t.after.toFixed(4)+'<strong class="'+(t.after-t.before>=0?'positive':'negative')+'">'+(t.after-t.before>0?'+':'')+(t.after-t.before).toFixed(4)+'</strong></span></div>';}).join('')+'</div>';
}
function ckBodies(row,highlight){
  var e=row.e,segments=new Set((row.m.changedSegment.text||'').split('\n').filter(Boolean));
  function text(body,arm){return body.split('\n').map(function(line){return arm==='after'&&highlight&&segments.has(line)?'<mark>'+esc(line)+'</mark>':esc(line);}).join('\n');}
  return '<div class="ck-two ck-bodies">'+['before','after'].map(function(arm){return '<article><h3>'+(arm==='before'?'수정 전':'수정 후')+' 청크</h3><p class="cap">#'+esc(e[arm].id.split('#').pop())+' · '+esc(e[arm].path.join(' → ')||'제목 경로 없음')+'</p><pre>'+text(e[arm].body,arm)+'</pre></article>';}).join('')+'</div>';
}
function ckReturn(row){
  var m=row.m;
  function table(title,a,b){return '<h3>'+title+'</h3><div class="ck-table-wrap"><table class="ck-table"><thead><tr><th>검색 방식</th><th>수정 전 후보</th><th>수정 후 후보</th><th>수정 전 반환</th><th>수정 후 반환</th></tr></thead><tbody>'+['SPLADE','dense','Hybrid'].map(function(name,i){return '<tr><th>'+name+'</th><td>'+ckRank(a.candidateRanks[i])+'</td><td>'+ckRank(b.candidateRanks[i])+'</td><td>'+ckRank(a.returnedRanks[i])+'</td><td>'+ckRank(b.returnedRanks[i])+'</td></tr>';}).join('')+'</tbody></table></div>';}
  return table('질문 전체의 필수 근거',m.globalBefore,m.globalAfter)+table('이 대상 문서의 완전한 근거',m.before,m.after)+'<p class="note">질문 전체 비교는 이 커밋으로 모델 입력이 바뀐 문서 '+m.globalChangedParents+'개를 함께 교체했습니다. 다른 문서가 이미 답을 반환하던 질문은 대상 청크가 좋아져도 질문 전체의 반환 순위가 그대로일 수 있습니다.</p>';
}
function ckVisualCompare(row,kind){
  var terms=kind==='sp'?row.m.spladeTokens:row.m.denseWords;
  var max=Math.max.apply(null,terms.flatMap(function(t){return [Math.abs(t.before),Math.abs(t.after)];}).concat([.0001]));
  var segments=(row.m.changedSegment.text||'').split('\n').filter(Boolean);
  function changedText(text,start,arm){
    var data=((window.CATEGORY_CHUNKING_DIFF||{})[row.x.id]||{})[row.e.commit],ranges=data?data[arm]:[];
    var out='',end=start+text.length,at=start;
    ranges.forEach(function(r){var a=Math.max(start,r[0]),b=Math.min(end,r[1]);if(a>=b)return;out+=esc(text.slice(at-start,a-start));out+='<span class="ck-diff '+arm+'" title="'+r[2]+'"'+(a===r[0]?' data-change="'+r[2]+'"':'')+'>'+esc(text.slice(a-start,b-start))+'</span>';at=b;});
    return out+esc(text.slice(at-start));
  }
  function body(arm){
    var raw=row.e[arm].body;
    if(kind==='dn'){
      var data=((window.CATEGORY_CHUNKING_BODY||{})[row.x.id]||{})[row.e.commit];
      if(!data)return esc(raw);
      var maxDrop=Math.max.apply(null,['before','after'].flatMap(function(a){return data[a].map(function(z){return Math.abs(z[1]);});}).concat([.0005]));
      var offset=0;return data[arm].map(function(z){var start=offset;offset+=z[0].length;var v=z[1],alpha=Math.abs(v)>.001?Math.min(.9,.15+.75*Math.abs(v)/maxDrop):0;return '<span class="ck-body-segment'+(v<0?' negative':'')+'" style="--segment-alpha:'+alpha.toFixed(3)+'" title="이 구간을 빼면 유사도 '+(v>=0?'−':'+')+Math.abs(v).toFixed(4)+'">'+changedText(z[0],start,arm)+'</span>';}).join('');
    }
    var tokens=terms.filter(function(t){return t[arm]>0&&t.token.length>1&&!t.token.startsWith('[');}).sort(function(a,b){return b.token.length-a.token.length;});
    var out='',i=0;
    while(i<raw.length){var t=tokens.find(function(t){return raw.startsWith(t.token,i);});if(t){out+='<mark class="ck-sp-match" title="토큰 기여 '+t[arm].toFixed(4)+'" style="--match-alpha:'+(.18+.62*t[arm]/max).toFixed(3)+'">'+changedText(t.token,i,arm)+'</mark>';i+=t.token.length;}else{out+=changedText(raw[i],i,arm);i++;}}
    return out;
  }
  function bodyTop(arm){
    var data=((window.CATEGORY_CHUNKING_BODY||{})[row.x.id]||{})[row.e.commit];
    if(!data)return '';
    var top=data[arm].slice().sort(function(a,b){return b[1]-a[1];}).filter(function(z){return z[1]>.001;}).slice(0,2);
    return '<p class="ck-body-top">'+(top.length?'영향이 큰 구간: '+top.map(function(z){return '<b>“'+esc(z[0].trim())+'”</b> (−'+z[1].toFixed(4)+')';}).join(', '):'뚜렷하게 영향을 준 구간이 없습니다.')+'</p>';
  }
  return '<p class="ck-diff-legend"><span class="before">삭제·교체 전</span><span class="after">추가·교체 후</span> 점선 표시가 실제 청킹 변경 부분입니다.</p><div class="ck-visual-compare '+kind+'">'+['before','after'].map(function(arm){
    var scores=row.m[arm],field=kind==='sp'?'spladeScore':'denseCosine',idx=kind==='sp'?0:1;
    var top=terms.slice().sort(function(a,b){return Math.abs(b[arm])-Math.abs(a[arm]);}).slice(0,5);
    return '<article class="ck-visual-arm"><header><b>'+(arm==='before'?'청킹 수정 전':'청킹 수정 후')+'</b><span>'+(kind==='sp'?'SPLADE 점수 ':'dense 코사인 ')+scores[field].toFixed(4)+'</span></header><h3>'+(kind==='sp'?'질문을 이렇게 바꿔서 찾았습니다 (SPLADE)':'질문의 어느 단어가 이 청크와 가깝게 만들었나 (근사)')+'</h3><div class="ck-heat '+kind+'">'+terms.map(function(t){var v=t[arm];return '<span class="'+(v<0?'negative':'')+'" style="--heat-alpha:'+(.12+.73*Math.abs(v)/max).toFixed(3)+'" title="기여 '+v.toFixed(4)+'">'+esc(t.token||t.word)+'</span>';}).join('')+'</div><h3>'+(kind==='sp'?'비교 대상 청크 · 본문과 단어별 기여':'이 청크의 본문 — 질문과의 유사도에 기여한 부분 (근사)')+'</h3><div class="ck-result-body"><div class="ck-result-meta"><b>#'+esc(row.e[arm].id.split('#').pop())+'</b><span>대상 문서 근거 반환: '+ckRank(scores.returnedRanks[idx])+'</span></div><p class="cap">'+esc(row.e[arm].path.join(' → '))+'</p><div class="ck-attributed-body">'+body(arm)+'</div><div class="ck-term-summary">'+top.map(function(t){return '<span>'+esc(t.token||t.word)+' <b>'+t[arm].toFixed(3)+'</b></span>';}).join('')+'</div></div>' +(kind==='dn'?'<p class="ck-legend">진할수록 이 구간을 빼면 유사도가 더 떨어집니다 (6어절 단위). 붉은색은 빼면 유사도가 오르는 구간입니다.</p>'+bodyTop(arm):'')+'</article>';
  }).join('')+'</div><p class="note">'+(kind==='sp'?'보라색은 질문의 확장 토큰 기여, 노란색은 그 토큰이 본문에 직접 등장한 위치입니다. 확장 토큰은 본문에 없어도 점수에 기여할 수 있습니다.':'질문 색 농도는 어절 삭제 실험값입니다. 본문은 질문별 화면과 동일하게 6어절 구간을 하나씩 빼고 재임베딩한 영향도입니다. 전·후에 같은 색 눈금을 적용합니다. 각 값은 근사치이며 합산되지 않습니다.')+'</p>';
}
function ckPanel(row){
  if(CK.tab==='return')return ckReturn(row);
  if(CK.tab==='body')return ckBodies(row,true)+'<div class="ck-explanation"><b>무엇이 바뀌었나</b><p>'+esc(row.e.change)+'</p><p>'+esc(row.e.benefit.replace('검색 순위 향상은 측정하지 않았습니다.','점수와 반환 변화는 아래 추가 측정에서 확인합니다.'))+'</p><a href="'+row.e.url+'" target="_blank" rel="noopener">Git 변경 기록 보기</a></div>';
  var kind=CK.tab==='dn'?'dn':'sp',segment=row.m.changedSegment;
  return ckScoreCards(row,kind)+ckVisualCompare(row,kind)+ckBars(row,kind);
}
function ckDetail(){
  var selection=ckSelected(),el=document.getElementById('detail');
  if(!selection){el.innerHTML='<div class="wrap"><h1>청킹 결과</h1><p>조건에 맞는 청킹 변경이 없습니다.</p></div>';return;}
  var g=selection.g,row=selection.row,m=row.m,improved=g.rows.filter(function(r){return ckEffect(r)>0;}),sorted=g.rows.slice().sort(function(a,b){return ckEffect(b)-ckEffect(a)||a.x.i.localeCompare(b.x.i);});
  el.innerHTML='<div class="wrap ck"><div class="kicker">법령·고시 · 청킹 결과</div><h1>어떤 청킹 변경이 검색을 개선했나</h1><section class="ck-group-detail"><div class="kicker">'+esc(g.date.slice(0,10))+' · '+esc(g.commit)+'</div><h2>'+esc(g.title)+'</h2><div class="ck-process"><div><b>이전 문제</b><p>'+esc(row.e.problem)+'</p></div><div><b>청킹 수정</b><p>'+esc(row.e.change)+'</p></div><div><b>확인 결과</b><p>질문 '+g.rows.length+'개 중 Hybrid 개선 '+g.gain+'개 · 동일 '+(g.rows.length-g.gain-g.loss)+'개 · 악화 '+g.loss+'개</p></div></div><h3>이 청킹으로 검색이 나아진 질문</h3><div class="ck-successes">'+(improved.length?improved.map(function(r){return '<button type="button" data-ck-q="'+r.x.i+'" aria-pressed="'+(r.x.i===CK.qid)+'"><b>'+r.x.i+'</b><span>'+esc(r.x.q)+'</span><small>Hybrid '+ckChange(r.m.globalBefore.returnedRanks[2],r.m.globalAfter.returnedRanks[2])+'</small></button>';}).join(''):'<p class="note">질문 전체의 Hybrid 반환 개선은 없었습니다. 아래에서 점수·구조 변화와 다른 검색기의 결과를 확인할 수 있습니다.</p>')+'</div><details class="ck-all-questions"'+(g.rows.length<=6?' open':'')+'><summary>영향을 받은 모든 질문 '+g.rows.length+'개 보기 · 동일·악화 포함</summary><div class="ck-table-wrap"><table class="ck-table"><thead><tr><th>질문</th><th>내용</th><th>질문 전체 Hybrid</th><th>dense 변화</th><th>SPLADE 변화</th></tr></thead><tbody>'+sorted.map(function(r){return '<tr'+(r.x.i===CK.qid?' class="selected"':'')+'><td><button type="button" data-ck-q="'+r.x.i+'">'+r.x.i+'</button></td><td>'+esc(r.x.q)+'</td><td>'+ckChange(r.m.globalBefore.returnedRanks[2],r.m.globalAfter.returnedRanks[2])+'</td><td>'+r.m.delta.denseCosine.toFixed(4)+'</td><td>'+r.m.delta.spladeScore.toFixed(4)+'</td></tr>';}).join('')+'</tbody></table></div></details></section><section class="ck-question"><div class="kicker">선택한 질문 · '+row.x.i+'</div><p class="q">'+esc(row.x.q)+'</p><div class="ck-outcome '+(ckEffect(row)>0?'positive':ckEffect(row)<0?'negative':'')+'"><b>질문 전체 Hybrid: '+ckChange(m.globalBefore.returnedRanks[2],m.globalAfter.returnedRanks[2])+'</b><span>'+esc(row.e.benefit.replace('검색 순위 향상은 측정하지 않았습니다.','점수와 반환 변화는 아래 추가 측정에서 확인합니다.'))+'</span></div><div class="tabs" role="tablist" aria-label="청킹 영향도">'+[['sp','SPLADE 영향도'],['dn','벡터 영향도'],['body','청크 전후'],['return','반환 비교']].map(function(t){return '<button type="button" role="tab" data-ck-tab="'+t[0]+'" aria-selected="'+(CK.tab===t[0])+'">'+t[1]+'</button>';}).join('')+'</div><div class="ck-panel" role="tabpanel">'+ckPanel(row)+'</div></section><p class="cap">현재 모델과 배경 문서를 고정한 오프라인 비교입니다. 정확한 코사인·희소 내적으로 계산했으며 운영 ANN 재색인·LLM 답변 평가는 포함하지 않았습니다. 111·125·143은 단위까지 있어야 근거 충족으로 셉니다.</p></div>';
}
function renderChunking(){ckSelected();ckList();ckDetail();document.getElementById('detail').scrollTop=0;}
function ckInit(){
  document.getElementById('list').addEventListener('click',function(e){if(st.view!=='ck')return;var f=e.target.closest('[data-ck-filter]'),g=e.target.closest('[data-ck-group]');if(f){CK.filter=f.dataset.ckFilter;renderChunking();ckSetHash();}else if(g){CK.group=g.dataset.ckGroup;CK.qid=null;renderChunking();ckSetHash();}});
  document.getElementById('list').addEventListener('input',function(e){if(st.view!=='ck'||e.target.id!=='ck-search')return;CK.search=e.target.value;var start=e.target.selectionStart;renderChunking();var input=document.getElementById('ck-search');input.focus();input.setSelectionRange(start,start);});
  document.getElementById('detail').addEventListener('click',function(e){if(st.view!=='ck')return;var q=e.target.closest('[data-ck-q]'),t=e.target.closest('[data-ck-tab]');if(q){CK.qid=q.dataset.ckQ;ckDetail();ckSetHash();document.querySelector('.ck-question').scrollIntoView({block:'start'});}else if(t){CK.tab=t.dataset.ckTab;var scroll=this.scrollTop;ckDetail();this.scrollTop=scroll;}});
}
