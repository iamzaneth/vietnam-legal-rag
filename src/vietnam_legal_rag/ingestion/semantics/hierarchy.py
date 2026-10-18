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
DECIMAL_COUNTER = re.compile(r"^(\d+(?:\.\d+)+)(?:[.)]\s*|[-/]\s+)(?=[^\d\s])")
ALPHA_DECIMAL_COUNTER = re.compile(r"^([a-zđ](?:\.\d+)+)(?:[.)]\s*|[-/]\s+)(?=[^\d\s])", re.I)
ROMAN_COUNTER = re.compile(r"M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})$", re.I)
DOCUMENT_TYPES = r"THÔNG TƯ LIÊN TỊCH|THÔNG TƯ|BỘ LUẬT|LUẬT|NGHỊ ĐỊNH|NGHỊ QUYẾT LIÊN TỊCH|NGHỊ QUYẾT|QUYẾT ĐỊNH|CHỈ THỊ|PHÁP LỆNH|SẮC LỆNH|LỆNH|JOINT CIRCULAR|CIRCULAR|LAW|DECREE|RESOLUTION|DECISION|DIRECTIVE|ORDINANCE"
SOURCE_SCOPE_BOUNDARIES = {'closing_before_attached_legal_act', 'attached_legal_act_header',
                           'source_technical_standard_scope'}
AUTHORITY = r"(?:BỘ(?: TRƯỞNG)?\b|ỦY BAN\b|UỶ BAN\b|UBND\b|BAN TỔ CHỨC\b|CHÍNH PHỦ\b|QUỐC HỘI\b|HỘI ĐỒNG\b|TỔNG CỤC\b|CỤC\b|SỞ\b|TÒA ÁN\b|TOÀ ÁN\b|VIỆN KIỂM SÁT\b|THỦ TƯỚNG\b|CHỦ TỊCH\b|CHỦ NHIỆM\b|THE (?:MINISTER|GOVERNMENT|PRIME MINISTER|NATIONAL ASSEMBLY)\b|MINISTRY OF\b)"
SIGNER_TITLE = r"(?:THỨ TRƯỞNG(?: THỨ NHẤT| THƯỜNG TRỰC)?|BỘ TRƯỞNG|(?:PHÓ )?CHỦ TỊCH(?: QUỐC HỘI| HỘI ĐỒNG (?:NHÀ NƯỚC|BỘ TRƯỞNG)| (?:ỦY|UỶ) BAN NHÂN DÂN)?|GIÁM ĐỐC|PHÓ GIÁM ĐỐC|TỔNG GIÁM ĐỐC|(?:PHÓ )?TỔNG CỤC TRƯỞNG|CỤC TRƯỞNG|(?:PHÓ )?CHỦ NHIỆM|CHÁNH ÁN|VIỆN TRƯỞNG|(?:QUYỀN )?THỦ TƯỚNG(?: CHÍNH PHỦ)?|PHÓ THỦ TƯỚNG(?: CHÍNH PHỦ)?)"
DELEGATION_ABBREVIATION = r"(?:T\.?M|K\.?T|T\.?L|T\.?U\.?Q|Q)"
ENGLISH_SIGNER_TITLE = r"(?:Minister|MINISTER|Prime Minister|PRIME MINISTER|Deputy Prime Minister|DEPUTY PRIME MINISTER|Chairman|CHAIRMAN)(?: (?:of|OF) [A-Z][A-Za-z-]*(?: (?:[A-Z][A-Za-z-]*|of|the|and))*)?"
NATIONAL_HEADING = r"CỘNG\s*H[ÒO][ÀA]\s*XÃ\s*HỘI\s*CHỦ\s*NGHĨA\s*VIỆT\s*NAM|VIỆT\s*NAM\s*DÂN\s*CHỦ\s*CỘNG\s*H[ÒO][ÀA]"
NATIONAL_MOTTO = r"Độc lập\s*[-–—]\s*Tự do\s*[-–—]\s*Hạnh phúc"
NORMATIVE_TYPES = r'QUY CHẾ|QU[IY] ĐỊNH|ĐIỀU LỆ|NỘI QUY|DANH MỤC'
DOCUMENT_SET_TITLE = re.compile(r'^BỘ\s+(?:HỒ SƠ|TÀI LIỆU|BIỂU MẪU|BÁO CÁO)\b', re.I)
NORMATIVE_TITLE = re.compile(r'^(?:(?:' + NORMATIVE_TYPES + r')(?:\[\d+\])?(?: (?:VỀ|VỀ VIỆC) .+)?|(?:REGULATIONS?|CHARTER|STATUTE)(?: (?:ON|OF) .+)?)$')
ATTACHMENT_NOTE = re.compile(r'^\(?\s*(?:Ban hành kèm theo|Kèm theo|(?:Issued|Promulgated|Ratified) together with)\b', re.I)


def normative_heading(block):
    return bool(NORMATIVE_TITLE.fullmatch(block.get('text') or '') and (
        block.get('heading_evidence') or block.get('_alignment') == 'center'))


def roman_ordinal(number):
    """Compare canonical source counters without changing their displayed labels."""
    if not number or not ROMAN_COUNTER.fullmatch(number):
        return None
    values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    digits = [values[c] for c in number.upper()]
    return sum(-value if index + 1 < len(digits) and value < digits[index + 1] else value
               for index, value in enumerate(digits))


def source_key(node):
    return node["order"], node.get("source_offset", 0)


