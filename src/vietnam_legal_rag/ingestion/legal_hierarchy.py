"""Deterministic document phases and a legal hierarchy stack, independent of DOM nesting.

Patterns only produce candidates. Document phase, current legal parents, list
scope, preceding prose and adjacent headings decide how candidates are used.
Private evidence keys exist only during parsing and are never serialized.
"""
from __future__ import annotations

from copy import deepcopy
import re
import unicodedata

LEVELS = {"part": 10, "chapter": 20, "section": 30, "subsection": 40,
          "article": 50, "clause": 60, "point": 70}
LEGAL_LABELS = {"phần": "part", "chương": "chapter", "mục": "section",
                "tiểu mục": "subsection", "điều": "article", "khoản": "clause", "điểm": "point",
                "part": "part", "chapter": "chapter", "section": "section", "subsection": "subsection",
                "article": "article", "clause": "clause", "point": "point"}
TEXT_TYPES = {"paragraph", "heading", "unknown"}
DOCUMENT_TYPES = r"THÔNG TƯ LIÊN TỊCH|THÔNG TƯ|BỘ LUẬT|LUẬT|NGHỊ ĐỊNH|NGHỊ QUYẾT|QUYẾT ĐỊNH|CHỈ THỊ|PHÁP LỆNH|LỆNH|JOINT CIRCULAR|CIRCULAR|LAW|DECREE|RESOLUTION|DECISION|DIRECTIVE|ORDINANCE"
AUTHORITY = r"(?:BỘ(?: TRƯỞNG)?\b|ỦY BAN\b|UỶ BAN\b|CHÍNH PHỦ\b|QUỐC HỘI\b|HỘI ĐỒNG\b|TỔNG CỤC\b|CỤC\b|SỞ\b|TÒA ÁN\b|TOÀ ÁN\b|VIỆN KIỂM SÁT\b|THỦ TƯỚNG\b|CHỦ TỊCH\b)"
SIGNER_TITLE = r"(?:THỨ TRƯỞNG|BỘ TRƯỞNG(?: .+)?|CHỦ TỊCH|PHÓ CHỦ TỊCH|GIÁM ĐỐC|PHÓ GIÁM ĐỐC|TỔNG GIÁM ĐỐC|TỔNG CỤC TRƯỞNG|CỤC TRƯỞNG|CHÁNH ÁN|VIỆN TRƯỞNG|THỦ TƯỚNG(?: CHÍNH PHỦ)?|PHÓ THỦ TƯỚNG(?: CHÍNH PHỦ)?)"


def source_key(node):
    return node["order"], node.get("source_offset", 0)


def container(kind, first=None, ref=None):
    ref = ref or first["source_ref"]
    return {"type": kind, "order": ref["dom_order"], "source_ref": ref, "children": []}


def normalized_scan(text):
    """Normalize only the matching view; offsets always address original Unicode."""
    scan, offsets, i = "", [0], 0
    while i < len(text):
        end = i + 1
        while end < len(text) and unicodedata.combining(text[end]):
            end += 1
        normalized = unicodedata.normalize("NFC", text[i:end])
        scan += normalized
        offsets.extend([end] * len(normalized))
        i = end
    return scan, offsets


