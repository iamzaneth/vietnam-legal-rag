"""Source-backed form semantics, note sequences and local lists for EXTRACT 2.3.

All repairs stay within one source form, note or table cell. Labels preserve
the original marker characters; semantic text excludes those markers.
"""
from __future__ import annotations

import re
import unicodedata

from .legal_hierarchy import container, normalized_scan, opening_role, closing_role, slice_unit, short_heading
from .html_source import Node

FORM_NUMBER = re.compile(r"^(?:Mẫu|Biểu|Phiếu)\s+(?:số\s*)?(\d+)(?=[\s.:)]|$)", re.I)
NOTE_HEADING = re.compile(r"^(?:\*\s*)?(?:Ghi chú|Chú thích|Notes|Hướng dẫn|Lưu ý)\s*:?$", re.I)
BIBLIOGRAPHY = re.compile(r"(?:DANH MỤC\s+)?TÀI LIỆU THAM KHẢO|^REFERENCES$", re.I)
DIGIT = re.compile(r"^(\d+)[.)]\s+")
DECIMAL = re.compile(r"^\d+(?:\.\d+)+\.?\s+")
ALPHA = re.compile(r"^([a-zđ])[.)]\s+", re.I)
DASH = re.compile(r"^([-–—•])\s+")
FOOTNOTE = re.compile(r"^(\d+)(?:\s+|[.)]\s+)\S")
BLANK = re.compile(r"\.{3,}|…|_{3,}|\[\s*(?:\.\.\.|…|[^]]+)\]|\(\d+\)")
INPUT = re.compile(r"^(?:Tên(?:\s+[^:]{1,65})?|Địa chỉ(?:\s+[^:]{1,65})?|Ngày|Người nộp|Đơn vị|Số(?: hiệu)?|Ký tên|Họ(?: và)? tên|Điện thoại|Fax|Email|Cơ quan|Tác giả|Nơi[^:]{0,40})\s*:", re.I)
INSTRUCTION = re.compile(r"\b(?:phải|ghi|điền|kê khai|khai báo|liệt kê|nêu (?:rõ|cụ thể)|được trình bày|trình bày theo|trang (?:bìa|đầu tiên|\d+)|quy cách|để trống)\b", re.I)
TEXTUAL = {"paragraph", "heading", "unknown", "form_field", "footnote", "note", "numbered_paragraph"}


def scan(text):
    return unicodedata.normalize("NFC", text or "")


def form_boundary(block, active=False):
    text, offsets = normalized_scan(block.get("text", ""))
    match = FORM_NUMBER.match(text)
    if match:
        if re.match(r"\s+(?:của|được|này|theo)\b", text[match.end():], re.I):
            return None  # A prose citation cannot start another form.
        return {"number": block["text"][offsets[match.start(1)]:offsets[match.end(1)]], "end": offsets[match.end()], "evidence": "explicit_form_number"}
    # A displayed heading can start a standalone form only before any active
    # form. Within a numbered form it is a title, not a new boundary.
    if not active and block.get("heading_evidence") and text.isupper() and re.match(r"^(?:PHIẾU|ĐƠN|BÁO CÁO|BIÊN BẢN)\b", text):
        return {"number": None, "end": 0, "evidence": "standalone_form_heading"}
    return None


def semantic_body(node, match, kind, *, number=False):
    """Split structural label/body without changing characters or source order."""
    original = node.get("text", "")
    tail = slice_unit(node, match.end())
    result = {k: v for k, v in node.items() if k not in {"text", "annotations", "candidate_role", "confidence"}}
    result.update(type=kind, label=original[:match.end()].rstrip(), text=tail["text"])
    result["number" if number else "marker"] = match[1]
    if tail.get("annotations"):
        result["annotations"] = tail["annotations"]
    label_annotations = [{**a, "end": min(a["end"], match.end())} for a in node.get("annotations", []) if a["start"] < match.end()]
    if label_annotations:
        result["label_annotations"] = label_annotations
    return result