def container(kind, first=None, ref=None):
    ref = ref or first["source_ref"]
    result = {"type": kind, "order": ref["dom_order"], "source_ref": ref, "children": []}
    if first and first['order'] == ref['dom_order'] and 'source_offset' in first:
        result['source_offset'] = first['source_offset']
    return result


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
    match = re.match(r"^(Tiểu mục|Phần|Chương|Mục|Điều|Khoản|Điểm|Subsection|Part|Chapter|Section|Article|Clause|Point)(?:\s+|(?=\d))"
                     r"((?:thứ[ \t]+(?:nhất|hai|ba|tư|bốn|năm|sáu|bảy|tám|chín|mười|\d+)"
                     r"(?:[ \t]+(?:mươi|mốt|một|hai|ba|tư|bốn|năm|lăm|sáu|bảy|tám|chín))*)"
                     r"|[IVXLCDM]+|\d+[a-zđ]?|[a-zđ])(?=[\s.:)]|[-–—]\s|\[\d+\]|$)", scan, re.I)
    if match:
        end = offsets[match.end()]
        rest = text[end:]
        # A leading citation such as "Điều 5 của Luật ..." is not a heading.
        if rest.strip() and not re.match(r"^[ \t]*[.:)\n]", rest) and not block.get("heading_evidence"):
            if re.match(r'\s*(?:và|hoặc)(?=(?:Điều|Article)\d)', rest, re.I):
                return None  # Joined source words still form a cross-reference.
            if re.match(r"\s*(?:của|tại|quy định|được|và|có|này|of|in|under|provides|shall|is|and)\b", rest, re.I):
                return None
            if re.match(r'\s+(?:' + DOCUMENT_TYPES + r')\b[^:;\n]{0,160}\b(?:ghi rõ|quy định|nêu|định rằng)\b', rest, re.I):
                return None  # A named-act citation followed by its reported wording.
        return {"kind": LEGAL_LABELS[match[1].casefold()],
                "number": text[offsets[match.start(2)]:offsets[match.end(2)]],
                "label_end": end, "explicit": True}
    declared = block.get('_source_declared_kind')
    if declared in {'chapter', 'section', 'subsection', 'part'}:
        joined = re.match(r'^(Phần|Chương|Mục|Tiểu mục|Part|Chapter|Section|Subsection)\s+([IVXLCDM]+)(?=[^IVXLCDM\d\s])', scan, re.I)
        if (joined and LEGAL_LABELS[joined[1].casefold()] == declared and roman_ordinal(joined[2]) is not None and
                scan[joined.end():].isupper() and len(scan[joined.end():].split()) >= 2):
            # Source declares the structural role and joins an unambiguous
            # Roman counter to uppercase title text. Preserve the missing
            # separator rather than inserting punctuation or whitespace.
            return {'kind': declared, 'number': text[offsets[joined.start(2)]:offsets[joined.end(2)]],
                    'label_end': offsets[joined.end()], 'explicit': True}
    if declared in {'article', 'chapter', 'section', 'subsection', 'part'}:
        malformed = re.match(r'^[^\W\d_]+(?:\s+[^\W\d_]+)?\s+(\d+[a-zđ]?)(?=[.:)]|\s|$)', scan, re.I)
        if malformed:
            return {'kind': declared, 'number': text[offsets[malformed.start(1)]:offsets[malformed.end(1)]],
                    'label_end': offsets[malformed.end()], 'explicit': True, 'malformed_label': True}
    match = re.match(r"^(\d+[a-zđ]?)(?:\[\d+\])*([.)]|[-/]\s*(?=[^\d\s]))(?:\s+|(?=[^\d\s])|$)", scan, re.I)
    if match:
        return {"kind": "clause", "number": text[offsets[match.start(1)]:offsets[match.end(1)]],
                "label_end": offsets[match.end(2)], "explicit": False}
    if block.get('_source_declared_kind') == 'clause':
        match = re.match(r'^(\d+(?:\.\d+)+)(?=\[\d+\])', scan)
        if match:
            return {'kind': 'clause', 'number': text[:offsets[match.end(1)]],
                    'label_end': offsets[match.end(1)], 'explicit': False, 'unusual_counter': True}
    if ALPHA_DECIMAL_COUNTER.match(scan):
        return None  # An explicit compound local path is not its first legal letter.
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
    text = re.sub(r'^[-–—]\s+(?=Căn cứ|Pursuant to|Sau khi|Xét)', '', text, flags=re.I)
    if re.match(r'^Chiểu\s+(?:đề nghị|kiến nghị)\b', text, re.I):
        return 'proposal_basis'
    if (re.match(r"^(?:Căn cứ|Chiểu|Pursuant to)\s", text, re.I) or
            re.match(r'^Căn\s+cứ(?=Luật\b|Nghị\s+định\b|Nghị\s+quyết\b|Quyết\s+định\b|Thông\s+tư\b)', text, re.I)):
        return "legal_basis"
    if re.match(r"^(?:Xét\s|Sau khi\s+(?:Tờ trình|xem xét|nghe)|Theo\s+(?:đề nghị|kiến nghị)|At the proposals?\s+of\b)", text, re.I):
        return "proposal_basis"
    if re.match(r'^(?:' + DOCUMENT_TYPES + r')\s+số\s*:\s*\S', text, re.I):
        return 'document_number'
    if re.fullmatch(DOCUMENT_TYPES, text, re.I):
        return "document_type_heading"
    if ((block.get('heading_evidence') or block.get('_alignment') == 'center') and
            (re.fullmatch(DOCUMENT_TYPES.replace(' ', r'\s*'), text, re.I) or
             re.match(r'^(?:' + DOCUMENT_TYPES + r')[ \t]*\n\S', text, re.I) or
             re.match(r'^(?:' + DOCUMENT_TYPES + r')\s+(?:Về|Ban hành|Quy định)\b', text, re.I))):
        return 'document_type_heading'
    if re.match(r"^(?:" + DOCUMENT_TYPES + r")\s+\S", text):
        return "document_type_heading"  # A combined type/title candidate, split in pass two.
    if re.fullmatch(NATIONAL_HEADING + r'(?:\s*[-_]{3,})?', text, re.I):
        return "national_heading"
    if re.fullmatch(NATIONAL_MOTTO + r'(?:\s*[-_]{3,})?', text, re.I):
        return "national_motto"
    if re.match(r"^Số\s*:\s*\S", text, re.I):
        return "document_number"
    if re.fullmatch(r".+,\s*ngày\s*\d+\s*tháng\s*\d+\s*năm\s*\d{4}\s*", text, re.I):
        return "place_and_date"
    authority_text = re.sub(r'[-_]{3,}$', '', text).rstrip()
    if authority_text.isupper() and not DOCUMENT_SET_TITLE.match(authority_text) and (re.match(AUTHORITY, authority_text) or
            re.fullmatch(r'THỦ\s*TƯỚNG\s*CHÍNH\s*PHỦ', authority_text) or
            re.match(r'^[ỦU][ỶY]BAN\s+NHÂN\s+DÂN\b', authority_text)):
        return "issuing_authority"
    return None


