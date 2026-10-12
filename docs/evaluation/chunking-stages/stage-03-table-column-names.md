# 청킹 3단계: 표의 실제 열 이름 복구 (2026-10-12)

`열1·열2`라는 임시 이름이 남던 표에서 원문 머리글을 복구한다. 청커 v8이며 LLM은 사용하지 않는다. 법령·고시 150문서만 새 코퍼스와 실험 인덱스로 생성했다.

## 실제 전후 예시

「북한 맞춤형 감시대상품목(watch-list)」의 `<별표 6> / 1 핵 관련 89개 품목` 원문:

| 원문 빈칸 | 국문 | 영문 |
|---|---|---|
| 1 | 아세트산 | Acetic acid |
| 2 | 알루미늄 | Aluminium |
| 3 | 질산알루미늄 | Aluminium nitrate |

수정 전에는 빈 첫 머리글 때문에 머리글 전체를 인식하지 못했고, 머리글도 데이터 행으로 취급했다.

```text
수정 전 — #0002 / 저장된 행 위치 2/90
열1: 1
열2: 아세트산
열3: Acetic acid
columns: [열1, 열2, 열3]

수정 후 — #0001 / 저장된 행 위치 1/89
순번: 1
국문: 아세트산
영문: Acetic acid
columns: [순번, 국문, 영문]
```

`국문·영문`은 원문 머리글이다. `순번`은 원문에 없는 이름이며, 해당 열의 값이 **3개 이상이고 1, 2, 3…으로 연속**하는 것을 확인해 추론했다. 그 조건을 만족하지 않는 빈 머리글은 이름을 추측하지 않는다. 행 수 90→89는 머리글을 데이터에서 분리한 결과이고, 89개 품목은 보존된다.

## 적용 규칙과 과적합 점검

- HTML의 명시적인 `<th>`를 머리글 정보로 보존한다.
- 표 맨 앞의 빈 행을 건너뛰고, 병합 제목 뒤의 실제 머리글을 확인한다. 긴 표 소개문은 이름 복구 과정에서 버리지 않는다.
- 빈 모서리 칸이 있어도 나머지 짧은 열 제목이 일렬로 채워져 있고, 다음 행이 데이터라면 열 이름을 읽는다. 내부 빈칸을 사이에 둔 흐름도는 한 줄 머리글로 취급하지 않는다.
- PDF에서 연속된 페이지의 표가 같은 열 수를 유지하면 앞 구간의 실제 열 이름을 전달한다. 새 제목·별표·서식·페이지 간격에서 전달을 끊는다. 열 수가 손상된 구간에는 이름을 붙이지 않는다.
- 문서 ID·파일명·품목명·평가 질문을 비교하는 예외 분기를 추가하지 않았다. 기존 머리글 길이 기준 20자를 평가 수치에 맞춰 조정하지 않았다.

테스트는 한국어·영어·그리스 문자 열 이름, 명시적 긴 HTML 머리글, 순번이 아닌 코드, 짧은 신구대비 본문, 흐름도, 다른 제목·페이지 간격·열 수 등의 반례를 확인한다. `tests/chunking` **133개 통과**.

원문 셀 보존 검사는 법령 150문서 / 논리 표 323개와 행정 20문서 / 논리 표 54개에서 **누락된 셀 0개**였다. 이는 머리글·표 제목·행 값에 원문 셀 글자가 남는지를 검사하며, 모든 열 이름의 의미가 맞음을 보장하는 검사는 아니다.

행정 문서는 검색을 실행하지 않고 구조만 검토했다. 이 과정에서 흐름도 반례를 발견해 규칙을 수정했으므로, 이 결과를 최종 미사용 홀드아웃 검증이라고 부르지 않는다. 기존 149문항 역시 회귀 평가이며 일반화 성능을 보장하지 않는다.

## 구조 결과

| 항목 | 수정 전 | 수정 후 |
|---|---:|---:|
| 법령 문서 | 150 | 150 |
| 전체 청크 | 6,502 | 6,493 |
| 임시 열 이름이 하나라도 있는 청크 | 1,251 | 382 |
| 임시 열 이름이 하나라도 있는 표 ID | 187 | 89 |

