# 파서 문서 검색 성능 이력

단계별 측정 기록의 색인이다. 단계는 두 갈래로 따로 센다: **검색엔진 단계**(검색기·임베딩·컷오프·코퍼스, 1~45단계)와 **청킹 단계**(문서를 청크로 나누는 방식, 1단계부터). 두 갈래는 번호가 겹치지 않게 각자의 목록과 폴더(`stages/`, `chunking-stages/`)를 가진다. 각 단계는 자체 문서를 갖고, 이 파일은 링크만 남긴다.
숫자가 내려간 이유가 검색 시스템의 회귀인지 평가셋이 더 어려워졌기 때문인지 구분할 수
있도록, 각 문서는 그 단계의 코퍼스와 질문 세트를 함께 기록한다.

읽기 전에 [공통 측정 조건과 재현](measurement_conditions.md)을 먼저 본다. 단계마다
코퍼스·평가셋·임베딩 모델이 달라, 조건을 모르면 단계 간 수치를 잘못 비교하게 된다.

단계 문서는 코드 반영 여부로 두 폴더에 나뉜다. `stages/applied/`는 검색 코드에 들어간 단계이고
(기본 꺼짐인 선택 기능 포함), `stages/not-applied/`는 기준선·측정·채택하지 않은 실험이다.
분류는 `config.py` 기본값과 `query.py`·색인 코드를 대조해 정했다(2026-09-29).
아래 목록은 단계 번호 순서를 그대로 유지하고, 링크가 어느 폴더를 가리키는지로 구분한다.

## 검색엔진 단계

