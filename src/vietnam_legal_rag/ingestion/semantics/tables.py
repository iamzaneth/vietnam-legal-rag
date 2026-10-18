"""Effective cell text and conservative, context-sensitive table classification."""
from __future__ import annotations

import re
import unicodedata

from vietnam_legal_rag.ingestion.html.source import whitespace
from vietnam_legal_rag.ingestion.validation.quality import title_owned_by_child
from vietnam_legal_rag.ingestion.semantics.hierarchy import AUTHORITY, DELEGATION_ABBREVIATION

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


def source_blank_region(segment):
    """Distinguish completion blanks from ellipses in populated column prose."""
    if PLACEHOLDER.fullmatch(segment.strip()) or re.match(r'^[^:\n]{1,80}:\s*\.{3}', segment):
        return True
    for match in re.finditer(r'\.{4,}|…{2,}|_{3,}|\[\s*(?:tên|ghi|điền)[^]]*\]', segment, re.I):
        if match[0].startswith('.') and re.search(r'[,;]\s*$', segment[:match.start()]):
            continue
        return True
    return False


def classify_table(source, rows, cells):
    """Called only AFTER geometry, cell content, segments and effective_text."""
    text = unicodedata.normalize("NFC", " ".join(c["effective_text"] for c in cells))
    headers = any(c["cell_type"] == "header" for c in cells)
    if source.attrs.get("role") == "presentation":
        return "layout", "explicit_presentation_role"
    heading = re.search(r"CỘNG\s+H[ÒO][ÀA].*VIỆT\s+NAM|Độc lập\s*[-–—]\s*Tự do", text, re.I)
    authority = re.search(r"Số\s*:|" + AUTHORITY, text, re.I)
    closing = re.search(r"Nơi nhận\s*:", text, re.I) and re.search(r"KT\.|TM\.|TL\.|THỨ TRƯỞNG|BỘ TRƯỞNG|CHỦ TỊCH|Đã ký", text, re.I)
    meaningful_rows = [r for r in rows if any(c["effective_text"] for c in r["cells"])]
    from vietnam_legal_rag.ingestion.semantics.hierarchy import opening_role, closing_role
    segments = [segment for cell in cells for segment in cell['text_segments'] if segment]
    from vietnam_legal_rag.ingestion.semantics.hierarchy import NATIONAL_HEADING, NATIONAL_MOTTO
    national_pair = re.compile(r'(?:' + NATIONAL_HEADING + r')\s*(?:' + NATIONAL_MOTTO + r')(?:\s*[-_]{3,})?', re.I)
    if (len(meaningful_rows) == 1 and len(cells) <= 2 and not headers and
            len(segments) == 1 and national_pair.fullmatch(segments[0])):
        return 'layout', 'source_national_heading_without_authority'
    from vietnam_legal_rag.ingestion.semantics.hierarchy import signer_name_text
    if (len(rows) == 1 and len(cells) <= 2 and
            sum(bool(c['effective_text']) for c in cells) == 1 and len(segments) == 2 and
            closing_role({'text': segments[0]}) == 'signer_title' and
            signer_name_text(segments[1]) and not segments[1].isupper()):
        return 'layout', 'source_signature_block'
    # Explicit verification scope takes precedence over the more general
    # signing-column layout, including tables containing only a single row.
    verification_details = (any(re.match(r'^Số\s*:\s*\S', s, re.I) for s in segments) and
                            any(re.fullmatch(r'.+,\s*ngày\s*(?:\d+)?\s*tháng\s*(?:\d+)?\s*năm\s*\d{4}', s, re.I)
                                for s in segments))
    if (len(meaningful_rows) <= 3 and len(cells) <= 6 and not headers and
            re.search(r'XÁC THỰC VĂN BẢN HỢP NHẤT', text, re.I) and
            (re.search(r'Nơi nhận\s*:', text, re.I) or verification_details) and
            (any(closing_role({'text': segment}) == 'signer_title' for segment in segments) or
             verification_details and any(opening_role({'text': s}) == 'issuing_authority' for s in segments))):
        return 'layout', 'source_consolidated_verification_block'
    spanned_signer = closing and not headers and any(c['rowspan'] >= len(rows) and re.search(
        r'CHỦ TỊCH|BỘ TRƯỞNG|GIÁM ĐỐC|Đã ký', c['effective_text'], re.I) for c in cells)
    if spanned_signer and len({c['column'] for c in cells}) == 2:
        return 'layout', 'spanned_signature_and_recipient_columns'
    signing_cells = [c for c in cells if c['effective_text']]
    if len(signing_cells) >= 2 and all(re.match(
            r'^' + DELEGATION_ABBREVIATION + r'[./]\s*(?:BỘ|CHÁNH ÁN|VIỆN TRƯỞNG|CHỦ TỊCH|GIÁM ĐỐC)',
            c['effective_text']) for c in signing_cells):
        return 'layout', 'explicit_delegation_in_each_signing_cell'
    letterhead_only = heading and all(not segment or re.fullmatch(
        r"CỘNG\s+H[ÒO][ÀA].*VIỆT\s+NAM|Độc lập\s*[-–—]\s*Tự do\s*[-–—]\s*Hạnh phúc",
        segment, re.I) for c in cells for segment in c['text_segments'])
    letterhead_only = bool(letterhead_only) or bool(heading and segments and all(
        opening_role({'text': segment}) in {'national_heading', 'national_motto'} or
        re.fullmatch(r'[-–—_\s]+', segment) for segment in segments))
    if len(meaningful_rows) <= 2 and len(cells) <= 12 and not headers and (heading and authority or closing or letterhead_only):
        return "layout", "paired_document_heading_or_closing"
    if len(meaningful_rows) == 3 and len(cells) <= 12 and not headers and heading and authority:
        from vietnam_legal_rag.ingestion.semantics.hierarchy import opening_role
        segments = [segment for cell in cells
                    if opening_role({'text': cell['effective_text']}) != 'issuing_authority'
                    for segment in cell['text_segments'] if segment]
        if all(opening_role({'text': segment}) in {
                'issuing_authority', 'national_heading', 'national_motto', 'document_number', 'place_and_date'} or
                re.fullmatch(r'.{0,80},\s*ngày\s*\d+\s*tháng\s*\d+\s*năm\s*\d{4}', segment, re.I) or
                re.fullmatch(r'[-–—_\s]+', segment) for segment in segments):
            return 'layout', 'source_multirow_letterhead'
    if len(rows) <= 3 and len(cells) <= 6 and not headers:
        # Recipient lists can be long; their explicit address label supplies
        # evidence independently of the short signature-block heuristic.
        meaningful = [c for c in cells if c['effective_text']]
        if (meaningful and re.match(r"Kính gửi\s*:", meaningful[0]['effective_text'], re.I)
                and any(re.match(r"^[-–—]\s*\S", segment)
                        for c in meaningful for segment in c['text_segments'])):
            return "layout", "source_addressee_block"
    if len(rows) <= 3 and len(cells) <= 6 and not headers and len(text) <= 300:
        from vietnam_legal_rag.ingestion.semantics.hierarchy import closing_role
        segments = [t for c in cells for t in c['text_segments']]
        title_names = len(rows) == 1 and 2 <= len(segments) <= 4 and sum(
            closing_role({'text': t}) == 'signer_title' for t in segments) == 1 and all(
                closing_role({'text': t}) == 'signer_title' or
                2 <= len(t.split()) <= 7 and all(w.isalpha() and w[0].isupper() for w in t.split()) for t in segments)
        signature = re.search(r"\bĐã ký\b|\[\s*daky\s*\]", text, re.I) or (re.search(r"\b" + DELEGATION_ABBREVIATION + r"[./]\s*", text) and
                    re.search(r"\b(?:CHỦ TỊCH|BỘ TRƯỞNG|GIÁM ĐỐC|THỦ TƯỚNG)\b", text))
        if (signature or title_names) and not any(
                re.fullmatch(r"[\d.,%]+", c["effective_text"]) for c in cells):
            return "layout", "source_signature_block"
    # A source directory of forms is a label/value mapping, not an empty form.
    from vietnam_legal_rag.ingestion.refinement.forms import FORM_NUMBER
    if len(rows) >= 2 and all(len(r["cells"]) == 2 and FORM_NUMBER.fullmatch(r["cells"][0]["effective_text"]) for r in rows):
        return "key_value", "repeated_source_label_value_pairs"
    definition_rows = [[c for c in r["cells"] if c["effective_text"]] for r in rows]
    if len(rows) >= 2 and all(len(r) == 2 and re.match(r'^[:=]\s*\S', r[1]['effective_text'])
                             and len(r[0]['effective_text']) <= 120 for r in definition_rows):
        return 'key_value', 'source_label_and_delimited_value_columns'
    if len(rows) >= 2 and all(len(r) == 3 and r[1]["effective_text"] in {"=", ":"} and
                             len(r[0]["effective_text"]) <= 60 and r[2]["effective_text"] for r in definition_rows):
        return "key_value", "repeated_symbol_definition_separator"
    if len(rows) >= 2 and all(len(r) == 3 and len(r[0]['effective_text']) <= 120 and r[2]['effective_text'] and
            re.fullmatch(r'[A-Za-zΑ-Ωα-ω][A-Za-z0-9_Α-Ωα-ω]*\s*=', r[1]['effective_text']) for r in definition_rows):
        return 'key_value', 'repeated_source_labeled_symbol_assignments'
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
    ordinal_columns = bool(len(rows) >= 2 and len(rows[0]['cells']) >= 2 and
                           re.fullmatch(r'STT|TT|Số TT', rows[0]['cells'][0]['effective_text'], re.I))
    if (headers or any(r['section'] == 'thead' for r in rows) or ordinal_columns) and placeholders:
        # Three dots in populated column prose can be punctuation. Declared
        # data headers require an actual blank region or completion prompt
        # before ordinary empty physical cells can turn the table into a form.
        placeholders = any(source_blank_region(segment) for cell in cells for segment in cell['text_segments'])
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
    if ordinal_columns:
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
    populated_values = (table['table_kind'] == 'data' and
                        not any(source_blank_region(segment) for cell in table['cells']
                                for segment in cell['text_segments']) and
                        any(cell['cell_type'] == 'data' and cell['column'] > 0 and
                            cell.get('header_refs', {}).get('column') and
                            re.fullmatch(r'[+−-]?\d+(?:[.,]\d+)+(?:\s*%)?', cell['effective_text'])
                            for cell in table['cells']))
    if (annex and not populated_values and table["table_kind"] not in {"matrix", "key_value"}
            and (form or table["table_kind"] == "form")):
        table.update(table_kind="annex_form", classification_evidence="annex_and_source_form_context")
        suppress_axes(table)
    finalize_table_issues(table, quality)
    for cell in table["cells"]:
        for node in cell.get("content", []):
            if node["type"] == "table":
                refine_table_context(node, quality, annex, form)
