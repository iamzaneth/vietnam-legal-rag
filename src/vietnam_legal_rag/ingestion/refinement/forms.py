"""Source-backed form semantics, note sequences and local lists for EXTRACT 2.3.

All repairs stay within one source form, note or table cell. Labels preserve
the original marker characters; semantic text excludes those markers.
"""
from __future__ import annotations

import re
import unicodedata

from vietnam_legal_rag.ingestion.semantics.hierarchy import ATTACHMENT_NOTE, AUTHORITY, DOCUMENT_SET_TITLE, container, normalized_scan, opening_role, closing_role, roman_ordinal, slice_unit, short_heading
from vietnam_legal_rag.ingestion.html.source import Node

FORM_NUMBER = re.compile(r"^(?:Mẫu|Biểu|Phiếu)\s+(?:số\s*:?\s*)?((?:\d+[a-zđ]?(?:[-/][a-zđ0-9]+)*|(?=[a-zđ0-9/-]*\d)[a-zđ]{1,12}\d*(?:[-/][a-zđ0-9]+)+)(?:,\s*(?-i:[A-ZĐ0-9/-]{1,12}))*)(?:\[\d+\])*(?=[\s.:)(,]|$)", re.I)
FORM_TITLE = re.compile(r'^(?:PHIẾU|ĐƠN(?!\s+(?:VỊ|GIẢN)\b)|BÁO CÁO|BIÊN BẢN|HỢP ĐỒNG|GIẤY PHÉP|BẢNG KÊ)\b', re.I)
NOTE_HEADING = re.compile(r"^(?:\*\s*)?(?:Ghi chú|Chú thích|Notes|Hướng dẫn|Lưu ý)\s*:?$", re.I)
BIBLIOGRAPHY = re.compile(r"(?:DANH MỤC\s+)?TÀI LIỆU THAM KHẢO|^REFERENCES$", re.I)
DIGIT = re.compile(r"^(\d+)(?:[.)](?:\s+|(?=[^\W\d_]))|[-/]\s*(?=[^\d\s]))")
DECIMAL = re.compile(r"^\d+(?:\.\d+)+\.?\s+")
ALPHA = re.compile(r"^([a-zđ])[.)/](?:\s+|(?=[^\W\d_]))", re.I)
DASH = re.compile(r"^([-–—•])(?:\s+|(?=[^\W\d_]))")
SYMBOL = re.compile(r"^([-–—•+])(?:\s+(?=\S)|(?=[^\W\d_]))")
FOOTNOTE = re.compile(r"^(\d+)(?:\s+|[.)]\s+)\S")
BLANK = re.compile(r"\.{3,}|…|_{3,}|\[\s*(?:\.\.\.|…|[^]]+)\]|\(\d+\)")
LITERAL_INPUT_REGION = re.compile(r'\.{3,}|…|_{3,}|\(\d+\)|\[(?!\d+\])[^]]+\]')
INPUT = re.compile(r"^(?:Tên(?:\s+[^:]{1,65})?|Địa chỉ(?:\s+[^:]{1,65})?|Ngày|Người nộp|Đơn vị|Số(?: hiệu)?|Ký tên|Họ(?: và)? tên|Điện thoại|Fax|Email|Cơ quan|Tác giả|Nơi[^:]{0,40})\s*:", re.I)
INSTRUCTION = re.compile(r"\b(?:phải|ghi|điền|ký xác nhận|kê khai|khai báo|liệt kê|nêu (?:rõ|cụ thể)|được trình bày|trình bày theo|trang (?:bìa|đầu tiên|\d+)|quy cách|để trống)\b", re.I)
TEXTUAL = {"paragraph", "heading", "unknown", "form_field", "footnote", "note", "numbered_paragraph"}
DECLARATION = re.compile(
    r'^(?:Chúng tôi|Tôi|Doanh nghiệp|Thương nhân|Cơ quan|Đơn vị|Tổ chức)\s+'
    r'(?:xin\s+)?(?:cam kết|chịu trách nhiệm)\b', re.I)
SIGNATURE_COMPLETION = re.compile(r'^\(?\s*Ký\b.*(?:họ\s*tên|đóng\s*dấu)', re.I)


def scan(text):
    return unicodedata.normalize("NFC", text or "")


def form_boundary(block, active=False, *, completion_evidence=False):
    text, offsets = normalized_scan(block.get("text", ""))
    match = FORM_NUMBER.match(text)
    if match:
        if re.match(r"\s+(?:của|được|này|theo)\b", text[match.end():], re.I):
            return None  # A prose citation cannot start another form.
        references = re.match(r'(?:\[\d+\])+', text[match.end():])
        end = match.end() + (references.end() if references else 0)
        return {"number": block["text"][offsets[match.start(1)]:offsets[match.end(1)]], "end": offsets[end], "evidence": "explicit_form_number"}
    # A displayed heading can start a standalone form only before any active
    # form. Within a numbered form it is a title, not a new boundary.
    # These common compounds use "đơn" as an adjective/institutional noun,
    # rather than naming an application document.
    if not active and block.get("heading_evidence") and text.isupper() and FORM_TITLE.match(text):
        return {"number": None, "end": 0, "evidence": "standalone_form_heading"}
    principal, separator, qualifier = text.partition('(')
    if (not active and completion_evidence and (block.get('heading_evidence') or block.get('_alignment') == 'center') and separator and
            principal.strip().isupper() and len(text) <= 400 and qualifier.rstrip().endswith(')') and
            not BLANK.search(principal) and not ATTACHMENT_NOTE.match('(' + qualifier)):
        return {'number': None, 'end': 0, 'evidence': 'source_qualified_cover_with_completion_inputs'}
    return None


def semantic_body(node, match, kind, *, number=False):
    """Split structural label/body without changing characters or source order."""
    original = node.get("text", "")
    tail = slice_unit(node, match.end())
    result = {k: v for k, v in node.items() if k not in {"text", "annotations", "children", "candidate_role", "confidence"}}
    # Note lookahead may build lists it does not consume. Refinement must not
    # mutate the source candidate's child array during that speculative scan.
    result.update(type=kind, label=original[:match.end()].rstrip(), text=tail["text"],
                  children=list(node.get("children", [])))
    if tail['text'] and match.end() and not original[match.end() - 1].isspace():
        result['_joined_label_source'] = {'text': original, 'annotations': node.get('annotations')}
    result["number" if number else "marker"] = match[1]
    if tail.get("annotations"):
        result["annotations"] = tail["annotations"]
    label_annotations = [{**a, "end": min(a["end"], match.end())} for a in node.get("annotations", []) if a["start"] < match.end()]
    if label_annotations:
        result["label_annotations"] = label_annotations
    return result


def make_form(block, boundary):
    if block['type'] == 'table':
        header = container('form_header', block)
        header['children'] = [block]
        form = container('form', block)
        form.update(number=boundary['number'], title=None, children=[header],
                    boundary_evidence=boundary['evidence'])
        return form
    if not boundary["end"]:
        form = container("form", block)
        form.update(number=None, title=None, boundary_evidence=boundary["evidence"],
                    children=[{**block, "type": "paragraph" if boundary.get('header_first') else "form_title"}])
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


def table_form_boundary(node):
    """An explicit caption and attachment note in the first physical row."""
    if node['type'] != 'table':
        return None
    if '_template_caption_boundary' not in node:
        cells = node.get('cells', [])
        first_row = min((cell['row'] for cell in cells), default=None)
        header = [cell for cell in cells if cell['row'] == first_row]
        captions = []
        for cell in header:
            pending = list(cell.get('content', []))
            if not pending:
                pending = [{'text': cell.get('effective_text') or cell.get('text') or ''}]
            while pending:
                fragment = pending.pop()
                boundary = form_boundary(fragment)
                if boundary:
                    captions.append(boundary)
                pending.extend(fragment.get('children', []))
        # An attachment note can continue in the next physical header row.
        # This does not remove spacer cells or change any source geometry.
        band = header + [cell for cell in cells if cell['row'] == first_row + 1]
        text = ' '.join(cell.get('effective_text') or cell.get('text') or '' for cell in band)
        attached = re.search(r'\(\s*(?:Ban hành kèm theo|Kèm theo)\b', text, re.I)
        node['_template_caption_boundary'] = (
            {**captions[0], 'evidence': 'explicit_template_caption_in_source_header_table'}
            if attached and len(captions) == 1 else None)
    return node['_template_caption_boundary']


