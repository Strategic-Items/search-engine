"""Markdown을 청크로 분할. `unstructured-doc-parser_ver2`의 `chunking/chunker.py`를 이식했다
([청킹을 검색엔진으로 옮긴다](../../docs/design/chunking_ownership_move.md)).

원래 계획은 마크다운 헤더(#, ##)로 1차 분할하는 것이었는데, 처음 파서 출력을 까봤을 땐(2026-09-15)
**HWPX/PDF 출력엔 헤더가 거의/전혀 없었다**(python-hwpx의 `doc.text.markdown()`은 헤더를 안 만들고,
`pdf_parser.py`도 헤더를 생성하지 않았음). HWP(unhwp) 출력에만 `##`/`####` 헤더가 간헐적으로
나오는데 그마저도 모든 조항에 일관되게 붙지는 않았다.

그래서 헤더만으로는 부족하다고 보고, 공고문/법령 문서에서 실제로 일관되게 나타나는 구조 마커
(제N조, 최상위 번호 "1.", 하위 번호 "가."/"나.")를 헤더 다음 우선순위 구분자로 추가한
[langchain-text-splitters](https://pypi.org/project/langchain-text-splitters/)의
`RecursiveCharacterTextSplitter`(`is_separator_regex=True`)를 쓴다. 큰 구조 단위를 우선 유지하고,
chunk_size를 넘는 조각만 더 잘게 재귀 분할한다. 표는 앞뒤가 빈 줄(`\\n\\n`)로 둘러싸여 있어서(파서
출력 공통 패턴, 2026-09-15 확인) chunk_size보다 작은 표는 대체로 통째로 남고, chunk_size를 넘는
표만 행 단위(`\\n`)로 쪼개진다.

**2026-09-16 갱신**: HWPX(실제 "개요" 스타일 메타데이터 기반)와 PDF(글자 크기 비율 휴리스틱)도
이제 헤더를 만든다. 그래서 지금은 4개 포맷 다 어느 정도 헤더가 섞여 있지만, 조항/번호 구분자는
여전히 헤더가 없거나 듬성듬성한 문서를 위한 안전망으로 남겨뒀다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter

from search_engine.chunking.params import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, DEFAULT_MIN_CHUNK_CHARS

# 우선순위 순서: 큰 구조 단위 -> 작은 구조 단위 -> 일반 텍스트 경계.
# 전부 정규식으로 취급되므로(is_separator_regex=True) 리터럴 문자는 이스케이프한다.
# langchain이 각 구분자를 캡처 그룹으로 감싸기 때문에(`(separator)`), 전역
# `(?m)` 플래그는 "맨 앞에 와야 한다"는 Python 3.11+ 제약에 걸린다 -- 그룹에
# 스코프가 한정되는 `(?m:...)` 형태를 대신 쓴다.
_KOREAN_LEGAL_SEPARATORS = [
    r"(?m:^#{1,6}\s+)",          # 마크다운 헤더 (있을 때만, HWP 출력 일부)
    r"(?m:^제\d+조)",            # 조항 (제1조, 제2조 ...)
    r"(?m:^\d+\.\s)",            # 최상위 번호 항목 (1. 2. 3. ...)
    r"(?m:^\s{0,4}[가-힣]\.\s)", # 하위 번호 항목 (가. 나. 다. ...)
    r"\n\n",                     # 문단 구분
    r"\n",                       # 줄바꿈 (표 행 등)
    r"\.\s",                     # 문장 끝 추정
    r"\s",
    r"",
]


@dataclass
class Chunk:
    chunk_id: str
    text: str
    order: int
    metadata: dict = field(default_factory=dict)


def _merge_tiny_pieces(texts: list[str], min_chars: int) -> list[str]:
    """min_chars보다 짧은 조각(주로 본문과 분리된 제목/조항 헤더)을 다음 조각과 합친다. 헤더 한 줄만
    있는 청크는 그 자체로는 검색에 쓸모가 없어서(2026-09-15, 실제 코퍼스에서 737개 중 25개=3.4% 발견)
    뒤 내용과 묶는다 -- 헤더는 보통 뒤에 오는 내용을 설명하므로 앞이 아니라 뒤와 합치는 게 의미상 맞다.
    """
    merged: list[str] = []
    pending = ""
    for text in texts:
        candidate = f"{pending}\n\n{text}" if pending else text
        if len(candidate) < min_chars:
            pending = candidate
            continue
        merged.append(candidate)
        pending = ""
    if pending:
        if merged:
            merged[-1] = f"{merged[-1]}\n\n{pending}"
        else:
            merged.append(pending)
    return merged


_HEADING_PATTERN = re.compile(r"^(#{1,6}\s.+|\**제\d+조[^\n]*)")


def _extract_heading(text: str) -> str | None:
    """청크 맨 앞이 헤더/조항 표기면 그 줄을 `heading` 메타데이터용으로 뽑는다."""
    match = _HEADING_PATTERN.match(text)
    return match.group(0).strip() if match else None


def build_chunks(texts: list[str], strategy: str, reasons: list[str] | None = None) -> list[Chunk]:
    """텍스트 조각 리스트를 공통 메타데이터(전략 이름·헤더·길이)가 붙은 `Chunk` 리스트로 만든다.

    `chunk_id`에 전략 이름을 접두어로 붙이는 이유: 여러 청킹 전략을 나란히 비교할 때 id가 서로 안
    겹쳐야 해서다.
    """
    chunks = []
    for i, text in enumerate(texts):
        metadata: dict = {"strategy": strategy, "char_count": len(text)}
        heading = _extract_heading(text)
        if heading:
            metadata["heading"] = heading
        if reasons:
            metadata["split_reason"] = reasons[i]
        chunks.append(Chunk(chunk_id=f"{strategy}-{i:04d}", text=text, order=i, metadata=metadata))
    return chunks


def chunk_markdown(
    markdown: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    min_chunk_chars: int = DEFAULT_MIN_CHUNK_CHARS,
) -> list[Chunk]:
    """Markdown 문자열을 Chunk 리스트로 분할한다(규칙 기반, 구조 보존 우선)."""
    splitter = RecursiveCharacterTextSplitter(
        separators=_KOREAN_LEGAL_SEPARATORS,
        is_separator_regex=True,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        keep_separator="start",
    )
    texts = [t.strip() for t in splitter.split_text(markdown) if t.strip()]
    texts = _merge_tiny_pieces(texts, min_chunk_chars)
    return build_chunks(texts, strategy="rule_based")
