import json,subprocess,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
repo=str(ROOT.parent/'unstructured-doc-parser_ver2')
revs=subprocess.check_output(['git','-C',repo,'log','--all','--no-merges','--reverse','--format=%h','--','data/category_chunks'],text=True).splitlines()
qs={s:[json.loads(l) for l in (ROOT/f).read_text().splitlines() if l] for s,f in [('law100','data/queries_law150_v1.jsonl'),('admin30','data/queries_admin_v1.jsonl'),('faq30','data/queries_faq_v1.jsonl')]}
paths={'law100':'01_법령고시','admin30':'02_행정업무','faq30':'03_민원FAQ'}
def norm(s):return re.sub('[^0-9A-Za-z가-힣]','',re.sub(r'<br\s*/?>',' ',s,flags=re.I)).lower()
cache={}
def chunks(rev,category):
 k=(rev,category)
 if k not in cache:
  p=f'data/category_chunks/{paths[category]}/docs.jsonl'
  r=subprocess.run(['git','-C',repo,'show',rev+':'+p],capture_output=True,text=True)
  cache[k]=[json.loads(l) for l in r.stdout.splitlines()] if r.returncode==0 else []
 return cache[k]
impacts=[]
for rev in revs:
 for cat,questions in qs.items():
  before=chunks(rev+'^',cat);after=chunks(rev,cat)
  bi={c['id']:c for c in before}; ai={c['id']:c for c in after}
  changed={c['parent_id'] for c in after if c['id'] in bi and (c['body'],c.get('heading_path'))!=(bi[c['id']]['body'],bi[c['id']].get('heading_path'))}
  for q in questions:
   parents=set(q.get('gold',[]))&changed
   needles=[norm(p) for p in q['phrases']]
   if not parents:continue
   def relevant(items):return [c for c in items if c['parent_id'] in parents and any(n and n in norm(c['body']) for n in needles)]
   old=relevant(before);new=relevant(after)
   def signature(cs):return sorted((c['body'],tuple(c.get('heading_path',[]))) for c in cs)
   if not old or not new or signature(old)==signature(new):continue
   def complete(cs):return [c for c in cs if all(n in norm(c['body']+' '+' '.join(c.get('heading_path',[]))) for n in needles)]
   hits=[c for c in new if c['id'] in bi and c['body']!=bi[c['id']]['body']]
   sample=next((c for c in hits if all(n in norm(c['body']) for n in needles)),hits[0] if hits else new[0])
   prev=bi.get(sample['id'],old[0])
   impacts.append({'set':cat,'qid':q['qid'].rsplit('-',1)[-1],'query':q['query'],'commit':rev,'parents':sorted(parents),'oldComplete':len(complete(old)),'newComplete':len(complete(new)),'before':{'id':prev['id'],'body':prev['body'],'path':prev.get('heading_path',[])},'after':{'id':sample['id'],'body':sample['body'],'path':sample.get('heading_path',[])}})
output=ROOT/'data/generated/chunking-history'
output.mkdir(parents=True,exist_ok=True)
(output/'commits.json').write_text(json.dumps(revs,ensure_ascii=False,indent=2)+'\n')
(output/'audit.json').write_text(json.dumps(impacts,ensure_ascii=False,indent=2)+'\n')
for rev in revs:
 a=[i for i in impacts if i['commit']==rev];print(rev,len(a),'; '.join(i['set']+':'+i['qid']+'('+str(i['oldComplete'])+'>'+str(i['newComplete'])+')' for i in a))