def make_form(block, boundary):
    if not boundary["end"]:
        form = container("form", block)
        form.update(number=None, title=None, boundary_evidence=boundary["evidence"], children=[{**block, "type": "form_title"}])
        return form
    text, end = block["text"], boundary["end"]
    punctuation = re.match(r"[ \t]*[.:)]?", text[end:])[0]
    end += len(punctuation)
    tail = slice_unit(block, end)
    form = {k: v for k, v in block.items() if k not in {"text", "annotations", "children"}}
    form.update(type="form", number=boundary["number"], label=text[:end].rstrip(),
                title=tail["text"] or None, text="", children=[], boundary_evidence=boundary["evidence"])
    if tail.get("annotations"):
        form["title_annotations"] = tail["annotations"]
    return form


def consecutive(previous, following, style):
    if style == "digit":
        return int(following) == int(previous) + 1
    if style == "dash":
        return previous == following
    a, b = previous.casefold(), following.casefold()
    return any(a in alphabet and b in alphabet and alphabet.index(b) == alphabet.index(a) + 1
               for alphabet in ("abcdđeghiklmnopqrstuvxy", "abcdefghijklmnopqrstuvwxyz"))


def marker(node, pattern):
    return pattern.match(node.get("text") or "") if node["type"] in TEXTUAL else None


def group_runs(children, bibliography=False):
    output, i = [], 0
    while i < len(children):
        node = children[i]
        if node["type"] not in {"paragraph", "heading", "unknown", "numbered_paragraph"}:
            output.append(node); i += 1; continue
        for pattern, style in ((DIGIT, "digit"), (ALPHA, "alpha"), (DASH, "dash")):
            first = marker(node, pattern)
            if first:
                break
        else:
            output.append(node); i += 1; continue
        run, previous = [], None
        while i + len(run) < len(children):
            item = children[i + len(run)]
            if item["type"] not in {"paragraph", "heading", "unknown", "numbered_paragraph"}:
                break
            match = marker(item, pattern)
            if not match or previous and not consecutive(previous, match[1], style):
                break
            run.append((item, match)); previous = match[1]
        if len(run) < 2 and not (bibliography and style == "digit"):
            output.append(node); i += 1; continue
        kind = "bibliography" if bibliography and style == "digit" else "list"
        listing = container(kind, node)
        listing.update(list_kind="unordered" if style == "dash" else "ordered", style="dash" if style == "dash" else style, numbering={})
        listing["children"] = [semantic_body(n, m, "bibliography_entry" if kind == "bibliography" else "list_item", number=style == "digit") for n, m in run]
        for item in listing["children"]:
            item.pop("field_kind", None)
        output.append(listing); i += len(run)
    return output


def group_notes(children):
    output, i = [], 0
    while i < len(children):
        node = children[i]
        explicit = bool(NOTE_HEADING.fullmatch(scan(node.get("text"))))
        if explicit:
            node["type"] = "note"
            j = i + 1
        else:
            j = i
        run, previous = [], None
        while j + len(run) < len(children):
            item = children[j + len(run)]
            match = FOOTNOTE.match(item.get("text") or "") if item["type"] in TEXTUAL else None
            if not match or previous and int(match[1]) != int(previous) + 1:
                break
            # FOOTNOTE includes its first body character to require real text.
            prefix = re.match(r"^(\d+)(?:\s+|[.)]\s+)", item["text"])
            run.append((item, prefix)); previous = match[1]
        supported = explicit or len(run) >= 2 and any(n.get("_note_style") or n["type"] == "footnote" for n, _ in run)
        if run and supported:
            group = container("footnote_group", run[0][0])
            group["children"] = [semantic_body(n, m, "footnote") for n, m in run]
            if explicit:
                node["children"].append(group); output.append(node)
            else:
                output.append(group)
            i = j + len(run)
            continue
        if explicit:
            following = children[j:]
            grouped = group_runs(following)
            if grouped and grouped[0]["type"] == "list":
                listing = grouped[0]
                count = len(listing["children"])
                node["children"].append(listing); output.append(node); i = j + count; continue
        output.append(node); i += 1
    return output


