"""Write a per-label structural audit without rerunning retrieval or certifying prose with an LLM."""
import json
from pathlib import Path

from reconcile_explorer_labels import FILES, load_explorer, complete_hit
from evidence_validation import policies, validate
from search_engine.config import get_settings

ROOT = Path(__file__).resolve().parents[2]


def main():
    settings = get_settings()
    paths = {'law100': Path(settings.search_law_source), 'admin30': Path(settings.search_admin_source),
             'faq30': Path(settings.search_law_source).parent.parent/'03_민원FAQ/docs.jsonl'}
    chunks = {s: {c['id']: c for c in map(json.loads, p.read_text().splitlines())} for s, p in paths.items()}
    ex = load_explorer()
    rules = policies()
    report = []
    for s, path in FILES.items():
        for q in map(json.loads, path.read_text().splitlines()):
            i=q['qid'][-3:]
            d=ex['CATH'][s][i]
            review=q.get('positive_review', {})
            removed=review.get('removed_chunks', {})
            gold={c for g in q['evidence_groups'] for c in g}
            returned={c[0] for r in d['fx']['ret'] for c in r['ch']}
            candidates={h['c'] for name in ['sp','dn','hy'] for h in d[name]} | returned
            records=[]
            for cid in sorted(gold | set(removed)):
                c=chunks[s].get(cid)
                reason=removed.get(cid)
                if cid in gold:
                    assert c is not None
                    assert validate(rules.get(q['query']), c) is None
                records.append({'chunk_id': cid, 'status':'rejected' if reason else 'scope_checks_passed',
                                'reason':reason, 'returned':cid in returned, 'title':c['title'] if c else None,
                                'heading_path':c.get('heading_path',[]) if c else [],
                                'body':c['body'] if c else None})
            report.append({'set':s,'id':i,'query':q['query'],
                           'display_query':next(r['q'] for r in ex['CATD'][s] if r['i']==i),
                           'evaluation_eligible':review.get('evaluation_eligible',True),
                           'return_requirements_met':complete_hit(d),
                           'evidence_groups':q['evidence_groups'], 'review':review or None,
                           'scope_note':d.get('scope_note'), 'labels':records,
                           'checked_candidate_count':len(candidates)})
    out=ROOT/'docs/evaluation/category_positive_audit_2026-10-07.json'
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'questions':len(report),'label_records':sum(len(r['labels']) for r in report),
                      'rejected':sum(sum(c['status']=='rejected' for c in r['labels']) for r in report),
                      'changed_questions':sum(any(c['status']=='rejected' for c in r['labels']) for r in report),
                      'excluded':[r['set']+'-'+r['id'] for r in report if not r['evaluation_eligible']],
                      'complete_returns':sum(r['return_requirements_met'] for r in report)},ensure_ascii=False))


if __name__=='__main__':
    main()
