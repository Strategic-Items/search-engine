"""Equivalent answers must keep actor, control number and source constraints."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('reconcile_labels', ROOT/'scripts/law/reconcile_explorer_labels.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
RULES = {(r['set'], r['id']): r for r in json.loads(module.RULES.read_text())}


def chunk(body, parent='any'):
    return {'body': body, 'parent_id': parent}


def test_centrifuge_control_number_and_exclusion_are_required():
    rule = RULES['law100', '093']
    assert module.matches(rule, chunk('통제번호: 2B122\n해석 세부지침: 실험실에서 사용되는 생물학적 원심분리기는 이에 해당하지 않는다.'))
    assert not module.matches(rule, chunk('통제번호: 2B121\n실험실에서 사용되는 생물학적 원심분리기는 이에 해당하지 않는다.'))
    assert not module.matches(rule, chunk('통제번호: 2B122\n생물학적 원심분리기는 이에 해당한다.'))


def test_mentor_duration_is_not_any_extension():
    rule = RULES['admin30', '001']
    assert module.matches(rule, chunk('(멘토 기업) 유효기간 연장(3년→5년)'))
    assert not module.matches(rule, chunk('(멘티 기업) 유효기간 연장(3년→5년)'))
    assert not module.matches(rule, chunk('(멘토 기업) 유효기간 연장(3년→4년)'))


def test_different_confirming_authority_is_not_equivalent():
    rule = RULES['law100', '091']
    body = '원자력플랜트기술수출허가를 받은 자는 기술을 이전하기 전에 원자력안전위원회 위원장으로부터 당해 기술이 별표 2의 제10부(원자력전용품목)에 해당하는 전략물자인지 여부를 확인받아야 한다'
    assert module.matches(rule, chunk(body))
    assert not module.matches(rule, chunk(body.replace('원자력안전위원회 위원장', '한국원자력통제기술원장')))


def test_tour_destination_requires_same_tour_document():
    rule = RULES['admin30', '013']
    assert module.matches(rule, chunk('(국가 선정) 대만', rule['parents'][0]))
    assert not module.matches(rule, chunk('(국가 선정) 대만', 'different-tour'))


def test_same_deadline_for_different_country_is_not_evidence():
    from scripts.law.evidence_validation import policies, validate
    rule = next(r for r in policies().values() if r['set']=='law100' and r['id']=='022')
    c = chunk('수출허가 신청일로부터 7일 이내에 통보하며 유효기간은 1년으로 한다.')
    c['heading_path'] = ['제11장 리비아에 대한 무역에 관한 특별조치']
    assert validate(rule, c)
    c['heading_path'] = ['제5장 소말리아에 대한 무역에 관한 특별조치']
    assert validate(rule, c) is None


def test_stability_requires_both_date_and_control_number():
    from scripts.law.evidence_validation import policies, validate
    rule = next(r for r in policies().values() if r['set']=='law100' and r['id']=='052')
    c = chunk('통제번호: 3A226.b\n전압 출력 변동값/전압 출력 x 100 %', '01_법령고시-11008-2393869-지침')
    assert validate(rule, c) is None
    assert validate(rule, {**c, 'body': c['body'].replace('3A226.b', '3A227.b')})
    assert validate(rule, {**c, 'parent_id': '01_법령고시-16585-2391491-지침'})


def test_four_digit_transcribed_control_number_does_not_get_truncated():
    from scripts.law.evidence_validation import policies, validate
    rule = next(r for r in policies().values() if r['set']=='law100' and r['id']=='064')
    assert validate(rule, chunk('통제 번호: 1B1174\n개정안: 압력 범위')) is None
    assert validate(rule, chunk('통제 번호: 1B118\n개정안: 압력 범위'))


def test_deleted_article_and_before_only_are_not_current_evidence():
    from scripts.law.evidence_validation import validate
    assert validate(None, chunk('현 행:\n수출을 면제한다.\n개 정 안:\n<삭제>'))
    assert validate(None, chunk('개정 전:\n수출을 면제한다.'))
    assert validate(None, chunk('현행:\n옛 금수조치\n개정:\n금수조치 해제\n개정사유: WMD 관련 금수조치 해제')) is None


def test_actor_context_and_answer_are_two_requirements():
    from scripts.law.evidence_validation import apply_review
    query = {'query': '한국과 외국 국적을 둘 다 가진 사람에게 전략기술을 넘기면 어느 나라 기준으로 보나요?', 'evidence_groups': [['context']], 'gold': ['p']}
    rule = {'reason': 'recipient context', 'evidence_groups': [['context'], ['answer']]}
    chunks = {c: {'parent_id': 'p', 'body': ''} for c in ['context','answer']}
    result = apply_review(query, chunks, {query['query']: rule})
    assert result['evidence_groups'] == [['context'], ['answer']]
    d = {'fx': {'ret': [{'ch': [['context',0,0,1,2]]}]}, 'evidence_groups': result['evidence_groups']}
    assert not module.complete_hit(d)
    d['fx']['ret'][0]['ch'].append(['answer',0,0,1,2])
    assert module.complete_hit(d)


def test_review_can_restore_a_label_after_corrected_validation():
    from scripts.law.evidence_validation import apply_review
    query = {'query': 'q', 'evidence_groups': [[]], 'gold': [], 'positive_review': {'original_groups': [['c']], 'removed_chunks': {'c':'old error'}}}
    result = apply_review(query, {'c': {'body':'supported answer', 'parent_id':'p'}}, {})
    assert result['evidence_groups'] == [['c']]
    assert result['gold'] == ['p']
    assert 'positive_review' not in result