def closing_role(block):
    text = unicodedata.normalize("NFC", block.get("text", ""))
    if re.match(r"^Nơi nhận\s*:", text, re.I):
        return "recipients"
    if re.match(r"^" + DELEGATION_ABBREVIATION + r"(?:\.\s*|/\s*(?=" + AUTHORITY + r"))", text):
        return "delegation_title"
    if re.fullmatch(r"On behalf of (?:the )?[A-Z][A-Za-z -]{1,120}", text):
        return "delegation_title"
    if (re.fullmatch(SIGNER_TITLE, text, re.I) or re.fullmatch(r'BỘ TRƯỞNG .+', text) or
            re.fullmatch(ENGLISH_SIGNER_TITLE, text)):
        return "signer_title"
    if text.isupper() and re.fullmatch(SIGNER_TITLE + r'\s+(?:NGÂN HÀNG|TỔNG CỤC|CỤC|SỞ|VIỆN|TÒA ÁN|TOÀ ÁN|HỘI ĐỒNG|ỦY BAN|UỶ BAN)\b.+', re.sub(r'\s+', ' ', text)):
        return 'signer_title'
    if re.fullmatch(r"\(?\s*(?:Đã ký|đã ký|Ký tên|đã ký và đóng dấu)\s*\)?", text):
        return "signature_status"
    if re.fullmatch(r"\[\s*daky\s*\]", text, re.I):
        return "signature_marker"
    return None


def signer_name_text(text):
    """A name-shaped source string, only used with adjacent signing evidence."""
    if text.isupper() and re.match(AUTHORITY, text):
        return False
    name = re.sub(r'^(?:(?:PGS|GS|TS|THS|BS|KS|KH)(?:\.\s*|\s+)){1,4}', '', text, flags=re.I)
    name = re.sub(r'^(?:Đại|Thượng|Trung|Thiếu)\s+(?:tướng|tá|úy)\s+', '', name, flags=re.I)
    words = name.split()
    return 2 <= len(words) <= 7 and all(w.isalpha() and w[0].isupper() for w in words)


def signer_before_status(block, following):
    text = block.get('text') or ''
    return bool(block['type'] in TEXT_TYPES and following and not text.isupper() and
                signer_name_text(text) and closing_role(following) in {'signature_status', 'signature_marker'})


