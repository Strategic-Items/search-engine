"""청킹 버전별 색인 산출물(임베딩 포함)을 보관하고 되살린다.

버전 N의 인덱스를 `data/chunking_artifacts/v<N>/`에 문서 전체(`_source`: 본문, dense 임베딩, SPLADE 가중치)로 저장해 두면, 나중에 청커를
v10까지 바꾼 뒤에도 v1을 임베딩을 다시 만들지 않고 인덱스로 되살려 같은 질문으로 다시 잴 수 있다. 큰 파일이라 git에는 넣지 않는다
(`.gitignore`). 보관본의 무결성은 manifest의 SHA-256이 지킨다.

    .venv/bin/python scripts/chunking/version_artifacts.py save    --version 1 --index exp-chk-law-port [--corpus law.jsonl]
    .venv/bin/python scripts/chunking/version_artifacts.py restore --version 1 [--alias exp-chk-law-v1-restored]
    .venv/bin/python scripts/chunking/version_artifacts.py list

되살린 인덱스는 새 이름의 별칭으로만 붙는다. 서비스 별칭(`search-law` 등)에는 붙이지 않는다.
"""

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from opensearchpy.helpers import scan, streaming_bulk

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "data/chunking_artifacts"
SERVICE_ALIASES = {"search-law", "search-admin", "search-docs", "search-documents", "search-hsk", "search-callcenter"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def client_and_settings():
    sys.path.insert(0, str(ROOT))
    from search_engine.client import create_client
    from search_engine.config import get_settings

    settings = get_settings()
    return create_client(settings), settings


def save(version: int, index: str, corpus: Path | None) -> None:
    from search_engine.chunking.params import CHUNKER_VERSION

    client, settings = client_and_settings()
    target = DIR / f"v{version}"
    target.mkdir(parents=True, exist_ok=True)
    physical = sorted(client.indices.get_alias(name=index)) if client.indices.exists_alias(name=index) else [index]
    if len(physical) != 1:
        raise ValueError(f"{index}가 인덱스 하나를 가리키지 않는다: {physical}")
    rows = sorted(({"_id": h["_id"], **h["_source"]} for h in scan(
        client, index=physical[0], query={"query": {"match_all": {}}}, size=500)), key=lambda r: r["_id"])
    if not rows:
        raise ValueError("빈 인덱스는 보관하지 않는다")
    if not all("embedding" in r for r in rows):
        raise ValueError("임베딩이 없는 문서가 있다 -- 임베딩까지 든 인덱스만 보관한다")
    path = target / "index.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    if corpus is not None:
        with corpus.open("rb") as src, gzip.open(target / "corpus.jsonl.gz", "wb") as dst:
            dst.write(src.read())
    manifest = {
        "version": version, "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_index": physical[0], "documents": len({r["parent_id"] for r in rows}), "chunks": len(rows),
        "has_splade": all("splade" in r for r in rows), "embedding_dimensions": len(rows[0]["embedding"]),
        "embedding_model": settings.ollama_embedding_model, "splade_model": settings.search_splade_model,
        "dense_include_heading_path": settings.search_dense_include_heading_path,
        "splade_include_heading_path": settings.search_splade_include_heading_path,
        "chunker_version_in_code": CHUNKER_VERSION, "search_engine_commit": git("rev-parse", "--short", "HEAD"),
        "dirty": bool(git("status", "--porcelain", "--", "search_engine")),
        "files": {"index.jsonl.gz": {"sha256": sha256(path), "bytes": path.stat().st_size}},
    }
    if corpus is not None:
        manifest["files"]["corpus.jsonl.gz"] = {"sha256": sha256(target / "corpus.jsonl.gz"), "bytes": (target / "corpus.jsonl.gz").stat().st_size}
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"v{version}: {len(rows)}청크 -> {path} ({path.stat().st_size / 1e6:.1f}MB)")


def restore(version: int, alias: str | None) -> None:
    from search_engine.indexing.mapping import law_index_body
    from search_engine.indexing.synonyms import load_synonyms

    target = DIR / f"v{version}"
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    path = target / "index.jsonl.gz"
    if sha256(path) != manifest["files"]["index.jsonl.gz"]["sha256"]:
        raise ValueError("보관본의 SHA-256이 manifest와 다르다")
    alias = alias or f"exp-chk-law-v{version}-restored"
    if alias in SERVICE_ALIASES:
        raise ValueError(f"서비스 별칭 {alias}에는 되살리지 않는다")
    client, settings = client_and_settings()
    mapping = deepcopy(law_index_body(manifest["embedding_dimensions"]))
    mapping["settings"]["number_of_replicas"] = settings.search_number_of_replicas
    mapping["settings"]["analysis"]["filter"]["domain_synonyms"]["synonyms"] = load_synonyms()
    index = f"{alias}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}"
    client.indices.create(index=index, body=mapping)

    def actions():
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                yield {"_op_type": "index", "_index": index, "_id": row.pop("_id"), "_source": row}

    count = 0
    for ok, item in streaming_bulk(client, actions(), chunk_size=500, max_retries=3, raise_on_error=True):
        if not ok:
            raise RuntimeError(f"bulk indexing failed: {item}")
        count += 1
    client.indices.refresh(index=index)
    if client.count(index=index)["count"] != manifest["chunks"] or count != manifest["chunks"]:
        raise RuntimeError("복원한 문서 수가 manifest와 다르다")
    old = sorted(client.indices.get_alias(name=alias)) if client.indices.exists_alias(name=alias) else []
    client.indices.update_aliases(body={"actions": [{"remove": {"index": i, "alias": alias}} for i in old] + [{"add": {"index": index, "alias": alias}}]})
    print(f"v{version}: {count}청크 -> {index} (별칭 {alias}). 평가: eval_category_chunking.py --reference search-law --arm v{version}={alias}")


def list_versions() -> None:
    for manifest in sorted(DIR.glob("v*/manifest.json"), key=lambda p: int(p.parent.name[1:])):
        m = json.loads(manifest.read_text(encoding="utf-8"))
        size = sum(f["bytes"] for f in m["files"].values()) / 1e6
        print(f"v{m['version']}\t{m['chunks']}청크\t{size:.0f}MB\t{m['embedding_model']}\tSPLADE={'예' if m['has_splade'] else '아니오'}\t"
              f"커밋 {m['search_engine_commit']}{'+dirty' if m['dirty'] else ''}\t{m['saved_at']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("save")
    p.add_argument("--version", type=int, required=True)
    p.add_argument("--index", required=True, help="보관할 인덱스 또는 별칭")
    p.add_argument("--corpus", type=Path, help="이 버전이 만든 코퍼스 jsonl(임베딩 없는 원본)도 같이 보관")
    p = sub.add_parser("restore")
    p.add_argument("--version", type=int, required=True)
    p.add_argument("--alias")
    sub.add_parser("list")
    args = parser.parse_args()
    if args.command == "save":
        save(args.version, args.index, args.corpus)
    elif args.command == "restore":
        restore(args.version, args.alias)
    else:
        list_versions()
    return 0


if __name__ == "__main__":
    sys.exit(main())
