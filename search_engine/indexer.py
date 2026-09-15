import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from opensearchpy import NotFoundError
from opensearchpy.helpers import streaming_bulk

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.documents import SearchDocument
from search_engine.mapping import INDEX_BODY

log = logging.getLogger(__name__)


def document_actions(path: Path, index_name: str):
    seen = set()
    with path.open(encoding="utf-8") as file:
        for line_no, line in enumerate(file, 1):
            if not line.strip():
                continue
            try:
                doc = SearchDocument.model_validate_json(line)
            except Exception as exc:
                raise ValueError(f"invalid document at line {line_no}: {exc}") from exc
            if doc.id in seen:
                raise ValueError(f"duplicate document ID at line {line_no}: {doc.id}")
            seen.add(doc.id)
            yield {"_op_type": "index", "_index": index_name, "_id": doc.id,
                   "_source": doc.index_source()}


def current_alias_indexes(client, alias: str) -> list[str]:
    try:
        return sorted(client.indices.get_alias(name=alias))
    except NotFoundError:
        return []


def rebuild(path: Path) -> tuple[str, int]:
    """Build a complete new index, verify it, then atomically move the read alias."""
    if not path.is_file():
        raise FileNotFoundError(path)
    settings = get_settings()
    client = create_client(settings)
    if not client.ping():
        raise RuntimeError("OpenSearch is unavailable")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    index_name = f"{settings.search_index_prefix}{stamp}-{uuid4().hex[:6]}"
    client.indices.create(index=index_name, body=INDEX_BODY)
    switched = False
    try:
        indexed = 0
        for ok, item in streaming_bulk(
            client, document_actions(path, index_name),
            chunk_size=500, max_retries=3, raise_on_error=True,
        ):
            if not ok:
                raise RuntimeError(f"bulk indexing failed: {item}")
            indexed += 1
        if indexed == 0:
            raise ValueError("refusing to publish an empty index")
        client.indices.refresh(index=index_name)
        actual = client.count(index=index_name)["count"]
        if actual != indexed:
            raise RuntimeError(f"index count mismatch: expected {indexed}, got {actual}")

        previous = current_alias_indexes(client, settings.search_index_alias)
        actions = [{"remove": {"index": old, "alias": settings.search_index_alias}}
                   for old in previous]
        actions.append({"add": {"index": index_name, "alias": settings.search_index_alias}})
        client.indices.update_aliases(body={"actions": actions})
        switched = True
        log.info("published %s (%d documents); previous indexes retained: %s",
                 index_name, indexed, previous)
        return index_name, indexed
    finally:
        if not switched:
            # A transport error after a successful alias update is ambiguous.
            # Never delete an index that may already be serving reads.
            try:
                published = index_name in current_alias_indexes(client, settings.search_index_alias)
            except Exception:
                published = True
            if not published:
                client.indices.delete(index=index_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the OpenSearch read index from JSONL")
    parser.add_argument("jsonl", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    index_name, count = rebuild(args.jsonl)
    print(json.dumps({"index": index_name, "count": count}))
