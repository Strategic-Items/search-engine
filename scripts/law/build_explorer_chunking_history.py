"""Build per-question chunking evidence from the Git audit (no inferred search ranks).

Run audit_chunking_history.py first. Parser checkout is the sibling repository.
Evidence retains full bodies; the UI shows excerpts with the complete text expandable.
"""
import difflib
import json
import subprocess
from collections import Counter
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARSER = ROOT.parent / 'unstructured-doc-parser_ver2'
DATA = ROOT / 'docs/presentation/question_explorer/data'
SOURCE = ROOT / 'data/generated/chunking-history/audit.json'
# A change to a relevant evidence chunk is evidence of structure improvement,
# not proof that retrieval improved. Summaries name the exact parser rule.
RULES = {
 'b0db313': ('행정 문서 제목·목록 경계 개선', '행정 문서의 개조식 절 제목과 목록 단계가 근거 경로에 제대로 반영되지 않았습니다.', '행정·업무 구조 규칙과 목록 접두를 정리했습니다.', '개조식 문서의 절 제목과 항목 문맥을 유지합니다.'),
 '7d9cdee': ('별표 소속·제목 복구', '별표의 소속 규정과 사람이 읽을 제목을 구분하기 어려웠습니다.', '별표의 부모 규정과 표지 제목을 복구했습니다.', '근거 청크의 별표·문서 제목을 구분할 수 있습니다.'),
 'e2b2fb9': ('별표 표지 경로 정리', '별표 표지가 근거 경로에 충분히 반영되지 않았습니다.', '별표 표지 인식과 경로를 보강했습니다.', '별표의 소속 문맥을 근거 경로에 유지합니다. 판 연결 메타데이터 변화는 청킹 성과에 포함하지 않습니다.'),
 'a1b9ecb': ('겹쳐 인쇄된 제목 반복 제거', '무형이전 FAQ의 제목 글자가 같은 자리에서 반복돼 추출됐습니다.', '거의 같은 자리에 겹친 동일 글자를 한 번만 읽도록 수정했습니다.', '반복된 제목 글자가 한 번만 남아 문서 제목 문맥을 읽을 수 있습니다.'),
 'f2131ca': ('조문 맥락 복구', '조문 중간의 목록·표 칸 조각에 편·장·절·조 제목이 빠졌습니다.', '조각 시작 위치의 조문 제목을 heading_path에 유지했습니다.', '조문 제목으로 근거의 소속을 확인할 수 있습니다. 조문 맥락 없는 목록 3→0, 조문 경로 없는 칸 조각 40→0.'),
 'c80cda3': ('PDF 낱말·빈 서식 경계 수정', 'PDF 줄바꿈에 낱말이 끊기거나 빈 서식이 작은 청크로 나뉘었습니다.', '낱말 중간 줄바꿈을 결합하고 빈 서식의 경계를 정리했습니다.', '본문·서식의 문맥과 낱말을 함께 읽을 수 있습니다.'),
 '127b4d8': ('절 제목·조문 인용 경계 수정', '무번호 절 제목을 놓치거나 본문에서 인용한 조문을 새 조문으로 오인했습니다.', '형제 절 제목과 본문 인용을 구분하고 제목 조각을 결합했습니다.', '근거가 실제 소속 절·조문 경로에 놓이도록 구조가 바뀌었습니다.'),
 '9c9f994': ('신구대비표를 조문 쌍으로 청킹', '현행·개정안이 섞이거나 페이지 경계에서 대비 내용이 끊겼습니다.', '대비표를 조문 쌍으로 묶고 이어지는 표를 연결했습니다.', '같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다.'),
 '6af69aa': ('작은 대비표도 조문 쌍으로 분리', '작은 대비표의 현행·개정안이 한 표 청크에 섞였습니다.', '작은 표에도 조문 쌍 분리 규칙을 적용했습니다.', '열별 조문 내용을 구분하여 비교할 수 있습니다.'),
 '9cc9c54': ('표 행·각주·부속 경계 복구', 'PDF 표의 여러 품목이 한 행에 뭉치거나 각주와 행이 분리되고 부칙 경로가 붙었습니다.', '첫 열의 키로 행을 나누고 표식 각주를 연결하며 부속 표지에서 제목 경로를 닫았습니다.', '통제번호·조건·설명을 해당 행에서 읽을 수 있습니다. 2017 세부지침 27→44청크, 파서 탈락→통과, 잘못된 부칙 경로 129→0.'),
 'e1749ca': ('표 전체 각주를 행에 연결', '사전신고 시 보고 생략 조건이 별도 각주 청크에만 있어 검색이 답을 놓쳤습니다.', '※※ 표 전체 주석을 적용되는 표 행 끝에도 포함했습니다.', '조건과 생략 예외가 한 청크에 들어갑니다. 관련 표 행 44개 변경.'),
 'bb75fbf': ('품목 키·이어지는 표·일반기준 분리', '통제번호가 빈 행과 긴 조각에서 키가 빠지고 열 이름이 열1·열2로 남았습니다.', '빈 키 행을 앞 행에 잇고 조각에 키를 반복하며 머리글을 상속하고 일반기준을 본문으로 분리했습니다.', '2010 대비표: 열N 45→0, 통제번호 없는 청크 43→1. 대비표·과태료 별표 2문서 파서 탈락→통과.'),
 '709767e': ('부칙 뒤 붙임의 제목 경로 복구', '부칙 뒤 붙임 표에 제목 경로가 비거나 같은 이름의 문서를 구분하기 어려웠습니다.', '붙임 표의 소속 제목을 복구하고 문서 제목을 구분했습니다.', '표의 근거를 붙임·문서 경로로 구분할 수 있습니다.'),
 '694d713': ('개정문·서식·넘친 칸 경계 복구', '개정고시안의 구조·서식 표·칸 밖 글자가 올바른 경계로 들어가지 않았습니다.', '개정문 구조를 인식하고 서식 표와 넘친 칸 글자의 경계를 보정했습니다.', '근거 본문과 서식의 소속 구조가 복구됐습니다.'),
 '26a43bf': ('법령정보센터 별표 표지 복구', '■ 법령명 [별표 N] 머리 줄이 별표 표지로 인식되지 않았습니다.', '머리 줄을 별표 표지로 인식하여 청크 경로에 넣었습니다.', '근거가 어느 법령·별표에 속하는지 확인할 수 있습니다.'),
 '07d383c': ('개정문 머리·제목 판 경계 수정', '개정문 머리와 선으로 나눈 표·판 제목이 본문 구조와 섞였습니다.', '개정문 머리, 가로 전체 표, 제목 판을 구분했습니다.', '판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다.'),
 'e117272': ('HWP 박스 안 표 복원', '한 칸 박스 안의 표 구조를 읽지 못했습니다.', 'HWP 레코드에서 박스 안 표를 읽어 행과 열로 복원했습니다.', '박스에 든 표의 근거를 표 구조와 함께 읽을 수 있습니다.'),
 '582b5b9': ('첫 섹션의 짧은 앞머리 유지', '첫 섹션 앞의 짧은 문맥이 별도 청크로 떨어졌습니다.', '150자 이하 앞머리를 첫 섹션 청크 앞에 붙였습니다.', '첫 섹션의 근거와 앞 문맥을 함께 가져올 수 있습니다.'),
 'e400e04': ('단위·머리글·목록·내용 유실 복구', '숫자의 단위·다단 머리글·목록 구역이 분리되거나 CAS·FAQ 앞부분이 유실됐습니다.', '행마다 단위와 구역을 넣고 머리글·이어지는 행·칸 줄바꿈을 복구했으며 덮어쓰기 버그를 고쳤습니다.', '단위·구역·목록 경계와 누락된 값을 근거 청크에 보존합니다. 원문 숫자 값 약 18,300개 유실 0.'),
}