def consecutive(previous, following, style):
    if style == 'roman':
        a, b = roman_ordinal(previous), roman_ordinal(following)
        return a is not None and b is not None and b == a + 1
    if style == "digit":
        return int(following) == int(previous) + 1
    if style == "dash":
        return previous == following
    a, b = previous.casefold(), following.casefold()
    return any(a in alphabet and b in alphabet and alphabet.index(b) == alphabet.index(a) + 1
               for alphabet in ("abcdđeghiklmnopqrstuvxy", "abcdefghijklmnopqrstuvwxyz"))


def marker(node, pattern):
    return pattern.match(node.get("text") or "") if node["type"] in TEXTUAL else None


def symbol_marker(node):
    if node['type'] == 'footnote':
        # The note already owns a source counter. A dash in its explanatory
        # body cannot replace that label or merge independently numbered notes.
        return None
    match = marker(node, SYMBOL)
    # A sign followed only by numbers/operators is not a textual list item.
    return match if match and any(c.isalpha() for c in node["text"][match.end():]) else None


def same_flow(left, right):
    from vietnam_legal_rag.ingestion.semantics.hierarchy import source_key
    if source_key(left) >= source_key(right):
        return False
    return (left.get("_scope") == right.get("_scope") and
            left.get("_source_layout") == right.get("_source_layout"))


def topic_label(node, match, *, max_length=160, max_words=24):
    """Bounded heading-like text, including topic labels ending in a period."""
    body = scan(node["text"][match.end():]).strip()
    return (len(body) <= max_length and len(body.split()) <= max_words and
            not re.search(r"\b(?:phải|được|là|gồm|thực hiện|ghi|điền|must|shall|is|are)\b", body, re.I))


def symbol_run(children, start, parent=None):
    """Find a source-contiguous run before assigning any form-field roles.

    A dash starts a parent item; following plus markers are its sublist.
    Unmarked paragraphs need a heading/lead-in AND a following compatible
    marker. Adjacency alone cannot absorb the prose following a list.
    """
    first = symbol_marker(children[start])
    if not first:
        return start, []
    root_marker, current, current_match = first[1], children[start], first
    inline_topic_run = bool(re.match(
        r'[^:]{1,120}:\s+(?=[^\W\d_])', children[start]['text'][first.end():]))
    entries, marked, i = [], 0, start
    while i < len(children):
        node = children[i]
        following = children[i + 1] if i + 1 < len(children) else None
        peer = symbol_marker(following) if following else None
        if (marked >= 2 and node['type'] == 'table' and
                node.get('table_kind') in {'form', 'annex_form'} and
                current['text'].rstrip().endswith(':') and
                any(not cell['effective_text'] for cell in node['cells']) and
                peer and peer[1] == root_marker and same_flow(current, following)):
            # Geometry lacks paragraph flow metadata. Its colon prompt and
            # the next same-flow peer bound it; it cannot cross a counter or
            # bridge populated factual tables.
            entries.append((node, None)); i += 1; continue
        previous_flow = (current if i > start and children[i - 1]['type'] == 'table' and
                         entries and entries[-1][0] is children[i - 1] else children[i - 1])
        if i > start and not same_flow(previous_flow, node):
            break
        match = symbol_marker(node)
        if match:
            if match[1] != root_marker and not (root_marker != "+" and match[1] == "+"):
                break
            entries.append((node, match)); marked += 1
            current, current_match = node, match
            i += 1; continue
        if node.get("evidence") == "explicit_source_quotation" and current["text"].rstrip().endswith(":"):
            entries.append((node, None)); i += 1; continue
        # An explicit monetary equation is a continuation of its preceding
        # source marker, even when the marker ends in a comma. Ordinary prose
        # still needs a bounded lead-in and a following compatible marker.
        text = node.get('text') or ''
        calculation = (node['type'] == 'paragraph' and
                       re.match(r'^[\d.,]+\s+(?:đồng|VNĐ|VND|đ)\b', text, re.I) and
                       '=' in text and re.search(r'\s(?:x|×|\*|\+|:)\s', text))
        if calculation:
            entries.append((node, None)); i += 1; continue
        # No semantic boundary, emphasis or another numbering scheme may be
        # crossed while searching for a continuation's closing marker.
        end = i
        while end < len(children):
            following = children[end]
            from vietnam_legal_rag.ingestion.semantics.hierarchy import candidate
            boundary = candidate(following)
            if symbol_marker(following):
                break
            if (following["type"] != "paragraph" or following.get("heading_evidence") or
                    boundary and boundary['explicit'] or
                    re.match(r"^(?:\d+[.)]\s|\d+\.\d+|[a-zđ][.)]\s)", following.get("text") or "", re.I) or
                    NOTE_HEADING.fullmatch(scan(following.get("text"))) or
                    not same_flow(children[end - 1], following)):
                break
            end += 1
        next_match = symbol_marker(children[end]) if end < len(children) else None
        compatible = (next_match and same_flow(children[end - 1], children[end]) and
                      (next_match[1] == root_marker or root_marker != "+" and next_match[1] == "+"))
        nested = root_marker != "+" and (current_match[1] == "+" or next_match and next_match[1] == "+")
        plus_topics = current_match[1] == "+" and next_match and next_match[1] == "+"
        parent_lead_in = bool(marked == 1 and parent and parent.get('type') in {'numbered_paragraph', 'list_item', 'point', 'clause'} and
                              (parent.get('text') or parent.get('title') or '').rstrip().endswith(':'))
        lead_in = parent_lead_in or current["text"].rstrip().endswith(":") or (inline_topic_run and bool(re.match(
            r'[^:]{1,120}:\s+(?=[^\W\d_])', current['text'][current_match.end():])))
        if end == i or not compatible or not (lead_in or (nested or plus_topics) and topic_label(current, current_match)):
            break
        entries.extend((n, None) for n in children[i:end])
        i = end
    # A source-declared parent supports a solitary textual dash item. It
    # groups siblings under that parent, not prose under a preceding bullet.
    supported_single = marked == 1 and (bool(children[start].get('_source_parent_id')) or
        bool(parent and parent.get('type') in {'numbered_paragraph', 'list_item', 'point', 'clause'} and
             (parent.get('text') or parent.get('title') or '').rstrip().endswith(':')))
    return (i, entries) if marked >= 2 or supported_single else (start, [])


def symbol_list(entries, in_form=False):
    first, first_match = entries[0]
    listing = container("list", first)
    listing.update(list_kind="unordered", style="plus" if first_match[1] == "+" else "dash", numbering={})
    active, parent, sublist = None, None, None
    for node, match in entries:
        if not match:
            active["children"].append(node)
            continue
        item = semantic_body(node, match, "list_item")
        # Source-backed input prompts remain fields within a form's list item.
        # Inline completion commentary remains display text, not a fake input.
        classification = field_evidence(item["text"]) if in_form else None
        if classification and classification[0] == "input":
            field = slice_unit(node, match.end())
            field.update(type="form_field", field_name=None, value_text=None,
                         field_kind=classification[0], field_evidence=classification[1])
            placeholders(field)
            item.update(text=None, children=[field])
            item.pop("references", None)
            item.pop("annotations", None)
        for key in ("field_name", "field_kind", "field_evidence", "value_text", "placeholder_refs"):
            item.pop(key, None)
        if first_match[1] != "+" and match[1] == "+":
            if sublist is None:
                sublist = container("list", node)
                sublist.update(list_kind="unordered", style="plus", numbering={})
                parent["children"].append(sublist)
            sublist["children"].append(item)
        else:
            listing["children"].append(item)
            parent, sublist = item, None
        active = item
    return listing


def group_symbol_runs(children, in_form=False, parent=None):
    expanded = []
    for index, node in enumerate(children):
        text = node.get('text') or ''
        splits = []
        if node['type'] == 'paragraph' and SYMBOL.match(text):
            splits = [m.start(1) for m in re.finditer(r';\s+([-–—•+])\s+(?=\S)', text)]
        elif node['type'] == 'paragraph' and index + 1 < len(children) and symbol_marker(children[index + 1]):
            lead = re.search(r':\s+([-–—•+])\s+(?=\S)', text)
            if lead and same_flow(node, children[index + 1]):
                splits = [lead.start(1)]
        if splits:
            bounds = [0, *splits, len(text)]
            expanded.extend(slice_unit(node, start, end) for start, end in zip(bounds, bounds[1:]))
        else:
            expanded.append(node)
    children = expanded
    output, i = [], 0
    while i < len(children):
        end, entries = symbol_run(children, i, parent)
        if entries:
            output.append(symbol_list(entries, in_form)); i = end
        else:
            output.append(children[i]); i += 1
    return output


