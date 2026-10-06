"""Extract source fields/events/groups without cross-tab normalization."""
from __future__ import annotations

import re

from .html_source import Node, whitespace
from .structured_html import SemanticBuilder, document_number_roles, reference

PROPERTY_LABELS = ("Số hiệu", "Loại văn bản", "Ngành", "Ngày ban hành", "Lĩnh vực", "Ngày có hiệu lực",
                   "Tình trạng hiệu lực", "Ngày hết hiệu lực", "Cơ quan ban hành", "Chức danh", "Người ký")


def refs(node, source_url):
    return [reference(a, source_url) for a in node.find("a")]


def parse_fields(root, quality, source_url, unknown=True):
    fields, claimed = [], set()
    containers = root.find(css_class="ant-descriptions-item-container")
    for node in containers:
        labels = node.find(css_class="ant-descriptions-item-label")
        values = node.find(css_class="ant-descriptions-item-content")
        if len(labels) != 1 or len(values) != 1:
            quality.add("incomplete_property_field", "Unclear field boundaries; retained as unknown source text", node.ref)
            field = {"label": None, "value": node.text(blocks=True), "role": "unknown", "evidence": "ambiguous_field_markup"}
        else:
            label, value = labels[0].text(blocks=True), values[0].text(blocks=True)
            # Interstitial text (e.g. punctuation/help text) must not disappear.
            represented = re.sub(r"\s+", "", label + value)
            if represented != re.sub(r"\s+", "", node.text(blocks=True)):
                quality.add("incomplete_property_field", "Extra source text outside label/value; retained as an unknown field", node.ref)
                field = {"label": None, "value": node.text(blocks=True), "role": "unknown", "evidence": "extra_field_text"}
            else:
                field = {"label": label, "value": value, "evidence": "label_content_markup"}
        field.update(order=node.dom_order, source_ref=node.ref)
        if node.find("table") or node.find("ol") or node.find("ul"):
            if field["label"] is not None:
                field["value_content"] = SemanticBuilder(source_url, quality).flow(values[0])
            else:
                field["value_content"] = SemanticBuilder(source_url, quality).flow(node)
            field["value"] = ""
        links = refs(node, source_url)
        if links:
            field["references"] = links
        fields.append(field); claimed.add(node.dom_order)
        quality.record(node.dom_order, (field["label"] or "") + field["value"])
    if containers:
        return fields, claimed
    # Legacy snapshots removed label spans. Keep unrecognized labels as raw values.
    source_cells = root.find("td")
    nested_cells = {id(n) for c in source_cells for n in c.find("td")}
    for cell in source_cells:
        if id(cell) in nested_cells:
            continue
        text = cell.text(blocks=True)
        label = next((s for s in PROPERTY_LABELS if re.match(re.escape(s) + r"(?:\s|:|$)", text)), None)
        if not text or (not label and not unknown):
            continue
        value = text[len(label):].strip() if label else text
        field = {"label": label, "value": value, "order": cell.dom_order, "source_ref": cell.ref,
                 "evidence": "source_label_prefix" if label else "unrecognized_field"}
        if cell.find("table") or cell.find("ol") or cell.find("ul"):
            field.update(label=None, value="", role="unknown",
                         value_content=SemanticBuilder(source_url, quality).flow(cell), evidence="structured_unknown_field")
            quality.add("unknown_property_structure", "Structured property retained without guessing field boundaries", cell.ref)
        if not label:
            field["role"] = "unknown"
            quality.add("unknown_property_label", "Field retained without guessing its label", cell.ref)
        links = refs(cell, source_url)
        if links:
            field["references"] = links
        fields.append(field); claimed.add(cell.dom_order)
        quality.record(cell.dom_order, (label or "") + value)
    if fields:
        quality.add("legacy_property_markup", "Label/value boundaries extracted from legacy source text", root.ref)
    return fields, claimed


