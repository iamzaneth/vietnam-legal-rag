"""Source-declared technical standards and their local outlines/appendices.

A standard cover needs a category and identifier, or a national letterhead,
issuer, emphasized title and identifier. Physical tables remain intact.
Local counters never become legal Articles, and absent prefixes are not invented.
"""
import re

from .hierarchy import (ALPHA_DECIMAL_COUNTER, DECIMAL_COUNTER, TEXT_TYPES, candidate, container,
                        opening_role)

CATEGORY = re.compile(r'^TIÊU CHUẨN (?:NGÀNH|VIỆT NAM)$', re.I)
IDENTIFIER = re.compile(r'^(?:TCVN\s+\d+\s*[:-]\s*\d{2,4}|\d+\s+TCN\s+\d+\s*[-:]\s*\d{2,4})(?:\s|$)', re.I)


def text_units(node):
    if node['type'] in TEXT_TYPES:
        yield node
    for child in node.get('children', []):
        yield from text_units(child)
    for cell in node.get('cells', []):
        if cell.get('text'):
            # Plain physical cells can hold a standard cover's category and
            # identifier without a nested paragraph tree. This scan is only
            # boundary evidence; the original cell/text/geometry stays intact.
            for text in cell['text'].splitlines():
                yield {'type': 'paragraph', 'text': text.strip(), '_source_cell_text': True}
        yield from text_units({'type': 'layout_block', 'children': cell.get('content', [])})


def standard_cover(blocks, index):
    units = list(text_units(blocks[index]))
    category = next((n for n in units if CATEGORY.fullmatch(n.get('text') or '') and
                     (n.get('heading_evidence') or n.get('_alignment') == 'center' or
                      n.get('_source_cell_text') and len(blocks[index].get('cells', [])) <= 8)), None)
    nearby = units + [n for block in blocks[index + 1:index + 5] for n in text_units(block)]
    identifier = any(IDENTIFIER.match(n.get('text') or '') for n in nearby)
    if category:
        return identifier
    # Legacy technical covers sometimes name the issuer and standard instead
    # of displaying a category. A lone identifier or national heading is not
    # enough; all independent cover signals must be present in source flow.
    national = any(opening_role(n) == 'national_heading' for n in units)
    issuer = any(opening_role(n) == 'issuing_authority' for n in nearby)
    title = any((n.get('text') or '').isupper() and len((n.get('text') or '').split()) >= 4 and
                not opening_role(n) and not IDENTIFIER.match(n.get('text') or '') and
                (n.get('heading_evidence') or n.get('_alignment') == 'center' or n.get('_source_cell_text'))
                for n in nearby)
    return bool(national and issuer and title and identifier)


def technical_contents_entry(node):
    """Bare technical contents numbers need an explicit contents scope."""
    if node['type'] not in TEXT_TYPES:
        return None
    match = re.match(r'^(\d+(?:\.\d+)*)(?:[.)]?\s+)(?=\S)', node.get('text') or '')
    if match:
        return {'number': match[1], 'kind': 'contents', 'level': 10}, match
    return None


