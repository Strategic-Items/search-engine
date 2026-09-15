"""Prepare the reviewed lab snapshot for separate core and HSK indexes."""

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from search_engine.documents import SearchDocument
from search_engine.indexer import file_sha256

CORE_TYPES = {"FAQ", "민원서식", "공지사항", "판정 안내", "허가 안내", "이용 안내"}
FORM_TYPE = "민원서식"
# 「전략물자수출입고시」의 서식은 별지·별표 번호로 자리를 잡는다. 같은 자리의
# 새 판이 올라오면 옛 판은 대체된다. 제목 형식은 두 가지가 섞여 있다:
# "[38차 개정, 26.9.1] 별지 4." 와 "[별지 제4호 서식]".
FORM_SLOT = re.compile(r"(별지|별표)\s*(?:제\s*)?(\d+)\s*(?:호)?\s*(?:의\s*(\d+))?")
# 다른 법령의 서식은 번호 체계가 달라 같은 자리로 볼 수 없다.
OTHER_STATUTE = re.compile(r"[가-힣]{2,}법(?:\s*시행(?:령|규칙))?\s*별지")
HSK_TYPE = "HSK 연계표"
# Lab review found that this undated FAQ conflicts with the current self-judgement guide.
EXCLUDED_CORE_IDS = {"faq-042": "conflicts_with_current_self_judgement_guide"}


def form_slot(title: str) -> tuple[str, str] | None:
    """The 별지/별표 slot a form occupies, or None when it is not one."""
    if OTHER_STATUTE.search(title):
        return None
    match = FORM_SLOT.search(title)
    if not match:
        return None
    suffix = f"의{match.group(3)}" if match.group(3) else ""
    return match.group(1), match.group(2) + suffix


def supersessions(rows: list[dict]) -> dict[str, str]:
    """Map each outdated form to the newest form in the same slot.

    Superseded forms are kept and indexed. The published record is public and
    people do ask for an earlier edition by its year; search demotes them
    instead of hiding them.
    """
    slots = {}
    for row in rows:
        slot = form_slot(row["title"])
        published = row.get("published_at")
        if slot and published:
            slots.setdefault(slot, []).append((published, row["parent_id"]))
    superseded = {}
    for versions in slots.values():
        versions.sort()
        newest_date, newest_id = versions[-1]
        for published, parent_id in versions[:-1]:
            if published < newest_date and parent_id != newest_id:
                superseded[parent_id] = newest_id
    return superseded


def _date_basis(row: dict) -> str:
    if row.get("effective_from") or row.get("effective_to"):
        return "effective"
    if row.get("published_at"):
        return "publication_only"
    return "undated"


