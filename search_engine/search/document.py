"""문서 전체를 읽는 것, 하나의 청크를 검색하는 것과는 대조적으로."""

from opensearchpy import OpenSearch

from search_engine.search.results import Document, DocumentChunk

# 문서는 분할되지 않고 청크로 나뉜다; 이것은 병리적인 부모에 대한 상한선이다.
# 병리적인 부모에 대한 상한선이지, 페이지 크기가 아니다.
MAX_CHUNKS = 400

# 청크보다는 문서를 설명하는 필드이므로 첫 번째 청크가 하나를 담으면 전체에 대해 결정된다.
# 첫 번째 청크가 하나를 담으면 전체에 대해 결정된다.
_DOCUMENT_FIELDS = (
    "title", "code", "source_type", "source_url",
    "published_at", "effective_from", "effective_to", "superseded_by",
)


def fetch_document(client: OpenSearch, alias: str, parent_id: str) -> Document | None:
    """문서 순서대로 한 문서의 각 조각.

조각 ID는 부모 ID에 0으로 채워진 순서번호(`...#0007`)를 붙인 것이므로,
ID를 정렬하면 별도의 순서를 저장하지 않고도 문서 순서를 얻을 수 있다.
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
            # 조각은 문서의 메타데이터를 반복하지만, 일부 메타데이터 없이 인덱싱된 조각은 이전 조각이 이미 제공한 것을 비우지 않아야 한다.
            # 인덱싱된 조각은 문서의 메타데이터를 반복하지만, 일부 메타데이터 없이 인덱싱된 조각은 이전 조각이 이미 제공한 것을 비우지 않아야 한다.
            # 인덱싱된 조각은 문서의 메타데이터를 반복하지만, 일부 메타데이터 없이 인덱싱된 조각은 이전 조각이 이미 제공한 것을 비우지 않아야 한다.
            if not getattr(document, field) and source.get(field):
                setattr(document, field, source[field])
        document.chunks.append(DocumentChunk(id=hit["_id"], body=source.get("body", "")))
    return document
