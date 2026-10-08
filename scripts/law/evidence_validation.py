"""Reviewed scope constraints for category evidence, shared by build and reconciliation."""
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY_FILE = ROOT / 'data/label_reviews/category_positive_constraints_2026-10-07.json'


def norm(text):
    return re.sub(r'[^\w]', '', unicodedata.normalize('NFKC', text)).lower()


def policies():
    return {q: r for r in json.loads(POLICY_FILE.read_text()) for q in [r['query'], *r.get('aliases', [])]}


def validate(rule, chunk):
    """Return a reviewed exclusion reason; None is a structural pass, not LLM certification."""
    after = re.split(r"(?:개\s*정\s*안|개\s*정\s*후|개정|과기부․산자부 개정\(안\))\s*:", chunk["body"], maxsplit=1)
    if len(after)==2 and re.fullmatch(r"[\s<>〈〉]*삭\s*제[\s<>〈〉]*", after[1]):
        return "개정 전 문장은 있지만 개정 후 조항이 삭제되어 현재 답의 근거로 인정하지 않습니다."
    if re.match(r"^\s*(?:현\s*행|개\s*정\s*전)\s*:", chunk["body"]) and len(after)==1:
        return "신구대비표의 개정 전 문장만 있는 청크입니다. 개정 후 유지·변경 여부를 이 청크만으로 확인할 수 없습니다."
    if not rule:
        return None
    if rule.get('invalid_question'):
        return rule['reason']
    if rule.get('partial_only'):
        return rule['reason']
    parent = chunk['parent_id']
    if rule.get('parent_contains') and not any(p in parent for p in rule['parent_contains']):
        return rule['reason']
    heading = ' '.join(chunk.get('heading_path', []))
    if rule.get('heading_any') and not any(norm(p) in norm(heading) for p in rule['heading_any']):
        return rule['reason']
    if rule.get('context_any') and not any(norm(p) in norm(heading + ' ' + chunk['body']) for p in rule['context_any']):
        return rule['reason']
    body = norm(chunk['body'])
    if any(norm(p) not in body for p in rule.get('body_all', [])):
        return rule['reason']
    if rule.get('primary_code'):
        match = re.search(r'통제\s*(?:번호|기준)\s*[:：]\s*([0-9][A-E][0-9]{3,}(?:\.[a-z0-9]+)*)', chunk['body'])
        if match:
            if norm(match[1]) != norm(rule['primary_code']):
                return rule['reason']
        elif norm(rule['primary_code']) not in norm(chunk['body'].splitlines()[0]):
            return rule['reason']
    return None


def apply_review(query, chunks, by_query=None):
    rule = (by_query or policies()).get(query['query'])
    groups = query.get('positive_review', {}).get('original_groups') or query['evidence_groups']
    if len(groups) == 1:
        groups = [sorted(set(groups[0]) | set(query.get('label_review', {}).get('added_chunks', [])))]
    previous = sorted({c for g in groups for c in g})
    removed = {c: validate(rule, chunks[c]) if c in chunks else '현재 코퍼스에 없는 청크 ID' for c in previous}
    removed = {c: reason for c, reason in removed.items() if reason}
    groups = [[c for c in group if c not in removed] for group in groups]
    if not rule and not removed:
        query['evidence_groups'] = groups
        query['gold'] = sorted({chunks[c]['parent_id'] for g in groups for c in g if c in chunks})
        query.pop('positive_review', None)
        return query
    rule = rule or {'reason': next(iter(removed.values()))}
    if rule.get('evidence_groups'):
        groups = rule['evidence_groups']
    valid = {c for g in groups for c in g}
    query['evidence_groups'] = groups
    query['gold'] = sorted({chunks[c]['parent_id'] for c in valid if c in chunks})
    prior = query.get('positive_review', {})
    query['positive_review'] = {
        'date': '2026-10-07', 'reason': rule['reason'],
        'removed_chunks': removed,
        'original_groups': prior.get('original_groups', query.get('_original_groups', [])) or [[c for c in previous]],
        'evaluation_eligible': all(groups),
    }
    if rule.get('suggested_query'):
        query['positive_review']['suggested_query'] = rule['suggested_query']
    return query
