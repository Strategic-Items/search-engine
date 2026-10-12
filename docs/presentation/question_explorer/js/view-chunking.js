/* 검증된 청킹 작업을 단계별로 보여준다. */
var CK={stageId:"stage-03"};
function ckStages(){return window.CATEGORY_CHUNKING_STAGES||[];}
function ckSelected(){return ckStages().find(function(s){return s.id===CK.stageId;})||ckStages()[ckStages().length-1]||null;}
function ckSetHash(){var s=ckSelected();if(s)location.hash="cat-chunking-"+s.id;}
function ckReadHash(hash){
  if(hash==="cat-chunking"){CK.stageId="stage-03";return true;}
  if(hash.indexOf("cat-chunking-")!==0)return false;
  var id=hash.slice("cat-chunking-".length);
  /* 이전 질문별 변경 링크도 청킹 단계 화면으로 열리게 한다. */
  CK.stageId=ckStages().some(function(s){return s.id===id;})?id:"stage-02";
  return true;
}
function ckList(){
  var stages=ckStages();
  document.getElementById("list").innerHTML='<div class="ck-controls"><p class="cap">청킹 단계 '+stages.length+'개 · 법령·고시 및 행정·업무</p></div>'+stages.map(function(s){
    return '<button type="button" class="item ck-stage-item" role="option" data-ck-stage="'+s.id+'"'+(s.id===CK.stageId?' aria-current="true"':'')+'><span class="dot"></span><span><span class="meta">'+s.number+'단계 · '+s.date+'</span><span class="txt">'+esc(s.title)+'</span><span class="ck-group-count">'+esc(s.status)+'</span></span></button>';
  }).join("");
}
function ckDetail(){
  var s=ckSelected(),el=document.getElementById("detail");
  if(!s){el.innerHTML='<div class="wrap ck"><h1>청킹 단계</h1><p>기록된 단계가 없습니다.</p></div>';return;}
  var example=((window.CATEGORY_CHUNKING_EXAMPLES||{})[s.exampleKey]||null);
  function tableHtml(columns,rows,highlight,changedHeaders){
    return '<table class="ck-visible-table"><thead><tr>'+columns.map(function(c,i){return '<th scope="col"'+(changedHeaders&&changedHeaders[i]?' class="ck-recovered-header"':'')+'>'+esc(c||'(원문 빈칸)')+'</th>';}).join('')+'</tr></thead><tbody>'+rows.map(function(row,i){return '<tr'+(highlight&&i===0?' class="ck-selected-row"':'')+'>'+row.map(function(v){return '<td>'+esc(v)+'</td>';}).join('')+'</tr>';}).join('')+'</tbody></table>';
  }
  function chunkBlock(c,label){
    if(c.table_example){
      var changed=!!c.table_context_after;
      var note=changed?'<div class="ck-added-note"><span class="ck-added-label">＋ 새로 추가된 표 주석</span><p>'+esc(c.table_context_after)+'</p></div>':'<div class="ck-missing-note"><b>표 주석이 청크에 없음</b><p>행의 값만 검색에 사용됩니다.</p></div>';
      var headersChanged=example.headerChange&&label!=="수정 전";
      if(example.headerChange){
        note=headersChanged?'<div class="ck-added-note"><span class="ck-added-label">원문에서 복구한 열 이름</span><p>'+c.columns.map(function(name,i){return name!==example.before.columns[i]?esc(example.before.columns[i])+' → '+esc(name):'';}).filter(Boolean).join('<br>')+'</p></div><p class="ck-source-hint">열1은 그대로 유지합니다. 원문에 제목이 없어 이름을 추측하지 않습니다.</p>':'<div class="ck-missing-note"><b>실제 열 제목을 인식하지 못함</b><p>국문·영문 머리글도 데이터 행으로 취급했습니다.</p></div>';
      }
      var changedColumns=headersChanged?c.columns.map(function(name,i){return name!==example.before.columns[i];}):null;
      return '<article class="ck-table-example"><div class="ck-example-title"><h3>'+label+'</h3><span>청크 #'+esc(c.id.split('#').pop())+'</span></div><p class="ck-row-caption">저장된 행 위치 '+(c.row_index+1)+' / '+c.row_count+' · 같은 데이터 행 비교</p>'+tableHtml(c.columns,[c.row_values],false,changedColumns)+note+'<details class="ck-raw-chunk"><summary>저장된 본문·메타데이터 확인</summary><pre>'+esc(c.body)+'</pre><p>열 이름: '+esc(c.columns.join(' / '))+'<br>행 위치: '+(c.row_index+1)+' / '+c.row_count+'<br>표 뒤 주석: '+esc(c.table_context_after||'없음')+'</p></details></article>';
    }
    return '<article><h3>'+label+' · '+esc(c.id.split('#').pop())+'</h3><p class="cap">경로: '+esc((c.heading_path||[]).join(' → ')||'제목 경로 없음')+'</p><pre>'+esc(c.body)+'</pre></article>';
  }
  var source=example&&example.sourceTable;
  var sourceMarkup=source?'<section class="ck-original-table"><h3>① 원본 표</h3><p class="ck-source-title">'+esc(source.title)+'</p><p class="ck-source-hint">전체 '+source.rows.length+'행 중 앞 3행입니다. 첫 번째 데이터 행을 아래에서 비교합니다.</p>'+tableHtml(source.columns,source.rows.slice(0,3),true)+'<p class="ck-source-note">'+esc(source.note)+'</p><details class="ck-full-table"><summary>원본 표 전체 '+source.rows.length+'행 펼쳐보기</summary>'+tableHtml(source.columns,source.rows,false)+'</details></section><h3 class="ck-compare-heading">② 같은 데이터 행의 전후 청크</h3>':'';
  var originalMd=example&&example.sourceMarkdownPath?'<details class="ck-source-md" data-md-path="'+esc(example.sourceMarkdownPath)+'" open><summary>청킹 입력 원문 Markdown 전문 · '+esc(example.sourceMarkdownName||"원문.md")+'</summary><p><a href="'+esc(example.sourceMarkdownPath)+'" target="_blank" rel="noopener">원문 Markdown 파일 열기</a> · TextBundle <code>'+esc(example.sourceBundle||"")+'</code></p><pre data-md-content>원문 Markdown을 불러오는 중…</pre></details>':'';
  var exampleMarkup=example?sourceMarkup+(example.summary?'<p class="ck-example-summary">'+esc(example.summary)+'</p>':'')+'<div class="ck-two ck-stage-examples">'+chunkBlock(example.before,"수정 전")+example.after.map(function(c,i){return chunkBlock(c,example.after.length===1?"수정 후":"수정 후 청크 "+i);}).join("")+'</div>':'<div class="ck-two ck-stage-examples"><article><h3>변경 전</h3><pre>'+esc(s.before)+'</pre></article><article><h3>변경 후</h3><pre>'+esc(s.after)+'</pre></article></div>';
  var metrics=s.metrics.map(function(m){return '<article class="ck-stage-metric"><span>'+esc(m.label)+'</span><b>'+esc(m.value)+'</b><p>'+esc(m.note)+'</p></article>';}).join("");
  el.innerHTML='<div class="wrap ck"><div class="kicker">법령·고시 · 행정·업무 · 청킹 단계 '+s.number+'</div><h1>청킹 변경 단계</h1><section class="ck-group-detail"><div class="kicker">'+esc(s.date)+' · '+esc(s.status)+'</div><h2>'+esc(s.title)+'</h2><div class="ck-process"><div><b>이전 문제</b><p>'+esc(s.problem)+'</p></div><div><b>청킹 수정</b><p>'+esc(s.change)+'</p></div><div><b>확인 결과</b><p>'+esc(s.result)+'</p></div></div><h3>'+(example?(example.sourceMarkdownPath?'원문 Markdown과 실제 전후 청크 전체':'실제 표로 보는 변경 내용'):'전후 구조')+'</h3>'+originalMd+exampleMarkup+'<h3>평가 결과</h3><div class="ck-stage-metrics">'+metrics+'</div><p class="note">'+esc(s.note)+'</p><details class="ck-source-md" data-md-path="'+esc(s.mdPath)+'"><summary>단계 평가 기록 Markdown 보기 · '+esc(s.mdPath.split("/").pop())+'</summary><p><a href="'+esc(s.mdPath)+'" target="_blank" rel="noopener">Markdown 파일을 새 탭에서 열기</a></p><pre data-md-content>원문을 불러오는 중…</pre></details></section></div>';
}
function renderChunking(){var s=ckSelected();if(s)CK.stageId=s.id;ckList();ckDetail();document.getElementById("detail").scrollTop=0;}
function ckInit(){
  document.getElementById("list").addEventListener("click",function(e){
    if(st.view!=="ck")return;
    var item=e.target.closest("[data-ck-stage]");
    if(item){CK.stageId=item.dataset.ckStage;renderChunking();ckSetHash();}
  });
  document.getElementById("detail").addEventListener("toggle",function(e){
    var box=e.target;
    if(!box.matches("details.ck-source-md[open]")||box.dataset.loaded)return;
    box.dataset.loaded="1";
    fetch(box.dataset.mdPath).then(function(r){if(!r.ok)throw new Error("HTTP "+r.status);return r.text();}).then(function(text){box.querySelector("[data-md-content]").textContent=text;}).catch(function(){box.querySelector("[data-md-content]").textContent="Markdown 원문을 불러오지 못했습니다. 위 링크로 파일을 열어 확인하세요.";});
  },true);
}