- [1. 초기 기준선](stages/not-applied/stage-01-initial-baseline.md) — v1 키워드 50문항, 어휘 검색에 유리한 조건에서 출발한다
- [2. 자연어 기준선](stages/not-applied/stage-02-natural-language-baseline.md) — v2 자연어 40문항으로 바꾸자 dense·하이브리드의 약점이 드러난다
- [3. 최신 파서 재추출·재색인](stages/not-applied/stage-03-parser-reextraction.md) — 파서만 새로 돌려도 검색 성능은 거의 그대로다
- [4. 문서당 청크 여러 개 반환](stages/applied/stage-04-chunks-per-document.md) — 순위 단위는 두고 반환 단위만 분리해 근거 Recall을 올린다
- [5. 질의 재작성 융합](stages/applied/stage-05-query-rewrite.md) — 품질은 오르지만 검색이 0.6초가 되어 기본값은 꺼짐이다
- [6. 임베딩 모델 교체](stages/applied/stage-06-embedding-model.md) — `bge-m3`로 바꾸자 순위가 뒤집힌다. dense의 약세는 모델 선택의 결과였다
- [7. 모델 교체 후 질의 재작성은 남는가](stages/not-applied/stage-07-rewrite-after-model.md) — 재작성이 고치던 문제를 임베딩 모델이 이미 고쳤다
- [8. 120문항 평가셋과 문서당 청크 6개](stages/applied/stage-08-120q-chunks6.md) — 평가셋을 키우고 문서당 청크를 6으로 올린다
- [9. 식별자 질의 15문항 추가](stages/not-applied/stage-09-identifier-queries.md) — 식별자 구간에서 하이브리드가 무너지고, 컷오프가 정답을 잘라낸다
- [10. 학습형 sparse(bge-m3)를 어휘 경로로](stages/not-applied/stage-10-learned-sparse.md) — 정밀도를 맞추면 dense와 동률이다. 같은 비율로 모드를 비교하면 안 된다
- [11. Qwen3-Embedding-0.6B는 bge-m3를 넘는가](stages/not-applied/stage-11-qwen3-embedding.md) — 넘지 못한다. 남은 구멍은 임베딩 모델의 문제가 아니다
- [12. 구어체 어미가 검색을 망가뜨린다](stages/applied/stage-12-auxiliary-verb-stoptags.md) — 보조용언이 검색 토큰으로 남아 엉뚱한 1위를 만들고, 컷오프가 정답을 잘라낸다
- [13. dragonkue/BGE-m3-ko는 bge-m3를 넘는가](stages/applied/stage-13-bge-m3-ko.md) — 넘는다. 포화라고 봤던 구간이 실은 다국어 모델의 천장이었다
- [14. 절대 바닥값으로 한 번 더 자르기](stages/applied/stage-14-absolute-score-floor.md) — 도메인 밖은 전부 거르지만, 도메인 안의 무응답은 여전히 못 거른다
- [15. BGE-m3-ko 채택](stages/applied/stage-15-adopt-bge-m3-ko.md) — 변환본을 검증해 Ollama로 서빙하고, 바닥값을 다시 쟀다
- [16. 어휘 바닥값을 걷고 dense에 주제 판정을 맡긴다](stages/applied/stage-16-vector-decides-topicality.md) — BM25 바닥값은 관련성이 아니라 질의 길이를 재고 있었다. 해제는 되돌렸고, 노이즈 게이트로만 남긴다
- [17. BM25 대신 sparse를 섞으면](stages/not-applied/stage-17-sparse-instead-of-bm25.md) — 어휘 짝으로는 낫지만, 융합이 강점을 평균 내버린다
- [18. 도메인 안 무응답을 거를 수 있는가](stages/applied/stage-18-llm-answerability-judge.md) — 리랭커는 0/8, LLM 판정은 7/8. 관련도가 아니라 사실의 유무를 물어야 한다
- [19. 문서는 맞는데 청크가 틀렸다](stages/applied/stage-19-chunk-rerank-within-document.md) — 판정자 거짓 거절의 절반은 근거가 문서 내 7~21위로 밀려 안 보인 것이었다. 문서 내 재정렬로 14.8% → 7.4%
- [20. 진단이 맞으면 해법은 공짜였다](stages/applied/stage-20-dense-order-inside-documents.md) — 같은 진단이 cross-encoder 대신 밀집 순서를 가리키고 있었다. 지연 0으로 근거 `@1` +23.3p
- [21. 컷오프가 융합을 투표로 바꿔 놓고 있었다](stages/applied/stage-21-fusion-cutoff-and-judge-polarity.md) — RRF 점수에 비율 컷오프는 "두 검색기 모두에 있어야 한다"는 뜻이었다. P@1 +3.0p, Hit@5 +3.7p, 지연 0. 판정자 폴라리티 규칙 한 줄로 거짓 거절 5.9% → 3.7%
- [22. 어휘 검색이 본문 근거를 버리고 있었다](stages/applied/stage-22-most-fields-instead-of-best-fields.md) — `best_fields`가 문서를 단일 최고 필드로만 점수 내고 있었다. `most_fields` 한 단어로 Hit@5 +1.5p, 반환분 정밀도 +4.1p, 반환 수는 감소. bm25 단독은 17단계 sparse와 동률이 된다
- [23. 채점 단위를 청크로 옮겼다](stages/applied/stage-23-chunk-is-the-scoring-unit.md) — 검색이 아니라 재는 자를 바꿨다. 답변 모델이 받는 것은 문서가 아니라 청크이므로 근거 청크 지표가 주 지표이고 문서 지표는 진단용이다. 근거 Precision·MRR을 새로 더했다. 22단계 순위를 다시 재도 하이브리드 우위는 유지되고 더 선명해진다(문서 P@1은 dense와 동률이지만 근거 R@5는 +5.9p)
- [24. SPLADE를 현재 검색기와 같은 135문항에 세웠다](stages/not-applied/stage-24-splade-against-current-retrievers.md) — SPLADE+dense는 현재 BM25+dense보다 문서 P@1 94.8% → 97.8%, 청크 근거 Recall 91.1% → 94.1%로 오른다. 기존 판정표에 있는 청크만 비교하면 풀링 Precision 53.0% → 61.1%, 직접 답 Precision 31.4% → 38.1%다. 첫 근거 순위와 미판정 19%의 선택 편향, 온라인 비용은 남는다
- [25. core를 docs 질의셋에 섞으면 무엇이 깎이고, 왜 깎이는가](stages/applied/stage-25-core-corpus-against-docs-queries.md) — 검색기는 그대로 두고 읽는 별칭만 바꿨다. core를 섞으면 근거 Recall@5가 0.9630에서 0.9111로 5.2p 떨어지고 정답은 전부 색인 안에 있으므로 순위 문제다. 청크 폭주 4건, 컷오프, 시점 부스트, 청크 길이 불일치가 차례로 기각됐다(청킹을 docs 규약으로 맞춰 다시 잘라도 회복되지 않는다). 라벨 한계도 아니다 — 1위를 잃은 24건 중 22건이 진짜 오답이다. 원인은 **합치는 방식**이었다. 별칭 두 개를 한 질의로 던지면서 `search_type`을 지정하지 않아 IDF와 평균 길이가 인덱스마다 따로 계산된다(`러시아`는 docs 0.42%, core 5.54%). 손해는 어휘 검색기에서만 나고(bm25 −59, dense −9), 전역 통계로 bm25 63 → 92, hybrid 109 → 114다. 제목 증폭기까지 고치면 −17이 −7로 줄고 재청킹과 기존 청킹의 차이가 사라진다
- [27. 질의마다 검색 방식을 고르면 얻을 게 있는가](stages/not-applied/stage-27-retriever-routing.md) — 채택하지 않는다. docs-only 오라클도 hybrid 대비 근거 Recall@5 +3문항분뿐이고 식별자 규칙 라우터는 0.9037로 더 나쁘다. 문서 단위로 fold를 나눠 학습한 라우터도 hybrid를 넘지 못했다(docs-only −0.74%p, docs+Core +0.49%p, 구간이 0을 포함). 회수 가능한 손실은 문서 안 청크 선택 문제였다
- [28. `title^1`+다중 인덱스 DFS 랭커 판정과 반영](stages/applied/stage-28-title1-dfs-ranker.md) — 랭커를 고정하고 새 상위 결과의 라벨만 판정했다. 반환 문서 Precision@5가 docs +15.9p, holdout +7.0p 올랐고 근거 손실은 holdout-v1-004 한 문항이다. 혼합 코퍼스 평가기의 색인 범위 오류를 고치고 서버 반영을 확인했다
- [29. 새 검증 질문을 검색 전에 동결하고 평가](stages/not-applied/stage-29-independent-validation.md) — 36부모를 무작위로 뽑아 질문과 정답을 먼저 커밋했다. 반환 근거를 정답 대안으로 추가한 뒤 core+docs 1위 34/36이다. 남은 실패는 연도·보고 기간 혼동 두 문항이다
- [30. 연도·반기가 비슷한 문서를 구별한다](stages/applied/stage-30-period-disambiguation.md) — 질문에 적힌 연도·반기와 주제어가 제목과 맞는 후보로 세 번째 RRF 목록을 만들고, 이런 후보는 컷오프에서 보존했다. 날짜 진단 5위 내 10 → 14/14, CP 확인 4 → 8/8이고 docs 135·holdout 69는 반환 배열까지 그대로다
- [31. 전달 청크의 Precision을 올릴 수 있는가](stages/applied/stage-31-chunk-precision.md) — LLM 관련도 필터는 Recall 손실 없이 25.1% → 37.8%다. 점수 컷오프는 최고 68.9%로 80%에 못 미친다. 제목을 뺀 청크 점수는 더 나빴고, SPLADE는 95% 조건에서 청크 1위만 +2.2p다
- [32. core+docs에서 정답이 1위에 오지 않는 이유](stages/applied/stage-32-why-the-answer-is-not-first.md) — 정답은 대부분 후보 안에 있고, 1위를 뺏는 것은 같은 주제인데 답이 없는 문서다. 날짜를 모르는 문서에도 기간 가산점을 주는 것만 반영했다(docs 1위 0.837 → 0.844, 퇴행 없음). 컷오프 완화, FAQ 사본 병합, 부모 순위 RRF, 출처 설명 분리, LLM 재정렬은 기각했다. LLM 목록 선택은 개발 셋 근거 Recall을 0.919로 올리지만 동결 셋 1위는 52 → 53문항이고 질문마다 LLM 호출이 붙는다
- [33. 문서를 먼저 고르지 않고 청크를 먼저 고르면 나아지는가](stages/applied/stage-33-chunk-first-pipeline.md) — 문서 안 청크 순서(첫 청크는 dense, 나머지는 청크 RRF)만 반영했다(개발 셋 +4문항, 손실 0, 95% 구간 하한 0). 청크 우선 파이프라인은 만들었지만 기본 꺼짐이다. 예산·컷오프·문서 상한·합의 가산·트림 모두 같은 재현율–정밀도 곡선 위에 있고, 문서 우선과 같은 Recall에서 같은 문서 정밀도를 내지 못했다. 이득은 복수 근거 질의(0.776 → 0.81~0.86)뿐이다
- [34. 어휘 검색에서 효과 없는 장치를 걷어낸다](stages/applied/stage-34-drop-standard-fields.md) — 넣고 뺀 차이가 개발 셋에서 한두 문항이고 방향이 엇갈린다. 식별자 질문 22개에서는 있는 쪽이 1문항 앞섰지만(127) 표본이 작아 쿼리에서 뺐다. 색인에 값이 없어서 작동하지 않던 문서 종류 부스트도 지웠다(현행판 우대는 상수 +4로 작동해 유지)

