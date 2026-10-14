from datetime import date
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from search_engine.config import Settings
from search_engine.search import query as retrieval


def test_law_hnsw_exploration_does_not_expand_returned_candidates():
    query = retrieval.build_vector_query([0.1], date(2026, 10, 13), 25, law_ranking=True)
    assert query['knn']['embedding']['k'] == 25
    assert query['knn']['embedding']['method_parameters'] == {'ef_search': 512}
    general = retrieval.build_vector_query([0.1], date(2026, 10, 13), 25)
    assert 'method_parameters' not in general['knn']['embedding']


def test_law_ranking_uses_splade_without_bm25():
    query = retrieval.build_law_splade_query({'t1': 1.0}, date(2026, 10, 7), '보관 기간은?',
                                            reference_boost=6)
    assert 'neural_sparse' in str(query['bool']['must'])
    assert 'multi_match' not in str(query)
    assert 'effective_from' in str(query['bool']['filter'])
    assert 'effective_to' in str(query['bool']['filter'])
    pure = retrieval.build_law_splade_query({'t1': 1.0}, date(2026, 10, 7), '보관 기간은?',
                                           reference_boost=0)
    assert 'multi_match' not in str(pure)


def test_reference_bonus_distinguishes_annex_code_and_requested_body_item():
    query = retrieval.build_law_splade_query({'t1': 1.0}, date(2026, 10, 7),
                                            '별표 2에서 3A002.d.1의 개정반영 내용은 무엇?',
                                            reference_boost=6)
    functions = query['function_score']['functions']
    assert len(functions) == 2  # Matching the annex must not erase the control-code signal.
    assert 'heading_path' in str(functions[0])
    assert '3A002.d.1' in str(functions[1])
    form = retrieval.build_law_splade_query({'t1': 1.0}, date(2026, 10, 7),
                                           '별지 제4호 전문판정서의 주의사항에는 무엇이 적혀 있나요?',
                                           reference_boost=6)
    focus = form['function_score']['functions'][-1]['filter']['bool']['must']
    assert focus[-1] == {'match_phrase': {'body': '주의사항'}}
    assert 'heading_path' in str(focus[0])


def test_law_fetches_only_two_lists_of_25_even_with_article_and_control_code(monkeypatch):
    settings = Settings(search_splade_model='test', search_chunk_filter=False,
                        search_chunk_first_identifier_weight=0.5, search_vector_candidates=100)
    monkeypatch.setattr(retrieval, 'get_settings', lambda: settings)
    monkeypatch.setattr(retrieval, 'encode_sparse_query', lambda _: {'t1': 1.0})
    hit = {'_id': 'p#1', '_score': 1.0, '_source': {
        'parent_id': 'p', 'title': '별표', 'body': '근거 내용', 'heading_path': ['제85조'],
    }}
    client = Mock()
    client.search.return_value = {'hits': {'hits': [hit]}}
    embedder = Mock()
    embedder.embed_query.return_value = [0.1]
    hits = retrieval.retrieve(client, 'law', '제85조와 3A002.d.1 내용은?', date(2026, 10, 7),
                              5, embedder, mode='hybrid', lexical='splade', chunk_first=True,
                              chunk_first_cutoff_ratio=0.7, hybrid_candidates=25, law_ranking=True,
                              answerability=False, rerank_chunks=False, query_rewrite=False, score_floor=0)
    assert hits[0].chunk_ids == ['p#1']
    assert client.search.call_count == 2
    assert [call.kwargs['size'] for call in client.search.call_args_list] == [25, 25]
    assert 'neural_sparse' in str(client.search.call_args_list[0].kwargs['body'])
    assert 'multi_match' not in str(client.search.call_args_list[0].kwargs['body'])
    assert 'knn' in str(client.search.call_args_list[1].kwargs['body'])


@pytest.mark.parametrize('category', ['law', 'admin'])
def test_law_options_are_scoped_to_law_category(monkeypatch, category):
    from search_engine.api import routes
    from search_engine.search.results import ModeComparison

    monkeypatch.setattr(routes, 'get_settings', lambda: Settings(search_splade_model='test'))
    monkeypatch.setattr(routes, 'create_client', Mock())
    compare = Mock(return_value=ModeComparison(query='허가', modes=[]))
    monkeypatch.setattr(routes, 'search_modes', compare)
    routes.search_category_compare(category, routes.SearchRequest(query='허가'))
    options = compare.call_args.kwargs
    assert options['modes'] == ('splade', 'vector', 'hybrid')
    if category == 'law':
        assert options['hybrid_candidates'] == 25
        assert options['law_ranking'] is True
    else:
        assert 'hybrid_candidates' not in options
        assert 'law_ranking' not in options


def test_law_does_not_fall_back_to_bm25_without_splade(monkeypatch):
    from fastapi import HTTPException
    from search_engine.api import routes

    monkeypatch.setattr(routes, 'get_settings', lambda: Settings(search_splade_model=''))
    compare = Mock()
    monkeypatch.setattr(routes, 'search_modes', compare)
    with pytest.raises(HTTPException) as error:
        routes.search_category_compare('law', routes.SearchRequest(query='허가'))
    assert error.value.status_code == 503
    compare.assert_not_called()


def test_law_candidate_count_cannot_be_expanded():
    with pytest.raises(ValidationError):
        Settings(search_law_candidates=50)


@pytest.mark.parametrize('text', [
    '2026년 고시로 봐줘요. 시험한 장비 재수입 신고는?',
    '2026년 전략물자수출입고시 기준 검사·시험 신고',
    '2026 고시 버그 패치 수출허가 면제',
    '2015년도 고시의 유효기간',
])
def test_notice_edition_year_filters_both_law_retrievers(text):
    year = text[:4]
    sp = retrieval.build_law_splade_query({'t1': 1.0}, date(2026, 10, 12), text, reference_boost=6)
    dn = retrieval.build_vector_query([0.1], date(2026, 10, 12), 25, text, law_ranking=True)
    sp = sp.get('function_score', {}).get('query', sp)
    assert sp['bool']['filter'][-1] == dn['knn']['embedding']['filter']['bool']['filter'][-1]
    assert {'prefix': {'doc_number_norm': year+'-'}} in sp['bool']['filter'][-1]['bool']['should']


@pytest.mark.parametrize('text', [
    '2026년에 수출한 장비의 신고기한은?',
    '2026년 수출 실적을 고시 기준으로 보고하려면?',
    '2015년과 2026년 고시를 비교해 주세요',
    '제2026-101호 고시의 신고기한은?',
    '최신 고시의 재수입 신고기한은?',
])
def test_event_year_comparison_and_exact_docket_do_not_add_edition_year_gate(text):
    assert retrieval._law_edition_filters(text) == []


def test_admin_and_general_dense_search_do_not_filter_notice_year():
    query = '2026년 고시로 봐줘요'
    sp = retrieval.build_splade_query({'t1': 1.0}, date(2026, 10, 12), query)
    dn = retrieval.build_vector_query([0.1], date(2026, 10, 12), 25, query)
    assert 'doc_number_norm' not in str(sp)
    assert 'doc_number_norm' not in str(dn)
