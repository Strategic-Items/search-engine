"""민원FAQ 원본으로 SPLADE·dense 실험 색인(exp-faq-splade)을 만든다. 서비스 별칭은 건드리지 않는다.

FAQ는 서비스 카테고리가 아니라 상시 색인이 없다. 탐색기 FAQ 문서 지표를 다시 잴 때만 쓰고, 끝나면 지운다.
    .venv/bin/python scripts/law/build_faq_experiment_index.py
    QUERIES_FAQ30=data/queries_faq_v1.jsonl LIVE_KEYS=faq30 .venv/bin/python scripts/law/add_explorer_doc_metrics.py
"""
import json
from pathlib import Path

from search_engine.config import get_settings
from search_engine.indexing import indexer

settings = get_settings()
for name, value in (("search_faqexp_alias", "exp-faq-splade"), ("search_faqexp_prefix", "exp-faq-splade-v")):
    object.__setattr__(settings, name, value)
indexer.DATASETS["faqexp"] = {"alias": "search_faqexp_alias", "prefix": "search_faqexp_prefix", "mapping": "law", "embed": True}
source = Path(settings.search_law_source).parent.parent / "03_민원FAQ/docs.jsonl"
index_name, count = indexer.rebuild(source, dataset="faqexp")
print(json.dumps({"index": index_name, "count": count}))
