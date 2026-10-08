"""Measure Git chunking changes with fixed encoders and frozen background corpora.

For every linked question/change, replace only the affected parent document with
its Git before/after chunks. Score by exact cosine and sparse dot product, fuse
25+25 candidates with RRF, and apply the explorer's cutoffs and budgets. No live
index or alias is changed. Dense word deletion is an attribution approximation.
"""
import hashlib
import difflib
import json
import re
import subprocess
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np
from opensearchpy.helpers import scan

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.indexing.law import law_embedding_title
from search_engine.sparse import SparseEncoder
from search_engine.search.query import _chunk_first

ROOT = Path(__file__).resolve().parents[2]
PARSER = ROOT.parent / 'unstructured-doc-parser_ver2'
OUT = ROOT / 'data/generated/chunking-impact'
OUT.mkdir(parents=True, exist_ok=True)
SETS = {'law100': ('01_법령고시', 'search-law', 'data/queries_law150_v1.jsonl'),
        'admin30': ('02_행정업무', 'search-admin', 'data/queries_admin_v1.jsonl'),
        'faq30': ('03_민원FAQ', None, 'data/queries_faq_v1.jsonl')}


def load_js(path, prefix):
 text = path.read_text(); start = text.index(prefix) + len(prefix)
 return json.JSONDecoder().raw_decode(text[start:])[0]


@lru_cache(maxsize=None)
def snapshot(rev, category):
 raw = subprocess.check_output(['git','-C',str(PARSER),'show',rev+':data/category_chunks/'+SETS[category][0]+'/docs.jsonl'],text=True)
 return [json.loads(line) for line in raw.splitlines()]


def normalized(s):
 return re.sub(r'[^0-9A-Za-z가-힣]', '', re.sub(r'<br\s*/?>', ' ', s, flags=re.I)).lower()


def norm(v):
 a = np.asarray(v, dtype=np.float32)
 return a / max(float(np.linalg.norm(a)), 1e-12)


def sparse_score(q, d):
 return sum(w * d.get(t, 0) for t, w in q.items())


def keep(order, scores, rows, ratio, leaders=()):
 result=[]; docs=Counter(); top=scores[order[0]] if order else 0
 for i in order:
  if scores[i] < top * ratio and i not in leaders: continue
  parent=rows[i]['parent_id']
  if (parent not in docs and len(docs)>=5) or docs[parent]>=6: continue
  result.append(i);docs[parent]+=1
  if len(result)==10: break
 return result


def required_phrases(q,category,qid):
 phrases=[normalized(p) for p in q['phrases']]
 # Unit restoration must not be graded as a numeric-only answer.
 if category=='law100' and qid in ['125','143']: phrases+=['만원']
 if category=='law100' and qid=='111': phrases+=['밀리시버트']
 return phrases


def complete(row,q,category,qid):
 return all(p in normalized(row['body']) for p in required_phrases(q,category,qid))


def rank_result(rows, sp, dn, foreground, question, category, qid, whole_question=False):
 gold={i for i in foreground if complete(rows[i],question,category,qid)}
 sort=lambda scores:sorted(range(len(rows)),key=lambda i:(-float(scores[i]),rows[i]['id']))
 so,do=sort(sp),sort(dn)
 def rank(order):
  if not whole_question:return next((r for r,i in enumerate(order,1) if i in gold),None)
  requirements=required_phrases(question,category,qid);found=set();parents=set(question.get('gold',[]))
  for pos,i in enumerate(order,1):
   if rows[i]['parent_id'] not in parents:continue
   body=normalized(rows[i]['body']);found.update(j for j,p in enumerate(requirements) if p in body)
   if len(found)==len(requirements):return pos
  return None
 sr={i:r for r,i in enumerate(so[:25],1)};dr={i:r for r,i in enumerate(do[:25],1)}
 fused={i:(1/(60+sr[i]) if i in sr else 0)+(1/(60+dr[i]) if i in dr else 0) for i in set(sr)|set(dr)}
 ho=sorted(fused,key=lambda i:(-fused[i],dr.get(i,10**6),rows[i]['id']))
 hs=np.zeros(len(rows));
 for i,v in fused.items():hs[i]=v
 leaders=set(so[:1]+do[:1])
 index_by_id={row['id']:i for i,row in enumerate(rows)}
 hit=lambda i: {'_id':rows[i]['id'],'_source':rows[i],'_score':float(sp[i])}
 hybrid_groups=_chunk_first([([hit(i) for i in so[:25]],1.0,'splade'),([hit(i) for i in do[:25]],1.0,'vector')],question['query'],rrf_k=60,max_chunks=10,cutoff_ratio=.95,max_documents=5,chunks_per_document=6)
 hybrid_window=[index_by_id[h['_id']] for group in hybrid_groups for h in group]
 windows={'splade':keep(so[:100],sp,rows,.80,so[:1]),'dense':keep(do[:50],dn,rows,.93,do[:1]),'hybrid':hybrid_window}
 return {'candidateRanks':[rank(so),rank(do),rank(ho)],'returnedRanks':[rank(windows[m]) for m in ['splade','dense','hybrid']], 'completeChunks':len(gold), 'window':{m:[rows[i]['id'] for i in order] for m,order in windows.items()}}