def scope_local_enumerations(blocks):
    """A source lead-in or lettered item bounds a subordinate numeric run.

    Keep its counter namespace independent of the standard's decimal path.
    Require a displayed consecutive sequence starting at one; stop at any
    other counter, so a later technical section remains outside the list.
    """
    from .quotations import quotation
    output, index, figure_region = [], 0, False
    def legend_marker(node):
        if node['type'] not in TEXT_TYPES:
            return None
        match = re.match(r'^(\d+)\s*[-–—]\s*(?=\S)', node.get('text') or '')
        if match:
            return {'number': match[1], 'kind': 'clause', 'level': 10, 'explicit': False}, match
        return None
    def reference_path(node):
        if node['type'] not in TEXT_TYPES:
            return None
        text = node.get('text') or ''
        match = re.match(r'^([A-ZĐ](?:\.\d+)+|\d+(?:\.\d+)+)(?=\s|$)\s*', text)
        if match and (not text[match.end():] or re.fullmatch(
                r'(?:đến|to)\s+(?:[A-ZĐ](?:\.\d+)+|\d+(?:\.\d+)+)', text[match.end():], re.I)):
            return {'number': match[1], 'kind': 'reference', 'level': 10}, match
        return None
    while index < len(blocks):
        prior = blocks[index - 1] if index else None
        reference_lead = prior and re.search(
            r'\b(?:Phần|Mục|Điều|Section|Article)\s+[\w.]+[,;]\s*(?:điều|mục|sections?|articles?)\s*:\s*$',
            prior.get('text') or '', re.I)
        if reference_lead:
            end = index
            while end < len(blocks) and reference_path(blocks[end]):
                end += 1
            if end - index >= 2:
                output.append(quotation(blocks[index:end], 'source_technical_reference_enumeration', reference_path))
                index = end
                continue
        previous = candidate(prior) if prior else None
        first = candidate(blocks[index])
        text = blocks[index].get('text') or ''
        if blocks[index]['type'] == 'unknown' or any(n['type'] == 'unknown' for n in blocks[index].get('children', [])):
            figure_region = True
        caption = re.match(r'^(?:Hình\s+[A-ZĐ]?\d|Figure\s+\d|Mặt cắt\s+[A-ZĐ]\s*[-–]\s*[A-ZĐ])', text, re.I)
        if caption and (blocks[index].get('_alignment') == 'center' or blocks[index].get('heading_evidence')):
            figure_region = True
        legend = figure_region and re.match(r'^1\s*[-–—]\s*(?=\S)', text)
        if legend:
            first = legend_marker(blocks[index])[0]
        supported = prior and (prior.get('text', '').rstrip().endswith(':') or
                               previous and previous['kind'] == 'point' and not previous['explicit'])
        if (supported or legend) and first and not first['explicit'] and first['kind'] == 'clause' and first['number'] == '1':
            end, count = index, 0
            while end < len(blocks):
                node = blocks[end]
                if legend and (node['type'] == 'unknown' or re.match(
                        r'^(?:Hình\s+[A-ZĐ]?\d|Figure\s+\d|Mặt cắt\s+)', node.get('text') or '', re.I)):
                    break
                legend_found = legend_marker(node) if legend else None
                marker = legend_found[0] if legend_found else candidate(node)
                text = node.get('text') or ''
                if marker:
                    if marker['explicit'] or marker['kind'] != 'clause' or marker['number'] != str(count + 1):
                        break
                    if legend and not re.match(r'^\d+\s*[-–—]\s*(?=\S)', text):
                        break
                    count += 1
                elif node['type'] in TEXT_TYPES and (DECIMAL_COUNTER.match(text) or
                        ALPHA_DECIMAL_COUNTER.match(text) or re.match(r'^\d+(?:\.\d+)+\s', text)):
                    break
                elif node.get('heading_evidence') or node.get('_alignment') == 'center' and text.isupper():
                    break
                end += 1
            if count >= 2:
                if legend:
                    output.append(quotation(blocks[index:end], 'source_technical_figure_legend', legend_marker))
                else:
                    output.append(quotation(blocks[index:end], 'technical_source_subordinate_enumeration'))
                figure_region = False
                index = end
                continue
        if first or DECIMAL_COUNTER.match(text) or re.match(r'^[A-ZĐ]\d+(?:\.\d+)*\s', text):
            figure_region = False
        output.append(blocks[index])
        index += 1
    return output


