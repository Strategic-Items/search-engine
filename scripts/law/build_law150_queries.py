"""Rebind the reviewed 100 questions and add 50 source-grounded questions."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from law150_specs import NEW_SPECS, ADDITIONAL_EVIDENCE
from evidence_validation import norm
from search_engine.config import get_settings

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/generated/law150-2026-10-07'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    base = OUT / 'queries_existing100.jsonl'
    env = {**os.environ, 'SPECS':'law100', 'QUERIES_FILE':str(base), 'QID_PREFIX':'law150-v1'}
    subprocess.run([sys.executable, str(ROOT/'scripts/law/evaluate_law.py'), '--build'], env=env, cwd=ROOT, check=True)
    source = Path(get_settings().search_law_source)
    raw = source.read_bytes()
    chunks = [json.loads(l) for l in raw.decode().splitlines() if l.strip()]
    by_parent = {}
    for c in chunks:
        by_parent.setdefault(c['parent_id'], []).append(c)
    rows = [json.loads(l) for l in base.read_text().splitlines()]
    audit = []
    for number, (suffix, kind, query, phrases) in enumerate(NEW_SPECS, 101):
        parents = [p for p in by_parent if p.endswith(suffix)]
        assert len(parents)==1, (query,parents)
        parent = parents[0]
        family = parent.split('-b')[0].split('-t')[0]
        needles = [norm(p) for p in phrases]
        matches = [c for c in chunks if c['parent_id'].startswith(family+'-') and all(n in norm(c['body']) for n in needles)]
        # A specifically named annex must not accept another annex with similar text.
        title = by_parent[parent][0]['title']
        annex = re.search(r'별표\s*(\d+(?:의\d+|-\d+)?)', title)
        if annex:
            def section(c):
                tags = re.findall(r'별표\s*(\d+(?:의\d+|-\d+)?)', c['title']+' '+' '.join(c.get('heading_path',[])))
                return c['parent_id']==parent or annex[1] in tags
            matches = [c for c in matches if section(c)]
        assert any(c['parent_id']==parent for c in matches), (number,query,phrases)
        row = {'qid':f'law150-v1-{number:03d}', 'category':kind, 'query':query, 'phrases':phrases,
               'gold':sorted({c['parent_id'] for c in matches}), 'evidence_groups':[[c['id'] for c in matches]],
               'question_source_parent':parent, 'label_scope':'동일 법령 원본 및 질문이 지정한 별표; 필수 답 구절 모두 포함',
               'generation':'본문을 읽고 작성; 검색 결과 확인 전에 동결'}
        if number in ADDITIONAL_EVIDENCE:
            required = ADDITIONAL_EVIDENCE[number]
            headers = [c for c in by_parent[parent] if all(norm(p) in norm(c['body']) for p in required)]
            assert headers, (number, required)
            row['evidence_groups'].append([c['id'] for c in headers])
            row['additional_phrases'] = required
            row['gold'] = sorted(set(row['gold']) | {c['parent_id'] for c in headers})
            matches = list({c['id']:c for c in matches + headers}.values())
        rows.append(row)
        audit.append({'qid':row['qid'],'source_parent':parent,'evidence_groups':row['evidence_groups'],'matched_chunks':[c['id'] for c in matches],
                      'evidence':[{'id':c['id'],'title':c['title'],'body':c['body']} for c in matches]})
    assert len(rows)==150 and len({r['query'] for r in rows})==150
    for row in rows:
        row['cohort'] = 'existing100' if int(row['qid'][-3:])<=100 else 'new50'
    target = ROOT/'data/queries_law150_v1.jsonl'
    payload = ''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows)
    target.write_text(payload)
    (OUT/'queries.jsonl').write_text(payload)
    (OUT/'new_question_evidence.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    (OUT/'corpus.jsonl').write_bytes(raw)
    metadata={'source':str(source),'documents':len(by_parent),'chunks':len(chunks),
              'source_sha256':hashlib.sha256(raw).hexdigest(),'queries_sha256':hashlib.sha256(payload.encode()).hexdigest(),
              'questions':150,'eligible':sum(r.get('positive_review',{}).get('evaluation_eligible',True) for r in rows),
              'new_source_documents':len({r['question_source_parent'] for r in rows[100:]}),'new_questions':50}
    (OUT/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    print(json.dumps(metadata,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
