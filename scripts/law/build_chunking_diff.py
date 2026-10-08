"""Build exact line-change ranges for before/after chunk display."""
import difflib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=ROOT/'docs/presentation/question_explorer/data/category-chunking-history.js'
s=p.read_text();history=json.JSONDecoder().raw_decode(s[s.index('{'):])[0];out={}
for key,entries in history.items():
 if not key.startswith('law100-'):continue
 for e in entries:
  lines={arm:e[arm]['body'].splitlines(keepends=True) for arm in ['before','after']};ranges={'before':[],'after':[]}
  offsets={arm:[0] for arm in lines}
  for arm in lines:
   for line in lines[arm]:offsets[arm].append(offsets[arm][-1]+len(line))
  for tag,a,b,c,d in difflib.SequenceMatcher(None,lines['before'],lines['after'],autojunk=False).get_opcodes():
   if tag=='equal':continue
   if a<b:ranges['before'].append([offsets['before'][a],offsets['before'][b],'교체 전' if tag=='replace' else '삭제'])
   if c<d:ranges['after'].append([offsets['after'][c],offsets['after'][d],'교체 후' if tag=='replace' else '추가'])
  out.setdefault(key,{})[e['commit']]=ranges
(ROOT/'docs/presentation/question_explorer/data/category-chunking-diff.js').write_text('window.CATEGORY_CHUNKING_DIFF='+json.dumps(out,ensure_ascii=False,separators=(',',':'))+';\n')
