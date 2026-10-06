"""Second-pass inference and repair of source-backed preliminary semantic nodes.

This pass owns no HTML parser and invents no legal labels or missing parents.
It uses siblings, source order, heading evidence, sequences and semantic scope.
"""
from __future__ import annotations

import re
import unicodedata

from .legal_hierarchy import (DOCUMENT_TYPES, LEVELS, TEXT_TYPES, candidate, container,
                              legal_node, normalized_scan, opening_role, closing_role,
                              is_formula, short_heading, slice_unit, source_key)
from .table_semantics import FORM_HEADING, PLACEHOLDER, refine_table_context

NUMBER = re.compile(r"^(\d+(?:\.\d+)*)([.)]?)(?=\s|$)\s*")
ROMAN = re.compile(r"M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})$", re.I)
NOTE = re.compile(r"^\(?\s*(?:Ban hành kèm theo|Kèm theo)\b", re.I)
FIELD = re.compile(r"^(?:\d+[.)]?\s+)?(?:Tên (?:cơ quan|đơn vị|tổ chức|báo cáo)|Địa chỉ|Điện thoại|Email|Số hiệu|Tọa độ|Tác giả)\b", re.I)


def walk(nodes, ancestors=()):
    for node in nodes:
        yield node, ancestors
        yield from walk(node.get("children", []), ancestors + (node,))
        for cell in node.get("cells", []):
            yield from walk(cell.get("content", []), ancestors + (node, cell))


def annex_candidate(block):
    if block["type"] not in TEXT_TYPES:
        return None
    text = block.get("text", "")
    scan, offsets = normalized_scan(text)
    start = re.match(r"^Phụ\s+lục(?=\s|$)", scan, re.I)
    if not start:
        return None
    rest = scan[start.end():]
    if re.match(r"\s*(?:này|kèm theo tài liệu|của|được|tại)\b", rest, re.I):
        return None
    numbered = re.match(r"\s+(?:số\s+)?(\d+|[IVXLCDM]+)", rest, re.I)
    if numbered:
        end = start.end() + numbered.end()
        number = numbered[1]
        if number.isalpha():
            while number and not ROMAN.fullmatch(number):
                number = number[:-1]
                end -= 1
            if not number:
                return None
        if scan[end:].startswith(".") and re.match(r"\.{2,}|…", scan[end:]):
            return None  # A blank 'PHỤ LỤC SỐ....' on a cover is not an annex boundary.
        remainder = scan[end:]
        if not remainder.startswith("\n") and re.match(r"\s+(?:của|này|được|tại)\b", remainder, re.I):
            return None  # A leading appendix citation in prose is not a boundary.
        return {"number": text[offsets[end - len(number)]:offsets[end]], "label_end": offsets[end]}
    if re.match(r"\s*số", rest, re.I):
        return None
    if rest.strip() and not rest.startswith("\n") and not (block.get("heading_evidence") and rest.strip().isupper()):
        return None
    return {"number": None, "label_end": offsets[start.end()]}


def append_title(node, paragraph):
    text = paragraph["text"]
    previous = node.get("title") or ""
    if previous and "title_source_spans" not in node:
        node["title_source_spans"] = [{"start": 0, "end": len(previous),
            "source_ref": node.get("title_source_ref", node["source_ref"]),
            "source_offset": node.get("title_source_offset", node.get("_title_offset", 0))}]
    start = len(previous) + (1 if previous else 0)
    node["title"] = previous + ("\n" if previous else "") + text
    if previous:
        node["title_source_spans"].append({"start": start, "end": start + len(text),
            "source_ref": paragraph["source_ref"], "source_offset": paragraph.get("source_offset", 0)})
    else:
        node["title_source_ref"] = paragraph["source_ref"]
        node["title_source_offset"] = paragraph.get("source_offset", 0)
    refs = node.setdefault("source_refs", [node["source_ref"]])
    if paragraph["source_ref"] not in refs:
        refs.append(paragraph["source_ref"])
    node["title_evidence"] = "adjacent_heading"
    if paragraph.get("references"):
        node.setdefault("references", []).extend(paragraph["references"])
    if paragraph.get("annotations"):
        node.setdefault("title_annotations", []).extend({**a, "start": start + a["start"], "end": start + a["end"]} for a in paragraph["annotations"])