def main():
 history=load_js(ROOT/'docs/presentation/question_explorer/data/category-chunking-history.js','window.CATEGORY_CHUNKING_HISTORY=')
 settings=get_settings(); client=create_client(settings)
 embedder=OllamaEmbedder(settings)
 encoder=SparseEncoder(settings)
 metadata={'method':'Affected parent document replaced in fixed current background. Exact dense cosine and sparse dot product; 25+25 RRF k=60; 80%/93%/95% cutoffs; 10 chunks/5 parents/6 per parent.',
   'denseModel':settings.ollama_embedding_model,'spladeModel':settings.search_splade_model,
   'denseHeadingPath':settings.search_dense_include_heading_path,'spladeHeadingPath':settings.search_splade_include_heading_path,
   'docMaxLength':settings.search_splade_doc_max_length,'queryMaxLength':settings.search_splade_query_max_length,
   'topTerms':settings.search_splade_top_terms,'minWeight':settings.search_splade_min_weight,
   'wordAttribution':'Full query cosine minus cosine after deleting one query word; signed, not a percentage.',
   'limits':'Offline exact reranking; no live ANN index rebuild. Only affected parent replaced; other corpus documents fixed. Mandatory phrases plus units on 111/125/143 are graded; current ID-based multi-group labels are not transplanted onto old chunk IDs. No date/number-filter or version-weight change in this experiment.',
   'backgrounds':{}}
 dense_cache={};sparse_cache={}
 def inputs(row):
  title=row['title']
  dt=law_embedding_title(row) if settings.search_dense_include_heading_path else title
  st=law_embedding_title(row) if settings.search_splade_include_heading_path else title
  return embedding_text(dt,row['body']),embedding_text(st,row['body'])
 config_hash=hashlib.sha256(json.dumps(metadata,sort_keys=True).encode()).hexdigest()[:16]
 cache_path=OUT/('vectors-'+config_hash+'.json')
 if cache_path.exists():
  cached=json.loads(cache_path.read_text());dense_cache.update(cached['dense']);sparse_cache.update(cached['sparse'])
 corpora={}; questions={}; foreground={}
 for category,(folder,alias,qfile) in SETS.items():
  questions[category]={r['qid'].rsplit('-',1)[-1]:r for r in (json.loads(l) for l in (ROOT/qfile).read_text().splitlines() if l)}
  if alias:
   physical=list(client.indices.get_alias(name=alias))
   if len(physical)!=1:raise ValueError('Expected one physical background')
   rows=sorted((h['_source'] for h in scan(client,index=physical[0],query={'query':{'match_all':{}}},_source=['id','parent_id','title','body','heading_path','embedding','splade','published_at'])),key=lambda r:r['id'])
   sample=[r for r in rows[::max(1,len(rows)//3)][:3] if r.get('splade')]
   dense_actual=embedder.embed([inputs(r)[0] for r in sample]);sparse_actual=encoder.encode_documents([inputs(r)[1] for r in sample])
   dc=min(float(norm(v)@norm(r['embedding'])) for r,v in zip(sample,dense_actual))
   sc=max(abs(v.get(k,0)-r['splade'].get(k,0)) for r,v in zip(sample,sparse_actual) for k in set(v)|set(r['splade']))
   # Never mix vectors from an unknown encoder/input with the new vectors.
   reuse_dense=dc>.999;reuse_sparse=sc<.02
   print(category,'background',len(rows),'reuse',reuse_dense,reuse_sparse,'sample',dc,sc,flush=True)
   for row in rows:
    dt,st=inputs(row)
    if reuse_dense:dense_cache[dt]=row['embedding']
    if reuse_sparse:sparse_cache[st]=row['splade']
   metadata['backgrounds'][category]={'index':physical[0],'chunks':len(rows),'denseSampleMinCosine':dc,'sparseSampleMaxDifference':sc,'reuseDense':reuse_dense,'reuseSparse':reuse_sparse}
  else:
   rows=snapshot('e400e04^',category)
   metadata['backgrounds'][category]={'git':'e400e04^','chunks':len(rows),'reason':'No FAQ live alias; frozen pre-fix parser corpus, newly encoded with the same models.'}
  corpora[category]=rows
 for key,entries in history.items():
  category,qid=key.rsplit('-',1)
  for e in entries:
   parent=e['after']['id'].rsplit('#',1)[0]
   for arm,rev in [('before',e['commit']+'^'),('after',e['commit'])]:
    foreground[(key,e['commit'],arm)]=[r for r in snapshot(rev,category) if r['parent_id']==parent]
 ablations={}
 for key, entries in history.items():
  for e in entries:
   category=key.rsplit('-',1)[0]
   after=next(r for r in foreground[(key,e['commit'],'after')] if r['id']==e['after']['id'])
   old_lines=e['before']['body'].splitlines();new_lines=after['body'].splitlines()
   changed=set()
   for tag,a,b,c,d in difflib.SequenceMatcher(None,old_lines,new_lines,autojunk=False).get_opcodes():
    if tag in ('insert','replace'):changed.update(range(c,d))
   ablations[(key,e['commit'])]={'row':{**after,'body':'\n'.join(line for i,line in enumerate(new_lines) if i not in changed)},'text':'\n'.join(line for i,line in enumerate(new_lines) if i in changed)}
 global_foreground={}
 for key,entries in history.items():
  category=key.rsplit('-',1)[0];current_parents={r['parent_id'] for r in corpora[category]}
  for e in entries:
   rev=e['commit'];old={r['id']:r for r in snapshot(rev+'^',category)};new={r['id']:r for r in snapshot(rev,category)}
   common={r['parent_id'] for r in old.values()}&{r['parent_id'] for r in new.values()}&current_parents
   changed={r['parent_id'] for r in new.values() if r['parent_id'] in common and (r['id'] not in old or inputs(r)!=inputs(old[r['id']]))}
   changed|={r['parent_id'] for r in old.values() if r['parent_id'] in common and r['id'] not in new}
   for arm,data in [('before',old),('after',new)]:global_foreground[(rev,category,arm)]=[r for r in data.values() if r['parent_id'] in changed]
 dense_texts=set();sparse_texts=set(); query_variants={}
 for category,rows in corpora.items():
  for row in rows:
   dt,st=inputs(row);dense_texts.add(dt);sparse_texts.add(st)
 for rows in foreground.values():
  for row in rows:
   dt,st=inputs(row);dense_texts.add(dt);sparse_texts.add(st)
 for key in history:
  category,qid=key.rsplit('-',1);query=questions[category][qid]['query'];words=query.split()
  variants=[query]+[' '.join(words[:i]+words[i+1:]) for i in range(len(words))]
  query_variants[key]=variants;dense_texts.update(variants)
 for rows in global_foreground.values():
  for row in rows:
   dt,st=inputs(row);dense_texts.add(dt);sparse_texts.add(st)
 for ablation in ablations.values():
  dt,st=inputs(ablation['row']);dense_texts.add(dt);sparse_texts.add(st)
 query_sparse={}
 queries=list(dict.fromkeys(variants[0] for variants in query_variants.values()))
 query_sparse.update(zip(queries,encoder.encode(queries,settings.search_splade_query_max_length)))
 def checkpoint():cache_path.write_text(json.dumps({'dense':dense_cache,'sparse':sparse_cache},ensure_ascii=False,separators=(',',':')))
 missing_sparse=sorted(sparse_texts-set(sparse_cache));missing_dense=sorted(dense_texts-set(dense_cache))
 print('Pending encoding: SPLADE',len(missing_sparse),'dense',len(missing_dense),flush=True)
 for start in range(0,len(missing_sparse),8):
  batch=missing_sparse[start:start+8];sparse_cache.update(zip(batch,encoder.encode_documents(batch)))
  if start%64==0:print('SPLADE',min(start+8,len(missing_sparse)),'/',len(missing_sparse),flush=True)
  if start%256==0:checkpoint()
 checkpoint()
 for start in range(0,len(missing_dense),16):
  batch=missing_dense[start:start+16];dense_cache.update(zip(batch,embedder.embed(batch)))
  if start%64==0:print('dense',min(start+16,len(missing_dense)),'/',len(missing_dense),flush=True)
  if start%256==0:checkpoint()
 checkpoint()
 matrices={c:np.stack([norm(dense_cache[inputs(r)[0]]) for r in rows]) for c,rows in corpora.items()}
 measurements={};summaries=[]
 for num,(key,entries) in enumerate(history.items(),1):
  category,qid=key.rsplit('-',1);q=questions[category][qid];query=q['query'];qv=norm(dense_cache[query]);qs=query_sparse[query]
  background=corpora[category]
  bs=np.array([sparse_score(qs,sparse_cache[inputs(r)[1]]) for r in background]);bd=(1+matrices[category]@qv)/2
  variants=query_variants[key];words=query.split();drop_vectors=[norm(dense_cache[v]) for v in variants[1:]]
  measurements[key]={}
  for e in entries:
   parent=e['after']['id'].rsplit('#',1)[0];keep_bg=[i for i,r in enumerate(background) if r['parent_id']!=parent]
   result={'before':{},'after':{},'denseWords':[],'spladeTokens':[]}
   target_vectors={};target_sparse={};target_score={}
   for arm in ['before','after']:
    fg=foreground[(key,e['commit'],arm)]
    published=next((r.get('published_at') for r in background if r['parent_id']==parent),None)
    fg=[{**r,'published_at':published} for r in fg]
    rows=[background[i] for i in keep_bg]+fg
    sv=np.array([sparse_score(qs,sparse_cache[inputs(r)[1]]) for r in fg]);dv=np.array([(1+float(norm(dense_cache[inputs(r)[0]])@qv))/2 for r in fg])
    sp=np.concatenate([bs[keep_bg],sv]);dn=np.concatenate([bd[keep_bg],dv])
    result[arm]=rank_result(rows,sp,dn,set(range(len(keep_bg),len(rows))),q,category,qid)
    target=next(r for r in fg if r['id']==e[arm]['id']);dt,st=inputs(target)
    cv=norm(dense_cache[dt]);target_vectors[arm]=cv;target_sparse[arm]=sparse_cache[st]
    raw=float(cv@qv);sparse=sparse_score(qs,target_sparse[arm]);target_score[arm]=[raw,sparse]
    result[arm].update(denseCosine=raw,denseScore=(1+raw)/2,spladeScore=sparse,targetId=target['id'])
   changed_parents={r['parent_id'] for r in global_foreground[(e['commit'],category,'before')]}
   rest=[i for i,r in enumerate(background) if r['parent_id'] not in changed_parents]
   for arm in ['before','after']:
    fg=global_foreground[(e['commit'],category,arm)]
    published={r['parent_id']:r.get('published_at') for r in background}
    fg=[{**r,'published_at':published.get(r['parent_id'])} for r in fg]
    rows=[background[i] for i in rest]+fg
    sv=np.array([sparse_score(qs,sparse_cache[inputs(r)[1]]) for r in fg]);dv=np.array([(1+float(norm(dense_cache[inputs(r)[0]])@qv))/2 for r in fg])
    result['global'+arm.title()]=rank_result(rows,np.concatenate([bs[rest],sv]),np.concatenate([bd[rest],dv]),set(range(len(rest),len(rows))),q,category,qid,whole_question=True)
   result['globalChangedParents']=len(changed_parents)
   ablation=ablations[(key,e['commit'])];dt,st=inputs(ablation['row'])
   result['changedSegment']={'text':ablation['text'],'denseDrop':target_score['after'][0]-float(norm(dense_cache[dt])@qv),'spladeDrop':target_score['after'][1]-sparse_score(qs,sparse_cache[st])}
   result['delta']={'denseCosine':target_score['after'][0]-target_score['before'][0],'spladeScore':target_score['after'][1]-target_score['before'][1]}
   result['denseWords']=sorted([{'word':word,'before':float(qv@target_vectors['before']-drop_vectors[i]@target_vectors['before']),'after':float(qv@target_vectors['after']-drop_vectors[i]@target_vectors['after'])} for i,word in enumerate(words)],key=lambda x:abs(x['after']-x['before']),reverse=True)
   result['spladeTokens']=sorted([{'token':encoder._tokenizer.convert_ids_to_tokens(int(t[1:])).replace('##','').replace('▁',''),'before':w*target_sparse['before'].get(t,0),'after':w*target_sparse['after'].get(t,0)} for t,w in qs.items()],key=lambda x:abs(x['after']-x['before']),reverse=True)
   measurements[key][e['commit']]=result
   summaries.append({'question':key,'commit':e['commit'],'title':e['title'],'delta':result['delta'],'beforeReturned':result['before']['returnedRanks'],'afterReturned':result['after']['returnedRanks']})
  if num%10==0:print('Measured',num,'/',len(history),flush=True)
 metadata['wholeQuestionControl']='Also replace all shared current parents whose encoder input changed in this parser commit. Evaluate mandatory phrases across the returned chunks from allowed gold parents; 111/125/143 include units. These are phrase-based offline evidence checks, not an LLM answer evaluation.'
 artifact={'metadata':metadata,'measurements':measurements,'summary':summaries}
 (OUT/'results.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n')
 compact={'metadata':metadata,'measurements':{key:{rev:{k:v for k,v in result.items() if k not in []} for rev,result in es.items()} for key,es in measurements.items()}}
 (ROOT/'docs/presentation/question_explorer/data/category-chunking-impact.js').write_text('window.CATEGORY_CHUNKING_IMPACT='+json.dumps(compact,ensure_ascii=False,separators=(',',':'))+';\n')
 print('Finished',len(summaries),'comparisons',flush=True)

if __name__=='__main__':main()
