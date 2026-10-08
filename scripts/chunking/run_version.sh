#!/bin/zsh
# 청킹 버전 하나를 처음부터 끝까지 돌린다(법령·고시만): 코퍼스 만들기 -> 별도 인덱스 색인 -> 서비스 인덱스 대비 평가 -> 버전 기록.
# 서비스 별칭(search-law)은 읽기만 한다(공식 라벨의 기준, 비교 대상). 새 청크는 exp-chk-law-v<N>에 색인한다.
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
.venv/bin/python scripts/chunking/build_corpus_from_bundles.py $PARSER/data/category_chunks/01_법령고시 --out $OUT/law.jsonl
env SEARCH_LAW_ALIAS=exp-chk-law-v$V SEARCH_LAW_PREFIX=exp-chk-law-v$V- .venv/bin/search-index $OUT/law.jsonl --dataset law 2>&1 | tail -1
.venv/bin/python scripts/chunking/eval_category_chunking.py --queries data/queries_law150_v1.jsonl --reference search-law \
  --arm live=search-law --arm new=exp-chk-law-v$V --out $OUT/eval_law.json 2>&1 | grep -v "^INFO\|Warning\|warn\|Loading weights"
.venv/bin/python scripts/chunking/record_chunking_version.py --version $V --label "$LABEL" --notes "$NOTES" \
  --corpus law=$OUT/law.jsonl --eval law=$OUT/eval_law.json:new
