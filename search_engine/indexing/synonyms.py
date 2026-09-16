"""The domain synonym dictionary, as OpenSearch synonym rules.

`data/synonyms.txt` is the human-edited file, carried over from the lab
repository. One line is one group of mutually equivalent terms.
"""

from pathlib import Path

# parents[2] is the repository root: search_engine/indexing/synonyms.py -> repo.
REPO_ROOT = Path(__file__).resolve().parents[2]
SYNONYM_PATH = REPO_ROOT / "data" / "synonyms.txt"


def load_synonyms(path: Path | None = None) -> list[str]:
    """Read the dictionary into the `a, b, c` rules a synonym_graph filter takes."""
    rules = []
    for line in (path or SYNONYM_PATH).read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        terms = [term.strip() for term in line.split(",") if term.strip()]
        if len(terms) > 1:
            rules.append(", ".join(terms))
    return rules