def is_formula(block):
    text = unicodedata.normalize("NFC", block.get("text", ""))
    return bool(re.fullmatch(r"(?:QUYẾT ĐỊNH|NGHỊ ĐỊNH|NGHỊ QUYẾT|QUYẾT NGHỊ|BAN HÀNH|RA SẮC LỆNH|DECIDES|DECREES|RESOLVES)\s*:", text, re.I) or
                re.fullmatch(r'Nay ra\s+(?:' + DOCUMENT_TYPES + r')(?:\s+[^\n:]{1,160})?\s+như sau\s*:', text, re.I) or
                re.fullmatch(r"(?:QUYẾT NGHỊ|BAN HÀNH)", text, re.I) or
                re.match(r"^(?:Chính\s*phủ|Thủ\s*tướng\s+Chính\s*phủ|Quốc\s+hội|Hội\s+đồng\s+nhân\s+dân.{0,160}?|Bộ\s*trưởng\s+Bộ.{0,160}?|[ỦU]y\s*ban.{0,160}?)\s+ban\s+hành\s+(?:" +
                         DOCUMENT_TYPES + '|' + NORMATIVE_TYPES + r")\b", text, re.I))


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
        if block['type'] in TEXT_TYPES and re.fullmatch(r'[\s_—–=*-]{3,}', block.get('text') or ''):
            # A separator inside a larger source block must keep its text and
            # offsets; it cannot be ignored using that block's whole anchor.
            block['type'] = 'separator'
            yield block
            continue
        if block.get("evidence") in {"source_signature_block", "source_addressee_block"}:
            yield block
            continue
        if block["type"] == "layout_block" and block.get("source_layout"):
            for child in logical_blocks(block["children"]):
                child["_source_layout"] = block["source_layout"]
                if block['source_layout'].get('classification_evidence') == 'source_consolidated_verification_block':
                    child['_source_closing_layout'] = True
                if closing_role(child) == 'signer_title':
                    # An authority qualifier can wrap within one displayed
                    # title; its uppercase continuation is not a signer name.
                    yield child
                    continue
                if child["type"] in TEXT_TYPES and "\n" in child.get("text", ""):
                    offset = 0
                    for line in child["text"].splitlines(keepends=True):
                        if line.strip():
                            yield from logical_blocks([slice_unit(child, offset, offset + len(line))])
                        offset += len(line)
                else:
                    yield from logical_blocks([child])
        else:
            if block['type'] in TEXT_TYPES and closing_role(block) == 'signer_title':
                yield block
                continue
            text = block.get('text') or ''
            scan, offsets = normalized_scan(text)
            authority_number = re.fullmatch(r'(.+?[-_]{3,})\s*(Số\s*:\s*\S.*)', scan, re.I | re.S)
            if (block['type'] in TEXT_TYPES and authority_number and
                    opening_role({'type': 'paragraph', 'text': authority_number[1]}) == 'issuing_authority'):
                for group in (1, 2):
                    yield slice_unit(block, offsets[authority_number.start(group)], offsets[authority_number.end(group)])
                continue
            national_date = re.fullmatch(r'(' + NATIONAL_HEADING + r')\s*(' + NATIONAL_MOTTO +
                                         r'\s*[-_]{3,})\s*(.+,\s*ngày\s*\d+\s*tháng\s*\d+\s*năm\s*\d{4})', scan, re.I)
            if block['type'] in TEXT_TYPES and national_date:
                for group in (1, 2, 3):
                    yield slice_unit(block, offsets[national_date.start(group)], offsets[national_date.end(group)])
                continue
            delegated_authority = r'(?:CHÍNH PHỦ|(?:ỦY|UỶ) BAN NHÂN DÂN|' + SIGNER_TITLE + r')'
            delegation = DELEGATION_ABBREVIATION + r'\.\s*' + delegated_authority
            signing_chain = re.fullmatch(r'((?:' + delegation + r'\s*){2,})(' + SIGNER_TITLE + r')\s*(.+)', scan)
            if (block['type'] in TEXT_TYPES and signing_chain and signer_name_text(signing_chain[3]) and
                    any(c.islower() for c in signing_chain[3])):
                for part in re.finditer(delegation, signing_chain[1]):
                    yield slice_unit(block, offsets[part.start()], offsets[part.end()])
                for group in (2, 3):
                    yield slice_unit(block, offsets[signing_chain.start(group)], offsets[signing_chain.end(group)])
                continue
            start = block.get('_emphasized_suffix_offset')
            if (start and block['type'] in TEXT_TYPES and
                    (closing_role({'text': text[start:]}) or signer_name_text(text[start:]))):
                prefix, suffix = slice_unit(block, 0, start), slice_unit(block, start)
                prefix.pop('_emphasized_suffix_offset', None)
                suffix.pop('_emphasized_suffix_offset', None)
                suffix['_source_emphasized_signing_suffix'] = True
                yield prefix
                yield suffix
                continue
            joined_roles = re.fullmatch('(' + DELEGATION_ABBREVIATION + r'\.\s*' + SIGNER_TITLE + r')\s*('
                                       + SIGNER_TITLE + r')\s*(.+)', scan)
            if block['type'] in TEXT_TYPES and joined_roles and signer_name_text(joined_roles[3]):
                for group in (1, 2, 3):
                    yield slice_unit(block, offsets[joined_roles.start(group)], offsets[joined_roles.end(group)])
                continue
            national_pair = re.fullmatch(r'(' + NATIONAL_HEADING + r')\s*(' + NATIONAL_MOTTO + r'(?:[ \t]*[-_]{3,})?)', scan, re.I)
            if block['type'] in TEXT_TYPES and national_pair:
                for group in (1, 2):
                    yield slice_unit(block, offsets[national_pair.start(group)], offsets[national_pair.end(group)])
                continue
            title_name = re.fullmatch('(' + SIGNER_TITLE + r')\s*(.+)', scan)
            if (block['type'] in TEXT_TYPES and title_name and signer_name_text(title_name[2]) and
                    any(c.islower() for c in title_name[2])):
                # A source span can join a displayed title directly to the
                # personal name. Split only the established title grammar and
                # a name-shaped suffix; retain actual offsets and spacing.
                yield slice_unit(block, offsets[title_name.start(1)], offsets[title_name.end(1)])
                yield slice_unit(block, offsets[title_name.start(2)], offsets[title_name.end(2)])
                continue
            compact_signing = re.fullmatch(r'(.+?)\s*(\(\s*(?:Đã ký|đã ký)\s*\))\s*(.*)', scan, re.S)
            if (block['type'] in TEXT_TYPES and compact_signing and
                    closing_role({'text': compact_signing.group(1)}) in {'signer_title', 'delegation_title'} and
                    (not compact_signing.group(3) or signer_name_text(compact_signing.group(3)))):
                yield slice_unit(block, offsets[compact_signing.start(1)], offsets[compact_signing.end(1)])
                yield slice_unit(block, offsets[compact_signing.start(2)], offsets[compact_signing.end(2)])
                if compact_signing.group(3):
                    yield slice_unit(block, offsets[compact_signing.start(3)], offsets[compact_signing.end(3)])
                continue
            lines = (block.get('text') or '').splitlines(keepends=True) if block['type'] in TEXT_TYPES else []
            meaningful = [line.strip() for line in lines if line.strip()]
            signer_pair = (len(meaningful) == 2 and
                           closing_role({'text': meaningful[0]}) in {'signer_title', 'delegation_title', 'signature_status'} and
                           2 <= len(meaningful[1].split()) <= 7 and
                           all(w.isalpha() and w[0].isupper() for w in meaningful[1].split()))
            signing_lines = (len(meaningful) >= 2 and all(closing_role({'text': line}) in {
                'delegation_title', 'signer_title', 'signature_status', 'signature_marker'} for line in meaningful))
            if signer_pair or signing_lines:
                offset = 0
                for line in lines:
                    if line.strip():
                        yield slice_unit(block, offset, offset + len(line))
                    offset += len(line)
            else:
                yield block


