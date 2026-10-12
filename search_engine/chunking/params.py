"""청킹 정책(검색엔진 소유)과 버전 표시.

전에는 이 값을 바꾸려면 파서(`unstructured-doc-parser_ver2`)를 다시 돌려야 했다. 파서의 규칙 목록(`CHUNKING_RULES.md`)에서 "옮김"으로
분류된 22개가 이 저장소의 정책이다. 그 중 숫자로 정해지는 것을 `ChunkPolicy`에 모았다 -- 기본값은 파서가 쓰던 값 그대로다. **측정 없이
바꾸지 않는다**(규칙별 위치와 측정 후보는 [설계](../../docs/design/chunking_ownership_move.md) "옮김 22개 정책").

`CHUNKER_VERSION`은 색인 manifest에 남겨, 다른 버전으로 만든 청크가 같은 인덱스에 섞이는 것을 추적하는 용도다. 이 패키지의 로직(구분자,
표 처리 규칙 등)이나 정책 기본값을 바꾸면 올린다.
"""

from dataclasses import dataclass

CHUNKER_VERSION = 7

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_MIN_CHUNK_CHARS = 30


@dataclass(frozen=True)
class ChunkPolicy:
    # A1·A3·E1·G6·I8: 청크 크기(글자). 문단·목록 항목은 경계에서만 자르고, 그 하나가 넘으면 글자 수 분할기가 나눈다.
    chunk_size: int = DEFAULT_CHUNK_SIZE
    # A3·L1: 분할기가 나눈 이웃 조각의 겹침
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    # B2·L2·A3: 이보다 짧은 조각은 따로 청크로 두지 않고 이웃과 합친다
    min_chunk_chars: int = DEFAULT_MIN_CHUNK_CHARS
    # D1: 물음표로 끝나는 짧은 줄이 이만큼 있는 문서는 문답 문서로 보고 질문마다 청크를 연다
    question_min: int = 3
    question_max_chars: int = 300
    question_path_chars: int = 80
    # G6: 청크 크기를 넘는 행의 칸 분류 -- 이 길이 이하의 칸은 식별자(통제번호 등)라서 조각마다 머리 줄로 붙는다
    row_key_max_chars: int = 40
    # G6: 칸이 청크 크기의 이 비율을 넘으면 그 칸을 따로 글자 수 분할한다
    long_cell_ratio: float = 0.5
    # I8: 대비표 조문 쌍이 청크 크기의 이 배수를 넘으면 현행·개정안을 각각 조각으로 나눈다
    pair_oversize_ratio: float = 1.5
    # I6: 조문 없는 쌍이 이보다 짧으면(법령명 줄, `<신설>` 자리표시) 다음 쌍 앞에 붙인다
    carry_max_chars: int = 40
    # K4: 청크 제목에 붙이는 절 표시의 최대 길이
    heading_max_chars: int = 60

    @property
    def long_cell_chars(self) -> int:
        return int(self.chunk_size * self.long_cell_ratio)


DEFAULT_POLICY = ChunkPolicy()
