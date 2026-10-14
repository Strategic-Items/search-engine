"""LLM 기반 표(Table) 청킹 및 안전한 폴백(Graceful Fallback) 모듈.

- LLM 스위치가 켜져 있고 서버가 정상이면: 계층 헤더와 병합 셀(rowspan, colspan)을 복원한 원자 청크 생성
- LLM 스위치가 꺼져 있거나 서버 장애/타임아웃 시: None을 반환하여 기존 규칙 기반 표 청킹으로 자동 폴백
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from search_engine.chunking.params import ChunkPolicy

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 법령 및 행정 고시의 복잡한 표(HTML Table)를 검색 엔진(SPLADE, Dense Retrieval)에 최적화된 독립된 원자 청크(Atomic Chunk)로 분할/직렬화하는 전문가입니다.

[청킹 원칙]
1. 언어 100% 보존 (절대 규칙): 절대로 중국어나 영어 등 다른 언어로 번역하지 마세요. 표의 모든 품목명, 법령 용어, 수치, 단위는 원문의 한국어 텍스트 그대로 보존해야 합니다.
2. 계층 헤더 및 병합 셀 복원: rowspan, colspan으로 병합된 상위 분류나 공통 컬럼(수출 지역, 법령 구분 등)을 하위 행마다 빠짐없이 복원하여 주입하세요.
3. 독립적 검색 가능성: 각 청크만 떼어놓고 보아도 전체 표의 맥락(표 제목, 대분류, 상세 항목)을 즉시 이해할 수 있는 완전한 문맥으로 만드세요.
4. 토큰 최적화: 불필요한 마크업을 제거하고, 핵심 정보만 밀도 있게 표현하세요.
5. 출력 형식: 반드시 순수 JSON 형식으로만 응답하세요:
{
  "chunks": [
    {
      "chunk_id": 1,
      "category_path": "상위경로 > 하위항목",
      "summary": "1줄 핵심 요약",
      "text": "검색 인덱싱용 상세 본문 (원문 한국어 단어 유지)"
    }
  ]
}
"""


def _get_endpoint(policy: ChunkPolicy) -> str:
    if policy.llm_table_endpoint:
        base = policy.llm_table_endpoint.rstrip("/")
    else:
        # 기본값: 설정 또는 로컬/Tailscale Ollama
        try:
            from search_engine.config import get_settings
            settings = get_settings()
            base = getattr(settings, "chunking_llm_endpoint", None) or settings.ollama_base_url
        except Exception:
            base = "http://100.120.44.11:11434"
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return f"{base}/chat/completions"


def _slice_large_table(table_html: str, max_chars: int = 2500) -> list[str]:
    """긴 HTML 표를 헤더를 유지한 채로 적절한 크기의 서브 테이블 목록으로 분할합니다."""
    if len(table_html) <= max_chars or "<tr" not in table_html:
        return [table_html]

    import re
    # <tr> 태그 단위로 분할
    rows = re.findall(r"<tr.*?>.*?</tr>", table_html, flags=re.DOTALL | re.IGNORECASE)
    if len(rows) <= 3:
        return [table_html]

    header_row = rows[0]
    data_rows = rows[1:]

    slices = []
    current_rows = []
    current_len = len(header_row)

    for r in data_rows:
        if current_rows and (current_len + len(r) > max_chars):
            sub_tbl = f"<table>\n{header_row}\n" + "\n".join(current_rows) + "\n</table>"
            slices.append(sub_tbl)
            current_rows = [r]
            current_len = len(header_row) + len(r)
        else:
            current_rows.append(r)
            current_len += len(r)

    if current_rows:
        sub_tbl = f"<table>\n{header_row}\n" + "\n".join(current_rows) + "\n</table>"
        slices.append(sub_tbl)

    return slices


def chunk_table_with_llm(
    table_text: str,
    title: str = "",
    *,
    policy: ChunkPolicy,
    heading_path: list[str] | None = None,
    page_start: int = 1,
    page_end: int = 1,
) -> list[dict[str, Any]] | None:
    """
    LLM을 호출하여 표를 원자 청크들로 분할합니다.
    - policy.use_llm_tables가 False이거나,
    - 글자 수가 policy.llm_table_min_chars 미만이거나,
    - LLM 호출에 실패/타임아웃이 발생하면
    안전하게 None을 반환하여 호출자가 기존 규칙 기반 청킹으로 폴백하도록 합니다.
    """
    if not policy.use_llm_tables:
        return None

    # 너무 작은 표는 굳이 LLM을 태우지 않음
    clean_text = table_text.strip()
    if len(clean_text) < policy.llm_table_min_chars:
        return None

    # 대형 표(3,000자 초과)의 경우 행(<tr>) 단위로 분할하여 서브 테이블로 호출
    sub_tables = _slice_large_table(clean_text, max_chars=2500)
    endpoint = _get_endpoint(policy)
    all_chunks_data: list[dict[str, Any]] = []

    for sub_tbl in sub_tables:
        prompt = f"[표 제목]: {title}\n[표 원문]:\n{sub_tbl}\n\n위 표를 분석하여 병합 셀을 전개하고 독립 검색 청크(JSON)로 분할하세요."
        payload = {
            "model": policy.llm_table_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=policy.llm_table_timeout) as res:
                data = json.loads(res.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    all_chunks_data.extend(parsed)
                elif isinstance(parsed, dict):
                    all_chunks_data.extend(parsed.get("chunks", []))
        except Exception as e:
            logger.warning("서브 표 청킹 중 오류 발생 (%s): %s", title, e)
            return None

    chunks_data = all_chunks_data
    if not chunks_data:
        return None

    base_path = list(heading_path or [])
    results: list[dict[str, Any]] = []

    for item in chunks_data:
        text = (item.get("text") or "").strip()
        if not text:
            continue

        sub_path = item.get("category_path")
        current_path = [*base_path]
        if sub_path:
            current_path.extend([p.strip() for p in sub_path.split(">") if p.strip()])

        results.append({
            "text": text,
            "heading_path": current_path,
            "element_types": ["table"],
            "page_start": page_start,
            "page_end": page_end,
            "llm_chunked": True,
            "table_title": title,
            "summary": item.get("summary", ""),
        })

    return results if results else None