def refine_titles(node):
    children = node.get("children", [])
    if node["type"] in {"part", "chapter", "section", "subsection", "article"}:
        while children and children[0]["type"] in TEXT_TYPES:
            text_node = children[0]
            text = text_node.get("text", "")
            if not text or candidate(text_node) or opening_role(text_node) or closing_role(text_node) or is_formula(text_node) or annex_candidate(text_node):
                break
            separate = source_key(text_node) > source_key(node)
            compatible = node.get("_scope") is not None and node.get("_scope") == text_node.get("_scope")
            emphasized = bool(text_node.get("heading_evidence") and node.get("heading_evidence"))
            aligned = node.get("_alignment") == text_node.get("_alignment") == "center"
            structural = bool(node["type"] != "article" and text.isupper())
            after = children[1] if len(children) > 1 else None
            bare = not node.get("title") and separate
            inline_heading = bool(node.get("heading_evidence") and text_node["order"] == node["order"] and
                                  after and after["type"] == "clause" and not re.search(r"[;.!?]$", text))
            if not separate or not compatible or len(text) > 600 or not (emphasized or aligned or structural or
                    inline_heading or bare and short_heading(text) and after and after["type"] in {"clause", "numbered_paragraph"}):
                break
            if node.get("title") and not (emphasized or aligned or structural):
                break
            # A separated source block with heading emphasis can have ellipses.
            if not (emphasized or aligned or structural or inline_heading) and not short_heading(text):
                break
            append_title(node, children.pop(0))
            if inline_heading:
                node["title_evidence"] = "heading_markup_and_child_structure"
    for child in children:
        refine_titles(child)


def flatten_article_children(children):
    for node in children:
        if node["type"] in {"clause", "point"}:
            nested = node["children"]
            node["children"] = []
            yield node
            yield from flatten_article_children(nested)
        else:
            yield node


def clause_scores(units, article):
    numbered = [(i, n) for i, n in enumerate(units) if n["type"] in {"numbered_paragraph", "clause"} and n.get("number", "").isdigit()]
    scores = {}
    for index, (i, node) in enumerate(numbered):
        if node["type"] != "numbered_paragraph":
            continue
        evidence = {"article_parent": 0.35}
        value = int(node["number"])
        previous = numbered[index - 1][1] if index else None
        following = numbered[index + 1][1] if index + 1 < len(numbered) else None
        def compatible_between(start, end):
            return not any(n["type"] in {"table", "list", "form", "annex"} for n in units[start + 1:end])
        if previous and int(previous["number"]) + 1 == value and compatible_between(numbered[index - 1][0], i):
            evidence["previous_sequential_number"] = 0.25
        if following and int(following["number"]) == value + 1 and compatible_between(i, numbered[index + 1][0]):
            evidence["next_sequential_number"] = 0.25
        if "previous_sequential_number" in evidence or "next_sequential_number" in evidence:
            evidence["multiple_sibling_counters"] = 0.15
        end = numbered[index + 1][0] if following else len(units)
        following_units = units[i + 1:end]
        boundary = next((j for j, n in enumerate(following_units) if n["type"] in {"table", "list", "form", "annex"}), len(following_units))
        points = [n.get("number", "").casefold() for n in following_units[:boundary] if n["type"] == "point"]
        if "a" in points:
            evidence["following_point_a"] = 0.30
        if "b" in points:
            evidence["following_point_b"] = 0.20
        if node.get("heading_evidence") and any(n.get("heading_evidence") == node["heading_evidence"] for _, n in numbered if n is not node):
            evidence["compatible_heading_style"] = 0.10
        text = node.get("text", "")
        contradiction = bool(FIELD.match(text) and PLACEHOLDER.search(text))
        procedural = bool(re.match(r"^\d+[.)]\s*(?:Bước\b|Thao tác\b)", text, re.I))
        introductory = " ".join([article.get("title") or ""] + [n.get("text", "") for n in units[:i] if n["type"] == "paragraph"])
        procedural_context = bool(re.search(r"(?:các bước|trình tự thao tác)\s*:\s*$", introductory, re.I))
        if procedural_context:
            evidence["explicit_procedural_list_context"] = -0.35
            contradiction = True
        if contradiction:
            evidence["form_field"] = -0.35
        if procedural:
            evidence["procedural_steps"] = -0.30
        scores[i] = (round(min(1.0, max(0.0, sum(evidence.values()))), 2), evidence, contradiction)
    return scores


