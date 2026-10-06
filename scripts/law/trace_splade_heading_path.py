"""Trace SPLADE/dense ranks and RRF cutoff for changed heading_path outcomes."""
from datetime import date
import json
from pathlib import Path

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder
from search_engine.search import query as retrieval
from search_engine.sparse import SparseEncoder

OUT = Path('data/generated/splade-heading-path-2026-10-06')
TARGETS = ['law100-v1-020', 'law100-v1-093', 'law100-v1-021', 'law100-v1-022', 'law100-v1-080', 'law100-v1-058']


def main():
    previous = json.loads((OUT / 'results.json').read_text())
    meta = previous['metadata']
    queries = {q['qid']: q for q in [json.loads(line) for line in (OUT / 'queries.jsonl').read_text().splitlines()]}
    settings = get_settings()
    if settings.search_chunk_first_agreement or settings.search_chunk_first_trim:
        raise RuntimeError('Trace currently requires the recorded zero agreement/no-trim settings')
    client = create_client(settings)
    sparse = SparseEncoder(settings)
    embedder = OllamaEmbedder(settings)
    result = {'conditions': meta, 'questions': []}
    for qid in TARGETS:
        q = queries[qid]
        terms = sparse.encode_query(q['query'].strip())
        dense = client.search(index=meta['baseline_index'], body={'query': retrieval.build_vector_query(embedder.embed_query(q['query']), date.fromisoformat(meta['as_of']), meta['candidates_hybrid']['dense'], q['query']), '_source': {'excludes': ['embedding', 'splade']}}, size=meta['candidates_hybrid']['dense'])['hits']['hits']
        dr = {h['_id']: i for i, h in enumerate(dense, 1)}
        gold = {cid for group in q['evidence_groups'] for cid in group}
        source = {h['_id']: h['_source'] for h in client.mget(index=meta['baseline_index'], body={'ids': list(gold)}, _source_excludes=['embedding', 'splade'])['docs'] if h.get('found')}
        record = {'qid': qid, 'query': q['query'], 'gold': [{'id': cid, 'title': source[cid].get('title'), 'heading_path': source[cid].get('heading_path'), 'body_excerpt': source[cid].get('body', '')[:350]} for cid in sorted(gold)], 'arms': {}}
        for arm, index in [('baseline', meta['baseline_index']), ('heading_path', meta['experiment_index'])]:
            query = {'query': retrieval.build_splade_query(terms, date.fromisoformat(meta['as_of'])), '_source': {'excludes': ['embedding', 'splade']}}
            sp = client.search(index=index, body=query, size=meta['candidates_hybrid']['splade'])['hits']['hits']
            sp100 = client.search(index=index, body=query, size=100)['hits']['hits']
            sr = {h['_id']: i for i, h in enumerate(sp, 1)}
            sr100 = {h['_id']: i for i, h in enumerate(sp100, 1)}
            chunk_sources = {h['_id']: h['_source'] for h in sp + dense}
            scores = {}
            for ranked in [sp, dense]:
                for rank, h in enumerate(ranked, 1):
                    scores[h['_id']] = scores.get(h['_id'], 0) + 1 / (meta['rrf_k'] + rank)
            leaders = {ranked[0]['_id'] for ranked in [sp, dense] if ranked}
            order = sorted(scores, key=lambda cid: (-scores[cid], dr.get(cid, len(scores) + 1), cid))
            ranks = {cid: i for i, cid in enumerate(order, 1)}
            peak = scores[order[0]]
            def window(cutoff):
                groups = retrieval._chunk_first([(sp, 1, 'splade'), (dense, 1, 'vector')], q['query'], rrf_k=meta['rrf_k'], max_chunks=meta['max_chunks'], cutoff_ratio=cutoff, max_documents=meta['max_documents'], chunks_per_document=meta['per_document'], agreement=0)
                hits = []
                for group in groups:
                    lead = group[0]
                    source = lead['_source']
                    hits.append(retrieval.SearchHit.model_validate({
                        **{k: v for k, v in source.items() if v is not None},
                        'id': lead['_id'], 'parent_id': source.get('parent_id') or lead['_id'],
                        'score': lead['_score'],
                        'passages': [retrieval.Passage(id=h['_id'], body=h['_source'].get('body', ''), score=h['_score']) for h in group[1:]],
                    }))
                before_editions = [cid for hit in hits for cid in hit.chunk_ids]
                before_parents = [hit.parent_id for hit in hits]
                hits = retrieval._with_current_editions(client, index, hits, meta['max_documents'])
                return {'before_editions': before_editions, 'before_parents': before_parents, 'after_parents': [hit.parent_id for hit in hits], 'window': [cid for hit in hits for cid in hit.chunk_ids], 'added_editions': [hit.parent_id for hit in hits if hit.parent_id not in before_parents]}
            selection = window(meta['hybrid_cutoff'])
            uncut_selection = window(0)
            selected = selection['window']
            no_cutoff = uncut_selection['window']
            old = next(r for r in previous['outcomes'][arm]['hybrid']['results'] if r['qid'] == qid)
            if selected != old['window']:
                raise RuntimeError(f'Replay differs from original experiment: {qid}/{arm}')
            details = []
            for cid in sorted(gold):
                ratio = scores.get(cid, 0) / peak
                if cid not in scores:
                    reason = 'Not in either top-25 candidate list'
                elif ratio < meta['hybrid_cutoff'] and cid not in leaders:
                    reason = 'Below 95% RRF cutoff'
                elif cid not in selected and cid in selection['before_editions']:
                    reason = 'Document limit after adding current editions'
                elif cid not in selected:
                    reason = 'Selection budget, duplicate edition, or document/chunk limit'
                else:
                    reason = 'Returned'
                details.append({'id': cid, 'splade_rank_25': sr.get(cid), 'splade_rank_100': sr100.get(cid), 'dense_rank_25': dr.get(cid), 'fused_rank': ranks.get(cid), 'rrf_score': scores.get(cid, 0), 'ratio_to_best': ratio, 'leader_exempt': cid in leaders, 'returned': cid in selected, 'returned_without_cutoff': cid in no_cutoff, 'reason': reason})
            top = [{'id': cid, 'title': chunk_sources[cid].get('title'), 'body_excerpt': chunk_sources[cid].get('body', '')[:300], 'splade_rank': sr.get(cid), 'dense_rank': dr.get(cid), 'score': scores[cid], 'ratio': scores[cid] / peak, 'leader_exempt': cid in leaders, 'returned': cid in selected} for cid in order[:10]]
            record['arms'][arm] = {'best_score': peak, 'cutoff_score': peak * meta['hybrid_cutoff'], 'gold_trace': details, 'top_fused': top, 'window': selected, 'edition_selection': selection, 'window_without_cutoff': no_cutoff, 'uncut_edition_selection': uncut_selection, 'recall_without_cutoff': bool(set(no_cutoff) & gold)}
        result['questions'].append(record)
        (OUT / 'trace.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(qid, flush=True)
        for arm, data in record['arms'].items():
            print(arm, [(g['id'].split('#')[-1], g['splade_rank_100'], g['dense_rank_25'], g['fused_rank'], round(g['ratio_to_best'], 4), g['reason']) for g in data['gold_trace']], flush=True)
    (OUT / 'trace.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('Saved', OUT / 'trace.json', flush=True)


if __name__ == '__main__':
    main()
