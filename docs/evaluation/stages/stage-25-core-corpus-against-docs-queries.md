# 25단계: core를 docs 질의셋에 섞으면 무엇이 깎이는가 (2026-09-22)

지금까지 docs-v2 측정은 `search-docs-only` 하나만 읽었다. 운영은 `core,docs`가
기본값이므로(`.env.example`), 두 코퍼스를 함께 읽을 때 지금 지표가 유지되는지
재지 않은 채로 있었다. 이 단계는 **core를 섞었을 때 docs 질의 135문항이
얼마나 깎이는지**와 **그 손해가 어디서 나오는지**를 가른다.

여기서 바꾼 것은 검색기가 아니다. 모드·컷오프·임베딩 모델·질의셋 모두 그대로이고
**읽는 별칭만** 다르다.

## 왜 core 질의셋으로 재지 않았나

core에도 자체 질의셋 `data/queries_v1.jsonl` 93문항이 있지만 이 비교에 쓸 수 없다.

| | `queries_v1` (core) | `queries_docs_v2` (docs) |
|---|---|---|
| `gold` | 있음 (parent_id) | 있음 (parent_id) |
| `gold_groups` | 없음 | 있음 |
| `evidence_groups` | **없음** | 있음 |
| `evidence_requirements` | **없음** | 있음 |
| `answerable` | 없음 | 있음 |

`evidence_groups`가 없으면 23단계가 주 지표로 올린 근거 청크 지표가 계산되지
않는다(`evaluate.py`가 라벨 없음을 찍고 넘어간다). 게다가 93문항 전부에
`review_status: needs_co_gold_review`와 "코퍼스 확대에 따른 FAQ 외 공동 정답 재판정
필요"가 붙어 있다. `gold_basis`는 "기존 FAQ 207건 수작업 라벨"이다. 코퍼스가 넓어지면
공동 정답을 다시 봐야 한다고 라벨 스스로 예고해 둔 상태다.

그래서 이번 측정은 **라벨을 손대지 않고** docs 질의셋을 그대로 던져, core 3,956청크가
방해물로 들어왔을 때 docs 정답을 여전히 위로 올리는지만 본다. 노이즈 내성 측정이다.
**core 문서를 얼마나 잘 찾는지는 이 단계에서 재지 않는다.**

## 조건

코퍼스와 질의셋은 기존과 같다. docs 1,198청크(`review-corpus/docs.jsonl`),
core 3,956청크, 질의 `data/queries_docs_v2.jsonl` 135문항. 세 API를 같은 코드로
동시에 띄우고 별칭만 달리했다.

| 포트 | `SEARCH_DOCUMENT_DATASETS` | 읽는 별칭 |
|---|---|---|
| 8101 | `docs` | `search-docs-only` |
| 8102 | `core,docs` | `search-documents` + `search-docs-only` |
| 8103 | `core,docs` | `search-documents-trim` + `search-docs-only` |

`search-documents-trim`은 아래 진단을 위해 core에서 청크가 폭주한 부모 문서 4건만
빼고 새로 색인한 926청크짜리 별도 별칭이다. 기존 `search-documents`와
`search-docs-only`는 손대지 않았다.

재현 명령:

```bash
# 세 API를 같은 코드로 띄운다
SEARCH_DOCUMENT_DATASETS=docs \
  .venv/bin/uvicorn search_engine.api:app --host 127.0.0.1 --port 8101
SEARCH_DOCUMENT_DATASETS=core,docs \
  .venv/bin/uvicorn search_engine.api:app --host 127.0.0.1 --port 8102

# core에서 거대 문서 4건을 뺀 별도 별칭
python3 -c 'import json,sys
drop={"yestrade-notice-21177","yestrade-notice-23257",
      "yestrade-notice-22867","yestrade-form-23302"}
for line in open("data/generated/core.jsonl"):
    if line.strip() and (json.loads(line).get("parent_id") or "") not in drop:
        sys.stdout.write(line)' > core-trim.jsonl
SEARCH_INDEX_ALIAS=search-documents-trim SEARCH_INDEX_PREFIX=search-documents-trim-v \
  .venv/bin/search-index core-trim.jsonl --dataset core
SEARCH_DOCUMENT_DATASETS=core,docs SEARCH_INDEX_ALIAS=search-documents-trim \
  .venv/bin/uvicorn search_engine.api:app --host 127.0.0.1 --port 8103

# 같은 질의셋을 세 번
.venv/bin/search-evaluate data/queries_docs_v2.jsonl \
  --base-url http://127.0.0.1:8101 \
  --prepared data/generated/docs-v2/review-corpus \
  --k 5 --out data/generated/docs-v2/evaluation-135q-docs-only.json
```

