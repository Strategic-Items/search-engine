"""Compare current table chunks with one chunk per parsed table, without indexing.

The experiment disables only the table-splitting branch in an isolated copy of
chunk_elements. All other chunking, table metadata, and postprocessing stay intact.
"""

import argparse
import ast
import copy
import inspect
import json
import re
from html import unescape
from pathlib import Path
from statistics import median

from search_engine.chunking import pipeline, structured
from search_engine.chunking.bundle import iter_bundles
from search_engine.chunking.elements import markdown_to_elements
from search_engine.chunking.postprocess import chunk_title, index_text
from search_engine.chunking.tables import element_tables
from search_engine.config import get_settings
from search_engine.embeddings import embedding_text
from search_engine.indexing.law import law_embedding_body, law_embedding_title


def atomic_chunker():
    tree = ast.parse(inspect.getsource(structured.chunk_elements))
    branches = [node for node in ast.walk(tree) if isinstance(node, ast.If)
                and isinstance(node.test, ast.BoolOp)
                and isinstance(node.test.values[0], ast.Name)
                and node.test.values[0].id == "any_comparison"]
    assert len(branches) == 1, "Table split branch changed; review the experiment."
    branches[0].test = ast.Constant(value=False)
    ast.fix_missing_locations(tree)
    namespace = dict(structured.chunk_elements.__globals__)
    exec(compile(tree, "<atomic-table-experiment>", "exec"), namespace)
    return namespace["chunk_elements"]


def describe(values):
    return {"count": len(values), "median": median(values) if values else 0,
            "max": max(values, default=0),
            **{f"over_{limit}": sum(v > limit for v in values)
               for limit in (800, 2000, 8000, 32000)}}


def plain_table(text):
    """Keep row/cell boundaries while removing HTML; a diagnostic third arm."""
    text = re.sub(r"</t[dh]\s*>", "\t", text, flags=re.I)
    text = re.sub(r"</tr\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return "\n".join(line.strip() for line in unescape(text).splitlines() if line.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundles", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    from transformers import AutoTokenizer

    settings = get_settings()
    tokenizer = AutoTokenizer.from_pretrained(settings.search_splade_model,
                                             local_files_only=True)
    tokenizer.model_max_length = 10**9  # Count full input, without truncation warnings.
    atomic = atomic_chunker()
    namespace = dict(pipeline.chunk_bundle.__globals__)
    namespace["chunk_elements"] = atomic
    exec(compile(inspect.getsource(pipeline.chunk_bundle), "<atomic-bundle-experiment>", "exec"), namespace)
    atomic_bundle = namespace["chunk_bundle"]
    records, documents, examples = [], [], []
    lengths = {"current": [], "atomic": [], "atomic_without_html": []}
    tokens = {"current": [], "atomic": [], "atomic_without_html": []}

    for bundle in iter_bundles(args.bundles):
        current_full = pipeline.chunk_bundle(bundle)
        atomic_full = atomic_bundle(bundle)
        documents.append({"document_id": bundle.document_id, "title": bundle.title,
                          "current_chunks": len(current_full), "atomic_chunks": len(atomic_full)})
        parsed = markdown_to_elements(bundle.markdown)
        tables = element_tables(parsed.elements, hard_breaks=bundle.source_format != "pdf")
        table_index = 0
        for element in parsed.elements:
            if element["type"] != "table":
                continue
            objects = tables[table_index]
            table_index += 1
            if not element["text"].strip():
                continue
            arms = {}
            for name, chunker in (("current", structured.chunk_elements), ("atomic", atomic)):
                raw = chunker([copy.deepcopy(element)], document_id=bundle.document_id,
                              tables=[copy.deepcopy(objects)])
                arms[name] = [c for c in raw if index_text(c["text"])]
                for c in arms[name]:
                    c["text"] = index_text(c["text"])
                    lengths[name].append(len(c["text"]))
                    title = chunk_title(bundle.title, (c.get("heading_path") or [""])[-1])
                    source = {"title": title, "body": c["text"],
                              "heading_path": c.get("heading_path") or []}
                    text = embedding_text(law_embedding_title(source), law_embedding_body(source))
                    tokens[name].append(len(tokenizer.encode(text, truncation=False)))
            assert len(arms["atomic"]) == 1, (bundle.document_id, table_index)
            plain = plain_table(arms["atomic"][0]["text"])
            lengths["atomic_without_html"].append(len(plain))
            source["body"] = plain
            text = embedding_text(law_embedding_title(source), law_embedding_body(source))
            tokens["atomic_without_html"].append(len(tokenizer.encode(text, truncation=False)))
            record = {"document_id": bundle.document_id, "title": bundle.title,
                      "table_index": table_index - 1, "page": element.get("page"),
                      "current_chunks": len(arms["current"]),
                      "current_max_chars": max((len(c["text"]) for c in arms["current"]), default=0),
                      "atomic_chars": len(arms["atomic"][0]["text"]),
                      "atomic_sparse_tokens": tokens["atomic"][-1],
                      "atomic_plain_chars": len(plain),
                      "atomic_plain_sparse_tokens": tokens["atomic_without_html"][-1],
                      "columns": arms["atomic"][0].get("columns", []),
                      "row_count": arms["atomic"][0].get("row_count")}
            records.append(record)
            examples.append({**record, "atomic_text": arms["atomic"][0]["text"],
                             "current_first_text": arms["current"][0]["text"] if arms["current"] else ""})

    limit = settings.search_splade_doc_max_length
    assert sum(d["current_chunks"] - d["atomic_chunks"] for d in documents) == (
        len(lengths["current"]) - len(lengths["atomic"])
    ), "Postprocessing changed chunk counts beyond the isolated table differences."
    result = {"method": "Offline chunking and token counts; no retrieval scores or model inference.",
              "unit": "One parsed table element; this may span pages or contain multiple logical tables.",
              "token_input": "Isolated table, document title + available table heading; surrounding document headings excluded.",
              "bundles": len(documents), "nonempty_table_elements": len(records),
              "changed_table_elements": sum(r["current_chunks"] != 1 for r in records),
              "full_document_chunks": {"current": sum(d["current_chunks"] for d in documents),
                                       "atomic": sum(d["atomic_chunks"] for d in documents)},
              "table_chunk_chars": {name: describe(v) for name, v in lengths.items()},
              "sparse_tokenizer": settings.search_splade_model, "sparse_limit": limit,
              "table_input_tokens": {name: {**describe(v), "over_sparse_limit": sum(n > limit for n in v)}
                                     for name, v in tokens.items()},
              "tables": records, "documents": documents}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    selected = sorted(examples, key=lambda r: r["atomic_chars"], reverse=True)[:5]
    for fragment in ("할당관세", "세부평가", "비해당품목", "채용"):
        match = next((e for e in examples if fragment in e["title"]), None)
        if match and match not in selected:
            selected.append(match)
    (args.out / "examples.json").write_text(json.dumps(selected, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("tables", "documents")},
                     ensure_ascii=False, indent=2))
    print(json.dumps([{k: v for k, v in e.items() if not k.endswith("text")} for e in selected],
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
