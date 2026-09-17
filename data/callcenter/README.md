# 상담 통화 STT 데이터 — 검색엔진 연동 테스트용 샘플

- 작성: 석수호 (STT 파트) · 2026-09-17
- 목적: 상담 통화 음성을 STT로 텍스트화하고 요약·분류·엔티티를 붙인 데이터를 OpenSearch에 색인해 보는 연동 테스트
- **테스트용 가상 데이터**: 전략물자 상담 5건. yesTrade 공개 FAQ를 바탕으로 쓴 대본을 한 사람이 녹음한 것이라 실제 상담 기록이 아니고, 개인정보도 없음

## 파일

| 파일 | 문서 수 | 문서 1개 단위 | 용도 |
|---|---|---|---|
| `calls.jsonl` | 5 | 통화 1건 | 통화 단위 조회 (요약·분류·엔티티·Q&A) |
| `chunks.jsonl` | 12 | 통화의 일부 구간 (약 300자, 앞 청크와 50자 겹침) | 본문 검색 |

- 형식: UTF-8 JSONL (한 줄에 문서 하나)
- 문서 ID로 쓸 필드: 통화는 `call_id`, 청크는 `chunk_id` (중복 없음, 다시 처리해도 같은 ID)
- 연결 관계: `chunk.call_id` → `call.call_id`, `call.chunk_ids` → `chunk.chunk_id`
- `seg_ids`(s0, s1, …)는 STT 원문 문장 번호. 원문 문장·타임스탬프 데이터(segment, 101건)는 따로 있음. 검색 결과에서 원문 위치를 보여줄 때 필요하면 드릴게요

## chunk 문서 (`chunks.jsonl`)

| 필드 | 타입 | 설명 | 매핑 제안 |
|---|---|---|---|
| `chunk_id` | string | 청크 ID (`sg01#c0`) | keyword, 문서 ID |
| `call_id` | string | 소속 통화 ID | keyword |
| `seq` | int | 통화 안에서 청크 순서 (0부터) | integer |
| `text` | string | **청크 본문** (정제된 STT 텍스트, 화자 구분 없음) | text (nori), 임베딩 대상 후보 |
| `char_len` | int | 본문 글자 수 | integer |
| `start_sec` / `end_sec` | float | 음성에서 청크 시작·끝 (초) | float |
| `seg_start` / `seg_end` / `seg_ids` | string / string[] | 청크에 포함된 원문 문장 번호 | keyword (색인 불필요) |
| `keywords` | string[] | 청크 키워드 (형태소 분석 + KeyBERT) | keyword 또는 text |
| `categories` | string[] | 통화의 상담 유형 (통화에서 상속, 첫 번째가 주 유형) | keyword, 필터용 |
| `call_inquiry` | string | 통화의 문의 요약 한 문장 (검색 결과에 "무슨 통화인지" 표시용) | text |
| `entities` | object[] | 이 청크 구간에 나온 엔티티 (아래 참고) | nested 또는 object |
| `doc_type` | string | 항상 `"chunk"` | keyword |
| `condition`, `pipeline_version` | string | 처리 조건·버전 (내부 추적용) | 색인 불필요 |

## call 문서 (`calls.jsonl`)

| 필드 | 타입 | 설명 | 매핑 제안 |
|---|---|---|---|
| `call_id` | string | 통화 ID | keyword, 문서 ID |
| `text` | string | 통화 전체 텍스트 (정제된 STT, 화자 구분 없음) | text (nori) |
| `summary_text` | string | 요약 (문의 + 안내 + 결과를 이어 붙인 것) | text (nori), 임베딩 대상 후보 |
| `summary` | object | 요약을 `inquiry` / `answer` / `result`로 나눈 것. 각각 `text`, `seg_ids` | object (text만 색인) |
| `categories` | string[] | 상담 유형, 첫 번째가 주 유형 | keyword, 필터용 |
| `category_details` | object[] | 유형별 `category`, `reason`(판단 이유), `evidence_seg_ids` | object, 색인 불필요 |
| `entities` | object[] | 엔티티 목록 (아래 참고) | nested 또는 object |
| `keywords` | string[] | 통화 키워드 (LLM 추출) | keyword 또는 text |
| `qa_pairs` | object[] | 통화 속 질문·답변 쌍. `question`, `answer`, `seg_ids` | nested 또는 object |
| `duration_sec` | float | 통화 길이 (초) | float |
| `source` | string | 데이터 출처 (`sg_script` = 가상 대본 녹음) | keyword |
| `audio_file` | string | 원본 음성 파일명 (현재는 파일명만, 저장 위치는 미정) | keyword, 색인 불필요 |
| `processed_at` | string | 처리 시각 (`2026-09-17T04:03:21`, 시간대 없음) — **통화 일시가 아님** | date |
| `seg_ids`, `chunk_ids` | string[] | 원문 문장 번호 목록, 소속 청크 ID 목록 | keyword, 색인 불필요 |
| `doc_type`, `condition`, `pipeline_version`, `stt_model`, `llm_model` | string | 처리 정보 | 색인 불필요 |

## entities 항목 구조 (call·chunk 공통)

```json
{"type": "통제번호", "mention": "3A001", "normalized": "3A001", "seg_ids": ["s3"]}
```

- `type`: 품목 / 통제번호 / HS코드 / 국가 / 기관 / 법령·조항 / 업무·절차 / 서류 / 기간·날짜 / 금액·수량 / 사양·수치 / 시스템·메뉴 / 상품·서비스 / 장소 / 기타
- `mention`은 원문에 나온 표현, `normalized`는 정리한 값 (예: `예스트레이드` → `Yestrade`). 검색·필터에는 `normalized` 추천
- "유형이 통제번호이고 값이 3A001인 문서"처럼 type과 값을 **짝지어** 검색하려면 nested 매핑이 필요

## 알고 쓰셔야 할 점

- **STT 오류가 그대로 들어 있음**: 예) sg01의 통제번호가 실제 2B001인데 `22001`로 저장됨, 기관명이 "무효관복 원리원"(무역안보관리원)으로 인식된 문장도 있음. 요약·엔티티는 원문에 근거가 있는 값만 남겼지만, STT가 틀리게 받아쓴 값은 걸러지지 않음
- **상담 유형은 임시 분류** (지정 / 판정 / 허가 / 신고 / 보고 / 기타). 공식 분류 체계가 정해지면 바뀜
- **통화 일시, 업체·고객 식별자 없음**: 실제 녹음·상담 기록 DB가 연결되면 추가 예정
- **필드명은 임시** (영문 snake_case). 기관 데이터 표준(DAR-001)에 맞춰야 하면 바뀔 수 있음
- 화자(상담원/고객) 구분이 없음 (화자분리를 하지 않는 구성)
- 청크끼리 50자씩 겹쳐서 같은 문장이 인접한 두 청크에 모두 검색될 수 있음

## 확인 부탁드릴 것

1. 청크와 통화 중 어느 단위로 색인하실지 (둘 다 / 청크만)
2. 임베딩을 어느 필드로 만드실지 (`chunk.text`, `call.summary_text` 등), 모델·차원
3. 매핑하면서 빠졌거나 바꿔야 할 필드
4. 이미 연동된 공지 데이터와 같은 인덱스에 넣는지. 같이 넣는다면 공지와 통화 사례를 구분하는 필드를 맞추고 싶습니다 (통화는 공식 근거가 아니라 과거 사례로 보여줘야 해서)
5. segment(원문 문장·타임스탬프) 데이터도 필요하신지
