"""In-process retrieval over the search engine."""

from datetime import date

from anyio import to_thread

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.search.results import SearchHit
from search_engine.search import search_all


async def retrieve(query_text: str) -> list[SearchHit]:
    settings = get_settings()
    results = await to_thread.run_sync(
        lambda: search_all(
            create_client(), settings.search_index_alias, settings.search_hsk_alias,
            query_text, date.today(), settings.rag_top_k,
        )
    )
    return results.hits
