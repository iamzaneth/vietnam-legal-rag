"""General patterns discovered by the real-document validation batch."""
import unittest

from vietnam_legal_rag.ingestion.extract_legal_documents import encoded, parse_source
from vietnam_legal_rag.ingestion.validation.extract import walk_content
from vietnam_legal_rag.ingestion.html.structure import document_number_roles, document_numbers

SOURCE = {"layer": "raw", "path": "content.html", "sha256": "a" * 64}


def parse(html):
    return parse_source(html, "content", "Nội dung", "https://vbpl.vn/doc--1", "vbpl:1", SOURCE)


class BatchSourcePatternTests(unittest.TestCase):
    def check(self, html):
        result = parse(html)
        self.assertTrue(result["validation"]["meaningful_text_preserved"], result["issues"])
        self.assertTrue(result["validation"]["schema_valid"], result["issues"])
        self.assertTrue(result["hierarchy_validation"]["semantic_complete"], result["issues"])
        self.assertEqual(encoded(result), encoded(parse(html)))
        return result

    def test_attached_act_after_signature_keeps_one_body_and_independent_counters(self):
        result = self.check('<p>Điều 1. Ban hành quy chế.</p><p>Điều 2. Thi hành.</p>'
                            '<p>Nơi nhận:</p><p>- Cơ quan thực hiện.</p><p>KT. CHỦ TỊCH</p>'
                            '<p>PHÓ CHỦ TỊCH</p><p>Nguyễn Văn A</p>'
                            '<p><b>ỦY BAN NHÂN DÂN</b></p><p><b>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</b></p>'
                            '<p><b>Độc lập - Tự do - Hạnh phúc</b></p>'
                            '<p><strong>QUY CHẾ</strong><sup>[3]</sup></p><p><b>Về phối hợp thực hiện</b></p>'
                            '<p>Chương I</p><p><b>QUY ĐỊNH CHUNG</b></p>'
                            '<p>Điều 1. Phạm vi.</p><p>1. Nội dung.</p><p>Điều 2. Trách nhiệm.</p>')
        self.assertEqual(sum(n['type'] == 'body' for n in result['document']['children']), 1)
        self.assertEqual(result['hierarchy_validation']['legal_hierarchy']['articles'], 4)
        self.assertEqual(result['hierarchy_validation']['legal_hierarchy']['chapters'], 1)
        nodes = list(walk_content([result['document']]))
        self.assertTrue(any(n.get('evidence') == 'attached_legal_act_header' for n in nodes))
        self.assertTrue(any(n.get('title') == 'QUY ĐỊNH CHUNG' for n in nodes))

    def test_unconsumed_split_label_in_closing_preserves_its_title(self):
        result = self.check('<p>Điều 1. Thi hành.</p><p>Nơi nhận:</p><p>- Cơ quan.</p>'
                            '<p>Chương I</p><p><b>VĂN BẢN ĐƯỢC TRÍCH DẪN</b></p>')
        self.assertTrue(any(n.get('text') == 'VĂN BẢN ĐƯỢC TRÍCH DẪN'
                            for n in walk_content([result['document']])))

    def test_footer_excerpt_counters_do_not_become_articles_or_form_fields(self):
        result = self.check('<p>Điều 1. Nội dung.</p><hr><ol><li><p>Quy định sửa đổi như sau:</p>'
                            '<p>Điều 5. Thi hành</p><p>1…</p><p>2. Có hiệu lực từ ngày ban hành.</p>'
                            '<em>↩</em></li></ol>')
        self.assertEqual(result['hierarchy_validation']['legal_hierarchy']['articles'], 1)
        nodes = list(walk_content([result['document']]))
        self.assertEqual(sum(n['type'] == 'footnote' for n in nodes), 1)
        self.assertEqual(sum(n['type'] == 'form_field' for n in nodes), 0)
        self.assertTrue(any(n.get('evidence') == 'source_footnote_provision_excerpt' for n in nodes))

    def test_english_translation_headings_use_the_same_source_backed_hierarchy(self):
        result = self.check('<p>LAW ON BUSINESS</p><p>Pursuant to the Constitution;</p>'
                            '<p>Chapter I</p><p>GENERAL PROVISIONS</p>'
                            '<p><b>Article 1.-</b>Scope</p><p>1. First provision.</p>'
                            '<p>a) First requirement.</p><p>b) Second requirement.</p>'
                            '<p>Section I. IMPLEMENTATION</p>'
                            '<p>Article 2.-Responsibilities</p><p>Article 1 of this Law applies.</p>')
        counts = result['hierarchy_validation']['legal_hierarchy']
        self.assertEqual((counts['chapters'], counts['sections'], counts['articles'], counts['clauses'], counts['points']), (1, 1, 2, 1, 2))
        nodes = list(walk_content([result['document']]))
        article = next(n for n in nodes if n['type'] == 'article')
        self.assertEqual(article['label'], 'Article 1')
        self.assertEqual(article['label_suffix'], '.-')
        self.assertEqual(article['title'], 'Scope')
        self.assertTrue(any(n.get('text') == 'Article 1 of this Law applies.' and n['type'] == 'paragraph' for n in nodes))
        self.assertTrue(any(n['type'] == 'document_type_heading' and n.get('text') == 'LAW' for n in nodes))

    def test_slash_points_and_hyphen_clauses_preserve_their_source_markers(self):
        result = self.check('<p>Article 1.-Scope</p><p>1- Requirements:</p>'
                            '<p>a/ First requirement.</p><p>b/ Second requirement.</p>'
                            '<p>2- Other provision.</p><p>3/ Further provision.</p>'
                            '<p>1-3 days is a range.</p><p>a/b is a ratio.</p><p>3/ 4 is a fraction.</p>')
        counts = result['hierarchy_validation']['legal_hierarchy']
        self.assertEqual((counts['clauses'], counts['points']), (3, 2))
        nodes = list(walk_content([result['document']]))
        self.assertTrue(any(n['type'] == 'point' and n['label'].strip() == 'a/' for n in nodes))
        self.assertTrue(any(n['type'] == 'paragraph' and n.get('text') == '1-3 days is a range.' for n in nodes))
        self.assertTrue(any(n['type'] == 'paragraph' and n.get('text') == 'a/b is a ratio.' for n in nodes))
        self.assertTrue(any(n['type'] == 'paragraph' and n.get('text') == '3/ 4 is a fraction.' for n in nodes))

    def test_actual_duplicate_source_numbers_remain_actionable_diagnostics(self):
        html = '<p>Chapter I</p><p>Article 8.-First provision</p><p>1. Content.</p>' \
               '<p>Article 8.-Second provision</p><p>1. Content.</p><p>2. Content.</p><p>2. Other content.</p>'
        result = parse(html)
        self.assertTrue(result['validation']['meaningful_text_preserved'])
        self.assertTrue(result['validation']['schema_valid'])
        self.assertFalse(result['hierarchy_validation']['semantic_complete'])
        self.assertEqual(sum(i['code'] == 'duplicate_legal_number' for i in result['issues']), 2)

    def test_article_free_roman_headings_form_local_outline_before_signature(self):
        result = self.check('<p>THÔNG TƯ</p><p>Về tổ chức thực hiện</p>'
                            '<p><b>I. TỔ CHỨC</b></p><p>1. Trách nhiệm.</p><p>2. Phối hợp.</p>'
                            '<p><b>II. THỰC HIỆN</b></p><p>Nội dung tiếp theo.</p>'
                            '<p>Nơi nhận:</p><p>- Cơ quan.</p><p>CHỦ TỊCH</p><p>Nguyễn Văn A</p>')
        self.assertEqual(result['hierarchy_validation']['legal_hierarchy']['articles'], 0)
        nodes = list(walk_content([result['document']]))
        self.assertTrue(any(n.get('evidence') == 'emphasized_roman_body_outline' for n in nodes))
        self.assertTrue(any(n['type'] == 'list_item' and n.get('number') == 'II' for n in nodes))
        self.assertTrue(any(n['type'] == 'body' for n in result['document']['children']))
        self.assertTrue(any(n['type'] == 'closing' for n in result['document']['children']))

    def test_uppercase_alpha_headings_are_between_roman_and_numeric_outline_levels(self):
        result = self.check('<p>THÔNG TƯ</p><p>Về tổ chức</p><p><b>I. PHẠM VI</b></p>'
                            '<p><b>A. NHÓM THỨ NHẤT</b></p><p>1. Nội dung.</p>'
                            '<p><b>B. NHÓM THỨ HAI</b></p><p>1. Nội dung khác.</p>'
                            '<p><b>C. NHÓM THỨ BA</b></p><p>1. Nội dung cuối.</p>'
                            '<p><b>II. THỰC HIỆN</b></p><p>Nội dung triển khai.</p>')
        nodes = list(walk_content([result['document']]))
        for number in ('A', 'B', 'C'):
            item = next(n for n in nodes if n['type'] == 'list_item' and n.get('number') == number)
            self.assertEqual(item['children'][0]['type'], 'list')
            self.assertEqual(item['children'][0]['children'][0]['number'], '1')

    def test_source_heading_class_supports_plain_uppercase_outline_subdivisions(self):
        result = self.check('<p>THÔNG TƯ</p><p>Về tổ chức</p><p><b>I. TỔ CHỨC</b></p>'
                            '<p class="prov-chapter">A. NHÓM THỨ NHẤT</p><p>1. Nội dung.</p>'
                            '<p class="prov-chapter">B. NHÓM THỨ HAI</p><p>1. Nội dung khác.</p>'
                            '<p><b>II. THỰC HIỆN</b></p><p>Nội dung triển khai.</p>')
        nodes = list(walk_content([result['document']]))
        subdivisions = [n for n in nodes if n['type'] == 'list_item' and n.get('number') in {'A', 'B'}]
        self.assertEqual(len(subdivisions), 2)
        self.assertTrue(all(n['heading_evidence'] == 'source_provision_heading_class' for n in subdivisions))

    def test_missing_quote_cannot_absorb_next_explicit_amendment(self):
        html = '<p>Article 1. Amendments.</p><p>31. To amend Article 82 as follows:</p>' \
               '<p>“Article 82. Licensing</p><p>1. First provision.</p><p>2. Other provision.</p>' \
               '<p>32. To amend Article 83 as follows:</p><p>“Article 83. Responsibility</p>' \
               '<p>1. Responsible authority.”</p><p>Article 2.</p><p>1. This Law takes effect.</p>'
        result = parse(html)
        self.assertTrue(result['validation']['meaningful_text_preserved'])
        self.assertTrue(result['validation']['schema_valid'])
        self.assertEqual(result['hierarchy_validation']['legal_hierarchy']['articles'], 2)
        self.assertEqual(result['hierarchy_validation']['legal_hierarchy']['clauses'], 3)
        self.assertEqual([i['code'] for i in result['issues'] if i['severity'] == 'warning'], ['incomplete_source_quotation'])
        self.assertFalse(result['hierarchy_validation']['semantic_complete'])
        self.assertEqual(encoded(result), encoded(parse(html)))

    def test_clause_sequence_and_points_continue_around_opaque_table_children(self):
        result = self.check('<p>Điều 1. Phạm vi:</p><p>1. Cấp tỉnh:</p><p>a) Định mức:</p>'
                            '<table><tr><th>Nội dung</th><th>Giá trị</th></tr>'
                            '<tr><td>Nhóm A</td><td>10</td></tr></table><p>b) Công việc khác.</p>'
                            '<p>2. Cấp huyện.</p>')
        counts = result['hierarchy_validation']['legal_hierarchy']
        self.assertEqual((counts['clauses'], counts['points']), (2, 2))
        self.assertEqual(result['hierarchy_validation']['unresolved']['orphan_nodes'], 0)

    def test_source_unit_qualifier_is_part_of_named_column_header(self):
        result = self.check('<p>Điều 1.</p><table><tr><td><b>Nội dung</b></td>'
                            '<td><p><b>Định mức</b></p><p>(triệu đồng/biên chế/năm)</p></td></tr>'
                            '<tr><td>Nhóm A</td><td>38</td></tr></table>')
        table = next(n for n in walk_content([result['document']]) if n['type'] == 'table')
        self.assertEqual(table['table_kind'], 'data')
        self.assertEqual(table['cells'][1]['role'], 'column_header')
        self.assertEqual(table['cells'][1]['effective_text'], 'Định mức (triệu đồng/biên chế/năm)')

    def test_spanned_assignment_table_has_no_invented_axis_semantics(self):
        result = self.check('<p>Điều 1.</p><table><tr><td rowspan="2">Kinh phí</td>'
                            '<td rowspan="2">=</td><td rowspan="2">Tổng kinh phí</td>'
                            '<td rowspan="2">X</td><td rowspan="2">11%</td>'
                            '<td rowspan="2">X</td><td>Giá trị trên địa bàn</td></tr>'
                            '<tr><td>Giá trị toàn tỉnh</td></tr></table>')
        table = next(n for n in walk_content([result['document']]) if n['type'] == 'table')
        self.assertEqual(table['table_kind'], 'key_value')
        self.assertEqual(len(table['cells']), 8)
        self.assertEqual(table['grid_shape']['rows'], 2)
        self.assertTrue(all('role' not in c and 'confidence' not in c for c in table['cells']))

    def test_slash_delegation_abbreviation_requires_actual_authority_evidence(self):
        result = self.check('<p>Điều 1. Thi hành.</p><table><tr><td>'
                            '<p>KT/CHỦ TỊCH UBND TỈNH</p><p>PHÓ CHỦ TỊCH</p>'
                            '<p>(Đã ký)</p><p>Nguyễn Văn A</p></td></tr></table>')
        self.assertTrue(any(n['type'] == 'delegation_title' and n.get('text') == 'KT/CHỦ TỊCH UBND TỈNH'
                            for n in walk_content([result['document']])))
        ordinary = parse('<p>Điều 1. Công thức.</p><p>Q/ x là tỷ số.</p>')
        self.assertTrue(ordinary['validation']['meaningful_text_preserved'])
        self.assertTrue(ordinary['validation']['schema_valid'])
        self.assertFalse(any(n['type'] == 'delegation_title' for n in walk_content([ordinary['document']])))

    def test_motivation_before_explicit_basis_or_formula_stays_in_preamble(self):
        result = self.check('<p>LUẬT VỀ TỔ CHỨC</p><p>Để tổ chức thực hiện công việc;</p>'
                            '<p>Căn cứ Hiến pháp;</p><p>Điều 1. Phạm vi.</p>')
        sections = result['document']['children']
        preamble = next(n for n in sections if n['type'] == 'preamble')
        self.assertEqual(preamble['children'][0]['text'], 'Để tổ chức thực hiện công việc;')
        self.assertEqual(preamble['children'][1]['type'], 'legal_basis')
        result = self.check('<p>NGHỊ QUYẾT</p><p>Về tổ chức thực hiện</p>'
                            '<ul><li>Sau khi nghe báo cáo và thảo luận;</li></ul>'
                            '<p>QUYẾT NGHỊ</p><p>Điều 1. Thi hành.</p>')
        self.assertTrue(any(n['type'] == 'preamble' for n in result['document']['children']))
        self.assertTrue(any(n['type'] == 'enacting_formula' for n in result['document']['children']))

    def test_amendment_control_icons_are_audited_but_provision_is_preserved(self):
        html = '<p>Điều 1. Phạm vi.</p><div data-provision-highlighted="true">' \
               '<div><button class="ant-btn"><svg><path></path></svg>Thao tác nguồn</button></div>' \
               '<div><p>1. Nội dung còn nguyên.</p></div></div>'
        result = self.check(html)
        self.assertEqual(result["hierarchy_validation"]["legal_hierarchy"]["clauses"], 1)
        self.assertEqual(result["ignored_elements"][0]["text"], "Thao tác nguồn")
        self.assertEqual(result["issue_summary"]["warning"], 0)
        ordinary = parse('<p>Điều 1.</p><button>Nội dung nguồn</button>')
        self.assertFalse(ordinary["ignored_elements"])

    def test_embedded_html_title_is_metadata_with_audited_source_evidence(self):
        result = self.check('<title>Source document metadata</title><p>Điều 1. Nội dung.</p>')
        self.assertEqual(result["ignored_elements"][0]["reason"], "embedded_document_metadata")
        self.assertEqual(result["ignored_elements"][0]["text"], "Source document metadata")

    def test_directive_without_articles_has_a_body_and_structured_lists(self):
        result = self.check('<p align="center"><b>CHỈ THỊ</b></p>'
                            '<p align="center"><b>Về việc tổ chức thực hiện</b></p>'
                            '<p>' + 'Nội dung chỉ đạo thực hiện công việc. ' * 5 + '</p>'
                            '<p>1. Cơ quan thực hiện:</p><p>- Công việc một.</p><p>- Công việc hai.</p>'
                            '<p>2. Cơ quan phối hợp.</p>')
        body = next(n for n in result["document"]["children"] if n["type"] == "body")
        self.assertEqual(sum(n["type"] == "list" for n in walk_content([body])), 1)
        self.assertEqual(result["hierarchy_validation"]["legal_hierarchy"]["clauses"], 0)

    def test_multiblock_replacement_counters_do_not_leak_to_enclosing_act(self):
        html = '<p>Điều 1. Sửa đổi văn bản.</p><p>1. Sửa đổi như sau:</p>' \
               '<p>a) Sửa đổi nội dung:</p><p>"5. Nội dung mới:</p>' \
               '<p>a) Yêu cầu thứ nhất;</p><p>b) Yêu cầu thứ hai;</p>' \
               '<p>Giải thích tiếp theo.".</p><p>b) Sửa đổi phần tiếp theo.</p>' \
               '<p>Điều 2. Thi hành.</p>'
        result = self.check(html)
        self.assertEqual(result["hierarchy_validation"]["legal_hierarchy"]["clauses"], 1)
        self.assertEqual(result["hierarchy_validation"]["legal_hierarchy"]["points"], 2)
        nodes = list(walk_content([result["document"]]))
        quote = next(n for n in nodes if n.get("evidence") == "explicit_source_quotation" and n["type"] == "layout_block")
        items = [n for n in walk_content([quote]) if n["type"] == "list_item"]
        self.assertEqual([n["number"] for n in items], ["5", "a", "b"])
        self.assertEqual(items[-1]["children"][0]["text"], 'Giải thích tiếp theo.".')

    def test_curly_quote_and_incomplete_quote_keep_source_faithful(self):
        result = self.check('<p>Điều 1.</p><p>1. Thay thế:</p><p>“Điều 7. Nội dung mới</p>'
                            '<p>1. Yêu cầu một;</p><p>2. Yêu cầu hai.”</p><p>Điều 2.</p>')
        self.assertEqual(result["hierarchy_validation"]["legal_hierarchy"]["articles"], 2)
        self.assertEqual(result["hierarchy_validation"]["legal_hierarchy"]["clauses"], 1)
        incomplete = parse('<p>Điều 1.</p><p>“Văn bản chưa có dấu đóng.</p>')
        self.assertTrue(incomplete["validation"]["meaningful_text_preserved"])
        self.assertFalse(any(n.get("evidence") == "explicit_source_quotation" for n in walk_content([incomplete["document"]])))

    def test_header_authority_in_layout_table_is_not_a_closing_signature(self):
        result = self.check('<table><tr><td><p>THỦ TƯỚNG CHÍNH PHỦ</p></td>'
                            '<td><p>CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM</p>'
                            '<p>Độc lập - Tự do - Hạnh phúc</p></td></tr></table>'
                            '<p>CHỈ THỊ</p><p align="center">Về việc tổ chức thực hiện</p>'
                            '<p>' + 'Cơ quan thực hiện theo yêu cầu nguồn. ' * 5 + '</p>'
                            '<p>1. Cơ quan chủ trì:</p><p>- Công việc một.</p><p>- Công việc hai.</p>'
                            '<p>2. Cơ quan phối hợp.</p>')
        self.assertEqual([n["type"] for n in result["document"]["children"]], ["header", "title_block", "body"])

    def test_sparse_numbered_body_owns_alpha_items_and_continuation(self):
        result = self.check('<p>1. Công tác thứ nhất:</p><p>Giải thích thứ nhất.</p>'
                            '<p>2. Công tác thứ hai:</p><p>a) Yêu cầu một.</p><p>Giải thích.</p>'
                            '<p>b) Yêu cầu hai.</p><p>Điều 1. Quy định khác.</p>')
        numbers = [n for n in walk_content([result["document"]]) if n["type"] == "numbered_paragraph"]
        self.assertEqual([n["number"] for n in numbers], ["1", "2", "a", "b"])
        self.assertEqual(numbers[2]["children"][0]["text"], "Giải thích.")
        self.assertEqual(result["hierarchy_validation"]["unresolved"]["orphan_nodes"], 0)

    def test_bounded_counter_restart_is_a_local_enumeration(self):
        result = self.check('<p>Điều 1.</p><p>1. Phạm vi.</p><p>2. Đối tượng áp dụng:</p>'
                            '<p>1. Đối tượng thứ nhất.</p><p>2. Đối tượng thứ hai.</p><p>Điều 2.</p>')
        self.assertEqual(result["hierarchy_validation"]["legal_hierarchy"]["clauses"], 2)
        self.assertEqual(sum(n["type"] == "list_item" for n in walk_content([result["document"]])), 2)

    def test_legacy_signature_and_addressee_tables_use_local_layout_semantics(self):
        for html in ('<table><tr><td></td><td><p>TM. UỶ BAN NHÂN DÂN</p>'
                     '<p>CHỦ TỊCH</p><p>(Đã ký)</p><p>Nguyễn Văn A</p></td></tr></table>',
                     '<table><tr><td>Kính gửi:</td><td><p>- Cơ quan A</p><p>- Cơ quan B</p></td></tr></table>'):
            result = self.check(html)
            block = next(n for n in walk_content([result["document"]]) if n.get("source_layout"))
            self.assertEqual(block["source_layout"]["table_kind"], "layout")
            self.assertIn(block["children"][0]["type"], {"signature", "recipients"})
            self.assertFalse(any(n["type"] == "table" for n in walk_content([result["document"]])))

    def test_legacy_hyphenated_reference_numbers_preserve_primary_and_mentions(self):
        self.assertEqual(document_number_roles('Chỉ thị số 39-TTg thi hành Quyết định số 780-TTg'),
                         {"primary_document_number_candidate": "39-TTg", "mentioned_document_numbers": ["780-TTg"]})
        self.assertEqual(document_numbers('Nghị quyết số 498-NQ/HĐNN7 ngày 29-2-1984; 30-50%; x-y'), ['498-NQ/HĐNN7'])
        self.assertEqual(document_number_roles('Luật Thuế Lợi tức số 270b-NQ/HĐNN8'),
                         {'primary_document_number_candidate': '270b-NQ/HĐNN8', 'mentioned_document_numbers': []})
        self.assertEqual(document_number_roles('Quyết định số 1417/TC/TCĐN Ban hành quy định'),
                         {'primary_document_number_candidate': '1417/TC/TCĐN', 'mentioned_document_numbers': []})

    def test_letter_header_ends_before_body_and_quoted_list_continuations(self):
        result = self.check('<p>ỦY BAN NHÂN DÂN</p><p>Số: 01/UBND</p>'
                            '<p>' + 'Nội dung đính chính nguồn đã được công bố. ' * 5 + '</p>'
                            '<p>- Đính chính mục một:</p><p>“1. Nội dung thứ nhất.”</p>'
                            '<p>- Đính chính mục hai:</p><p>“2. Nội dung thứ hai.”</p>')
        self.assertEqual([n["type"] for n in result["document"]["children"]], ["header", "body"])
        listing = next(n for n in walk_content([result["document"]]) if n.get("style") == "dash")
        self.assertEqual(len(listing["children"]), 2)
        self.assertTrue(all(n["children"] for n in listing["children"]))

    def test_article_local_alpha_sequence_does_not_invent_a_clause(self):
        result = self.check('<p>Điều 4.</p><p>Các nhiệm vụ được quy định như sau:</p>'
                            '<p>a) Nhiệm vụ thứ nhất;</p><p>b) Nhiệm vụ thứ hai.</p><p>Điều 5.</p>')
        self.assertEqual(result['hierarchy_validation']['legal_hierarchy']['clauses'], 0)
        self.assertEqual(result['hierarchy_validation']['legal_hierarchy']['points'], 0)
        self.assertEqual(sum(n['type'] == 'list_item' for n in walk_content([result['document']])), 2)
        isolated = parse('<p>Điều 4.</p><p>a) Điểm chưa có khoản.</p>')
        self.assertTrue(any(i['code'] == 'orphan_point' for i in isolated['issues']))

    def test_roman_article_outline_owns_decimal_and_alpha_subdivisions(self):
        result = self.check('<p>Điều 1.</p><p><b>I. Các tuyến đường:</b></p>'
                            '<p>1.1.Các tuyến thứ nhất:</p><p>a. Đường thứ nhất.</p><p>b. Đường thứ hai.</p>'
                            '<p><b>II. Xử lý vi phạm:</b></p><p>1. Yêu cầu thứ nhất.</p><p>2. Yêu cầu thứ hai.</p>'
                            '<p>Điều 2.</p>')
        self.assertEqual(result['hierarchy_validation']['legal_hierarchy']['clauses'], 0)
        items = [n for n in walk_content([result['document']]) if n['type'] == 'list_item']
        self.assertEqual([n['number'] for n in items], ['I', '1.1', 'a', 'b', 'II', '1', '2'])

    def test_article_number_with_attached_footnote_remains_an_article(self):
        result = self.check('<p><strong>Điều 4</strong><sup>[3]</sup><strong>. Phạm vi</strong></p>'
                            '<p>1. Nội dung.</p><p>Điều 5.</p><p>1. Nội dung khác.</p>')
        self.assertEqual(result['hierarchy_validation']['legal_hierarchy']['articles'], 2)

    def test_bold_td_ordinal_headers_join_source_qualifier_lines(self):
        result = self.check('<p>Điều 1.</p><table><tr><td><b>STT</b></td>'
                            '<td><p><b>Hệ số sử dụng đất</b></p><p><b>(theo quy hoạch)</b></p></td>'
                            '<td><p><b>Hệ số điều chỉnh</b></p><p><b>theo quy hoạch</b></p></td></tr>'
                            '<tr><td>1</td><td>≤ 1,50</td><td>1,00</td></tr></table>')
        table = next(n for n in walk_content([result['document']]) if n['type'] == 'table')
        self.assertEqual(table['cells'][1]['role'], 'column_header')
        self.assertEqual(table['cells'][1]['source_ref']['tag'], 'td')
        self.assertEqual(table['cells'][-1]['association_status'], 'supported')

    def test_shaded_spanning_header_band_has_source_backed_column_axes(self):
        result = self.check('<p>Điều 1.</p><table><tr><td rowspan="2" style="background-color:#eee">Thành phần</td>'
                            '<td colspan="2" style="background-color:#eee">Mùa khô</td></tr>'
                            '<tr><td style="background-color:#ddd">Cao điểm</td><td style="background-color:#ddd">Thấp điểm</td></tr>'
                            '<tr><td>Chi phí</td><td>X</td><td>0</td></tr></table>')
        table = next(n for n in walk_content([result['document']]) if n['type'] == 'table')
        self.assertEqual(len(table['cells'][-1]['header_refs']['column']), 2)

    def test_symbol_definitions_preserve_table_geometry_without_axis_metadata(self):
        result = self.check('<p>Điều 1.</p><table><tr><td>A</td><td>=</td><td>Giá trị thứ nhất;</td></tr>'
                            '<tr><td>B</td><td>=</td><td>Giá trị thứ hai.</td></tr></table>')
        table = next(n for n in walk_content([result['document']]) if n['type'] == 'table')
        self.assertEqual(table['table_kind'], 'key_value')
        self.assertEqual(len(table['cells']), 6)
        self.assertTrue(all('role' not in c and 'confidence' not in c for c in table['cells']))

    def test_empty_state_svg_is_audited_while_source_media_is_retained(self):
        html = '<div class="ant-empty"><div class="ant-empty-image"><svg><title>Trống</title></svg></div><div>Không có dữ liệu</div></div>'
        result = parse_source(html, 'tab_lenh_cong_bo', 'Lệnh công bố', 'https://vbpl.vn/doc--1', 'vbpl:1', SOURCE)
        self.assertTrue(result['validation']['meaningful_text_preserved'])
        self.assertFalse(result['issue_summary']['warning'])
        self.assertEqual(result['ignored_elements'][0]['reason'], 'empty_state_interface_graphic')
        self.assertTrue(any(i['code'] == 'non_text_content' for i in parse('<svg><title>Biểu đồ nguồn</title></svg>')['issues']))

    def test_interleaved_signer_column_does_not_interrupt_recipients(self):
        result = self.check('<p>Điều 1.</p><table><tr><td>Nơi nhận:</td><td>BỘ TRƯỞNG</td></tr>'
                            '<tr><td><p>- Cơ quan A;</p><p>- Cơ quan B.</p></td><td><p>(Đã ký)</p><p>Nguyễn Văn A</p></td></tr></table>')
        recipients = [n for n in walk_content([result['document']]) if n['type'] == 'recipient']
        self.assertEqual(len(recipients), 2)
        groups = [n for n in walk_content([result['document']]) if n['type'] == 'recipients']
        self.assertEqual(groups[0]['text'], 'Nơi nhận:')
        self.assertEqual(groups[-1]['evidence'], 'source_recipient_continuation_in_closing_table')

    def test_annex_alpha_sequence_retains_formula_continuations(self):
        result = self.check('<p>Điều 1.</p><p>PHỤ LỤC I. Phương pháp</p><p>1. Cách tính:</p>'
                            '<p>a) Trường hợp thứ nhất:</p><p>Công thức A = B + C.</p>'
                            '<p>b) Trường hợp thứ hai.</p><p>2. Phương pháp khác.</p>')
        items = [n for n in walk_content([result['document']]) if n['type'] == 'list_item']
        self.assertEqual(items[0]['children'][0]['text'], 'Công thức A = B + C.')

    def test_annex_nested_dash_lists_do_not_break_alpha_sibling_sequence(self):
        result = self.check('<p>Điều 1.</p><p>Phụ lục I</p><p>1. Phương pháp:</p>'
                            '<p>a) Trường hợp thứ nhất:</p><p>- Yêu cầu một.</p><p>- Yêu cầu hai.</p>'
                            '<p>b) Trường hợp thứ hai:</p><p>- Yêu cầu ba.</p><p>- Yêu cầu bốn.</p>'
                            '<p>c) Trường hợp cuối.</p><p>2. Nội dung khác.</p>')
        nodes = list(walk_content([result['document']]))
        alpha = [n for n in nodes if n['type'] == 'list' and n.get('evidence') == 'annex_alpha_sequence_with_source_continuations']
        self.assertEqual(len(alpha), 1)
        self.assertEqual([n['number'] for n in alpha[0]['children']], ['a', 'b', 'c'])
        self.assertEqual(alpha[0]['children'][1]['children'][0]['type'], 'list')

    def test_contract_contents_and_lettered_appendices_keep_their_local_scope(self):
        result = self.check('<p>Điều 1.</p><p>Phụ lục IV</p><p>MỤC LỤC</p>'
                            '<p>Điều 1. Giá mua bán</p><p>Điều 2. Thanh toán</p>'
                            '<p>Phụ lục A: Giá</p><p>Phụ lục B: Thông số</p>'
                            '<p align="center"><span style="font-weight:bold">HỢP ĐỒNG MUA BÁN</span></p>'
                            '<p>Địa chỉ: ...................</p>'
                            '<p><span style="font-weight:bold">Điều 1. Giá mua bán</span></p>'
                            '<p>1. Giá theo thỏa thuận thứ nhất trong hợp đồng mua bán.</p><p>Giải thích về giá.</p>'
                            '<p>2. Giá theo thỏa thuận thứ hai trong hợp đồng mua bán.</p>'
                            '<p><span style="font-weight:bold">Phụ lục A</span></p>'
                            '<p>BIỂU GIÁ</p><p>Đơn giá: ...................</p>')
        self.assertEqual(result['hierarchy_validation']['annex_hierarchy']['annexes'], 1)
        self.assertEqual(result['hierarchy_validation']['legal_hierarchy']['articles'], 1)
        nodes = list(walk_content([result['document']]))
        self.assertEqual(sum(n['type'] == 'form' for n in nodes), 1)
        self.assertTrue(any(n.get('evidence') == 'explicit_source_table_of_contents' for n in nodes))
        self.assertTrue(any(n.get('evidence') == 'explicit_article_heading_in_source_template' for n in nodes))
        self.assertTrue(any(n.get('evidence') == 'source_template_article_local_counters' for n in nodes))
        self.assertTrue(any(n['type'] == 'annex_heading' and n.get('text') == 'Phụ lục A' for n in nodes))

    def test_directive_decimal_items_have_exact_source_prefix_parents(self):
        result = self.check('<p>1. Yêu cầu thứ nhất.</p><p>2. Yêu cầu thứ hai.</p>'
                            '<p>2.1. Công việc một.</p><p>Giải thích tiếp theo.</p><p>2.2. Công việc hai.</p>'
                            '<p>3. Yêu cầu thứ ba.</p>')
        numbers = [n for n in walk_content([result['document']]) if n['type'] == 'numbered_paragraph']
        parent = next(n for n in numbers if n['number'] == '2')
        self.assertEqual([n['number'] for n in parent['children']], ['2.1', '2.2'])
        self.assertEqual(parent['children'][0]['children'][0]['text'], 'Giải thích tiếp theo.')
        ordinary = parse('<p>Đoạn văn nguồn.</p><p>2.5 kg là khối lượng đã tính.</p>')
        self.assertTrue(ordinary['validation']['meaningful_text_preserved'])
        self.assertFalse(any(n.get('number') == '2.5' for n in walk_content([ordinary['document']])))


if __name__ == "__main__":
    unittest.main()
