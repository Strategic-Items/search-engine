import json

import pytest

from search_engine.chunking.bundle import DOMAIN_KEY, iter_bundles, read_bundle


def make(root, name, document_id="doc-1", markdown="# 제목\n\n본문\n"):
    folder = root / "bundles" / f"{name}.textbundle"
    folder.mkdir(parents=True)
    info = {"version": 2, DOMAIN_KEY: {"document_id": document_id, "title": "제목", "source_path": "a/b.hwp",
                                       "source_format": "hwp5", "document": {"category": "행정·업무"}}}
    (folder / "info.json").write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    (folder / "text.markdown").write_text(markdown, encoding="utf-8")
    return folder


def test_read_bundle_exposes_document_metadata(tmp_path):
    bundle = read_bundle(make(tmp_path, "a"))
    assert (bundle.document_id, bundle.title, bundle.source_format) == ("doc-1", "제목", "hwp5")
    assert bundle.document["category"] == "행정·업무"
    assert bundle.markdown.startswith("# 제목")
    assert bundle.asset("assets/x.png") == bundle.path / "assets/x.png"


def test_missing_document_id_fails_loudly(tmp_path):
    folder = make(tmp_path, "a")
    (folder / "info.json").write_text(json.dumps({"version": 2}), encoding="utf-8")
    with pytest.raises(ValueError):
        read_bundle(folder)


def test_iter_bundles_is_sorted_and_recursive(tmp_path):
    make(tmp_path, "b", "doc-b")
    make(tmp_path, "a", "doc-a")
    assert [b.document_id for b in iter_bundles(tmp_path)] == ["doc-a", "doc-b"]
