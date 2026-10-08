"""Reconcile reviewed equivalent evidence against every chunk in the category corpora.

No retrieval is rerun: preserve scores, candidate order, cutoffs and dense attribution.
Only reviewed answer-equivalent passages are added; differing dates/numbers/actors are
not inferred from title similarity. Each addition and the original labels are recorded.

    .venv/bin/python scripts/law/reconcile_explorer_labels.py
"""
import json
import re
import subprocess
import unicodedata
from pathlib import Path

from search_engine.config import get_settings
try:
    from evidence_validation import policies, apply_review
except ModuleNotFoundError:
    from scripts.law.evidence_validation import policies, apply_review

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / 'docs/presentation/question_explorer/data'
RULES = ROOT / 'data/label_reviews/category_equivalents_2026-10-07.json'
FILES = {'law100': ROOT / 'data/generated/explorer-law100-2026-10-07/queries_law100_rechunk.jsonl',
         'admin30': ROOT / 'data/queries_admin_v1.jsonl', 'faq30': ROOT / 'data/queries_faq_v2.jsonl'}


def norm(text):
    return re.sub(r'[^\w]', '', unicodedata.normalize('NFKC', text)).lower()


def matches(rule, chunk):
    if rule['parents'] and chunk['parent_id'] not in rule['parents']:
        return False
    body = norm(chunk['body'])
    return any(all(norm(p) in body for p in alt) for alt in rule['alternatives'])


def dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def load_explorer():
    code = "const fs=require('fs'),vm=require('vm'),c={};vm.createContext(c);" \
           "for(const n of ['categories','category-detail'])vm.runInContext(fs.readFileSync(process.argv[1]+'/'+n+'.js','utf8'),c);" \
           "process.stdout.write(JSON.stringify({CATD:c.CATD,CATH:c.CATH,CATB:c.CATB}));"
    return json.loads(subprocess.check_output(['node', '-e', code, str(EXP)], text=True))


def relabel(d, gold, chunks, groups=None, law=False):
    old = set(d['gc'])
    old_ranks = list(d['gr'])
    groups = groups or [sorted(gold)]
    parents = {c.split('#')[0] for c in gold}
    titles = {chunks[c]['title'].split(' — ')[0] for c in gold if c in chunks}
    ranks = [{}, {}, {}]
    for k, name in enumerate(['sp', 'dn', 'hy']):
        for i, h in enumerate(d[name], 1):
            ranks[k][h['c']] = i
            if h['c'] in gold:
                h['g'] = 1
            else:
                h.pop('g', None)
    for k, side in enumerate(['sp', 'dn']):
        fx = d['fx'][side]
        fx['n'] = len(gold)
        for c in fx['cr']:
            ranks[k][c[0]] = c[1]
            c[4] = int(c[0] in gold)
        for group in fx['ret']:
            for c in group:
                c[1] = int(c[0] in gold)
                if law or c[0] in gold:
                    c[2] = 2 if c[0] in gold else 0
        for r in fx['rows']:
            r[4] = int(r[0] in titles)
    for i, r in enumerate(d['fx']['cr'], 1):
        ranks[2][r[0]] = i
        r[7] = int(r[0] in gold)
    for r in d['fx']['ret']:
        r['g'] = int(any(c[0].split('#')[0] in parents for c in r['ch']))
        for c in r['ch']:
            c[3] = int(c[0] in gold)
            if law or c[0] in gold:
                c[4] = 2 if c[0] in gold else 0
    d['rank_incomplete'] = [False, False, False]
    for k in range(3):
        per_group = [min((ranks[k][c] for c in g if c in ranks[k]), default=None) for g in groups]
        known = max(per_group) if all(r is not None for r in per_group) else None
        if old <= gold and len(groups) == 1:
            known = min([r for r in [known, old_ranks[k]] if r is not None], default=None)
        elif gold and known is None:
            d['rank_incomplete'][k] = True
        d['gr'][k] = known
    d['gc'] = sorted(gold, key=lambda c: (min(ranks[0].get(c, 10**6), ranks[1].get(c, 10**6)), c))
    d['evidence_groups'] = groups
    d['fx']['gd'] = d['gr'][2] or 0


def complete_hit(d):
    returned = {c[0] for r in d['fx']['ret'] for c in r['ch']}
    return all(bool(set(g) & returned) for g in d.get('evidence_groups', [d.get('gc', [])]))