def group_runs(children, bibliography=False, in_form=False):
    children = group_symbol_runs(children, in_form)
    output, i = [], 0
    while i < len(children):
        node = children[i]
        if node["type"] not in {"paragraph", "heading", "unknown", "numbered_paragraph"}:
            output.append(node); i += 1; continue
        for pattern, style in ((DIGIT, "digit"), (ALPHA, "alpha")):
            first = marker(node, pattern)
            if first:
                break
        else:
            output.append(node); i += 1; continue
        run, previous, consumed = [], None, 0
        while i + consumed < len(children):
            item = children[i + consumed]
            if (style == 'alpha' and run and item['type'] == 'table' and
                    item.get('table_kind') in {'form', 'annex_form'} and
                    any(not cell['effective_text'] for cell in item['cells'])):
                # A fillable table is content of its source topic. It can
                # connect consecutive alphabetic peers, never invent them.
                run[-1][2].append(item)
                consumed += 1
                continue
            if item["type"] not in {"paragraph", "heading", "unknown", "numbered_paragraph"}:
                break
            match = marker(item, pattern)
            if not match or previous and not consecutive(previous, match[1], style):
                break
            run.append((item, match, [])); previous = match[1]
            consumed += 1
        if len(run) < 2 and not (bibliography and style == "digit"):
            output.append(node); i += 1; continue
        kind = "bibliography" if bibliography and style == "digit" else "list"
        listing = container(kind, node)
        listing.update(list_kind="unordered" if style == "dash" else "ordered", style="dash" if style == "dash" else style, numbering={})
        listing["children"] = []
        for n, m, continuation in run:
            item = semantic_body(n, m, "bibliography_entry" if kind == "bibliography" else "list_item", number=style == "digit")
            item['children'].extend(continuation)
            listing['children'].append(item)
        for item in listing["children"]:
            item.pop("field_kind", None)
        output.append(listing); i += consumed
    return output


def group_notes(children, *, in_form=False):
    def template_references(nodes):
        references = set()
        for item in nodes:
            references.update(re.findall(r'\((\d+)\)', item.get('text') or ''))
            references.update(template_references(item.get('children', [])))
            for cell in item.get('cells', []):
                references.update(re.findall(r'\((\d+)\)', cell.get('effective_text') or cell.get('text') or ''))
                references.update(template_references(cell.get('content', [])))
        return references

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
        parenthesized = re.compile(r'^\((\d+)\)\s*(?=\S)')
        while j + len(run) < len(children):
            item = children[j + len(run)]
            text = item.get('text') or ''
            parenthetical = parenthesized.match(text) if explicit or in_form else None
            match = (parenthetical or FOOTNOTE.match(text)) if item["type"] in TEXTUAL else None
            if not match or previous and int(match[1]) != int(previous) + 1:
                break
            # FOOTNOTE includes its first body character to require real text.
            prefix = parenthetical or re.match(r"^(\d+)(?:\s+|[.)]\s+)", text)
            run.append((item, prefix)); previous = match[1]
        supported = explicit or len(run) >= 2 and any(n.get("_note_style") or n["type"] == "footnote" for n, _ in run)
        if in_form and len(run) >= 2 and all(m[0].startswith('(') for _, m in run):
            # Parenthesized explanatory counters refer back to actual template
            # placeholders. Ordinary numbered inputs cannot provide this evidence.
            references = template_references(children[:i])
            bodies = [n['text'][m.end():] for n, m in run]
            supported |= ({m[1] for _, m in run} <= references and
                          any(INSTRUCTION.search(body) for body in bodies) and
                          not any(re.search(r'\.{3,}|…|_{3,}|\[[^]]*\]', body) for body in bodies))
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
                # Nested lists/continuations consume more source siblings than
                # the number of top-level list items.
                from vietnam_legal_rag.ingestion.semantics.hierarchy import source_key
                def end_key(item):
                    return max([source_key(item)] + [end_key(c) for c in item.get("children", [])])
                last = end_key(listing)
                count = sum(source_key(n) <= last for n in following)
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
    if re.fullmatch(r'(?:Xác nhận|Đề nghị)(?:\s+và\s+(?:xác nhận|đề nghị))?\s*:', body, re.I):
        return "instruction", "source_form_confirmation_leadin"
    # An ellipsis after comma/semicolon enumerates omitted prose, rather
    # than providing an input region. Other placeholders remain literal.
    blanks = any(not (re.fullmatch(r'\.{3,4}|…', found[0]) and
                          re.search(r'[,;]\s*$', body[:found.start()]))
                 for found in BLANK.finditer(body))
    if blanks or INPUT.match(body):
        return "input", "source_placeholder_or_input_label"
    if INSTRUCTION.search(body):
        return "instruction", "source_completion_instruction"
    if prefix and re.match(
            r'^[^:\n]{1,160}:\s*(?:đề nghị|yêu cầu|hãy)\s+'
            r'(?:đánh giá|ghi|điền|nêu|liệt kê|kê khai|báo cáo|trình bày)\b', body, re.I):
        return "instruction", "source_numbered_inline_completion_directive"
    if prefix and body.rstrip().endswith(":"):
        return "instruction", "numbered_form_data_request"
    if re.match(r'^(?:Chúng tôi|Tôi)\s+(?:xin\s+)?(?:cam kết|chịu trách nhiệm)\b', body, re.I) or prefix and re.search(r"\b(?:xin chịu trách nhiệm|cam kết)\b", body, re.I):
        return "display", "source_form_declaration"
    return None


def form_footer_table(node):
    """Actual signing layouts close topics; signature columns alone do not."""
    if node['type'] != 'table':
        return False
    if '_form_footer_boundary' not in node:
        from vietnam_legal_rag.ingestion.validation.extract import walk_content
        # Plain source cells need not have semantic child nodes. Their frozen
        # display text carries the same signing evidence as paragraph cells.
        texts = [text for cell in node.get('cells', [])
                 for text in [cell['effective_text'], *[n.get('text') or ''
                              for n in walk_content(cell.get('content', []))]]]
        def completion(text):
            return (SIGNATURE_COMPLETION.match(text) or
                    any(SIGNATURE_COMPLETION.match(m[0]) for m in re.finditer(r'\([^()]+\)', text)) or
                    re.search(r'\bChữ\s+ký\s*[,;]\s*(?:đóng\s*)?dấu\b', text, re.I))

        def signatory(text):
            prefix = text.split('(', 1)[0].strip()
            return (re.match(r'^(?:Người|Đại diện|Bên|Thủ trưởng)\b', prefix, re.I) or
                    closing_role({'text': prefix}) in {'signer_title', 'delegation_title'})

        nonempty = [t for t in texts if t.strip()]
        signature = any(completion(t) for t in nonempty)
        recipients = any(re.match(r'^Nơi nhận\s*:', t, re.I) for t in nonempty)
        signing_only = (not any(c.get('cell_type') == 'header' for c in node['cells']) and
                        any(signatory(t) and completion(t) for t in nonempty) and
                        all(signatory(t) or completion(t) or not any(c.isalpha() for c in t)
                            for t in nonempty))
        node['_form_footer_boundary'] = bool(signature and (recipients or signing_only))
    return node['_form_footer_boundary']


def form_input_table(node):
    """Actual empty source cells support table-input ownership, never a footer."""
    if node['type'] != 'table' or node.get('table_kind') not in {'form', 'annex_form'} or form_footer_table(node):
        return False
    if '_form_input_slots' not in node:
        node['_form_input_slots'] = any(not cell['effective_text'] for cell in node['cells'])
    return node['_form_input_slots']


def numbered_heading_before_letterhead(node, following):
    """An emphasized case label before a real letterhead is a source heading."""
    if (node['type'] not in {'paragraph', 'heading'} or not node.get('heading_evidence') or
            not marker(node, DIGIT) or re.search(r'\.{3,}|…|_{3,}', node.get('text') or '')):
        return False
    from vietnam_legal_rag.ingestion.semantics.hierarchy import NATIONAL_HEADING, NATIONAL_MOTTO
    from vietnam_legal_rag.ingestion.validation.extract import walk_content
    text = scan(' '.join(n.get('text') or '' for n in walk_content(following[:8])))
    return bool(re.search(NATIONAL_HEADING, text, re.I) and re.search(NATIONAL_MOTTO, text, re.I))


