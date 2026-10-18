"""Keep explicit replacement quotations in their own counter scope.

Quoted counters are source list markers, not provisions of the enclosing act.
No missing article/clause is synthesized for a partial quotation.
"""
from __future__ import annotations

import re

from vietnam_legal_rag.ingestion.semantics.hierarchy import DECIMAL_COUNTER, TEXT_TYPES, candidate, container, closing_role, slice_unit
from vietnam_legal_rag.ingestion.refinement.forms import semantic_body


def scope_terminal_notes(blocks, quality=None):
    """Bound unlinked terminal notes using literal markers and body references.

    Require an ordered series starting at one, with at least two preceding
    references. Bracketed placeholders or an isolated bracket number cannot
    start a note scope. The notes retain their actual source continuation.
    """
    pattern = re.compile(r'^(?:\d+(?=\[\d+\]))?\[(\d+)\]\s*(?=\S)')
    def note_marker(node):
        text = node.get('text') or ''
        match = pattern.match(text) if node['type'] in TEXT_TYPES else None
        repeated = re.match(r'^(\d+)(?=\[)', text)
        return match if match and (not repeated or repeated[1] == match[1] or
                                   repeated[1] == match[1] * 2) else None
    for index, first in enumerate(blocks):
        match = note_marker(first)
        if not match or match[1] != '1':
            continue
        positions = [(i, m) for i, node in enumerate(blocks[index:], index)
                     if (m := note_marker(node))]
        numbers = [int(m[1]) for _, m in positions]
        if len(numbers) < 2 or numbers != list(range(1, len(numbers) + 1)):
            continue
        earlier = ' '.join(node.get('text') or '' for node in blocks[:index])
        if not all('[' + str(number) + ']' in earlier for number in numbers[:2]):
            continue
        group = container('footnote_group', first)
        group['evidence'] = 'source_terminal_note_sequence_with_body_references'
        for position, (start, marker) in enumerate(positions):
            end = positions[position + 1][0] if position + 1 < len(positions) else len(blocks)
            repeated = re.match(r'^(\d+)(?=\[)', blocks[start].get('text') or '')
            if repeated and repeated[1] != marker[1] and quality is not None:
                quality.add('inconsistent_source_footnote_prefix',
                            'Source prefix repeats its bracketed note counter; literal marker retained without correction',
                            blocks[start]['source_ref'])
            note = semantic_body(blocks[start], marker, 'footnote')
            note['evidence'] = group['evidence']
            note['children'].extend(blocks[start + 1:end])
            tail = slice_unit(blocks[start], marker.end())
            opening = re.search(r'(?:như sau|as follows)\s*:\s*(["“])', tail['text'], re.I)
            if opening:
                lead = slice_unit(tail, 0, opening.start(1))
                note['text'] = lead['text']
                if lead.get('annotations'):
                    note['annotations'] = lead['annotations']
                else:
                    note.pop('annotations', None)
                note['children'].insert(0, slice_unit(tail, opening.start(1)))
            note['children'] = scope_quotations(note['children'], quality)
            group['children'].append(note)
        return blocks[:index] + [group]
    return blocks


def quoted_marker(node):
    text = node.get("text") or ""
    opening = 1 if text.startswith(('"', '“')) else 0
    composite = re.match(r'^(\d+\.[a-zđ])[.)]\s*', text[opening:], re.I)
    decimal = DECIMAL_COUNTER.match(text[opening:])
    marker = ({'kind': 'clause', 'number': composite[1], 'label_end': composite.end(), 'explicit': False}
              if composite else
              {'kind': 'decimal', 'number': decimal[1], 'label_end': decimal.end(), 'explicit': False,
               'level': 60 + decimal[1].count('.')}
              if decimal else candidate({**node, "type": "paragraph", "text": text[opening:]}))
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


