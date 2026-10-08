"""Keep explicit replacement quotations in their own counter scope.

Quoted counters are source list markers, not provisions of the enclosing act.
No missing article/clause is synthesized for a partial quotation.
"""
from __future__ import annotations

import re

from .legal_hierarchy import TEXT_TYPES, candidate, container
from .form_refinement import semantic_body


def quoted_marker(node):
    text = node.get("text") or ""
    opening = 1 if text.startswith(('"', '“')) else 0
    marker = candidate({**node, "type": "paragraph", "text": text[opening:]})
    if not marker:
        return None
    end = opening + marker["label_end"]
    if marker["explicit"]:
        end += len(re.match(r"[ \t]*[.:)]?", text[end:])[0])
    # semantic_body consumes group 1 as the source number and the complete
    # matched prefix as the displayed label, including a leading quote.
    pattern = re.compile(re.escape(text[:end]).replace(re.escape(marker["number"]),
                                                     "(" + re.escape(marker["number"]) + ")", 1))
    return marker, pattern.match(text)


def quotation(nodes, evidence="explicit_source_quotation", marker_function=quoted_marker):
    block = container("layout_block", nodes[0])
    block["evidence"] = evidence
    block.update({k: nodes[0][k] for k in ("_scope", "_source_layout") if k in nodes[0]})
    stack = []
    levels = {"part": 10, "chapter": 20, "section": 30, "subsection": 40,
              "article": 50, "clause": 60, "point": 70}
    for node in nodes:
        found = marker_function(node) if node["type"] in TEXT_TYPES else None
        if not found:
            (stack[-1][1]["children"] if stack else block["children"]).append(node)
            continue
        marker, match = found
        if evidence in {'emphasized_roman_body_outline', 'emphasized_roman_article_outline'} and node.get('heading_evidence'):
            upper = re.match(r'^([A-ZĐ])[.)]\s+', node.get('text') or '')
            prior_upper = next((item for depth, item in reversed(stack) if depth == 15), None)
            if upper and prior_upper and ord(upper[1]) == ord(prior_upper['number']) + 1:
                marker, match = {'number': upper[1], 'kind': 'uppercase_alpha', 'level': 15}, upper
        level = marker.get("level", levels.get(marker["kind"]))
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else block
        children = parent["children"]
        listing = children[-1] if children and children[-1]["type"] == "list" and children[-1].get("_quoted_level") == level else None
        if listing is None:
            listing = container("list", node)
            listing.update(list_kind="ordered", style="quoted_counter" if evidence == "explicit_source_quotation" else "local_counter", numbering={},
                           evidence=evidence, _quoted_level=level)
            children.append(listing)
        item = semantic_body(node, match, "list_item", number=True)
        item["evidence"] = "quoted_counter_in_independent_source_scope" if evidence == "explicit_source_quotation" else evidence
        listing["children"].append(item)
        stack.append((level, item))
    return block


def amendment_lead_in(node):
    text = node.get('text') or ''
    marker = candidate(node)
    return marker if marker and marker['kind'] == 'clause' and not marker['explicit'] and re.search(
        r'(?:sửa đổi|bổ sung|thay thế|amend|supplement|replace|add)\b', text, re.I) and re.search(
        r'(?:như sau|as follows)\s*:\s*$', text, re.I) else None


def scope_quotations(blocks, quality=None):
    output, index = [], 0
    while index < len(blocks):
        first = blocks[index]
        text = first.get("text") or ""
        previous = blocks[index - 1].get("text") or "" if index else ""
        supported = first["type"] in TEXT_TYPES and text.startswith(('"', '“')) and (
            quoted_marker(first) or re.search(r"(?:như sau|thành|thay bằng)\s*:\s*$", previous, re.I))
        end, quotes = index, 0
        previous_lead = amendment_lead_in(blocks[index - 1]) if index else None
        if supported:
            while end < len(blocks):
                node = blocks[end]
                next_lead = amendment_lead_in(node) if end > index else None
                # A missing closing quote cannot absorb the next explicitly
                # numbered amendment. Its actual boundary is kept, without
                # inventing punctuation or treating quoted clauses as outer
                # provisions.
                if previous_lead and next_lead and previous_lead['number'].isdigit() and next_lead['number'] == str(int(previous_lead['number']) + 1):
                    evidence = 'source_quotation_bounded_by_next_amendment'
                    output.append(quotation(blocks[index:end], evidence))
                    if quality is not None:
                        quality.add('incomplete_source_quotation', 'Source quotation lacks a closing mark before the next explicit amendment lead-in; local counters retained in source scope', first['source_ref'],
                                    details={'boundary_source_ref': node['source_ref'], 'outer_number': previous_lead['number']})
                    index = end
                    break
                if node["type"] not in TEXT_TYPES | {"table", "list", "separator"}:
                    break
                display = node.get("text") or ""
                quotes += display.count('"') if text[0] == '"' else display.count('“') - display.count('”')
                balanced = quotes % 2 == 0 if text[0] == '"' else quotes == 0
                if balanced and re.search(r'["”]\s*[.;,]?\s*$', display):
                    output.append(quotation(blocks[index:end + 1]))
                    index = end + 1
                    break
                end += 1
            else:
                supported = False
            if index >= end and end > 0:
                continue
        output.append(first)
        index += 1
    return output


