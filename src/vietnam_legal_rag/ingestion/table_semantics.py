"""Effective cell text and conservative, context-sensitive table classification."""
from __future__ import annotations

import re
import unicodedata

from .html_source import whitespace
from .extract_quality import title_owned_by_child

TABLE_KINDS = ("layout", "data", "form", "matrix", "key_value", "annex_form", "ambiguous")
NO_AXES = {"layout", "form", "annex_form", "key_value"}
PLACEHOLDER = re.compile(r"\.{3,}|…{2,}|_{3,}|\[\s*(?:tên|ghi|điền)[^]]*\]", re.I)
FORM_HEADING = re.compile(r"^(?:Mẫu\s+số\s*\d+|Biểu\s+(?:số\s*)?\d+|(?:Phiếu|Đơn|Báo cáo|Biên bản)\b)", re.I)


def ordered_text_segments(nodes):
    parts = []

    def visit(node):
        position = node["order"], node.get("source_offset", 0)
        if node.get("label"):
            parts.append((position, node["label"] + node.get("label_suffix", "")))
        if node.get("title") and not title_owned_by_child(node):
            parts.append(((node.get("title_source_ref", {}).get("dom_order", node["order"]),
                           node.get("title_source_offset", node.get("source_offset", 0))), node["title"]))
        if node.get("text"):
            for i, line in enumerate(node["text"].splitlines()):
                if whitespace(line):
                    parts.append(((position[0], position[1] + i), line))
        for child in node.get("children", []):
            visit(child)
        for cell in node.get("cells", []):
            if cell.get("text") and not cell.get("content"):
                parts.append(((cell["order"], 0), cell["text"]))
            for child in cell.get("content", []):
                visit(child)

    for node in nodes:
        visit(node)
    return [whitespace(text) for _, text in sorted(parts, key=lambda item: item[0])]


def effective_cell_text(cell):
    """A derived search/inference view; conservation projects original records only."""
    segments = ([whitespace(line) for line in cell["text"].splitlines() if whitespace(line)]
                if whitespace(cell.get("text", "")) else ordered_text_segments(cell.get("content", [])))
    return segments, whitespace(" ".join(segments))