def quotation(nodes, evidence="explicit_source_quotation", marker_function=quoted_marker, *, outline_boundaries=False):
    block = container("layout_block", nodes[0])
    block["evidence"] = evidence
    block.update({k: nodes[0][k] for k in ("_scope", "_source_layout") if k in nodes[0]})
    stack = []
    levels = {"part": 10, "chapter": 20, "section": 30, "subsection": 40,
              "article": 50, "clause": 60, "point": 70}
    for node in nodes:
        if outline_boundaries:
            from vietnam_legal_rag.ingestion.refinement.forms import form_component_boundary, form_global_boundary
            if form_component_boundary(node):
                minimum = 0 if form_global_boundary(node) else 20
                while stack and stack[-1][0] >= minimum:
                    stack.pop()
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
    split = []
    for node in blocks:
        marker = candidate(node)
        opening = re.search(r'(?:như sau|as follows)\s*:\s*(["“])', node.get('text') or '', re.I)
        if (marker and marker['kind'] == 'clause' and not marker['explicit'] and opening and
                re.search(r'sửa đổi|bổ sung|thay thế|amend|supplement|replace|add', node['text'][:opening.start()], re.I)):
            split.extend([slice_unit(node, 0, opening.start(1)), slice_unit(node, opening.start(1))])
        else:
            split.append(node)
    blocks = split
    blocks = scope_replacement_articles(scope_replacement_outlines(blocks), quality)
    output, index = [], 0
    while index < len(blocks):
        first = blocks[index]
        text = first.get("text") or ""
        previous = blocks[index - 1].get("text") or "" if index else ""
        # A literal replacement counter plus an explicit unit citation and an
        # unmatched terminal quote can establish scope despite a missing open.
        # Do not repair punctuation or let that local counter reset outer parents.
        reference = re.search(r'\b(khoản|điểm|điều|clause|point|article)\s+(\d+[a-zđ]?|[a-zđ])\s+'
                              r'(?:như sau|as follows)\s*:\s*$', previous, re.I)
        terminal = re.search(r'(["”])\s*[.;,]?\s*$', text)
        marker = quoted_marker(first) if first['type'] in TEXT_TYPES else None
        unit_kinds = {'khoản': 'clause', 'clause': 'clause', 'điểm': 'point',
                      'point': 'point', 'điều': 'article', 'article': 'article'}
        missing_open = (terminal and (text.count('"') % 2 == 1 if terminal[1] == '"' else
                                      text.count('”') == text.count('“') + 1))
        if (reference and marker and not text.startswith(('"', '“')) and missing_open and
                re.search(r'\b(?:sửa đổi|bổ sung|thay thế|amend|supplement|replace)\b', previous, re.I) and
                marker[0]['kind'] == unit_kinds[reference[1].lower()] and
                marker[0]['number'].lower() == reference[2].lower()):
            output.append(quotation([first], 'source_replacement_missing_opening_quotation'))
            if quality is not None:
                quality.add('incomplete_source_quotation',
                            'Source replacement has a matching cited counter and terminal quotation mark but no opening mark; literal text retained in local scope',
                            first['source_ref'], details={'lead_source_ref': blocks[index - 1]['source_ref'],
                                                         'cited_unit': reference[1], 'cited_number': reference[2]})
            index += 1
            continue
        supported = first["type"] in TEXT_TYPES and text.startswith(('"', '“')) and (
            quoted_marker(first) or re.search(r"(?:như sau|thành|thay bằng)\s*:\s*$", previous, re.I))
        end, quotes = index, 0
        previous_lead = amendment_lead_in(blocks[index - 1]) if index else None
        if supported:
            while end < len(blocks):
                node = blocks[end]
                next_lead = amendment_lead_in(node) if end > index else None
                local_number = quoted_marker(first)[0]['number'] if quoted_marker(first) else ''
                outer_counter = candidate(node) if end > index else None
                composite_boundary = (previous_lead and local_number.startswith(previous_lead['number'] + '.') and
                                      outer_counter and not outer_counter['explicit'] and outer_counter['kind'] == 'clause')
                boundary_number = next_lead or (outer_counter if composite_boundary else None)
                # A missing closing quote cannot absorb the next explicitly
                # numbered amendment. Its actual boundary is kept, without
                # inventing punctuation or treating quoted clauses as outer
                # provisions.
                if previous_lead and boundary_number and previous_lead['number'].isdigit() and boundary_number['number'] == str(int(previous_lead['number']) + 1):
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
                terminal = re.search(r'(["”])\s*[.;,]?\s*$', display)
                following_lead = amendment_lead_in(blocks[end + 1]) if end + 1 < len(blocks) else None
                mixed = (terminal and terminal[1] != ('"' if text[0] == '"' else '”') and quotes == 1 and
                         previous_lead and following_lead and previous_lead['number'].isdigit() and
                         following_lead['number'] == str(int(previous_lead['number']) + 1))
                if mixed:
                    output.append(quotation(blocks[index:end + 1]))
                    if quality is not None:
                        quality.add('mixed_source_quotation_marks', 'Source opening and terminal quotation marks differ; both preserved at the evidenced amendment boundary',
                                    first['source_ref'], details={'closing_source_ref': node['source_ref']})
                    index = end + 1
                    break
                if balanced and re.search(r'["”]', display):
                    closing = display.rfind('"' if text[0] == '"' else '”') + 1
                    suffix = display[closing:]
                    if suffix.strip(' .;,\t\n'):
                        terminal_node = slice_unit(node, 0, closing)
                        output.append(quotation([*blocks[index:end], terminal_node]))
                        output.append(slice_unit(node, closing))
                    else:
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


