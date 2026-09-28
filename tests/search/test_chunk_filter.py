from unittest.mock import patch

from search_engine.config import Settings
from search_engine.search.chunk_filter import filter_chunks
from search_engine.search.results import SearchHit, Passage


def test_filter_promotes_kept_passage_preserves_context_and_document_score():
    hit = SearchHit(id='a', parent_id='doc', body='unrelated', score=19,
                    passages=[Passage(id='b', body='condition', score=.8),
                              Passage(id='c', body='answer', score=.9)])
    with patch('search_engine.search.chunk_filter.generate', return_value='{"grades":[0,1,2]}'):
        result = filter_chunks('question', [hit], Settings())
    assert result[0].chunk_ids == ['b', 'c']
    assert result[0].score == 19
    assert result[0].chunk_relevance == 1
    assert result[0].passages[0].relevance == 2
    assert hit.chunk_ids == ['a', 'b', 'c']


def test_all_irrelevant_removes_document():
    with patch('search_engine.search.chunk_filter.generate', return_value='{"grades":[0]}'):
        assert filter_chunks('q', [SearchHit(id='a', parent_id='d')], Settings()) == []


def test_invalid_or_partial_grades_preserve_all_input():
    hits = [SearchHit(id='a', parent_id='d')]
    for response in ['{"grades":[]}', '{"grades":[true]}', '{"grades":[3]}', 'invalid']:
        with patch('search_engine.search.chunk_filter.generate', return_value=response):
            assert filter_chunks('q', hits, Settings()) is hits


def test_later_batch_failure_does_not_partially_filter():
    hits = [SearchHit(id=str(i), parent_id=str(i)) for i in range(7)]
    with patch('search_engine.search.chunk_filter.generate', side_effect=['{"grades":[0,0,0,0,0,0]}', RuntimeError('timeout')]):
        assert filter_chunks('q', hits, Settings()) is hits


def test_retrieval_judges_only_filtered_chunks():
    from datetime import date
    from unittest.mock import Mock
    from search_engine.search.query import retrieve

    client = Mock()
    client.search.return_value = {"hits": {"hits": [{"_id": "a", "_score": 20,
        "_source": {"parent_id": "d", "body": "unrelated"}}]}}
    kept = [SearchHit(id='b', parent_id='d', body='answer')]
    settings = Settings(search_chunk_filter=True, search_answerability_judge=True)
    with patch('search_engine.search.query.get_settings', return_value=settings), \
         patch('search_engine.search.query.filter_chunks', return_value=kept) as filtering, \
         patch('search_engine.search.query.is_unanswerable', return_value=False) as judging:
        result = retrieve(client, 'index', 'q', date.today(), 5, mode='bm25')
    assert result == kept
    filtering.assert_called_once()
    judging.assert_called_once_with('q', kept, settings)
