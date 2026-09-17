"""Reading a whole document, as opposed to searching for chunks of one."""

from opensearchpy import OpenSearch

from search_engine.search.results import Document, DocumentChunk

# A document is chunked, not split into volumes; this is a ceiling against a
# pathological parent, not a page size.
MAX_CHUNKS = 400

# Fields that describe the document rather than the chunk, so the first chunk
# carrying one settles it for the whole.
_DOCUMENT_FIELDS = (
    "title", "code", "source_type", "source_url",
    "published_at", "effective_from", "effective_to", "superseded_by",
)


def fetch_document(client: OpenSearch, alias: str, parent_id: str) -> Document | None:
    """Every chunk of one document, in document order.

    Chunk ids are the parent id with a zero-padded ordinal (`...#0007`), so
    sorting on the id is document order without storing a separate one.
    """
    response = client.search(
        index=alias,
        body={"query": {"bool": {"filter": [{"term": {"parent_id": parent_id}}]}},
              "sort": [{"id": "asc"}]},
        size=MAX_CHUNKS,
        ignore_unavailable=True,
    )
    hits = response["hits"]["hits"]
    if not hits:
        return None

    document = Document(parent_id=parent_id)
    for hit in hits:
        source = hit["_source"]
        for field in _DOCUMENT_FIELDS:
            # Chunks repeat the document's metadata, but a chunk that was
            # indexed without some of it should not blank what an earlier one
            # already gave.
            if not getattr(document, field) and source.get(field):
                setattr(document, field, source[field])
        document.chunks.append(DocumentChunk(id=hit["_id"], body=source.get("body", "")))
    return document