def coalesce(elements):
    from vietnam_legal_rag.ingestion.refinement.semantic import annex_candidate
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
        if block.get('evidence') in SOURCE_SCOPE_BOUNDARIES:
            self.stack = []
            self.generic_parent = self.generic_child = None
            self.generic_numbers = {}
            if block['evidence'] == 'attached_legal_act_header':
                self.seen_numbers = set()
            self.children.append(block)
            self.previous = block
            return
        marker = candidate(block)
        if marker and marker.get('malformed_label'):
            self.quality.add('source_structural_label_conflict',
                             'Source markup declares a structural role but its literal label is malformed; original label retained',
                             block['source_ref'], details={'source_declared_kind': marker['kind']})
        if number := block.pop('_body_outline_heading', None):
            self.stack = []
            self.generic_parent = self.generic_child = None
            self.generic_numbers = {}
            block.update(type='heading', number=number, evidence='source_outer_outline_above_legal_hierarchy')
            self.children.append(block)
            self.previous = block
            return
        active = {kind for kind, node in self.stack if node.get("parent_status") != "unresolved"}
        if marker and marker.get('unusual_counter') and 'article' in active:
            self.quality.add('source_counter_role_conflict',
                             'Source declares a clause with an undelimited compound counter; entire displayed counter retained without interpreting or correcting its components',
                             block['source_ref'], details={'displayed_number': marker['number'], 'source_declared_kind': 'clause'})
        if (marker and marker['kind'] == 'point' and not marker['explicit'] and
                block.get('_source_declared_kind') == 'clause' and 'article' in active and 'clause' not in active):
            self.quality.add('source_counter_role_conflict',
                             'Source declares a clause but displays an alphabetic counter; original counter and declared role retained without correction',
                             block['source_ref'], details={'displayed_number': marker['number'], 'source_declared_kind': 'clause'})
            marker = {**marker, 'kind': 'clause'}
        compound = (ALPHA_DECIMAL_COUNTER.match(block.get('text') or '') or
                    DECIMAL_COUNTER.match(block.get('text') or '')) if block['type'] in TEXT_TYPES else None
        if compound:
            number, prefix = compound[1], compound[1].rsplit('.', 1)[0]
            parent = self.generic_numbers.get(prefix) or next(
                (n for _, n in reversed(self.stack) if n.get('number') == prefix), None)
            # Existing numeric decimal handling inside Articles requires an
            # actual source prefix. Alphabetic paths retain a missing-prefix
            # warning instead of being misread as a simple legal point.
            if parent is None and 'article' in active and number[0].isdigit():
                compound = None
        if compound:
            block.update(type='numbered_paragraph', number=number,
                         evidence='source_compound_counter_with_prefix_parent' if parent else 'explicit_compound_counter_without_prefix_parent')
            if parent:
                block['parent_number'] = prefix
                parent['children'].append(block)
            else:
                (self.stack[-1][1]['children'] if self.stack else self.children).append(block)
                code = 'unresolved_decimal_prefix' if number[0].isdigit() else 'unresolved_counter_prefix'
                self.quality.add(code, 'Explicit compound counter has no source prefix parent in this body scope', block['source_ref'])
            self.generic_numbers[number] = block
            # Subsequent lettered subdivisions and prose belong to this
            # decimal unit, rather than its outer numeric prefix.
            if number[0].isdigit():
                self.generic_parent, self.generic_child = block, None
            else:
                self.generic_child = block
            self.previous = block
            return
        if (marker and marker['kind'] == 'point' and not marker['explicit'] and
                self.generic_parent and '.' in self.generic_parent.get('number', '')):
            # A letter below a source decimal topic belongs to that local
            # topic, even when its enclosing Article also contains clauses.
            block.update(type='numbered_paragraph', number=marker['number'],
                         parent_number=self.generic_parent['number'], evidence='source_counter_under_compound_local_parent')
            self.generic_parent['children'].append(block)
            self.generic_numbers = {k: v for k, v in self.generic_numbers.items() if k[0].isdigit()}
            self.generic_numbers[marker['number']] = block
            self.generic_child = self.previous = block
            return
        if marker and marker["kind"] == "point" and not marker["explicit"] and not any(
                k in {"article", "clause"} for k, _ in self.stack):
            block.update(type="numbered_paragraph", number=marker["number"],
                         evidence="source_counter_outside_article_scope")
            marker = None
        if marker and marker["kind"] == "clause" and not marker["explicit"]:
            # Decimal amounts do not match the candidate pattern. Lists introduced
            # by prose inside a legal unit retain their list meaning when uncertain.
            previous_clause = next((n for k, n in reversed(self.stack) if k == 'clause'), None)
            compound_scope = self.generic_parent or self.generic_child
            outer_sibling = bool(compound_scope and '.' in compound_scope.get('number', '') and
                                 previous_clause and previous_clause['number'].isdigit() and marker['number'].isdigit() and
                                 int(marker['number']) == int(previous_clause['number']) + 1)
            introduced_list = not outer_sibling and self.previous and (
                self.previous.get("text", "").endswith(":") or self.previous.get("type") == "numbered_paragraph")
            nested_counter = self.list_context and "clause" in active
            if "article" not in active or (introduced_list or nested_counter) and not marker.get('unusual_counter'):
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
                self.generic_numbers[block['number']] = block
            else:
                target.append(block)
                self.generic_numbers = {block['number']: block}
                self.generic_child = block
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


def scoped_document_blocks(blocks, quality, evidence, phase_hint=None):
    """Retain an evidenced embedded opening or closing in the canonical body."""
    first = blocks[0]
    parsed = build_document(blocks, first['source_ref'], quality, phase_hint=phase_hint)
    wrapper = container('layout_block', first)
    wrapper['evidence'] = evidence
    for key in ('source_layout', 'source_layouts', 'source_identifiers'):
        if key in first:
            wrapper[key] = first[key]
    for section in parsed['children']:
        if section['type'] not in {'header', 'title_block', 'preamble', 'body', 'closing', 'annexes'}:
            if section['type'] == 'enacting_formula':
                # Root section roles cannot occur inside an embedded opening.
                # Keep the literal heading and its explicit enactment evidence.
                section.update(type='heading', evidence='source_embedded_enacting_formula')
            wrapper['children'].append(section)
            continue
        for child in section['children']:
            if child['type'] == 'layout_block' and source_key(child) == source_key(wrapper):
                wrapper['children'].extend(child['children'])
            else:
                wrapper['children'].append(child)
    return wrapper