def candidate(block):
    if block["type"] not in TEXT_TYPES:
        return None
    text = block.get("text", "")
    scan, offsets = normalized_scan(text)
    match = re.match(r"^(Tiểu mục|Phần|Chương|Mục|Điều|Khoản|Điểm|Subsection|Part|Chapter|Section|Article|Clause|Point)\s+"
                     r"((?:thứ[ \t]+(?:nhất|hai|ba|tư|bốn|năm|sáu|bảy|tám|chín|mười|\d+)"
                     r"(?:[ \t]+(?:mươi|mốt|một|hai|ba|tư|bốn|năm|lăm|sáu|bảy|tám|chín))*)"
                     r"|[IVXLCDM]+|\d+[a-zđ]?|[a-zđ])(?=[\s.:)]|\[\d+\]|$)", scan, re.I)
    if match:
        end = offsets[match.end()]
        rest = text[end:]
        # A leading citation such as "Điều 5 của Luật ..." is not a heading.
        if rest.strip() and not re.match(r"^[ \t]*[.:)\n]", rest) and not block.get("heading_evidence"):
            if re.match(r"\s*(?:của|tại|quy định|được|và|có|này|of|in|under|provides|shall|is|and)\b", rest, re.I):
                return None
        return {"kind": LEGAL_LABELS[match[1].casefold()],
                "number": text[offsets[match.start(2)]:offsets[match.end(2)]],
                "label_end": end, "explicit": True}
    match = re.match(r"^(\d+[a-zđ]?)([.)]|[-/]\s+(?=[^\d\s]))(?:\s+|(?=[^\d\s])|$)", scan, re.I)
    if match:
        return {"kind": "clause", "number": text[offsets[match.start(1)]:offsets[match.end(1)]],
                "label_end": offsets[match.end(2)], "explicit": False}
    match = re.match(r"^([a-zđ])([).]\s*|/\s+)", scan, re.I)
    if match:
        return {"kind": "point", "number": text[offsets[match.start(1)]:offsets[match.end(1)]],
                "label_end": offsets[match.end(2)], "explicit": False}
    return None


def short_heading(text):
    return bool(text and len(text) <= 120 and len(text.split()) <= 16 and
                not re.search(r"[;:.!?]", text) and "\n" not in text)


def opening_role(block):
    text = unicodedata.normalize("NFC", block.get("text", ""))
    if re.match(r"^(?:Căn cứ|Pursuant to)\s", text, re.I):
        return "legal_basis"
    if re.match(r"^(?:Xét\s|Theo\s+(?:đề nghị|kiến nghị))", text, re.I):
        return "proposal_basis"
    if re.fullmatch(DOCUMENT_TYPES, text, re.I):
        return "document_type_heading"
    if re.match(r"^(?:" + DOCUMENT_TYPES + r")\s+\S", text):
        return "document_type_heading"  # A combined type/title candidate, split in pass two.
    if re.fullmatch(r"CỘNG H[ÒO][ÀA] XÃ HỘI CHỦ NGHĨA VIỆT NAM", text, re.I):
        return "national_heading"
    if re.fullmatch(r"Độc lập\s*[-–—]\s*Tự do\s*[-–—]\s*Hạnh phúc", text, re.I):
        return "national_motto"
    if re.match(r"^Số\s*:\s*\S", text, re.I):
        return "document_number"
    if re.fullmatch(r".+,\s*ngày\s+\d+\s+tháng\s+\d+\s+năm\s+\d{4}\s*", text, re.I):
        return "place_and_date"
    if re.match(AUTHORITY, text) and text.isupper():
        return "issuing_authority"
    return None


def closing_role(block):
    text = unicodedata.normalize("NFC", block.get("text", ""))
    if re.match(r"^Nơi nhận\s*:", text, re.I):
        return "recipients"
    if re.match(r"^(?:TM|KT|TL|TUQ|Q)(?:\.\s*|/\s*(?=" + AUTHORITY + r"))", text):
        return "delegation_title"
    if re.fullmatch(SIGNER_TITLE, text):
        return "signer_title"
    if re.fullmatch(r"\(?\s*(?:Đã ký|đã ký|Ký tên|đã ký và đóng dấu)\s*\)?", text):
        return "signature_status"
    if re.fullmatch(r"\[\s*daky\s*\]", text, re.I):
        return "signature_marker"
    return None


def is_formula(block):
    text = unicodedata.normalize("NFC", block.get("text", ""))
    return bool(re.fullmatch(r"(?:QUYẾT ĐỊNH|NGHỊ ĐỊNH|NGHỊ QUYẾT|QUYẾT NGHỊ|BAN HÀNH)\s*:", text, re.I) or
                re.fullmatch(r"(?:QUYẾT NGHỊ|BAN HÀNH)", text, re.I) or
                re.match(r"^(?:Chính\s*phủ|Bộ\s*trưởng\s+Bộ.{0,160}?|[ỦU]y\s*ban.{0,160}?)\s+ban\s+hành\s+(?:" +
                         DOCUMENT_TYPES + r")\b", text, re.I))


