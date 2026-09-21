"""채팅 모델에게 검색된 텍스트가 실제로 질문에 답하는지 묻는다.

점수 기준값은 이를 할 수 없다. 코퍼스가 답할 수 없는 질문은 여전히 그것에 관한 문서를 검색하고, 답이 있는 질문들이 차지하는 범위 내에서 점수를 매긴다 -- docs v2에서 8개의 도메인 내 비답할 수 있는 질문 중 0개가 절대 하한선에 의해 거부되었고, 0개가 크로스엔코더 재순위付け 랭커에 의해 거부되었으며, 점수 갭이나 결과 수로는 답이 있는 질문들과 구별되지 않았다. 그들을 구분하는 것은 관련성(그들은 관련성이 있다)이 아니라, 질문이 요구하는 사실이 조각들에 기록되어 있는지 여부이다. 오직 독자만이 이를 알 수 있다.

따라서 모델에게 제기되는 질문은 "이것이 관련이 있는가?"가 아니라 "이 질문이 요구하는 사실이 이 텍스트에 존재하는가?"이다. 그렇게 측정했을 때, 8개 중 7개를 거부했으며, 그代价로 코퍼스가 답할 수 있는 질문의 14.8%를 거부했다 (docs/evaluation/stages/stage-18-llm-answerability-judge.md).

기본적으로 비활성화되어 있다. 이는 검색 경로에 채팅 모델을 포함시키는 것이며, 그렇지 않으면 모델 의존성이 없는 검색에 비해 약 2초의 비용이 든다 -- 이는 쿼리 리라이트를 비활성화하는 것과 동일한 Trade-off이다.
"""

import json
import logging

from search_engine.config import Settings, get_settings
from search_engine.rag.llm import generate
from search_engine.search.results import SearchHit

log = logging.getLogger(__name__)

# 규칙은 각각의 턴에 들어간다. 사용자 턴에 접혀지면, 동일하다
# 모델은 14.8%에 비해 20.7%의 답할 수 있는 질문을 거부했다.
#
# 두 번째 규칙은 극성에 관한 것이다. 이 규칙이 없으면 판독자는 질문을 거부했다
# 그 질문의 답변을 방금 인용한 질문을
# 동일한 사양이 미국 라이선스를 요구하는지 묻는다면, 그 답변은 "그러한 진술이 존재하지 않는다"라고 했고, 그리고
# 사실은 텍스트가 그 근거로 라이선스를 신청할 필요가 없다고 말한다" --
# 그리고 응답 가능한: false. "이 사실이 이 질문이 요구하는가?"
# "쓰여진다"는 것은 질문의 전제를 그 사실로 읽도록 유도하므로, 하나의
# 전제를 부정하는 문서는 그것에 대해 침묵하는 문서처럼 보인다.
# 이 잃어버린 모든 질문은 예/아니오 질문이었고 그 답은 아니었다.
SYSTEM = """당신은 검색 결과를 검수한다. 주어진 발췌문만 보고, 질문이 요구하는 사실이 그 안에 실제로 적혀 있는지 판단한다.
- 주제가 같아도 요구된 사실이 없으면 답할 수 없는 것이다.
- 질문이 어떤 내용의 성립 여부를 묻고 발췌문이 그것을 부정하고 있으면, 답할 수 있는 것이다. 질문의 전제를 뒤집는 근거도 근거다.
- 집계 결과, 실시간 현황, 개인별 처리 상태처럼 문서가 담지 않는 종류는 답할 수 없다.
- 추측하거나 상식으로 보충하지 않는다.
JSON만 출력한다: {"answerable": true|false, "confidence": 0.0~1.0, "reason": "한 문장"}"""

PROMPT = """질문: {query}

발췌문:
{context}"""

# 판사가 각 문서의 얼마나 많은 부분을 보는가. 이것을 잘라내는 것은 중립적인
# 조절 장치가 아니다: 맥락을 3분의 1로 줄이면 거짓 거부율이 135개 중 26개에서 51개로 상승한다.
# 왜냐하면 문서가 라벨링된 증거가 종종 그 밖에 위치하기 때문이다
# 첫 번째 청크들 -- 파이프라인이 문서당 여섯 개를 유지하는 이유와 동일하다.
DOCUMENTS_JUDGED = 3
BODY_CHARS = 1500
PASSAGES_PER_DOCUMENT = 5
PASSAGE_CHARS = 1200


def _context(hits: list[SearchHit]) -> str:
    blocks = []
    for hit in hits[:DOCUMENTS_JUDGED]:
        parts = [f"[{hit.title}]"]
        if hit.body:
            parts.append(hit.body[:BODY_CHARS])
        parts += [p.body[:PASSAGE_CHARS] for p in hit.passages[:PASSAGES_PER_DOCUMENT] if p.body]
        blocks.append("\n".join(parts))
    return "\n\n---\n\n".join(blocks)


def is_unanswerable(
    query: str, hits: list[SearchHit], settings: Settings | None = None,
) -> bool:
    """모델이 검색된 텍스트에서 질문에 대한 답변을 하지 않는다고 말할 때 참이다.

    판결은 그대로 받아들여진다. 모델은 자신의 신뢰도를 평가하며,
    한 실행에서 그 수치는 사용 가능해 보였다 -- 정확한 거절은 약 0.10,
    잘못된 거절은 약 0.85이며, 낮은 수치만을 존중하면 거짓 거절을 14.8%에서 2.2%로 줄일 수 있었다. 그러나 이는 재현되지 않았다. 동일한 쿼리가 동일한 패스를 대상으로 한 번은 0.10, 다음 실행에서는 0.85로 돌아왔기 때문이다. 제공되는 모델의 출력은 요청이 배치되는 방식에 따라 변하기 때문이다. 판결 자체는 모든 반복에서 안정적이었다. 따라서 불리언 값이 사용되며 수치는 무시된다.

    결코 예외를 발생시키지 않는다. 도달할 수 없는 판사가 판결이 아니며, 이미 무언가를 찾은 검색은 두 번째 의견이 없어서 실패해서는 안 된다.
    """
    settings = settings or get_settings()
    if not hits:
        return False
    try:
        raw = generate(PROMPT.format(query=query.strip(), context=_context(hits)),
                       temperature=0.0, max_tokens=200, settings=settings,
                       system=SYSTEM, json_object=True)
        answerable = json.loads(raw)["answerable"]
    except Exception as exc:
        log.warning("answerability judge unavailable, keeping results: %s", exc)
        return False
    return answerable is False