def scope_restarted_counters(blocks):
    """A counter restart beneath an explicit lead-in is a local enumeration.

    Require a complete adjacent sequence bounded by a new explicit legal
    label. Unbounded restarts remain available to the ambiguity validator.
    """
    output, index = [], 0
    while index < len(blocks):
        prior = blocks[index - 1] if index else None
        previous = candidate(prior) if prior else None
        first = candidate(blocks[index])
        supported = previous and previous["kind"] == "clause" and not previous["explicit"] and (
            previous["number"].isdigit() and int(previous["number"]) > 1 and
            (prior.get("text") or "").rstrip().endswith(":")) and first and (
            first["kind"] == "clause" and not first["explicit"] and first["number"] == "1")
        end = index
        run = []
        if supported:
            while end < len(blocks):
                marker = candidate(blocks[end])
                if not marker or marker["explicit"] or marker["kind"] != "clause" or marker["number"] != str(len(run) + 1):
                    break
                run.append(blocks[end]); end += 1
            boundary = candidate(blocks[end]) if end < len(blocks) else None
            if len(run) >= 2 and boundary and boundary["explicit"] and boundary["kind"] in {"article", "chapter", "section"}:
                wrapper = container("layout_block", run[0])
                wrapper["evidence"] = "counter_restart_under_explicit_lead_in"
                wrapper["children"] = quotation(run, evidence=wrapper["evidence"])["children"]
                output.append(wrapper); index = end; continue
        output.append(blocks[index]); index += 1
    return output


def outline_marker(node):
    text = node.get("text") or ""
    for pattern, kind, level in ((r"^([IVXLCDM]+)[.)]\s*", "roman", 10),
                                 (r"^([A-ZĐ])[.)]\s+", "uppercase_alpha", 15),
                                 (r"^(\d+(?:\.\d+)+)\.?\s*(?=[^\d\s])", "decimal", 30),
                                 (r"^(\d+)(?:[.)]\s*|[-/]\s+(?=[^\d\s]))", "digit", 20),
                                 (r"^([a-zđ])(?:[.)]\s*|/\s+)", "alpha", 100)):
        match = re.match(pattern, text)
        if match and (kind != 'uppercase_alpha' or node.get('heading_evidence')):
            return {"number": match[1], "kind": kind, "level": level + (match[1].count(".") if kind == "decimal" else 0)}, match
    return None


def scope_article_enumerations(blocks):
    """Retain source subdivisions without inventing absent legal levels.

    Two emphasized Roman headings establish an article-local outline. A
    consecutive alphabetic list directly under an article requires a colon
    lead-in and no preceding clause. Isolated points keep their diagnostics.
    """
    from .form_refinement import consecutive
    output, index, article, clause = [], 0, False, False
    while index < len(blocks):
        node = blocks[index]
        marker = candidate(node)
        if marker and marker["explicit"]:
            if marker["kind"] == "article":
                article, clause = True, False
            elif marker["kind"] in {"chapter", "section", "part", "subsection"}:
                article, clause = False, False
        if marker and marker["kind"] == "clause":
            clause = True
        outline = outline_marker(node) if article and node["type"] in TEXT_TYPES else None
        if outline and outline[0]["kind"] == "roman" and node.get("heading_evidence"):
            end = index
            while end < len(blocks):
                boundary = candidate(blocks[end])
                if end > index and boundary and boundary["explicit"] or blocks[end]["type"] not in TEXT_TYPES | {"table", "list", "separator"}:
                    break
                end += 1
            headings = [b for b in blocks[index:end] if b.get("heading_evidence") and
                        (m := outline_marker(b)) and m[0]["kind"] == "roman"]
            if len(headings) >= 2:
                output.append(quotation(blocks[index:end], "emphasized_roman_article_outline", outline_marker))
                index = end; continue
        if outline and outline[0]["kind"] == "alpha" and article and not clause and index and (
                (blocks[index - 1].get("text") or "").rstrip().endswith(":")):
            end, previous, marked = index, None, 0
            while end < len(blocks):
                following = blocks[end]
                m = outline_marker(following) if following["type"] in TEXT_TYPES else None
                if not m or m[0]["kind"] != "alpha" or previous and not consecutive(previous, m[0]["number"], "alpha"):
                    break
                previous = m[0]["number"]; marked += 1; end += 1
            if marked >= 2:
                output.append(quotation(blocks[index:end], "article_local_alpha_list_after_lead_in", outline_marker))
                index = end; continue
        output.append(node); index += 1
    return output