def slice_unit(block, start, end=None):
    """Split a source unit without rewriting text, links or notation offsets."""
    end = len(block["text"]) if end is None else end
    text = block["text"][start:end]
    leading = len(text) - len(text.lstrip())
    start += leading
    text = text.strip()
    unit = {k: deepcopy(v) for k, v in block.items() if k not in {"children", "annotations", "_title_block", "number", "title", "ordinal", "candidate_role", "candidate_evidence", "confidence", "parent_status"}}
    unit.update(type="paragraph", text=text, children=[])
    unit["source_offset"] = block.get("source_offset", 0) + start
    annotations = []
    for annotation in block.get("annotations", []):
        left, right = max(annotation["start"], start), min(annotation["end"], start + len(text))
        if left < right:
            annotations.append({**annotation, "start": left - start, "end": right - start})
    if annotations:
        unit["annotations"] = annotations
    return unit


def logical_blocks(elements):
    """Unwrap presentation tables and split explicit line breaks in their cells."""
    for block in elements:
        if block.get("evidence") in {"source_signature_block", "source_addressee_block"}:
            yield block
            continue
        if block["type"] == "layout_block" and block.get("source_layout"):
            for child in logical_blocks(block["children"]):
                child["_source_layout"] = block["source_layout"]
                if child["type"] in TEXT_TYPES and "\n" in child.get("text", ""):
                    offset = 0
                    for line in child["text"].splitlines(keepends=True):
                        if line.strip():
                            yield slice_unit(child, offset, offset + len(line))
                        offset += len(line)
                else:
                    yield child
        else:
            yield block


def coalesce(elements):
    from .semantic_refinement import annex_candidate
    """Merge only adjacent bare headings with independently supported titles."""
    result, i = [], 0
    while i < len(elements):
        block = elements[i]
        marker = candidate(block)
        if marker and marker["explicit"] and marker["kind"] not in {"clause", "point"}:
            tail = block["text"][marker["label_end"]:].strip(" .:)\n")
            following = elements[i + 1] if i + 1 < len(elements) else None
            after = candidate(elements[i + 2]) if i + 2 < len(elements) else None
            if not tail and following and following["type"] in TEXT_TYPES:
                title = following.get("text", "")
                same_scope = block.get("_scope") is not None and block.get("_scope") == following.get("_scope")
                typography = (following.get("heading_evidence") or
                              block.get("_alignment") == following.get("_alignment") == "center")
                structural = (marker["kind"] != "article" and title.isupper() or
                              marker["kind"] == "article" and after and after["kind"] == "clause")
                boundary = candidate(following) or annex_candidate(following) or opening_role(following) or closing_role(following) or is_formula(following)
                if same_scope and source_key(block) < source_key(following) and short_heading(title) and not boundary and (typography or structural):
                    block["_title_block"] = following
                    i += 1
        result.append(block)
        i += 1
    return result