def scope_attached_acts(blocks, quality):
    """An intermediate signature/header belongs to an attached act's boundary.

    Keep one canonical document body. Local closing and attached letterhead
    blocks preserve source roles and order without repeating root sections.
    """
    index = 0
    while index < len(blocks):
        role = opening_role(blocks[index])
        previous_text = blocks[index - 1].get('text') or '' if index else ''
        promulgation = re.search(r'\b(?:ban bố|công bố)\b.+\b(?:nguyên văn|toàn văn)\s+như sau\s*:\s*$',
                                 previous_text, re.I)
        if (role == 'document_type_heading' and promulgation and
                (blocks[index].get('heading_evidence') or blocks[index].get('_alignment') == 'center')):
            end = next((i for i in range(index + 1, min(index + 16, len(blocks)))
                        if (m := candidate(blocks[i])) and m['explicit'] and
                        m['kind'] in {'chapter', 'article', 'part'}), None)
            if end is not None:
                header = scoped_document_blocks(blocks[index:end], quality, 'attached_legal_act_header')
                blocks = blocks[:index] + [header] + blocks[end:]
                index += 1
                continue
        heading_start = normative_heading(blocks[index])
        if (not heading_start and closing_role(blocks[index]) == 'signer_title' and
                index + 1 < len(blocks) and (closing_role(blocks[index + 1]) in
                {'signature_status', 'signature_marker'} or signer_name_text(blocks[index + 1].get('text') or ''))):
            index += 1; continue
        if role not in {'issuing_authority', 'national_heading'} and not heading_start:
            index += 1; continue
        end = next((i for i in range(index + 1, min(index + 16, len(blocks)))
                    if (m := candidate(blocks[i])) and m['explicit'] and m['kind'] in {'chapter', 'article', 'part'} or
                    re.match(r'^[IVXLCDM]+[.)]\s+', blocks[i].get('text') or '') and blocks[i].get('heading_evidence')), None)
        note_index = next((i for i in range(index + 1, min(index + 16, len(blocks)))
                           if ATTACHMENT_NOTE.match(blocks[i].get('text') or '') or
                           re.search(r'\(\s*(?:Ban hành kèm theo|Kèm theo)\b', blocks[i].get('text') or '', re.I)), None)
        if heading_start and note_index is not None and (end is None or note_index < end):
            # The explicit attachment note closes the title even when the
            # attached act is article-free and begins with ordinary prose.
            end = note_index + 1 if note_index + 1 < len(blocks) else None
        normative = end and any(normative_heading(b) for b in blocks[index:end])
        attachment_note = note_index is not None and end and note_index < end
        if attachment_note and end:
            # A repeated source letterhead and explicit attachment note also
            # delimit titled procedures whose names are not legal-act types.
            roles = {opening_role(b) for b in blocks[index:note_index]}
            normative |= bool({'issuing_authority', 'national_heading', 'national_motto'} <= roles and
                              any(b.get('heading_evidence') and b.get('_alignment') == 'center' and
                                  (b.get('text') or '').isupper() and not opening_role(b)
                                  for b in blocks[index:note_index]))
        previous_legal = max((i for i in range(index) if (m := candidate(blocks[i])) and m['explicit'] and m['kind'] == 'article'), default=-1)
        closing_start = next((i for i in range(previous_legal + 1, index)
                              if closing_role(blocks[i]) in {'recipients', 'delegation_title', 'signer_title', 'signature_status'} or
                              blocks[i].get('_source_closing_layout') or
                              blocks[i].get('evidence') in {'source_signature_block', 'source_addressee_block'}), None)
        if not normative or heading_start and not attachment_note or previous_legal < 0 or (closing_start is None and not attachment_note):
            index += 1; continue
        if closing_start is not None and closing_start > previous_legal + 1:
            name = blocks[closing_start - 1].get('text') or ''
            if 2 <= len(name.split()) <= 7 and all(w.isalpha() and w[0].isupper() for w in name.split()):
                closing_start -= 1
        replacements = ([scoped_document_blocks(blocks[closing_start:index], quality,
                                                'closing_before_attached_legal_act', 'closing')] if closing_start is not None else [])
        replacements.append(scoped_document_blocks(blocks[index:end], quality, 'attached_legal_act_header'))
        if closing_start is None:
            closing_start = index
        blocks = blocks[:closing_start] + replacements + blocks[end:]
        index = closing_start + 2
    return blocks


