#!/bin/bash
# usage: eval_ckpt.sh <model_path_or_name> <tag>  -> docs_v2 / holdout-small / validation_v2 SPLADE 단독 평가
S=/private/tmp/claude-501/-Users-jeongbin-git-searchEngine/b71074ab-b8c9-4f2a-a981-afa2931fdbd2/scratchpad; R=/Users/jeongbin/git/searchEngine
export PYTORCH_ENABLE_MPS_FALLBACK=1
cd $R
for set in "docs:data/generated/docs-v2/review-corpus/docs.jsonl:data/queries_docs_v2.jsonl" "hs:$S/holdout-small.jsonl:data/queries_holdout_v1_adjudicated.jsonl" "val:$S/validation-small.jsonl:data/queries_validation_v2.jsonl"; do
  IFS=: read n c q <<< "$set"
  $S/.venv-train/bin/python scripts/evaluate_splade.py --corpus $c --queries $q --model $1 --batch-size 8 --max-length 256 --out $S/gen/ev-$2-$n.json > /dev/null 2>&1
done
python3 - <<PY
import json
tot=0; out=[]
for n in ("docs","hs","val"):
    j=json.load(open("$S/gen/ev-$2-$n.json")); top=lambda r:bool(r["ranked"]) and r["ranked"][0]["parent_id"] in set(r["gold"])
    p1=sum(top(r) for r in j["results"]); s=[x for x in j["sweeps"] if x["ratio"]==0.97][0]
    out.append(f"{n} P@1 {p1}/{len(j['results'])} Hit@5(r.97) {s['hit_at_5']:.3f} MRR {s['mrr_at_5']:.3f}")
print("$2 |"," | ".join(out))
PY
