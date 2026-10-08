"""TextBundle 폴더 하나 읽기(`<이름>.textbundle/{info.json, text.markdown, assets/}`).

파서(`export/textbundle.py`)가 쓰는 규격을 읽는 쪽이다. 파서 코드를 import하지 않고 파일 모양만 따른다.
우리 메타데이터는 `info.json`의 `kr.strategic-items.docparser` 키 아래에 있다(`DOMAIN_KEY`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DOMAIN_KEY = "kr.strategic-items.docparser"
BUNDLE_SUFFIX = ".textbundle"


@dataclass
class Bundle:
    path: Path
    markdown: str
    document_id: str
    title: str = ""
    source_path: str = ""
    source_format: str = ""
    document: dict = field(default_factory=dict)  # docs.jsonl의 문서 속성과 같은 객체(category, document_type, ...)
    info: dict = field(default_factory=dict)

    def asset(self, relative: str) -> Path:
        """마크다운이 참조하는 그림의 번들 안 경로(`assets/img-….png`)."""
        return self.path / relative


def read_bundle(path: Path | str) -> Bundle:
    """번들 폴더를 읽는다. `text.markdown`이나 `info.json`이 없으면 FileNotFoundError, 문서 ID가 없으면 ValueError."""
    path = Path(path)
    info = json.loads((path / "info.json").read_text(encoding="utf-8"))
    markdown = (path / "text.markdown").read_text(encoding="utf-8")
    ours = info.get(DOMAIN_KEY) or {}
    document_id = ours.get("document_id")
    if not document_id:
        raise ValueError(f"info.json에 {DOMAIN_KEY}.document_id가 없다: {path}")
    return Bundle(
        path=path,
        markdown=markdown,
        document_id=document_id,
        title=ours.get("title") or "",
        source_path=ours.get("source_path") or "",
        source_format=ours.get("source_format") or "",
        document=ours.get("document") or {},
        info=info,
    )


def iter_bundles(root: Path | str):
    """`root` 아래의 모든 번들 폴더를 이름 순으로 읽는다(`bundles/` 폴더이든 그 상위든 재귀로 찾는다)."""
    for folder in sorted(Path(root).rglob(f"*{BUNDLE_SUFFIX}")):
        if folder.is_dir():
            yield read_bundle(folder)
