"""문서를 검색 청크로 나누는 로직. 전에는 `unstructured-doc-parser_ver2`가 가졌다
([청킹을 검색엔진으로 옮긴다](../../docs/design/chunking_ownership_move.md)).

파서는 이제 TextBundle(`text.markdown` + `info.json` + `assets/`)까지만 만들고, 이 패키지가 번들을
읽어 원소로 되돌린 뒤(`elements.py`) 같은 규칙으로 청킹한다(`structured.py`).
"""