def form_global_boundary(node):
    """Global declarations and signing/recipient evidence close every local topic."""
    return bool(node['type'] in {'recipients', 'form_signature'} or form_footer_table(node) or
                node['type'] in TEXTUAL and DECLARATION.match(scan(node.get('text')).strip()))


def form_component_boundary(node):
    """Source scope evidence is independent of placeholder/field roles.

    Displayed uppercase numbered captions close local report counters even
    when their literal wording does not match a recognized form heading.
    A self-declaration remains global when it contains citation/date blanks.
    Neither case invents a heading or changes the source field's input role.
    """
    text = scan(node.get('text')).strip()
    if form_global_boundary(node):
        return True
    if node['type'] not in TEXTUAL:
        return False
    caption = (text.isupper() and (node.get('_alignment') == 'center' or node.get('heading_evidence')) and
               re.fullmatch(r'[^\W\d_][^\d:;.!?\n]{0,80}\s+\d+[A-ZĐ]?(?:\s*:\s*\S.*)?', text))
    return bool(caption)


def form_header_role(node):
    text = scan(node.get('text'))
    role = opening_role({**node, 'type': 'paragraph'})
    if text.isupper() and re.match(r'^TÊN (?:THƯƠNG NHÂN|DOANH NGHIỆP|CƠ QUAN|ĐƠN VỊ|TỔ CHỨC)\b', text):
        return 'issuing_authority'
    if text.isupper() and re.match(r'^CƠ QUAN\b', text) and ':' not in text and not LITERAL_INPUT_REGION.search(text):
        return 'issuing_authority'
    if re.match(r'^Số\s*:', text, re.I) or re.fullmatch(r'/[A-ZĐ0-9]+(?:[-/][A-ZĐ0-9]+)*', text):
        return 'document_number'
    if re.fullmatch(r'(?:.{0,80},\s*)?ngày.{0,30}tháng.{0,30}năm.{0,30}', text, re.I):
        return 'place_and_date'
    if re.fullmatch(r'[-–—_\s]+', text):
        return 'separator'
    return role


def group_recipients(children, *, in_form=False):
    output, recipients, recipient = [], None, None
    for node in children:
        text = scan(node.get("text"))
        recipient_prefix = re.match(r'^(?:Kính gửi|Sao kính gửi|Đồng kính gửi|Nơi nhận)\s*:', text, re.I)
        if (re.fullmatch(r"(?:Kính gửi|Sao kính gửi|Đồng kính gửi|Nơi nhận)\s*:?", text, re.I) or
                recipient_prefix):
            recipients = {**node, "type": "recipients"}
            if (in_form or node['type'] == 'form_field') and recipient_prefix and BLANK.search(text):
                field = {**node, 'type': 'form_field', 'field_kind': node.get('field_kind', 'input'),
                         'field_evidence': node.get('field_evidence', 'source_recipient_placeholder')}
                placeholders(field)
                recipients = container('recipients', node)
                recipients['children'].append(field)
            output.append(recipients); recipient = None
        elif recipients and (prefix := re.match(r"^([-–—•])\s*(?=\S)", node.get("text") or "")) and node["type"] in TEXTUAL:
            # Inline emphasis may join a dash and its body in effective text.
            # Only an explicit recipient heading permits the tight marker;
            # ordinary signed values/prose retain the whitespace requirement.
            if prefix.end() == 1:
                # Keep the tight source display intact: joining a separated
                # label/body would insert a space into physical effective_text.
                recipient = {**node, "type": "recipient", "marker": prefix[1]}
            else:
                recipient = semantic_body(node, prefix, "recipient")
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
    def boundary(node):
        return (form_component_boundary(node) or marker(node, DIGIT) or node['type'] == 'form_field' and node.get('number') or
                node['type'] in {'note', 'footnote_group', 'form_header', 'form_title',
                                 'form_subtitle', 'form_signature', 'recipients', 'form'} or
                node.get('evidence') == 'explicit_article_heading_in_source_template')

    # Only intervening inputs before another local alpha peer are part of
    # the run. A trailing total or other standalone input closes that run.
    alpha_ahead, following_alpha = [False] * len(children), False
    for index in range(len(children) - 1, -1, -1):
        alpha_ahead[index] = following_alpha
        if boundary(children[index]):
            following_alpha = False
        elif marker(children[index], ALPHA):
            following_alpha = True
    output, active, i = [], None, 0
    while i < len(children):
        node = children[i]
        match = marker(node, ALPHA)
        if form_component_boundary(node):
            active = None
        elif node["type"] == "form_field" and not match:
            active = node
        elif node['type'] == 'form_field' and match and not (
                active and (active.get('number') or (active.get('text') or '').rstrip().endswith(':'))):
            # An ordinary completed input is not a declared owner of the
            # next alphabetic field. Retain that field as a local peer.
            active = None
        elif marker(node, DIGIT):
            active = None  # An unclassified counter still closes the preceding field.
        elif (node["type"] in {"note", "footnote_group", "form_title", "form_subtitle", "form_header", "form_signature", "recipients"}
              or node.get('evidence') == 'explicit_article_heading_in_source_template'):
            active = None
        if match and active and (active.get('number') or (active.get('text') or '').rstrip().endswith(':')):
            end = i
            while end < len(children) and (end == i or not boundary(children[end])):
                if (end != i and children[end]['type'] == 'form_field' and
                        not marker(children[end], ALPHA) and not alpha_ahead[end]):
                    break
                end += 1
            marked = [(n, marker(n, ALPHA)) for n in children[i:end]]
            marked = [(n, m) for n, m in marked if m]
            sequential = len(marked) >= 2 and all(consecutive(a[1][1], b[1][1], "alpha") for a, b in zip(marked, marked[1:]))
            single_input = (len(marked) == 1 and active.get('field_kind') == 'composite' and
                            active.get('field_evidence') == 'source_numbered_input_component' and
                            BLANK.search(marked[0][0].get('text') or ''))
            if sequential or single_input:
                # Preserve the contiguous field's introductory content before
                # its subfields; never cross another numbered unit.
                position = next(j for j, n in enumerate(output) if n is active)
                active["children"].extend(output[position + 1:])
                del output[position + 1:]
                subfield = None
                for offset, item in enumerate(children[i:end], i):
                    found = marker(item, ALPHA)
                    if found:
                        subfield = semantic_body(item, found, "form_subfield")
                        classification = ((item['field_kind'], item['field_evidence'])
                                          if item['type'] == 'form_field' and item.get('field_kind') and
                                          item.get('field_evidence') else field_evidence(subfield["text"]))
                        following = children[offset + 1] if offset + 1 < end else None
                        if (not classification and re.fullmatch(r'[^:\n]{1,80}:\s*', subfield['text']) and
                                following and following['type'] == 'table' and
                                following.get('table_kind') in {'form', 'annex_form'} and
                                any(not cell['effective_text'] for cell in following['cells'])):
                            classification = ('composite', 'source_form_prompt_before_fillable_table')
                        if not classification and re.fullmatch(
                                r'[^:\n]{1,120}:\s*[+−-]?\d[\d.,]*\s*(?:đồng|đ|VNĐ|VND)'
                                r'(?:\s*\([^)]*\))?\.?', subfield['text'], re.I):
                            classification = ('display', 'source_literal_currency_value')
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


def candidate_template_article(node):
    from vietnam_legal_rag.ingestion.semantics.hierarchy import candidate
    marker = candidate(node) if node["type"] in TEXTUAL else None
    return marker and marker["explicit"] and marker["kind"] == "article" and node.get("heading_evidence")


