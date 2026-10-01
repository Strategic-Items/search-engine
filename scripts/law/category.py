"""카테고리별 평가 스크립트가 공유하는 경로. 환경변수 CATEGORY(law 기본, admin)로 고른다."""

import os
from pathlib import Path

CATEGORY = os.environ.get("CATEGORY", "law")
QUERIES = Path(f"data/queries_{CATEGORY}_v1.jsonl")


def alias(settings) -> str:
    return getattr(settings, f"search_{CATEGORY}_alias")


def source(settings) -> str:
    return getattr(settings, f"search_{CATEGORY}_source")
