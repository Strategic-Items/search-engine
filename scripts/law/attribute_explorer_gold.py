"""Add comparison-only gold chunks and attribution without changing retrieval results."""
import json
from attribute_dense import load_object, DETAIL, CATEGORIES, tidy, cosine, chunks, SEG_SIZE
from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.sparse import SparseEncoder


def main():
    cath, span, txt = load_object(DETAIL, 'CATH')
    catb, _, _ = load_object(DETAIL, 'CATB')
    catd, _, _ = load_object(CATEGORIES, 'CATD')
    queries = {(s, r['i']): r['q'] for s, rows in catd.items() for r in rows}
    settings = get_settings()
    client, embedder, encoder = create_client(settings), OllamaEmbedder(settings), SparseEncoder(settings)
    for s, qs in cath.items():
        for qid, d in sorted(qs.items(), key=lambda item: (item[0] != "077", item[0])):
            if not d['gc'] or d.get('gold_attribution_version') == 1:
                continue
            query = queries[s, qid]
            terms = encoder.encode_query(query)
            ids = d['gc']
            found = client.mget(index={'law100':'search-law', 'admin30':'search-admin', 'faq30':'search-callcenter'}[s], body={'ids':ids})['docs']
            docs = {h['_id']:h['_source'] for h in found if h.get('found')}
            if len(docs) != len(ids):
                # Older offline corpora may no longer be indexed; encode their saved bodies.
                missing = [c for c in ids if c not in docs]
                vectors = encoder.encode_documents([embedding_text(*catb[c]) for c in missing])
                docs.update({c:{'splade':v} for c,v in zip(missing,vectors)})
            cached_gold = {h['c']:h for h in d.get('dn_gold', []) if h.get('attr') and h.get('cs')}
            d['sp_gold'], d['dn_gold'] = [], []
            words = query.split()
            pending_dense = [c for c in ids if c not in cached_gold and not any(h['c']==c for h in d['dn'])]
            qvs = embedder.embed([query]+[' '.join(words[:i]+words[i+1:]) for i in range(len(words))]) if pending_dense else []
            for c in ids:
                if not any(h['c']==c for h in d['sp']):
                    dw = docs[c].get('splade', {})
                    contrib = sorted([(encoder._tokenizer.convert_ids_to_tokens(int(k[1:])).replace('##','').replace('▁',''), round(w*dw[k],2)) for k,w in terms.items() if k in dw], key=lambda z:-z[1])
                    rank = d.get('gold_ranks', {}).get(c, [None, None])[0] or next((r[1] for r in d['fx']['sp']['cr'] if r[0]==c), None)
                    d['sp_gold'].append({'c':c,'s':round(sum(w*dw.get(k,0) for k,w in terms.items()),2),'t':contrib[:12],'g':1,'rank':rank,'comparison':True})
                if any(h['c']==c for h in d['dn']):
                    continue
                if c in cached_gold:
                    hit = cached_gold[c]
                    hit['rank'] = d.get('gold_ranks', {}).get(c, [None, None])[1]
                    d['dn_gold'].append(hit)
                    continue
                title, body = catb[c]
                cw = tidy(body).split()
                segs = chunks(cw, SEG_SIZE)
                texts = [embedding_text(title, ' '.join(cw))]
                pos = 0
                for seg in segs:
                    texts.append(embedding_text(title, ' '.join(cw[:pos]+cw[pos+len(seg):])))
                    pos += len(seg)
                vs = embedder.embed(texts)
                base = cosine(qvs[0], vs[0])
                rank = d.get('gold_ranks', {}).get(c, [None, None])[1] or next((r[1] for r in d['fx']['dn']['cr'] if r[0]==c), None)
                d['dn_gold'].append({'c':c,'s':round((1+base)/2,4),'g':1,'rank':rank,'comparison':True,'cs':[[ ' '.join(seg),round(base-cosine(qvs[0],v),4)] for seg,v in zip(segs,vs[1:])], 'attr':{'w':words,'base':round(base,3),'d':[round(base-cosine(v,vs[0]),4) for v in qvs[1:]]}})
            d['gold_attribution_version'] = 1
            new = json.dumps(cath,ensure_ascii=False,separators=(',',':'))
            DETAIL.write_text(txt[:span[0]]+new+txt[span[1]:],encoding='utf-8')
            print(s,qid,'gold attribution saved',flush=True)

if __name__ == '__main__':
    main()