- [37. 카테고리를 고르고 검색하는 경로를 만들고, 법령·고시에서 SPLADE·컷오프·실패 원인을 쟀다](stages/applied/stage-37-law-category-search.md) — 카테고리별 인덱스(`search-law`, 청크 673개)와 카테고리 ID를 받는 범용 API·화면을 붙였다. `.env`의 docs v2 기준 BM25 하한(14.75)이 이 인덱스에서 BM25 결과를 비웠고(21문항 중 10문항 빈 결과) 답변 가능성 판정도 기각을 일으켜 카테고리 경로에서는 끈다. 질문 21개(본문을 보고 쓴 점검용): 근거 Recall dense 0.952, hybrid 0.905, bm25 0.762. 오프라인으로 잰 결과 창 크기를 맞추면 SPLADE가 BM25보다 낫고(약 6청크 0.905 대 0.667) BM25를 SPLADE에 더해도 좋아지지 않으며 SPLADE+dense가 대부분의 창 크기에서 가장 낫거나 같다(차이 1~2문항). 문서 인코딩 512토큰은 변화 없음. 못 싣는 이유는 라벨 2, 청킹 1(번호 목록 분할로 조문 제목 소실), SPLADE 코드 토큰 약점 1. 서비스에는 붙이지 않았다. 같은 경로로 행정·업무 카테고리(`search-admin`, 청크 183개)도 붙여 질문 30개(본문을 보고 쓴 점검용)로 같은 측정을 했다: 근거 Recall dense 0.933, hybrid 0.933, bm25 0.833, 같은 창 크기에서 SPLADE가 BM25보다 높고(약 3청크 0.900 대 0.833) 차이는 한두 문항이다. 읽은 실패 4문항은 청킹 1(표 제목이 앞 청크로 넘어감), 옛 판이 최신 판보다 앞섬 1, 문서 안 청크 순위 2이고, 문서 단위 오답은 모두 옛 판이 1위였다(카테고리 인덱스에는 최신 판 처리가 없음)
- [39. BM25·dense 후보 수를 바꿔 보고 dense를 25개로 낮춘다](stages/applied/stage-39-candidate-counts.md) — BM25 5~100개 × dense 10~200개 25조합을 docs_v2 135문항으로 재면 25개 이상에서 지표가 소수점까지 같고(문서 P@1 95.6, 근거 Recall 95.6) 줄여도 떨어지지 않는다. 성능이 같아 dense 후보 기본값을 50에서 25로 낮췄다. 개발 셋 한 곳만 썼고 지연은 재지 않았다
- [40. SPLADE(C)+dense 융합 방식을 재 보고, 카테고리 청크 RRF의 k와 행정·업무 Precision 원인을 가렸다](stages/not-applied/stage-40-rrf-fusion-variants.md) — RRF k(30/60/100), SPLADE 가중 RRF(0.5/1.5), 점수합(CombSUM 방식)을 docs_v2 135·holdout-small 69에서 비교했다. k는 최종 비율 컷오프 때문에 이 범위에서 무의미하고, SPLADE 가중치를 올리면 문서 P@1이 떨어지며(0.963 → 0.933), 점수합은 RRF와 사실상 같다(청크 MRR +0.004~0.015, 잡음 수준). 반영하지 않는다. 카테고리 코퍼스(청크 단위 RRF, 95% 컷오프)에서는 행정·업무 Precision(0.525)이 낮은 것이 문서당 한도·예외 규칙이 아니라 RRF가 순위만 써서 95% 컷오프가 두 목록 상위 4~5위를 그대로 통과시키기 때문임을 가렸고, k를 줄이면 Precision은 오르지만(행정 0.525 → 0.778) 정답 청크를 반환하는 질문이 줄어(27 → 22/30) 한 값으로 세 카테고리를 맞출 수 없었다. 반영하지 않는다
- [41. 법령·고시 코퍼스가 50건에서 100건으로 늘어, 새 50건으로 질문 50개를 더 써서 100문항으로 다시 쟀다](stages/applied/stage-41-law-100-doc-growth.md) — `search-law`를 100건(청크 4,633개)으로 재색인하고 새 50건에 질문 50개를 더해 기존 50문항과 합쳐 100문항으로 쟀다. 서비스 경로(청크 컷오프 0.95) hybrid 청크 Recall 0.910, Precision 0.558(평균 3.4청크), 문서 Hit 97/100(컷오프 0이면 0.940/0.235). 놓친 질문 중 일부(splade 3, dense·hybrid 4)는 정답 문서는 상위 5위 안인데 정답 청크가 문서당 6청크 한도 밖으로 밀린 것이고, 나머지는 정답 문서 자체를 놓쳤다. 공통으로 걸리는 몇 질문은 37단계에서 적은 "같은 조항이 여러 판에 있다" 문제의 재현으로 보인다(전수 확인은 아님). 운영 설정은 바꾸지 않았다

