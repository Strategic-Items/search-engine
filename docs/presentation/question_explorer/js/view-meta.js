function panelMeta(){
  var Y='<td class="y">●</td>', N='<td class="n">–</td>';
  function row(f,desc,ex,fl,bo,rs,pr,note){ return '<tr><td><code>'+f+'</code></td><td>'+desc+'</td><td>'+ex+'</td>'+(fl?Y:N)+(bo?Y:N)+(rs?Y:N)+(pr?Y:N)+'<td>'+note+'</td></tr>'; }
  return '<div class="em">'+
  '<p class="note" id="mt-flow">청크마다 붙은 메타데이터가 검색의 어느 지점에서 쓰이는지 정리했습니다. 코드는 <code>query.py</code>·<code>indexer.py</code>·<code>guardrail.py</code>, 수치는 지금 떠 있는 색인에서 센 값입니다.</p>'+
  '<div class="steps">'+
    '<div class="step"><b>① 색인할 때</b>같은 제목·발행일 사본은 먼저 오른 1개만 남김. 본문 앞머리에서 <code>period_hint</code>를 계산해 붙임</div>'+
    '<div class="step kw"><b>② 필터</b>유효기간(시행일·종료일)과 공고번호로 후보를 먼저 거름. 키워드·dense 둘 다 같은 조건</div>'+
    '<div class="step kw"><b>③ 가산점</b>BM25 점수에 현행판 +4, 질문의 연·월과 일치하면 +6 / +4를 더함</div>'+
    '<div class="step"><b>④ 결과 정리</b>제목·발행일이 같은 사본을 묶고, 옛 판 뒤에 현행 문서를 붙임</div>'+
    '<div class="step vec"><b>⑤ 답변 프롬프트</b>유형·제목·시행일·출처·대체 여부를 근거 머리말로 LLM에 전달</div>'+
  '</div>'+

  '<h2 id="mt-fields">필드별로 어디에 쓰이나</h2>'+
  '<table><thead><tr><th>필드</th><th>무슨 값인가</th><th>예</th><th>필터</th><th>가산점</th><th>결과<br>정리</th><th>프롬프트</th><th>쓰임</th></tr></thead><tbody>'+
    row('effective_from','문서가 효력을 갖기 시작하는 날(시행일). 개정 고시처럼 “9.1부터 시행”이 있는 문서에 채워짐','2026-09-01',1,0,0,1,'기준일보다 뒤면 제외. 없으면 통과. 연·월 가산점 대상. 프롬프트에는 “시행일”로, 없으면 “확인 필요”')+
    row('effective_to','문서의 효력이 끝나는 날(종료일). 한시적 안내·기간이 정해진 공고에만 있음','2027-12-31',1,0,0,0,'기준일 이전에 끝났으면 제외. 없으면 통과')+
    row('published_at','게시글이 올라온 날(발행일). 시행일과 다를 수 있음','2026-09-01',0,1,1,0,'연·월 가산점 대상. 사본 묶음 키(제목+발행일)')+
    row('period_hint','발행일이 비었을 때 본문 앞머리에서 읽어 낸 시점의 추정값. 확정된 날짜가 아님','본문 앞머리가 말하는 시점',0,1,0,0,'발행일이 비어 있을 때만 붙는 추정값. 연·월 가산점(+4)에만 쓰고 사본·대체 판정에는 안 씀')+
    row('superseded_by','이 문서를 대체한 다음 판 문서의 ID. 비어 있으면 아직 현행판','다음 판 문서 ID',0,1,1,1,'없으면 현행판 +4. 있으면 옛 판 뒤에 현행 문서를 붙이고 프롬프트에 “대체됨” 표시')+
    row('title (제목 부분)','문서 제목에서 <code>" — "</code> 앞부분. 같은 문서인지 가릴 때 이 부분만 비교함','제38차 전략물자수출입고시 개정 안내',0,0,1,1,'<code>" — "</code> 앞부분을 사본 묶음 키로 씀. 프롬프트 머리말에 들어감')+
    row('source_type','문서가 어느 게시판·종류에서 왔는지(공지사항, FAQ, 민원서식 등)','공지사항 · FAQ · 민원서식',0,0,0,1,'프롬프트 머리말 첫 칸. 검색 점수에는 안 씀')+
    row('source_url','원문 게시글의 인터넷 주소. 답변의 출처 링크가 됨','yestrade 게시글 주소',0,0,0,1,'프롬프트 머리말과 응답에 출처로 표시')+
    row('공고번호 (질문 쪽)','사용자 질문에 적힌 고시·공고 번호. 문서 필드가 아니라 질문에서 읽어 냄','제2026-598호',1,0,0,0,'질문에서 번호를 읽어 제목·본문에 그 번호가 든 청크만 남김. 메타데이터 필드가 아니라 본문과 대조')+
  '</tbody></table>'+
  '<p class="cap">같은 필터는 키워드와 dense 두 검색에 똑같이 걸립니다. dense는 가산점을 줄 수 없어(kNN은 function_score를 못 씀) 유효기간 조건만 중복해서 겁니다.</p>'+

  '<h2 id="mt-filter">필터 · 유효기간과 공고번호</h2>'+
  '<table><thead><tr><th>조건</th><th>통과 규칙</th><th>값이 없을 때</th></tr></thead><tbody>'+
    '<tr><td>시행일</td><td><code>effective_from ≤ 기준일</code></td><td>통과</td></tr>'+
    '<tr><td>종료일</td><td><code>effective_to &gt; 기준일</code></td><td>통과</td></tr>'+
    '<tr><td>공고번호</td><td>질문에 번호가 있으면 제목 또는 본문에 그 번호가 있어야 함</td><td>질문에 번호가 없으면 걸지 않음</td></tr>'+
  '</tbody></table>'+
  '<p class="note">번호는 관련도가 아니라 어느 문서인지를 가리키므로 가산점이 아니라 필터로 둡니다. 임베딩은 네 자리 일련번호를 거의 구별하지 못해 590호와 598호가 코사인으로는 갈리지 않기 때문에 dense에도 같은 필터를 겁니다.</p>'+

  '<h2 id="mt-boost">가산점 · 현행판과 연·월</h2>'+
  '<table><thead><tr><th>조건</th><th>가산점</th><th>대상</th></tr></thead><tbody>'+
    '<tr><td>현행판 (<code>superseded_by</code> 없음)</td><td>+4</td><td>모든 문서에 똑같이. 대체된 옛 판만 상대적으로 낮아짐</td></tr>'+
    '<tr><td>질문의 연·월 = <code>published_at</code> 또는 <code>effective_from</code></td><td>+6</td><td>“2024년 3월” 같은 표현이 있을 때만</td></tr>'+
    '<tr><td>질문의 연·월 = <code>period_hint</code></td><td>+4</td><td>발행일이 비어 추정 날짜만 있는 문서</td></tr>'+
    '<tr><td>날짜를 하나도 모름</td><td>+4</td><td>그 기간이 아니라고 말할 근거가 없으므로, 추정 날짜와 같은 무게</td></tr>'+
  '</tbody></table>'+
  '<p class="cap">연·월이 없는 질문에서는 현행판 +4만 붙고 모두에게 같아 순위에 영향이 없습니다. 연·월 질문에서는 합산 단계에도 제목이 기간과 맞는 후보로 3번째 목록(가중치 1.0)이 추가됩니다.</p>'+

  '<h2 id="mt-clean">결과 정리 · 사본과 대체</h2>'+
  '<p class="note"><b>사본:</b> 같은 법령이 hwp·pdf·hwpx로 세 번 들어오면 파서가 끊는 위치가 달라 <code>content_hash</code>로는 묶이지 않습니다. 그래서 제목(<code>" — "</code> 앞부분)과 발행일이 같으면 먼저 오른 1개만 남깁니다.</p>'+
  '<p class="note"><b>대체:</b> 옛 판이 결과에 올라오면 <code>superseded_by</code>를 따라 현행 문서를 그 바로 뒤에 붙입니다. 38차 개정처럼 문서 이름이 바뀐 경우, 옛 이름으로 검색해도 현행 판에 닿게 하려는 장치입니다. 문서 수 상한(최대 5) 안에서 처리합니다.</p>'+

  '<h2 id="mt-prompt">답변 프롬프트에 들어가는 메타데이터</h2>'+
  '<pre>[<span class="lb">공지사항</span> · 제38차 전략물자수출입고시 개정 안내(9.1 시행) · 시행일 <span class="lb">2026-09-01</span> · 출처 <span class="lb">https://www.yestrade.go.kr/…/23257</span>]\n제38차 전략물자 수출입고시 개정(9.1) 안내 …\n[같은 문서의 다른 부분]\n …</pre>'+
  '<p class="cap">시행일이 없으면 “확인 필요”, 대체된 문서면 <code>· 대체됨: {다음 판 ID}</code>가 붙습니다. 같은 문서의 청크는 <code>[같은 문서의 다른 부분]</code>으로 끊어 이어 읽지 않게 합니다.</p>'+

  '<h2 id="mt-fill">채움률 · 있는 값이 얼마나 되나</h2>'+
  '<table><thead><tr><th>필드</th><th>docs<br>1,198</th><th>core<br>3,956</th><th>법령·고시<br>673</th><th>행정·업무<br>183</th></tr></thead><tbody>'+
    '<tr><td><code>published_at</code></td><td>390 (33%)</td><td>3,714 (94%)</td><td>364 (54%)</td><td>20 (11%)</td></tr>'+
    '<tr><td><code>effective_from</code></td><td>0</td><td>1,904 (48%)</td><td>201 (30%)</td><td>0</td></tr>'+
    '<tr><td><code>effective_to</code></td><td>0</td><td>0</td><td>0</td><td>0</td></tr>'+
    '<tr><td><code>period_hint</code></td><td>0</td><td>0</td><td>25 (4%)</td><td>9 (5%)</td></tr>'+
    '<tr><td><code>superseded_by</code></td><td>0</td><td>1,905 (48%)</td><td>0</td><td>0</td></tr>'+
  '</tbody></table>'+
  '<p class="cap">docs 코퍼스에는 시행일·종료일이 전혀 없어 유효기간 필터가 아무것도 거르지 못하고, 날짜 단서는 발행일 33%뿐입니다. 이 탐색기의 docs 질문에서 메타데이터가 순위를 바꾸는 일은 거의 없습니다. core는 종료일이 한 건도 없고, 시행일과 대체 정보가 절반 가량 있어 현행판 판단이 실제로 작동하는 쪽입니다.</p>'+

  '<h2 id="mt-skip">검색에 쓰지 않는 메타데이터</h2>'+
  '<p class="note">법령·행정 카테고리의 <code>doc_type</code>·<code>doc_status</code>·<code>issuer</code>·<code>doc_number</code>·<code>revision_date</code>·<code>legal_structure</code>는 청크마다 펼쳐 저장하고 응답에도 싣지만, 필터나 점수에는 쓰지 않습니다. 채움률이 낮기 때문입니다(고시 번호 4/20, 시행일 4/20). 있을 때만 맞는 신호로 남겨 둔 상태입니다. <code>code</code>는 <code>codes_exact</code>·<code>code_norm</code>으로 풀어 색인하지만, 읽은 검색 코드에서는 이 필드로 거르거나 점수를 주는 곳을 찾지 못했습니다.</p>'+
  '<p class="note"><b>임베딩과의 관계:</b> dense 벡터는 제목과 본문(법령·행정은 조문 경로 포함)만으로 만들고, 위 메타데이터는 벡터에 반영되지 않습니다. 그래서 날짜·번호는 필터와 가산점이 맡고 벡터는 의미만 맡습니다.</p>'+
  '</div>';
}
function renderMeta(){
  var nav=document.getElementById("stnav"), items=[["mt-flow","전체 흐름"],["mt-fields","필드별 쓰임"],["mt-filter","필터"],["mt-boost","가산점"],["mt-clean","사본·대체 정리"],["mt-prompt","답변 프롬프트"],["mt-fill","채움률"],["mt-skip","쓰지 않는 메타데이터"]];
  nav.innerHTML=items.map(function(x){ return '<button type="button" data-go2="'+x[0]+'"><span class="nl">메타데이터</span><span class="nt">'+x[1]+'</span></button>'; }).join("");
  var el=document.getElementById("detail"); el.innerHTML=panelMeta(); el.scrollTop=0;
}
