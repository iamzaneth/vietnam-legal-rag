"""Validate document structure and provenance without repairing extracted facts."""
from __future__ import annotations

from .legal_hierarchy import LEVELS, source_key

COUNTERS = {"part": "parts", "chapter": "chapters", "section": "sections", "subsection": "subsections",
            "article": "articles", "clause": "clauses", "point": "points"}
SECTION_ORDER = ("header", "title_block", "preamble", "enacting_formula", "body", "closing", "annexes")
DOCUMENT_SECTIONS = set(SECTION_ORDER)
TABLE_KINDS = ("layout", "data", "matrix", "form", "key_value", "annex_form", "ambiguous")


def validate_hierarchy(document, quality, text_preserved=True):
    """max_depth counts edges from document through sections and legal nodes.

    Paragraphs/lists/tables do not add legal hierarchy levels. List wrappers
    remain ordered content but are transparent for legal parent validation.
    """
    counts = {"document_sections": dict.fromkeys(SECTION_ORDER, 0),
              "legal_hierarchy": dict.fromkeys(COUNTERS.values(), 0),
              "annex_hierarchy": dict.fromkeys(("annexes", "numbered_sections", "numbered_items", "max_depth"), 0),
              "tables": dict.fromkeys(TABLE_KINDS, 0),
              "unresolved": dict.fromkeys(("numbered_candidates", "orphan_nodes", "ambiguous_tables"), 0),
              "max_depth": 0, "schema_valid": True, "order_valid": True,
              "parent_child_valid": True, "semantic_complete": True, "status": "valid"}
    seen = set()
    legal_positions = []
    body_events = []

    def error(code, message, node):
        quality.add(code, message, node.get("source_ref"), "error")
        counts["order_valid" if code == "invalid_order" else "parent_child_valid"] = False

    def visit(node, ancestors=(), depth=0, parent=None, in_cell=False, list_scope=()):
        kind = node["type"]
        key = source_key(node)
        identity = (kind, *key)
        if identity in seen:
            error("duplicate_semantic_block", "Semantic source unit appears more than once", node)
        seen.add(identity)
        refs = node.get("source_refs", []) or [node.get("source_ref", {})]
        if not refs or any("dom_order" not in r for r in refs) or refs[0].get("dom_order") != node["order"]:
            error("invalid_provenance", "Node order does not identify its first source reference", node)
        if [r.get("dom_order", -1) for r in refs] != sorted(r.get("dom_order", -1) for r in refs):
            error("invalid_provenance", "Coalesced references differ from source order", node)
        if parent and key < source_key(parent):
            error("invalid_order", "Semantic child appears in source before its parent", node)
        title_ref = node.get("title_source_ref")
        if title_ref and title_ref not in refs:
            error("invalid_provenance", "Merged title lost its source reference", node)
        title_spans = node.get("title_source_spans", [])
        for span in title_spans:
            if span["source_ref"] not in refs or not 0 <= span["start"] < span["end"] <= len(node.get("title") or ""):
                error("invalid_provenance", "Merged title span lost its source reference or text bounds", node)
        if title_spans and any(node["title"][a["end"]:b["start"]].strip() for a, b in zip(title_spans, title_spans[1:])):
            error("invalid_provenance", "Merged title has meaningful text without a source span", node)
        legal_parents = [a for a in ancestors if a["type"] in LEVELS]
        if kind in LEVELS:
            counts["legal_hierarchy"][COUNTERS[kind]] += 1
            legal_positions.append(key)
            body_events.append((key, node, legal_parents, list_scope))
            if in_cell:
                error("invalid_table_parent", "A data-table cell contains asserted document hierarchy", node)
            if not any(a["type"] == "body" for a in ancestors):
                error("invalid_hierarchy", "Legal hierarchy node is outside document body", node)
            if legal_parents and LEVELS[kind] <= LEVELS[legal_parents[-1]["type"]]:
                error("invalid_parent", "Legal hierarchy contains a same/higher-level child", node)
            required = "article" if kind == "clause" else "clause" if kind == "point" else None
            unresolved = node.get("parent_status") == "unresolved"
            valid_parent = any(a["type"] == required and a.get("parent_status") != "unresolved" for a in legal_parents)
            if not unresolved and required and not valid_parent:
                error("invalid_parent", f"Asserted {kind} lacks a valid {required} parent", node)
        if node.get("parent_status") == "unresolved":
            counts["unresolved"]["orphan_nodes"] += 1
        if node.get("candidate_role"):
            counts["unresolved"]["numbered_candidates"] += 1
        if kind == "annex":
            counts["annex_hierarchy"]["annexes"] += 1
            if not parent or parent["type"] != "annexes":
                error("invalid_parent", "Annex must belong to the document annexes section", node)
        if kind in {"numbered_section", "numbered_item"}:
            counts["annex_hierarchy"]["numbered_sections" if kind == "numbered_section" else "numbered_items"] += 1
            counts["annex_hierarchy"]["max_depth"] = max(counts["annex_hierarchy"]["max_depth"], node.get("level", 0))
            if not any(a["type"] == "annex" for a in ancestors):
                error("invalid_parent", "Annex numbering is outside its annex scope", node)
            path = node.get("number_path", [])
            parts = node.get("number", "").split(".")
            if not all(p.isdigit() for p in parts) or [int(p) for p in parts] != path or node.get("level") != len(path):
                error("invalid_hierarchy", "Generic number path differs from its source number", node)
            if kind == "numbered_item" and node.get("parent_status") != "unresolved":
                if not parent or parent.get("number") != node.get("parent_number") or parent.get("number_path") != path[:-1]:
                    error("invalid_parent", "Decimal numbered item lacks its exact prefix parent", node)
        if kind == "table" and node.get("table_kind") == "layout":
            error("layout_table_in_hierarchy", "Layout table must be represented by semantic document nodes", node)
        if kind == "table" and not in_cell and any(a["type"] == "body" for a in ancestors):
            body_events.append((key, node, legal_parents, list_scope))
        if kind in DOCUMENT_SECTIONS and (not parent or parent["type"] != "legal_document"):
            error("invalid_hierarchy", "Document section is not directly below legal_document", node)
        if kind == "legal_document" and parent:
            error("invalid_hierarchy", "Document root is nested inside another semantic node", node)
        if kind in DOCUMENT_SECTIONS:
            counts["document_sections"][kind] += 1
        layouts = {r["table_id"] for r in node.get("source_layouts", [])}
        layout = node.get("source_layout")
        if isinstance(layout, dict) and layout.get("table_id"):
            layouts.add(layout["table_id"])
        for identifier in layouts - layout_seen:
            counts["tables"]["layout"] += 1
            layout_seen.add(identifier)
        if kind == "table":
            counts["tables"][node["table_kind"]] += 1
            counts["unresolved"]["ambiguous_tables"] += node["table_kind"] == "ambiguous"
        next_depth = depth + (kind in LEVELS or kind in DOCUMENT_SECTIONS or kind in {"annex", "numbered_section", "numbered_item"})
        counts["max_depth"] = max(counts["max_depth"], next_depth)
        children = node.get("children", [])
        if [source_key(n) for n in children] != sorted(source_key(n) for n in children):
            error("invalid_order", "Semantic children differ from source order", node)
        # Content introduced after a later legal heading cannot belong to an
        # earlier sibling. Check source intervals, including coalesced titles.
        for child, following in zip(children, children[1:]):
            if maximum_source(child) > source_key(following):
                error("invalid_order", "Sibling subtrees overlap or cross their source boundary", child)
        for child in children:
            visit(child, ancestors + (node,), next_depth, node, in_cell,
                  list_scope + (key,) if kind == "list" else list_scope)
        for cell in node.get("cells", []):
            for child in cell.get("content", []):
                visit(child, ancestors + (node,), next_depth, node, True, list_scope)

    if document is None:
        counts.update(schema_valid=False, parent_child_valid=False, semantic_complete=False, status="invalid")
        return counts
    if document.get("type") != "legal_document":
        error("invalid_hierarchy", "Content root must be legal_document", document)
    children = document.get("children", [])
    if any(n["type"] not in DOCUMENT_SECTIONS for n in children):
        error("invalid_hierarchy", "Document root contains an ungrouped semantic node", document)
    if len({n["type"] for n in children}) != len(children):
        error("invalid_hierarchy", "Document contains repeated semantic sections", document)
    phases = {name: i for i, name in enumerate(SECTION_ORDER)}
    if [phases.get(n["type"], -1) for n in children] != sorted(phases.get(n["type"], -1) for n in children):
        error("invalid_hierarchy", "Document semantic sections cross their phase boundaries", document)
    layout_seen = set()
    visit(document)
    if legal_positions != sorted(legal_positions):
        error("invalid_order", "Legal hierarchy traversal differs from source order", document)
    stack = []
    for _, node, legal_parents, scope in sorted(body_events, key=lambda e: e[0]):
        # A legal list item stops being active when traversal leaves its list.
        stack = [(n, s) for n, s in stack if scope[:len(s)] == s]
        if node["type"] in LEVELS:
            while stack and LEVELS[stack[-1][0]["type"]] >= LEVELS[node["type"]]:
                stack.pop()
            stack.append((node, scope))
        elif stack and (not legal_parents or source_key(legal_parents[-1]) != source_key(stack[-1][0])):
            error("invalid_table_parent", "Table does not belong to the active legal unit at its source position", node)
    structural_errors = any(i["severity"] in {"error", "fatal"} for i in quality.issues)
    counts["semantic_complete"] = (text_preserved and not structural_errors and counts["order_valid"] and counts["parent_child_valid"]
                                   and not any(counts["unresolved"].values()) and not any(i["severity"] == "warning" for i in quality.issues))
    counts["status"] = ("invalid" if structural_errors or not text_preserved or not counts["order_valid"] or not counts["parent_child_valid"]
                        else "valid" if counts["semantic_complete"] else "valid_with_warnings")
    return counts


def maximum_source(node):
    positions = [source_key(node)]
    positions.extend((r["dom_order"], 0) for r in node.get("source_refs", []))
    positions.extend(maximum_source(n) for n in node.get("children", []))
    for cell in node.get("cells", []):
        positions.append((cell["order"], 0))
        positions.extend(maximum_source(n) for n in cell.get("content", []))
    return max(positions)


def format_hierarchy(document):
    """Readable audit tree; includes content units without duplicating text JSON."""
    lines = [document["type"]]

    def branch(node, prefix, last):
        label = node["type"]
        if node.get("number"):
            label += " " + node["number"]
        if node.get("parent_status"):
            label += " [" + node["parent_status"] + "]"
        lines.append(prefix + ("└── " if last else "├── ") + label)
        children = node.get("children", [])
        for i, child in enumerate(children):
            branch(child, prefix + ("    " if last else "│   "), i == len(children) - 1)

    for i, child in enumerate(document["children"]):
        branch(child, "", i == len(document["children"]) - 1)
    return "\n".join(lines)
