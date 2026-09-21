import argparse
import hashlib
import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from opensearchpy import NotFoundError
from opensearchpy.helpers import streaming_bulk

from search_engine.client import create_client
from search_engine.config import get_settings
from search_engine.embeddings import OllamaEmbedder, embedding_text
from search_engine.indexing.callcenter import CallCenterChunk
from search_engine.indexing.documents import SearchDocument
from search_engine.indexing.mapping import HSK_INDEX_BODY, callcenter_index_body, index_body
from search_engine.indexing.synonyms import load_synonyms

log = logging.getLogger(__name__)

# 각 데이터셋은 자체 인덱스와 자체 별칭을 가지며 독립적으로 재구성된다.
# "core"와 "docs"는 문서 매핑을 공유하므로 한 번의 검색으로 둘 다 읽을 수 있다;
# "hsk"는 벡터가 없는 정확한 조회 테이블이다.
DATASETS = {
    "core": {"alias": "search_index_alias", "prefix": "search_index_prefix",
             "mapping": "document", "embed": True},
    "docs": {"alias": "search_docs_alias", "prefix": "search_docs_prefix",
             "mapping": "document", "embed": True},
    "callcenter": {"alias": "search_callcenter_alias", "prefix": "search_callcenter_prefix",
                   "mapping": "callcenter", "embed": True},
    "hsk": {"alias": "search_hsk_alias", "prefix": "search_hsk_prefix",
            "mapping": "hsk", "embed": False},
}


def document_actions(
    path: Path, index_name: str, embedder: OllamaEmbedder | None = None, *, callcenter: bool = False,
):
    """각 줄을 검증하고 문서 ID를 반복하는 파일을 거부한다."""
    seen = set()
    with path.open(encoding="utf-8") as file:
        for line_no, line in enumerate(file, 1):
            if not line.strip():
                continue
            try:
                doc = (CallCenterChunk.model_validate_json(line) if callcenter
                       else SearchDocument.model_validate_json(line))
            except Exception as exc:
                raise ValueError(f"invalid document at line {line_no}: {exc}") from exc
            doc_id = doc.chunk_id if callcenter else doc.id
            if doc_id in seen:
                raise ValueError(f"duplicate document ID at line {line_no}: {doc_id}")
            seen.add(doc_id)
            source = doc.index_source()
            if embedder is not None:
                source["embedding"] = embedder.embed([
                    embedding_text(source["title"], source["body"])
                ])[0]
            yield {"_op_type": "index", "_index": index_name, "_id": doc_id, "_source": source}


def current_alias_indexes(client, alias: str) -> list[str]:
    try:
        return sorted(client.indices.get_alias(name=alias))
    except NotFoundError:
        return []


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rebuild(
    path: Path, dataset: str = "core", expected_count: int | None = None,
    expected_sha256: str | None = None,
) -> tuple[str, int]:
    """완전히 새로운 인덱스를 구축하고 검증한 후 원자적으로 읽기 별칭을 이동한다."""
    if not path.is_file():
        raise FileNotFoundError(path)
    spec = DATASETS.get(dataset)
    if spec is None:
        raise ValueError(f"unknown dataset: {dataset}")
    if expected_sha256 and file_sha256(path) != expected_sha256:
        raise ValueError("input file checksum does not match manifest")
    settings = get_settings()
    client = create_client(settings)
    if not client.ping():
        raise RuntimeError("OpenSearch is unavailable")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    alias = getattr(settings, spec["alias"])
    prefix = getattr(settings, spec["prefix"])
    is_document = spec["mapping"] in ("document", "callcenter")
    mapping = deepcopy(
        index_body(settings.search_embedding_dimensions) if spec["mapping"] == "document"
        else callcenter_index_body(settings.search_embedding_dimensions)
        if spec["mapping"] == "callcenter" else HSK_INDEX_BODY
    )
    mapping["settings"]["number_of_replicas"] = settings.search_number_of_replicas
    if is_document:
        mapping["settings"]["analysis"]["filter"]["domain_synonyms"]["synonyms"] = load_synonyms()
    index_name = f"{prefix}{stamp}-{uuid4().hex[:6]}"
    client.indices.create(index=index_name, body=mapping)
    switched = False
    try:
        indexed = 0
        embedder = OllamaEmbedder(settings) if spec["embed"] else None
        for ok, item in streaming_bulk(
            client, document_actions(path, index_name, embedder, callcenter=spec["mapping"] == "callcenter"),
            chunk_size=500, max_retries=3, raise_on_error=True,
        ):
            if not ok:
                raise RuntimeError(f"bulk indexing failed: {item}")
            indexed += 1
        if indexed == 0:
            raise ValueError("refusing to publish an empty index")
        if expected_count is not None and indexed != expected_count:
            raise RuntimeError(f"input count mismatch: expected {expected_count}, got {indexed}")
        client.indices.refresh(index=index_name)
        actual = client.count(index=index_name)["count"]
        if actual != indexed:
            raise RuntimeError(f"index count mismatch: expected {indexed}, got {actual}")

        previous = current_alias_indexes(client, alias)
        actions = [{"remove": {"index": old, "alias": alias}} for old in previous]
        actions.append({"add": {"index": index_name, "alias": alias}})
        client.indices.update_aliases(body={"actions": actions})
        switched = True
        log.info("published %s (%d documents); previous indexes retained: %s",
                 index_name, indexed, previous)
        return index_name, indexed
    finally:
        if not switched:
            # 성공적인 별칭 업데이트 후 발생한 전송 오류는 모호하다.
            # 이미 읽기 요청을 처리하고 있을 수 있는 인덱스는 절대 삭제하지 않는다.
            try:
                published = index_name in current_alias_indexes(client, alias)
            except Exception:
                published = True
            if not published:
                client.indices.delete(index=index_name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the OpenSearch read index from JSONL")
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--dataset", choices=tuple(DATASETS), default="core")
    parser.add_argument("--manifest", type=Path,
                        help="Manifest from search-prepare; verifies count and SHA-256")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    expected = {}
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        expected = manifest["datasets"][args.dataset]
    index_name, count = rebuild(
        args.jsonl, dataset=args.dataset,
        expected_count=expected.get("count"),
        expected_sha256=expected.get("sha256"),
    )
    print(json.dumps({"index": index_name, "count": count}))
