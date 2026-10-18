"""Final source-faithful contract cleanup, after structural inference.

This pass does not classify legal hierarchy or alter physical table data.
Only confirmed form scopes admit input labels and composite input fields.
"""
from __future__ import annotations

import json
import re

from vietnam_legal_rag.ingestion.refinement.forms import BLANK, INSTRUCTION, SYMBOL, field_evidence, scan, semantic_body
from vietnam_legal_rag.ingestion.semantics.hierarchy import slice_unit

FIELD_KINDS = {"input", "input_label", "instruction", "composite", "display", "unknown"}
LABEL = re.compile(r"^([^:\n]{1,80}):\s*(.*)$", re.S)
FIELD_NAME = re.compile(
    r"^(?:Chủ biên|Tác giả|Tỷ lệ|Tọa độ|Đơn vị(?:\s+[^:]{1,55})?|"
    r"Tên(?:\s+[^:]{1,65})?|Người(?:\s+[^:]{1,55})?|Ngày(?:\s+[^:]{1,55})?|"
    r"Địa (?:chỉ|điểm)(?:\s+[^:]{1,55})?|Họ(?: và)? tên|Chức vụ|"
    r"Điện thoại|E-?mail|Fax|Website|Số(?:\s+[^:]{1,55})?|"
    r"Cơ quan(?:\s+[^:]{1,55})?|Nơi(?:\s+[^:]{1,55})?|Loại khác)$", re.I)
COORDINATE = re.compile(r"^([XYHZ])\s*[:=]?\s*([.\d,…_+\-\s]+?)(?:\s*\(([^()]+)\))?\s*;?$", re.I)
EXCLUDED_SCOPES = {"bibliography", "bibliography_entry", "note", "footnote_group", "footnote", "recipients", "recipient"}
OPTIONAL_QUALIFIER = re.compile(r"\s*\((?:nếu\b|không bắt buộc\b|tùy chọn\b)[^()]*\)\s*$", re.I)
SENTENCE = re.compile(r"\b(?:phải|đã|là|gồm|đề nghị|thực hiện|ghi|điền|liệt kê|để trống)\b", re.I)
CONTINUATION = re.compile(r"^(?:được\s+)?cấp\s+ngày\b", re.I)
INPUT_KINDS = {"input", "input_label", "composite"}


def short_label(text, known_name=True):
    """A noun-like candidate, never an authoritative classification alone."""
    text = (text or "").strip()
    name = OPTIONAL_QUALIFIER.sub("", text).rstrip()
    body = scan(name)
    # A reason noun phrase can name the action requested, rather than issue
    # that action as an imperative. Its field meaning still stays unknown.
    sentence = SENTENCE.search(body) and not re.match(r'^Lý do\b', body, re.I)
    if not name or len(text) > 80 or len(body.split()) > 12 or re.search(r"[\n:;.!?,]", body) or BLANK.search(body) or sentence:
        return None
    if known_name and not FIELD_NAME.fullmatch(body):
        return None
    if not body[0].isalpha():
        return None
    return name


def input_anchor(node):
    return node.get("type") == "form_field" and node.get("field_kind") in INPUT_KINDS


def unpunctuated_labels(nodes):
    """Confirm a contiguous noun-label run inside a bounded input section."""
    confirmed, i = {}, 0
    while i < len(nodes):
        if nodes[i].get("type") != "paragraph" or not short_label(nodes[i].get("text")):
            i += 1; continue
        end = i
        while end < len(nodes) and nodes[end].get("type") == "paragraph" and short_label(nodes[end].get("text")):
            end += 1
        following = end
        # One issued-document continuation can be part of the same input run;
        # arbitrary prose or a new heading/table cannot be skipped.
        if following < len(nodes) and nodes[following].get("type") == "paragraph" and CONTINUATION.match(scan(nodes[following].get("text"))):
            following += 1
        before = i > 0 and input_anchor(nodes[i - 1])
        after = following < len(nodes) and (input_anchor(nodes[following]) or nodes[following].get("type") == "form_placeholder")
        if before and after:
            confirmed.update({id(n): short_label(n["text"]) for n in nodes[i:end]})
        i = end
    return confirmed


