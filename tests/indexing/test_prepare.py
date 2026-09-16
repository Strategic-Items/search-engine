import json
from pathlib import Path

from search_engine.indexing.indexer import file_sha256
from search_engine.indexing.prepare import prepare


def test_prepare_separates_core_and_hsk_and_checks_manifest(tmp_path: Path):
    source = tmp_path / "corpus_project_v1.jsonl"
    rows = [
        {"id": "faq-1", "title": "허가", "body": "본문", "code": "5D002"},
        {"id": "faq-042", "title": "자가판정", "body": "오래된 안내"},
        {"id": "notice-1", "title": "고시", "body": "본문", "source_type": "공지사항",
         "published_at": "2026-09-01", "effective_from": "2026-09-01"},
        {"id": "form-1", "title": "서식", "body": "본문", "source_type": "민원서식",
         "source_id": "form-23311", "source_url": "https://www.yestrade.go.kr/user/boards/70/posts"},
        {"id": "hsk-1", "title": "HSK", "body": "연계", "source_type": "HSK 연계표",
         "hsk_code": "0123456789", "control_number": "1A001.",
         "source_url": "https://example.invalid/hsk"},
        {"id": "law-1", "title": "법령", "body": "본문", "source_type": "intl_law"},
    ]
    source.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    source.with_suffix(".manifest.json").write_text(
        json.dumps({"corpus_sha256": file_sha256(source)}))

    manifest = prepare(source, tmp_path / "out")
    assert manifest["datasets"]["core"]["count"] == 3
    assert manifest["datasets"]["hsk"]["count"] == 1
    assert manifest["excluded"] == {"conflicts_with_current_self_judgement_guide": 1}
    core = [json.loads(line) for line in (tmp_path / "out/core.jsonl").read_text().splitlines()]
    assert core[0]["source_type"] == "FAQ"
    assert core[0]["date_basis"] == "undated"
    assert core[1]["date_basis"] == "effective"
    assert core[2]["source_url"].endswith("/70/posts/23311")
    hsk = json.loads((tmp_path / "out/hsk.jsonl").read_text())
    assert hsk["hsk_code"] == "0123456789"
    assert manifest["datasets"]["core"]["sha256"] == file_sha256(tmp_path / "out/core.jsonl")
