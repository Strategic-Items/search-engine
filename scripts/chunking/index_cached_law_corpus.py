"""Index a law corpus while reusing vectors from a matching experimental index.

Only chunks whose title or body changed are re-embedded/re-encoded. Intended for
controlled chunking experiments where full corpus re-embedding is needlessly slow.
"""

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from opensearchpy.helpers import scan, streaming_bulk

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.indexing.law import law_embedding_body, law_embedding_title
from search_engine.indexing.mapping import law_index_body
from search_engine.indexing.synonyms import load_synonyms
from search_engine.sparse import SparseEncoder, sparse_enabled


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--cache", required=True, help="Existing index or alias with vectors")
    parser.add_argument("--alias", required=True, help="New experimental alias")
    parser.add_argument("--prefix", required=True, help="New experimental index prefix")
    args = parser.parse_args()

    settings = get_settings()
    client = create_client(settings)
    cache = {}
    for hit in scan(client, index=args.cache, query={"query": {"match_all": {}}}):
        cache[hit["_id"]] = hit["_source"]

    rows = [json.loads(line) for line in args.corpus.read_text(encoding="utf-8").splitlines() if line.strip()]
    changed = []
    reused = 0
    for row in rows:
        old = cache.get(row["id"])
        if old and old.get("title") == row.get("title") and old.get("body") == row.get("body"):
            row["embedding"] = old.get("embedding")
            if old.get("splade") is not None:
                row["splade"] = old["splade"]
            reused += 1
        else:
            changed.append(row)

    dense_path = settings.search_dense_include_heading_path
    sparse_path = settings.search_splade_include_heading_path

    def model_input(row, include_path):
        if include_path:
            return embedding_text(law_embedding_title(row), law_embedding_body(row))
        return embedding_text(row["title"], row["body"])

    embedder = OllamaEmbedder(settings)
    sparse = SparseEncoder(settings) if sparse_enabled(settings) else None
    for start in range(0, len(changed), 32):
        batch = changed[start:start + 32]
        vectors = embedder.embed([model_input(row, dense_path) for row in batch])
        for row, vector in zip(batch, vectors):
            row["embedding"] = vector
        if sparse is not None:
            weights = sparse.encode_documents([model_input(row, sparse_path) for row in batch])
            for row, terms in zip(batch, weights):
                row["splade"] = terms

    mapping = deepcopy(law_index_body(settings.search_embedding_dimensions))
    mapping["settings"]["number_of_replicas"] = settings.search_number_of_replicas
    mapping["settings"]["analysis"]["filter"]["domain_synonyms"]["synonyms"] = load_synonyms()
    index = f"{args.prefix}{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
    client.indices.create(index=index, body=mapping)
    try:
        actions = ({"_op_type": "index", "_index": index, "_id": row["id"], "_source": row} for row in rows)
        indexed = sum(1 for ok, _ in streaming_bulk(client, actions, chunk_size=500, max_retries=3,
                                                     raise_on_error=True) if ok)
        client.indices.refresh(index=index)
        if indexed != len(rows) or client.count(index=index)["count"] != len(rows):
            raise RuntimeError("indexed count mismatch")
        old = sorted(client.indices.get_alias(name=args.alias)) if client.indices.exists_alias(name=args.alias) else []
        actions = [{"remove": {"index": item, "alias": args.alias}} for item in old]
        actions.append({"add": {"index": index, "alias": args.alias}})
        client.indices.update_aliases(body={"actions": actions})
    except Exception:
        if not client.indices.exists_alias(name=args.alias):
            client.indices.delete(index=index, ignore=[404])
        raise

    print(f"{args.alias}: {indexed} chunks; reused vectors {reused}; recomputed {len(changed)}; index {index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