def legal_node(block, marker, following=None):
    kind, end = marker["kind"], marker["label_end"]
    text = block["text"]
    tail_start = end
    if marker["explicit"]:
        punctuation = re.match(r"[ \t]*[.:)]?(?:[-–—])?", text[end:])[0]
        tail_start += len(punctuation)
    else:
        punctuation = ""
    tail = text[tail_start:].strip()
    node = {k: v for k, v in block.items() if k not in {"text", "annotations", "_title_block"}}
    node.update(type=kind, number=marker["number"], label=text[:end], title=None,
                children=[], evidence="explicit_label" if marker["explicit"] else "source_counter_in_legal_context")
    if punctuation.strip():
        node["label_suffix"] = punctuation.strip()
    if block.get("annotations"):
        label_annotations = slice_unit(block, 0, end).get("annotations")
        if label_annotations:
            node["label_annotations"] = label_annotations
    title_block = block.get("_title_block")
    next_marker = candidate(following) if following else None
    title_evidence = (block.get("heading_evidence") or kind in {"part", "chapter", "section", "subsection"} or
                      next_marker and next_marker["kind"] in {"clause", "point"})
    if title_block:
        node["title"] = title_block["text"]
        node["title_source_ref"] = title_block["source_ref"]
        node["title_source_offset"] = title_block.get("source_offset", 0)
        node["source_refs"] = [block["source_ref"], title_block["source_ref"]]
        node["title_evidence"] = "adjacent_heading"
        if title_block.get("annotations"):
            node["title_annotations"] = title_block["annotations"]
        if title_block.get("references"):
            node.setdefault("references", []).extend(title_block["references"])
    elif kind not in {"clause", "point"} and tail and short_heading(tail) and title_evidence:
        node["title"] = tail
        node["_title_offset"] = block.get("source_offset", 0) + tail_start + len(text[tail_start:]) - len(text[tail_start:].lstrip())
        node["title_evidence"] = "heading_markup" if block.get("heading_evidence") else "adjacent_legal_structure"
        title_annotations = slice_unit(block, tail_start).get("annotations")
        if title_annotations:
            node["title_annotations"] = title_annotations
    elif tail:
        paragraph = slice_unit(block, tail_start)
        paragraph.pop("heading_evidence", None)
        node["children"].append(paragraph)
    return node


