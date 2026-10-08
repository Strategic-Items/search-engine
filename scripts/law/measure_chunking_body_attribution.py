"""Measure six-word body deletion attribution for law chunking comparisons."""
import json
import re
from pathlib import Path
import numpy as np
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.indexing.law import law_embedding_title
from scripts.law.measure_chunking_impact import load_js, snapshot, norm
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/generated/chunking-impact'
JS=ROOT/'docs/presentation/question_explorer/data/category-chunking-body.js'

def main():
 settings=get_settings();embedder=OllamaEmbedder(settings)
 history=load_js(ROOT/'docs/presentation/question_explorer/data/category-chunking-history.js','window.CATEGORY_CHUNKING_HISTORY=')
 impact=load_js(ROOT/'docs/presentation/question_explorer/data/category-chunking-impact.js','window.CATEGORY_CHUNKING_IMPACT=')
 assert settings.ollama_embedding_model==impact['metadata']['denseModel'], 'Dense model changed; rerun the score comparison first'
 queries={q['qid'].rsplit('-',1)[-1]:q['query'] for q in map(json.loads,(ROOT/'data/queries_law150_v1.jsonl').read_text().splitlines())}
 cache={}
 for path in OUT.glob('vectors-*.json'):cache.update(json.loads(path.read_text())['dense'])
 path=OUT/'body-vectors.json'
 if path.exists():cache.update(json.loads(path.read_text()))
 extra=json.loads(path.read_text()) if path.exists() else {};results={};jobs=[]
 for key,entries in history.items():
  if not key.startswith('law100-'):continue
  query=queries[key.rsplit('-',1)[-1]]
  for e in entries:
   result={};results.setdefault(key,{})[e['commit']]=result
   for arm,rev in [('before',e['commit']+'^'),('after',e['commit'])]:
    row=next(r for r in snapshot(rev,'law100') if r['id']==e[arm]['id'])
    # Preserve whitespace and the exact model input when deleting a segment.
    title=law_embedding_title(row) if impact['metadata']['denseHeadingPath'] else row['title']
    body=row['body'];words=list(re.finditer(r'\S+',body));segments=[]
    for start in range(0,len(words),6):
     a=words[start].start();b=words[min(start+5,len(words)-1)].end()
     if start==0:a=0
     if start+6>=len(words):b=len(body)
     else:b=words[start+6].start()
     segments.append((body[a:b],embedding_text(title,body[:a]+body[b:])))
    base=embedding_text(title,body)
    result[arm]=[];jobs.append((query,base,segments,result[arm]))
 missing=sorted({t for q,b,segs,_ in jobs for t in [q,b]+[t for _,t in segs]}-cache.keys())
 print('Pending body embeddings',len(missing),flush=True)
 for i in range(0,len(missing),16):
  batch=missing[i:i+16];vectors=embedder.embed(batch);cache.update(zip(batch,vectors));extra.update(zip(batch,vectors))
  if i%160==0:
   print('Encoded',min(i+16,len(missing)),'/',len(missing),flush=True)
   path.write_text(json.dumps(extra,separators=(',',':')))
 path.write_text(json.dumps(extra,separators=(',',':')))
 for query,base,segs,target in jobs:
  q=norm(cache[query]);score=float(q@norm(cache[base]))
  target.extend([[text,score-float(q@norm(cache[t]))] for text,t in segs])
 JS.write_text('window.CATEGORY_CHUNKING_BODY='+json.dumps(results,ensure_ascii=False,separators=(',',':'))+';\n')
 print('Completed',len(jobs),'before/after bodies',flush=True)
if __name__=='__main__':main()
