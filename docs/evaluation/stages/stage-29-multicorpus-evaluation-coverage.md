# 29단계: 혼합 코퍼스 평가에서 색인 범위를 정확히 확인한다 (2026-09-25)

28단계 재측정 때 평가기에 holdout의 `core.jsonl` 폴더만 주면 docs 정답이 모두
미색인으로 표시됐다. 평가기는 결과 JSON을 쓴 뒤 `answerable['queries']`를 읽으며
`KeyError`로 종료했다. 검색 자체의 오류는 아니지만, 순위 실패와 색인 범위 실패를
가르는 보고서가 신뢰할 수 없게 된다.

## 수정

- `search-evaluate --prepared DIR`를 여러 번 줄 수 있게 했다. 각 폴더의
  `core.jsonl`·`docs.jsonl`·`hsk.jsonl` ID를 합쳐 색인 범위를 확인한다.
- 정답이 색인된 질문이 0개여도 보고서는 `0건`으로 출력한다.
- 별도 폴더의 부모 ID를 합치는 테스트와 정답 전부 미색인인 보고서 테스트를 추가했다.

## 확인

```sh
.venv/bin/search-evaluate data/queries_docs_v2.jsonl \
  --base-url http://127.0.0.1:8113 \
  --prepared data/generated/holdout-v1 \
  --prepared data/generated/docs-v2/review-corpus \
  --k 5 --out /tmp/stage29-multicorpus-check.json
```

135문항의 보고서가 정상 종료됐다. 정답이 모두 색인된 질문은 133개이며,
`docs-v2-018`의 `yestrade-form-22209`와 `docs-v2-020`의 `yestrade-form-23307`은
두 준비 폴더 어디에도 없다고 구분해 표시했다. 이 확인에 쓴 8113 서버는 이전
검색 코드로 실행 중이므로, 여기서 나온 검색 적중률은 28단계의 새 랭커 성능이 아니다.
전체 테스트는 236개 통과했다.

## 범위

이 단계는 평가 도구의 색인 범위와 보고서 종료 오류만 고쳤다. 검색 순위와 `gold`는
변경하지 않았다. 여러 준비 폴더에 파일이 있더라도 실제 검색 인덱스의 별칭이 그
파일을 가리키는지는 별도로 확인해야 한다.