def main():
    settings = get_settings()
    sources = {'law100': Path(settings.search_law_source), 'admin30': Path(settings.search_admin_source),
               'faq30': Path(settings.search_law_source).parent.parent / '03_민원FAQ/docs.jsonl'}
    corpora = {s: {c['id']: c for c in map(json.loads, p.read_text().splitlines())} for s, p in sources.items()}
    rules = {r['query']: r for r in json.loads(RULES.read_text())}
    ex = load_explorer()
    notes = {(r['set'], r['id']): r['note'] for r in json.loads((RULES.parent / 'category_scope_notes_2026-10-07.json').read_text())}
    report = []
    positive = policies()
    for s, qfile in FILES.items():
        queries = [json.loads(l) for l in qfile.read_text().splitlines() if l.strip()]
        for q in queries:
            i = q['qid'][-3:]
            d = ex['CATH'][s][i]
            original = set(q.get('label_review', {}).get('original_chunks', [c for g in q.get('positive_review', {}).get('original_groups', q['evidence_groups']) for c in g]))
            rule = rules.get(q['query'])
            if (s, i) in notes:
                d['scope_note'] = notes[s, i]
            approved = {c for c, chunk in corpora[s].items() if rule and matches(rule, chunk)}
            q['evidence_groups'] = [sorted(set(g) | approved) for g in q['evidence_groups']] if len(q['evidence_groups']) == 1 else q['evidence_groups']
            apply_review(q, corpora[s], positive)
            gold = {c for g in q['evidence_groups'] for c in g}
            d['supporting_chunks'] = sorted(approved-gold) if s=='law100' and i=='093' else []
            additions = gold - original
            if additions and rule:
                review = {'date': '2026-10-07', 'scope': rule['scope'], 'reason': rule['reason'],
                          'original_chunks': sorted(original), 'added_chunks': sorted(additions)}
                q['label_review'] = review
                # One OR group: alternative chunks independently answer the same requirement.
                q['gold'] = sorted({c.split('#')[0] for c in gold})
                d['label_review'] = review
                for c in additions:
                    ex['CATB'][c] = [corpora[s][c]['title'], corpora[s][c]['body']]

            if q.get('positive_review'):
                d['positive_review'] = q['positive_review']
            else:
                d.pop('positive_review', None)
            for c in gold:
                ex['CATB'][c] = [corpora[s][c]['title'], corpora[s][c]['body']]
            relabel(d, gold, corpora[s], q['evidence_groups'], law=s=='law100')
            row = next(r for r in ex['CATD'][s] if r['i'] == i)
            row['n'] = len(gold)
            row['r'] = [r if r and r <= 5 else None for r in d['gr']]
            row['eligible'] = q.get('positive_review', {}).get('evaluation_eligible', True)
            after = complete_hit(d)
            report.append({'set': s, 'id': i, 'query': q['query'], 'added_chunks': sorted(additions),
                           'original_return_hit': any(c[0] in original for r in d['fx']['ret'] for c in r['ch']),
                           'return_hit': after, 'reason': rule['reason'] if rule else None,
                           'scope_note': notes.get((s, i)),
                           'positive_review': q.get('positive_review')})
        qfile.write_text(''.join(json.dumps(q, ensure_ascii=False) + '\n' for q in queries))
    # Apply the same review to canonical older sets by exact question, mapping to their own corpus IDs.
    for path in [ROOT/'data/queries_law100_v1.jsonl', ROOT/'data/queries_law50_v1.jsonl', ROOT/'data/queries_law_v1.jsonl']:
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        for q in rows:
            rule = rules.get(q['query'])
            original = set(q.get('label_review', {}).get('original_chunks', [c for g in q.get('positive_review', {}).get('original_groups', q['evidence_groups']) for c in g]))
            additions = {c for c, chunk in corpora['law100'].items() if rule and matches(rule, chunk)} - original
            if additions and rule:
                q['label_review'] = {'date': '2026-10-07', 'scope': rule['scope'], 'reason': rule['reason'],
                                     'original_chunks': sorted(original), 'added_chunks': sorted(additions)}
                assert len(q['evidence_groups']) == 1
                q['evidence_groups'][0] = sorted(original | additions)
                q['gold'] = sorted({c.split('#')[0] for c in q['evidence_groups'][0]})
            apply_review(q, corpora['law100'], positive)
        path.write_text(''.join(json.dumps(q, ensure_ascii=False) + '\n' for q in rows))
    for name, names in [('categories', ['CATD']), ('category-detail', ['CATH', 'CATB'])]:
        path = EXP / (name + '.js')
        header = path.read_text().splitlines()[0]
        path.write_text(header + '\n' + '\n'.join('var '+n+'='+dump(ex[n])+';' for n in names) + '\n')
    target = ROOT / 'docs/evaluation/category_label_audit_2026-10-07.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(dump({'questions': len(report), 'corrected': sum(bool(r['added_chunks']) for r in report),
                'new_return_hits': [r['set']+'-'+r['id'] for r in report if r['return_hit'] and not r['original_return_hit']]}))


if __name__ == '__main__':
    main()