def _prepare_row(row: dict, source_type: str) -> dict:
    source = {**row, "source_type": source_type,
              "source_url": row.get("source_url") or ""}
    if source_type == "민원서식":
        source_id = str(row.get("source_id") or "")
        match = re.fullmatch(r"form-(\d+)", source_id)
        if match:
            source["source_url"] = f"https://www.yestrade.go.kr/user/boards/70/posts/{match.group(1)}"
    if source_type in CORE_TYPES:
        source["date_basis"] = _date_basis(row)
    if not source.get("content_hash"):
        content = "\n".join(str(source.get(k) or "") for k in ("title", "body", "code"))
        source["content_hash"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if source_type == HSK_TYPE:
        hsk_code = str(source.get("hsk_code") or "")
        if not (len(hsk_code) == 10 and hsk_code.isdigit()):
            raise ValueError(f"invalid 10-digit HSK code: {hsk_code!r}")
        if not source["source_url"]:
            raise ValueError(f"HSK row has no source URL: {source.get('id')}")
    return SearchDocument.model_validate(source).model_dump(mode="json", exclude_none=True)


def _form_parents(source_path: Path) -> list[dict]:
    """One row per form parent, read ahead so supersession is known before writing."""
    seen = {}
    with source_path.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("source_type") != FORM_TYPE or row.get("id") in EXCLUDED_CORE_IDS:
                continue
            parent_id = row.get("parent_id") or row.get("id")
            seen.setdefault(parent_id, {"parent_id": parent_id,
                                        "title": row.get("title") or "",
                                        "published_at": row.get("published_at")})
    return list(seen.values())


def prepare(source_path: Path, out_dir: Path) -> dict:
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    source_sha = file_sha256(source_path)
    source_manifest_path = source_path.parent / f"{source_path.stem}.manifest.json"
    source_manifest_sha = None
    if source_manifest_path.is_file():
        source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        if source_manifest.get("corpus_sha256") != source_sha:
            raise ValueError("lab corpus does not match its source manifest")
        source_manifest_sha = file_sha256(source_manifest_path)

    superseded = supersessions(_form_parents(source_path))

    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_core = out_dir / f".core-{uuid4().hex}.tmp"
    tmp_hsk = out_dir / f".hsk-{uuid4().hex}.tmp"
    counts = {"core": Counter(), "hsk": Counter()}
    parents = {"core": set(), "hsk": set()}
    ids = {"core": set(), "hsk": set()}
    ranges = {"core": [], "hsk": []}
    excluded = Counter()
    try:
        with source_path.open(encoding="utf-8") as input_file, \
                tmp_core.open("w", encoding="utf-8") as core_file, \
                tmp_hsk.open("w", encoding="utf-8") as hsk_file:
            for line_no, line in enumerate(input_file, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    source_type = row.get("source_type") or "FAQ"
                    if source_type not in CORE_TYPES and source_type != HSK_TYPE:
                        continue
                    if row.get("id") in EXCLUDED_CORE_IDS:
                        excluded[EXCLUDED_CORE_IDS[row["id"]]] += 1
                        continue
                    dataset = "hsk" if source_type == HSK_TYPE else "core"
                    prepared = _prepare_row(row, source_type)
                except Exception as exc:
                    raise ValueError(f"invalid source line {line_no}: {exc}") from exc
                doc_id = prepared["id"]
                if doc_id in ids[dataset]:
                    raise ValueError(f"duplicate {dataset} document ID: {doc_id}")
                ids[dataset].add(doc_id)
                parents[dataset].add(prepared.get("parent_id") or doc_id)
                counts[dataset][source_type] += 1
                counts[dataset]["missing_source_url"] += not bool(prepared.get("source_url"))
                counts[dataset]["missing_published_at"] += not bool(prepared.get("published_at"))
                counts[dataset]["missing_effective_from"] += not bool(prepared.get("effective_from"))
                if prepared.get("published_at"):
                    ranges[dataset].append(prepared["published_at"])
                replacement = superseded.get(prepared.get("parent_id") or doc_id)
                if replacement:
                    prepared["superseded_by"] = replacement
                    counts[dataset]["superseded"] += 1
                output = hsk_file if dataset == "hsk" else core_file
                output.write(json.dumps(prepared, ensure_ascii=False) + "\n")

        if len(ids["core"]) == 0 or len(ids["hsk"]) == 0:
            raise ValueError("core and HSK datasets must both be nonempty")

        core_path = out_dir / "core.jsonl"
        hsk_path = out_dir / "hsk.jsonl"
        os.replace(tmp_core, core_path)
        os.replace(tmp_hsk, hsk_path)
        datasets = {}
        for dataset, path in (("core", core_path), ("hsk", hsk_path)):
            datasets[dataset] = {
                "count": len(ids[dataset]),
                "parent_count": len(parents[dataset]),
                "source_types": {k: v for k, v in sorted(counts[dataset].items())
                                 if not k.startswith("missing_")},
                "missing_source_url": counts[dataset]["missing_source_url"],
                "missing_published_at": counts[dataset]["missing_published_at"],
                "missing_effective_from": counts[dataset]["missing_effective_from"],
                "superseded": counts[dataset]["superseded"],
                "published_min": min(ranges[dataset]) if ranges[dataset] else None,
                "published_max": max(ranges[dataset]) if ranges[dataset] else None,
                "sha256": file_sha256(path),
            }
        manifest = {
            "schema_version": 1,
            "prepared_at": datetime.now(timezone.utc).isoformat(),
            "source_path": str(source_path.resolve()),
            "source_sha256": source_sha,
            "source_manifest_sha256": source_manifest_sha,
            "datasets": datasets,
            "excluded": dict(excluded),
        }
        manifest_path = out_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        return manifest
    finally:
        tmp_core.unlink(missing_ok=True)
        tmp_hsk.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the lab corpus for operational indexes")
    parser.add_argument("source_jsonl", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/generated"))
    args = parser.parse_args()
    manifest = prepare(args.source_jsonl, args.out)
    print(json.dumps(manifest["datasets"], ensure_ascii=False, indent=2))