class BodyParser:
    def __init__(self, children, quality, active=(), list_context=False):
        self.children, self.quality = children, quality
        self.stack = list(active)
        self.previous = None
        self.seen_numbers = set()
        self.list_context = list_context
        self.generic_parent = None
        self.generic_child = None
        self.generic_numbers = {}

    def append(self, block, following=None):
        if block.get('evidence') in {'closing_before_attached_legal_act', 'attached_legal_act_header'}:
            self.stack = []
            self.generic_parent = self.generic_child = None
            self.generic_numbers = {}
            if block['evidence'] == 'attached_legal_act_header':
                self.seen_numbers = set()
            self.children.append(block)
            self.previous = block
            return
        marker = candidate(block)
        active = {kind for kind, node in self.stack if node.get("parent_status") != "unresolved"}
        decimal = re.match(r"^(\d+(?:\.\d+)+)[.)]\s*(?=[^\d\s])", block.get("text") or "") if block["type"] in TEXT_TYPES and 'article' not in active else None
        if decimal:
            block.update(type='numbered_paragraph', number=decimal[1], evidence='explicit_decimal_counter_outside_article_scope')
            parent = self.generic_numbers.get(decimal[1].rsplit('.', 1)[0])
            if parent:
                parent['children'].append(block)
            else:
                (self.stack[-1][1]['children'] if self.stack else self.children).append(block)
                self.quality.add('unresolved_decimal_prefix', 'Explicit decimal counter has no source prefix parent in this body scope', block['source_ref'])
            self.generic_numbers[decimal[1]] = block
            self.generic_parent, self.generic_child = parent, block
            self.previous = block
            return
        if marker and marker["kind"] == "point" and not marker["explicit"] and not any(
                k in {"article", "clause"} for k, _ in self.stack):
            block.update(type="numbered_paragraph", number=marker["number"],
                         evidence="source_counter_outside_article_scope")
            marker = None
        if marker and marker["kind"] == "clause" and not marker["explicit"]:
            # Decimal amounts do not match the candidate pattern. Lists introduced
            # by prose inside a legal unit retain their list meaning when uncertain.
            introduced_list = self.previous and (self.previous.get("text", "").endswith(":") or
                                                  self.previous.get("type") == "numbered_paragraph")
            nested_counter = self.list_context and "clause" in active
            if "article" not in active or introduced_list or nested_counter:
                block.update(type="numbered_paragraph", number=marker["number"])
                if "article" in active:
                    previous_clause = next((n for k, n in reversed(self.stack) if k == "clause"), None)
                    sequential = bool(previous_clause and previous_clause["number"].isdigit() and marker["number"].isdigit() and
                                      int(marker["number"]) == int(previous_clause["number"]) + 1)
                    block.update(candidate_role="clause", confidence=0.6 if sequential else 0.4)
                    self.quality.add("ambiguous_clause_candidate", "Numbered content lacks sufficient clause evidence in this list/prose context", block["source_ref"])
                marker = None
        if marker:
            self.generic_parent = self.generic_child = None
            self.generic_numbers = {}
            kind = marker["kind"]
            while self.stack and LEVELS[self.stack[-1][0]] >= LEVELS[kind]:
                self.stack.pop()
            active = {k for k, n in self.stack if n.get("parent_status") != "unresolved"}
            node = legal_node(block, marker, following)
            required = "article" if kind == "clause" else "clause" if kind == "point" else None
            if required and required not in active:
                node["parent_status"] = "unresolved"
                self.quality.add(f"orphan_{kind}", f"Source {kind} has no valid {required} parent; no parent invented", node["source_ref"])
            parent = self.stack[-1][1] if self.stack else None
            key = ((source_key(parent) if parent else None), kind, node["number"])
            if key in self.seen_numbers:
                self.quality.add("duplicate_legal_number", "Repeated legal number retained in source order", node["source_ref"])
            self.seen_numbers.add(key)
            (parent["children"] if parent else self.children).append(node)
            self.stack.append((kind, node))
            self.previous = node["children"][-1] if node["children"] else node
            return
        if block["type"] == "list":
            self.parse_list(block)
        if re.fullmatch(r"\d+", block.get("text", "")):
            self.quality.add("possible_page_number", "Bare source number retained; no evidence to remove it or infer a clause", block["source_ref"])
        target = self.stack[-1][1]["children"] if self.stack else self.children
        if "article" not in active and block["type"] == "numbered_paragraph":
            block.setdefault("evidence", "source_counter_outside_article_scope")
            if block.get("number", "").isdigit():
                target.append(block)
                self.generic_numbers = {block['number']: block}
                self.generic_parent = block if (block.get("text") or "").rstrip().endswith(":") else None
                self.generic_child = None
            elif self.generic_parent:
                self.generic_parent["children"].append(block)
                self.generic_child = block
            else:
                target.append(block)
        elif self.generic_child or self.generic_parent:
            (self.generic_child or self.generic_parent)["children"].append(block)
        else:
            target.append(block)
        self.previous = block

    def parse_list(self, listing):
        active = {k for k, n in self.stack if n.get("parent_status") != "unresolved"}
        numbering = listing.get("numbering", {}).get("type", "1")
        introduced_list = self.previous and self.previous.get("type") not in LEVELS and self.previous.get("text", "").endswith(":")
        if introduced_list and listing["list_kind"] == "ordered" and "article" in active:
            listing.update(candidate_role="clause", confidence=0.4)
            self.quality.add("ambiguous_clause_candidate", "Ordered list introduced by prose retained without asserted clauses", listing["source_ref"])
        for item in listing["children"]:
            if item["type"] != "list_item":
                continue
            first = item["children"][0] if item["children"] and item["children"][0]["type"] == "paragraph" else item
            marker = candidate({**first, "type": "paragraph"})
            if marker and (marker["explicit"] or marker["kind"] == "point" or
                           "article" in active and "clause" not in active and not introduced_list):
                converted = legal_node(first, marker)
                if first is not item:
                    converted["children"].extend(item["children"][1:])
                    converted["source_refs"] = [item["source_ref"], first["source_ref"]]
                    converted["source_ref"] = item["source_ref"]
                    converted["order"] = item["order"]
                converted["ordinal"] = item.get("ordinal")
                item.clear()
                item.update(converted)
            elif listing["list_kind"] == "ordered" and "article" in active and item.get("ordinal") is not None and not introduced_list:
                ordinal = item["ordinal"]
                kind, number = None, None
                if numbering == "1" and "clause" not in active:
                    kind, number = "clause", str(ordinal)
                elif numbering in {"a", "A"} and ordinal > 0:
                    letters = ""
                    while ordinal:
                        ordinal, digit = divmod(ordinal - 1, 26)
                        letters = chr(ord('a') + digit) + letters
                    kind, number = "point", letters.upper() if numbering == "A" else letters
                if kind:
                    if item.get("text"):
                        item["children"].insert(0, slice_unit(item, 0))
                        item["text"] = ""
                        item.pop("annotations", None)
                    item.update(type=kind, number=number, evidence="html_list_counter_in_legal_context")
            context = list(self.stack)
            if item["type"] in LEVELS:
                required = "article" if item["type"] == "clause" else "clause" if item["type"] == "point" else None
                if required and required not in active:
                    item["parent_status"] = "unresolved"
                    self.quality.add(f"orphan_{item['type']}", f"List legal unit lacks a valid {required} parent; no parent invented", item["source_ref"])
                context.append((item["type"], item))
            # Nested lists inherit this item's legal context, which never leaks
            # to siblings or to the surrounding document stack.
            local = BodyParser([], self.quality, context, list_context=True)
            for child in item["children"]:
                if child["type"] == "list":
                    local.parse_list(child)


