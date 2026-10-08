"""A single conservative semantic tree; HTML nodes remain internal only."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse

from .extract_quality import Quality
from .html_source import NON_CONTENT, BLOCK_TAGS, Node, whitespace, whole_unit_emphasis
from .html_tables import parse_table
from .legal_hierarchy import LEVELS, build_document, closing_role, container, logical_blocks
from .table_semantics import classify_table, effective_cell_text, finalize_table_issues

SCHEMA_VERSION = "2.3.2"
PARSER_VERSION = "2.3.2"
INLINE = {"a", "span", "b", "strong", "em", "i", "u", "s", "sup", "sub", "font", "br", "small", "mark", "wbr"}
MEDIA = {"img", "svg", "canvas", "object", "iframe", "embed", "audio", "video"}


def text_annotations(node, text, quality):
    """Retain exact notation offsets; never locate a superscript by matching its value."""
    nodes = [n for n in node.find() if n.tag in {"sup", "sub"}]
    if not nodes:
        return []
    prefix = "\ufdd0"
    while prefix in text:
        prefix += "\ufdd0"
    indexes = {id(n): i for i, n in enumerate(nodes)}
    def marked(n):
        children = []
        for child in n.children:
            if isinstance(child, str):
                children.append(child)
            else:
                clone = marked(child)
                if id(child) in indexes:
                    index = indexes[id(child)]
                    clone = Node("span", children=[f"{prefix}S{index}{prefix}", clone, f"{prefix}E{index}{prefix}"])
                children.append(clone)
        return Node(n.tag, n.attrs, children)
    rendered = marked(node).text(blocks=True)
    pattern = re.compile(re.escape(prefix) + r"([SE])(\d+)" + re.escape(prefix))
    plain, cursor, opened, annotations = [], 0, {}, []
    for match in pattern.finditer(rendered):
        plain.append(rendered[cursor:match.start()])
        position = sum(len(piece) for piece in plain)
        index = int(match[2])
        if match[1] == "S":
            opened[index] = position
        elif index in opened:
            child = nodes[index]
            annotations.append({"type": "superscript" if child.tag == "sup" else "subscript",
                                "start": opened[index], "end": position, "source_ref": child.ref})
        cursor = match.end()
    plain.append(rendered[cursor:])
    if ''.join(plain) != text:
        quality.add("ambiguous_inline_notation", "Inline notation offsets could not be established; text and source references retained", node.ref)
        return []
    return sorted(annotations, key=lambda a: (a["start"], a["end"]))


def text_without_tables(node, blocks=False):
    if node.tag == "table":
        return ""
    def filtered(n):
        return Node(n.tag, n.attrs, [Node("br") if isinstance(c, Node) and c.tag == "table" else
                                    filtered(c) if isinstance(c, Node) else c for c in n.children])
    return filtered(node).text(blocks)


def reference(node, source_url):
    href = node.attrs.get("href")
    target = urljoin(source_url, href) if href else None
    url = target if target and urlparse(target).scheme in {"http", "https"} else None
    identifiers = [{"attribute": k, "value": v} for k, v in node.attrs.items() if v is not None and
                   (k in {"id", "data-id", "data-key", "data-row-key"} or
                    re.search(r"(?:document|doc|item|vb).*(?:id|key)$", k, re.I))]
    if url:
        part = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1].rsplit("--", 1)[-1]
        if re.fullmatch(r"\d+|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", part):
            identifiers.append({"attribute": "url_path_identifier", "value": part})
        for key, values in parse_qs(urlparse(url).query).items():
            if re.fullmatch(r"(?:item|document|doc|vb)?id", key, re.I):
                identifiers.extend({"attribute": "url_query_" + key, "value": v} for v in values)
    return {"href": href, "url": url, "identifiers": identifiers, "source_ref": node.ref}


def document_numbers(text):
    # Candidates are exact source slices, never a selected/resolved target.
    pattern = (r"(?<![\w/])\d+(?:\.\d+)?[a-zđ]?(?:\s*/\s*(?:\d{4}\s*/\s*)?[A-ZĐ][A-ZĐa-zđ0-9.-]*(?:[-/][A-ZĐa-zđ0-9.]+)*"
               r"|\s*-\s*[A-ZĐ][A-ZĐa-zđ0-9.]*(?:[-/][A-ZĐa-zđ0-9.]+)*)(?![\w/])")
    return list(dict.fromkeys(m.group().rstrip('.;,:') for m in re.finditer(pattern, text)))


def document_number_roles(text):
    """Select only the leading citation, including a named Law before 'số'."""
    candidates = document_numbers(text)
    citation = re.match(r"^\s*(?:Quyết định|Nghị định|Thông tư(?: liên tịch)?|Luật|"
                        r"Bộ luật|Nghị quyết|Pháp lệnh|Chỉ thị|Sắc lệnh|Lệnh|Văn bản hợp nhất)\s+số\s+", text, re.I)
    if not citation:
        # A named Law cannot skip across another cited document or sentence to
        # select a later identifier. Match the name before its first 'số'.
        citation = re.match(r"^\s*(?:Bộ luật|Luật)\s+((?:(?!\bsố\b)[^;.!?\n]){1,180}?)\s+số\s+", text, re.I)
        if citation and re.search(r"\b(?:Nghị định|Thông tư|Quyết định|Nghị quyết)\b|\b(?:sửa(?: đổi)?|theo|của|và)\s+(?:Bộ luật|Luật)\b", citation[1], re.I):
            citation = None
    primary = next((number for number in candidates if citation and
                    text[citation.end():].startswith(number)), None)
    return {"primary_document_number_candidate": primary,
            "mentioned_document_numbers": [n for n in candidates if n != primary]}



class GeometryBuilder:
    """Private adapter for geometry; never exposes its transient row wrappers."""
    def __init__(self, semantic):
        self.semantic = semantic
        self.issues = []

    def base(self, node, kind, text=None):
        return {"id": f"cell_{node.dom_order}", "type": kind, "text": node.text(blocks=True) if text is None else text,
                "children": [], "order": node.dom_order, "source_ref": node.ref, "attributes": node.attrs}

    def text(self, node, blocks=False):
        return node.text(blocks)

    def serialize_children(self, node):
        return []

    def prepare_cells(self, source, cells):
        by_order = {n.dom_order: n for n in source.find()}
        for cell in cells:
            node = by_order[cell["order"]]
            paragraphs = node.find("p")
            nested = (any(n.tag in {"table", "ol", "ul"} | MEDIA for n in node.find()) or
                      len(paragraphs) > 1 or
                      (paragraphs and any(isinstance(c, str) and whitespace(c) for c in node.children)))
            if nested:
                cell["text"] = ""
                cell["content"] = self.semantic.flow(node)
            else:
                annotations = text_annotations(node, cell["text"], self.semantic.quality)
                if annotations:
                    cell["annotations"] = annotations
            cell["text_segments"], cell["effective_text"] = effective_cell_text(cell)

    def classify_table(self, source, rows, cells):
        return classify_table(source, rows, cells)

    def serialize_child(self, child, parent, index):
        if isinstance(child, Node) and child.tag == "colgroup":
            return []
        return self.semantic.flow(Node("div", children=[child], dom_order=parent.dom_order,
                                       text_refs={0: parent.text_refs.get(index, parent.ref)}))


class SemanticBuilder:
    def __init__(self, source_url="", quality=None, excluded=None):
        self.source_url = source_url
        self.quality = quality or Quality()
        self.excluded = set(excluded or [])

    def covered(self, node):
        if node.dom_order in self.excluded or node.tag in NON_CONTENT:
            return True
        for i, child in enumerate(node.children):
            if isinstance(child, Node):
                if child.tag in MEDIA and child.dom_order not in self.excluded:
                    return False
                if not self.covered(child):
                    return False
            elif whitespace(child) and node.text_refs.get(i, node.ref)["dom_order"] not in self.excluded:
                return False
        return True

    def base(self, node, kind, text="", ref=None):
        source_ref = ref or node.ref
        return {"type": kind, "text": text,
                "order": source_ref["dom_order"], "children": [], "source_ref": source_ref}

    def unit(self, node, kind="paragraph"):
        text = node.text(blocks=True)
        if not text:
            return []
        if re.fullmatch(r"[\s_—–=*-]{3,}", text):
            self.quality.ignore(node, "decorative_separator")
            return []
        block = self.base(node, kind, text)
        alignment = node.attrs.get("align") or next(iter(re.findall(
            r"text-align\s*:\s*(center|left|right|justify)", node.attrs.get("style", ""), re.I)), None)
        if alignment:
            block["_alignment"] = alignment.lower()
        identifiers = reference(node, self.source_url)["identifiers"]
        if identifiers:
            block["source_identifiers"] = identifiers
        refs = [reference(n, self.source_url) for n in node.find("a")]
        if node.tag == "a":
            refs.insert(0, reference(node, self.source_url))
        if refs:
            block["references"] = refs
        annotations = text_annotations(node, text, self.quality)
        if annotations:
            block["annotations"] = annotations
        if kind == "heading" or node.tag in {"b", "strong"}:
            block["heading_evidence"] = "heading_markup"
        elif len(text) <= 160 and whole_unit_emphasis(node):
            block["heading_evidence"] = "whole_unit_emphasis"
        elif all(not whitespace(c) if isinstance(c, str) else c.tag in {"b", "strong", "br"} for c in node.children):
            block["heading_evidence"] = "whole_unit_emphasis"
        elif text.isupper() and set(node.attrs.get('class', '').split()) & {'prov-part', 'prov-chapter', 'prov-section', 'prov-subsection', 'prov-article'}:
            block['heading_evidence'] = 'source_provision_heading_class'
        for child in node.find():
            if child.tag in {"b", "strong"} and child.text().startswith(("Phụ lục", "PHỤ LỤC")):
                block["_heading_prefix"] = child.text(blocks=True).splitlines()[0]
                break
        if node.tag == "small" or node.find("small") or re.search(r"font-size\s*:\s*(?:[6-9]|10)(?:pt|px)", node.attrs.get("style", ""), re.I):
            block["_note_style"] = True
        self.quality.record(block["order"], text)
        return [block]

    def flow(self, node):
        result, pending, pending_refs = [], [], []
        def flush():
            if not pending:
                return
            # Only an uninterrupted inline run is combined; never combine paragraphs.
            run = Node("p", children=list(pending), dom_order=pending_refs[0]["dom_order"],
                       line=pending_refs[0].get("line", 0), column=pending_refs[0].get("column", 0))
            units = self.unit(run)
            if units:
                units[0]["source_ref"] = pending_refs[0]
                units[0]["order"] = pending_refs[0]["dom_order"]
                units[0]["_scope"] = node.dom_order
            result.extend(units)
            pending.clear(); pending_refs.clear()
        for i, child in enumerate(node.children):
            if isinstance(child, str):
                if node.text_refs.get(i, node.ref)["dom_order"] in self.excluded:
                    flush()
                    continue
                if whitespace(child) or pending:
                    pending.append(child)
                    pending_refs.append(node.text_refs.get(i, node.ref))
                continue
            if child.dom_order in self.excluded or (self.excluded and self.covered(child)):
                flush()
                continue
            if child.tag in NON_CONTENT or child.tag in {"comment", "meta", "link", "input", "colgroup", "col"}:
                flush()
                continue
            if child.tag in INLINE and not any(n.tag in BLOCK_TAGS | {"table"} | MEDIA for n in child.find()):
                pending.append(child); pending_refs.append(child.ref)
                continue
            flush()
            if child.tag == "table":
                result.append(self.table(child))
            elif child.tag in {"tr", "tbody", "thead", "tfoot"}:
                result.extend(self.flow(child))
            elif child.tag in {"ol", "ul"}:
                listing = self.list(child)
                if listing["children"]:
                    result.append(listing)
            elif child.tag == "hr":
                result.append(self.base(child, "separator"))
            elif child.tag in MEDIA:
                block = self.base(child, "unknown", child.text(blocks=True))
                block["media"] = {k: child.attrs[k] for k in ("src", "href", "alt", "title", "data") if k in child.attrs}
                if child.tag == "img" and child.attrs.get("alt"):
                    block["media"]["alt"] = child.attrs["alt"]
                self.quality.record(block["order"], block["text"])
                self.quality.add("non_text_content", "Media retained by source reference and source URL; not interpreted", child.ref)
                result.append(block)
            elif child.tag == "button" and any(n.tag in {"table", "ol", "ul"} for n in child.find()):
                block = self.base(child, "layout_block")
                block["children"] = self.flow(child)
                identifiers = reference(child, self.source_url)["identifiers"]
                if identifiers:
                    block["source_identifiers"] = identifiers
                result.append(block)
            elif not any(n.tag in {"p", "table", "ol", "ul", "div", "section", "li"} | MEDIA for n in child.find()):
                if any(n.dom_order in self.excluded for n in child.find()):
                    result.extend(self.flow(child))
                else:
                    known = child.tag in BLOCK_TAGS | INLINE | {"body", "html", "main", "root", "center", "td", "th", "tbody", "thead", "tfoot"}
                    kind = "heading" if re.fullmatch(r"h[1-6]", child.tag) else "paragraph" if known else "unknown"
                    units = self.unit(child, kind)
                    for unit in units:
                        unit["_scope"] = child.dom_order if child.tag in {"td", "th"} else node.dom_order
                    result.extend(units)
                    if not known:
                        self.quality.add("unknown_element", "Unrecognized source element retained as a semantic unknown unit", child.ref)
            else:
                result.extend(self.flow(child))
        flush()
        alignment = node.attrs.get("align") or next(iter(re.findall(
            r"text-align\s*:\s*(center|left|right|justify)", node.attrs.get("style", ""), re.I)), None)
        if node.tag == "center":
            alignment = "center"
        if alignment:
            for block in result:
                block.setdefault("_alignment", alignment.lower())
        if node.attrs.get("data-page"):
            page = {"scope": node.dom_order, "number": node.attrs["data-page"]}
            for index, block in enumerate(result):
                block.setdefault("_page", page)
                if index in {0, len(result) - 1}:
                    block["_page_edge"] = True
        return result

    def list(self, node):
        result = self.base(node, "list")
        if node.attrs.get("_extract_footnote_scope"):
            result["_footnote_scope"] = True
        result["list_kind"] = "ordered" if node.tag == "ol" else "unordered"
        result["numbering"] = {k: node.attrs[k] for k in ("start", "type", "reversed") if k in node.attrs}
        step = -1 if "reversed" in node.attrs else 1
        try:
            current = int(node.attrs.get("start", sum(isinstance(c, Node) and c.tag == 'li' for c in node.children) if step == -1 else 1))
        except (ValueError, TypeError):
            current = None
            self.quality.add("invalid_list_start", "Source counter retained without inferred numbering", node.ref)
        for i, child in enumerate(node.children):
            if not isinstance(child, Node) or child.tag != "li":
                if isinstance(child, Node) or whitespace(child):
                    result["children"].extend(self.flow(Node("div", children=[child], text_refs={0: node.text_refs.get(i, node.ref)})))
                continue
            item = self.base(child, "list_item")
            raw = child.attrs.get("value")
            if raw is not None:
                try:
                    current = int(raw)
                except ValueError:
                    current = None
                    self.quality.add("invalid_list_value", "Source item counter retained without inferred numbering", child.ref)
                item["number"] = raw
            item["ordinal"] = current if node.tag == "ol" else None
            item["children"] = self.flow(child)
            if not item["children"] and self.covered(child):
                if current is not None:
                    current += step
                continue
            # One paragraph directly in li is its own text, without a redundant child.
            if len(item["children"]) == 1 and item["children"][0]["type"] == "paragraph":
                paragraph = item["children"].pop()
                item["text"] = paragraph["text"]
                for key in ("references", "annotations", "source_identifiers"):
                    if paragraph.get(key):
                        item[key] = paragraph[key]
            result["children"].append(item)
            if current is not None:
                current += step
        return result

    def table(self, node):
        adapter = GeometryBuilder(self)
        geometry = parse_table(node, adapter, table_kind=None)
        kind, evidence = geometry["table_kind"], geometry["classification_evidence"]
        if kind == "layout":
            result = self.base(node, "layout_block")
            result["source_layout"] = {"type": "table", "table_id": f"table_{node.dom_order}",
                                       "table_kind": kind, "classification_evidence": evidence}
            result["children"] = self.flow(node)
            if evidence in {"source_signature_block", "source_addressee_block"}:
                # A standalone display block has a local semantic scope. It
                # must not end the main body before a following attached act.
                units = list(logical_blocks([result]))
                group = container("signature" if evidence == "source_signature_block" else "recipients", units[0])
                for unit in units:
                    role = closing_role(unit)
                    text = unit.get("text") or ""
                    if evidence == "source_signature_block":
                        name = 2 <= len(text.split()) <= 7 and all(w[0].isupper() and w.isalpha() for w in text.split())
                        unit["type"] = role or ("signer_name" if name else unit["type"])
                    elif re.match(r"Kính gửi\s*:", text, re.I):
                        group.update(text=text, source_ref=unit["source_ref"], order=unit["order"])
                        continue
                    else:
                        unit["type"] = "recipient"
                    group["children"].append(unit)
                result["children"] = [group]
                result["evidence"] = evidence
            for diagnostic in adapter.issues:
                severity = "info" if diagnostic["code"] in {"ragged_table", "table_grid_gap", "span_crosses_row_group"} else None
                self.quality.add(diagnostic["code"], diagnostic["message"], diagnostic["source_ref"], severity)
            self.quality.add("layout_table_detected", "Document layout semanticized from source flow", node.ref)
            return result
        result = self.base(node, "table")
        result.update(table_id=f"table_{node.dom_order}", table_kind=kind,
                      classification_evidence=evidence, grid_shape=geometry["grid_shape"], cells=[],
                      semantics=geometry["semantics"], issues=[], _diagnostics=adapter.issues)
        result["row_groups"] = [{"group_id": g["id"], "section": g["section"],
                                 "row_start": min(g["rows"]) if g["rows"] else None,
                                 "row_end": max(g["rows"]) if g["rows"] else None,
                                 "source_ref": g["source_ref"]} for g in geometry["row_groups"]]
        if geometry["column_groups"]:
            result["column_groups"] = [{"group_id": g["id"], **{k: g[k] for k in
                                        ("column", "colspan", "source_ref")}} for g in geometry["column_groups"]]
        by_order = {n.dom_order: n for n in node.find()}
        for row in geometry["rows"]:
            for cell in row["cells"]:
                source = by_order[cell["order"]]
                out = {k: cell[k] for k in ("row", "column", "rowspan", "colspan", "text", "cell_type", "order", "source_ref", "section", "text_segments", "effective_text")}
                out.update(cell_id=cell["id"], original_rowspan=source.attrs.get("rowspan", "1"),
                           original_colspan=source.attrs.get("colspan", "1"), row_group_id=cell["row_group"])
                if "content" in cell:
                    out["content"] = cell["content"]
                else:
                    self.quality.record(out["order"], out["text"])
                if cell.get("annotations"):
                    out["annotations"] = cell["annotations"]
                out.update({k: cell[k] for k in ("role", "confidence", "header_refs", "header_candidates", "association_status", "header_evidence", "evidence") if k in cell})
                if not out.get("header_candidates"):
                    out.pop("header_candidates", None)
                if not any(out.get("header_refs", {}).values()):
                    out.pop("header_refs", None)
                if cell.get("association_status") != "supported":
                    out.pop("header_evidence", None)
                if cell.get("header_kind"):
                    out["role"] = cell["header_kind"]
                    out["labels"] = [label["text"] for label in cell["candidate_labels"]]
                    out.update(orientation="unknown", row_axis=None, column_axis=None)
                    if cell["header_kind"] == "dual_axis_header":
                        out["orientation"] = "explicit"
                        out["row_axis"] = [label["text"] for label in cell["candidate_labels"] if label["role"] == "row_header"]
                        out["column_axis"] = [label["text"] for label in cell["candidate_labels"] if label["role"] == "column_header"]
                if source.find("a"):
                    out["references"] = [reference(a, self.source_url) for a in source.find("a")]
                result["cells"].append(out)
        def extras(blocks):
            for block in blocks:
                if block["type"] == "row_group":
                    yield from extras(block["children"])
                elif block["type"] not in {"row_ref", "cell_ref"}:
                    yield block
        result["children"] = list(extras(geometry["children"]))
        for row in geometry["rows"]:
            result["children"].extend(extras(row["children"]))
        result["children"].sort(key=lambda b: b["order"])
        finalize_table_issues(result, self.quality)
        return result



def parse_content(root, source_url="", quality=None):
    from .semantic_refinement import refine_document
    from .form_refinement import navigation_artifacts
    quality = quality or Quality()
    for issue in root.issues:
        quality.add(issue["code"], issue["message"], issue.get("source_ref"))
    builder = SemanticBuilder(source_url, quality, excluded=navigation_artifacts(root, quality))
    document = build_document(builder.flow(root), root.ref, quality)
    document = refine_document(document, quality, root)
    if not document["children"]:
        quality.add("source_content_missing", "No meaningful content in HTML", root.ref)
    return {"document": document, "ignored_elements": quality.ignored, "issues": quality.issues}
