"""Post-extract validation without altering source text or inferred facts."""
from __future__ import annotations

from importlib.resources import files
import json
import re

from jsonschema import Draft202012Validator

from .structured_html import LEVELS
from .hierarchy_validation import validate_hierarchy
from .legal_hierarchy import source_key
from .extract_quality import compact_text, digest, text_units


def schema_validator():
    schema = json.loads(files("vietnam_legal_rag.ingestion").joinpath("schemas/extracted.schema.json").read_text())
    return Draft202012Validator(schema)


def walk_content(nodes):
    for node in nodes:
        yield node
        yield from walk_content(node.get("children", []))
        for cell in node.get("cells", []):
            yield from walk_content(cell.get("content", []))


def semantic_roots(result):
    if result.get("document"):
        yield result["document"]
    for key in ("content", "context"):
        yield from result.get(key, [])
    for group in result.get("groups", []):
        yield from group.get("context", [])
        for item in group["items"]:
            yield from item.get("content", [])
    for key in ("fields", "context_fields"):
        for field in result.get(key, []):
            yield from field.get("value_content", [])
    for column in result.get("columns", []):
        yield from column.get("unparsed_content", [])


def semantic_count(result):
    count = sum(1 + len(node.get("cells", [])) for node in walk_content(list(semantic_roots(result))))
    return count + sum(len(result.get(key, [])) for key in ("fields", "events", "context_fields")) + sum(
        1 + len(group["items"]) for group in result.get("groups", [])) + sum("label" in c for c in result.get("columns", []))


def validate_result(result, document_id, quality):
    # An independent artifact recheck must retain extraction diagnostics when
    # deriving semantic_complete/status, just as the original parse did.
    existing = {i["issue_id"] for i in quality.issues}
    quality.issues.extend(i for i in result.get("issues", []) if i["issue_id"] not in existing)
    if result["document_id"] != document_id:
        quality.add("invalid_document_id", "Extracted identity differs from raw manifest")
    if not re.fullmatch(r"[0-9a-f]{64}", result["source_ref"].get("sha256", "")):
        quality.add("invalid_source_ref", "Source SHA-256 is missing/invalid", result["source_ref"])
    evidence = result.get("validation", {})
    if evidence.get("source_text_sha256"):
        actual_text = compact_text("".join(text for _, text in sorted(text_units(result), key=lambda item: item[0])))
        evidence["extracted_text_sha256"] = digest(actual_text)
        evidence["extracted_characters"] = len(actual_text)
        evidence["meaningful_text_preserved"] = evidence["source_text_sha256"] == evidence["extracted_text_sha256"]
        if not evidence["meaningful_text_preserved"]:
            quality.add("semantic_text_mismatch", "Actual serialized semantic text differs from source text checksum", result["source_ref"])
    seen = set()
    def units(nodes, ancestors=()):
        orders = [source_key(n) for n in nodes]
        if orders != sorted(orders):
            quality.add("invalid_order", "Semantic siblings differ from source order")
        for node in nodes:
            ref = node.get("source_ref") or next(iter(node.get("source_refs", [])), {})
            identity = (node["type"], *source_key(node), ref.get("tag"))
            if identity in seen:
                quality.add("duplicate_semantic_block", "Source unit is represented more than once", ref)
            seen.add(identity)
            kind = node["type"]
            if kind in {"clause", "point"} and "article" not in ancestors and node.get("parent_status") != "unresolved":
                quality.add("invalid_parent", "Legal child lacks an article parent and ambiguity flag", ref)
            legal_parents = [a for a in ancestors if a in LEVELS]
            if kind in LEVELS and legal_parents and LEVELS[kind] <= LEVELS[legal_parents[-1]]:
                quality.add("invalid_parent", "Legal hierarchy contains a same/higher-level child", ref)
            if kind == "table":
                validate_table(node, quality)
                for cell in node["cells"]:
                    # Legal fragments inside a cell form an independent local scope.
                    units(cell.get("content", []))
            units(node.get("children", []), ancestors + (kind,))
    # Main roots from separate metadata contexts are individually ordered.
    for key in ("content", "context"):
        units(result.get(key, []))
    if "document" in result:
        if result["document"]:
            units([result["document"]])
            from .form_validation import validate_forms
            result["form_validation"], result["structured_paragraph_audit"] = validate_forms(result["document"], quality)
        result["hierarchy_validation"] = validate_hierarchy(result["document"], quality,
            result["validation"].get("meaningful_text_preserved", False))
    for group in result.get("groups", []):
        units(group.get("context", []))
        for item in group["items"]:
            units(item.get("content", []))
        real = len(group["items"])
        if group["declared_count"] is not None and group["declared_count"] != real:
            quality.add("relation_count_mismatch", f"Source declares {group['declared_count']} related documents; HTML contains {real} real items", group["source_ref"])
        if any((i["text"] or "").strip() == "--" for i in group["items"]):
            quality.add("fake_relation_item", "Placeholder incorrectly appears as a real relation item", group["source_ref"], "error")
    for column in result.get("columns", []):
        units(column.get("unparsed_content", []))
    for key in ("fields", "events", "groups", "context_fields"):
        orders = [n["order"] for n in result.get(key, [])]
        if orders != sorted(orders):
            quality.add("invalid_order", f"{key} differs from source order")
        if key in {"fields", "context_fields"}:
            for field in result.get(key, []):
                units(field.get("value_content", []))
    errors = sorted(schema_validator().iter_errors(result), key=lambda e: str(list(e.path)))
    for error in errors:
        quality.add("invalid_schema", f"{'.'.join(map(str, error.path)) or '$'}: {error.message}")
    result["validation"]["schema_valid"] = not errors
    if result.get("hierarchy_validation"):
        result["hierarchy_validation"]["schema_valid"] = not errors
        if errors:
            result["hierarchy_validation"].update(semantic_complete=False, status="invalid")
    return not errors


