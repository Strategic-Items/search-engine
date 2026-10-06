var Q = window.QDATA;
var SG = window.SDATA;
var WEAK = ["수","있","무엇","관하","작","받","조","것","하"];
var FEAT = {"docs-v2-001":"A","docs-v2-121":"B","docs-v2-128":"C"};
var WHO = {both:"키워드·dense 모두 상위 5", kw:"키워드만 상위 5", vec:"dense만 상위 5", none:"둘 다 상위 5 밖", na:"무응답 대상"};
var st = {view:"q", stage:"s13", hit:"all", who:"all", cat:"all", stg:"all", txt:"", id:null, tab:"kw", chunk:null};
function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function hl(s){ return esc(s).replace(/&lt;&lt;/g,"<mark>").replace(/&gt;&gt;/g,"</mark>"); }
function tidy(s){ return String(s).replace(/<br\s*\/?>/gi," ").replace(/\\[*_]/g,"").replace(/\*\*/g,"").replace(/^#+\s*/g,"").replace(/\s#{1,4}\s/g," ").replace(/\|/g," ").replace(/-{3,}/g," ").replace(/\s+/g," ").trim(); }
function goldIn(l){ return l.some(function(h){return h.g;}); }
var EMPTY_ANS="문의하신 내용에 대해 확인 가능한 근거 자료를 찾지 못했습니다.\n정확한 확인을 위해 전략물자관리시스템(yesTrade)의 전문판정 신청을 이용해 주시기 바랍니다.";
Q.forEach(function(q){ q.na=(q.cat==="unanswerable"||q.cat==="out_of_domain"); var j=q.j||{}; q.gate=!!j.e; q.jrej=(j.a===false); q.blocked=q.gate||q.jrej; if(q.na) q.hit=q.blocked?1:0; });
Q.forEach(function(q){ var k=goldIn(q.kw), v=goldIn(q.vec); q.who = q.na?"na":k&&v?"both":k?"kw":v?"vec":"none"; q.gi = q.fz.findIndex(function(r){return r.g;}); });
