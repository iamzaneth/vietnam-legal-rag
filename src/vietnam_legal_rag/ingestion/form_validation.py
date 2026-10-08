"""Independent form checks and a source-scoped audit of structured paragraphs."""
from __future__ import annotations

import re

from .form_refinement import ALPHA, BIBLIOGRAPHY, DIGIT, SYMBOL, NOTE_HEADING, consecutive, scan

STRUCTURED = re.compile(r"^(?:\d+[.)]\s+|\d+[-/]\s+(?=[^\d\s])|\d+\.\d+|[a-zđ][.)/]\s+|[-–—•+]\s+|↩$)", re.I)
NOTE_NUMBER = re.compile(r"^(\d+)(?:[.)]\s+|\s+)\S")
FORM_NODE_PROPERTIES = ("field_name", "field_kind", "field_evidence", "value_text")


def walk(nodes, ancestors=()):
    for node in nodes:
        yield node, ancestors
        yield from walk(node.get("children", []), ancestors + (node,))
        for cell in node.get("cells", []):
            yield from walk(cell.get("content", []), ancestors + (node, cell))


def source_text(node):
    return (node.get("label", "") + " " + (node.get("text") or "")).strip()


def numbered_note(node):
    if node["type"] == "footnote":
        return node.get("marker")
    match = NOTE_NUMBER.match(source_text(node))
    return match[1] if match else None


def note_inconsistencies(document):
    problems = []
    for parent, _ in walk([document]):
        children = parent.get("children", [])
        i = 0
        while i < len(children):
            run, previous = [], None
            j = i
            while j < len(children):
                marker = numbered_note(children[j])
                if not marker or previous and int(marker) != int(previous) + 1:
                    break
                run.append(children[j]); previous = marker; j += 1
            preceding = children[i - 1] if i else None
            explicit = parent["type"] in {"note", "footnote_group"} or preceding and NOTE_HEADING.fullmatch(scan(preceding.get("text")))
            mixed = any(n["type"] == "footnote" for n in run) and any(n["type"] != "footnote" for n in run)
            if len(run) >= 2 and (mixed or explicit and any(n["type"] != "footnote" for n in run)):
                problems.append({"source_ref": run[0]["source_ref"], "markers": [numbered_note(n) for n in run],
                                 "types": [n["type"] for n in run]})
            i = j if j > i else i + 1
    return problems


def split_forms(document):
    candidates = []
    for parent, _ in walk([document]):
        previous = None
        for node in parent.get("children", []):
            if node["type"] != "form":
                continue
            if previous and previous.get("number") and not node.get("number"):
                candidates.append({"source_ref": node["source_ref"], "preceding_form_number": previous["number"]})
            previous = node
    return candidates


def bibliography_misclassified(document):
    problems = []
    for node, ancestors in walk([document]):
        form = next((a for a in reversed(ancestors) if a.get("type") == "form"), None)
        if node["type"] == "form_field" and form and BIBLIOGRAPHY.search(scan(form.get("title") or form.get("text"))) and (node.get("number") or DIGIT.match(node.get("text") or "")):
            problems.append(node)
    return problems


def symbol_sequence(siblings, index):
    """Audit serialized source markers independently of the list builder.

    Both sides may be generic paragraphs or prematurely classified fields.
    A nested marker is not isolated just because prose separates it from its
    parent. Semantic boundaries and unrelated prose still end flat runs.
    """
    text = source_text(siblings[index])
    match = SYMBOL.match(text)
    if not match or not any(c.isalpha() for c in text[match.end():]):
        return False
    for step in (-1, 1):
        position, gap = index + step, 0
        while 0 <= position < len(siblings):
            node = siblings[position]
            other_text = source_text(node)
            other = SYMBOL.match(other_text)
            if node["type"] not in {"paragraph", "heading", "unknown", "numbered_paragraph", "form_field"}:
                break
            if other:
                if not any(c.isalpha() for c in other_text[other.end():]):
                    break
                # A plus can follow its dash parent. A preceding standalone
                # plus followed by a dash is a boundary, not nested evidence.
                mixed = (match[1] == "+" and step == -1 and other[1] != "+" or
                         match[1] != "+" and step == 1 and other[1] == "+")
                same = match[1] == other[1]
                lead_in = any(t.rstrip().endswith(":") for t in (text, other_text))
                # Plus-only topic lists may also have unmarked explanatory
                # paragraphs. Do not blanket-justify those sequences either.
                plus_topic = same and match[1] == "+" and any(len(t.split()) <= 25 for t in (text, other_text))
                if (same or mixed) and (not gap or mixed or lead_in or plus_topic):
                    return True
                break
            if (node["type"] != "paragraph" or node.get("heading_evidence") or
                    STRUCTURED.match(other_text) or NOTE_HEADING.fullmatch(scan(other_text))):
                break
            gap += 1; position += step
    return False


