#!/bin/bash
G=/private/tmp/claude-501/-Users-jeongbin-git-searchEngine/b71074ab-b8c9-4f2a-a981-afa2931fdbd2/scratchpad/gen; S=$G/..
export PYTORCH_ENABLE_MPS_FALLBACK=1 HF_HUB_OFFLINE=1
log() { echo "$(date +%H:%M:%S) $*" | tee -a $G/chain2.log; }
for cfg in "D 5e-6 0" "E 3e-6 0"; do
  set -- $cfg; n=$1
  log "학습 $n (lr $2, λ $3, 1에폭)"; $S/.venv-train/bin/python $G/train_v2.py --out $G/ckpt-$n --lr $2 --lam $3 --epochs 1 --bs 8 > $G/train-$n.log 2>&1; grep -E "saved|Error" $G/train-$n.log | tail -1 | tee -a $G/chain2.log
  [ -d $G/ckpt-$n ] && { log "평가 $n"; $G/eval_ckpt.sh $G/ckpt-$n $n > /dev/null 2>&1; log "$n 평가 끝"; } || log "$n 학습 실패"
done
log "요약"; $S/.venv-train/bin/python $G/summarize.py base,D,E RESULTS2.md | tee -a $G/chain2.log; log "전체 완료"
