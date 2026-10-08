#!/bin/zsh
# 청킹 버전 하나를 처음부터 끝까지 돌린다: 코퍼스 만들기 -> 별도 인덱스 색인 -> 기준(v0) 대비 평가 -> 버전 기록.
# 서비스 별칭(search-law, search-admin)은 건드리지 않는다. 기준 인덱스 exp-chk-{law,admin}-old가 있어야 한다.
#
#   scripts/chunking/run_version.sh <버전> "<요약>" "<무엇을 왜 바꿨나>"
#
# 먼저 search_engine/chunking/params.py의 CHUNKER_VERSION을 <버전>으로 올려 둔다(다르면 기록 때 경고).
set -e
cd "$(dirname "$0")/../.."
V=${1:?버전}; LABEL=${2:?요약}; NOTES=${3:-}
PARSER=${PARSER_ROOT:-../unstructured-doc-parser_ver2}
OUT=data/generated/chunking-v$V
mkdir -p $OUT
for pair in law:01_법령고시:data/queries_law150_v1.jsonl admin:02_행정업무:data/queries_admin_v1.jsonl; do
  name=${pair%%:*}; rest=${pair#*:}; dir=${rest%%:*}; queries=${rest#*:}
  .venv/bin/python scripts/chunking/build_corpus_from_bundles.py $PARSER/data/category_chunks/$dir --out $OUT/$name.jsonl
  upper=$(echo $name | tr a-z A-Z)
  env SEARCH_${upper}_ALIAS=exp-chk-$name-v$V SEARCH_${upper}_PREFIX=exp-chk-$name-v$V- \
    .venv/bin/search-index $OUT/$name.jsonl --dataset $name 2>&1 | tail -1
  .venv/bin/python scripts/chunking/eval_category_chunking.py --queries $queries \
    --arm old=exp-chk-$name-old --arm new=exp-chk-$name-v$V --out $OUT/eval_$name.json 2>&1 | grep -v "^INFO\|Warning\|warn\|Loading weights"
done
.venv/bin/python scripts/chunking/record_chunking_version.py --version $V --label "$LABEL" --notes "$NOTES" \
  --corpus law=$OUT/law.jsonl --corpus admin=$OUT/admin.jsonl \
  --eval law=$OUT/eval_law.json:new --eval admin=$OUT/eval_admin.json:new