def refine_article(article):
    refine_legal_lists(article, article)
    units = sorted(flatten_article_children(article["children"]), key=source_key)
    scores = clause_scores(units, article)
    for i, (score, evidence, contradiction) in scores.items():
        node = units[i]
        if score >= 0.70 and not contradiction:
            marker = candidate({**node, "type": "paragraph"})
            promoted = legal_node(node, marker)
            promoted.update(evidence="second_pass_structural_inference",
                            promotion_evidence={"score": score, "signals": evidence})
            for key in ("candidate_role", "confidence", "ambiguous"):
                promoted.pop(key, None)
            units[i] = promoted
        elif score >= 0.45 and not contradiction:
            node.update(candidate_role="clause", confidence=score,
                        candidate_evidence={"score": score, "signals": evidence})
        else:
            node.pop("candidate_role", None)
            node.pop("confidence", None)
    article["children"] = []
    stack = [("article", article)]
    for node in units:
        kind = node["type"]
        if kind in {"clause", "point"}:
            while LEVELS[stack[-1][0]] >= LEVELS[kind]:
                stack.pop()
            required = "article" if kind == "clause" else "clause"
            if any(k == required and n.get("parent_status") != "unresolved" for k, n in stack):
                node.pop("parent_status", None)
            else:
                node["parent_status"] = "unresolved"
            stack[-1][1]["children"].append(node)
            stack.append((kind, node))
        else:
            if kind == "numbered_paragraph":
                # An unpromoted source counter cannot silently inherit the
                # preceding clause and make its following points look resolved.
                stack = [("article", article)]
            stack[-1][1]["children"].append(node)


def refine_legal_lists(node, article, clause_context=False):
    """Use source counters and child points inside HTML lists, keeping scopes.

    The list wrapper remains content; it never becomes a fabricated clause.
    Lists already under a clause cannot introduce a same-level legal child.
    """
    clause_context |= node["type"] == "clause"
    if node["type"] == "list" and not clause_context:
        units, sources = [], {}
        for item in node["children"]:
            first = item["children"][0] if item.get("children") and item["children"][0]["type"] == "paragraph" else item
            marker = candidate({**first, "type": "paragraph"}) if first.get("text") else None
            if item["type"] == "list_item" and marker and marker["kind"] == "clause":
                index = len(units)
                units.append({**first, "type": "numbered_paragraph", "number": marker["number"]})
                sources[index] = item, first, marker
                # Explicit point labels are source evidence despite an HTML
                # list wrapper; data-table counters stay behind a barrier.
                units.extend(n for n, parents in walk(item.get("children", [])) if n["type"] in {"point", "table"} and
                             not any(p.get("type") == "table" for p in parents))
            elif item["type"] == "clause":
                units.append(item)
        context = {**article, "title": (article.get("title") or "") + " ".join(n.get("text", "") for n in article["children"]
                    if n["type"] == "paragraph" and source_key(n) < source_key(node))}
        scores = clause_scores(units, context)
        promoted = 0
        for index, (item, first, marker) in sources.items():
            score, evidence, contradiction = scores[index]
            if score >= .70 and not contradiction:
                following = item["children"][1:] if first is not item else item.get("children", [])
                converted = legal_node(first, marker)
                converted["children"].extend(following)
                if first is not item:
                    converted.update(order=item["order"], source_ref=item["source_ref"], source_refs=[item["source_ref"], first["source_ref"]])
                converted.update(evidence="second_pass_structural_inference",
                                 promotion_evidence={"score": score, "signals": {**evidence, "html_list_scope": True}})
                item.clear()
                item.update(converted)
                promoted += 1
            elif score >= .45 and not contradiction:
                item.update(candidate_role="clause", confidence=score, candidate_evidence={"score": score, "signals": evidence})
        if sources and promoted == len(sources):
            for field in ("candidate_role", "confidence", "candidate_evidence"):
                node.pop(field, None)
    if node["type"] == "point" and clause_context:
        node.pop("parent_status", None)
    for child in node.get("children", []):
        if child["type"] != "table":
            refine_legal_lists(child, article, clause_context)