def label_colon(text):
    """Find a field delimiter outside literal parenthetical explanations."""
    stack = []
    pairs = {')': '(', ']': '[', '}': '{'}
    for index, character in enumerate(text):
        if character == '\n':
            return None
        if character in '([{':
            stack.append(character)
        elif character in pairs and stack and stack[-1] == pairs[character]:
            stack.pop()
        elif character == ':' and not stack and text[:index].strip():
            return index
    return None


def label_parts(node):
    text = node.get('text') or ''
    colon = label_colon(text)
    if colon is None:
        return None
    name, value = text[:colon].strip(), text[colon + 1:].strip() or None
    # A long terminal prompt still supplies no entered value. Longer prose
    # containing a colon needs other evidence before asserting a value split.
    return (name, value) if len(name) <= 80 or value is None else None


def label_value_start(text):
    start = label_colon(text) + 1
    return start + len(text[start:]) - len(text[start:].lstrip())


def refine_field(node, active):
    kind = node.get("type")
    if active and kind in {"paragraph", "heading", "unknown", "form_subfield"}:
        parts = label_parts(node)
        if parts and FIELD_NAME.fullmatch(scan(parts[0])):
            if kind != "form_subfield":
                node.update(type="form_field", field_evidence="source_input_label_in_form")
            node["field_kind"] = "input" if parts[1] is not None else "input_label"
    if node.get("type") in {"form_field", "form_subfield"}:
        # Both field families use the same existing source classification.
        # Unknown names/values stay explicit nulls, never fabricated labels.
        classification = field_evidence(node.get("text"))
        role, evidence = classification or ("unknown", "source_form_field_without_value_classification")
        node.setdefault("field_name", None)
        node.setdefault("value_text", None)
        node.setdefault("field_kind", role)
        node.setdefault("field_evidence", evidence)
        parts = label_parts(node)
        if parts:
            node.update(field_name=parts[0], value_text=parts[1])
            if node.get("field_kind") == "input" and parts[1] is None:
                node["field_kind"] = "input_label"
        elif node.get("type") == "form_field" and not node.get("field_name"):
            node.update(field_name=None, value_text=None)
        if node.get("field_kind") == "declaration":
            node["field_kind"] = "display"
        refs = re.findall(r"\((\d+)\)", node.get("text") or "")
        if refs:
            node["placeholder_refs"] = list(dict.fromkeys(refs))
        if node.get("field_kind") == "instruction":
            node["value_text"] = None
        elif parts and parts[1]:
            body = parts[1]
            qualifier = re.match(r'\([^()]+\)\s*', body)
            completion = bool(qualifier and INSTRUCTION.search(qualifier[0]))
            if completion:
                rest = body[qualifier.end():]
                blank = re.match(r'[.…_\s]+', rest)
                if not rest.strip(' :'):
                    node.update(field_kind='instruction', field_evidence='source_completion_qualifier', value_text=None)
                    return
                if blank and BLANK.search(blank[0]):
                    node['value_text'] = blank[0].strip()
                    prompt = rest[blank.end():].strip()
                    if prompt.endswith(':') and short_label(prompt[:-1], known_name=False):
                        start = label_value_start(node['text']) + qualifier.end() + blank.end()
                        child = slice_unit(node, start)
                        child.update(type='form_subfield', field_name=prompt[:-1], value_text=None,
                                     field_kind='input_label', field_evidence='source_nested_prompt_after_placeholder')
                        for key in ('number', 'label', 'marker', 'placeholder_refs'):
                            child.pop(key, None)
                        prefix = slice_unit(node, 0, start)
                        node.update(text=prefix['text'], source_offset=prefix['source_offset'], field_kind='composite')
                        if prefix.get('annotations'):
                            node['annotations'] = prefix['annotations']
                        else:
                            node.pop('annotations', None)
                        node.setdefault('children', []).insert(0, child)
                    return
            # A second short prompt after the first colon is source-backed
            # field structure. Split it with offsets, rather than calling it a
            # value or inventing an identity.
            symbol = SYMBOL.match(body)
            prompt_name = body[symbol.end():] if symbol else body
            if body.endswith(":") and short_label(prompt_name[:-1], known_name=False):
                start = label_value_start(node['text'])
                child = slice_unit(node, start)
                if symbol:
                    child = semantic_body(child, symbol, 'form_subfield')
                child.update(type="form_subfield", field_name=prompt_name[:-1].strip(), value_text=None,
                             field_kind="input_label", field_evidence="source_nested_prompt")
                child.pop("placeholder_refs", None)
                child.pop("number", None)
                if not symbol:
                    child.pop("label", None)
                    child.pop("marker", None)
                prefix = slice_unit(node, 0, start)
                node["text"] = prefix["text"]
                node["source_offset"] = prefix["source_offset"]
                if prefix.get("annotations"):
                    node["annotations"] = prefix["annotations"]
                else:
                    node.pop("annotations", None)
                node["value_text"] = None
                node["field_kind"] = "composite"
                node.setdefault("children", []).insert(0, child)
            elif (blank := re.match(r"(?:\(\d+\)\s*)?[.…_\s]+(?:\(\d+\)[.…_\s]*)?", body)) and BLANK.search(blank[0]) and any(c.isalpha() for c in body[blank.end():]):
                # A source blank followed by another label/declaration prose
                # is a value placeholder, not the whole display. Preserve the
                # complete line, including later prompts, in node.text.
                node["value_text"] = blank[0].strip()