`--prepared`에는 `core.jsonl`과 `docs.jsonl`이 함께 있는 디렉터리를 넘겨야
색인 범위 문제와 순위 문제가 갈린다. 세 실행 모두
`gold_missing_from_index`가 0이므로 **아래 하락은 전부 순위 문제다.**

## 결과

| 지표 | docs만 | core+docs | core(4건 제외)+docs |
|---|---:|---:|---:|
| **근거 Recall@5** | **0.9630** | 0.9111 | 0.9222 |
| **근거 모든 근거@5** | **0.9481** | 0.9037 | 0.9111 |
| **근거 MRR@5** | **0.8179** | 0.7446 | 0.7742 |
| 근거 Precision@5 (하한) | 0.2635 | 0.2177 | 0.2492 |
| 평균 반환 청크 | 5.78 | 6.83 | 5.64 |
| 문서 P@1 | 0.9481 | 0.8444 | 0.8889 |
| 문서 P@5 (반환분) | 0.9274 | 0.6433 | 0.8359 |
| 문서 Recall@5 | 0.9105 | 0.8599 | 0.8747 |
| 문서 MRR@5 | 0.9704 | 0.8848 | 0.9191 |
| 평균 반환 문서 | 1.19 | 2.07 | 1.50 |
| 첫 결과 적중 | 128 / 135 | 114 / 135 | 120 / 135 |
| 상위 5건 적중 | 134 / 135 | 127 / 135 | 129 / 135 |

유형별 첫 결과 적중:

| 유형 | 질의 | docs만 | core+docs | trim+docs |
|---|---:|---:|---:|---:|
| paraphrase | 34 | 32 | 25 | 28 |
| scenario | 68 | 66 | 60 | 63 |
| multi_evidence | 18 | 18 | 17 | 17 |
| identifier_number | 6 | 6 | 6 | 6 |
| identifier_mixed | 5 | 5 | 5 | 5 |
| identifier_article | 4 | 1 | 1 | 1 |

식별자 구간은 꿈쩍하지 않는다. 공고번호 필터가 두 검색기에 걸려 있으므로 core가
들어와도 식별자 질의는 흔들리지 않는다. 손해는 전부 자연어 질의(`paraphrase`,
`scenario`)에서 난다.

## 진단 1: 청크 폭주는 눈에 띄지만 주범이 아니었다

core 인덱스는 부모 문서 **612건**에 청크 **3,956개**다. 분포가 고르지 않다.

| 청크 수 | 부모 문서 |
|---:|---|
| 1,268 | `yestrade-notice-21177` (제37차 전략물자수출입고시 개정 안내) |
| 636 | `yestrade-notice-23257` |
| 630 | `yestrade-notice-22867` |
| 496 | `yestrade-form-23302` |
| 95 | `yestrade-notice-23249` |
| 나머지 607문서 | 합계 831 |

**상위 4개 문서가 core 전체 청크의 77%(3,030개)를 차지한다.** 본문을 보면 공지 한 건에
별지 서식 전체가 첨부로 딸려 들어가 잘게 쪼개진 것이다.

```text
yestrade-notice-21177#c0002  "개별수출 허가 건수 ... 상황허가대상품목 건 ⑳ 비고 ..."
yestrade-notice-21177#c0003  "[별지 제19호 서식] Annexed paper No.19 자율준수무역거래자 실적 보고서 ..."
```

이런 조각이 1,268개 있으면 어떤 질의든 하나는 어휘가 걸린다. 실제로 `core+docs`에서
gold를 1위에서 밀어낸 문서 1·2위가 `yestrade-notice-23257`(3회)와
`yestrade-notice-21177`(2회)였다.

그런데 이 4건을 빼도 회복은 일부다. 1위를 잃은 질의는 **14건 → 8건**으로 줄고
(`docs-v2-091/094/095/097/113/120`이 회복), 근거 Recall@5는 0.9111 → 0.9222에
그친다. 하락폭 −5.2p를 나누면 이렇다.

- **−1.1p**가 거대 공지 4건 탓 — 전체 청크의 77%를 차지하고도 이만큼이다
- **−4.1p**가 나머지 608문서 탓

**손해의 4분의 3은 평범한 FAQ가 낸다.** 청크 폭주는 진짜 결함이지만 지금 지표의
주범은 아니다.

## 진단 2: core 재색인은 아무것도 바꾸지 않는다

24단계에서 내려받기 사본 제거와 시점 힌트를 `prepare`에서 `indexer`로 옮겼으므로,
core 색인(2026-09-22 11:57)이 그 이전 것이라 수치가 core에 불리하게 나왔을 가능성을
먼저 확인했다. **아니었다.**

