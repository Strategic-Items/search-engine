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
from search_engine.indexing.law import law_embedding_body, law_embedding_title, law_source
from search_engine.indexing.identity import FIRST_CHUNK_INDEX, chunk_index, download_copies, period_hint
from search_engine.indexing.mapping import HSK_INDEX_BODY, callcenter_index_body, index_body, law_index_body
from search_engine.indexing.synonyms import load_synonyms
from search_engine.sparse import SparseEncoder, sparse_enabled

# 임베딩은 문서마다 한 번씩 부르면 호출 비용이 대부분을 차지한다. ollama는
# 병렬 요청을 직렬로 처리하므로(2026-09-22 측정, 4병렬이 1.6배에 그친다)
# 묶어 보내는 것만이 효과가 있다 -- 32묶음이 한 건씩 보낼 때의 2.8배다.
EMBED_BATCH = 32

log = logging.getLogger(__name__)

# 각 데이터셋은 자체 인덱스와 자체 별칭을 가지며 독립적으로 재구성된다.
# "core"와 "docs"는 문서 매핑을 공유하므로 한 번의 검색으로 둘 다 읽을 수 있다;
# "hsk"는 벡터가 없는 정확한 조회 테이블이다.
DATASETS = {
    "core": {"alias": "search_index_alias", "prefix": "search_index_prefix",
             "mapping": "document", "embed": True},
    "docs": {"alias": "search_docs_alias", "prefix": "search_docs_prefix",
             "mapping": "document", "embed": True},
    "law": {"alias": "search_law_alias", "prefix": "search_law_prefix",
            "mapping": "law", "embed": True},
    "admin": {"alias": "search_admin_alias", "prefix": "search_admin_prefix",
              "mapping": "law", "embed": True},
    "callcenter": {"alias": "search_callcenter_alias", "prefix": "search_callcenter_prefix",
                   "mapping": "callcenter", "embed": True},
    "hsk": {"alias": "search_hsk_alias", "prefix": "search_hsk_prefix",
            "mapping": "hsk", "embed": False},
}


def parent_identity(path: Path) -> tuple[set[str], dict[str, str]]:
    """쓰기 전에 한 번 읽어 부모 단위의 사실을 정한다.

    사본이냐 아니냐도, 앞머리가 말하는 시점도 부모의 성질이라 줄 단위로
    흘려보내면서는 정할 수 없다. 파일을 두 번 읽는 대신 색인 한 번을
    통째로 메모리에 들고 있는 쪽이 더 나쁘다.
    """
    parents: dict[str, dict] = {}
    with path.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            parent_id = row.get("parent_id") or row.get("id")
            if not parent_id:
                continue
            parent = parents.setdefault(parent_id, {
                "parent_id": parent_id,
                "source_path": row.get("source_path") or "",
                "published_at": row.get("published_at"),
                "head": "",
            })
            # 앞머리는 첫 청크의 것이어야 한다. 줄이 순서대로 온다는 보장이 없다.
            # 첫 청크는 0번이다 -- 규약은 prepare가 검사한다.
            if chunk_index(row) == FIRST_CHUNK_INDEX:
                parent["head"] = row.get("body") or ""
    hints = {parent_id: period_hint(parent["head"])
             for parent_id, parent in parents.items() if not parent["published_at"]}
    return download_copies(list(parents.values())), {k: v for k, v in hints.items() if v}


def _sources(path: Path, callcenter: bool, dropped: list | None, law: bool = False):
    """줄마다 검증해 색인할 _source를 내놓는다. 임베딩은 아직 붙이지 않는다."""
    seen = set()
    copies, hints = (set(), {}) if callcenter else parent_identity(path)
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
            if law:
                source = law_source(source)
            if source["parent_id"] in copies:
                if dropped is not None:
                    dropped.append(doc_id)
                continue
            hint = hints.get(source["parent_id"])
            if hint:
                source["period_hint"] = hint
            yield doc_id, source


def document_actions(
    path: Path, index_name: str, embedder: OllamaEmbedder | None = None, *, callcenter: bool = False,
    dropped: list | None = None, batch: int = EMBED_BATCH, law: bool = False,
    sparse: SparseEncoder | None = None,
    sparse_heading_path: bool = False,
    dense_heading_path: bool = True,
):
    """각 줄을 검증하고 문서 ID를 반복하는 파일을 거부한다."""
    pending: list[tuple[str, dict]] = []

    def embedding_input(source: dict, include_heading_path: bool) -> str:
        if law and include_heading_path:
            return embedding_text(law_embedding_title(source), law_embedding_body(source))
        return embedding_text(source["title"], source["body"])

    def flush():
        if embedder is not None:
            vectors = embedder.embed([embedding_input(s, dense_heading_path) for _, s in pending])
            for (_, source), vector in zip(pending, vectors):
                source["embedding"] = vector
        if sparse is not None:
            # 기본은 학습·측정 당시의 title+body. 옵션을 켜면 dense와 같은 제목 경로를 추가한다.
            terms = sparse.encode_documents([embedding_input(s, sparse_heading_path) for _, s in pending])
            for (_, source), weights in zip(pending, terms):
                source["splade"] = weights
        for doc_id, source in pending:
            yield {"_op_type": "index", "_index": index_name, "_id": doc_id, "_source": source}
        pending.clear()

    for doc_id, source in _sources(path, callcenter, dropped, law):
        pending.append((doc_id, source))
        if len(pending) >= batch:
            yield from flush()
    yield from flush()


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