def scope_replacement_articles(blocks, quality=None):
    """A cited replacement heading can precede its opening quotation mark.

    The explicit amendment lead-in and repeated replacement number establish
    the scope. A subsequent amendment or outer heading bounds a missing close;
    original quotation punctuation and wording are always retained.
    """
    def lead(node):
        return re.match(r'^(?:Điều|Article)\s+(\d+[a-zđ]?)\s+(?:trong|tại|của|in|of)\b.*'
                        r'(?:sửa đổi|thay|amend|replace).*?(?:như sau|as follows)\s*:\s*$',
                        node.get('text') or '', re.I) if node['type'] in TEXT_TYPES else None
    output, index = [], 0
    while index < len(blocks):
        first = lead(blocks[index])
        quoted = re.match(r'^(?:Điều|Article)\s+(\d+[a-zđ]?)\s+(?:mới|new)\s*:\s*(["“])',
                          blocks[index + 1].get('text') or '', re.I) if index + 1 < len(blocks) else None
        if not first or not quoted or first[1] != quoted[1]:
            output.append(blocks[index]); index += 1; continue
        end, closed, balance = index + 1, False, 0
        while end < len(blocks):
            node = blocks[end]
            boundary = candidate(node)
            if end > index + 1 and (lead(node) or boundary and boundary['explicit'] and
                    boundary['kind'] in {'article', 'chapter', 'part', 'section', 'subsection'} or closing_role(node)):
                break
            if node['type'] not in TEXT_TYPES | {'table', 'list', 'layout_block', 'separator'}:
                break
            display = node.get('text') or ''
            balance += display.count('"') if quoted[2] == '"' else display.count('“') - display.count('”')
            end += 1
            if (balance % 2 == 0 if quoted[2] == '"' else balance == 0) and re.search(r'["”]\s*[.;,]?\s*$', display):
                closed = True; break
        wrapper = container('layout_block', blocks[index])
        wrapper['evidence'] = 'source_replacement_article_scope'
        blocks[index]['evidence'] = 'source_amendment_citation_lead_in'
        wrapper['children'] = [blocks[index], quotation(blocks[index + 1:end],
                                                       'source_replacement_article_scope')]
        if not closed and quality is not None:
            quality.add('incomplete_source_quotation',
                        'Replacement quotation lacks a closing mark before its source boundary; cited article and local counters retained without punctuation repair',
                        blocks[index + 1]['source_ref'], details={'boundary_source_ref': blocks[end]['source_ref'] if end < len(blocks) else None})
        output.append(wrapper); index = end
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
    for pattern, kind, level in ((r"^([IVXLCDM]+)(?:[.)]\s*|[-/]\s+)", "roman", 10),
                                 (r"^([A-ZĐ])[.)]\s+", "uppercase_alpha", 15),
                                 (DECIMAL_COUNTER, "decimal", 30),
                                 (r"^(\d+)(?:[.)]\s*|[-/]\s*(?=[^\d\s]))", "digit", 20),
                                 (r"^([a-zđ])(?:[.)]\s*|/\s+)", "alpha", 100)):
        match = re.match(pattern, text)
        if match and (kind != 'uppercase_alpha' or node.get('heading_evidence')):
            return {"number": match[1], "kind": kind, "level": level + (match[1].count(".") if kind == "decimal" else 0)}, match
    return None