def scope_form_decimal_fields(children, *, with_inputs=False):
    """Only literal prefix parents may own consecutive decimal form inputs.

    Annex numbering must not claim these counters. A missing parent or a
    nonsequential series remains available to the independent audit.
    """
    from vietnam_legal_rag.ingestion.refinement.semantic import number_candidate
    def source_counter(node):
        found = number_candidate(node)
        if found or node['type'] != 'form_field':
            return found, False
        # Preclassified decimal instructions still retain their literal
        # counter in text; already split fields retain it in their label.
        label = {**node, 'type': 'paragraph', 'text': (node.get('label') or '') + ' '}
        marked = number_candidate(label)
        if marked and marked[0][1] == node.get('number'):
            return marked, True
        return number_candidate({**node, 'type': 'paragraph'}), False
    output, index = [], 0
    while index < len(children):
        node = children[index]
        parent, existing_parent = source_counter(node)
        if existing_parent and node.get('field_kind') != 'instruction':
            parent = None
        end, marked = index + 1, []
        if parent and len(parent[1]) == 1:
            while end < len(children):
                found, existing_child = source_counter(children[end])
                if not found or len(found[1]) != 2 or found[1][:-1] != parent[1]:
                    break
                start = end
                end += 1
                if with_inputs:
                    while end < len(children) and not source_counter(children[end])[0]:
                        child = children[end]
                        if (child['type'] in {'form_signature', 'form_header', 'note', 'footnote', 'footnote_group'} or
                                child['type'] == 'table' and not form_input_table(child)
                                or child.get('field_kind') == 'display' or form_component_boundary(child)):
                            break
                        end += 1
                marked.append((children[start], found[0], found[1][-1], children[start + 1:end], existing_child))
        def has_input(nodes):
            return any(n.get('field_kind') in {'input', 'input_label', 'composite'} or form_input_table(n) or
                       has_input(n.get('children', [])) for n in nodes)
        supported = not with_inputs or all(has_input(m[3]) or m[0].get('field_kind') in {
            'input', 'input_label', 'instruction', 'composite'} for m in marked)
        if supported and len(marked) >= 2 and [m[2] for m in marked] == list(range(1, len(marked) + 1)):
            field = ({**node, 'children': list(node.get('children', []))} if existing_parent else
                     semantic_body(node, parent[0], 'form_field', number=True))
            field.update(field_kind='composite', field_evidence='source_decimal_subfield_sequence',
                         field_name=None, value_text=None)
            for child, match, _, dependents, existing_child in marked:
                subfield = ({**child, 'type': 'form_subfield', 'children': list(child.get('children', []))}
                            if existing_child else semantic_body(child, match, 'form_subfield', number=True))
                role, evidence = (('composite', 'source_numbered_input_component') if dependents else
                                  field_evidence(subfield['text']) or ('unknown', 'source_empty_numbered_form_input'))
                subfield.update(field_kind=role, field_evidence=evidence, field_name=None, value_text=None)
                subfield['children'].extend(dependents)
                field['children'].append(subfield)
            output.append(field); index = end
        else:
            output.append(node); index += 1
    return output


def scope_form_local_outline(children):
    """Consecutive Roman/uppercase-alpha topics bound local numeric restarts."""
    for root_pattern, root_kind in ((re.compile(r'^([IVXLCDM]+)[.)]\s+'), 'roman'),
                                    (re.compile(r'^([A-ZĐ])[.)]\s+'), 'alpha')):
        headings = [(i, root_pattern.match(n.get('text') or '')) for i, n in enumerate(children)
                    if n['type'] == 'paragraph' and root_pattern.match(n.get('text') or '')]
        restarts = [i + 1 < len(children) and
                    bool(children[i + 1].get('number') == '1' or
                         re.match(r'^1[.)]\s+', children[i + 1].get('text') or '')) for i, _ in headings]
        if (len(headings) >= 2 and all(consecutive(a[1][1], b[1][1], root_kind)
                                      for a, b in zip(headings, headings[1:])) and
                (all(restarts) if root_kind == 'alpha' else any(restarts))):
            break
    else:
        return children
    end = next((i for i in range(headings[0][0] + 1, len(children))
                if children[i]['type'] in {'form_signature', 'recipients', 'note', 'footnote_group', 'bibliography'} or
                form_global_boundary(children[i])), len(children))
    def counter(node):
        text = node.get('text') or ''
        for pattern, kind, level in ((root_pattern, root_kind, 10), (DIGIT, 'digit', 20), (ALPHA, 'alpha', 30)):
            found = pattern.match(text)
            if found:
                return {'number': found[1], 'kind': kind, 'level': level}, found
        return None
    root = container('layout_block', children[headings[0][0]])
    root['evidence'] = f'source_consecutive_{root_kind}_form_outline'
    stack = []
    for node in children[headings[0][0]:end]:
        if form_component_boundary(node):
            # A caption is outside the preceding numeric component. Keep
            # its Roman report topic; a global declaration closes all topics.
            if form_global_boundary(node):
                stack.clear()
            else:
                while stack and stack[-1][0] >= 20:
                    stack.pop()
        found = counter(node) if node['type'] in {'paragraph', 'heading', 'unknown'} else None
        field_counter = node['type'] == 'form_field' and (node.get('number') or '').isdigit()
        if found or field_counter:
            level = found[0]['level'] if found else 20
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else root
            if field_counter:
                parent['children'].append(node)
                stack.append((level, node))
                continue
            siblings = parent['children']
            listing = siblings[-1] if siblings and siblings[-1]['type'] == 'list' and siblings[-1].get('_form_level') == level else None
            if listing is None:
                listing = container('list', node)
                listing.update(list_kind='ordered', style='local_counter', numbering={},
                               evidence=root['evidence'], _form_level=level)
                siblings.append(listing)
            item = semantic_body(node, found[1], 'list_item', number=True)
            item['evidence'] = root['evidence']
            listing['children'].append(item)
            stack.append((level, item))
        else:
            (stack[-1][1] if stack else root)['children'].append(node)
    return [*children[:headings[0][0]], root, *children[end:]]


def scope_form_input_components(children):
    """Consecutive numbered topics may own actual source input fields.

    A bounded counter alone is insufficient: every topic needs actual input
    fields, a fillable table, or sequential colon prompts before its boundary.
    """
    children = scope_form_decimal_fields(children, with_inputs=True)
    headings = []
    for index, node in enumerate(children):
        if node['type'] == 'form_field' and (node.get('number') or '').isdigit():
            # A field already recognized from its table or input label is a
            # counter boundary, not a gap in the later topic sequence.
            headings.append((index, node, None))
            continue
        match = marker(node, DIGIT) if node['type'] == 'paragraph' else None
        body = (node.get('text') or '')[match.end():].strip() if match else ''
        terminal_ok = not re.search(r'[.;!?]$', body) or bool(node.get('heading_evidence') and body.endswith('.'))
        bounded_topic = (body and len(body) <= 400 and len(body.split()) <= 60 and
                         terminal_ok and not INSTRUCTION.search(body))
        if match:
            # Display topics also supply literal counter boundaries, but
            # their presence alone cannot assert an input-field role.
            headings.append((index, node, match if terminal_ok and
                             (topic_label(node, match) or bounded_topic) else None))
    numbers = [int(m[1] if m else n.get('number') or DIGIT.match(n['text'])[1]) for _, n, m in headings]
    if not headings or numbers != list(range(1, len(headings) + 1)):
        return children
    intervals = []
    for position, (start, node, match) in enumerate(headings):
        # A literal numbered colon request may already be an instruction.
        # Actual local input/table proof can make it a component without
        # stripping its source counter twice or borrowing later inputs.
        existing_request = (match is None and node['type'] == 'form_field' and
                            node.get('field_kind') == 'instruction' and
                            (node.get('text') or '').rstrip().endswith(':') and
                            len(node.get('text') or '') <= 400 and
                            not INSTRUCTION.search(node.get('text') or ''))
        if match is None and not existing_request:
            continue
        end = headings[position + 1][0] if position + 1 < len(headings) else len(children)
        end = next((i for i in range(start + 1, end) if children[i]['type'] in {
            'form_signature', 'form_header', 'note', 'footnote', 'footnote_group', 'bibliography'} or
            form_component_boundary(children[i]) or marker(children[i], DIGIT) or children[i]['type'] == 'form_field' and
            (children[i].get('number') or '').isdigit()), end)
        from vietnam_legal_rag.ingestion.validation.extract import walk_content
        inputs = [n for n in walk_content(children[start + 1:end]) if n['type'] in {'form_field', 'form_subfield'} and
                  n.get('field_kind') in {'input', 'input_label', 'composite'}]
        literal_alpha_inputs = any(n['type'] == 'paragraph' and marker(n, ALPHA) and
                                   BLANK.search(n.get('text') or '') for n in children[start + 1:end])
        fillable_tables = any(n['type'] == 'table' and n.get('table_kind') in {'form', 'annex_form'} and
                              any(not cell['effective_text'] for cell in n['cells'])
                              for n in walk_content(children[start + 1:end]))
        prompts = [m for n in children[start + 1:end]
                   if (m := marker(n, ALPHA)) and (n.get('text') or '').rstrip().endswith(':')]
        prompt_sequence = len(prompts) >= 2 and all(consecutive(a[1], b[1], 'alpha')
                                                    for a, b in zip(prompts, prompts[1:]))
        if not (inputs or literal_alpha_inputs or fillable_tables or prompt_sequence):
            continue
        if len(headings) == 1 and not fillable_tables:
            continue
        intervals.append((start, end, node, match))
    output, index = [], 0
    for start, end, node, match in intervals:
        output.extend(children[index:start])
        parent = (semantic_body(node, match, 'form_field', number=True) if match else
                  {**node, 'children': list(node.get('children', []))})
        parent.update(field_name=None, value_text=None, field_kind='composite',
                      field_evidence='source_numbered_input_component')
        refined = refine_subfields([parent, *children[start + 1:end]])
        parent['children'].extend(refined[1:])
        output.append(parent)
        index = end
    return [*output, *children[index:]]