def composite_fields(nodes):
    output, i = [], 0
    while i < len(nodes):
        parent = nodes[i]
        if parent.get("type") == "form_field" and scan(parent.get("field_name")).casefold() == "tọa độ" and not parent.get("value_text"):
            run, axes = [], []
            for child in nodes[i + 1:]:
                match = COORDINATE.fullmatch(child.get("text") or "") if child.get("type") == "paragraph" else None
                if not match or match[1].upper() in axes or not (BLANK.search(match[2]) or re.search(r"\d", match[2])):
                    break
                run.append((child, match)); axes.append(match[1].upper())
            # Axis identities, continuity and explicit blanks/values are all
            # required. Do not invent a missing coordinate or cross prose.
            if len(run) >= 2 and axes[:2] == ["X", "Y"]:
                parent.update(field_kind="composite", field_evidence="adjacent_coordinate_inputs")
                for child, match in run:
                    child.update(type="form_subfield", field_name=match[1], value_text=match[2].strip().rstrip(";").rstrip(),
                                 field_kind="input", field_evidence="source_coordinate_axis")
                    if match[3]:
                        child["unit"] = match[3]
                    parent.setdefault("children", []).append(child)
                i += len(run)
        output.append(parent); i += 1
    return output


def refine_prompts(nodes, *, in_cell=False):
    labels = unpunctuated_labels(nodes)
    grids = {}
    for node in nodes:
        if node.get('_source_grid_parent') is not None:
            grids.setdefault(node['_source_grid_parent'], []).append(node)
    for group in grids.values():
        parts = [label_parts(node) for node in group]
        if (len(group) >= 2 and all(part and part[1] is None for part in parts) and
                all(node.get('type') in {'paragraph', 'form_field'} and not node.get('heading_evidence') for node in group) and
                any(short_label(re.sub(r'[,()]', ' ', part[0]), known_name=False) for part in parts)):
            # Explicit source columns pair terminal input prompts. Preserve
            # unfamiliar labels, including request addressees, without guessing
            # field meaning or entered values from their vocabulary.
            for node, part in zip(group, parts):
                if node['type'] == 'paragraph':
                    node.update(type='form_field', field_name=part[0], value_text=None,
                                field_kind='unknown', field_evidence='source_paired_grid_prompts')
    # Explicit unfamiliar prompts can form a chain next to actual input
    # fields. Classify their structural role without asserting field meaning.
    index = 0
    while index < len(nodes):
        end = index
        def prompt(node):
            parts = label_parts(node)
            return (node.get('type') == 'paragraph' and parts and parts[1] is None and
                    (short_label(parts[0], known_name=False) or
                     '/' in parts[0] and not SENTENCE.match(scan(parts[0])) and not BLANK.search(parts[0])) and
                    not CONTINUATION.match(scan(parts[0])) and
                    not re.search(r'\b(?:kiểm tra|được|như sau|kèm theo)\b', scan(parts[0]), re.I) and
                    not (node.get('heading_evidence') and scan(node['text']).isupper()))
        while end < len(nodes) and prompt(nodes[end]):
            end += 1
        bounded = (end - index >= 2 or
                   in_cell and end > index and not any(n.get('heading_evidence') for n in nodes[index:end]) and
                   not (end < len(nodes) and nodes[end].get('type') == 'list') or
                   index > 0 and (input_anchor(nodes[index - 1]) or
                                  nodes[index - 1].get('field_evidence') == 'source_paired_grid_prompts') or
                   end < len(nodes) and (input_anchor(nodes[end]) or
                                        nodes[end].get('field_evidence') == 'source_paired_grid_prompts' or
                                        nodes[end].get('field_evidence') == 'source_form_declaration'))
        if end > index and bounded:
            for node in nodes[index:end]:
                node.update(type='form_field', field_name=label_parts(node)[0], value_text=None,
                            field_kind='unknown', field_evidence='source_colon_prompt_in_input_sequence')
        index = max(end, index + 1)
    for i, node in enumerate(nodes):
        if id(node) in labels:
            node.update(type="form_field", field_name=labels[id(node)], value_text=None,
                        field_kind="input_label", field_evidence="bounded_form_input_sequence")
        parts = label_parts(node)
        if node.get("type") != "paragraph" or not parts or parts[1] is not None:
            continue
        if node.get("heading_evidence") and scan(node["text"]).isupper():
            node["type"] = "heading"
        elif i + 1 < len(nodes) and nodes[i + 1].get("type") == "form_placeholder":
            # Source supplies an explicit blank immediately after this prompt.
            # Its content is preserved separately; no value is inferred.
            node.update(type="form_field", field_name=parts[0], value_text=None,
                        field_kind="input_label", field_evidence="adjacent_source_placeholder")
    return nodes