def number_candidate(node):
    if node["type"] not in TEXT_TYPES | {"numbered_paragraph"}:
        return None
    match = NUMBER.match(node.get("text", ""))
    if not match or (not match[2] and "." not in match[1]):
        return None
    path = [int(n) for n in match[1].split(".")]
    tail = node["text"][match.end():]
    if len(path) > 1 and (any(len(n) >= 3 and n.startswith("0") for n in match[1].split(".")[1:]) or re.match(r"(?:kg|km|m2|m3|tấn|ha|%)(?:\s|$)", tail, re.I)):
        return None
    return match, path


def numbered_node(node, marker, path):
    tail = slice_unit(node, marker.end())
    result = {k: v for k, v in node.items() if k not in {"text", "children", "annotations", "candidate_role", "confidence"}}
    result.update(type="numbered_section" if len(path) == 1 else "numbered_item",
                  number=marker[1], number_path=path, level=len(path),
                  label=node["text"][:marker.end()].rstrip(), title=None, text=tail["text"], children=[])
    if tail.get("annotations"):
        result["annotations"] = tail["annotations"]
    if len(path) == 1 and short_heading(tail["text"]) and node.get("heading_evidence"):
        result.update(title=tail["text"], text="")
        if result.get("annotations"):
            result["title_annotations"] = result.pop("annotations")
    if len(path) > 1:
        result["parent_number"] = marker[1].rsplit(".", 1)[0]
    return result