def relation_groups(root, quality, source_url):
    groups, claimed = [], set()
    nodes = root.find(css_class="ant-card-body")
    if not nodes:
        nodes = [node for node in root.find("div") if re.search(r"\(\d+\)\s*$",
                 whitespace(''.join(c for c in node.children if isinstance(c, str))))]
    for node in nodes:
        label_nodes = [c for c in node.children if isinstance(c, Node) and c.tag in {"span", "h2", "h3", "h4"}]
        label_node = next((c for c in label_nodes if re.search(r"\(\d+\)\s*$", c.text())), None)
        label_raw = label_node.text() if label_node else whitespace(''.join(c for c in node.children if isinstance(c, str)))
        if not label_raw:
            continue
        match = re.match(r"^(.*?)\s*\((\d+)\)\s*$", label_raw, re.S)
        relation_type = match[1].strip() if match else label_raw
        count = int(match[2]) if match else None
        group = {"label_raw": label_raw, "relation_type_raw": relation_type,
                 "declared_count": count, "items": [], "order": node.dom_order, "source_ref": node.ref}
        consumed = set()
        if label_node:
            consumed.add(label_node.dom_order)
            quality.record(label_node.dom_order, label_raw)
        else:
            for i, c in enumerate(node.children):
                if isinstance(c, str) and whitespace(c):
                    ref = node.text_refs.get(i, node.ref)
                    consumed.add(ref["dom_order"])
                    quality.record(ref["dom_order"], c)
        item_nodes = node.find("li")
        # Lists without links are still document records, e.g. button cards.
        if not item_nodes:
            item_nodes = node.find("button")
        nested_items = {id(n) for item in item_nodes for n in item.find()}
        top_items = [item for item in item_nodes if id(item) not in nested_items]
        for item in top_items:
            text = item.text(blocks=True)
            consumed.add(item.dom_order)
            if text in {"--", "—", "-"}:
                quality.ignore(item, "empty_relation_placeholder")
                continue
            if not text:
                continue
            references = refs(item, source_url)
            own = reference(item, source_url)
            identifiers = own["identifiers"] + [identifier for r in references for identifier in r["identifiers"]]
            urls = list(dict.fromkeys(r["url"] for r in references if r["url"]))
            record = {"text": text, "url": urls[0] if len(urls) == 1 else None,
                      **document_number_roles(text), "resolved_document_id": None,
                      "order": item.dom_order, "source_ref": item.ref}
            if item.find("table") or item.find("ol") or item.find("ul"):
                record["text"] = ""
                record["content"] = SemanticBuilder(source_url, quality).flow(item)
            if references:
                record["references"] = references
            if identifiers:
                record["source_identifiers"] = identifiers
            if len(urls) > 1:
                quality.add("ambiguous_document_reference", "Item contains multiple document URLs; no single target selected", item.ref, "info")
            elif not urls and not identifiers and not (record["primary_document_number_candidate"] or
                                                        record["mentioned_document_numbers"]):
                quality.add("unresolved_document_reference", "Source contains no document URL, identifier or number candidate", item.ref)
            record["resolution_status"] = "source_reference" if urls or identifiers else "candidate_only" if (
                record["primary_document_number_candidate"] or record["mentioned_document_numbers"]) else "unidentified"
            group["items"].append(record)
            quality.record(item.dom_order, text)
        context = SemanticBuilder(source_url, quality, consumed).flow(node)
        if context:
            group["context"] = context
        groups.append(group); claimed.add(node.dom_order)
    return groups, claimed


def history_events(root, quality, source_url):
    events, columns, context, claimed = [], [], [], set()
    tables = root.find("table")
    nested = {id(n) for t in tables for n in t.find("table")}
    for table in tables:
        if id(table) in nested:
            continue
        row_nested = {id(n) for t in table.find("table") for n in t.find("tr")}
        rows = [r for r in table.find("tr") if id(r) not in row_nested]
        cell_rows = [[c for c in row.children if isinstance(c, Node) and c.tag in {"th", "td"}] for row in rows]
        header_index = next((i for i, cells in enumerate(cell_rows) if cells and all(c.tag == "th" for c in cells)), None)
        headers = [c.text() for c in cell_rows[header_index]] if header_index is not None else []
        # Plan the whole table before claiming any text. Ambiguous geometry remains a table.
        simple = bool(headers) and len(set(headers)) == len(headers) and not table.find("table")
        for i, cells in enumerate(cell_rows):
            if not cells or not rows[i].text():
                continue
            simple &= (len(cells) == len(headers) and all(c.attrs.get("rowspan", "1") == "1" and
                       c.attrs.get("colspan", "1") == "1" and not c.find("ol") and not c.find("ul") for c in cells))
        if not simple:
            quality.add("ambiguous_history_structure", "History column associations are uncertain; full semantic table retained without guessed events", table.ref)
            context.append(SemanticBuilder(source_url, quality).table(table))
            claimed.add(table.dom_order)
            continue
        known = {"Thời gian": "date", "Trạng thái": "status", "Văn bản nguồn": "source_document"}
        table_claimed = set()
        for i, (row, cells) in enumerate(zip(rows, cell_rows)):
            if not cells or not row.text():
                continue
            if all(c.tag == "th" for c in cells):
                # Repeated pagination headers remain in their source order.
                for cell in cells:
                    columns.append({"label": cell.text(), "order": cell.dom_order, "source_ref": cell.ref})
                    quality.record(cell.dom_order, cell.text())
                table_claimed.add(row.dom_order)
                continue
            event = {"date": None, "status": None, "source_document": None,
                     "order": row.dom_order, "source_ref": row.ref, "source_cells": []}
            if row.attrs.get("data-row-key"):
                event["source_key"] = row.attrs["data-row-key"]
            values = []
            for label, cell in zip(headers, cells):
                text, key = cell.text(blocks=True), known.get(label)
                references = refs(cell, source_url)
                if key == "source_document":
                    urls = list(dict.fromkeys(r["url"] for r in references if r["url"]))
                    document = {"text": text, "url": urls[0] if len(urls) == 1 else None,
                                **document_number_roles(text)}
                    if references:
                        document["references"] = references
                    event[key] = document
                elif key:
                    event[key] = text
                else:
                    key = "other_values:" + str(len(values))
                    values.append({"label": label, "value": text, "source_ref": cell.ref})
                event["source_cells"].append({"field": key, "source_ref": cell.ref})
                quality.record(cell.dom_order, text)
            if values:
                event["other_values"] = values
            events.append(event); table_claimed.add(row.dom_order)
        context.extend(SemanticBuilder(source_url, quality, table_claimed).flow(table))
        claimed.add(table.dom_order)
    return events, columns, context, claimed


