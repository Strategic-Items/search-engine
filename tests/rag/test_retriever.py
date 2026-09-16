from unittest.mock import Mock

from search_engine.config import Settings
from search_engine.rag import retriever


async def test_retriever_calls_search_in_process_with_configured_aliases(monkeypatch):
    client = Mock()
    monkeypatch.setattr(retriever, "create_client", lambda: client)
    monkeypatch.setattr(retriever, "get_settings", lambda: Settings(
        search_index_alias="docs", search_docs_alias="parsed",
        search_hsk_alias="hsk", rag_top_k=3,
    ))
    client.search.return_value = {"hits": {"hits": [{
        "_id": "form-1", "_score": 2.0, "_source": {
            "title": "자가판정 신청서", "body": "본문", "source_type": "민원서식",
        },
    }]}}

    hits = await retriever.retrieve("자가판정")

    assert hits[0].id == "form-1"
    assert hits[0].source_type == "민원서식"
    assert client.search.call_args.kwargs["index"] == "docs,parsed"