def structured_paragraphs(document):
    """Every retained marker gets evidence or remains an actionable candidate.

    A singleton separated by a table/list is legitimate prose: adjacency alone
    does not justify grouping across that boundary. Sequential siblings are
    unresolved and must be refined instead of receiving a blanket exception.
    """
    audit = []
    for node, ancestors in walk([document]):
        if node["type"] != "paragraph":
            continue
        siblings = ancestors[-1].get("children", ancestors[-1].get("content", [])) if ancestors else []
        index = next((i for i, n in enumerate(siblings) if n is node), -1)
        tight_recipient = (index > 0 and siblings[index - 1]["type"] == "recipients" and
                           not siblings[index - 1].get("children") and
                           re.match(r"^[-–—•](?=[^\d\s])", node.get("text") or ""))
        if not STRUCTURED.match(node.get("text") or "") and not tight_recipient:
            continue
        neighboring = siblings[max(0, index - 1):index] + siblings[index + 1:index + 2] if index >= 0 else []
        scope = "table_cell" if any("cell_id" in a for a in ancestors) else "form" if any(a.get("type") == "form" for a in ancestors) else "annex" if any(a.get("type") == "annex" for a in ancestors) else "legal_body"
        reason, resolved = "insufficient_structural_evidence", False
        if tight_recipient:
            reason = "unresolved_recipient_marker"
        symbol = SYMBOL.match(node["text"])
        if symbol:
            if not any(c.isalpha() for c in node["text"][symbol.end():]):
                reason, resolved = "numeric_expression_without_list_body", True
            elif symbol_sequence(siblings, index):
                reason = "unresolved_symbol_sequence"
            else:
                reason, resolved = "isolated_marker_without_sequence_evidence", True
        for pattern, style in (() if symbol else ((ALPHA, "alpha"), (DIGIT, "digit"))):
            match = pattern.match(node["text"])
            if not match:
                continue
            sequential = any(n.get("type") == "paragraph" and (other := pattern.match(n.get("text") or "")) and
                             (consecutive(match[1], other[1], style) or consecutive(other[1], match[1], style)) for n in neighboring)
            if not sequential and style in {"dash", "alpha"}:
                reason, resolved = "isolated_marker_without_adjacent_sequence", True
            break
        audit.append({"order": node["order"], "source_ref": node["source_ref"], "text": node["text"], "scope": scope,
                      "reason": reason, "justified": resolved,
                      "neighboring_types": [n["type"] for n in neighboring]})
    return audit


def form_metrics(document):
    from .schema_cleanup import form_label_audit
    nodes = list(walk([document]))
    form_nodes = [n for n, _ in nodes if n["type"] in {"form_field", "form_subfield"}]
    kinds = {kind: sum(n["type"] == kind for n, _ in nodes) for kind in
             ("form", "form_field", "form_subfield", "form_placeholder", "footnote")}
    paragraphs = structured_paragraphs(document)
    return {"forms": kinds["form"], "fields": kinds["form_field"], "subfields": kinds["form_subfield"],
            "placeholders": kinds["form_placeholder"], "footnotes": kinds["footnote"],
            "placeholder_references": sum(len(n.get("placeholder_refs", [])) for n, _ in nodes),
            "unresolved_numbered_form_items": sum(p["scope"] == "form" and not p["justified"] for p in paragraphs),
            "split_form_candidates": len(split_forms(document)),
            "inconsistent_footnote_sequences": len(note_inconsistencies(document)),
            "bibliography_fields_misclassified": len(bibliography_misclassified(document)),
            "structured_table_cell_lists": sum(n["type"] == "list" and any("cell_id" in a for a in parents) for n, parents in nodes),
            "generic_structured_paragraphs": len(paragraphs),
            "form_nodes_missing_field_kind": sum("field_kind" not in n for n in form_nodes),
            "form_nodes_missing_field_evidence": sum("field_evidence" not in n for n in form_nodes),
            "suspicious_value_text": len(value_text_audit(document)),
            "semantic_empty_string_fields": sum(v == "" for n, _ in nodes for v in n.values() if isinstance(v, str)),
            "physical_empty_cells": sum(c.get("text") == "" and c.get("effective_text") == "" for n, _ in nodes for c in n.get("cells", [])),
            "unexplained_form_label_paragraphs": sum(not p["justified"] for p in form_label_audit(document)),
            "unexplained_structured_paragraphs": sum(not p["justified"] for p in paragraphs)}