def field_evidence(text):
    body = scan(text)
    prefix = DIGIT.match(body)
    if prefix:
        body = body[prefix.end():]
    dash = DASH.match(body)
    if dash:
        body = body[dash.end():]
    if BLANK.search(body) or INPUT.match(body):
        return "input", "source_placeholder_or_input_label"
    if INSTRUCTION.search(body):
        return "instruction", "source_completion_instruction"
    if prefix and body.rstrip().endswith(":"):
        return "instruction", "numbered_form_data_request"
    if prefix and re.search(r"\b(?:xin chịu trách nhiệm|cam kết)\b", body, re.I):
        return "display", "source_form_declaration"
    return None


def group_recipients(children):
    output, recipients, recipient = [], None, None
    for node in children:
        text = scan(node.get("text"))
        if re.fullmatch(r"(?:Sao kính gửi|Đồng kính gửi|Nơi nhận)\s*:?", text, re.I):
            recipients = {**node, "type": "recipients"}
            output.append(recipients); recipient = None
        elif recipients and DASH.match(text) and node["type"] in TEXTUAL:
            recipient = semantic_body(node, DASH.match(node["text"]), "recipient")
            recipients["children"].append(recipient)
        elif recipients and recipient and node["type"] in TEXTUAL and text.startswith("("):
            recipient["children"].append(node)
        elif recipients and recipient and node["type"] in TEXTUAL and sum(n.get("text", "").count("(") - n.get("text", "").count(")") for n in recipient["children"]) > 0:
            recipient["children"].append(node)
        else:
            recipients = recipient = None
            output.append(node)
    return output


def placeholders(node):
    refs = re.findall(r"\((\d+)\)", node.get("text") or "")
    if refs:
        node["placeholder_refs"] = list(dict.fromkeys(refs))


def refine_subfields(children):
    output, active, i = [], None, 0
    while i < len(children):
        node = children[i]
        if node["type"] == "form_field":
            active = node
        elif marker(node, DIGIT):
            active = None  # An unclassified counter still closes the preceding field.
        elif node["type"] in {"note", "footnote_group", "form_title", "form_subtitle", "form_header", "form_signature"}:
            active = None
        match = marker(node, ALPHA)
        if match and active:
            end = i
            while end < len(children) and (end == i or not marker(children[end], DIGIT) and children[end]["type"] not in {"form_field", "note", "footnote_group", "form_header", "form_title", "form_subtitle", "form_signature"}):
                end += 1
            marked = [(n, marker(n, ALPHA)) for n in children[i:end]]
            marked = [(n, m) for n, m in marked if m]
            sequential = len(marked) >= 2 and all(consecutive(a[1][1], b[1][1], "alpha") for a, b in zip(marked, marked[1:]))
            if sequential:
                # Preserve the contiguous field's introductory content before
                # its subfields; never cross another numbered unit.
                position = next(j for j, n in enumerate(output) if n is active)
                active["children"].extend(output[position + 1:])
                del output[position + 1:]
                subfield = None
                for item in children[i:end]:
                    found = marker(item, ALPHA)
                    if found:
                        subfield = semantic_body(item, found, "form_subfield")
                        classification = field_evidence(subfield["text"])
                        kind, evidence = classification or ("unknown", "source_alphabetic_subfield_sequence")
                        subfield.update(field_name=None, field_kind=kind,
                                        field_evidence=evidence, value_text=None)
                        placeholders(subfield)
                        active["children"].append(subfield)
                    elif subfield:
                        subfield["children"].append(item)
                i = end; continue
        output.append(node); i += 1
    return output