def local_outline(blocks, quality, initial_prefix=None):
    from vietnam_legal_rag.ingestion.refinement.semantic import NUMBER, number_candidate
    from vietnam_legal_rag.ingestion.refinement.forms import group_notes
    from vietnam_legal_rag.ingestion.refinement.forms import semantic_body
    from .quotations import scope_contents
    children, prefixes, active, letter_parent = [], {}, None, None
    seen_numbers = set()
    for block in scope_local_enumerations(scope_contents(group_notes(blocks), technical_contents_entry)):
        text = block.get('text') or ''
        note = re.match(r'^(\d+)[)/]\s*', text) if block['type'] in TEXT_TYPES else None
        if note and any(a['type'] == 'superscript' and a['start'] == 0 and
                        a['end'] <= note.end() for a in block.get('annotations', [])):
            block = semantic_body(block, note, 'footnote')
            block['evidence'] = 'source_superscript_note_marker'
            (active['children'] if active else children).append(block)
            continue
        numeric = number_candidate(block)
        isolated_integer = block['type'] in TEXT_TYPES and re.fullmatch(r'\d+', text)
        bare = NUMBER.match(text) if block['type'] in TEXT_TYPES and not IDENTIFIER.match(text) and not isolated_integer else None
        scalar = bare and re.match(r'(?:\d|[<>=≤≥±]|(?:kg|km|m2|m3|mm|cm|m|K|Pa|kPa|s|tấn|ha|%|đồng)(?:\s|$))', text[bare.end():], re.I)
        if bare and not scalar:
            numeric = numeric or (bare, [int(n) for n in bare[1].split('.')])
        if scalar:
            numeric = None
        compound = DECIMAL_COUNTER.match(text) if block['type'] in TEXT_TYPES else None
        alpha = re.match(r'^([a-zđ]\s*(?:\.\s*\d+)+|[a-zđ]\d+(?:\.\d+)*)(?:[.)]?\s+|[.)](?=[^\d\s]))', text, re.I) if block['type'] in TEXT_TYPES else None
        if alpha and re.match(r'^[a-zđ]\d', alpha[1], re.I) and (
                not initial_prefix or alpha[1][0].casefold() != initial_prefix.casefold()):
            alpha = None  # Symbol subscripts need no invented appendix namespace.
        marker = candidate(block)
        malformed = re.match(r'^(\d+(?:\.{1,}\d+)+)[.)]\s+(?=[^\d\s])', text) if block['type'] in TEXT_TYPES else None
        number = malformed[1] if malformed and '..' in malformed[1] else numeric[0][1] if numeric else compound[1] if compound else alpha[1] if alpha else (
            marker['number'] if marker and marker['kind'] in {'point', 'clause'} and not marker['explicit'] else None)
        if number is not None:
            # Lettered siblings are local subdivisions of the active technical
            # unit, not new roots in its decimal counter namespace. Numeric
            # sublists have already been scoped independently above.
            if marker and marker['kind'] == 'point' and not marker['explicit'] and '.' not in number:
                if letter_parent is None:
                    letter_parent = active
                block.update(type='numbered_paragraph', number=number,
                             evidence='source_technical_local_counter')
                (letter_parent['children'] if letter_parent else children).append(block)
                if letter_parent:
                    block['parent_number'] = letter_parent['number']
                active = block
                continue
            letter_parent = None
            # Whitespace belongs to the displayed source label; only matching
            # keys ignore spaces adjacent to a separator.
            key = re.sub(r'\s*\.\s*', '.', number)
            prefix = key.rsplit('.', 1)[0] if '.' in key else None
            if prefix is None and re.fullmatch(r'[a-zđ]\d+', key, re.I):
                prefix = key[0]
            if key in seen_numbers:
                quality.add('duplicate_source_outline_number',
                            'Repeated technical outline number retained literally in its source scope without renumbering',
                            block['source_ref'], details={'displayed_number': number})
            seen_numbers.add(key)
            parent = prefixes.get(prefix) if prefix else None
            if prefix and parent is None:
                # An omitted intermediate counter never gets synthesized. The
                # nearest displayed ancestor can still bound the source region.
                ancestor = max((p for p in prefixes if key.startswith(p + '.')), key=len, default=None)
                parent = prefixes.get(ancestor)
            block.update(type='numbered_paragraph', number=number,
                         evidence='source_technical_local_counter')
            if parent:
                block['parent_number'] = parent['number']
                parent['children'].append(block)
            elif prefix and prefix != initial_prefix and active:
                # A mismatched source path does not close a displayed section.
                # Retain it in that source interval without claiming a numeric
                # parent or changing the active prefix namespace.
                block['evidence'] = 'source_technical_unresolved_counter'
                active['children'].append(block)
            else:
                children.append(block)
                if prefix and prefix == initial_prefix:
                    block['parent_number'] = prefix
            if prefix and prefix not in prefixes and prefix != initial_prefix:
                quality.add('unresolved_counter_prefix',
                            'Technical counter has no displayed immediate prefix in this source scope; no parent invented',
                            block['source_ref'], details={'number': number, 'requested_prefix': prefix})
            if '..' in number:
                quality.add('source_counter_role_conflict',
                            'Malformed technical counter punctuation retained literally without repair',
                            block['source_ref'], details={'displayed_number': number})
            # Only source ancestors remain active. A later sibling cannot
            # attach to an already closed earlier counter's subtree.
            if not (prefix and prefix != initial_prefix and parent is None and active):
                prefixes = {k: v for k, v in prefixes.items() if key.startswith(k + '.') and parent is not None}
                prefixes[key] = block
                active = block
        elif block['type'] in TEXT_TYPES and (block.get('heading_evidence') or
                block.get('_alignment') == 'center' and text.isupper()):
            block.update(type=opening_role(block) or 'heading')
            (active['children'] if active else children).append(block)
        else:
            (active['children'] if active else children).append(block)
    return children


def parse_standard(blocks, quality):
    from vietnam_legal_rag.ingestion.refinement.semantic import annex_candidate
    wrapper = container('layout_block', blocks[0])
    wrapper['evidence'] = 'source_technical_standard_scope'
    boundaries = [i for i, b in enumerate(blocks) if annex_candidate(b) and
                  (b.get('heading_evidence') or b.get('_alignment') == 'center')]
    first = boundaries[0] if boundaries else len(blocks)
    wrapper['children'] = local_outline(blocks[:first], quality)
    for start, end in zip(boundaries, boundaries[1:] + [len(blocks)]):
        heading = blocks[start]
        marker = annex_candidate(heading)
        heading.update(type='annex_heading', number=marker['number'],
                       evidence='source_appendix_in_technical_standard')
        appendix = container('layout_block', heading)
        appendix['evidence'] = 'source_technical_appendix_scope'
        appendix['number'] = marker['number']
        appendix['children'] = [heading] + local_outline(blocks[start + 1:end], quality,
                                                        marker['number'])
        wrapper['children'].append(appendix)
    return wrapper


def scope_technical_standards(blocks, quality):
    boundaries = [i for i in range(len(blocks)) if standard_cover(blocks, i)]
    if not boundaries:
        return blocks
    output = blocks[:boundaries[0]]
    for start, end in zip(boundaries, boundaries[1:] + [len(blocks)]):
        output.append(parse_standard(blocks[start:end], quality))
    return output