def build_document(elements, ref, quality, phase_hint=None):
    from vietnam_legal_rag.ingestion.refinement.semantic import annex_candidate
    from vietnam_legal_rag.ingestion.refinement.forms import BLANK, form_boundary, form_header_role, make_form, table_form_boundary
    from vietnam_legal_rag.ingestion.semantics.quotations import scope_quotations, scope_restarted_counters, scope_article_enumerations, scope_body_outlines, scope_contents, scope_terminal_notes
    from vietnam_legal_rag.ingestion.semantics.technical import scope_technical_standards
    blocks = scope_technical_standards(scope_attached_acts(list(logical_blocks(elements)), quality), quality)
    blocks = coalesce(scope_contents(scope_body_outlines(scope_article_enumerations(scope_restarted_counters(scope_quotations(scope_terminal_notes(blocks, quality), quality))))))
    document = container("legal_document", ref=ref)
    section, body, previous, closing_group, current_annex, current_form = None, None, None, None, None, None
    recipient_scopes = {}
    flat_recipient_scope = False
    embedded_contract = False
    phases = {"header": 0, "title_block": 1, "preamble": 2, "enacting_formula": 3, "body": 4, "closing": 5, "annexes": 6}
    phase = phases.get(phase_hint, -1)
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
        if (phase == 5 and not closing and not role and signer_name_text(block.get('text') or '') and
                any(c.islower() for c in block.get('text') or '') and
                (block.get('_source_emphasized_signing_suffix') or
                 block.get('_alignment') == 'center' and block.get('heading_evidence')) and
                any(n['type'] == 'signature' and any(c['type'] == 'signer_title' for c in n['children'])
                    for n in section['children'])):
            closing = 'signer_name'
        if block.get('_source_closing_layout') and re.match(r'^VĂN PHÒNG\b', block.get('text') or '') and block['text'].isupper():
            role = 'issuing_authority'
        if (not role and block.get('_source_closing_layout') and re.fullmatch(
                r'.{1,80},\s*ngày\s*(?:\d+)?\s*tháng\s*(?:\d+)?\s*năm\s*\d{4}',
                block.get('text') or '', re.I)):
            role = 'place_and_date'
            quality.add('incomplete_source_document_date',
                        'Source verification date omits day or month; literal text retained without completing the date',
                        block['source_ref'])
        if (phase == 1 and previous == 'document_type_heading' and role == 'issuing_authority' and
                re.search(r'\bSỐ\s+\S+', block.get('text') or '') and
                re.search(r'\bVỀ\b', block.get('text') or '')):
            role = None  # Combined issuer/number/subject is the source title.
        if (not role and (phase <= 0 or block.get('_source_closing_layout')) and previous == 'issuing_authority' and
                block.get('text', '').isupper() and len(block.get('text', '')) <= 80 and
                re.fullmatch(r'(?:TỈNH|THÀNH PHỐ|HUYỆN|QUẬN|THỊ XÃ)\s+[^\d;:.!?]+', block.get('text', ''))):
            role = 'issuing_authority'
        if (not role and not marker and not closing and phase <= 0 and previous == 'issuing_authority' and i and
                block.get('_source_layout') and block.get('_source_layout') == blocks[i - 1].get('_source_layout') and
                block.get('_scope') == blocks[i - 1].get('_scope') and
                block.get('_alignment') == blocks[i - 1].get('_alignment') == 'center' and
                block.get('text', '').isupper() and len(block.get('text', '')) <= 40 and
                len(block.get('text', '').split()) <= 3):
            role = 'issuing_authority'  # Preserve a wrapped fragment in its explicit source header cell.
        if not closing and signer_before_status(block, following):
            closing = 'signer_name'
        if phase <= 1 and normative_heading(block):
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
        if annex_marker and (phase < 6 or current_annex is None or annex_marker["number"] is not None):
            target = ensure("annexes", block)
            current_form = None
            current_annex = container("annex", block)
            current_annex["_annex_marker"] = annex_marker
            current_annex["number"] = annex_marker["number"]
            current_annex["children"].append(block)
            target["children"].append(current_annex)
            previous = "annex"
            continue
        # A source template can follow the closing without a displayed annex
        # label. Preserve its actual form boundary, not a synthetic annex unit.
        if phase == 5 or phase == 6 and current_annex is None:
            boundary = (form_boundary(block, active=current_form is not None) if block['type'] in TEXT_TYPES
                        else table_form_boundary(block))
            if (boundary is None and phase == 6 and current_form is not None and current_form['children'] and
                    form_header_role(block) == 'issuing_authority' and
                    not (i and blocks[i - 1].get('heading_evidence') and candidate(blocks[i - 1]))):
                # A repeated letterhead, displayed template title and actual
                # blank inputs delimit an uncoded template. Source variants
                # with their own numbered case headings keep their parent.
                title_index = None
                for offset, fragment in enumerate(blocks[i + 1:i + 9], i + 1):
                    proposed = form_boundary(fragment) if fragment['type'] in TEXT_TYPES else None
                    if proposed:
                        if proposed['evidence'] == 'standalone_form_heading':
                            title_index = offset
                        break
                    if (annex_candidate(fragment) or candidate(fragment) or closing_role(fragment) or
                            fragment['type'] not in TEXT_TYPES | {'separator'}):
                        break
                if (title_index is not None and any(BLANK.search(n.get('text') or '')
                        for n in blocks[title_index + 1:title_index + 9])):
                    boundary = {'number': None, 'end': 0, 'header_first': True,
                                'evidence': 'source_repeated_letterhead_and_template_inputs'}
            if (boundary is None and phase == 5 and not (role or closing or marker) and
                    not block.get('_source_closing_layout') and
                    block.get('heading_evidence') and block.get('text', '').isupper() and
                    len(block.get('text', '')) <= 200 and not BLANK.search(block.get('text', ''))):
                nearby = []
                for n in blocks[i + 1:i + 15]:
                    if annex_candidate(n) or closing_role(n) or form_boundary(n) or (
                            (m := candidate(n)) and m['explicit']):
                        break
                    nearby.append(n)
                from vietnam_legal_rag.ingestion.refinement.schema import FIELD_NAME, label_parts
                inputs = sum(bool(BLANK.search(n.get('text') or '') or
                                  (parts := label_parts(n)) and parts[1] is None and
                                  FIELD_NAME.fullmatch(parts[0])) for n in nearby)
                if inputs >= 2:
                    boundary = {'number': None, 'end': 0, 'evidence': 'source_completion_template_after_closing',
                                'header_first': form_header_role(block) == 'issuing_authority'}
            if boundary:
                ensure('annexes', block)
                current_form = make_form(block, boundary)
                section['children'].append(current_form)
                previous = 'form'
                continue
        if phase == 6:
            add_layout(section, block)
            (current_form if current_form is not None else current_annex)["children"].append(block)
            continue
        if marker and not marker["explicit"] and marker["kind"] == "clause" and phase < 3 and initial_opening:
            block.update(type="numbered_paragraph", number=marker["number"])
            marker = None
        header_authority = phase < 2 and initial_header and role == "issuing_authority"
        if phase == 5 or block.get('_source_closing_layout') and phase >= 3 or closing and not header_authority and (closing != "signer_title" or phase >= 4 or block.get("_source_layout")):
            target = ensure("closing", block)
            if block.get('_source_closing_layout') and role in {'issuing_authority', 'document_number', 'place_and_date'} and not (
                    role == 'issuing_authority' and closing_group and closing_group['type'] == 'signature' and
                    closing_group['children'] and closing_group['children'][-1]['type'] == 'delegation_title'):
                closing_group = None
                block['type'] = role
                if role == 'document_number':
                    block['number'] = block['text'].split(':', 1)[1].strip()
            if block.get('_source_closing_layout') and re.match(r'^XÁC THỰC VĂN BẢN HỢP NHẤT\b', block.get('text') or '', re.I):
                closing_group = None
                block.update(type='heading', evidence='source_consolidated_verification_heading')
            if re.match(r"^(?:PHỤ LỤC|Ghi chú\s*:|Chú thích\s*:)", block.get("text", ""), re.I):
                closing_group = None
            if closing == "recipients":
                block["type"] = "recipients"
                target["children"].append(block)
                closing_group = block
                flat_recipient_scope = not block.get('_source_layout')
                if block.get("_source_layout"):
                    recipient_scopes[block["_source_layout"]["table_id"]] = block
            elif (block.get("_source_layout", {}).get("table_id") in recipient_scopes or
                  flat_recipient_scope and closing_group and closing_group['type'] == 'signature' and
                  (following and (re.match(r'^[-–—•]\s*\S', following.get('text') or '') or
                                  following.get('_source_emphasized_signing_suffix')) or
                   any(n.get('_source_emphasized_signing_suffix') for group in target['children']
                       if group['type'] == 'signature' for n in group['children']))) and re.match(r"^[-–—•]\s*\S", block.get("text") or ""):
                block["type"] = "recipient"
                # Source rows interleave signing and recipient columns. Keep
                # their traversal order with an explicit continuation group.
                group = target["children"][-1]
                if group["type"] != "recipients":
                    group = container("recipients", block)
                    group["evidence"] = ("source_recipient_continuation_in_closing_table" if block.get('_source_layout')
                                         else 'source_recipient_continuation_after_signing_block')
                    target["children"].append(group)
                group["children"].append(block)
                closing_group = group
            elif closing in {"delegation_title", "signer_title", "signature_status", "signature_marker", "signer_name"}:
                if (closing_group is None or closing_group["type"] != "signature" or
                        closing == 'delegation_title' and any(n['type'] == 'signer_name' for n in closing_group['children'])):
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
                name = signer_name_text(text)
                if name and any(n["type"] in {"signer_title", "signature_status", "signature_marker"} for n in closing_group["children"]):
                    block["type"] = "signer_name"
                    closing_group["children"].append(block)
                elif (closing_group['children'][-1]['type'] == 'signature_marker' and
                      re.fullmatch(r'[a-z]+\]', text, re.I) and
                      closing_group['children'][-1]['text'].endswith(text)):
                    block['evidence'] = 'source_partial_signature_marker_fragment'
                    closing_group['children'].append(block)
                    quality.add('source_partial_signature_marker',
                                'Source repeats an incomplete suffix of its signing marker; literal fragment retained without repair',
                                block['source_ref'])
                elif role == 'issuing_authority' and closing_group['children'][-1]['type'] == 'delegation_title':
                    # Preserve a split authority line in the existing signing
                    # block. It supplies no evidence of a personal name.
                    closing_group['children'].append(block)
                else:
                    closing_group = None
                    flat_recipient_scope = False
                    target["children"].append(block)
            else:
                flat_recipient_scope = False
                target["children"].append(block)
        elif is_formula(block) and phase < 4 and (phase in {1, 2} or
                next_marker and next_marker["explicit"] and LEVELS[next_marker["kind"]] <= LEVELS["article"]):
            block["type"] = "enacting_formula"
            document["children"].append(block)
            section, phase = None, 3
        elif (marker or phase >= 3 or
              block['type'] == 'numbered_paragraph' and phase >= 1 and previous != 'document_type_heading' or
              block['type'] == 'numbered_paragraph' and phase == 1 and following and
              (re.match(r'^[-–—•+]\s+\S', following.get('text') or '') or
               next_marker and next_marker['kind'] == 'clause' and not next_marker['explicit'] and
               block.get('number', '').isdigit() and next_marker['number'].isdigit() and
               int(next_marker['number']) == int(block['number']) + 1) or
              block.get('evidence') in {'emphasized_roman_body_outline', 'source_article_free_alpha_outline'}):
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
                                if candidate(blocks[j])), len(blocks))
            preamble_evidence = any(opening_role(b) in {'legal_basis', 'proposal_basis'} or is_formula(b)
                                    for b in blocks[i + 1:first_legal])
            title_present = previous != 'document_type_heading' or i and not re.fullmatch(DOCUMENT_TYPES, blocks[i - 1].get('text') or '', re.I)
            if (title_present and preamble_evidence and not role and not block.get('heading_evidence') and
                    not block.get('text', '').isupper() and block['type'] in {'paragraph', 'list'}):
                ensure('preamble', block)['children'].append(block)
                previous = block['type']
                continue
            narrative = not role and not block.get("heading_evidence") and block.get("_alignment") != "center" and (
                len(block.get("text", "")) > 120 and not block.get('text', '').isupper() or block["type"] == "numbered_paragraph")
            if narrative and title_present:
                ensure("body", block)
                body.append(block, following)
                previous = block["type"]
                continue
            target = ensure("title_block", block)
            if ATTACHMENT_NOTE.match(block.get('text') or ''):
                block['type'] = 'paragraph'
                block['evidence'] = 'source_attached_act_note'
            elif role == "issuing_authority" or closing == "signer_title":
                block["type"] = "issuing_authority_title"
            elif (previous == "document_type_heading" or block.get("_alignment") == "center" and not role or
                  previous == 'document_title' and not role and block.get('text', '').isupper()):
                block["type"] = "document_title"
            target["children"].append(block)
        elif phase == 2:
            if (role == 'issuing_authority' and closing == 'signer_title' and following and
                    opening_role(following) in {'legal_basis', 'proposal_basis'}):
                block['type'] = 'issuing_authority_title'
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