def refine_form(form):
    bibliography = bool(BIBLIOGRAPHY.search(scan(form.get("title"))))
    children = scope_form_decimal_fields(group_symbol_runs(group_recipients(group_notes(form["children"], in_form=True), in_form=True), in_form=True))
    from vietnam_legal_rag.ingestion.semantics.hierarchy import candidate
    articles = [(node, marker) for node in children
                if node['type'] in TEXTUAL and (marker := candidate({**node, 'type': 'paragraph'})) and
                marker['explicit'] and marker['kind'] == 'article']
    article_sequence = (len(articles) >= 2 and [m['number'] for _, m in articles] ==
                        [str(i + 1) for i in range(len(articles))])
    template_articles = {id(node) for node, _ in articles} if article_sequence else set()
    output, header, signature = [], None, None
    title_phase, displayed = True, False
    for index, node in enumerate(children):
        text = node.get("text") or ""
        normalized = scan(text)
        following = children[index + 1] if index + 1 < len(children) else None
        if title_phase and node['type'] == 'form_header':
            header = node
            output.append(node)
            continue
        if numbered_heading_before_letterhead(node, children[index + 1:index + 9]):
            node.update(type='heading', evidence='source_numbered_form_heading_before_letterhead')
            output.append(node)
            title_phase, displayed, header, signature = True, False, None, None
            continue
        lines = text.splitlines(keepends=True)
        roles = [opening_role({'type': 'paragraph', 'text': line.strip()}) for line in lines]
        if (title_phase and len(lines) >= 2 and roles[0] == 'national_heading' and
                all(role == 'national_motto' or re.fullmatch(r'[-–—_\s]+', line)
                    for role, line in zip(roles[1:], lines[1:]))):
            compound = container('form_header', node)
            offset = 0
            for line, role in zip(lines, roles):
                part = slice_unit(node, offset, offset + len(line))
                part['type'] = role or 'paragraph'
                compound['children'].append(part)
                offset += len(line)
            output.append(compound)
            continue
        if node["type"] == "form_title":
            output.append(node); displayed = True; continue
        if title_phase and node["type"] == "table" and re.search(r"CỘNG H[ÒO][ÀA].*VIỆT NAM", scan(" ".join(c["effective_text"] for c in node["cells"])), re.I):
            output.append({**container("form_header", node), "children": [node]}); continue
        # Blank authority lines are official form header content when the next
        # source unit is the national heading. Their presence does not end the
        # displayed-title region or supply an authority identity.
        blank_authority = (re.fullmatch(r"[\s.…_]*(?:\(\d+\)[\s.…_]*)*", text) and BLANK.search(text) and
                           not re.fullmatch(r'[-–—_\s]+', text))
        header_following = following
        if title_phase and blank_authority:
            header_following = next((child for child in children[index + 1:]
                                     if child['type'] != 'separator' and not (
                                         re.fullmatch(r'[\s.…_]*(?:\(\d+\)[\s.…_]*)*', child.get('text') or '') and
                                         BLANK.search(child.get('text') or ''))), None)
        if title_phase and node['type'] != 'separator' and blank_authority and (header and not displayed or
                header_following and opening_role(header_following) == "national_heading"):
            if not header:
                header = container("form_header", node); output.append(header)
            node["type"] = "form_placeholder"; placeholders(node)
            header["children"].append(node); continue
        role = ('separator' if node['type'] == 'separator' else
                form_header_role(node) if text and node["type"] in TEXTUAL else None)
        # A split, mixed-case authority is supported by the immediately
        # following national heading/motto, rather than by a title whitelist.
        nearby = children[index + 1:index + 4]
        paired_header = any(opening_role(n) == 'national_heading' for n in nearby) and any(
            opening_role(n) == 'national_motto' for n in nearby)
        authority_words = (re.match(r'^(?:' + AUTHORITY + r'|Ban\b|Cơ quan\b|BTL\b)', text, re.I) or
                           normalized.isupper() and len(text.split()) >= 2)
        source_form_title = FORM_TITLE.match(text) or DOCUMENT_SET_TITLE.match(text)
        institutional_words = (role == 'issuing_authority' or
                               re.match(r'^(?:Cơ quan|Đơn vị|Ngân hàng|BTL)\b', text, re.I))
        if (title_phase and header and not displayed and node['type'] in TEXTUAL and role != 'separator' and
                normalized.isupper() and institutional_words and ':' not in text and
                LITERAL_INPUT_REGION.search(text) and not source_form_title):
            node.update(type='form_field', field_kind='input', field_evidence='source_header_placeholder')
            placeholders(node)
            header['children'].append(node)
            continue
        if (title_phase and paired_header and node['type'] in TEXTUAL and BLANK.search(text) and
                role not in {'document_number', 'place_and_date', 'national_heading', 'national_motto', 'separator'} and
                not source_form_title and (':' in text or not authority_words)):
            if not header:
                header = container('form_header', node); output.append(header)
            if re.fullmatch(r'[\s.…_]*(?:\(\d+\)[\s.…_\-–—]*)*', text):
                node['type'] = 'form_placeholder'
            else:
                node.update(type='form_field', field_kind='input', field_evidence='source_header_placeholder')
            placeholders(node); header['children'].append(node)
            continue
        if (title_phase and paired_header and node['type'] in TEXTUAL and len(text) <= 120 and
                authority_words and ':' not in text and not source_form_title and not candidate(node)):
            role = role or 'issuing_authority'
        if title_phase and role == 'separator':
            node['type'] = 'separator'
            (header['children'] if header else output).append(node)
            continue
        layout = node.get("_source_layout")
        displayed_title = bool(node['type'] in TEXTUAL and
                               (node.get('heading_evidence') or node.get('_alignment') == 'center') and
                               (not BLANK.search(text) or normalized.isupper() and
                                (FORM_TITLE.match(normalized) or DOCUMENT_SET_TITLE.match(normalized))))
        same_header_layout = bool(header and layout and not displayed_title and not candidate(node) and
                                  node['type'] == 'paragraph' and len(text) <= 120 and
                                  (normalized.isupper() or BLANK.search(text)) and
                                  any(c.get("_source_layout") == layout for c in header["children"]))
        if title_phase and (role in {"issuing_authority", "national_heading", "national_motto", "place_and_date", "document_number"} or re.match(r"^Số\s*:", normalized, re.I) or same_header_layout):
            if not header:
                header = container("form_header", node); output.append(header)
            node["type"] = "form_number" if role == "document_number" or re.match(r"^Số\s*:", normalized, re.I) else role or "paragraph"
            if not role and node["type"] == "paragraph" and BLANK.search(text):
                node.update(type="form_field", field_kind="input", field_evidence="source_header_placeholder")
            placeholders(node)
            header["children"].append(node); signature = None; continue
        header = None
        heading = bool(text and displayed_title and len(text) <= 400 and
                       not DIGIT.match(text) and not NOTE_HEADING.fullmatch(normalized))
        if title_phase and heading and node["type"] in TEXTUAL:
            node["type"] = "form_subtitle" if displayed else "form_title"
            bibliography |= bool(BIBLIOGRAPHY.search(normalized))
            displayed = True; output.append(node); continue
        if node["type"] not in {"annex_note", "separator"}:
            title_phase = False
        signature_role = closing_role({**node, "type": "paragraph"}) if text and node["type"] in TEXTUAL else None
        completion_signature = SIGNATURE_COMPLETION
        if (signature and node['type'] in TEXTUAL and completion_signature.match(text)):
            node.update(type='form_field', field_kind='instruction',
                        field_evidence='source_signature_completion_instruction', field_name=None, value_text=None)
            signature['children'].append(node)
            continue
        if (not signature_role and node['type'] in TEXTUAL and following and
                re.fullmatch(r'(?:Người|Đại diện)\s+[^\n:;.!?]{1,100}', text, re.I) and
                completion_signature.match(following.get('text') or '')):
            signature_role = 'signer_title'
        signing_prompt = re.fullmatch(r'(.+?)\s*\(\s*Ký\s+tên\s*,\s*đóng\s+dấu\s*\)', text, re.I)
        if signing_prompt and (closing_role({'text': signing_prompt[1].strip()}) == 'signer_title' or
                               signing_prompt[1].isupper() and re.match(r'^THỦ TRƯỞNG CƠ QUAN\b', signing_prompt[1])):
            signature_role = 'signer_title'
        if signature_role and signature_role != "recipients" or text and node.get("heading_evidence") and normalized.isupper() and re.match(r"^(?:NGƯỜI (?:NỘP|LẬP|YÊU CẦU)|ĐẠI DIỆN|BÊN (?:GIAO|NHẬN)|THỦ TRƯỞNG)\b", normalized):
            if not signature:
                signature = container("form_signature", node); output.append(signature)
            node["type"] = signature_role or "signer_title"
            if signature_role == "signature_marker":
                node["semantic"] = "signed"
            signature["children"].append(node); continue
        signature = None
        if candidate_template_article(node) or id(node) in template_articles:
            node.update(type="heading", evidence="explicit_article_heading_in_source_template")
            output.append(node); continue
        if node["type"] in TEXTUAL and text and not NOTE_HEADING.fullmatch(normalized):
            if node.get('field_evidence') == 'source_decimal_subfield_sequence':
                output.append(node); continue
            if bibliography and DIGIT.match(text):
                node["type"] = "paragraph"; node.pop("field_kind", None)
            elif re.fullmatch(r"[\s.…_]*(?:\(\d+\)[\s.…_]*)*", text) and BLANK.search(text):
                node["type"] = "form_placeholder"; placeholders(node)
            else:
                # Alphabetic markers are resolved against their preceding field
                # as a sequence, before considering independent input labels.
                evidence = field_evidence(text) if not ALPHA.match(text) else None
                if (ALPHA.match(text) and node['type'] == 'form_field' and
                        node.get('field_kind') and node.get('field_evidence')):
                    evidence = (node['field_kind'], node['field_evidence'])
                prefix = DIGIT.match(text)
                body = text[prefix.end():] if prefix else text
                if (not evidence and not prefix and text.rstrip().endswith(':') and
                        following and following['type'] == 'list' and following.get('children') and
                        all('□' in (n.get('text') or '') for n in following['children'])):
                    evidence = ('composite', 'source_checkbox_choice_list')
                    node['children'].append(following)
                    following['_form_component_owner'] = True
                if (not evidence and prefix and following and following["type"] == "table" and
                        not form_footer_table(following) and
                        topic_label(node, prefix, max_length=400, max_words=60)):
                    evidence = ("instruction", "short_numbered_form_component_before_table" if short_heading(body)
                                else "numbered_form_component_before_table")
                if not evidence and prefix and re.fullmatch(r"(?:Số điện thoại|Địa chỉ|Họ(?: và)? tên|Ngày|Tên [^:]{1,60})", scan(body), re.I):
                    evidence = ("input", "numbered_form_input_label")
                if not evidence and prefix and topic_label(node, prefix, max_length=400, max_words=60):
                    previous_field = next((n for n in reversed(output) if n.get('type') == 'form_field' and n.get('number')), None)
                    if (previous_field and previous_field['number'].isdigit() and
                            int(prefix[1]) == int(previous_field['number']) + 1):
                        evidence = ('instruction', 'source_numbered_form_component_sequence')
                from vietnam_legal_rag.ingestion.refinement.schema import FIELD_NAME, CONTINUATION
                if (not evidence and not prefix and re.fullmatch(r'[^:\n]{1,80}:\s*', text) and
                        not FIELD_NAME.fullmatch(normalized.rstrip(':').strip()) and
                        not CONTINUATION.match(normalized) and
                        not (node.get('heading_evidence') and normalized.isupper()) and
                        not re.search(r'\b(?:phải|đã|được|là|gồm|thực hiện|kiểm tra)\b|\bđề nghị\b(?!\s*:)', normalized, re.I) and
                        following and (following['type'] in TEXTUAL and field_evidence(following.get('text') or '') or
                                       not ALPHA.match(text) and following['type'] == 'table' and following.get('table_kind') in {'form', 'annex_form'} and
                                       any(not cell['effective_text'] for cell in following['cells']))):
                    # The explicit colon and following input confirm a prompt,
                    # while its unfamiliar field semantics remain unknown.
                    evidence = (('composite', 'source_form_prompt_before_fillable_table')
                                if following['type'] == 'table' else ('unknown', 'source_colon_prompt_before_form_input'))
                    if following['type'] == 'table':
                        node['children'].append(following)
                        following['_form_component_owner'] = True
                if evidence:
                    node = semantic_body(node, prefix, "form_field", number=True) if prefix else node
                    if not prefix and DASH.match(text):
                        node = semantic_body(node, DASH.match(text), "form_field")
                    node.update(type="form_field", field_kind=evidence[0], field_evidence=evidence[1]); placeholders(node)
                elif node["type"] == "form_field":
                    node["type"] = "paragraph"; node.pop("field_kind", None)
        if not node.pop('_form_component_owner', False):
            output.append(node)
    if any(n.get("evidence") == "explicit_article_heading_in_source_template" for n in output):
        from vietnam_legal_rag.ingestion.semantics.quotations import scope_template_counters
        output = scope_template_counters(output)
    form["children"] = group_runs(refine_subfields(scope_form_local_outline(scope_form_input_components(output))), bibliography=bibliography)
    if not form.get("title"):
        display = next((n for n in form["children"] if n["type"] == "form_title"), None)
        if display:
            form.update(title=display["text"], title_source_ref=display["source_ref"])