def refine_form(form):
    bibliography = bool(BIBLIOGRAPHY.search(scan(form.get("title"))))
    children = group_recipients(group_notes(form["children"]))
    output, header, signature = [], None, None
    title_phase, displayed = True, False
    for index, node in enumerate(children):
        text = node.get("text") or ""
        normalized = scan(text)
        following = children[index + 1] if index + 1 < len(children) else None
        if node["type"] == "form_title":
            output.append(node); displayed = True; continue
        if title_phase and node["type"] == "table" and re.search(r"CỘNG H[ÒO][ÀA].*VIỆT NAM", scan(" ".join(c["effective_text"] for c in node["cells"])), re.I):
            output.append({**container("form_header", node), "children": [node]}); continue
        # Blank authority lines are official form header content when the next
        # source unit is the national heading. Their presence does not end the
        # displayed-title region or supply an authority identity.
        if title_phase and re.fullmatch(r"[\s.…_]*(?:\(\d+\)[\s.…_]*)*", text) and BLANK.search(text) and following and opening_role(following) == "national_heading":
            if not header:
                header = container("form_header", node); output.append(header)
            node["type"] = "form_placeholder"; placeholders(node)
            header["children"].append(node); continue
        role = opening_role({**node, "type": "paragraph"}) if text and node["type"] in TEXTUAL else None
        if title_phase and normalized.isupper() and re.match(r"^TÊN (?:THƯƠNG NHÂN|CƠ QUAN|ĐƠN VỊ|TỔ CHỨC)\b", normalized):
            role = "issuing_authority"
        if title_phase and re.fullmatch(r".{0,80},\s*ngày.{0,30}tháng.{0,30}năm.{0,30}", normalized, re.I):
            role = "place_and_date"
        layout = node.get("_source_layout")
        same_header_layout = bool(header and layout and any(c.get("_source_layout") == layout for c in header["children"]))
        if title_phase and (role in {"issuing_authority", "national_heading", "national_motto", "place_and_date", "document_number"} or re.match(r"^Số\s*:", normalized, re.I) or same_header_layout):
            if not header:
                header = container("form_header", node); output.append(header)
            node["type"] = "form_number" if role == "document_number" or re.match(r"^Số\s*:", normalized, re.I) else role or "paragraph"
            if not role and node["type"] == "paragraph" and BLANK.search(text):
                node.update(type="form_field", field_kind="input", field_evidence="source_header_placeholder")
            placeholders(node)
            header["children"].append(node); signature = None; continue
        header = None
        heading = bool(text and (node.get("heading_evidence") or node.get("_alignment") == "center") and
                       len(text) <= 400 and not DIGIT.match(text) and not BLANK.search(text) and not NOTE_HEADING.fullmatch(normalized))
        if title_phase and heading and node["type"] in TEXTUAL:
            node["type"] = "form_subtitle" if displayed else "form_title"
            bibliography |= bool(BIBLIOGRAPHY.search(normalized))
            displayed = True; output.append(node); continue
        if node["type"] not in {"annex_note", "separator"}:
            title_phase = False
        signature_role = closing_role({**node, "type": "paragraph"}) if text and node["type"] in TEXTUAL else None
        if signature_role and signature_role != "recipients" or text and node.get("heading_evidence") and normalized.isupper() and re.match(r"^(?:NGƯỜI (?:NỘP|LẬP|YÊU CẦU)|ĐẠI DIỆN|BÊN (?:GIAO|NHẬN)|THỦ TRƯỞNG)\b", normalized):
            if not signature:
                signature = container("form_signature", node); output.append(signature)
            node["type"] = signature_role or "signer_title"
            if signature_role == "signature_marker":
                node["semantic"] = "signed"
            signature["children"].append(node); continue
        signature = None
        if node["type"] in TEXTUAL and text and not NOTE_HEADING.fullmatch(normalized):
            if bibliography and DIGIT.match(text):
                node["type"] = "paragraph"; node.pop("field_kind", None)
            elif re.fullmatch(r"[\s.…_]*(?:\(\d+\)[\s.…_]*)*", text) and BLANK.search(text):
                node["type"] = "form_placeholder"; placeholders(node)
            else:
                # Alphabetic markers are resolved against their preceding field
                # as a sequence, before considering independent input labels.
                evidence = field_evidence(text) if not ALPHA.match(text) else None
                prefix = DIGIT.match(text)
                body = text[prefix.end():] if prefix else text
                if not evidence and prefix and short_heading(body) and following and following["type"] == "table":
                    evidence = ("instruction", "short_numbered_form_component_before_table")
                if not evidence and prefix and re.fullmatch(r"(?:Số điện thoại|Địa chỉ|Họ(?: và)? tên|Ngày|Tên [^:]{1,60})", scan(body), re.I):
                    evidence = ("input", "numbered_form_input_label")
                if evidence:
                    node = semantic_body(node, prefix, "form_field", number=True) if prefix else node
                    if not prefix and DASH.match(text):
                        node = semantic_body(node, DASH.match(text), "form_field")
                    node.update(type="form_field", field_kind=evidence[0], field_evidence=evidence[1]); placeholders(node)
                elif node["type"] == "form_field":
                    node["type"] = "paragraph"; node.pop("field_kind", None)
        output.append(node)
    form["children"] = group_runs(refine_subfields(output), bibliography=bibliography)
    if not form.get("title"):
        display = next((n for n in form["children"] if n["type"] == "form_title"), None)
        if display:
            form.update(title=display["text"], title_source_ref=display["source_ref"])