def attach_continuations(nodes):
    output = []
    for node in nodes:
        previous = output[-1] if output else None
        if node.get("type") == "paragraph" and CONTINUATION.match(scan(node.get("text"))) and previous and input_anchor(previous) and re.match(r"^(?:Số|Mã)\b", scan(previous.get("field_name")), re.I):
            node["evidence"] = "adjacent_source_field_continuation"
            previous.setdefault("children", []).append(node)
        else:
            output.append(node)
    return output


def refine_form_labels(document):
    def visit(node, active=False):
        active = (active or node.get("type") == "form") and node.get("type") not in EXCLUDED_SCOPES
        if (active and node.get('type') == 'paragraph' and
                re.fullmatch(r'\d+[.…_\s]+', node.get('text') or '') and BLANK.search(node['text'])):
            node.update(type='form_placeholder', evidence='source_numbered_blank_input_slot')
        refine_field(node, active)
        for child in node.get("children", []):
            visit(child, active)
        if active:
            node["children"] = composite_fields(attach_continuations(refine_prompts(node.get("children", []))))
        for cell in node.get("cells", []):
            scope = active or node.get("table_kind") in {"annex_form", "form"}
            # A simple physical cell retains its raw text. Add a semantic view
            # only for reliable input labels; never for arbitrary cell prose.
            if scope and not cell.get("content") and cell.get("text"):
                text = cell["text"]
                lines = text.splitlines(keepends=True)
                if all((m := LABEL.fullmatch(line.strip())) and FIELD_NAME.fullmatch(scan(m[1].strip())) for line in lines):
                    base = {"type": "paragraph", "order": cell["order"], "source_ref": cell["source_ref"], "text": text, "children": []}
                    if cell.get("references"):
                        base["references"] = cell.pop("references")
                    if cell.get("annotations"):
                        base["annotations"] = cell.pop("annotations")
                    if len(lines) == 1:
                        content = [base]
                    else:
                        content, offset = [], 0
                        for line in lines:
                            content.append(slice_unit(base, offset, offset + len(line)))
                            offset += len(line)
                    cell["content"] = content
            before = cell.get("effective_text")
            for child in cell.get("content", []):
                visit(child, scope)
            if scope and cell.get("content"):
                cell["content"] = composite_fields(attach_continuations(refine_prompts(
                    cell["content"], in_cell=cell.get('cell_type') != 'header')))
            from vietnam_legal_rag.ingestion.semantics.tables import effective_cell_text
            assert effective_cell_text(cell)[1] == before, "Form cleanup changed physical cell text"
    visit(document)