- [42. 제목 경로를 SPLADE에 추가하고 dense에서 제거해 비교](stages/applied/stage-42-heading-path-input-ablation.md) — 법령 100·행정 30문항에서 입력만 바꿨다. SPLADE 경로 추가는 법령 단독 근거 회수 92→94/100, hybrid 91→89/100이고 행정은 둘 다 27→27/30이다. hybrid 손실 2건은 RRF 95% 컷오프와 대체 연결 문서 삽입 뒤의 5문서 상한에서 발생했다. dense 경로 제거는 단독 법령 90→89/100·행정 28→27/30, hybrid는 91→91/100·27→27/30이다. SPLADE 경로 추가 수치는 실험 스크립트의 갱신 병합 버그로 부풀어 있었고(재색인 실측은 법령 SPLADE 91→90, hybrid 89→87) 처음에는 기본값을 유지했으나 2026-10-07에 사용자 결정으로 SPLADE·dense 모두 경로를 넣는 입력으로 확정하고 법령·행정을 재색인했다
- [43. 임베딩 입력에 메타데이터 필드를 하나씩 넣어 법령 검색을 비교](stages/not-applied/stage-43-embedding-field-ablation.md) — 법령 100문항에서 문서종류·판본·발급기관·번호·공포일·개정일·시행일·대체 고시·표 열·표 제목 10개를 dense와 SPLADE 입력에 한 번에 하나씩 더했다(컷오프 0.95 hybrid 기준 91/100). 20개 arm의 hybrid 회수는 88~92/100으로 한 문항 차이가 잡음 범위이고, SPLADE에 넣으면 hybrid가 내려가는 경향(최대 −3), dense는 중립이다. 같은 질문으로 고른 조합도 92/100(MRR 0.798→0.823)이라 반영하지 않는다.
- [44. 판본을 지정하지 않은 질문에서 대체된 문서의 청크 점수를 깎아 봄](stages/applied/stage-44-superseded-edition-weight.md) — 법령 100문항 hybrid(컷오프 0.95)에서 `superseded_by`가 있는 문서의 청크 RRF 점수에 가중치를 곱했다. 가중치 0.97에서 청크 Recall 91→92/100, MRR 0.793→0.807, Precision(하한) 0.558→0.561, 반환 문서 중 대체된 문서 질문당 1.04→0.89개로 효과가 한 문항 수준이고, 0.90 이하는 Precision이 내려간다. 정답 문서의 42%가 대체된 문서라 라벨과 어긋나기 쉽다. 행정은 대체된 문서가 0개라 동작하지 않는다. 선택 기능(기본 꺼짐)만 반영한다.
- [45. 번호로 적힌 대체 관계를 문서 ID로 풀어 새 판 추가를 시험](stages/not-applied/stage-45-resolved-edition-pointers.md) — 법령 100문서에서 `superseded_by`가 번호인 16문서를 부모 ID로 풀고 새 판 추가가 도움이 되는지 쟀다. 40개 질문에 새 판이 붙었지만 붙은 청크 중 정답은 0개였고, 청크 Precision(하한)이 0.558→0.504로 내려갔다(Recall 91→90). 이미 켜진 새 판 추가(ID 6개)도 끄면 Precision이 0.558→0.569로 오른다. 반영하지 않는다.