def scope_replacement_outlines(blocks):
    """An explicit replacement heading has local scope even without quote marks."""
    output, index = [], 0
    while index < len(blocks):
        node = blocks[index]
        lead = re.search(r'\bbằng\s+(?:mục|chương|phần)\s+([IVXLCDM]+|\d+)\s+mới\s+như sau\s*:\s*$', node.get('text') or '', re.I)
        following = outline_marker(blocks[index + 1]) if index + 1 < len(blocks) else None
        if (lead and re.search(r'thay thế|sửa đổi', node.get('text') or '', re.I) and following and
                following[0]['number'].casefold() == lead[1].casefold()):
            end = index + 2
            while end < len(blocks):
                boundary = candidate(blocks[end])
                outline = outline_marker(blocks[end])
                if (boundary and boundary['explicit'] or closing_role(blocks[end]) or
                        outline and outline[0]['kind'] == following[0]['kind'] and blocks[end].get('heading_evidence')):
                    break
                end += 1
            output.extend([node, quotation(blocks[index + 1:end], 'explicit_replacement_outline_without_quote_marks', outline_marker)])
            index = end
        else:
            output.append(node)
            index += 1
    return output


def scope_article_enumerations(blocks):
    """Retain source subdivisions without inventing absent legal levels.

    Two emphasized Roman headings or consecutive A/B subdivisions establish
    an article-local outline. Consecutive letters without a clause retain
    their list scope, including intervening source tables and continuations.
    Isolated points keep their diagnostics; missing legal levels are not made.
    """
    from vietnam_legal_rag.ingestion.refinement.forms import consecutive, form_boundary
    from vietnam_legal_rag.ingestion.refinement.semantic import annex_candidate
    output, index, article, clause, form_scope = [], 0, False, False, False
    while index < len(blocks):
        node = blocks[index]
        if node.get('evidence') == 'attached_legal_act_header' or annex_candidate(node):
            article, clause, form_scope = False, False, False
        if form_boundary(node, active=True):
            article, clause, form_scope = False, False, True
        if form_scope:
            # Template provisions are handled by form refinement. Their local
            # counters cannot reactivate the enclosing legal article scope.
            output.append(node); index += 1
            continue
        marker = candidate(node)
        if marker and marker["explicit"]:
            if marker["kind"] == "article":
                article, clause = True, False
            elif marker["kind"] in {"chapter", "section", "part", "subsection"}:
                article, clause = False, False
        if marker and marker["kind"] == "clause":
            clause = True
        if (article and index and marker and marker['kind'] == 'clause' and not marker['explicit'] and
                (blocks[index - 1].get('text') or '').rstrip().endswith(':') and
                re.search(r'\bgồm\b', blocks[index - 1].get('text') or '', re.I)):
            end = index
            while end < len(blocks):
                member = candidate(blocks[end])
                if not member or member['explicit'] or member['kind'] != 'clause' or not re.match(
                        r'\s*(?:Ông|Bà|Mr\.?|Mrs\.?|Ms\.?)\s+', blocks[end]['text'][member['label_end']:], re.I):
                    break
                end += 1
            if end - index >= 2:
                output.append(quotation(blocks[index:end], 'source_declared_member_enumeration'))
                index = end
                clause = False
                continue
        outline = outline_marker(node) if article and node["type"] in TEXT_TYPES else None
        if outline and outline[0]["kind"] == "roman" and node.get("heading_evidence"):
            end = index
            while end < len(blocks):
                boundary = candidate(blocks[end])
                if (end > index and (boundary and boundary["explicit"] or
                                     annex_candidate(blocks[end]) or form_boundary(blocks[end], active=True)) or
                        blocks[end]["type"] not in TEXT_TYPES | {"table", "list", "separator"}):
                    break
                end += 1
            headings = [b for b in blocks[index:end] if b.get("heading_evidence") and
                        (m := outline_marker(b)) and m[0]["kind"] == "roman"]
            if len(headings) >= 2:
                output.append(quotation(blocks[index:end], "emphasized_roman_article_outline", outline_marker))
                index = end; continue
        upper = re.match(r'^([A-ZĐ])[.)]\s+', node.get('text') or '') if article and not clause else None
        kind = 'uppercase_alpha' if upper else 'alpha' if outline and outline[0]['kind'] == 'alpha' else None
        if kind and article and not clause:
            def local_marker(source):
                upper_match = re.match(r'^([A-ZĐ])[.)]\s+', source.get('text') or '')
                if kind == 'uppercase_alpha' and upper_match:
                    return {'number': upper_match[1], 'kind': kind, 'level': 15}, upper_match
                return outline_marker(source)
            end, previous, marked = index, None, 0
            while end < len(blocks):
                following = blocks[end]
                boundary = candidate(following)
                if (boundary and boundary['explicit'] or closing_role(following) or
                        annex_candidate(following) or form_boundary(following, active=True) or
                        following['type'] not in TEXT_TYPES | {'table', 'layout_block', 'list', 'separator'}):
                    break
                found = local_marker(following) if following['type'] in TEXT_TYPES else None
                if found and found[0]['kind'] == kind:
                    number = found[0]['number']
                    if previous and not consecutive(previous.casefold(), number.casefold(), 'alpha'):
                        break
                    previous = number; marked += 1
                elif found and kind == 'alpha':
                    break
                end += 1
            if marked >= 2:
                evidence = 'article_local_uppercase_outline' if kind == 'uppercase_alpha' else 'article_local_alpha_list_after_lead_in'
                output.append(quotation(blocks[index:end], evidence, local_marker))
                index = end; continue
        output.append(node); index += 1
    return output