def refine_cells(node, in_form=False):
    """Semanticize local sequences AFTER classification; effective text is frozen."""
    in_form |= node["type"] == "form"
    for cell in node.get("cells", []):
        before = cell["effective_text"]
        content = cell.get("content", [])
        if content:
            cell["content"] = group_runs(group_recipients(group_notes(content)))
            for child in cell["content"]:
                if in_form and child["type"] in TEXTUAL:
                    placeholders(child)
                refine_cells(child, in_form)
            from .table_semantics import effective_cell_text
            assert effective_cell_text(cell)[1] == before, "Cell semantic refinement changed effective text"
    for child in node.get("children", []):
        refine_cells(child, in_form)


def refine_annex_titles(node):
    siblings = node.get("children", [])
    candidates = [n for n in siblings if n["type"] == "numbered_item" and short_heading(n.get("text")) and n.get("children")]
    for child in siblings:
        text = child.get("text")
        if child["type"] == "numbered_item" and short_heading(text) and child.get("children") and (child.get("heading_evidence") or len(candidates) >= 2):
            child.update(title=text, text="", title_evidence="short_heading_with_dependent_content")
            if child.get("annotations"):
                child["title_annotations"] = child.pop("annotations")
        refine_annex_titles(child)


def refine_forms(document):
    def visit(node):
        if node.pop("_footnote_scope", False):
            node["type"] = "footnote_group"
            for item in node["children"]:
                item.update(type="footnote", marker=str(item["ordinal"]))
        if node["type"] == "form":
            refine_form(node)
        elif node["type"] not in {"note", "footnote_group"}:
            node["children"] = group_notes(node.get("children", []))
        for child in node.get("children", []):
            visit(child)
    visit(document)
    refine_annex_titles(document)
    refine_cells(document)


def navigation_artifacts(root, quality):
    """Only source-backed navigation/terminal footnote backlinks are excluded."""
    parents = {}
    def index(node):
        for child in node.children:
            if isinstance(child, Node):
                parents[id(child)] = node; index(child)
    index(root)
    excluded = set()
    for node in root.find():
        text = node.text().strip()
        if text not in {"↩", "↑", "↓", "«", "»", "Trở về", "Quay lại"}:
            continue
        if node.find():
            continue  # Audit only the leaf, never its legal-text ancestor.
        lineage, parent = [], parents.get(id(node))
        while parent:
            lineage.append(parent); parent = parents.get(id(parent))
        linked = any(n.tag in {"a", "nav", "button"} or n.attrs.get("role") == "navigation" for n in [node] + lineage)
        table = any(n.tag in {"table", "td", "th"} for n in lineage)
        footer_list = next((n for n in lineage if n.tag == "ol"), None)
        terminal = False
        if footer_list and text == "↩" and not table and node.tag == "em":
            parent = parents.get(id(footer_list))
            blocks = [c for c in parent.children if isinstance(c, Node)] if parent else []
            position = next((i for i, c in enumerate(blocks) if c is footer_list), -1)
            terminal = position == len(blocks) - 1 and any(c.tag == "hr" for c in blocks[:position])
            if terminal:
                footer_list.attrs["_extract_footnote_scope"] = True
        if linked or terminal:
            quality.ignore(node, "navigation_artifact"); excluded.add(node.dom_order)
    return excluded
