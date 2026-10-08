"""청킹 파라미터와 버전 표시.

전에는 이 값을 바꾸려면 파서(`unstructured-doc-parser_ver2`)를 다시 돌려야 했다. 이제 검색엔진
`Settings`에서 바로 바꿀 수 있다([설계](../../docs/design/chunking_ownership_move.md)).

`CHUNKER_VERSION`은 색인 manifest에 남겨, 다른 버전으로 만든 청크가 같은 인덱스에 섞이는 것을
추적하는 용도다. 이 모듈의 로직(구분자, 표 처리 규칙 등)을 바꾸면 올린다 — 파라미터 숫자만 바꿔도
결과 청크가 달라지므로 올린다.
"""

CHUNKER_VERSION = 1

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_MIN_CHUNK_CHARS = 30