def scope_cell_compound_counters(content):
    from vietnam_legal_rag.ingestion.refinement.semantic import number_candidate
    output, prefixes = [], {}
    for node in content:
        marker = number_candidate(node)
        number = marker[0][1] if marker else node.get('number') if node['type'] == 'numbered_paragraph' else None
        prefix = number.rsplit('.', 1)[0] if number and '.' in number else None
        parent = prefixes.get(prefix) if prefix else None
        if parent:
            node.update(type='numbered_paragraph', number=number, parent_number=prefix,
                        evidence='source_compound_counter_in_same_table_cell')
            parent['children'].append(node)
        else:
            output.append(node)
            prefixes = {}
        if node['type'] == 'numbered_paragraph' and number:
            prefixes[number] = node
    return output


def refine_cells(node, in_form=False, in_cell=False):
    """Semanticize local sequences AFTER classification; effective text is frozen."""
    joined = node.get('_joined_label_source')
    if in_cell and joined and node.get('label') and node.get('text'):
        # An attached counter stays in the physical display text. Its number
        # remains structured without inserting a synthetic label/body space.
        node['text'] = joined['text']
        node.pop('label')
        node.pop('label_annotations', None)
        node.pop('annotations', None)
        if joined['annotations']:
            node['annotations'] = joined['annotations']
    in_form |= node["type"] == "form"
    for cell in node.get("cells", []):
        before = cell["effective_text"]
        content = cell.get("content", [])
        if content:
            cell["content"] = group_runs(group_recipients(group_notes(content), in_form=in_form), in_form=in_form)
            if not in_form:
                from vietnam_legal_rag.ingestion.semantics.quotations import scope_alpha_continuations
                cell['content'] = scope_alpha_continuations(cell['content'], counter_kind='digit')
            counter_count = sum(bool(DIGIT.match(n.get('text') or '')) for n in cell['content'] if n['type'] == 'paragraph')
            for child in cell["content"]:
                # Decimal labels may occupy a single physical cell or precede
                # unmarked continuation text. They are local source counters;
                # no hierarchy or relationship across cells is asserted.
                from vietnam_legal_rag.ingestion.refinement.semantic import number_candidate
                decimal = number_candidate(child) if child['type'] == 'paragraph' and not in_form else None
                if decimal and len(decimal[1]) > 1 and decimal[0][2] == '.':
                    child.update(type='numbered_paragraph', number=decimal[0][1],
                                 evidence='source_decimal_counter_in_table_cell')
                counter = DIGIT.match(child.get('text') or '') if child['type'] == 'paragraph' and not in_form else None
                if counter_count == 1 and counter and any(c.isalpha() for c in child['text'][counter.end():]):
                    child.update(type='numbered_paragraph', number=counter[1], evidence='source_counter_in_table_cell')
                if in_form and child["type"] in TEXTUAL:
                    placeholders(child)
                refine_cells(child, in_form, True)
            if not in_form:
                cell['content'] = scope_cell_compound_counters(cell['content'])
            from vietnam_legal_rag.ingestion.semantics.tables import effective_cell_text
            assert effective_cell_text(cell)[1] == before, "Cell semantic refinement changed effective text"
    for child in node.get("children", []):
        refine_cells(child, in_form, in_cell)


