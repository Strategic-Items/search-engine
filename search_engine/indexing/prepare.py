"""검토된 실험실 스냅샷을 별도의 핵심 및 HSK 인덱스를 위해 준비한다."""

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from search_engine.indexing.documents import SearchDocument
from search_engine.indexing.indexer import file_sha256

FORM_TYPE = "민원서식"
# 「전략물자수출입고시」의 서식은 별지·별표 번호로 자리를 잡는다. 같은 자리의
# 새 판이 올라오면 옛 판은 대체된다. 제목 형식은 두 가지가 섞여 있다:
# "[38차 개정, 26.9.1] 별지 4." 와 "[별지 제4호 서식]".
FORM_SLOT = re.compile(r"(별지|별표)\s*(?:제\s*)?(\d+)\s*(?:호)?\s*(?:의\s*(\d+))?")
# 다른 법령의 서식은 번호 체계가 달라 같은 자리로 볼 수 없다.
OTHER_STATUTE = re.compile(r"[가-힣]{2,}법(?:\s*시행(?:령|규칙))?\s*별지")
NOTICE_TYPE = "공지사항"
# 고시는 차수로 이어지는 한 줄기다. 제38차가 제37차를 대체한다.
GOSI_REVISION = re.compile(r"제\s*\d+\s*차\s*[^\n]*?고시\s*개정")
# 행정예고는 시행 전 초안이다. 게시일이 현행 고시보다 나중일 수 있으므로
# 날짜 순서로는 현행을 가릴 수 있다. 초안은 언제 올라오든 현행이 아니다.
GOSI_DRAFT = re.compile(r"고시[^\n]*?(?:행정예고|입법예고)|(?:행정예고|입법예고)[^\n]*?고시")
HSK_TYPE = "HSK 연계표"
# 브라우저가 같은 파일을 두 번 내려받으면 `... (1).hwp`가 옆에 남고, 파서는 그것을
# 별개 문서로 색인한다. 본문이 글자까지 같으므로 검색은 같은 답을 두 번 싣고 창을
# 그만큼 좁힌다. 파일명이 스스로 사본이라고 말하고 있으니 추측할 것이 없다 --
# 제목+발행일 같은 추정 열쇠와 달리 서로 다른 문서를 잘못 묶을 여지가 없다.
DOWNLOAD_COPY = re.compile(r"^(?P<stem>.*?)\s*\((?P<copy>\d+)\)(?P<ext>\.[A-Za-z0-9]+)$")

# 실험실 검토 결과, 이 날짜가 표시되지 않은 FAQ는 현재 자기 평가 가이드와 충돌한다.
EXCLUDED_CORE_IDS = {"faq-042": "conflicts_with_current_self_judgement_guide"}


def form_slot(title: str) -> tuple[str, str] | None:
    """서식이 차지하는 별지/별표 위치를 반환하고, 해당하지 않으면 None을 반환한다."""
    if OTHER_STATUTE.search(title):
        return None
    match = FORM_SLOT.search(title)
    if not match:
        return None
    suffix = f"의{match.group(3)}" if match.group(3) else ""
    return match.group(1), match.group(2) + suffix


def document_slot(source_type: str, title: str) -> tuple[str, str] | None:
    """문서가 숫자로 구성된 시리즈에서 차지하는 위치, 만약 그 위치를 차지한다면.

    한 양식은 별지/별표 자리에 위치한다. 고시 개정 공고는 그 판의 전체 텍스트를 담고, 다음 판은 그것을 대체한다. 두 시리즈 모두 순서대로 출판되므로, 자리에 있는 최신 출판일이 적용 중인 것이다.
    """
    if source_type == FORM_TYPE:
        return form_slot(title)
    if source_type == NOTICE_TYPE and GOSI_REVISION.search(title):
        return "고시", "전략물자수출입고시"
    return None


def is_gosi_draft(source_type: str, title: str) -> bool:
    """의견 수렴 중인 고시 초안인지 판별한다. 초안은 현행 본문이 아니다."""
    return source_type == NOTICE_TYPE and bool(GOSI_DRAFT.search(title))


def supersessions(rows: list[dict]) -> dict[str, str]:
    """각 대체된 문서를 같은 슬롯에 있는 가장 최신 문서로 매핑한다.

대체된 문서는 유지되고 인덱싱된다. 게시된 레코드는 공개적이며,
사람들은 연도를 기준으로 이전 판을 요청한다; 검색은 이를 숨기기보다는
낮추어 표시한다.
"""
    slots = {}
    for row in rows:
        slot = document_slot(row.get("source_type", FORM_TYPE), row["title"])
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

    # 초안은 언제든지 실제로 시행 중인 것으로 대체된다.
    # 게시됨: 현재 판 이후 다음 판의 초안이 도착한다.
    enacted = slots.get(("고시", "전략물자수출입고시"))
    if enacted:
        in_force = enacted[-1][1]
        for row in rows:
            if is_gosi_draft(row.get("source_type", ""), row["title"]):
                superseded.setdefault(row["parent_id"], in_force)
    return superseded


# 본문 앞머리의 날짜. `2016. 3. 8.`과 `2016년 3월 8일` 둘 다 받는다.
HEAD_DATE = re.compile(r"(20\d{2})\s*[.년]\s*(\d{1,2})\s*[.월]\s*(\d{1,2})")
# 앞머리로 볼 범위. 공고문의 발신일은 서두에 있고, 뒤로 갈수록 개정 이력과
# 시행일이 섞여 어느 것이 발행일인지 본문만으로는 가릴 수 없다.
HEAD_CHARS = 600


