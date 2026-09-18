# 검색 품질 baseline — 2026-09-15

> 이 문서의 표는 자료 유형 가점을 넣기 **전**의 기준선이다.
> 가점 이후 수치는 [질의 유형 가점](../design/query_intent_boost.md)에 있다.

`search-evaluate`로 실행 중인 `/v1/search`를 실습 저장소의 검토 중인 정답 질의
93건(`/Users/jeongbin/git/search-engine/data/queries_project_v1_reviewed.jsonl`)에
대해 측정한 결과다. 평가셋은 실습 저장소에 두고 경로로 읽으며 이 저장소에 복사하지
않는다. 색인은 [import_v1](../design/import_v1.md)의 스냅샷(`search-documents` 3,499,
`search-hsk` 18,673)이다.

```bash
.venv/bin/uvicorn search_engine.api:app --host 127.0.0.1 --port 8092
.venv/bin/search-evaluate \
  /Users/jeongbin/git/search-engine/data/queries_project_v1_reviewed.jsonl \
  --out data/generated/baseline.json
```

| 유형 | 질의 | 첫 결과 | 상위 5건 | 정답 미색인 |
|---|---:|---:|---:|---:|
| country | 10 | 2 / 10 | 2 / 10 | 8 |
| faq_legacy | 26 | 11 / 26 | 15 / 26 | 4 |
| form | 12 | 6 / 12 | 9 / 12 | 0 |
| guide | 7 | 0 / 7 | 5 / 7 | 0 |
| hsk | 18 | 18 / 18 | 18 / 18 | 0 |
| law_code | 10 | 0 / 10 | 0 / 10 | 10 |
| notice | 10 | 9 / 10 | 10 / 10 | 0 |
| **합계** | 93 | 46 / 93 | 59 / 93 | 22 |

정답이 색인된 71건만 보면 첫 결과 46, 상위 5건 59다. FAQ·서식·안내·공지·HSK 수치는
[import_v1](../design/import_v1.md)의 기록과 일치하므로, 이 러너는 그 측정을 재현한다.

이 숫자는 독립 운영 품질 지표가 아니다. 93건 중 정답 검토가 끝난 것은 HSK 18건
(`structured_source_verified`)뿐이고, 67건이 `needs_co_gold_review`, 5건이
`source_conflict_review`, 3건이 `co_gold_added_needs_pool_review`다.

## 순위 문제가 아닌 것

정답 문서가 애초에 색인에 없는 질의가 22건이다. 순위를 고쳐도 오르지 않으므로
개선 측정에서 분리한다.

- `law_code` 10건 전부: 고시·법령 원문(`law-gosi-*`)은 이번 적재 범위가 아니다.
- `country` 8건: 국가별 제도 문서(`law-intl-*`)도 적재 범위 밖이다.
- `faq_legacy` 4건(q04, q06, q09, q15): 정답이 `faq-042` 하나인데, 이 FAQ는 현행
  자가판정 안내와 충돌한다는 실습 검토에 따라 색인에서 제외했다. 현행 안내
  문서(`yestrade-guide-self-judgement`)가 색인에 있으므로 정답 재판정 대상이다.
  q23은 두 번째 정답 `faq-034`가 색인돼 있어 순위 실패로 집계된다.

## 순위로 고쳐야 하는 것

정답이 색인돼 있는데 상위 5건에 못 든 12건이다.

- `guide` 2건, `form` 3건: 안내는 첫 결과 0/7로 가장 약하다. import_v1 측정에서
  자료 유형을 지정하면 7/7이었으므로, 신호는 색인의 `source_type`에 있는데 질의가
  쓰지 않고 있다. 요청 계약은 `query` 하나로 유지하므로 파라미터를 늘리지 말고
  서버가 질의를 해석해야 한다.
- `faq_legacy` 7건: 동의어(캐치올, 셀프 판정), 구어체("사이트에 못 들어가겠어요"),
  법령 조항 참조가 섞여 있다. 정답 재판정 전에는 이쪽 튜닝을 보류한다.
