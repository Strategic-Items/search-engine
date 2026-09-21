"""도메인 동의어 사전, OpenSearch 동의어 규칙으로서.

`data/synonyms.txt`는 실험실 리포지토리에서 이어온 사람이 편집한 파일이다. 한 줄은 서로 동등한 용어 그룹이다.
"""

from pathlib import Path

# parents[2]는 리포지토리 루트: search_engine/indexing/synonyms.py -> repo.
REPO_ROOT = Path(__file__).resolve().parents[2]
SYNONYM_PATH = REPO_ROOT / "data" / "synonyms.txt"


def load_synonyms(path: Path | None = None) -> list[str]:
    """동의어 그래프 필터가 받는 `a, b, c` 규칙으로 사전을 읽는다."""
    rules = []
    for line in (path or SYNONYM_PATH).read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        terms = [term.strip() for term in line.split(",") if term.strip()]
        if len(terms) > 1:
            rules.append(", ".join(terms))
    return rules