def refine_annex(annex, quality):
    from .form_refinement import form_boundary, make_form
    blocks = annex["children"]
    heading = blocks.pop(0)
    marker = annex.pop("_annex_marker")
    end = marker["label_end"]
    title = heading.get("text", "")[end:].strip()
    annex["_title_offset"] = end + len(heading["text"][end:]) - len(heading["text"][end:].lstrip())
    annex.update(label=heading["text"][:end], title=title or None, children=[])
    annex.update({k: v for k, v in heading.items() if k in {"heading_evidence", "_scope", "_alignment", "references", "source_identifiers"}})
    annex["source_refs"] = [heading["source_ref"]]
    if title:
        tail = slice_unit(heading, end)
        if tail.get("annotations"):
            annex["title_annotations"] = tail["annotations"]
    elif blocks and blocks[0]["type"] in TEXT_TYPES and not NOTE.match(blocks[0].get("text", "")):
        proposed = blocks[0]
        if len(proposed.get("text", "")) <= 600 and (proposed.get("heading_evidence") or proposed.get("text", "").isupper()) and not form_boundary(proposed):
            append_title(annex, blocks.pop(0))
    current_form = None
    active = None
    prefix_nodes = {}
    for index, node in enumerate(blocks):
        text = node.get("text", "")
        boundary = form_boundary(node, active=current_form is not None) if node["type"] in TEXT_TYPES else None
        if boundary:
            current_form = make_form(node, boundary)
            annex["children"].append(current_form)
            active, prefix_nodes = None, {}
            continue
        target = current_form or active or annex
        if node["type"] == "table":
            refine_table_context(node, quality, annex=True,
                form=current_form is not None or bool(FORM_HEADING.match(annex.get("title") or "")) or bool(re.match(r"^MẪU\b", annex.get("title") or "", re.I)))
            target["children"].append(node)
            continue
        if NOTE.match(text):
            node["type"] = "annex_note"
        elif current_form and re.match(r"^Phụ\s+lục", text, re.I):
            node["type"] = "annex_heading"
        elif current_form and FIELD.match(text) and PLACEHOLDER.search(text):
            node.update(type="form_field", field_kind="input")
        else:
            marker_path = number_candidate(node)
            if marker_path:
                match, path = marker_path
                if current_form and len(path) == 1:
                    # Form counters are candidates, not asserted input fields
                    # or annex hierarchy. The scoped form pass owns them.
                    pass
                else:
                    numbered = numbered_node(node, match, path)
                    parent_number = numbered.get("parent_number")
                    if parent_number:
                        parent = prefix_nodes.get(parent_number)
                        if parent is not None and source_key(parent) < source_key(numbered):
                            previous = [n for n in parent["children"] if n.get("number_path", [])[:-1] == path[:-1] and n.get("number_path")]
                            if previous and previous[-1]["number_path"][-1] >= path[-1]:
                                target = current_form or annex
                                numbered.update(parent_status="unresolved", unresolved_reason="numbering_sequence_conflict")
                            else:
                                target = parent
                        else:
                            target = current_form or annex
                            numbered["parent_status"] = "unresolved"
                            numbered["unresolved_reason"] = "prefix_parent_missing_in_current_annex_scope"
                    else:
                        target = current_form or annex
                    target["children"].append(numbered)
                    # A new ancestor invalidates later branches with a different
                    # prefix; stale parents cannot span a stronger numbered boundary.
                    prefix_nodes = {k: n for k, n in prefix_nodes.items() if len(k.split('.')) < len(path) and
                                    (numbered["number"] == k or numbered["number"].startswith(k + '.'))}
                    prefix_nodes[numbered["number"]] = numbered
                    active = numbered
                    continue
        boundary = candidate(node)
        if not current_form and boundary and boundary["explicit"] and boundary["kind"] in {"part", "chapter", "section", "subsection"}:
            node["type"] = "annex_heading"
            active, prefix_nodes, target = None, {}, annex
        if current_form:
            bare_note = re.match(r"^(\d+)\s+(.+)", text)
            neighboring = [b.get("text", "") for b in blocks[max(0, index - 1):index + 2] if b is not node]
            if bare_note and (node.get("_note_style") or FIELD.match(text) and any(re.match(r"^\d+\s+", t) for t in neighboring)):
                node.update(type="footnote", marker=bare_note[1])
            elif node.get("_note_style") or re.match(r"^(?:Ghi chú|Chú thích|Hướng dẫn)\s*:", text, re.I):
                node["type"] = "note"
        target["children"].append(node)


def group_dash_lists(node):
    children = node.get("children", [])
    grouped, i = [], 0
    while i < len(children):
        first = children[i]
        match = re.match(r"^([-–—•])\s+\S", first.get("text", "")) if first["type"] in TEXT_TYPES else None
        run = []
        if match:
            while i + len(run) < len(children):
                item = children[i + len(run)]
                if item["type"] not in TEXT_TYPES or not re.match(r"^" + re.escape(match[1]) + r"\s+\S", item.get("text", "")):
                    break
                run.append(item)
        if len(run) >= 2:
            listing = container("list", first)
            listing.update(list_kind="unordered", style="dash", numbering={})
            for item in run:
                item.update(type="list_item", marker=match[1])
            listing["children"] = run
            grouped.append(listing)
            i += len(run)
        else:
            grouped.append(first)
            i += 1
    node["children"] = grouped
    for child in grouped:
        group_dash_lists(child)


