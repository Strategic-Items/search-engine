import json
from pathlib import Path

from search_engine.indexing.indexer import file_sha256
from search_engine.indexing.prepare import download_copies, period_hint, prepare


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
    assert manifest["datasets"]["core"]["count"] == 4
    assert manifest["datasets"]["hsk"]["count"] == 1
    assert manifest["excluded"] == {"conflicts_with_current_self_judgement_guide": 1}
    core = [json.loads(line) for line in (tmp_path / "out/core.jsonl").read_text().splitlines()]
    assert core[0]["source_type"] == "FAQ"
    assert core[0]["date_basis"] == "undated"
    assert core[1]["date_basis"] == "effective"
    assert core[2]["source_url"].endswith("/70/posts/23311")
    assert core[3]["id"] == "law-1"
    assert core[3]["source_type"] == "intl_law"
    assert core[3]["date_basis"] == "undated"
    hsk = json.loads((tmp_path / "out/hsk.jsonl").read_text())
    assert hsk["hsk_code"] == "0123456789"
    assert manifest["datasets"]["core"]["sha256"] == file_sha256(tmp_path / "out/core.jsonl")


def _corpus(tmp_path: Path, rows: list[dict]) -> Path:
    source = tmp_path / "corpus_project_v1.jsonl"
    source.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    source.with_suffix(".manifest.json").write_text(
        json.dumps({"corpus_sha256": file_sha256(source)}))
    return source


def test_download_copies_keep_the_original_and_drop_the_rest():
    """`... (1).hwp`는 파일명이 스스로 사본이라고 말한다. 추측할 것이 없다."""
    rows = [
        {"parent_id": "a", "source_path": "안내문.hwp"},
        {"parent_id": "b", "source_path": "안내문 (1).hwp"},
        {"parent_id": "c", "source_path": "안내문 (2).hwp"},
        {"parent_id": "d", "source_path": "다른 문서.hwp"},
    ]
    assert download_copies(rows) == {"b", "c"}


def test_a_group_without_the_original_keeps_its_lowest_copy():
    """원본이 코퍼스에 없을 수 있다. 그래도 하나는 남아야 한다."""
    rows = [
        {"parent_id": "b", "source_path": "안내문 (2).hwp"},
        {"parent_id": "a", "source_path": "안내문 (1).hwp"},
    ]
    assert download_copies(rows) == {"b"}


def test_documents_without_a_source_path_are_never_grouped():
    """경로가 없으면 사본인지 알 수 없다. 지우지 않는다."""
    rows = [{"parent_id": "a", "source_path": ""}, {"parent_id": "b", "source_path": ""}]
    assert download_copies(rows) == set()


def test_prepare_drops_download_copies_and_counts_them(tmp_path: Path):
    source = _corpus(tmp_path, [
        {"id": "n-1", "parent_id": "p1", "title": "안내", "body": "본문",
         "source_type": "공지사항", "source_path": "안내문.hwp"},
        {"id": "n-2", "parent_id": "p2", "title": "안내", "body": "본문",
         "source_type": "공지사항", "source_path": "안내문 (1).hwp"},
        {"id": "hsk-1", "title": "HSK", "body": "연계", "source_type": "HSK 연계표",
         "hsk_code": "0123456789", "source_url": "https://example.invalid/hsk"},
    ])
    manifest = prepare(source, tmp_path / "out")
    core = [json.loads(line) for line in (tmp_path / "out/core.jsonl").read_text().splitlines()]
    assert [row["id"] for row in core] == ["n-1"]
    assert manifest["excluded"]["download_copy"] == 1


def test_period_hint_reads_the_head_in_either_date_style():
    assert period_hint("산업통상부 공고 2016. 3. 8.") == "2016-03-08"
    assert period_hint("2005년 1월 17일 시행") == "2005-01-17"
    assert period_hint("날짜가 없는 본문") is None
    assert period_hint("2016. 2. 30. 잘못된 날짜") is None


def test_period_hint_ignores_dates_past_the_head():
    """뒤로 갈수록 개정 이력과 시행일이 섞여 발행일을 가릴 수 없다."""
    assert period_hint("발신일 없음 " + "가" * 700 + " 2013. 4. 12.") is None


def test_prepare_fills_the_period_hint_only_where_the_date_is_unknown(tmp_path: Path):
    """아는 발행일이 있으면 추정으로 덮지 않는다."""
    source = _corpus(tmp_path, [
        {"id": "n-1", "parent_id": "p1", "title": "공고", "body": "산업통상부 공고 2016. 3. 8.",
         "source_type": "공지사항", "chunk_index": 0},
        {"id": "n-2", "parent_id": "p2", "title": "공고", "body": "산업통상부 공고 2016. 3. 8.",
         "source_type": "공지사항", "chunk_index": 0, "published_at": "2020-01-01"},
        {"id": "hsk-1", "title": "HSK", "body": "연계", "source_type": "HSK 연계표",
         "hsk_code": "0123456789", "source_url": "https://example.invalid/hsk"},
    ])
    manifest = prepare(source, tmp_path / "out")
    core = {row["id"]: row for row in
            (json.loads(line) for line in (tmp_path / "out/core.jsonl").read_text().splitlines())}
    assert core["n-1"]["period_hint"] == "2016-03-08"
    assert "period_hint" not in core["n-2"]
    assert manifest["datasets"]["core"]["period_hint"] == 1