def scope_body_outlines(blocks):
    """Source-supported Roman subdivisions in article-free acts have local scope."""
    from vietnam_legal_rag.ingestion.semantics.hierarchy import closing_role, opening_role, signer_before_status
    from vietnam_legal_rag.ingestion.refinement.semantic import annex_candidate
    from vietnam_legal_rag.ingestion.refinement.forms import consecutive, form_boundary
    output, index, article, annex, closing = [], 0, False, False, False
    normative_started = False
    def plain_roman_heading(position):
        node = blocks[position]
        found = outline_marker(node) if node['type'] in TEXT_TYPES else None
        following = outline_marker(blocks[position + 1]) if position + 1 < len(blocks) and blocks[position + 1]['type'] in TEXT_TYPES else None
        letters = [c for c in (node.get('text') or '') if c.isalpha()]
        heading_case = letters and sum(c.isupper() for c in letters) / len(letters) >= 0.85
        return bool(found and found[0]['kind'] == 'roman' and
                    len(node.get('text') or '') <= 600 and ((node.get('text') or '').endswith(':') or heading_case) and
                    following and following[0]['kind'] == 'digit' and following[0]['number'] == '1')
    def local_marker(node):
        text = node.get('text') or ''
        upper = re.match(r'^([A-ZĐ])[.)]\s+', text)
        if upper and text.isupper():
            return {'number': upper[1], 'kind': 'uppercase_alpha', 'level': 10}, upper
        explicit = candidate(node)
        if explicit and explicit['explicit'] and explicit['kind'] == 'clause':
            marker, match = quoted_marker(node)
            return {**marker, 'level': 30}, match
        found = outline_marker(node)
        if found and found[0]['kind'] == 'digit':
            return {**found[0], 'level': 20}, found[1]
        return found
    while index < len(blocks):
        node = blocks[index]
        marker = candidate(node)
        if marker and marker['explicit']:
            article = marker['kind'] in {'article', 'clause', 'point'}
        if node.get('evidence') == 'attached_legal_act_header':
            article, closing = False, False
        annex |= bool(annex_candidate(node))
        normative_started |= (opening_role(node) == 'document_type_heading' or
                              bool(marker and marker['explicit']) or
                              bool(outline_marker(node) and node.get('heading_evidence')))
        closing |= normative_started and bool(closing_role(node))
        outline = outline_marker(node) if not (article or annex or closing) and node['type'] in TEXT_TYPES else None
        upper = local_marker(node) if not (article or annex or closing) and node['type'] in TEXT_TYPES else None
        roman_heading = outline and outline[0]['kind'] == 'roman' and (node.get('heading_evidence') or (node.get('text') or '').isupper() or plain_roman_heading(index))
        alpha = not roman_heading and upper and upper[0]['kind'] == 'uppercase_alpha' and (node.get('text') or '').isupper()
        if alpha or roman_heading:
            end = index + 1
            while end < len(blocks):
                following = blocks[end]
                boundary = candidate(following)
                form = form_boundary(following)
                if (boundary and boundary['explicit'] and not (
                        alpha and boundary['kind'] in {'clause', 'part', 'chapter', 'section', 'subsection'} or
                        roman_heading and boundary['kind'] in {'article', 'clause', 'point'}) or
                        closing_role(following) or
                        signer_before_status(following, blocks[end + 1] if end + 1 < len(blocks) else None) or
                        annex_candidate(following) or following.get('evidence') in {
                            'closing_before_attached_legal_act', 'attached_legal_act_header', 'source_signature_block'} or
                        form and form['evidence'] == 'explicit_form_number' or
                        following['type'] not in TEXT_TYPES | {'table', 'list', 'separator', 'layout_block'}):
                    break
                end += 1
            marker_function = local_marker if alpha else outline_marker
            heading_kind = 'uppercase_alpha' if alpha else 'roman'
            headings = [b for position, b in enumerate(blocks[index:end], index)
                        if (b.get('heading_evidence') or (b.get('text') or '').isupper() or
                            roman_heading and plain_roman_heading(position)) and
                        (m := marker_function(b)) and m[0]['kind'] == heading_kind]
            plain = roman_heading and any(not b.get('heading_evidence') and not (b.get('text') or '').isupper() for b in headings)
            sequence = not plain or all(consecutive(marker_function(a)[0]['number'], marker_function(b)[0]['number'], 'roman')
                                        for a, b in zip(headings, headings[1:]))
            if len(headings) >= 2 and sequence:
                evidence = 'source_article_free_alpha_outline' if alpha else 'emphasized_roman_body_outline'
                if plain:
                    evidence = 'source_roman_outline_with_restarted_numeric_children'
                    for heading in headings:
                        heading.setdefault('heading_evidence', 'counter_restart_in_consecutive_roman_outline')
                if any((m := candidate(b)) and m['explicit'] and m['kind'] in (
                        {'part', 'chapter', 'section', 'subsection'} if alpha else
                        {'article'}) for b in blocks[index:end]):
                    # A displayed outer outline can separate real legal
                    # chapters. Keep those legal labels intact and reset their
                    # stack at the next evidenced outer heading.
                    for heading in headings:
                        heading['_body_outline_heading'] = marker_function(heading)[0]['number']
                    output.extend(blocks[index:end]); index = end; continue
                output.append(quotation(blocks[index:end], evidence, marker_function, outline_boundaries=True))
                index = end
                continue
        output.append(node)
        index += 1
    return output


