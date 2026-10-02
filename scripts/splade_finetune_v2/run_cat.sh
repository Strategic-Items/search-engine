#!/bin/bash
export PYTORCH_ENABLE_MPS_FALLBACK=1 HF_HUB_OFFLINE=1; R=/Users/jeongbin/git/searchEngine; S=/private/tmp/claude-501/-Users-jeongbin-git-searchEngine/b71074ab-b8c9-4f2a-a981-afa2931fdbd2/scratchpad; C=/private/tmp/claude-501/-Users-jeongbin-git-searchEngine/b71074ab-b8c9-4f2a-a981-afa2931fdbd2/scratchpad/cat; G=/private/tmp/claude-501/-Users-jeongbin-git-searchEngine/b71074ab-b8c9-4f2a-a981-afa2931fdbd2/scratchpad/gen; P=/Users/jeongbin/git/unstructured-doc-parser_ver2/data/category_chunks
log() { echo "$(date +%H:%M:%S) $*" | tee -a $C/cat.log; }
for n in law admin; do
  case $n in law) CORPUS=$P/01_법령고시/docs.jsonl;; admin) CORPUS=$P/02_행정업무/docs.jsonl;; esac
  q=$C/queries_${n}_v1.jsonl
  log "dense 임베딩 $n"; $S/.venv-train/bin/python $S/encode_dense.py dragonkue/BGE-m3-ko bge $CORPUS $q $C/emb-bge-$n.npz 2>&1 | grep -E "^bge " | tee -a $C/cat.log
  for t in base A C D E; do
    m=$G/ckpt-$t; [ $t = base ] && m=telepix/PIXIE-Splade-v1.5
    log "SPLADE $t $n"; $S/.venv-train/bin/python $R/scripts/evaluate_splade.py --corpus $CORPUS --queries $q --model $m --batch-size 8 --max-length 256 --out $C/ev-$t-$n.json > /dev/null 2>&1
  done
done
log "전체 완료"