- `search-prepare`를 다시 돌려도 `core.jsonl`의 sha256이 동일하다
  (`4801e13836e3ea7c273cc3934ad2e65fe95f86da8003446bd00e42e3674f871d`, 3,956청크).
- 새 `parent_identity()`를 core 코퍼스에 직접 걸면 **사본 0건, 시점 힌트 0건**이다.
- core 3,956청크는 `source_path`가 **전부 비어 있다**. `download_copies`는
  `... (1).hwp` 같은 파일명을 보고 판정하는데 core는 yestrade 크롤링·FAQ라 파일명이
  없다. 매니페스트의 `period_hint: 0`도 같은 이유다.

**사본 제거와 시점 힌트는 docs 코퍼스 전용 장치다.** core에는 걸리지 않는다. 따라서
재색인해도 위 수치는 그대로다.

## 남은 8건

trim 상태에서도 1위를 잃은 8건이다.

| qid | 유형 | gold | 1위를 가져간 문서 |
|---|---|---|---|
| 007 | paraphrase | 행정예고 공고문 | `faq-071` |
| 008 | paraphrase | 일부개정고시안 | `faq-184` |
| 017 | scenario | 별지16 사전거래보고서 | `faq-186` |
| 018 | scenario | 별지16 사전거래보고서 | `faq-186` |
| 020 | scenario | annexeds02_2 | `yestrade-guide-export-permission` |
| 040 | multi_evidence | 대외무역법 시행령 (3사본) | `faq-077` |
| 101 | paraphrase | 전략기술의 무형이전 통제 | `faq-127` |
| 109 | paraphrase | 한미양해각서 | `yestrade-board-67-1461` |

거대 문서는 사라지고 FAQ만 남았다. **이 8건이 오답인지 라벨 누락인지는 아직 가르지
않았다.** 성격이 갈린다.

- `docs-v2-007`은 "러시아 허가 목록 확대 의견수렴 **자료가 어디 있는지**"를 묻는다.
  정답은 행정예고 공고문이고 FAQ는 그 자료가 아니다. 자료의 소재를 묻는 질의에
  주제어만 겹친 FAQ가 온 것이므로 **명백한 오답**이다.
- `docs-v2-017`·`018`은 사전거래보고서 작성법을 묻고 `faq-186`이 1위, 정답 서식이
  2위다. FAQ가 실제로 같은 질문에 답하고 있다면 **라벨 누락**이지 검색 실패가 아니다.
  `faq-186`은 두 질의에서 1위를 가져간 유일한 문서다.
- `docs-v2-040`은 gold가 같은 시행령의 hwp·hwpx·pdf 세 사본인데 FAQ 세 건에 통째로
  밀렸다.

## 판단

**운영 기본값을 이 결과만으로 바꾸지 않는다.** 이 측정은 docs 질의셋에 대한 노이즈
내성만 봤고, core를 넣는 이유인 "core 문서를 잘 찾는가"는 재지 않았다.
한쪽만 재고 기본값을 정할 수는 없다.

확정된 것은 셋이다.

1. core를 섞으면 docs 질의 근거 Recall@5가 0.9630 → 0.9111로 **5.2p 떨어진다.**
   정답은 전부 색인 안에 있으므로 순위 문제다.
2. 그 손해의 4분의 1만 청크 폭주 문서 4건 탓이고, 나머지는 core 전반이 낸다.
3. core 재색인은 수치를 바꾸지 않는다. 사본 제거는 core에 적용되지 않는다.

다음 측정의 순서는 이렇다.

1. **남은 8건을 손으로 판정한다.** 오답인지 라벨 누락인지 가르기 전에는 −4.1p가
   검색 품질 저하인지 질의셋의 한계인지 말할 수 없다. 8건뿐이므로 이것이 가장 싸다.
2. 라벨 누락으로 판명되는 것이 있으면 `queries_docs_v2`의 `gold_groups`와
   `evidence_groups`에 core 문서를 더한다. 그 뒤 재측정해야 공정한 비교가 된다.
3. `yestrade-notice-21177` 등 4건의 청킹은 별도 트랙이다. 첨부 서식이 본문과 함께
   쪼개지는 것은 파서 쪽 문제이고, 이 지표와 무관하게 고칠 값어치가 있다.
4. core 질의 93문항에 `evidence_groups`를 붙이고 `needs_co_gold_review`를 푸는 일은
   그 다음이다. 그래야 core 방향도 청크 지표로 잴 수 있다.

원자료는 `data/generated/docs-v2/evaluation-135q-docs-only.json`,
`evaluation-135q-core-docs.json`, `evaluation-135q-core-trim-docs.json`이다.