def scope_alpha_continuations(blocks, counter_kind='alpha'):
    """Consecutive local counters may contain opaque continuation blocks.

    Alphabetic annex lists and numeric table topics share the same bounded
    sequence rule. Missing/nonsequential counters remain audit candidates.
    """
    from vietnam_legal_rag.ingestion.refinement.forms import consecutive
    def topic_marker(node):
        found = outline_marker(node) if node['type'] in TEXT_TYPES else None
        if found and counter_kind == 'digit' and not any(
                c.isalpha() for c in (node.get('text') or '')[found[1].end():]):
            return None  # A decimal/scalar cell value supplies no topic label.
        return found
    output, index = [], 0
    while index < len(blocks):
        first = topic_marker(blocks[index])
        if not first or first[0]["kind"] != counter_kind:
            output.append(blocks[index]); index += 1; continue
        end, accepted, marked, previous = index + 1, index + 1, 1, first[0]["number"]
        while end < len(blocks):
            node = blocks[end]
            marker = topic_marker(node)
            if marker:
                if marker[0]["kind"] != counter_kind or not consecutive(previous, marker[0]["number"], counter_kind):
                    break
                previous = marker[0]["number"]; marked += 1; accepted = end + 1
            elif node["type"] not in TEXT_TYPES | {"table", "layout_block", "list"} or node.get("heading_evidence") or candidate(node):
                break
            elif counter_kind == 'digit' and node['type'] in {'list', 'layout_block'}:
                # A physical cell bounds these topics. Preserve the final
                # topic's explicit subordinate list as well as earlier ones.
                accepted = end + 1
            end += 1
        if marked >= 2:
            evidence = 'annex_alpha_sequence_with_source_continuations' if counter_kind == 'alpha' else 'source_numeric_table_topics_with_continuations'
            output.append(quotation(blocks[index:accepted], evidence, outline_marker))
            index = accepted
        else:
            output.append(blocks[index]); index += 1
    return output


def scope_contents(blocks, counter_function=None):
    """Explicit contents headings scope citation entries, never legal bodies."""
    from vietnam_legal_rag.ingestion.refinement.semantic import annex_candidate
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
        return counter_function(node) if counter_function else None
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
