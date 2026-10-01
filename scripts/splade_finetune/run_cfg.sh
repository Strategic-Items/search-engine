#!/bin/bash
# usage: run_cfg.sh name train-args...
S=$(pwd); n=$1; shift
.venv-train/bin/python train_splade.py --out ckpt-$n "$@" > train-$n.log 2>&1
cd /Users/jeongbin/git/searchEngine
HF_HUB_OFFLINE=1 PYTORCH_ENABLE_MPS_FALLBACK=1 $S/.venv-train/bin/python scripts/evaluate_splade.py --corpus data/generated/docs-v2/review-corpus/docs.jsonl --queries data/queries_docs_v2.jsonl --model $S/ckpt-$n --batch-size 8 --max-length 256 --out $S/eval-ckpt-$n.json > /dev/null 2>&1
python3 - <<PY
import json
b=json.load(open("$S/eval-PIXIE-Splade-v1.5.json")); f=json.load(open("$S/eval-ckpt-$n.json"))
top=lambda r:r["ranked"][0]["parent_id"] if r["ranked"] else None
bw=sum(top(r) in r["gold"] for r in b["results"]); fw=sum(top(r) in r["gold"] for r in f["results"])
s=[x for x in f["sweeps"] if x["ratio"]==0.97][0]
print("$n","P@1 base",bw,"ft",fw,"| ratio.97 hit5",round(s["hit_at_5"],3),"retP",round(s["precision_returned"],3),"mrr",round(s["mrr_at_5"],3),"doc_terms",round(f["mean_document_terms"]),"vs",round(b["mean_document_terms"]))
PY