@lru_cache(maxsize=None)
def git(rev, path):
 return subprocess.check_output(['git', '-C', str(PARSER), 'show', rev+':'+path], text=True)


def main():
 audit = json.loads(SOURCE.read_text())
 groups = {}
 excluded = []
 for item in audit:
  rev, qid, category = item['commit'], item['qid'], item['set']
  if rev not in RULES or (rev == 'e1749ca' and qid != '033'):
   excluded.append(item); continue
  # Re-chunking changes ordinal IDs. Match old evidence by body similarity,
  # rather than showing an unrelated old row with the same chunk ordinal.
  label = {'law100':'01_법령고시','admin30':'02_행정업무','faq30':'03_민원FAQ'}[category]
  old = [json.loads(l) for l in git(rev+'^',f'data/category_chunks/{label}/docs.jsonl').splitlines()]
  candidates = [c for c in old if c['parent_id'] == item['after']['id'].rsplit('#',1)[0]]
  if candidates:
   chosen = max(candidates, key=lambda c: difflib.SequenceMatcher(None,c['body'][:6000],item['after']['body'][:6000],autojunk=True).ratio())
   item['before'] = {'id':chosen['id'],'body':chosen['body'],'path':chosen.get('heading_path',[])}
  if item['before']['body'] == item['after']['body'] and item['before']['path'] == item['after']['path']:
   excluded.append(item); continue
  title, problem, change, benefit = RULES[rev]
  if rev=='9cc9c54' and qid in ['014','032','040','058']:
   title='표의 조건 계층·표식 각주 연결'
   problem='특례 조건이 같은 열 이름으로 반복되고 적용 각주가 행과 분리됐습니다.'
   change='조건을 상위 > 하위로 묶고 같은 표식의 각주를 해당 행에 붙였습니다.'
   benefit='수출 대상·지역·등급과 각주 조건을 한 행에서 읽을 수 있습니다.'
  if rev=='9cc9c54' and qid in ['038','039','068','082','089','094']:
   title='통제번호별 행 분리와 부칙 경로 제거'
   problem='쪽 전체의 여러 통제번호가 한 행에 뭉치고 경로가 제1조(시행일)로 붙었습니다.'
   change='첫 칸 키를 기준으로 행을 나누고 부칙 뒤 붙임 경로를 분리했습니다.'
   benefit='각 통제번호와 그 해설이 같은 행 청크에 놓입니다. 2017 세부지침 27→44청크, 파서 탈락→통과.'
  if rev=='e400e04' and qid in ['111','125','143']:
   title='표 행에 단위·머리글 포함'
   problem='금액·선량 숫자는 행에 있지만 만원·밀리시버트 단위는 다른 청크에 있었습니다.'
   change='행 청크에 단위: 줄을 붙이고 다단 머리글을 의미 있는 열 이름으로 복구했습니다.'
   benefit='숫자와 단위를 함께 읽을 수 있습니다. 125번은 1차·2차·3차 위반 금액의 열 의미도 복구됐습니다.'
  if rev=='e400e04' and qid=='130':
   title='누락 CAS 번호와 화학물질 구역 복구';problem='사린·소만 CAS 번호 2개가 빠지고 첫 구역 설명이 모든 행에 반복됐습니다.';change='값이 둘인 행을 보존하고 각 청크에 실제 물질 구역을 넣었습니다.';benefit='원문 CAS 55개 중 53개→55개 보존, 구역 설명이 해당 물질에 맞게 바뀌었습니다.'
  if rev=='e400e04' and category=='faq30' and qid=='025':
   title='FAQ 답변 첫 조각 복구';problem='긴 답변을 나눌 때 첫 조각이 덮여 답변 앞부분이 사라졌습니다.';change='첫 조각 덮어쓰기를 수정해 엄격한 심사 설명과 고시 제22조 앞부분을 복구했습니다.';benefit='답변의 도입·법적 근거가 다시 청크에 포함됐습니다.'
  if rev=='e400e04' and qid not in ['111','125','130','143','148'] and not (category=='faq30' and qid=='025'):
   title='표 칸의 목록·줄바꿈·머리글 보존';problem='한 칸의 여러 항목이 붙거나 머리글·문맥이 분리됐습니다.';change='칸 줄바꿈과 목록 구분을 보존하고 표의 소속 문맥을 정리했습니다.';benefit='수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다.'
  if rev=='e400e04' and category=='law100' and qid=='103':
   title='관광업소 목록 경계 복구';problem='업소명·주소의 칸 줄바꿈이 사라져 별개 목록 항목이 붙었습니다.';change='HWP 칸 줄바꿈을 보존해 한국의 집과 관광식당을 구분했습니다.';benefit='별개 업소를 한 이름으로 읽는 문제를 줄였습니다. 원본의 이름·주소 줄 수가 달라 잘못된 일대일 짝짓기는 하지 않았습니다. 질문 자체의 대상 범위도 재검토해야 합니다.'
  when=subprocess.check_output(['git','-C',str(PARSER),'show','-s','--format=%aI',rev],text=True).strip()
  phase='before37' if when[:10]<'2026-10-06' else ('before41' if when[:10]=='2026-10-06' else 'after45')
  entry={**item,'title':title,'problem':problem,'change':change,'benefit':benefit,'date':when,'phase':phase,'kind':'structure','rankNote':'수정 전후 검색 재측정 기록 없음 · 구조 개선 확인','url':'https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/'+rev}
  if rev=='e1749ca' and category=='law100' and qid=='033':
   target='01_법령고시-admrul-2100000284150-b0019-00-0d1767c3#0021'
   for label_rev, side in [(rev+'^','before'),(rev,'after')]:
    chunk=next(json.loads(l) for l in git(label_rev,'data/category_chunks/01_법령고시/docs.jsonl').splitlines() if json.loads(l)['id']==target)
    entry[side]={'id':chunk['id'],'body':chunk['body'],'path':chunk.get('heading_path',[])}
   before=git(rev+'^','data/category_chunks/01_법령고시/docs.jsonl')
   foot=next(json.loads(l)['body'] for l in before.splitlines() if json.loads(l)['id']==entry['after']['id'].rsplit('#',1)[0]+'#0022')
   entry.update(kind='retrieval',beforeRanks=[29,16,22],afterRanks=[2,1,1],rankNote='이전 최종 반환에 정답 없음 → 41단계 Hybrid 정답 1위',beforeFootnote=foot,searchUrl='https://github.com/Strategic-Items/search-engine/blob/52708c3/docs/presentation/question_explorer/data/category-detail.js',comparisonNote='이전 50문항과 이후 100문항은 코퍼스·검색 설정이 다릅니다. 청킹만 바꾼 통제 실험은 아닙니다.')
  if rev=='9cc9c54' and qid=='038':
   entry['rankNote']='이전 탐색기 정답 2위 → 이후 1위 · 청크 재분할 후 정답 라벨도 재작성'
   entry['comparisonNote']='52708c3의 50문항 기록은 세 방식 모두 2위, 이후 50문항 기록은 1위입니다. 정답 라벨과 검색 설정도 바뀌었으므로 청킹만의 순위 개선으로 해석하지 않습니다.'
   entry['searchUrl']='https://github.com/Strategic-Items/search-engine/blob/52708c3/docs/presentation/question_explorer/data/categories.js'
  groups.setdefault(category+'-'+qid,[]).append(entry)
 (DATA/'category-chunking-history.js').write_text('/* Git-backed evidence. Candidate/returned ranks and corpus differences are explicit. */\nwindow.CATEGORY_CHUNKING_HISTORY='+json.dumps(groups,ensure_ascii=False,separators=(',',':'))+';\n')
 lines=['# Git 청킹 변경과 질문별 개선 기록','','검색 실패→성공으로 확인된 사례와 구조 개선 기록을 구분한다. 기존 단계 번호는 유지한다. 45단계 이후 수정은 날짜별 추가 기록이다.','','## 확인 범위',f'카테고리 전달물의 비병합 커밋 전체(28개)를 조사했다. 질문 근거가 바뀐 후보 {len(audit)}건 중 관련 전후 변화 {sum(map(len,groups.values()))}건을 {len(groups)}개 질문에 연결했다. 구조 변화만으로 검색 성과를 만들지 않았다.','','## 발표 대표 사례','','- 법령 033: SPLADE 29위·dense 16위·합산 22위, 최종 반환 정답 없음 → 각주 연결 후 41단계 Hybrid 1위. 코퍼스와 설정도 변경됐다.','- 법령 038: 통제번호별 행 분리, 잘못 붙은 부칙 경로 제거. 파서 탈락→통과. 2위→1위 기록에는 라벨 재작성도 포함된다.','- 법령 111·125·143: 표 숫자와 단위를 행에 함께 보존. 검색 수정 후 재측정 없음.','- 법령 130: CAS 53/55→55/55, 물질별 구역 복구. 검색 수정 후 재측정 없음.','- 민원FAQ 025: 덮여 사라진 답변 앞부분 복원. 검색 수정 후 재측정 없음.','','## 질문별 연결','','| 카테고리·질문 | 청킹 변경 | 확인된 개선 | 근거 |','|---|---|---|---|']
 for key,entries in groups.items():
  for e in entries:lines.append('| '+key+' | '+e['title']+' | '+e['benefit']+' '+e['rankNote']+' | ['+e['commit']+']('+e['url']+') |')
 lines+=['','## 별도 질문셋 사례','','37단계 법령 21문항 law-v1-009: 상황허가 조문 제목 복구(f2131ca). 수정 전 BM25 54위·dense 9위·SPLADE 5위·합산 8위. 같은 질문의 수정 후 순위는 저장돼 있지 않아 현재 150문항의 특정 질문에 대신 붙이지 않았다.','','## 유의할 연결','','같은 문서의 다른 행이나 경로가 바뀐 경우는 질문의 직접적인 검색 성공으로 계산하지 않는다. 전후 청크 번호가 달라질 수 있어 본문 유사도로 기존 근거를 연결했다. 전체 후보와 제외 대상은 data/generated/chunking-history에 저장한다.']
 report=ROOT/'docs/evaluation/chunking_history_2026-10-07.md';report.write_text('\n'.join(lines)+'\n')
 (SOURCE.parent/'excluded.json').write_text(json.dumps(excluded,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'questions':len(groups),'records':sum(map(len,groups.values())),'sets':dict(Counter(k.split('-')[0] for k in groups)),'excluded':len(excluded)},ensure_ascii=False))

if __name__=='__main__':main()