def validate_table(table, quality):
    from .table_semantics import effective_cell_text, NO_AXES
    cells = table["cells"]
    if [c["order"] for c in cells] != sorted(c["order"] for c in cells):
        quality.add("invalid_order", "Table cells differ from source order", table["source_ref"])
    for i, cell in enumerate(cells):
        _, effective = effective_cell_text(cell)
        if effective != cell.get("effective_text"):
            quality.add("lost_cell_content", "Effective cell text does not represent its preserved textual content", cell["source_ref"], "error")
        if table["table_kind"] in NO_AXES and (cell.get("header_refs") or cell.get("row_axis") or cell.get("column_axis")):
            quality.add("invalid_table_association", "Form/key-value table has unsupported inferred data axes", cell["source_ref"], "error")
        for previous in cells[:i]:
            if (cell["row"] < previous["row"] + previous["rowspan"] and previous["row"] < cell["row"] + cell["rowspan"]
                    and cell["column"] < previous["column"] + previous["colspan"]
                    and previous["column"] < cell["column"] + cell["colspan"]):
                # Geometry parser already reports this with the original source ref.
                if not any(issue["code"] == "table_grid_overlap" and issue.get("source_ref") == cell["source_ref"] for issue in quality.issues):
                    quality.add("table_grid_overlap", "Cell rectangles overlap; both source cells retained", cell["source_ref"])
    by_id = {c["cell_id"]: c for c in cells}
    for cell in cells:
        for axis, refs in cell.get("header_refs", {}).items():
            for identifier in refs:
                header = by_id.get(identifier)
                if not header or header["cell_type"] != "header":
                    quality.add("invalid_table_association", "Header reference does not identify a unique source header cell", cell["source_ref"], "error")
                elif axis == "row" and header.get("role") not in {"row_header", "row_group_header"}:
                    quality.add("invalid_table_association", "Row axis points to a header without a supported row role", cell["source_ref"], "error")
                elif axis == "column" and header.get("role") not in {"column_header", "column_group_header"}:
                    quality.add("invalid_table_association", "Column axis points to a header without a supported column role", cell["source_ref"], "error")