def compound_labels(segments, effective):
    """Join broken lines by a repeated lexical opener, not by guessing axes.

    E.g. seven fragments with two repeated two-word openers become two labels.
    Arbitrary fragments without this evidence remain candidate segments.
    """
    words = effective.split()
    for size in range(min(4, len(words) // 2), 1, -1):
        prefix = " ".join(words[:size])
        matches = list(re.finditer(r"(?<!\w)" + re.escape(prefix) + r"(?!\w)", effective, re.I))
        if len(matches) >= 2 and matches[0].start() == 0:
            starts = [m.start() for m in matches] + [len(effective)]
            return [effective[a:b].strip() for a, b in zip(starts, starts[1:])]
    return segments if len(segments) == 2 else [effective] if effective else []


def classify_table(source, rows, cells):
    """Called only AFTER geometry, cell content, segments and effective_text."""
    text = unicodedata.normalize("NFC", " ".join(c["effective_text"] for c in cells))
    headers = any(c["cell_type"] == "header" for c in cells)
    if source.attrs.get("role") == "presentation":
        return "layout", "explicit_presentation_role"
    heading = re.search(r"CỘNG\s+H[ÒO][ÀA].*VIỆT\s+NAM|Độc lập\s*[-–—]\s*Tự do", text, re.I)
    authority = re.search(r"Số\s*:|\bBỘ\b|[ỦU][YỶ] BAN|CHÍNH PHỦ|QUỐC HỘI", text, re.I)
    closing = re.search(r"Nơi nhận\s*:", text, re.I) and re.search(r"KT\.|TM\.|TL\.|THỨ TRƯỞNG|BỘ TRƯỞNG|CHỦ TỊCH|Đã ký", text, re.I)
    meaningful_rows = [r for r in rows if any(c["effective_text"] for c in r["cells"])]
    letterhead_only = heading and all(not c["effective_text"] or re.fullmatch(
        r"CỘNG\s+H[ÒO][ÀA].*VIỆT\s+NAM|Độc lập\s*[-–—]\s*Tự do\s*[-–—]\s*Hạnh phúc",
        c["effective_text"], re.I) for c in cells)
    if len(meaningful_rows) <= 2 and len(cells) <= 12 and not headers and (heading and authority or closing or letterhead_only):
        return "layout", "paired_document_heading_or_closing"
    if len(rows) <= 3 and len(cells) <= 6 and not headers and len(text) <= 300:
        signature = re.search(r"\bĐã ký\b|\[\s*daky\s*\]", text, re.I) or (re.search(r"\b(?:TM|KT|TL|TUQ)[./]\s*", text) and
                    re.search(r"\b(?:CHỦ TỊCH|BỘ TRƯỞNG|GIÁM ĐỐC)\b", text))
        if signature and not any(
                re.fullmatch(r"[\d.,%]+", c["effective_text"]) for c in cells):
            return "layout", "source_signature_block"
        if re.match(r"Kính gửi\s*:", text, re.I) and re.search(r"[-–—]\s*\S", text):
            return "layout", "source_addressee_block"
    # A source directory of forms is a label/value mapping, not an empty form.
    if len(rows) >= 2 and all(len(r["cells"]) == 2 and re.match(r"^(?:Mẫu|Biểu)\s+số\s*\d+", r["cells"][0]["effective_text"], re.I) for r in rows):
        return "key_value", "repeated_source_label_value_pairs"
    definition_rows = [[c for c in r["cells"] if c["effective_text"]] for r in rows]
    if len(rows) >= 2 and all(len(r) == 3 and r[1]["effective_text"] in {"=", ":"} and
                             len(r[0]["effective_text"]) <= 60 and r[2]["effective_text"] for r in definition_rows):
        return "key_value", "repeated_symbol_definition_separator"
    if rows and len(definition_rows[0]) >= 3 and definition_rows[0][1]['effective_text'] == '=' and not headers:
        left, equals = definition_rows[0][:2]
        if left['rowspan'] == equals['rowspan'] == len(rows) and sum(c['effective_text'] == '=' for c in cells) == 1:
            return 'key_value', 'source_assignment_with_spanned_expression'
    explicit = source.attrs.get("data-table-kind")
    if explicit in TABLE_KINDS:
        return explicit, "explicit_table_kind"
    blanks = sum(not c["effective_text"] for c in cells)
    placeholders = bool(PLACEHOLDER.search(text))
    form_signature = re.search(r"\bKý(?:\s+tên|\s+và|\s*,)|ghi\s+rõ\s+họ|đóng\s+dấu|TÊN THƯƠNG NHÂN|TÊN CƠ QUAN", text, re.I)
    if (placeholders and (form_signature or blanks or len(rows) <= 2) or
            form_signature and len(rows) <= 2 and not headers):
        return "form", "source_placeholders_or_signature_fields"
    corner = next((c for c in cells if c["row"] == c["column"] == 0), None)
    numeric = sum(bool(re.fullmatch(r"[\d.,%+−-]+", c["effective_text"])) for c in cells)
    coded_values = sum(bool(re.search(r"(?:^|\s)\d{2,}[a-zđ]?$", c["effective_text"], re.I)) for c in cells)
    if corner and len(rows) >= 3 and len(compound_labels(corner["text_segments"], corner["effective_text"])) > 1 and (numeric >= 2 or coded_values >= 3 and corner["rowspan"] >= 2):
        return "matrix", "compound_corner_and_numeric_grid"
    if headers or any(r["section"] == "thead" for r in rows):
        return "data", "header_markup"
    if source.attrs.get("role") in {"table", "grid"}:
        return "data", "explicit_table_role"
    # Source declares column labels with an ordinal column; no axis association
    # is asserted from this classification alone.
    if rows and len(rows) >= 2 and len(rows[0]["cells"]) >= 2 and re.fullmatch(r"STT|TT|Số TT", rows[0]["cells"][0]["effective_text"], re.I):
        return "data", "ordinal_column_and_source_labels"
    return "ambiguous", "insufficient_structural_evidence"


def suppress_axes(table):
    table["semantics"] = {"status": "not_applicable", "reason": table["table_kind"]}
    for cell in table["cells"]:
        for key in ("header_refs", "header_candidates", "header_evidence", "association_status", "row_axis", "column_axis", "orientation"):
            cell.pop(key, None)
        cell.pop("role", None)
        cell.pop("confidence", None)


def finalize_table_issues(table, quality):
    old = set(table.get("issues", []))
    quality.issues[:] = [i for i in quality.issues if i["issue_id"] not in old]
    table["issues"] = []
    diagnostics = table.get("_diagnostics", [])
    semantic_codes = {"unresolved_table_semantics", "ambiguous_compound_header", "unresolved_header_role",
                      "unresolved_header_reference", "partial_axis_coverage", "ambiguous_header_bands",
                      "invalid_header_scope", "scope_on_data_cell"}
    unresolved = [d for d in diagnostics if d["code"] in semantic_codes]
    for issue in diagnostics:
        if issue["code"] in semantic_codes:
            continue
        explainable_gap = table["table_kind"] in NO_AXES and issue["code"] in {"ragged_table", "table_grid_gap"} and not any(d["code"] == "overlapping_cells" for d in diagnostics)
        severity = "info" if explainable_gap else None
        details = {"reason": "source_rows_have_different_spanned_widths", "table_kind": table["table_kind"],
                   "axis_associations": "not_applicable", "geometry_preserved": True,
                   "missing_values_filled": False} if explainable_gap else None
        table["issues"].append(quality.add(issue["code"], issue["message"], issue["source_ref"], severity, details=details))
    kind = table["table_kind"]
    if kind in NO_AXES:
        suppress_axes(table)
        if kind in {"form", "annex_form"}:
            table["issues"].append(quality.add("form_table_preserved", "Form text and geometry preserved; axis associations are not applicable", table["source_ref"], "info"))
        return
    if kind == "ambiguous" or unresolved:
        details = {"table_kind": kind, "axis_headers_resolved": False,
                   "reasons": sorted({d["code"] for d in unresolved} or {"insufficient_structural_evidence"}),
                   "affected_cells": sorted({d["source_ref"]["dom_order"] for d in unresolved})}
        table["issues"].append(quality.add("table_semantics_unresolved", "Inspect source header declarations or table purpose; effective text and cell geometry are preserved", table["source_ref"], "warning", details=details))


def refine_table_context(table, quality, annex=False, form=False):
    # A coherent directory retains key/value semantics. A numerical matrix
    # remains factual. A form's context never invents ordinary data-table axes.
    if annex and table["table_kind"] not in {"matrix", "key_value"} and (form or table["table_kind"] == "form"):
        table.update(table_kind="annex_form", classification_evidence="annex_and_source_form_context")
        suppress_axes(table)
    finalize_table_issues(table, quality)
    for cell in table["cells"]:
        for node in cell.get("content", []):
            if node["type"] == "table":
                refine_table_context(node, quality, annex, form)
