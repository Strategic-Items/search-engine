"""Resolve number-valued `superseded_by` pointers to parent IDs and measure what the new-edition insert does.

Clone the live `search-law` index (no re-embedding), rewrite `superseded_by` to resolved parent IDs on the
clone, and compare hybrid retrieval with the pointer insert as shipped, appended only into free slots, and off.
Run: .venv/bin/python scripts/law/compare_resolved_editions.py
"""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

from opensearchpy.helpers import scan

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.indexing.law import resolve_superseded
from search_engine.search import query as retrieval
from search_engine.sparse import SparseEncoder

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sweep_superseded_weight import summarize  # noqa: E402

AS_OF = date(2026, 10, 6)


def insert_in_free_slots(client, alias, hits, k):
    """대체 문서를 반환 목록 끝의 남는 자리에만 붙인다. 이미 고른 문서를 밀어내지 않는다."""
    editions = retrieval._current_editions(client, alias, hits)
    out, present = list(hits), {h.parent_id for h in hits}
    for hit in hits:
        replacement = editions.get(hit.superseded_by)
        if replacement and replacement.parent_id not in present and len(out) < k:
            out.append(replacement)
            present.add(replacement.parent_id)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alias', default='search-law')
    parser.add_argument('--queries', type=Path, default=Path('data/queries_law100_v1.jsonl'))
    parser.add_argument('--out', type=Path, default=Path('data/generated/resolved-editions-2026-10-07'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    settings.search_chunk_filter = False
    settings.search_answerability_judge = False
    client = create_client(settings)
    baseline = list(client.indices.get_alias(name=args.alias))[0]
    rows = [h['_source'] for h in scan(client, index=baseline, query={'query': {'match_all': {}}, '_source': {'excludes': ['embedding', 'splade']}})]
    parents = {}
    for r in rows:
        p = parents.setdefault(r['parent_id'], {'superseded_by': r.get('superseded_by'), 'doc_number': r.get('doc_number'), 'doc_status': r.get('doc_status'), 'chunks': 0})
        p['chunks'] += 1
    resolved = resolve_superseded(parents)
    already = sum(1 for p in parents.values() if p['superseded_by'] in parents)
    print(f'superseded {sum(bool(p["superseded_by"]) for p in parents.values())}, already IDs {already}, newly resolved {len(resolved)}', flush=True)

    clone = 'exp-law-editions-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    mapping = client.indices.get_mapping(index=baseline)[baseline]['mappings']
    original = client.indices.get_settings(index=baseline)[baseline]['settings']['index']
    client.indices.create(index=clone, body={'settings': {k: original[k] for k in ('analysis', 'number_of_shards', 'number_of_replicas', 'knn') if k in original}, 'mappings': mapping})
    try:
        done = client.reindex(body={'source': {'index': baseline}, 'dest': {'index': clone}}, request_timeout=600, wait_for_completion=True)
        if done.get('failures') or done['created'] != len(rows):
            raise RuntimeError('clone incomplete')
        for parent_id, target in resolved.items():
            client.update_by_query(index=clone, body={'query': {'term': {'parent_id': parent_id}}, 'script': {'source': 'ctx._source.superseded_by = params.v', 'params': {'v': target}}}, refresh=True)
        client.indices.refresh(index=clone)
        questions = [json.loads(line) for line in args.queries.read_text().splitlines() if line.strip()]
        texts = [q['query'].strip() for q in questions]
        vectors = dict(zip(texts, OllamaEmbedder(settings).embed(texts)))
        sparse = dict(zip(texts, SparseEncoder(settings).encode(texts, settings.search_splade_query_max_length)))
        retrieval.encode_sparse_query = lambda q: sparse[q]

        class Frozen:
            def embed_query(self, q):
                return vectors[q.strip()]

        shipped = retrieval._with_current_editions
        variants = {'shipped': shipped, 'free_slots': insert_in_free_slots, 'off': lambda c, a, hits, k: hits}
        superseded_ids = {p for p, v in parents.items() if v['superseded_by']}
        out = {}
        for index_name, index in (('original', baseline), ('resolved', clone)):
            for weight in (1.0, 0.97):
                settings.search_chunk_first_superseded_weight = weight
                for variant, fn in variants.items():
                    retrieval._with_current_editions = fn
                    results = []
                    for q in questions:
                        hits = retrieval.retrieve(client, index, q['query'], AS_OF, 5, Frozen(), mode='hybrid', lexical='splade', chunk_first=True, chunk_first_cutoff_ratio=settings.search_category_cutoff_ratio, score_floor=0.0, answerability=False, rerank_chunks=False, query_rewrite=False, strict=True)
                        window = [c for h in hits for c in h.chunk_ids]
                        gold = {c for g in q['evidence_groups'] for c in g}
                        docs = list(dict.fromkeys(c.split('#')[0] for c in window))
                        results.append({'qid': q['qid'], 'rank': next((i for i, c in enumerate(window, 1) if c in gold), None), 'window': window,
                                        'gold_precision': sum(c in gold for c in window) / len(window) if window else 0,
                                        'document_hit': bool(set(docs) & set(q['gold'])), 'document_precision': sum(d in q['gold'] for d in docs) / len(docs) if docs else 0,
                                        'superseded_docs': sum(d in superseded_ids for d in docs)})
                    arm = f'{index_name}/w{weight}/{variant}'
                    base = out.get('original/w1.0/shipped', {}).get('results')
                    out[arm] = {'metrics': summarize(results), 'results': results}
                    if base:
                        out[arm]['gained'] = [b['qid'] for a, b in zip(base, results) if a['rank'] is None and b['rank'] is not None]
                        out[arm]['lost'] = [b['qid'] for a, b in zip(base, results) if a['rank'] is not None and b['rank'] is None]
                    m = out[arm]['metrics']
                    print(arm, {k: round(v, 3) for k, v in m.items() if k != 'questions'}, out[arm].get('gained'), out[arm].get('lost'), flush=True)
        retrieval._with_current_editions = shipped
    finally:
        client.indices.delete(index=clone, ignore_unavailable=True)
    (args.out / 'results.json').write_text(json.dumps({'resolved': resolved, 'arms': out}, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
