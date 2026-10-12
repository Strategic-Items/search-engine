/* 검증된 청킹 작업을 단계별로 보여준다. */
var CK={stageId:"stage-02"};
function ckStages(){return window.CATEGORY_CHUNKING_STAGES||[];}
function ckSelected(){return ckStages().find(function(s){return s.id===CK.stageId;})||ckStages()[ckStages().length-1]||null;}
function ckSetHash(){var s=ckSelected();if(s)location.hash="cat-chunking-"+s.id;}
function ckReadHash(hash){
  if(hash==="cat-chunking"){CK.stageId="stage-02";return true;}
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
  function chunkBlock(c,label){return '<article><h3>'+label+' · '+esc(c.id.split("#").pop())+'</h3><p class="cap">경로: '+esc((c.heading_path||[]).join(" → ")||"제목 경로 없음")+'</p><pre>'+esc(c.body)+'</pre></article>';}
  var originalMd=example&&example.sourceMarkdownPath?'<details class="ck-source-md" data-md-path="'+esc(example.sourceMarkdownPath)+'" open><summary>청킹 입력 원문 Markdown 전문 · '+esc(example.sourceMarkdownName||"원문.md")+'</summary><p><a href="'+esc(example.sourceMarkdownPath)+'" target="_blank" rel="noopener">원문 Markdown 파일 열기</a> · TextBundle <code>'+esc(example.sourceBundle||"")+'</code></p><pre data-md-content>원문 Markdown을 불러오는 중…</pre></details>':'';
  var exampleMarkup=example?'<div class="ck-two ck-stage-examples">'+chunkBlock(example.before,"수정 전")+example.after.map(function(c,i){return chunkBlock(c,"수정 후 청크 "+i);}).join("")+'</div>':'<div class="ck-two ck-stage-examples"><article><h3>변경 전</h3><pre>'+esc(s.before)+'</pre></article><article><h3>변경 후</h3><pre>'+esc(s.after)+'</pre></article></div>';
  var metrics=s.metrics.map(function(m){return '<article class="ck-stage-metric"><span>'+esc(m.label)+'</span><b>'+esc(m.value)+'</b><p>'+esc(m.note)+'</p></article>';}).join("");
  el.innerHTML='<div class="wrap ck"><div class="kicker">법령·고시 · 행정·업무 · 청킹 단계 '+s.number+'</div><h1>청킹 변경 단계</h1><section class="ck-group-detail"><div class="kicker">'+esc(s.date)+' · '+esc(s.status)+'</div><h2>'+esc(s.title)+'</h2><div class="ck-process"><div><b>이전 문제</b><p>'+esc(s.problem)+'</p></div><div><b>청킹 수정</b><p>'+esc(s.change)+'</p></div><div><b>확인 결과</b><p>'+esc(s.result)+'</p></div></div><h3>'+(example?'원문 Markdown과 실제 전후 청크 전체':'전후 구조')+'</h3>'+originalMd+exampleMarkup+'<h3>평가 결과</h3><div class="ck-stage-metrics">'+metrics+'</div><p class="note">'+esc(s.note)+'</p><details class="ck-source-md" data-md-path="'+esc(s.mdPath)+'"><summary>단계 평가 기록 Markdown 보기 · '+esc(s.mdPath.split("/").pop())+'</summary><p><a href="'+esc(s.mdPath)+'" target="_blank" rel="noopener">Markdown 파일을 새 탭에서 열기</a></p><pre data-md-content>원문을 불러오는 중…</pre></details></section></div>';
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