def period_hint(head: str) -> str | None:
    """문서 앞머리가 말하는 시점. 발행일이 아니라 시점 힌트다.

    파서는 파일명에서만 날짜를 읽으므로 docs-v2 52문서 중 43문서에
    `published_at`이 없다. 그 43문서 중 33문서는 본문에 날짜를 들고 있다.

    이것을 `published_at`에 넣으면 안 된다. 발행일을 아는 9문서로 맞춰
    보면 날짜까지 정확한 것은 6문서뿐이고 -- 한 문서는 앞머리에 제정일
    2013-04-12이 있어 실제 발행일 2025-09-23 대신 그것이 잡힌다 -- 대체
    판정과 사본 병합이 그 필드를 먹으므로 지금보다 나빠진다.

    연·월 눈금에서는 9문서 중 8문서가 맞는다. `_requested_period`가 그
    눈금으로만 묻기 때문에 그 부스트 전용으로 둔다. 틀린 한 문서는 부스트
    하나를 잘못 받을 뿐 필터처럼 문서를 지우지 않는다.
    """
    match = HEAD_DATE.search(head[:HEAD_CHARS])
    if not match:
        return None
    year, month, day = (int(group) for group in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def download_copy_key(source_path: str) -> tuple[str, int] | None:
    """내려받기 사본을 원본과 한데 묶는 열쇠와, 몇 번째 사본인지.

    `(1)`이 붙지 않은 원본은 0번으로 돌아오므로 정렬하면 언제나 원본이 먼저다.
    경로가 없으면 묶을 수 없고 None을 돌려준다 -- 그 문서는 그대로 남는다.
    """
    name = (source_path or "").rsplit("/", 1)[-1]
    if not name:
        return None
    match = DOWNLOAD_COPY.match(name)
    if not match:
        return name, 0
    return match.group("stem") + match.group("ext"), int(match.group("copy"))


def download_copies(rows: list[dict]) -> set[str]:
    """지워야 할 사본의 parent_id. 각 묶음에서 원본 하나만 남긴다.

    같은 열쇠에 사본만 있고 원본이 없을 수도 있으므로 번호가 가장 낮은 것을
    남긴다. 번호까지 같으면 parent_id로 갈라 실행마다 같은 것이 남게 한다.
    """
    groups: dict[str, list[tuple[int, str]]] = {}
    for row in rows:
        key = download_copy_key(row.get("source_path") or "")
        if key is None:
            continue
        groups.setdefault(key[0], []).append((key[1], row["parent_id"]))
    dropped = set()
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort()
        dropped.update(parent_id for _, parent_id in members[1:])
    return dropped


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
    if source_type != HSK_TYPE:
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


def _parents(source_path: Path) -> list[dict]:
    """부모마다 한 행씩, 쓰기 전에 미리 읽는다.

    대체 관계도 사본도 부모 단위의 사실이라 한 행씩은 전부 봐야 정해진다.
    첫 청크를 들고 다니는 것은 본문 앞머리에서 시점을 읽기 위해서다.
    """
    seen = {}
    with source_path.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("id") in EXCLUDED_CORE_IDS:
                continue
            if row.get("source_type") == HSK_TYPE:
                continue
            parent_id = row.get("parent_id") or row.get("id")
            parent = seen.setdefault(parent_id, {"parent_id": parent_id,
                                                 "source_type": row.get("source_type") or "",
                                                 "title": row.get("title") or "",
                                                 "published_at": row.get("published_at"),
                                                 "source_path": row.get("source_path") or "",
                                                 "head": ""})
            # 앞머리는 첫 청크의 것이어야 한다. 행이 순서대로 온다는 보장이 없다.
            if not row.get("chunk_index"):
                parent["head"] = row.get("body") or ""
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

    parents_ahead = _parents(source_path)
    superseded = supersessions(parents_ahead)
    dropped_copies = download_copies(parents_ahead)
    # 발행일을 아는 문서는 그것이 낫다. 힌트는 빈자리만 채운다.
    period_hints = {parent["parent_id"]: period_hint(parent["head"])
                    for parent in parents_ahead if not parent["published_at"]}

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
                    if row.get("id") in EXCLUDED_CORE_IDS:
                        excluded[EXCLUDED_CORE_IDS[row["id"]]] += 1
                        continue
                    dataset = "hsk" if source_type == HSK_TYPE else "core"
                    prepared = _prepare_row(row, source_type)
                except Exception as exc:
                    raise ValueError(f"invalid source line {line_no}: {exc}") from exc
                doc_id = prepared["id"]
                parent_id = prepared.get("parent_id") or doc_id
                if parent_id in dropped_copies:
                    excluded["download_copy"] += 1
                    continue
                hint = period_hints.get(parent_id)
                if hint:
                    prepared["period_hint"] = hint
                if doc_id in ids[dataset]:
                    raise ValueError(f"duplicate {dataset} document ID: {doc_id}")
                ids[dataset].add(doc_id)
                parents[dataset].add(parent_id)
                counts[dataset][source_type] += 1
                counts[dataset]["missing_source_url"] += not bool(prepared.get("source_url"))
                counts[dataset]["missing_published_at"] += not bool(prepared.get("published_at"))
                counts[dataset]["period_hint"] += bool(prepared.get("period_hint"))
                counts[dataset]["missing_effective_from"] += not bool(prepared.get("effective_from"))
                if prepared.get("published_at"):
                    ranges[dataset].append(prepared["published_at"])
                replacement = superseded.get(parent_id)
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
                "period_hint": counts[dataset]["period_hint"],
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