def legal_structure(elements, quality):
    """Parse an independent fragment with the same stack used by document bodies."""
    children = []
    parser = BodyParser(children, quality)
    blocks = coalesce(list(logical_blocks(elements)))
    for i, block in enumerate(blocks):
        parser.append(block, blocks[i + 1] if i + 1 < len(blocks) else None)
    return children


def add_layout(section, block):
    layout = block.get("_source_layout")
    if layout:
        layouts = section.setdefault("source_layouts", [])
        if layout not in layouts:
            layouts.append(layout)


def scope_attached_acts(blocks, quality):
    """An intermediate signature/header belongs to an attached act's boundary.

    Keep one canonical document body. Local closing and attached letterhead
    blocks preserve source roles and order without repeating root sections.
    """
    index = 0
    while index < len(blocks):
        role = opening_role(blocks[index])
        if role not in {'issuing_authority', 'national_heading'}:
            index += 1; continue
        end = next((i for i in range(index + 1, min(index + 16, len(blocks)))
                    if (m := candidate(blocks[i])) and m['explicit'] and m['kind'] in {'chapter', 'article', 'part'}), None)
        normative = end and any(re.match(r'^(?:QUY CHẾ|QUY ĐỊNH|ĐIỀU LỆ)(?:\[\d+\])?$', b.get('text') or '')
                               and b.get('heading_evidence') for b in blocks[index:end])
        previous_legal = max((i for i in range(index) if (m := candidate(blocks[i])) and m['explicit'] and m['kind'] == 'article'), default=-1)
        closing_start = next((i for i in range(previous_legal + 1, index) if closing_role(blocks[i]) in {'recipients', 'delegation_title', 'signer_title', 'signature_status'}), None)
        if not normative or previous_legal < 0 or closing_start is None:
            index += 1; continue
        closing = build_document(blocks[closing_start:index], blocks[closing_start]['source_ref'], quality)
        letterhead = build_document(blocks[index:end], blocks[index]['source_ref'], quality)
        replacements = []
        for parsed, evidence, first in ((closing, 'closing_before_attached_legal_act', blocks[closing_start]),
                                        (letterhead, 'attached_legal_act_header', blocks[index])):
            wrapper = container('layout_block', first)
            wrapper['evidence'] = evidence
            wrapper['children'] = [child for section in parsed['children'] for child in section['children']]
            replacements.append(wrapper)
        blocks = blocks[:closing_start] + replacements + blocks[end:]
        index = closing_start + 2
    return blocks