- [46. 법령 명시 근거 일치 가산점](stages/applied/stage-46-law-explicit-evidence-ranking.md) — SPLADE·dense 각 25개와 추가 조회 0개로 고정하고, BM25 없이 근거 일치 가산점만 적용해 근거 반환 144→147/149, 청크 Precision 하한 0.231→0.255. 첫 문서 적중은 129→128. 037·075·076을 회수하며 043·125는 남는다.

## 청킹 단계

청킹 방식(문서를 청크로 나누는 규칙, 입력, 정책 값)을 바꾸고 잰 기록이다. 검색엔진 단계와 번호를 따로 센다. 단계 문서는 `chunking-stages/`에 두고, 코드 버전별 숫자는 [청킹 버전 기록](chunking_versions.md)에 남긴다.

- [청킹 1. 청킹을 파서에서 검색엔진으로 옮기고, 옮기기 전과 카테고리 검색을 비교](chunking-stages/stage-01-move-chunking-to-search-engine.md) — 이식은 번들 189문서 모두 파서의 청크와 같다. 법령 149문항 정답 청크 반환은 옮기기 전 145 → 139(컷오프 0.7)로, 이식이 아니라 파서의 규칙 20개 삭제와 코퍼스 내용 차이 때문이다

- [청킹 2. 제목 메타데이터와 짧은 절 경계 보존](chunking-stages/stage-02-common-boundaries.md) — v2 대비 v5의 법령 149문항·행정 30문항 검색 지표는 동일했다. 법령 청크는 6,503 → 6,517이며 제목 페이지·원소 종류와 독립 절의 경로를 보완했다.