382개가 모두 해결됐다고 표현하지 않는다. 공통 열 머리글이 없는 신청서·서식, 일부 머리글이 빈 표, PDF 격자의 열 수가 달라져 대응을 확정할 수 없는 표 등이 남았다. 실제 이름을 임의로 붙이지 않고 `audit.json`에 청크 ID·본문·열 이름을 기록했다.

## 법령 검색 결과

같은 기존 법령 149문항, 기준일 2026-10-07, hybrid(SPLADE+dense), 청크 우선 검색, **서비스 컷오프 0.7만** 사용했다. LLM 필터·답변 가능성 판정·리랭커·질문 재작성은 사용하지 않았다. 기준선은 표 주석 연결까지 적용한 `exp-table-ctx-after-law`, 변경안은 `exp-table-headers-final-law`다. 질문·정답 라벨·검색 설정은 이 수정에 맞춰 변경하지 않았다.

| 지표 | 수정 전 | 수정 후 |
|---|---:|---:|
| 자동 평가의 정답 근거 청크 반환 | 143/149 | 144/149 |
| 정답 문서 반환 | 146/149 | 146/149 |
| 필수 구절 반환 | 139/149 | 141/149 |
| 평균 반환 청크 | 7.96 | 7.91 |
| 근거 라벨을 코퍼스에 대응하지 못한 질문 | 1 | 0 |

자동 평가에서 새로 성공한 1문항은 `law150-v1-143`이고, 새 실패는 없다. 1위 문서는 146/149문항에서 동일하다.

**143→144를 새 정답 행 발견으로 해석하지 않는다.** 143번 질문의 정답 행은 전후 모두 검색됐다. 수정 전 `열3: 500`이 수정 후 `과태료 금액: 500`으로 바뀌면서 기존 필수 구절 라벨이 대응했다. 이 사례의 정답 청크 ID와 정답 행 값도 전후 동일하다. `gain_case.json`에 실제 반환 청크를 보존했다. 따라서 확인한 효과는 실제 열 제목 복구와 기존 평가 라벨의 정상화이며, 별도 미사용 질문에서의 검색 향상은 아직 검증하지 않았다.

## 산출물과 재현

- `data/chunking_artifacts/v8/`: 새 코퍼스, dense·SPLADE 포함 인덱스, 평가, 구조 감사, 미해결 청크, 코드 패치.
- 기준선은 `data/chunking_artifacts/table-context-2026-10-12/after/`의 코퍼스·인덱스다.
- `data/generated/table-headers-2026-10-12/`: 비압축 작업 코퍼스와 측정 로그.
- 화면: Question Explorer의 `#cat-chunking-stage-03`.

```bash
.venv/bin/python -m pytest tests/chunking -q
.venv/bin/python scripts/chunking/build_corpus_from_bundles.py \
  ../unstructured-doc-parser_ver2/data/category_chunks/01_법령고시 \
  --out data/generated/table-headers-2026-10-12/final.jsonl
.venv/bin/python scripts/chunking/index_cached_law_corpus.py \
  data/generated/table-headers-2026-10-12/final.jsonl \
  --cache exp-table-ctx-after-law --alias exp-table-headers-final-law \
  --prefix exp-table-headers-final-law-
.venv/bin/python scripts/chunking/eval_category_chunking.py \
  --queries data/queries_law150_v1.jsonl --reference search-law \
  --arm before=exp-table-ctx-after-law --arm after=exp-table-headers-final-law \
  --out data/generated/table-headers-2026-10-12/eval_law.json
.venv/bin/python scripts/chunking/audit_table_headers.py \
  --before data/chunking_artifacts/table-context-2026-10-12/after/corpus.jsonl.gz \
  --after data/chunking_artifacts/v8/corpus.jsonl.gz \
  --review-category ../unstructured-doc-parser_ver2/data/category_chunks/02_행정업무 \
  --out data/generated/table-headers-2026-10-12/audit.json
```
