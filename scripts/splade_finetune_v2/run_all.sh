#!/bin/bash
G=/private/tmp/claude-501/-Users-jeongbin-git-searchEngine/b71074ab-b8c9-4f2a-a981-afa2931fdbd2/scratchpad/gen; S=$G/..; R=/Users/jeongbin/git/searchEngine
export PYTORCH_ENABLE_MPS_FALLBACK=1 HF_HUB_OFFLINE=1
log() { echo "$(date +%H:%M:%S) $*" | tee -a $G/chain.log; }
log "생성 종료 대기"; while kill -0 $GENPID 2>/dev/null; do sleep 60; done
log "생성 종료: $(wc -l < $G/generated.jsonl)청크"
log "난이도 선별"; $S/.venv-train/bin/python $G/build_train.py > $G/build.log 2>&1; tail -4 $G/build.log | tee -a $G/chain.log
[ -s $G/train_examples.json ] || { log "학습 예시 없음, 중단"; exit 1; }
log "기준 모델 평가"; $G/eval_ckpt.sh telepix/PIXIE-Splade-v1.5 base 2>&1 | tail -1 | tee -a $G/chain.log
for cfg in "A 1e-6 1" "B 2e-6 2" "C 5e-6 1"; do
  set -- $cfg; n=$1
  log "학습 $n (lr $2, 에폭 $3)"; $S/.venv-train/bin/python $G/train_v2.py --out $G/ckpt-$n --lr $2 --epochs $3 --bs 8 > $G/train-$n.log 2>&1; tail -2 $G/train-$n.log | tee -a $G/chain.log
  [ -d $G/ckpt-$n ] && { log "평가 $n"; $G/eval_ckpt.sh $G/ckpt-$n $n 2>&1 | tail -1 | tee -a $G/chain.log; } || log "$n 학습 실패"
done
log "요약"; $S/.venv-train/bin/python $G/summarize.py | tee -a $G/chain.log; log "전체 완료"
