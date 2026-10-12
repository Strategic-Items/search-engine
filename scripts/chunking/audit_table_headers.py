"""Audit generic column names and independently check source-cell preservation.

Search is deliberately separate: this reads TextBundles and corpora only.
The baseline parser is loaded from a Git revision so the comparison is reproducible.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import subprocess
import sys
import types
from collections import Counter
from pathlib import Path

from search_engine.chunking import table_rows, tables
from search_engine.chunking.bundle import iter_bundles
from search_engine.chunking.elements import markdown_to_elements


def generic(columns):
    return any(re.fullmatch(r"열\d+", name) for name in columns)


def load(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def corpus_summary(rows):
    unresolved = [row for row in rows if generic(row.get("columns", []))]
    return {
        "documents": len({row["parent_id"] for row in rows}), "chunks": len(rows),
        "generic_name_chunks": len(unresolved),
        "generic_name_tables": len({row["table_id"] for row in unresolved}),
        "generic_chunks_by_document": dict(Counter(row["parent_id"] for row in unresolved)),
    }


def baseline_module(name, path, ref):
    source = subprocess.check_output(["git", "show", f"{ref}:{path}"], text=True)
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(compile(source, path, "exec"), module.__dict__)
    return module


def inspect_bundles(category, ref):
    old_rows = baseline_module("_audit_baseline_rows", "search_engine/chunking/table_rows.py", ref)
    old_tables = baseline_module("_audit_baseline_tables", "search_engine/chunking/tables.py", ref)
    result = {"baseline_ref": ref, "documents": 0, "logical_tables": 0,
              "before_generic_tables": 0, "after_generic_tables": 0,
              "missing_source_cells": [], "changed_tables": []}
    for bundle in iter_bundles(category / "bundles"):
        result["documents"] += 1
        elements = markdown_to_elements(bundle.markdown).elements
        hard = bundle.source_format != "pdf"
        # element_tables imports logical_tables locally; substitute only during the baseline call.
        sys.modules[table_rows.__name__] = old_rows
        try:
            before_objects = old_tables.element_tables(elements, hard_breaks=hard)
        finally:
            sys.modules[table_rows.__name__] = table_rows
        after_objects = tables.element_tables(elements, hard_breaks=hard)
        for table_index, (before_parts, after_parts) in enumerate(zip(before_objects, after_objects)):
            for part_index, (before_part, after_part) in enumerate(zip(before_parts, after_parts)):
                before = old_rows.logical_tables(before_part)
                after = table_rows.logical_tables(after_part)
                result["logical_tables"] += len(after)
                result["before_generic_tables"] += sum(generic(lt.columns) for lt in before)
                result["after_generic_tables"] += sum(generic(lt.columns) for lt in after)
                retained = "".join("".join(lt.columns) + lt.caption + "".join("".join(row) for row in lt.rows)
                                   for lt in after)
                retained = re.sub(r"\s+", "", retained)
                missing = sorted({cell for row in after_part["rows"] for cell in row
                                  if cell.strip() and re.sub(r"\s+", "", cell) not in retained})
                if missing:
                    result["missing_source_cells"].append({"document": bundle.document_id,
                                                          "table": table_index, "part": part_index,
                                                          "cells": missing})
                if [lt.columns for lt in before] != [lt.columns for lt in after]:
                    result["changed_tables"].append({"document": bundle.document_id,
                                                    "table": table_index, "part": part_index,
                                                    "before": [lt.columns for lt in before],
                                                    "after": [lt.columns for lt in after]})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--review-category", type=Path)
    parser.add_argument("--baseline-ref", default="9e61bac")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    before, after = load(args.before), load(args.after)
    unresolved = [{key: row.get(key) for key in ("id", "parent_id", "table_id", "columns", "heading_path", "body")}
                  for row in after if generic(row.get("columns", []))]
    result = {"before": corpus_summary(before), "after": corpus_summary(after),
              "unresolved_chunks": unresolved}
    if args.review_category:
        result["structure_review"] = inspect_bundles(args.review_category, args.baseline_ref)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {arm: {k: v for k, v in result[arm].items() if k != "generic_chunks_by_document"} for arm in ("before", "after")}
    if "structure_review" in result:
        review = result["structure_review"]
        summary["structure_review"] = {k: v for k, v in review.items() if k not in ("changed_tables", "missing_source_cells")}
        summary["structure_review"].update(changed_tables=len(review["changed_tables"]), missing_source_cells=len(review["missing_source_cells"]))
    print(json.dumps(summary, ensure_ascii=False))
    if args.review_category and result["structure_review"]["missing_source_cells"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