def remove_page_artifacts(document, quality, root):
    candidates = [(n, parents) for n, parents in walk([document]) if re.fullmatch(r"\d{1,4}", n.get("text", "")) and
                  n.get("_page_edge") and n.get("_page") and not any(p.get("type") in LEVELS or p.get("type") in {"annex", "form", "table"} for p in parents)]
    plausible = [(n, p) for n, p in candidates if str(int(n["text"])) == str(n["_page"].get("number"))]
    if len({n["_page"]["scope"] for n, _ in plausible}) < 2:
        return
    sources = {n.dom_order: n for n in root.find()}
    for node, parents in plausible:
        source = sources.get(node["order"])
        if source and not node.get("source_offset") and source.text() == node["text"]:
            quality.ignore(source, "page_number")
            parents[-1]["children"].remove(node)


def final_structural_issues(document, quality):
    codes = {"orphan_point", "orphan_clause", "ambiguous_clause_candidate", "duplicate_legal_number", "possible_page_number"}
    quality.issues[:] = [i for i in quality.issues if i["code"] not in codes]
    seen = set()
    for node, parents in walk([document]):
        kind = node["type"]
        if node.get("parent_status") == "unresolved":
            code = "orphan_numbered_item" if kind in {"numbered_section", "numbered_item"} else f"orphan_{kind}"
            details = {"reason": node.get("unresolved_reason", "no_source_backed_compatible_parent"),
                       "number": node.get("number"), "parent_number": node.get("parent_number")}
            quality.add(code, "Source node retained with unresolved parent; inspect its source scope and preceding labels", node["source_ref"], details=details)
        if node.get("candidate_role") == "clause":
            quality.add("ambiguous_clause_candidate", "Numbered source unit has insufficient or contradictory evidence for clause promotion", node["source_ref"], details=node.get("candidate_evidence"))
        if kind in LEVELS:
            parent = next((p for p in reversed(parents) if p.get("type") in LEVELS or p.get("type") in {"body", "list"}), None)
            key = (source_key(parent) if parent else None, kind, node.get("number"))
            if key in seen:
                quality.add("duplicate_legal_number", "Repeated legal number retained in source order", node["source_ref"])
            seen.add(key)
        if kind in TEXT_TYPES and re.fullmatch(r"\d+", node.get("text", "")) and not any(p.get("type") in {"annex", "form", "table"} for p in parents):
            quality.add("possible_page_number", "Bare source number retained; page-transition evidence is insufficient to remove it", node["source_ref"])


def refine_document(document, quality, root):
    from .form_refinement import refine_forms
    for section in document["children"]:
        if section["type"] == "title_block":
            children = []
            for node in section["children"]:
                scan, offsets = normalized_scan(node.get("text", ""))
                prefix = re.match(r"^(?:" + DOCUMENT_TYPES + r")(?=\s)", scan)
                if prefix and scan[prefix.end():].strip():
                    heading = slice_unit(node, 0, offsets[prefix.end()])
                    heading["type"] = "document_type_heading"
                    title = slice_unit(node, offsets[prefix.end()])
                    title["type"] = "document_title"
                    children.extend([heading, title])
                else:
                    children.append(node)
            section["children"] = children
        elif section["type"] == "annexes":
            for annex in section["children"]:
                refine_annex(annex, quality)
    refine_titles(document)
    articles = [n for n, parents in walk([document]) if n["type"] == "article" and not any(p.get("type") in {"table", "annex"} for p in parents)]
    for article in articles:
        refine_article(article)
    for node, parents in walk([document]):
        if node["type"] == "table" and not any(p.get("type") == "annex" for p in parents):
            refine_table_context(node, quality)
    refine_forms(document)
    for section in document["children"]:
        if section["type"] in {"body", "annexes"}:
            group_dash_lists(section)
    remove_page_artifacts(document, quality, root)
    final_structural_issues(document, quality)
    return document