def value_text_audit(document):
    """Values must be source values/blanks, rather than completion prompts."""
    from .schema_cleanup import short_label, FIELD_NAME, BLANK
    problems = []
    for node, _ in walk([document]):
        value = node.get("value_text")
        if node.get("type") not in {"form_field", "form_subfield"} or not value:
            continue
        reason = None
        if node.get("field_kind") == "instruction":
            reason = "instruction_in_value_text"
        elif value.rstrip().endswith(":"):
            reason = "prompt_in_value_text"
        elif (blank := re.match(r"[.…_\s]+(?:\(\d+\)[.…_\s]*)?", value)) and BLANK.search(blank[0]) and any(c.isalpha() for c in value[blank.end():]):
            reason = "placeholder_followed_by_prompt_or_prose"
        elif FIELD_NAME.fullmatch(scan(value)) and short_label(value) and node.get("field_kind") in {"input_label", "composite"} and not BLANK.search(value):
            reason = "input_label_in_value_text"
        if reason:
            problems.append({"order": node["order"], "source_ref": node["source_ref"],
                             "field_name": node.get("field_name"), "value_text": value, "reason": reason})
    return problems


def validate_forms(document, quality):
    metrics = form_metrics(document)
    from .schema_cleanup import form_label_audit
    labels = form_label_audit(document)
    for problem in value_text_audit(document):
        quality.add("suspicious_value_text", "Field value contains a prompt or completion instruction", problem["source_ref"], details=problem)
    metrics["unexplained_form_label_paragraphs"] = sum(not p["justified"] for p in labels)
    for item in labels:
        if not item["justified"]:
            quality.add("form_label_unresolved", "Source input label remains a paragraph in confirmed form context", item["source_ref"], details=item)
    for problem in note_inconsistencies(document):
        quality.add("inconsistent_footnote_sequence", "Adjacent explanatory note counters have inconsistent semantic roles", problem["source_ref"], details=problem)
    for problem in split_forms(document):
        quality.add("possible_split_form", "An unnumbered form follows a numbered form without a new source form-number boundary", problem["source_ref"], details=problem)
    for node in bibliography_misclassified(document):
        quality.add("bibliography_entry_as_form_field", "A numbered reference entry is asserted as a form field", node["source_ref"])
    audit = structured_paragraphs(document)
    for paragraph in audit:
        if not paragraph["justified"]:
            quality.add("structured_paragraph_unresolved", "Source marker remains generic; inspect its sequence and semantic scope", paragraph["source_ref"], details={"scope": paragraph["scope"], "reason": paragraph["reason"]})
    for node, ancestors in walk([document]):
        if node["type"] in {"form_field", "form_subfield"}:
            missing = [key for key in FORM_NODE_PROPERTIES if key not in node]
            if missing:
                quality.add("invalid_form_node", "Form field/subfield lacks required contract properties", node["source_ref"], "error", details={"missing_properties": missing})
        if node["type"] == "form_subfield" and not any(a.get("type") == "form_field" for a in ancestors):
            quality.add("invalid_parent", "Form subfield lacks a source-backed form field parent", node["source_ref"], "error")
        if node["type"] == "form" and node.get("title_source_ref"):
            matching = [n for n in node.get("children", []) if n["type"] == "form_title" and n["source_ref"] == node["title_source_ref"] and n.get("text") == node.get("title")]
            if len(matching) != 1:
                quality.add("invalid_provenance", "Derived form title must reference one matching source-backed displayed title", node["source_ref"], "error")
    metrics["semantic_complete"] = not any(metrics[k] for k in ("unresolved_numbered_form_items", "split_form_candidates", "inconsistent_footnote_sequences", "bibliography_fields_misclassified", "unexplained_structured_paragraphs", "unexplained_form_label_paragraphs", "suspicious_value_text", "semantic_empty_string_fields", "form_nodes_missing_field_kind", "form_nodes_missing_field_evidence")) and not any(i["severity"] in {"error", "fatal"} for i in quality.issues)
    return metrics, audit