def semantic_nodes(result):
    from vietnam_legal_rag.ingestion.validation.extract import semantic_roots, walk_content
    return list(walk_content(list(semantic_roots(result))))


def clean_contract(result, source_root=None):
    """Remove true duplication while retaining distinct physical provenance."""
    if result.get("document"):
        refine_form_labels(result["document"])
    nodes = semantic_nodes(result)
    source_elements = {n.dom_order: n for n in source_root.find()} if source_root is not None else {}
    split_sources = {json.dumps(n["source_ref"], sort_keys=True) for n in nodes if n.get("source_offset", 0) > 0}
    for node in nodes:
        if "boundary_evidence" in node:
            node["evidence"] = node.pop("boundary_evidence")
        if "title_ref" in node:
            node["title_source_ref"] = node.pop("title_ref")
        if node.get("type") == "form" and node.get("title_source_ref") and node["title_source_ref"] != node["source_ref"]:
            node["source_refs"] = node.get("source_refs", [node["source_ref"]]) + [node["title_source_ref"]]
        for key in ("text", "title", "field_name", "value_text"):
            if node.get(key) == "":
                node[key] = None
        refs = node.get("source_refs")
        if refs is not None:
            refs = list({json.dumps(ref, sort_keys=True): ref for ref in refs}.values())
            if len(refs) == 1 and refs[0] == node.get("source_ref"):
                node.pop("source_refs")
            else:
                node["source_refs"] = refs
        if node.get("source_offset") == 0 and json.dumps(node["source_ref"], sort_keys=True) not in split_sources:
            node.pop("source_offset")
        if node.get("title_source_offset") == 0:
            node.pop("title_source_offset")
        if node.get("type") == "footnote_group":
            if not node.get("numbering"):
                node.pop("numbering", None)
                node.pop("list_kind", None)
        if node.get("type") == "footnote" and str(node.get("ordinal")) == node.get("marker"):
            node.pop("ordinal")
        if node.get("references"):
            node["references"] = list({json.dumps(ref, sort_keys=True): ref for ref in node["references"]}.values())
            # A split prompt inherits the original anchor on both fragments.
            # Keep the source link on its text owner; an anchor crossing the
            # split stays on the containing field, rather than being duplicated.
            for child in node.get("children", []):
                if child.get("source_ref") != node["source_ref"] or not child.get("source_offset") or not node.get("text"):
                    continue
                for ref in list(node["references"]):
                    if ref not in child.get("references", []):
                        continue
                    source = source_elements.get(ref["source_ref"]["dom_order"])
                    anchor = re.sub(r"\s+", "", source.text()) if source is not None else ""
                    owner = node if anchor and anchor in re.sub(r"\s+", "", child.get("text") or "") and anchor not in re.sub(r"\s+", "", node["text"]) else child
                    owner["references"].remove(ref)
                    if not owner["references"]:
                        owner.pop("references")
                if not node.get("references"):
                    break
            # A source-backed structural wrapper owns no body here. Identical
            # anchors already live on its actual paragraph/title owner.
            if node.get("references") and not node.get("text") and not node.get("title"):
                # A linked structural marker can legitimately own its anchor.
                # Source anchor text distinguishes it from an inherited body
                # reference; never move a marker-only URL onto unrelated prose.
                for ref in node["references"]:
                    source = source_elements.get(ref["source_ref"]["dom_order"])
                    anchor = re.sub(r"\s+", "", source.text()) if source is not None else ""
                    parent_display = re.sub(r"\s+", "", node.get("label") or "")
                    children = [c for c in node.get("children", []) if ref in c.get("references", [])]
                    if anchor and anchor in parent_display and not any(anchor in re.sub(r"\s+", "", (c.get("text") or "") + (c.get("title") or "") + (c.get("label") or "")) for c in children):
                        for child in children:
                            child["references"].remove(ref)
                            if not child["references"]:
                                child.pop("references")
                child_refs = [r for child in node.get("children", []) for r in child.get("references", [])]
                remaining = [r for r in node["references"] if r not in child_refs]
                if remaining:
                    node["references"] = remaining
                else:
                    node.pop("references")
    # Structured metadata records can delegate their display text to content;
    # null indicates semantic absence, while the physical cells stay untouched.
    def records(value):
        if isinstance(value, list):
            for child in value:
                records(child)
        elif isinstance(value, dict):
            if "cell_id" not in value:
                for key in ("text", "title", "field_name", "value_text", "value"):
                    if value.get(key) == "":
                        value[key] = None
            for child in value.values():
                if isinstance(child, (list, dict)):
                    records(child)
    records(result)