def refine_annex_titles(node):
    siblings = node.get("children", [])
    candidates = [n for n in siblings if n["type"] == "numbered_item" and short_heading(n.get("text")) and n.get("children")]
    for child in siblings:
        if (child['type'] == 'list_item' and re.fullmatch(r'[IVXLCDM]+|[A-ZĐ]', child.get('number') or '') and
                child.get('evidence') in {'emphasized_roman_body_outline', 'source_roman_outline_with_restarted_numeric_children',
                                         'source_article_free_alpha_outline'}):
            for fragment in child.get('children', []):
                text = fragment.get('text') or ''
                if (fragment['type'] != 'paragraph' or not fragment.get('heading_evidence') or
                        not text.isupper() or len(text) > 600 or not same_flow(child, fragment)):
                    break
                fragment.update(type='heading', evidence='source_local_outline_title_continuation')
        text = child.get("text")
        if child["type"] == "numbered_item" and short_heading(text) and child.get("children") and (child.get("heading_evidence") or len(candidates) >= 2):
            child.update(title=text, text="", title_evidence="short_heading_with_dependent_content")
            if child.get("annotations"):
                child["title_annotations"] = child.pop("annotations")
        refine_annex_titles(child)


def scope_form_explanations(children):
    """Keep referenced column explanations outside a form's input scope.

    Require an explicit explanation heading followed by a parenthesized source
    reference. These references need not be consecutive footnotes. A following
    numbered or semantic heading closes the note without inventing its end.
    """
    from vietnam_legal_rag.ingestion.semantics.hierarchy import candidate
    output, index = [], 0
    while index < len(children):
        node = children[index]
        following = children[index + 1] if index + 1 < len(children) else None
        supported = (node['type'] in TEXTUAL and
                     re.fullmatch(r'Giải thích\s*:', scan(node.get('text')), re.I) and
                     following and re.match(r'^\(\d+\)\s+\S', following.get('text') or ''))
        if not supported:
            output.append(node); index += 1; continue
        note = {**node, 'type': 'note', 'evidence': 'source_referenced_form_explanations',
                'children': list(node.get('children', []))}
        for key in ('field_name', 'field_kind', 'field_evidence', 'value_text', 'placeholder_refs'):
            note.pop(key, None)
        end = index + 1
        while end < len(children):
            child = children[end]
            text = child.get('text') or ''
            heading = candidate(child) if child['type'] in TEXTUAL else None
            if (child['type'] not in TEXTUAL or child.get('heading_evidence') or
                    heading or NOTE_HEADING.fullmatch(scan(text)) or
                    re.match(r'^[IVXLCDM]+[.)]\s+', text)):
                break
            note['children'].append(child)
            end += 1
        output.append(note); index = end
    return output


def refine_forms(document):
    def visit(node, in_form=False, in_note=False):
        in_form = (in_form or node['type'] == 'form') and node['type'] not in {'note', 'footnote', 'footnote_group'}
        in_note = in_note or node['type'] in {'note', 'footnote', 'footnote_group'}
        if in_form:
            node['children'] = scope_form_explanations(node.get('children', []))
        if node.pop("_footnote_scope", False):
            node["type"] = "footnote_group"
            for item in node["children"]:
                item.update(type="footnote", marker=str(item["ordinal"]))
        if node["type"] == "form":
            refine_form(node)
        elif node["type"] not in {"note", "footnote_group"}:
            node["children"] = group_notes(node.get("children", []))
        if in_note:
            node['children'] = group_symbol_runs(node.get('children', []), parent=node)
        if node["type"] == "footnote":
            # A source footnote may quote an amended provision without quote
            # punctuation. Its counters stay local to the actual note scope.
            from vietnam_legal_rag.ingestion.semantics.hierarchy import candidate
            from vietnam_legal_rag.ingestion.semantics.quotations import quotation, quoted_marker
            children = node.get("children", [])
            start = next((i for i, child in enumerate(children)
                          if (found := quoted_marker(child)) and found[0]["explicit"] and found[0]["kind"] == "article"), None)
            if start is not None and any((m := candidate(child)) and not m["explicit"]
                                         and m["kind"] == "clause" for child in children[start + 1:]):
                node["children"] = children[:start] + [quotation(children[start:], "source_footnote_provision_excerpt")]
            elif node.get('evidence') == 'source_linked_footnote_anchor' and (node.get('text') or '').rstrip().endswith(':'):
                node['children'] = group_runs(children)
        for child in node.get("children", []):
            visit(child, in_form, in_note)
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
    anchors = root.find('a')
    for listing in root.find('ol'):
        items = [n for n in listing.children if isinstance(n, Node) and n.tag == 'li']
        markers = [re.fullmatch(r'(?:id_)?footnote-(\d+)', n.attrs.get('id', '')) for n in items]
        parent = parents.get(id(listing))
        siblings = [n for n in parent.children if isinstance(n, Node)] if parent else []
        try:
            start = int(listing.attrs.get('start', '1'))
        except ValueError:
            continue
        if (not items or not all(markers) or not siblings or siblings[-1] is not listing or
                [int(m[1]) for m in markers] != list(range(start, start + len(items)))):
            continue
        # Both forward references and matching return links establish a
        # terminal note list; an ordinary numbered list cannot supply them.
        if all(any(a.attrs.get('href') == '#footnote-' + m[1] for a in anchors) and
               any(a.attrs.get('href') == '#footnote-ref-' + m[1] for a in item.find('a'))
               for item, m in zip(items, markers)):
            listing.attrs['_extract_footnote_scope'] = True
            listing.attrs['_extract_document_note_scope'] = True
    excluded = set()
    for node in root.find():
        if node.tag == 'table' and not any(isinstance(c, Node) or c.strip() for c in node.children):
            quality.ignore(node, 'empty_source_table')
            excluded.add(node.dom_order)
        if node.tag == "svg" and any("ant-empty-image" in p.attrs.get("class", "").split() for p in (parents.get(id(node)),) if p):
            quality.ignore(node, "empty_state_interface_graphic")
            excluded.add(node.dom_order)
        if node.tag == "title" and not any(node in svg.find() for svg in root.find("svg")):
            # Legacy fragments embed document metadata inside the preview body.
            # A title element is browser metadata, not displayed legal text.
            quality.ignore(node, "embedded_document_metadata")
            excluded.add(node.dom_order)
        # These controls annotate the rendered provision. Their buttons and
        # icons are interface content, while the sibling legal text remains.
        if node.tag == "button" and "ant-btn" in (node.attrs.get("class") or "").split():
            parent = parents.get(id(node))
            while parent:
                if parent.attrs.get("data-provision-highlighted") == "true":
                    quality.ignore(node, "navigation_artifact")
                    excluded.add(node.dom_order)
                    break
                parent = parents.get(id(parent))
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
            boundary = footer_list
            if (parent and parent.tag == 'section' and
                    'footnotes' in parent.attrs.get('class', '').split() and
                    'footnotes-list' in footer_list.attrs.get('class', '').split()):
                # Modern HTML wraps the terminal list in an explicitly marked
                # note section; its source separator is outside that wrapper.
                boundary, parent = parent, parents.get(id(parent))
            blocks = [c for c in parent.children if isinstance(c, Node)] if parent else []
            position = next((i for i, c in enumerate(blocks) if c is boundary), -1)
            terminal = position == len(blocks) - 1 and any(c.tag == "hr" for c in blocks[:position])
            if terminal:
                footer_list.attrs["_extract_footnote_scope"] = True
                if boundary is not footer_list:
                    footer_list.attrs['_extract_document_note_scope'] = True
        if linked or terminal:
            quality.ignore(node, "navigation_artifact"); excluded.add(node.dom_order)
    return excluded
