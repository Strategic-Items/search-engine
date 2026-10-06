"""청크 단위 RRF의 k를 바꿔 가며 95% 컷오프 창의 청크 Recall·Precision을 잰다(40단계).
판정은 탐색기 데이터(category-detail.js)의 Sonnet 판정을 쓴다.
사용: RANKS_DIR=<폴더>/ python scripts/law/sweep_rrf_k.py"""
import json, re, subprocess, numpy as np
from collections import defaultdict
REPO="/Users/jeongbin/git/searchEngine/"
import os
SC=os.environ.get("RANKS_DIR","")  # ev-C-<set>.json(SPLADE C 청크 순위), emb-bge-<set>.npz(dense), queries_*_v1.jsonl이 든 폴더
# 판정 캐시: 탐색기 데이터에서 반환된 모든 청크의 Sonnet 판정을 모은다
js=r'''var fs=require("fs"),vm=require("vm"),c={};vm.createContext(c);
["categories.js","category-detail.js"].forEach(f=>vm.runInContext(fs.readFileSync("%sdocs/presentation/question_explorer/data/"+f,"utf8"),c));
var o={};for(var k in c.CATH){o[k]={};for(var q in c.CATH[k]){var f=c.CATH[k][q].fx,m={};
f.sp.ret.forEach(l=>l.forEach(x=>m[x[0]]=x[2]));f.dn.ret.forEach(l=>l.forEach(x=>m[x[0]]=x[2]));f.ret.forEach(r=>r.ch.forEach(x=>m[x[0]]=x[4]));o[k][q]=m;}}
console.log(JSON.stringify(o))'''%REPO
J=json.loads(subprocess.check_output(["node","-e",js]))
SETS={"admin30":("admin","queries_admin_v1.jsonl"),"law50":("law50","queries_law50_v1.jsonl"),"faq30":("faq","queries_faq_v1.jsonl")}
def lists(key,tag,qfile):
    Q={}
    for l in open(SC+qfile):
        o=json.loads(l)
        if o.get("evidence_groups"): Q[o["qid"].split("-")[-1]]=o
    ev={r["qid"].split("-")[-1]:r for r in json.load(open(f"{SC}ev-C-{tag}.json"))["results"]}
    e=np.load(f"{SC}emb-bge-{tag}.npz"); ids=[str(x) for x in e["ids"]]; sims=e["queries"]@e["docs"].T; qp={str(q).split("-")[-1]:i for i,q in enumerate(e["qids"])}
    out={}
    for q in Q:
        sp=[h["chunk_id"] for h in ev[q]["chunk_ranked"]]
        dn=[ids[j] for j in np.argsort(-sims[qp[q]])[:50]]
        out[q]=(sp,dn,Q[q])
    return out
def run(sp,dn,k,ratio,maxc=10,maxd=5,perd=6):
    sc=defaultdict(float)
    for L in (sp,dn):
        for i,c in enumerate(L,1): sc[c]+=1/(k+i)
    dr={c:i for i,c in enumerate(dn,1)}
    order=sorted(sc,key=lambda c:(-sc[c],dr.get(c,10**6),c)); top=sc[order[0]]
    heads={sp[0],dn[0]}; docs=[]; per=defaultdict(int); out=[]
    for c in order:
        if len(out)>=maxc: break
        if sc[c]<top*ratio and c not in heads: continue
        d=c.split("#")[0]
        if d not in docs:
            if len(docs)>=maxd: continue
            docs.append(d)
        if per[d]>=perd: continue
        per[d]+=1; out.append(c)
    return order,out
def evaluate(key,k,ratio):
    tag,qf=SETS[key]; D=lists(key,tag,qf); n=len(D); rec5=ret=gotg=0; prel=pj=pu=0; anyret=0
    for q,(sp,dn,Qo) in D.items():
        order,out=run(sp,dn,k,ratio); groups=Qo["evidence_groups"]; want={c for g in groups for c in g}
        top5=set(order[:5]); rec5+=any(set(g)&top5 for g in groups)
        gotg+=any(set(g)&set(out) for g in groups); ret+=len(out)
        jm=J[key].get(q,{}); js=[jm[c]>=1 for c in out if c in jm]; unk=sum(1 for c in out if c not in jm)
        pj+=len(js); pu+=unk
        if out: prel+=(sum(js)/len(js)) if js else 0; anyret+=bool(js)
    return dict(k=k,ratio=ratio,recall5=f"{rec5}/{n}",goldReturned=f"{gotg}/{n}",avgRet=round(ret/n,2),judgedPrec=round(prel/max(anyret,1),3),unjudged=f"{pu}/{pj+pu}")
if __name__=="__main__":
    for key in SETS:
        print("==",key)
        for k in (60,30,20,10,5,2,1):
            print(evaluate(key,k,0.95))