def extract_tab_data(root, key, source_url, quality):
    claimed, result = set(), {}
    # Capture-generated page headings are UI metadata, not legal content.
    for node in root.find("h2"):
        if re.fullmatch(r"(?:Thuộc tính|Lịch sử|Lược đồ|Các văn bản hợp nhất)\s*—\s*\d+", node.text()):
            quality.ignore(node, "capture_page_heading"); claimed.add(node.dom_order)
    for issue in root.issues:
        quality.add(issue["code"], issue["message"], issue.get("source_ref"))
    if key == "properties":
        fields, used = parse_fields(root, quality, source_url)
        result["fields"] = fields; claimed |= used
        if not fields:
            quality.add("unparsed_properties", "No field boundaries recognized; all text retained as context", root.ref)
    elif key == "relations":
        groups, used = relation_groups(root, quality, source_url)
        result["groups"] = groups; claimed |= used
        fields, used = parse_fields(root, quality, source_url, unknown=False)
        result["context_fields"] = fields; claimed |= used
        if not groups and not re.search(r"Không có dữ liệu|Chưa có dữ liệu|No data", root.text(), re.I):
            quality.add("unparsed_relations", "No relation groups recognized; all text retained as context", root.ref)
    elif key == "history":
        events, columns, history_context, used = history_events(root, quality, source_url)
        result.update(events=events, columns=columns); claimed |= used
        if not events and not re.search(r"Không có dữ liệu|Chưa có dữ liệu|No data", root.text(), re.I):
            quality.add("unparsed_history", "No history events recognized; source retained as semantic context", root.ref)
    elif key == "consolidated":
        result["items"] = []
        for item in root.find("button"):
            text = item.text(blocks=True)
            if not text:
                continue
            if item.find("table") or item.find("ol") or item.find("ul"):
                quality.add("ambiguous_consolidated_card", "Complex card retained as semantic content; no flattened document record", item.ref)
                continue
            references = refs(item, source_url)
            urls = list(dict.fromkeys(r["url"] for r in references if r["url"]))
            record = {"text": text, "url": urls[0] if len(urls) == 1 else None,
                      **document_number_roles(text), "resolved_document_id": None,
                      "order": item.dom_order, "source_ref": item.ref}
            if references:
                record["references"] = references
            identifiers = reference(item, source_url)["identifiers"]
            if identifiers:
                record["source_identifiers"] = identifiers
            result["items"].append(record)
            quality.record(item.dom_order, text); claimed.add(item.dom_order)
            if not urls and not identifiers and not (record["primary_document_number_candidate"] or record["mentioned_document_numbers"]):
                quality.add("unresolved_document_reference", "Consolidated card has no source URL, identifier or number candidate", item.ref)
            record["resolution_status"] = "source_reference" if urls or identifiers else "candidate_only" if (
                record["primary_document_number_candidate"] or record["mentioned_document_numbers"]) else "unidentified"
    else:
        # Dynamic tabs (including consolidated documents) remain independently extracted.
        result["content"] = SemanticBuilder(source_url, quality, claimed).flow(root)
        result["ignored_elements"] = quality.ignored
        result["issues"] = quality.issues
        return result
    context = SemanticBuilder(source_url, quality, claimed).flow(root)
    if key == "history":
        context.extend(history_context)
        context.sort(key=lambda n: n["order"])
    if context:
        result["context"] = context
    result["ignored_elements"] = quality.ignored
    result["issues"] = quality.issues
    return result