def scope_body_outlines(blocks):
    """Emphasized Roman subdivisions in article-free acts have local scope."""
    from .legal_hierarchy import closing_role
    from .semantic_refinement import annex_candidate
    output, index, article, annex, closing = [], 0, False, False, False
    while index < len(blocks):
        node = blocks[index]
        marker = candidate(node)
        if marker and marker['explicit']:
            article = marker['kind'] in {'article', 'clause', 'point'}
        annex |= bool(annex_candidate(node))
        closing |= bool(closing_role(node))
        outline = outline_marker(node) if not (article or annex or closing) and node['type'] in TEXT_TYPES else None
        if outline and outline[0]['kind'] == 'roman' and node.get('heading_evidence'):
            end = index + 1
            while end < len(blocks):
                following = blocks[end]
                boundary = candidate(following)
                if boundary and boundary['explicit'] or closing_role(following) or annex_candidate(following) or following['type'] not in TEXT_TYPES | {'table', 'list', 'separator'}:
                    break
                end += 1
            headings = [b for b in blocks[index:end] if b.get('heading_evidence') and
                        (m := outline_marker(b)) and m[0]['kind'] == 'roman']
            if len(headings) >= 2:
                output.append(quotation(blocks[index:end], 'emphasized_roman_body_outline', outline_marker))
                index = end
                continue
        output.append(node)
        index += 1
    return output


def scope_alpha_continuations(blocks):
    """Annex-local alphabetic lists may contain explanatory formula blocks."""
    from .form_refinement import consecutive
    output, index = [], 0
    while index < len(blocks):
        first = outline_marker(blocks[index]) if blocks[index]["type"] in TEXT_TYPES else None
        if not first or first[0]["kind"] != "alpha":
            output.append(blocks[index]); index += 1; continue
        end, accepted, marked, previous = index + 1, index + 1, 1, first[0]["number"]
        while end < len(blocks):
            node = blocks[end]
            marker = outline_marker(node) if node["type"] in TEXT_TYPES else None
            if marker:
                if marker[0]["kind"] != "alpha" or not consecutive(previous, marker[0]["number"], "alpha"):
                    break
                previous = marker[0]["number"]; marked += 1; accepted = end + 1
            elif node["type"] not in TEXT_TYPES | {"table", "layout_block", "list"} or node.get("heading_evidence") or candidate(node):
                break
            end += 1
        if marked >= 2:
            output.append(quotation(blocks[index:accepted], "annex_alpha_sequence_with_source_continuations", outline_marker))
            index = accepted
        else:
            output.append(blocks[index]); index += 1
    return output


def scope_contents(blocks):
    """Explicit contents headings scope citation entries, never legal bodies."""
    from .semantic_refinement import annex_candidate
    output, index = [], 0
    def entry(node):
        if node["type"] not in TEXT_TYPES:
            return None
        marker = candidate(node)
        if marker and marker["explicit"]:
            return {**marker, "kind": "contents", "level": 10}, quoted_marker(node)[1]
        marker = annex_candidate(node)
        if marker and marker["number"]:
            text, number = node["text"], marker["number"]
            pattern = re.compile(re.escape(text[:marker["label_end"]]).replace(re.escape(number), '(' + re.escape(number) + ')', 1) + r"[.:]?\s*")
            return {"kind": "contents", "number": number, "level": 10}, pattern.match(text)
        return None
    while index < len(blocks):
        node = blocks[index]
        end = index + 1
        if re.fullmatch(r"MỤC LỤC|TABLE OF CONTENTS", node.get("text") or "", re.I):
            while end < len(blocks) and entry(blocks[end]):
                end += 1
            if end - index > 2:
                node["type"] = "heading"
                wrapper = quotation(blocks[index + 1:end], "explicit_source_table_of_contents", entry)
                wrapper["children"].insert(0, node)
                wrapper.update(order=node["order"], source_ref=node["source_ref"])
                output.append(wrapper); index = end; continue
        output.append(node); index += 1
    return output


def scope_template_counters(blocks):
    output, index = [], 0
    while index < len(blocks):
        node = blocks[index]
        output.append(node); index += 1
        if node.get("evidence") != "explicit_article_heading_in_source_template":
            continue
        end = index
        while end < len(blocks) and blocks[end].get("evidence") != "explicit_article_heading_in_source_template" and blocks[end]["type"] not in {"annex_heading", "form_signature"}:
            end += 1
        counters = [m for b in blocks[index:end] if (m := candidate(b)) and m["kind"] == "clause" and not m["explicit"]]
        if len(counters) >= 2 and [m["number"] for m in counters] == [str(i + 1) for i in range(len(counters))]:
            output.append(quotation(blocks[index:end], "source_template_article_local_counters"))
            index = end
    return output
