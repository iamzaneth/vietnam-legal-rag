"""Deterministic extraction diagnostics and text conservation evidence."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import re

from vietnam_legal_rag.ingestion.html.source import NON_CONTENT, Node, whitespace

SEVERITIES = ("info", "warning", "error", "fatal")
CODE_MAP = {"overlapping_cells": "table_grid_overlap", "ragged_table": "table_grid_gap",
            "ambiguous_compound_header": "ambiguous_table_header"}
INFO = {"layout_table_detected", "implied_end_tag", "legacy_property_markup"}
ERROR = {"table_grid_overlap", "source_checksum_mismatch", "semantic_text_mismatch",
         "duplicate_semantic_block", "invalid_schema", "invalid_parent", "invalid_order",
         "invalid_document_id", "invalid_source_ref", "invalid_output_checksum"}
ERROR |= {"invalid_hierarchy", "invalid_provenance", "layout_table_in_hierarchy", "invalid_table_parent"}
FATAL = {"source_content_missing", "source_missing", "html_parse_failure", "semantic_text_mismatch"}


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class Quality:
    def __init__(self):
        self.issues = []
        self.ignored = []
        self.units = []  # Transient ledger: never serialized as a second representation.

    def add(self, code, message, source_ref=None, severity=None, details=None):
        code = CODE_MAP.get(code, code)
        severity = severity or ("fatal" if code in FATAL else "error" if code in ERROR
                                else "info" if code in INFO else "warning")
        issue = {"severity": severity, "code": code, "message": message}
        if source_ref is not None:
            issue["source_ref"] = source_ref
        if details is not None:
            issue["details"] = details
        issue["issue_id"] = "issue_" + digest(json.dumps(issue, ensure_ascii=False, sort_keys=True))[:16]
        if not any(item["issue_id"] == issue["issue_id"] for item in self.issues):
            self.issues.append(issue)
        return issue["issue_id"]

    def record(self, order, text):
        if whitespace(text):
            self.units.append((order, text))

    def ignore(self, node, reason):
        text = node.text(blocks=True)
        item = {"reason": reason, "order": node.dom_order, "source_ref": node.ref}
        if text:
            item["text"] = text
        self.ignored.append(item)
        return item

    def conservation(self, root, result=None):
        # Ignore only audited UI/spacing nodes, not unknown legal text.
        ignored_orders = {i["order"] for i in self.ignored}
        parts = []
        def visit(node):
            if node.tag in NON_CONTENT or node.dom_order in ignored_orders:
                return
            for index, child in enumerate(node.children):
                if isinstance(child, Node):
                    visit(child)
                elif node.text_refs.get(index, node.ref)["dom_order"] not in ignored_orders:
                    parts.append(child)
        visit(root)
        source = compact_text("".join(parts))
        units = list(text_units(result)) if result is not None else self.units
        output = compact_text("".join(text for _, text in sorted(units, key=lambda x: x[0])))
        okay = source == output
        if not okay:
            self.add("semantic_text_mismatch", "Ordered semantic text differs from meaningful source text; source and parsed data retained", root.ref)
        return {"meaningful_text_preserved": okay, "source_characters": len(source),
                "extracted_characters": len(output), "source_text_sha256": digest(source),
                "extracted_text_sha256": digest(output), "ignored_elements": len(self.ignored)}


def title_owned_by_child(node):
    """A catalog title may reference its displayed child without duplicating it."""
    ref = node.get("title_source_ref")
    return bool(ref and any(child.get("source_ref") == ref and child.get("text") == node.get("title")
                            for child in node.get("children", [])))


def text_units(result):
    """Project the actual serialized records, not the parser's claim ledger."""
    def tree(nodes):
        for node in nodes:
            position = (node["order"], node.get("source_offset", 0))
            title_spans = node.get("title_source_spans")
            if node.get("label"):
                label = node["label"] + node.get("label_suffix", "")
                if not node.get("title_source_ref") and not title_spans:
                    label += node.get("title") or ""
                yield position, label
            elif node.get("title") and not node.get("title_source_ref") and not title_spans:
                yield position, node["title"]
            if title_spans:
                for span in title_spans:
                    yield (span["source_ref"]["dom_order"], span.get("source_offset", 0)), node["title"][span["start"]:span["end"]]
            elif node.get("title_source_ref") and not title_owned_by_child(node):
                yield (node["title_source_ref"]["dom_order"], node.get("title_source_offset", 0)), node["title"]
            if node.get("text"):
                yield position, node["text"]
            yield from tree(node.get("children", []))
            for cell in node.get("cells", []):
                if cell["text"] and not cell.get("content"):
                    yield (cell["order"], 0), cell["text"]
                yield from tree(cell.get("content", []))
    for key in ("content", "context"):
        yield from tree(result.get(key, []))
    if result.get("document"):
        yield from tree([result["document"]])
    for key in ("fields", "context_fields"):
        for field in result.get(key, []):
            yield (field["order"], 0), (field["label"] or "") + (field["value"] or "")
            yield from tree(field.get("value_content", []))
    for group in result.get("groups", []):
        yield (group["order"], 0), group["label_raw"]
        for item in group["items"]:
            yield (item["order"], 0), item["text"] or ""
            yield from tree(item.get("content", []))
        yield from tree(group.get("context", []))
    for item in result.get("items", []):
        yield (item["order"], 0), item["text"] or ""
    for column in result.get("columns", []):
        if "label" in column:
            yield (column["order"], 0), column["label"]
    for event in result.get("events", []):
        for cell in event.get("source_cells", []):
            field = cell["field"]
            if field.startswith("other_values:"):
                text = event["other_values"][int(field.split(':')[1])]["value"]
            elif field == "source_document":
                text = (event[field] or {}).get("text", "")
            else:
                text = event[field] or ""
            yield (cell["source_ref"]["dom_order"], 0), text


def issue_summary(issues):
    counts = Counter(i["severity"] for i in issues)
    return {severity: counts[severity] for severity in SEVERITIES}


def status(summary):
    if summary["error"] or summary["fatal"]:
        return "failed"
    return "success_with_warnings" if summary["warning"] else "success"