def build_document(elements, ref, quality):
    from .semantic_refinement import annex_candidate
    from .quoted_content import scope_quotations, scope_restarted_counters, scope_article_enumerations, scope_body_outlines, scope_contents
    blocks = coalesce(scope_contents(scope_body_outlines(scope_article_enumerations(scope_restarted_counters(scope_quotations(list(logical_blocks(elements)), quality))))))
    blocks = scope_attached_acts(blocks, quality)
    document = container("legal_document", ref=ref)
    section, body, previous, closing_group, current_annex = None, None, None, None, None
    recipient_scopes = {}
    embedded_contract = False
    phase = -1
    phases = {"header": 0, "title_block": 1, "preamble": 2, "enacting_formula": 3, "body": 4, "closing": 5, "annexes": 6}
    initial_header = False
    initial_opening = False
    for block in blocks:
        marker = candidate(block)
        if marker and marker["kind"] in {"part", "chapter", "section", "subsection", "article"}:
            break
        role = opening_role(block)
        initial_opening |= bool(role)
        if role == "document_type_heading":
            break
        initial_header |= role in {"issuing_authority", "document_number", "national_heading", "national_motto", "place_and_date"}

    def ensure(kind, first):
        nonlocal section, body, phase, closing_group
        if section is None or section["type"] != kind:
            section = container(kind, first)
            document["children"].append(section)
            phase = phases[kind]
            if kind == "body":
                body = BodyParser(section["children"], quality)
            closing_group = None
        add_layout(section, first)
        return section

    for i, block in enumerate(blocks):
        following = blocks[i + 1] if i + 1 < len(blocks) else None
        marker, role, closing = candidate(block), opening_role(block), closing_role(block)
        if phase <= 1 and re.match(r'^(?:QUY CHẾ|QUY ĐỊNH|ĐIỀU LỆ)(?:\[\d+\])?$', block.get('text') or '') and block.get('heading_evidence'):
            role = 'document_type_heading'
        next_marker = candidate(following) if following else None
        annex_marker = annex_candidate(block)
        if phase == 6 and re.match(r"^HỢP ĐỒNG\b", block.get("text") or "") and block.get("heading_evidence"):
            embedded_contract = True
        if embedded_contract and annex_marker and annex_marker["number"] and re.fullmatch(r"[A-ZĐ]", annex_marker["number"]):
            block.update(type="annex_heading", evidence="lettered_appendix_in_source_contract")
            annex_marker = None
        elif annex_marker:
            embedded_contract = False
        if annex_marker and (phase < 6 or annex_marker["number"] is not None):
            target = ensure("annexes", block)
            current_annex = container("annex", block)
            current_annex["_annex_marker"] = annex_marker
            current_annex["number"] = annex_marker["number"]
            current_annex["children"].append(block)
            target["children"].append(current_annex)
            previous = "annex"
            continue
        if phase == 6:
            add_layout(section, block)
            current_annex["children"].append(block)
            continue
        if marker and not marker["explicit"] and marker["kind"] == "clause" and phase < 3 and initial_opening:
            block.update(type="numbered_paragraph", number=marker["number"])
            marker = None
        header_authority = phase < 2 and initial_header and role == "issuing_authority"
        if phase == 5 or closing and not header_authority and (closing != "signer_title" or phase >= 4 or block.get("_source_layout")):
            target = ensure("closing", block)
            if re.match(r"^(?:PHỤ LỤC|Ghi chú\s*:|Chú thích\s*:)", block.get("text", ""), re.I):
                closing_group = None
            if closing == "recipients":
                block["type"] = "recipients"
                target["children"].append(block)
                closing_group = block
                if block.get("_source_layout"):
                    recipient_scopes[block["_source_layout"]["table_id"]] = block
            elif block.get("_source_layout", {}).get("table_id") in recipient_scopes and re.match(r"^[-–—•]\s*\S", block.get("text") or ""):
                block["type"] = "recipient"
                # Source rows interleave signing and recipient columns. Keep
                # their traversal order with an explicit continuation group.
                group = target["children"][-1]
                if group["type"] != "recipients":
                    group = container("recipients", block)
                    group["evidence"] = "source_recipient_continuation_in_closing_table"
                    target["children"].append(group)
                group["children"].append(block)
                closing_group = group
            elif closing in {"delegation_title", "signer_title", "signature_status", "signature_marker"}:
                if closing_group is None or closing_group["type"] != "signature":
                    closing_group = container("signature", block)
                    target["children"].append(closing_group)
                block["type"] = closing
                if closing == "signature_marker":
                    block["semantic"] = "signed"
                closing_group["children"].append(block)
            elif closing_group and closing_group["type"] == "recipients":
                block["type"] = "recipient" if block["type"] in TEXT_TYPES else block["type"]
                if block["type"] == "list":
                    for item in block["children"]:
                        if item["type"] == "list_item":
                            item["type"] = "recipient"
                closing_group["children"].append(block)
            elif closing_group and closing_group["type"] == "signature":
                text = block.get("text", "")
                name = 2 <= len(text.split()) <= 7 and all(w[0].isupper() and w.isalpha() for w in text.split())
                if name and any(n["type"] in {"signer_title", "signature_status", "signature_marker"} for n in closing_group["children"]):
                    block["type"] = "signer_name"
                    closing_group["children"].append(block)
                else:
                    closing_group = None
                    target["children"].append(block)
            else:
                target["children"].append(block)
        elif is_formula(block) and phase < 4 and (phase in {1, 2} or
                next_marker and next_marker["explicit"] and LEVELS[next_marker["kind"]] <= LEVELS["article"]):
            block["type"] = "enacting_formula"
            document["children"].append(block)
            section, phase = None, 3
        elif marker or phase >= 3 or block.get('evidence') == 'emphasized_roman_body_outline':
            target = ensure("body", block)
            body.append(block, following)
        elif role in {"legal_basis", "proposal_basis"}:
            target = ensure("preamble", block)
            block["type"] = role
            target["children"].append(block)
        elif role == "document_type_heading" and phase <= 1:
            target = ensure("title_block", block)
            block["type"] = role
            target["children"].append(block)
        elif phase == 1:
            # An unlabelled motivation paragraph/list can precede an explicit
            # legal basis or enacting formula. That source boundary prevents
            # a sparse-body fallback from swallowing the whole preamble.
            first_legal = next((j for j in range(i + 1, len(blocks))
                                if (m := candidate(blocks[j])) and m['explicit']), len(blocks))
            preamble_evidence = any(opening_role(b) in {'legal_basis', 'proposal_basis'} or is_formula(b)
                                    for b in blocks[i + 1:first_legal])
            title_present = previous != 'document_type_heading' or i and not re.fullmatch(DOCUMENT_TYPES, blocks[i - 1].get('text') or '', re.I)
            if title_present and preamble_evidence and not role and not block.get('heading_evidence') and block['type'] in {'paragraph', 'list'}:
                ensure('preamble', block)['children'].append(block)
                previous = block['type']
                continue
            narrative = not role and not block.get("heading_evidence") and block.get("_alignment") != "center" and (
                len(block.get("text", "")) > 120 or block["type"] == "numbered_paragraph")
            if narrative and previous != "document_type_heading":
                ensure("body", block)
                body.append(block, following)
                previous = block["type"]
                continue
            target = ensure("title_block", block)
            if role == "issuing_authority" or closing == "signer_title":
                block["type"] = "issuing_authority_title"
            elif previous == "document_type_heading" or block.get("_alignment") == "center" and not role:
                block["type"] = "document_title"
            target["children"].append(block)
        elif phase == 2:
            ensure("preamble", block)["children"].append(block)
        elif initial_header or role in {"national_heading", "national_motto", "document_number", "place_and_date", "issuing_authority"}:
            if phase <= 0 and not role and len(block.get("text", "")) > 120 and not block.get("heading_evidence") and not block.get("_source_layout"):
                ensure("body", block)
                body.append(block, following)
                previous = block["type"]
                continue
            target = ensure("header", block)
            if role:
                block["type"] = role
            if role == "document_number":
                block["number"] = block["text"].split(":", 1)[1].strip()
            if re.fullmatch(r"\d+", block.get("text", "")):
                quality.add("possible_page_number", "Bare source number retained in header; no evidence to remove it", block["source_ref"])
            target["children"].append(block)
        elif initial_opening:
            ensure("title_block", block)["children"].append(block)
        else:
            ensure("body", block)
            body.append(block, following)
        previous = block["type"]
    return document


def strip_private(value):
    """Drop transient evidence throughout all tabs, including nested data cells."""
    if isinstance(value, dict):
        for key in list(value):
            if key.startswith("_"):
                del value[key]
            else:
                strip_private(value[key])
    elif isinstance(value, list):
        for child in value:
            strip_private(child)