def encoding_metadata(settings, corpus_sha256: str) -> dict:
    """Persist the settings that actually produced a physical category index."""
    checkpoint = Path(settings.search_splade_model)
    checkpoint_files = sorted(checkpoint.glob("*.safetensors")) if checkpoint.is_dir() else []
    if checkpoint.is_dir() and not checkpoint_files:
        checkpoint_files = sorted(checkpoint.glob("pytorch_model*.bin"))
    return {
        "input_version": "normalized-law-path-v1",
        "corpus_sha256": corpus_sha256,
        "dense_model": settings.ollama_embedding_model,
        "dense_heading_path": settings.search_dense_include_heading_path,
        "sparse_model": settings.search_splade_model,
        "sparse_checkpoint_sha256": {path.name: file_sha256(path) for path in checkpoint_files},
        "sparse_heading_path": settings.search_splade_include_heading_path,
        "sparse_doc_max_length": settings.search_splade_doc_max_length,
        "sparse_document_strategy": "overlapping-windows-max-pool-v1",
        "sparse_window_overlap": min(64, settings.search_splade_doc_max_length - 3),
        "sparse_top_terms": settings.search_splade_top_terms,
        "sparse_min_weight": settings.search_splade_min_weight,
    }


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
    is_document = spec["mapping"] in ("document", "callcenter", "law")
    mapping = deepcopy(
        index_body(settings.search_embedding_dimensions) if spec["mapping"] == "document"
        else law_index_body(settings.search_embedding_dimensions) if spec["mapping"] == "law"
        else callcenter_index_body(settings.search_embedding_dimensions)
        if spec["mapping"] == "callcenter" else HSK_INDEX_BODY
    )
    mapping["settings"]["number_of_replicas"] = settings.search_number_of_replicas
    if spec["mapping"] == "law":
        mapping["mappings"]["_meta"] = encoding_metadata(settings, file_sha256(path))
    if is_document:
        mapping["settings"]["analysis"]["filter"]["domain_synonyms"]["synonyms"] = load_synonyms()
    index_name = f"{prefix}{stamp}-{uuid4().hex[:6]}"
    client.indices.create(index=index_name, body=mapping)
    switched = False
    try:
        indexed = 0
        dropped: list[str] = []
        embedder = OllamaEmbedder(settings) if spec["embed"] else None
        # 카테고리(law 매핑) 인덱스에만 SPLADE 벡터를 싣는다. 모델이 설정돼 있을 때만.
        sparse = SparseEncoder(settings) if spec["mapping"] == "law" and sparse_enabled(settings) else None
        for ok, item in streaming_bulk(
            client, document_actions(path, index_name, embedder,
                                     callcenter=spec["mapping"] == "callcenter", dropped=dropped,
                                     law=spec["mapping"] == "law", sparse=sparse,
                                     sparse_heading_path=settings.search_splade_include_heading_path,
                                     dense_heading_path=settings.search_dense_include_heading_path),
            chunk_size=500, max_retries=3, raise_on_error=True,
        ):
            if not ok:
                raise RuntimeError(f"bulk indexing failed: {item}")
            indexed += 1
        if indexed == 0:
            raise ValueError("refusing to publish an empty index")
        if dropped:
            log.info("dropped %d chunk(s) from download copies", len(dropped))
        # 매니페스트는 입력 줄 수를 센 것이므로 지운 사본을 되돌려 놓고 맞춰야
        # 한다. 그러지 않으면 사본이 있는 코퍼스가 전부 검증에서 걸린다.
        if expected_count is not None and indexed + len(dropped) != expected_count:
            raise RuntimeError(
                f"input count mismatch: expected {expected_count}, "
                f"got {indexed} indexed + {len(dropped)} dropped")
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
    parser.add_argument("jsonl", type=Path, nargs="?",
                        help="law·admin 데이터셋은 생략하면 SEARCH_LAW_SOURCE·SEARCH_ADMIN_SOURCE를 읽는다")
    parser.add_argument("--dataset", choices=tuple(DATASETS), default="core")
    parser.add_argument("--manifest", type=Path,
                        help="Manifest from search-prepare; verifies count and SHA-256")
    args = parser.parse_args()
    if args.jsonl is None:
        if args.dataset not in ("law", "admin"):
            parser.error("jsonl is required")
        args.jsonl = Path(getattr(get_settings(), f"search_{args.dataset}_source"))
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