def form_label_audit(document):
    """Inspect colon prompts and short unpunctuated labels in source context."""
    from vietnam_legal_rag.ingestion.validation.forms import walk
    audit = []
    sibling_metadata = {}
    for node, parents in walk([document]):
        colon = bool(re.fullmatch(r"[^:\n]{1,80}:\s*", node.get("text") or ""))
        bare = short_label(node.get("text"))
        if node.get("type") != "paragraph" or not (colon or bare):
            continue
        active = any(p.get("type") == "form" or p.get("table_kind") in {"annex_form", "form"} for p in parents)
        if not active:
            continue
        text = scan(node["text"])
        excluded = any(p.get("type") in EXCLUDED_SCOPES for p in parents)
        siblings = parents[-1].get("children", parents[-1].get("content", [])) if parents else []
        owner = id(parents[-1]) if parents else None
        if owner not in sibling_metadata:
            sibling_metadata[owner] = (unpunctuated_labels(siblings),
                                       {id(n): siblings[i + 1] if i + 1 < len(siblings) else None
                                        for i, n in enumerate(siblings)})
        bare_labels, next_nodes = sibling_metadata[owner]
        confirmed_bare = id(node) in bare_labels
        following = next_nodes.get(id(node))
        display_caption = bool(
            colon and re.fullmatch(r'(?:Mẫu|Biểu|Phiếu)\s*:', text, re.I) and
            node.get('heading_evidence') and following and
            following.get('type') in {'paragraph', 'heading', 'form_title', 'form_subtitle'} and
            following.get('heading_evidence') and (following.get('text') or '').isupper() and
            not BLANK.search(following.get('text') or ''))
        literal_list_leadin = bool(
            colon and following and following.get('type') == 'list' and
            len(following.get('children', [])) >= 2 and
            not any(n.get('field_kind') in {'input', 'input_label', 'composite'} or
                    BLANK.search(n.get('text') or '') for n, _ in walk([following])))
        if excluded:
            reason = "explanatory_note_or_recipient_context"
        elif display_caption:
            reason = "source_display_caption_before_title"
        elif literal_list_leadin:
            reason = "source_leadin_before_literal_list"
        elif bare and not colon:
            reason = "unresolved_input_sequence_label" if confirmed_bare else "short_label_outside_confirmed_input_sequence"
        elif text.isupper() and node.get("heading_evidence"):
            reason = "displayed_form_formula"
        elif INSTRUCTION.search(text) or re.search(r"(?:gồm|như sau|kèm theo|kiểm tra)\s*[^:]*:$", text, re.I):
            reason = "introductory_prose_for_following_content"
        elif re.match(r"^cấp\s+ngày\b", text, re.I):
            reason = "attached_source_field_continuation" if node.get("evidence") == "adjacent_source_field_continuation" else "source_continuation_without_input_label"
        elif re.search(r"\b(?:đã|được|là)\b", text, re.I):
            reason = "source_prose_statement"
        else:
            reason = "insufficient_form_label_evidence"
        unresolved = not (excluded or display_caption or literal_list_leadin) and (confirmed_bare or reason == "insufficient_form_label_evidence" or bool((parts := label_parts(node)) and FIELD_NAME.fullmatch(scan(parts[0]))))
        audit.append({"order": node["order"], "source_ref": node["source_ref"], "text": node["text"], "reason": reason, "justified": not unresolved})
    return audit