## 단계에 걸친 문서

- [청킹 버전 기록](chunking_versions.md) — 청킹 단계의 코드 버전별 정책값·코퍼스 통계·검색 결과
- [공통 측정 조건과 재현](measurement_conditions.md) — 측정 조건과 각 단계를 다시 만드는 명령
- [단계 1~7 한눈에 보기](stages_1_7_overview.md) — 일곱 단계를 같은 표에서 비교한다
- [단계 2~7 근거 청크 지표](evidence_chunk_metrics_v2.md) — 문서가 아니라 답이 적힌 청크가 반환됐는지를 따로 측정한다
- [현재 판단과 다음 측정](current_judgment.md) — 지금까지 확정된 것과 아직 재지 않은 것
- [앞으로 시도할 방법](next_ideas.md) — 단계 문서에 기록이 없는 개선 후보. 측정 전 가설이다
- [판정자 프롬프트 스윕](judge_prompt_sweep.md) — 다섯 프롬프트로 거짓 거절 8→1까지 움직였지만 무응답 포착은 22/26에서 꿈쩍하지 않는다. 채택한 것은 없다
- [컷오프 비율 스윕](cutoff_precision_sweep.md) — 비율별 반환분 정밀도 곡선
- [v1 기준선](baseline_v1.md) — v1 평가셋 자체의 기록

- [법령·고시 150문서 재평가 (2026-10-07)](law150_search_2026-10-07.md) — 6,288청크 재색인, 기존 100문항 + 신규 50문항(근거 불완전 1문항 제외). 최종 근거 회수는 SPLADE 135/149, dense·hybrid 137/149. 새 50문항의 hybrid는 48/50이며, 코퍼스·청킹이 바뀌어 과거 100문항 수치와 직접 비교하지 않는다.
- [SPLADE 문서 최대 길이 비교 (2026-10-08)](splade_doc_length_2026-10-08.md) — 법령 6,503청크·149문항에서 문서 길이 256/512/1024를 비교했다. 512는 근거 회수를 소폭 높였지만 대응 bootstrap 구간에 0이 포함됐고, 1024는 추가 이득이 없었다.
