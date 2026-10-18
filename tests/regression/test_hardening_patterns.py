"""Portable adversarial patterns exposed by incremental real-source waves."""
import unittest

from tests.support import parse_forms, nodes
from vietnam_legal_rag.ingestion.validation.extract import walk_content


class HardeningPatternTests(unittest.TestCase):
    def test_template_number_suffix_cannot_replace_the_displayed_title(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 7</p><p>BỘ TÀI CHÍNH</p>'
                             '<p><b>/QĐ-CQ</b></p><p>Ngày ... tháng ... năm ...</p>'
                             '<p><b>GIẤY PHÉP</b></p><p>Tên: ...</p>')
        self.assert_integrity(result)
        self.assertTrue(any(n['text'] == '/QĐ-CQ' for n in nodes(result, 'form_number')))
        self.assertEqual(nodes(result, 'form')[0]['title'], 'GIẤY PHÉP')

    def test_explicit_template_caption_owns_its_first_letterhead(self):
        result = parse_forms('<p>Điều 1. Thi hành.</p><p>Nơi nhận:</p><p>- Lưu.</p>'
                             '<p>Mẫu 7. Giấy phép đăng ký</p><p>BỘ TÀI CHÍNH</p>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p>'
                             '<p>Ngày ... tháng ... năm ...</p><p><b>GIẤY PHÉP</b></p><p>Tên: ...</p>')
        self.assert_integrity(result)
        self.assertEqual([n.get('number') for n in nodes(result, 'form')], ['7'])
        self.assertTrue(any(n['type'] == 'form_header' for n in walk_content(nodes(result, 'form')[0]['children'])))

    def test_document_set_cover_is_not_an_issuing_authority(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 3</p><p>BỘ TÀI CHÍNH</p>'
                             '<p><b>BỘ HỒ SƠ ĐĂNG KÝ[2]</b></p>'
                             '<p><b>THÔNG TIN SẢN PHẨM …[3]</b></p><p>I. Thông tin chung</p>')
        self.assert_integrity(result)
        self.assertFalse(any('BỘ HỒ SƠ' in n.get('text', '') for n in nodes(result, 'issuing_authority')))
        self.assertTrue(any('BỘ HỒ SƠ' in n.get('text', '') for n in nodes(result, 'form_title')))
        from vietnam_legal_rag.ingestion.validation.extract import walk
        field = next((n, a) for n, a in walk([result['document']]) if n['type'] == 'form_field' and 'THÔNG TIN SẢN PHẨM' in n.get('text', ''))
        self.assertFalse(any(n['type'] == 'form_header' for n in field[1]))

    def test_attachment_cover_is_not_a_form_because_later_templates_have_blanks(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>(Kèm theo văn bản nguồn)</p>'
                             '<p><b>MẪU VĂN BẢN TỔNG HỢP</b><br><i>(Ban hành kèm theo văn bản nguồn)</i></p>'
                             '<p>Mẫu 1</p><p>Tên: ...</p><p>Địa chỉ: ...</p>'
                             '<p>Mẫu 2</p><p>Tên: ...</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'form')], ['1', '2'])

    def test_header_citation_and_rule_line_are_not_input_blanks(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>BỘ QUỐC PHÒNG</p>'
                             '<p>BỘ TƯ LỆNH<a href="#note">[7]</a>--------</p>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM<br>Độc lập - Tự do - Hạnh phúc<br>'
                             '_________________<br>..., ngày ... tháng ... năm ...</p>'
                             '<p><b>PHIẾU ĐỀ NGHỊ</b></p><p>Tên: ...</p>')
        self.assert_integrity(result)
        self.assertFalse(any('[7]' in (n.get('text') or '') for n in nodes(result, 'form_field')))
        self.assertTrue(any('[7]' in n.get('text', '') for n in nodes(result, 'issuing_authority')))
        # Layout/header splitting can retain a rule as a source separator;
        # standalone decorative rules may already be ignored by HTML flow.
        from vietnam_legal_rag.ingestion.refinement.forms import refine_form
        children = [{'type': kind, 'text': text, 'order': i, 'children': [],
                     'source_ref': {'tag': 'p', 'dom_order': i}}
                    for i, (kind, text) in enumerate([
                        ('paragraph', 'BỘ QUỐC PHÒNG'), ('separator', '_________________'),
                        ('form_title', 'PHIẾU ĐỀ NGHỊ'), ('paragraph', 'Tên: ...')])]
        form = {'type': 'form', 'title': None, 'children': children}
        refine_form(form)
        self.assertTrue(any(n['type'] == 'separator' for n in walk_content(form['children'])))

    def test_repeated_template_header_placeholder_keeps_title_region(self):
        fragment = ('<p>CƠ QUAN TỔ CHỨC..</p><p>ĐƠN VỊ TIẾP NHẬN…</p>'
                    '<p><b>BẢNG KÊ HỒ SƠ</b></p><p>Ngày: ...</p><p>Địa chỉ: ...</p>')
        prefix = '<p>Điều 1. Thi hành.</p><p>Nơi nhận:</p><p>- Lưu.</p><p>Mẫu 1</p><p>Tên: ...</p>'
        result = parse_forms(prefix + fragment)
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'form')), 2)
        self.assertEqual(nodes(result, 'form')[1]['title'], 'BẢNG KÊ HỒ SƠ')
        variant = parse_forms(prefix + '<p><b>2. Trường hợp bổ sung</b></p>' + fragment)
        self.assert_integrity(variant)
        self.assertEqual(len(nodes(variant, 'form')), 1)

    def test_institutional_header_placeholder_remains_a_source_input(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p><b>CƠ QUAN CHỦ QUẢN (3)</b></p>'
                             '<p>Tên: ...</p><p>Địa chỉ: ...</p>')
        self.assert_integrity(result)
        field = next(n for n in nodes(result, 'form_field') if n.get('text') == 'CƠ QUAN CHỦ QUẢN (3)')
        self.assertEqual(field['field_kind'], 'input')
        self.assertEqual(field['placeholder_refs'], ['3'])

    def test_repeated_uncoded_letterhead_delimits_a_direct_template(self):
        result = parse_forms('<p>Điều 1. Thi hành.</p><p>Nơi nhận:</p><p>- Lưu.</p>'
                             '<p>Mẫu 1</p><p>Tên: ...</p><p>Người lập (Ký, ghi rõ họ tên)</p>'
                             '<div style="display:grid;grid-template-columns:1fr 1fr">'
                             '<div>CƠ QUAN TỔ CHỨC..</div><div></div></div>'
                             '<p style="text-align:center"><b>BẢNG KÊ HỒ SƠ</b></p>'
                             '<p>Ngày: ...</p><p>Địa chỉ: ...</p>')
        self.assert_integrity(result)
        self.assertEqual([n.get('number') for n in nodes(result, 'form')], ['1', None])
        self.assertEqual(nodes(result, 'form')[1]['title'], 'BẢNG KÊ HỒ SƠ')
        self.assertEqual(result['form_validation']['split_form_candidates'], 0)
        self.assertFalse(any('BẢNG KÊ' in (n.get('text') or '') for n in walk_content(nodes(result, 'form')[0]['children'])))

    def test_centered_uppercase_cover_keeps_separately_styled_qualifier(self):
        result = parse_forms('<p>PHỤ LỤC IV</p><p>(Kèm theo văn bản nguồn)</p>'
                             '<p style="text-align:center"><b>THUYẾT MINH BÁO CÁO</b><br>'
                             '<i>(Cho kỳ báo cáo năm 20X2)</i></p>'
                             '<p><b>I. KHÁI QUÁT</b></p><p>........</p>'
                             '<p><b>II. NỘI DUNG</b></p><p>........</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'form')), 1)
        self.assertIn('(Cho kỳ báo cáo năm 20X2)', nodes(result, 'form')[0]['title'])

    def test_unknown_prompt_can_adjoin_source_confirmed_grid_inputs(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>hoặc chuyển vào tài khoản:</p>'
                             '<div style="display:grid;grid-template-columns:1fr 1fr">'
                             '<div>Đơn vị, CQ:</div><div>Mã, ký hiệu:</div></div>')
        self.assert_integrity(result)
        self.assertEqual([n['field_name'] for n in nodes(result, 'form_field')],
                         ['hoặc chuyển vào tài khoản', 'Đơn vị, CQ', 'Mã, ký hiệu'])
        self.assertTrue(all(n['value_text'] is None for n in nodes(result, 'form_field')))

    def test_qualified_annex_cover_requires_source_completion_evidence(self):
        header = '<table><tr><td>ĐƠN VỊ CHỦ QUẢN: ...</td><td></td></tr></table>'
        title = 'BÁO CÁO TỔNG HỢP (Cho kỳ báo cáo năm 20X2)'
        prefix = '<p>PHỤ LỤC IV</p><p>(Kèm theo văn bản nguồn)</p>'
        result = parse_forms(prefix + header + '<p><b>' + title + '</b></p>'
                             '<p><b>I. TỔNG QUAN</b></p><p>........</p>'
                             '<p><b>II. NỘI DUNG</b></p><p>1. Phương pháp:</p><p>........</p>')
        self.assert_integrity(result)
        forms = nodes(result, 'form')
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms[0]['title'], title)
        self.assertTrue(any(n['type'] == 'table' for n in walk_content(forms[0]['children'])))
        ordinary = parse_forms(prefix + '<p><b>' + title + '</b></p><p>Nội dung đã công bố.</p>')
        self.assert_integrity(ordinary)
        self.assertFalse(nodes(ordinary, 'form'))

    def test_source_grid_pairs_support_unfamiliar_form_prompts(self):
        grid = ('<div style="display:grid;grid-template-columns:1fr 1fr">'
                '<div>Đề nghị CQ (ĐV):</div><div>Tỉnh, TP:</div></div>')
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p>' + grid)
        self.assert_integrity(result)
        self.assertEqual([n['field_name'] for n in nodes(result, 'form_field')], ['Đề nghị CQ (ĐV)', 'Tỉnh, TP'])
        self.assertTrue(all(n['field_kind'] == 'unknown' and n['value_text'] is None for n in nodes(result, 'form_field')))
        outside = parse_forms(grid)
        self.assert_integrity(outside)
        self.assertFalse(nodes(outside, 'form_field'))

    def test_template_caption_note_in_next_header_row_keeps_full_code_and_table(self):
        result = parse_forms('<p>Điều 1. Thi hành.</p><p>KT. BỘ TRƯỞNG</p><p>THỨ TRƯỞNG</p>'
                             '<table><tr><td>CƠ QUAN CẤP</td><td>Mẫu số 03/BC, QT</td></tr>'
                             '<tr><td></td><td>(Ban hành kèm theo văn bản nguồn)</td></tr>'
                             '<tr><td colspan="2"><b>BẢNG ĐỐI CHIẾU</b></td></tr>'
                             '<tr><td>Tên: ...</td><td>Địa chỉ: ...</td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'form')], ['03/BC, QT'])
        self.assertEqual(nodes(result, 'table')[0]['grid_shape'], {'rows': 4, 'columns': 2})

    def test_post_closing_template_with_colon_inputs_is_not_a_signer(self):
        result = parse_forms('<p>Điều 1. Thi hành.</p><p>KT. BỘ TRƯỞNG</p><p>THỨ TRƯỞNG</p>'
                             '<p><b>CƠ QUAN TỔ CHỨC</b></p><p>………….</p>'
                             '<p style="text-align:center"><b>LỆNH THANH TOÁN</b></p>'
                             '<p>Cơ quan ra lệnh:</p><p>Mã số thuế:</p><p>Địa chỉ:</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'signer_name'))
        form = nodes(result, 'form')[0]
        self.assertEqual(form['title'], 'LỆNH THANH TOÁN')
        self.assertTrue(nodes(result, 'form_header'))
        self.assertTrue(any(n['text'] == 'CƠ QUAN TỔ CHỨC' for n in nodes(result, 'issuing_authority')))
        self.assertEqual(len(nodes(result, 'form_field')), 3)

    def test_table_template_caption_starts_new_form_without_invented_annex(self):
        header = ('<table><tr><td>CƠ QUAN CẤP</td><td><p>Mẫu số: Q2-07/BC</p>'
                  '<p>(Ban hành kèm theo văn bản nguồn)</p></td></tr></table>')
        result = parse_forms('<p>Điều 1. Thi hành.</p><p>Nơi nhận:</p><p>- Lưu.</p>'
                             '<p>Mẫu 1</p><p>Tên: ...</p>' + header +
                             '<p><b>PHIẾU XÁC NHẬN</b></p><p>Địa chỉ: ...</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'annex'))
        forms = nodes(result, 'form')
        self.assertEqual([n['number'] for n in forms], ['1', 'Q2-07/BC'])
        self.assertFalse(any(n['type'] == 'table' for n in walk_content(forms[0]['children'])))
        self.assertEqual(len([n for n in walk_content(forms[1]['children']) if n['type'] == 'table']), 1)
        self.assertEqual(forms[1]['title'], 'PHIẾU XÁC NHẬN')
        self.assertTrue(any(n.get('field_name') == 'Địa chỉ' for n in walk_content(forms[1]['children'])))

    def test_repeated_explicit_form_prompts_do_not_need_a_known_name(self):
        labels = ['Khả năng nghe / Listening', 'Khả năng diễn đạt / Expression',
                  'Các ngày thực hiện khảo sát / Date(s) of Survey(s)']
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p>' +
                             ''.join('<p>' + text + ':</p>' for text in labels))
        self.assert_integrity(result)
        fields = {n.get('field_name'): n for n in nodes(result, 'form_field')}
        self.assertEqual(set(fields), set(labels))
        self.assertTrue(all(n['field_kind'] == 'unknown' and n['value_text'] is None for n in fields.values()))
        isolated = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Chủ đề / Topic:</p>')
        self.assert_integrity(isolated)
        self.assertFalse(nodes(isolated, 'form_field'))

    def test_form_cell_prompt_after_literal_list_does_not_retype_list_leadin(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><table><tr><td>'
                             '<p>Ghi chú:</p><p>Remarks:</p><p>- Bản chính</p><p>- Bản sao</p>'
                             '<p>Thông tin khác:</p></td><td></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['field_name'] for n in nodes(result, 'form_field')], ['Thông tin khác'])
        self.assertTrue(any(n['text'] == 'Remarks:' for n in nodes(result, 'paragraph')))
        self.assertEqual(len(nodes(result, 'list_item')), 2)

    def test_parenthetical_colon_in_long_form_prompt_has_no_value(self):
        label = '(2) Nội dung khảo sát (ví dụ: thông tin của các bên liên quan) / Description of the survey and participating organizations'
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>' + label + ':</p>')
        self.assert_integrity(result)
        field = nodes(result, 'form_field')[0]
        self.assertEqual(field['field_name'], label)
        self.assertIsNone(field['value_text'])
        self.assertEqual(result['form_validation']['suspicious_value_text'], 0)

    def test_placeholder_reference_before_blank_excludes_following_prompt(self):
        text = 'Cơ quan tiếp nhận: (4)……............ chứng nhận:'
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>' + text + '</p>')
        self.assert_integrity(result)
        field = nodes(result, 'form_field')[0]
        self.assertEqual(field['text'], text)
        self.assertEqual(field['value_text'], '(4)……............')
        self.assertEqual(result['form_validation']['suspicious_value_text'], 0)

    def test_unknown_form_cell_colon_label_preserves_translation_and_grid(self):
        table = '<table><tr><td><p>Điểm phát sóng:</p><p><i>Transmitting station</i></p></td><td></td></tr></table>'
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p>' + table)
        self.assert_integrity(result)
        field = next(n for n in nodes(result, 'form_field') if n.get('field_name') == 'Điểm phát sóng')
        self.assertEqual(field['field_kind'], 'unknown')
        self.assertIsNone(field['value_text'])
        physical = nodes(result, 'table')[0]
        self.assertEqual(physical['grid_shape'], {'rows': 1, 'columns': 2})
        self.assertEqual(physical['cells'][0]['effective_text'], 'Điểm phát sóng: Transmitting station')
        self.assertTrue(any(n['text'] == 'Transmitting station' for n in nodes(result, 'paragraph')))
        outside = parse_forms(table)
        self.assert_integrity(outside)
        self.assertFalse(nodes(outside, 'form_field'))

    def test_explicit_bilingual_prompts_in_bounded_input_run_keep_null_values(self):
        labels = ['Khả năng nghe / Listening',
                  'Chứng từ bổ sung / Other records (reference no., type and issuing office)',
                  'Những ngày khảo sát / Date(s) of Survey(s)']
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Tên: ...</p>' +
                             ''.join('<p>' + label + ':</p>' for label in labels) + '<p>Địa chỉ: ...</p>')
        self.assert_integrity(result)
        fields = {n.get('field_name'): n for n in nodes(result, 'form_field')}
        for label in labels:
            self.assertIn(label, fields)
            self.assertEqual(fields[label]['field_kind'], 'unknown')
            self.assertIsNone(fields[label]['value_text'])
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)
        prose = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Phải sử dụng / Must use:</p>'
                            '<p>1. Bản chính.</p><p>2. Bản sao.</p>')
        self.assert_integrity(prose)
        self.assertFalse(any(n.get('field_kind') in {'input', 'input_label', 'unknown'}
                             for n in nodes(prose, 'form_field')))

    def test_global_signing_footer_closes_roman_source_outline(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p>'
                             '<p><b>I. THÔNG TIN CHUNG</b></p><p>1. Tên: ...</p>'
                             '<p><b>II. NỘI DUNG ĐĂNG KÝ</b></p><p>1. Địa chỉ: ...</p><p>2. Kiến nghị: ...</p>'
                             '<table><tr><td>Nơi nhận: - Như trên;</td><td>...(2)... (Chữ ký, dấu)</td></tr>'
                             '<tr><td></td><td>Nguyễn Văn An</td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'table')), 1)
        for item in nodes(result, 'list_item'):
            self.assertFalse(any(n['type'] == 'table' for n in walk_content(item['children'])))

    def test_signature_footer_variants_stay_outside_numbered_request(self):
        footers = [
            '<table><tr><td>Nơi nhận: - Như trên;</td><td>...(2)... (Chữ ký, dấu)</td></tr><tr><td></td><td>Nguyễn Văn An</td></tr></table>',
            '<table><tr><td></td><td>Người đại diện theo pháp luật (ký tên và đóng dấu)</td></tr></table>',
        ]
        for table in footers:
            with self.subTest(table=table):
                result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p>'
                                     '<p>1. Nội dung:</p><p>Tên: ...</p>'
                                     '<p>2. Đề xuất:</p><p>Ý kiến: ...</p>' + table)
                self.assert_integrity(result)
                form = nodes(result, 'form')[0]
                self.assertTrue(any(n['type'] == 'table' for n in form['children']))
                for field in nodes(result, 'form_field'):
                    self.assertFalse(any(n['type'] == 'table' for n in walk_content(field['children'])))

    def test_signature_column_in_input_records_is_not_a_global_footer(self):
        for tag, label in [('th', 'Họ tên'), ('td', 'Người đại diện')]:
            with self.subTest(tag=tag, label=label):
                result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>1. Danh sách:</p>'
                                     '<table><tr><' + tag + '>' + label + '</' + tag + '><' + tag + '>Chữ ký, dấu</' + tag + '></tr>'
                                     '<tr><td>1. ...</td><td></td></tr></table>'
                                     '<p>2. Nội dung khác:</p><p>Tên: ...</p>')
                self.assert_integrity(result)
                first = next(n for n in nodes(result, 'form_field') if n.get('number') == '1')
                self.assertTrue(any(n['type'] == 'table' for n in first['children']))

    def test_flat_recipient_footer_closes_numbered_form_components(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p>'
                             '<p>1. Thông tin đơn vị:</p><p>Tên: ...</p>'
                             '<p>2. Thông tin khác:</p><p>Địa chỉ: ...</p>'
                             '<p>Nơi nhận:-</p><p>- Cơ quan tiếp nhận;</p>'
                             '<p><b>NGƯỜI XÁC NHẬN</b></p><p>(Ký, ghi rõ họ tên)</p>')
        self.assert_integrity(result)
        self.assertTrue(nodes(result, 'recipients'))
        for field in nodes(result, 'form_field'):
            self.assertFalse(any(n['type'] == 'recipients' for n in walk_content(field['children'])))

    def test_post_closing_template_lookahead_cannot_cross_signature_or_annex(self):
        result = parse_forms('<p>Điều 1. Thi hành.</p><p>Nơi nhận:</p><p>- Lưu hồ sơ.</p>'
                             '<p><b>THÔNG TIN XÁC NHẬN</b></p><p>KT. BỘ TRƯỞNG</p>'
                             '<p>THỨ TRƯỞNG</p><p>Nguyễn Văn An</p>'
                             '<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Tên: ...</p><p>Địa chỉ: ...</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'annex')), 1)
        self.assertEqual(len(nodes(result, 'form')), 1)
        self.assertEqual(len(nodes(result, 'signer_name')), 1)
        self.assertFalse(any('THÔNG TIN XÁC NHẬN' in (n.get('title') or '') for n in nodes(result, 'form')))

    def test_actual_unnumbered_annex_can_follow_direct_attached_template(self):
        result = parse_forms('<p>Điều 1. Thi hành.</p><p>Nơi nhận:</p><p>- Lưu.</p>'
                             '<p>Mẫu 1</p><p>Tên: ...</p>'
                             '<p>PHỤ LỤC</p><p>Mẫu 2</p><p>Địa chỉ: ...</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'annex')), 1)
        self.assertEqual([n['number'] for n in nodes(result, 'form')], ['1', '2'])

    def test_enactment_can_name_normative_object_without_repeating_act_type(self):
        for subject in ('Danh mục thiết bị chuyên dùng', 'Quy chế phối hợp', 'Điều lệ tổ chức'):
            text = 'Thủ tướng Chính phủ ban hành ' + subject + '.'
            result = parse_forms('<p>QUYẾT ĐỊNH</p><p>Ban hành văn bản kèm theo</p>'
                                 '<p>Căn cứ Luật liên quan;</p><p>Theo đề nghị của Bộ trưởng;</p>'
                                 '<p>' + text + '</p><p>Điều 1. Phạm vi</p>')
            self.assert_integrity(result)
            self.assertEqual([n['text'] for n in nodes(result, 'enacting_formula')], [text])
            body = parse_forms('<p>Điều 1. Trách nhiệm</p><p>' + text + '</p>')
            self.assert_integrity(body)
            self.assertFalse(nodes(body, 'enacting_formula'))

    def test_numbered_component_uses_literal_alpha_input_before_field_typing(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p>'
                             '<p>1. Khu vực tiếp nhận</p>'
                             '<p>a) Vị trí: .... b) Diện tích: (liệt kê cụ thể)</p>'
                             '<p>2. Trang thiết bị:</p><p>Tên: ...</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        parent = next(n for n in nodes(result, 'form_field') if n.get('number') == '1')
        self.assertEqual(parent['field_kind'], 'composite')
        self.assertTrue(any(n['type'] == 'form_subfield' for n in parent['children']))

    def test_symbol_prefixed_nested_cell_prompt_is_not_a_value(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p>'
                             '<table><tr><td>Người đại diện mới: + Họ và tên:</td><td></td></tr>'
                             '<tr><td>Địa chỉ:</td><td></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['suspicious_value_text'], 0)
        parent = next(n for n in nodes(result, 'form_field') if n.get('field_name') == 'Người đại diện mới')
        self.assertIsNone(parent['value_text'])
        self.assertEqual(parent['field_kind'], 'composite')
        sub = next(n for n in parent['children'] if n['type'] == 'form_subfield')
        self.assertEqual(sub['field_name'], 'Họ và tên')
        self.assertEqual(sub['label'], '+')
        self.assertIsNone(sub['value_text'])

    def test_reason_prompt_before_declaration_keeps_empty_input_label(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Lý do yêu cầu điều chỉnh:</p>'
                             '<p>Chúng tôi cam kết chịu trách nhiệm về nội dung kê khai.</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)
        field = next(n for n in nodes(result, 'form_field') if n.get('field_name') == 'Lý do yêu cầu điều chỉnh')
        self.assertEqual(field['field_kind'], 'unknown')
        self.assertIsNone(field['value_text'])
        self.assertFalse(field['children'])

    def test_post_closing_numbered_templates_do_not_require_invented_annex(self):
        result = parse_forms('<p>Điều 1. Thi hành.</p><p>Nơi nhận:</p><p>- Lưu hồ sơ.</p>'
                             '<p>Mẫu số 04. Nội dung đăng ký</p>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p>'
                             '<p>Độc lập - Tự do - Hạnh phúc</p><p>1. Họ tên: ...</p>'
                             '<p>Mẫu số 05. Nội dung xác nhận</p><p>1. Địa chỉ: ...</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'form')], ['04', '05'])
        self.assertFalse(nodes(result, 'annex'))
        self.assertEqual(len(nodes(result, 'form_field')), 2)
        self.assertFalse(any('Mẫu số' in n.get('text', '') for n in nodes(result, 'recipient')))
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_post_closing_completion_cover_starts_unnumbered_form(self):
        result = parse_forms('<p>Điều 1. Thi hành.</p><p>Nơi nhận:</p><p>- Lưu hồ sơ.</p>'
                             '<p><b>THÔNG TIN ĐĂNG KÝ</b></p><p>Tên: ...</p><p>Địa chỉ: ...</p>'
                             '<p>I. NỘI DUNG</p><p>1. Hồ sơ: ...</p>'
                             '<p>Mẫu số 02. Hồ sơ khác</p><p>Tên: ...</p>')
        self.assert_integrity(result)
        self.assertEqual([n.get('number') for n in nodes(result, 'form')], [None, '02'])
        self.assertFalse(nodes(result, 'annex'))
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_post_closing_prose_form_citation_is_not_a_template(self):
        result = parse_forms('<p>Điều 1. Thi hành.</p><p>Nơi nhận:</p>'
                             '<p>Mẫu số 04 của hồ sơ được lưu tại cơ quan.</p>'
                             '<p><b>THÔNG TIN TIẾP NHẬN</b></p><p>Nội dung thông báo kết thúc.</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'form'))

    def test_missing_opening_replacement_quote_keeps_following_amendment_parent(self):
        for closing in ('”', '"'):
            with self.subTest(closing=closing):
                replacement = '7. Nội dung thay thế.' + closing + ';'
                result = parse_forms('<p>Điều 1. Sửa đổi</p>'
                                     '<p class="prov-clause">2. Sửa đổi các khoản như sau:</p>'
                                     '<p>d) Sửa đổi, bổ sung khoản 7 như sau:</p><p>' + replacement + '</p>'
                                     '<p>đ) Sửa đổi khoản 9 như sau:</p><p>“9. Nội dung khác.”.</p>'
                                     '<p class="prov-clause">3. Thi hành.</p>')
                self.assert_integrity(result)
                clause = next(n for n in nodes(result, 'clause') if n['number'] == '2')
                self.assertEqual([n['number'] for n in clause['children'] if n['type'] == 'point'], ['d', 'đ'])
                self.assertEqual(result['hierarchy_validation']['unresolved']['orphan_nodes'], 0)
                point = next(n for n in clause['children'] if n.get('number') == 'd')
                item = next(n for n in walk_content(point['children']) if n['type'] == 'list_item')
                self.assertEqual(item['number'], '7')
                self.assertEqual(item['label'] + ' ' + item['text'], replacement)
                warning = next(i for i in result['issues'] if i['code'] == 'incomplete_source_quotation')
                self.assertEqual(warning['severity'], 'warning')
                self.assertIn('lead_source_ref', warning['details'])

    def test_missing_opening_quote_scope_requires_matching_unit_and_terminal_mark(self):
        for lead, body in [('Sửa đổi khoản 7 như sau:', '8. Nội dung.”;'),
                           ('Sửa đổi Điều 7 như sau:', '7. Nội dung.”;'),
                           ('Sửa đổi khoản 7 như sau:', '7. Nội dung.'),
                           ('Nội dung khoản 7 như sau:', '7. Nội dung.”;')]:
            with self.subTest(lead=lead, body=body):
                result = parse_forms('<p>Điều 1. Nội dung</p><p>2. Trường hợp:</p>'
                                     '<p>d) ' + lead + '</p><p>' + body + '</p>')
                self.assert_integrity(result)
                self.assertFalse(any(n.get('evidence') == 'source_replacement_missing_opening_quotation'
                                     for n in nodes(result, 'layout_block')))
                self.assertFalse(any(i['code'] == 'incomplete_source_quotation' for i in result['issues']))

    def test_closed_note_does_not_reclassify_following_form_counter_peers(self):
        table = '<table><tr><th>Thông tin</th><th>Ngày</th></tr><tr><td></td><td></td></tr></table>'
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Ghi chú:</p>'
                             '<p>- Hướng dẫn thứ nhất.</p><p>- Hướng dẫn thứ hai.</p>'
                             '<p>9. Chứng nhận chuyên môn</p><p>9.1. Trong nước</p>' + table +
                             '<p>9.2. Chứng nhận khác (liệt kê cụ thể nơi cấp)</p>'
                             '<p>10. Quá trình làm việc</p>' + table)
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['inconsistent_footnote_sequences'], 0)
        self.assertTrue(nodes(result, 'note')[0]['children'])

    def test_decimal_instruction_peer_does_not_own_next_numbered_table(self):
        table = '<table><tr><th>Thông tin</th><th>Ngày</th></tr><tr><td></td><td></td></tr></table>'
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>8. Thông tin:</p>'
                             '<p>9. Chứng nhận chuyên môn</p><p>9.1. Trong nước</p>' + table +
                             '<p>9.2. Chứng nhận khác (liệt kê cụ thể nơi cấp)</p>'
                             '<p>10. Quá trình làm việc</p>' + table)
        self.assert_integrity(result)
        parent = next(n for n in nodes(result, 'form_field') if n.get('number') == '9')
        subs = [n for n in parent['children'] if n['type'] == 'form_subfield']
        self.assertEqual([n['number'] for n in subs], ['9.1', '9.2'])
        self.assertEqual(subs[1]['field_kind'], 'instruction')
        self.assertFalse(any(n['type'] == 'table' for n in walk_content(subs[1]['children'])))
        self.assertFalse(any(n.get('number') == '10' for n in walk_content(parent['children'])))

    def test_compound_policy_heading_does_not_start_application_form(self):
        result = parse_forms('<p>PHỤ LỤC</p><p><b>ĐƠN GIẢN HÓA CÁC QUY ĐỊNH</b></p>'
                             '<p>1. Điều kiện thực hiện</p><p>a) Nội dung thứ nhất.</p>'
                             '<p>b) Nội dung thứ hai.</p><p>2. Điều kiện tiếp theo.</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'form'))

    def test_long_completion_blank_after_comma_keeps_input_role(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>1. Kê khai thông tin.</p>'
                             '<p>2. Nếu được chấp thuận,.......................sẽ thực hiện đúng quy định.</p>')
        self.assert_integrity(result)
        field = next(n for n in nodes(result, 'form_field') if n.get('number') == '2')
        self.assertEqual(field['field_kind'], 'input')
        self.assertIn('.......................', field['text'])

    def test_emphasized_period_topics_keep_actual_local_inputs(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p>'
                             '<p><b>1. Nội dung hồ sơ.</b></p><p>Tên: ...</p>'
                             '<p><b>2. Trách nhiệm tổng hợp.</b></p><p>Đơn vị đã rà soát……..trường hợp.</p>')
        self.assert_integrity(result)
        fields = [n for n in nodes(result, 'form_field') if n.get('number') in {'1', '2'}]
        self.assertEqual([n['number'] for n in fields], ['1', '2'])
        self.assertTrue(all(n['field_kind'] == 'composite' for n in fields))
        self.assertTrue(all(n['children'] for n in fields))

    def test_preclassified_decimal_parent_owns_fillable_tables(self):
        table = '<table><tr><th>Thông tin</th><th>Ngày</th></tr><tr><td></td><td></td></tr></table>'
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>8. Thông tin:</p>'
                             '<p>9. Chứng nhận chuyên môn</p><p>9.1. Trong nước</p>' + table +
                             '<p>9.2. Nước ngoài</p>' + table)
        self.assert_integrity(result)
        parent = next(n for n in nodes(result, 'form_field') if n.get('number') == '9')
        subs = [n for n in parent['children'] if n['type'] == 'form_subfield']
        self.assertEqual([n['number'] for n in subs], ['9.1', '9.2'])
        self.assertTrue(all(any(n['type'] == 'table' for n in s['children']) for s in subs))

    def test_numbered_variant_heading_before_letterhead_keeps_one_form(self):
        header = '<p>TÊN ĐƠN VỊ</p><p>Số: ...</p><p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p>'
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p>'
                             '<p><b>1. Trường hợp đăng ký lần đầu</b></p>' + header +
                             '<p><b>ĐƠN ĐĂNG KÝ</b></p><p>Tên: ...</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'form')), 1)
        variant = next(n for n in nodes(result, 'heading') if n.get('text', '').startswith('1. Trường hợp'))
        self.assertEqual(variant['evidence'], 'source_numbered_form_heading_before_letterhead')
        self.assertTrue(nodes(result, 'form_header'))

    def test_report_outline_does_not_absorb_recipient_signature_table(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Báo cáo hoạt động</p>'
                             '<p>A. Báo cáo của đơn vị thứ nhất:</p><p>1. Sản lượng.</p>'
                             '<p>B. Báo cáo của đơn vị thứ hai:</p><p>1. Kiến nghị.</p>'
                             '<table><tr><td><p>Nơi nhận:</p><p>- Như trên;</p></td>'
                             '<td><p>LÃNH ĐẠO ĐƠN VỊ</p><p>(Ký tên, đóng dấu)</p></td></tr></table>')
        self.assert_integrity(result)
        from vietnam_legal_rag.ingestion.validation.extract import walk
        table, ancestors = next((n, a) for n, a in walk([result['document']]) if n['type'] == 'table')
        self.assertFalse(any(a['type'] in {'list_item', 'form_field', 'form_subfield'} for a in ancestors))
        self.assertFalse(any(n['type'] == 'form_field' and n.get('number') == '1'
                             for n in walk_content([result['document']])))

    def test_input_table_with_only_recipient_wording_is_not_global_footer(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>1. Phương án giao nhận:</p>'
                             '<p>- Danh sách giao:</p><p>- Danh sách nhận:</p>'
                             '<table><tr><td>Nơi nhận:</td><td></td></tr></table>'
                             '<p>- Nội dung khác:</p><p>2. Kiến nghị:</p>')
        self.assert_integrity(result)
        owner = next(n for n in nodes(result, 'form_field') if n.get('number') == '1')
        self.assertTrue(any(n['type'] == 'table' for n in walk_content(owner['children'])))

    def test_mixed_case_alpha_form_topics_own_restarted_numeric_lists(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Báo cáo hoạt động</p>'
                             '<p>A. Nội dung của đơn vị thứ nhất:</p>'
                             '<p>1. Sản lượng trong năm.</p><p>2. Chi phí trong năm.</p>'
                             '<p>B. Nội dung của đơn vị thứ hai:</p>'
                             '<p>1. Sản lượng trong năm.</p><p>2. Kiến nghị.</p>')
        self.assert_integrity(result)
        from vietnam_legal_rag.ingestion.validation.extract import walk
        roots = [n for n in nodes(result, 'list_item') if n.get('number') in {'A', 'B'}]
        self.assertEqual([n['number'] for n in roots], ['A', 'B'])
        for root in roots:
            self.assertEqual([n['number'] for n in walk_content(root['children']) if n['type'] == 'list_item'], ['1', '2'])

    def test_alpha_form_topics_without_numeric_restarts_keep_flat_list(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Báo cáo hoạt động</p>'
                             '<p>A. Nội dung thứ nhất.</p><p>B. Nội dung thứ hai.</p>')
        self.assert_integrity(result)
        self.assertFalse(any(n.get('evidence') == 'source_consecutive_alpha_form_outline'
                             for n in walk_content([result['document']])))

    def test_form_colon_leadin_before_literal_list_is_not_missing_input(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Báo cáo hoạt động</p>'
                             '<p>Danh mục tổng hợp:</p><p>1. Sản lượng.</p><p>2. Chi phí.</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)
        from vietnam_legal_rag.ingestion.refinement.schema import form_label_audit
        item = next(n for n in form_label_audit(result['document']) if n['text'] == 'Danh mục tổng hợp:')
        self.assertEqual(item['reason'], 'source_leadin_before_literal_list')
        self.assertTrue(item['justified'])

    def test_displayed_template_caption_before_title_is_not_unexplained_input(self):
        result = parse_forms('<p>PHỤ LỤC</p><table><tr><td>'
                             '<p><b>Phiếu:</b></p><p><b>GIẤY BIÊN NHẬN</b></p>'
                             '<p>Số: ...</p></td><td></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)
        from vietnam_legal_rag.ingestion.refinement.schema import form_label_audit
        caption = next(n for n in form_label_audit(result['document']) if n['text'] == 'Phiếu:')
        self.assertTrue(caption['justified'])
        self.assertEqual(caption['reason'], 'source_display_caption_before_title')

    def test_template_caption_label_before_blank_is_not_justified_as_display(self):
        result = parse_forms('<p>PHỤ LỤC</p><table><tr><td>'
                             '<p><b>Phiếu:</b></p><p>........</p></td><td></td></tr></table>')
        self.assert_integrity(result)
        from vietnam_legal_rag.ingestion.refinement.schema import form_label_audit
        self.assertFalse(any(n['reason'] == 'source_display_caption_before_title'
                             for n in form_label_audit(result['document'])))

    def test_centered_inline_addressee_is_not_a_template_title(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p>'
                             '<p style="text-align: center;">Kính gửi: Cơ quan quản lý.</p>'
                             '<p>Báo cáo kết quả thực hiện như sau:</p><p>1. Thông tin:</p>')
        self.assert_integrity(result)
        self.assertFalse(any(n.get('text', '').startswith('Kính gửi:') for n in nodes(result, 'form_title')))
        self.assertEqual(nodes(result, 'recipients')[0]['text'], 'Kính gửi: Cơ quan quản lý.')
        self.assertIsNone(nodes(result, 'form')[0]['title'])

    def test_inline_addressee_placeholder_keeps_input_evidence(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Kính gửi: ........</p>'
                             '<p>Nội dung báo cáo.</p>')
        self.assert_integrity(result)
        recipients = nodes(result, 'recipients')[0]
        self.assertEqual(recipients['children'][0]['field_kind'], 'input')
        self.assertEqual(recipients['children'][0]['text'], 'Kính gửi: ........')

    def test_inline_request_noun_does_not_invent_completion_instruction(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Báo cáo hoạt động</p>'
                             '<p>1. Hồ sơ: đề nghị được lập trong năm trước.</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'form_field'))

    def test_dash_topics_do_not_bridge_a_populated_data_table(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Báo cáo hoạt động</p>'
                             '<p>- Khách hàng:</p><p>- Hợp đồng:</p>'
                             '<table><tr><th>Tên</th><th>Trị giá</th></tr>'
                             '<tr><td>A</td><td>5.000</td></tr></table><p>- Kết quả khác:</p>')
        self.assert_integrity(result)
        self.assertEqual(nodes(result, 'table')[0]['table_kind'], 'data')
        self.assertFalse(any(n['type'] == 'table' for item in nodes(result, 'list_item')
                             for n in walk_content(item['children'])))

    def test_numbered_form_inline_completion_directive(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Báo cáo hoạt động</p>'
                             '<p>1. Mục tiêu:</p>'
                             '<p>2. Kết quả thực hiện: đề nghị đánh giá so với mục tiêu đã đề ra.</p>'
                             '<p>3. Kiến nghị:</p>')
        self.assert_integrity(result)
        field = next(n for n in nodes(result, 'form_field') if n.get('number') == '2')
        self.assertEqual(field['field_kind'], 'instruction')
        self.assertEqual(field['text'], 'Kết quả thực hiện: đề nghị đánh giá so với mục tiêu đã đề ra.')

    def test_dash_form_topics_keep_fillable_table_and_later_peer(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Báo cáo hoạt động</p>'
                             '<p>1. Kết quả giao dịch:</p><p>- Khách hàng:</p><p>- Hợp đồng:</p>'
                             '<table><tr><th>Tên</th><th>Trị giá</th></tr>'
                             '<tr><td></td><td></td></tr></table><p>- Kết quả khác:</p>'
                             '<p>2. Đánh giá:</p>')
        self.assert_integrity(result)
        items = nodes(result, 'list_item')
        self.assertEqual([n['text'] for n in items], ['Khách hàng:', 'Hợp đồng:', 'Kết quả khác:'])
        self.assertEqual([n['type'] for n in items[1]['children']], ['table'])
        owner = next(n for n in nodes(result, 'form_field') if n.get('number') == '1')
        self.assertEqual(owner['field_kind'], 'composite')
        self.assertTrue(all(item in list(walk_content(owner['children'])) for item in items))
        self.assertFalse(any(i['code'] == 'form_label_unresolved' for i in result['issues']))

    def test_procedure_caption_closes_decimal_list_in_body_outline(self):
        result = parse_forms('<p>HƯỚNG DẪN</p><p><b>I. NỘI DUNG</b></p>'
                             '<p>1. Chuẩn bị</p><p>1.1. Thiết bị</p><p>Thiết bị sử dụng.</p>'
                             '<p style="text-align: center;">QUY TRÌNH SỐ 8</p>'
                             '<p style="text-align: center;">TÊN QUY TRÌNH</p>'
                             '<p><b>II. THỰC HIỆN</b></p><p>1. Thao tác</p>')
        self.assert_integrity(result)
        from vietnam_legal_rag.ingestion.validation.extract import walk
        for node, ancestors in walk([result['document']]):
            if node.get('text') in {'QUY TRÌNH SỐ 8', 'TÊN QUY TRÌNH'}:
                self.assertFalse(any(a.get('number') in {'1', '1.1'} for a in ancestors))

    def test_report_prose_ellipsis_is_not_an_input_blank(self):
        text = 'Mô tả các nội dung quản lý, đầu tư, mua sắm, ... Nêu số văn bản và nội dung thực hiện.'
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Báo cáo hoạt động</p>'
                             '<p>1. Nội dung hoạt động</p><p>' + text + '</p>'
                             '<p>2. Thông tin liên hệ</p><p>Tên: ...</p>')
        self.assert_integrity(result)
        self.assertFalse(any(n.get('text') == text for n in nodes(result, 'form_field')))
        self.assertTrue(any(n.get('text') == text for n in nodes(result, 'paragraph')))
        self.assertTrue(any(n.get('text') == 'Tên: ...' for n in nodes(result, 'form_field')))

    def test_numbered_caption_closes_report_component_before_input_table(self):
        table = '<table><tr><th>Chỉ tiêu</th><th>Kết quả</th></tr><tr><td>1</td><td></td></tr></table>'
        for caption in ['PHỤ BẢNG 07', 'BẢNG SỐ 8: TỔNG HỢP HOẠT ĐỘNG']:
            with self.subTest(caption=caption):
                result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Báo cáo hoạt động</p>'
                                     '<p>I. NỘI DUNG</p><p>1. Thông tin đơn vị</p><p>Tên: ...</p>'
                                     '<p>2. Chính sách hoạt động</p><p>Mô tả chính sách hoạt động.</p>'
                                     '<p style="text-align: center;">' + caption + '</p>' + table +
                                     '<p>II. KIẾN NGHỊ</p><p>1. Nội dung kiến nghị</p>')
                self.assert_integrity(result)
                from vietnam_legal_rag.ingestion.validation.extract import walk
                for node, ancestors in walk([result['document']]):
                    if node.get('text') == caption or node['type'] == 'table':
                        self.assertFalse(any(a.get('number') == '2' and
                                             a['type'] in {'form_field', 'form_subfield', 'list_item'}
                                             for a in ancestors))
                self.assertFalse(any(n.get('number') == '2' for n in nodes(result, 'form_field')))

    def test_centered_prose_number_does_not_close_input_component(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Báo cáo hoạt động</p>'
                             '<p>1. Thông tin đơn vị</p><p>Tên: ...</p>'
                             '<p>2. Tình hình hoạt động</p>'
                             '<p style="text-align: center;">Kết quả của 7 đơn vị trong kỳ.</p>'
                             '<p>Số lượng: ...</p>')
        self.assert_integrity(result)
        owner = next(n for n in nodes(result, 'form_field') if n.get('number') == '2')
        self.assertTrue(any(n.get('text') == 'Số lượng: ...' for n in walk_content(owner['children'])))

    def test_global_declaration_with_blanks_closes_decimal_component(self):
        for declaration in ['Doanh nghiệp xin chịu trách nhiệm về nội dung kê khai theo Thông tư số …/2025/TT.',
                            'Chúng tôi cam kết thực hiện theo văn bản số ... ngày ... tháng ... năm ...']:
            with self.subTest(declaration=declaration):
                result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Đơn đăng ký</p>'
                                     '<p>1. Mạng lưới hoạt động</p>'
                                     '<p>1.1. Đại lý thứ nhất</p><p>Tên đại lý: ...</p>'
                                     '<p>1.2. Đại lý thứ hai</p><p>Tên đại lý: ...</p>'
                                     '<p>' + declaration + '</p>')
                self.assert_integrity(result)
                from vietnam_legal_rag.ingestion.validation.extract import walk
                node, ancestors = next((n, a) for n, a in walk([result['document']])
                                       if n.get('text') == declaration)
                self.assertEqual(node['field_kind'], 'input')
                self.assertEqual(node['field_evidence'], 'source_placeholder_or_input_label')
                self.assertFalse(any(a['type'] in {'form_field', 'form_subfield'} for a in ancestors))
                owner = next(n for n in nodes(result, 'form_field') if n.get('number') == '1')
                self.assertEqual([n.get('number') for n in owner['children']], ['1.1', '1.2'])

    def test_ordinary_responsibility_mention_stays_in_decimal_component(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Đơn đăng ký</p>'
                             '<p>1. Mạng lưới hoạt động</p>'
                             '<p>1.1. Đại lý thứ nhất</p><p>Tên đại lý: ...</p>'
                             '<p>1.2. Đại lý thứ hai</p><p>Tên đại lý: ...</p>'
                             '<p>Ghi cơ quan chịu trách nhiệm: ...</p>')
        self.assert_integrity(result)
        subfield = next(n for n in nodes(result, 'form_subfield') if n.get('number') == '1.2')
        self.assertTrue(any(n.get('text') == 'Ghi cơ quan chịu trách nhiệm: ...'
                            for n in subfield['children']))

    def test_alphabetic_receipt_components_do_not_own_trailing_total(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Giấy nhận tiền</p>'
                             '<p>Thay mặt người nhận:</p><p>a) Khoản thứ nhất: ... đồng.</p>'
                             '<p>Quỹ bảo đảm: ... đồng.</p><p>b) Khoản thứ hai: 4.500.000 đồng.</p>'
                             '<p>Tổng số tiền: ... đồng.</p>')
        self.assert_integrity(result)
        total = next(n for n in nodes(result, 'form_field') if n.get('text', '').startswith('Tổng số tiền'))
        self.assertFalse(any(total is child for subfield in nodes(result, 'form_subfield')
                             for child in walk_content(subfield['children'])))
        fixed = next(n for n in nodes(result, 'form_subfield') if n.get('label') == 'b)')
        self.assertEqual(fixed['field_kind'], 'display')
        self.assertEqual(fixed['text'], 'Khoản thứ hai: 4.500.000 đồng.')
        self.assertEqual(fixed['value_text'], '4.500.000 đồng.')
        self.assertEqual(fixed['field_evidence'], 'source_literal_currency_value')

    def test_alphabetic_requirements_keep_numbered_owner_across_instruction(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Thông báo thủ tục</p>'
                             '<p>1. Người đăng ký thực hiện:</p><p>a) Nộp phiếu đăng ký.</p>'
                             '<p>Trường hợp ưu tiên phải nộp thêm tài liệu.</p>'
                             '<p>b) Tham dự buổi xác nhận.</p><p>c) Đăng ký xem tài liệu.</p>'
                             '<p>2. Thông tin liên hệ:</p>')
        self.assert_integrity(result)
        owner = next(n for n in nodes(result, 'form_field') if n.get('number') == '1')
        children = [n for n in owner['children'] if n['type'] == 'form_subfield']
        self.assertEqual([n['label'] for n in children], ['a)', 'b)', 'c)'])
        self.assertTrue(any(n.get('text') == 'Trường hợp ưu tiên phải nộp thêm tài liệu.'
                            for n in children[0]['children']))

    def test_written_amount_input_does_not_own_later_alphabetic_fields(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Quyết định chế độ</p>'
                             '<p><b>Điều 1. Mức trợ cấp</b></p><p>a) Trợ cấp một lần: ... đồng.</p>'
                             '<p>Bằng chữ (....................)</p><p>b) Trợ cấp hàng tháng: ... đồng.</p>'
                             '<p>c) Điều chỉnh trợ cấp:</p><p><b>Điều 2. Thi hành</b></p>')
        self.assert_integrity(result)
        amount = next(n for n in nodes(result, 'form_field') if n.get('text', '').startswith('Bằng chữ'))
        self.assertFalse(any((n.get('text') or '').startswith(('Trợ cấp hàng tháng', 'Điều chỉnh trợ cấp'))
                             for n in walk_content(amount['children'])))

    def test_standalone_alphabetic_table_topics_keep_list_scope(self):
        table = '<table><tr><th>STT</th><th>Dữ liệu</th></tr><tr><td>1</td><td></td></tr></table>'
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Báo cáo hoạt động</p>'
                             '<p>a) Kế hoạch hoạt động:</p>' + table +
                             '<p>b) Kết quả hoạt động:</p>' + table)
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'form_field'))
        self.assertEqual([n['label'] for n in nodes(result, 'list_item')], ['a)', 'b)'])
        self.assertEqual(len(nodes(result, 'table')), 2)

    def test_numbered_document_list_does_not_own_following_input_request(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Giấy chuyển hồ sơ</p>'
                             '<p>1. Bản khai cá nhân.</p><p>2. Quyết định hưởng trợ cấp.</p>'
                             '<p>Đề nghị cơ quan ................ tiếp nhận hồ sơ.</p>')
        self.assert_integrity(result)
        self.assertFalse(any(n.get('number') in {'1', '2'} for n in nodes(result, 'form_field')))
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['1', '2'])

    def test_preclassified_alphabetic_table_prompt_keeps_numbered_owner(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>1. Tình hình hoạt động:</p>'
                             '<p>a. Thông tin:</p><table><tr><th>STT</th><th>Dữ liệu</th></tr>'
                             '<tr><td>1</td><td></td></tr></table>'
                             '<p>b. Tình hình thực hiện nội dung hoạt động.</p><p>2. Kiến nghị:</p>')
        self.assert_integrity(result)
        owner = next(n for n in nodes(result, 'form_field') if n.get('number') == '1')
        subfields = [n for n in nodes(result, 'form_subfield')]
        self.assertEqual([n['label'] for n in subfields], ['a.', 'b.'])
        self.assertIn(subfields[0], owner['children'])
        self.assertEqual(subfields[0]['field_kind'], 'composite')
        self.assertEqual(subfields[0]['field_evidence'], 'source_form_prompt_before_fillable_table')
        self.assertEqual(sum(n['type'] == 'table' for n in walk_content(subfields[0]['children'])), 1)

    def test_populated_annex_report_table_retains_factual_axes(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Biểu số 1</p><p>Phân bổ kinh phí</p>'
                             '<table><tr><th scope="col">STT</th><th scope="col">Đơn vị</th>'
                             '<th scope="col">Tổng số</th><th scope="col">Chi đầu tư</th></tr>'
                             '<tr><td>1</td><td>Cơ quan A</td><td>45.000</td><td>40.000</td></tr>'
                             '<tr><td>2</td><td>Cơ quan B</td><td>5.000</td><td></td></tr></table>')
        self.assert_integrity(result)
        table = nodes(result, 'table')[0]
        self.assertEqual(table['table_kind'], 'data')
        value = next(c for c in table['cells'] if c['row'] == 1 and c['column'] == 2)
        self.assertEqual(value['effective_text'], '45.000')
        self.assertTrue(value['header_refs']['column'])

    def test_empty_annex_report_table_keeps_form_context(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Biểu số 1</p><p>Báo cáo số liệu</p>'
                             '<table><tr><th>STT</th><th>Đơn vị</th><th>Số lượng</th></tr>'
                             '<tr><td>1</td><td></td><td></td></tr>'
                             '<tr><td>2</td><td></td><td></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual(nodes(result, 'table')[0]['table_kind'], 'annex_form')

    def test_explicit_assembly_enactment_actors_are_scoped_to_opening(self):
        for actor, kind in [('Quốc hội', 'Luật'), ('Hội đồng nhân dân thành phố', 'Nghị quyết')]:
            text = actor + ' ban hành ' + kind + ' về tổ chức.'
            with self.subTest(actor=actor):
                result = parse_forms('<p>' + kind.upper() + '</p><p>Về tổ chức</p>'
                                     '<p>Căn cứ văn bản;</p><p>' + text + '</p><p>Điều 1. Phạm vi</p>')
                self.assert_integrity(result)
                self.assertEqual([n['text'] for n in nodes(result, 'enacting_formula')], [text])
                body = parse_forms('<p>Điều 1. Trách nhiệm</p><p>' + text + '</p>')
                self.assert_integrity(body)
                self.assertFalse(nodes(body, 'enacting_formula'))

    def test_prime_minister_enacting_statement_keeps_source_formula_role(self):
        text = 'Thủ tướng Chính phủ ban hành Quyết định về danh mục.'
        result = parse_forms('<p>QUYẾT ĐỊNH</p><p>Về danh mục</p>'
                             '<p>Căn cứ Luật liên quan;</p><p>Theo đề nghị của Bộ trưởng;</p>'
                             '<p>' + text + '</p><p>Điều 1. Phạm vi</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'enacting_formula')], [text])

    def test_prime_minister_statement_inside_body_is_literal_body_text(self):
        text = 'Thủ tướng Chính phủ ban hành Quyết định về danh mục.'
        result = parse_forms('<p>Điều 1. Trách nhiệm</p><p>' + text + '</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'enacting_formula'))
        self.assertTrue(any(n.get('text') == text for n in nodes(result, 'paragraph')))

    def test_form_counter_peers_include_display_and_preclassified_fields(self):
        table = ('<table><tr><th>TT</th><th>Dữ liệu</th></tr>'
                 '<tr><td>1</td><td></td></tr></table>')
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>1. Số liệu</p>'
                             '<p>a) Thông tin</p>' + table +
                             '<p>2. Tình hình thực hiện yêu cầu</p>'
                             '<p>a) Kế hoạch:</p><p>b) Kết quả:</p>'
                             '<p>3. Các sự cố.</p><p>4. Các khó khăn trong việc thực hiện.</p>'
                             '<p>5. Kiến nghị:</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        self.assertEqual([n['number'] for n in nodes(result, 'form_field') if n.get('number')],
                         ['1', '2', '5'])
        self.assertEqual([n['number'] for n in nodes(result, 'list_item') if n.get('number')], ['3', '4'])

    def test_display_topics_do_not_cancel_preceding_form_input_components(self):
        table = ('<table><tr><th>TT</th><th>Dữ liệu</th></tr>'
                 '<tr><td>1</td><td></td></tr></table>')
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>1. Số liệu</p>' + table +
                             '<p>2. Tình hình thực hiện yêu cầu</p>'
                             '<p>a) Kế hoạch:</p><p>b) Kết quả:</p>'
                             '<p>3. Các sự cố.</p><p>4. Các khó khăn trong việc thực hiện.</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        parents = [n for n in nodes(result, 'form_field') if n.get('number')]
        self.assertEqual([n['number'] for n in parents], ['1', '2'])
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['3', '4'])

    def test_data_table_overlong_ellipsis_after_punctuation_is_literal_prose(self):
        for text in ('Các loại,....', 'Các loại, .....', 'Các loại;....'):
            with self.subTest(text=text):
                result = parse_forms('<p>PHỤ LỤC</p><table><tr><th>Nhóm</th>'
                                     '<th>Nội dung</th><th>Ghi chú</th></tr>'
                                     '<tr><td>A</td><td>' + text + '</td><td></td></tr></table>')
                self.assert_integrity(result)
                self.assertEqual(nodes(result, 'table')[0]['table_kind'], 'data')
                self.assertEqual(nodes(result, 'table')[0]['cells'][4]['effective_text'], text)

    def test_fillable_table_does_not_turn_form_prose_into_a_prompt(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Đã xem xét như sau:</p>'
                             '<table><tr><th>Nội dung</th><th>Kết quả</th></tr>'
                             '<tr><td>Kiểm tra</td><td></td></tr></table>')
        self.assert_integrity(result)
        self.assertTrue(any(n.get('text') == 'Đã xem xét như sau:'
                            for n in nodes(result, 'paragraph')))
        self.assertFalse(any(n.get('text') == 'Đã xem xét như sau:'
                             for n in nodes(result, 'form_field')))

    def test_short_form_prompt_before_fillable_table_is_a_component(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Loại sản phẩm báo cáo:</p>'
                             '<table><tr><th>TT</th><th>Loại</th><th>Số lượng</th></tr>'
                             '<tr><td>1</td><td></td><td></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)
        self.assertTrue(any(n.get('text') == 'Loại sản phẩm báo cáo:'
                            for n in nodes(result, 'form_field')))
        field = next(n for n in nodes(result, 'form_field')
                     if n.get('text') == 'Loại sản phẩm báo cáo:')
        self.assertEqual([n['type'] for n in field['children']], ['table'])
        self.assertEqual(len(nodes(result, 'table')), 1)

    def test_form_verification_signing_instruction_is_literal_instruction(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Họ tên: ...</p>'
                             '<p>Người giám sát ký xác nhận kết quả:</p>')
        self.assert_integrity(result)
        prompt = next(n for n in nodes(result, 'form_field')
                      if n.get('text') == 'Người giám sát ký xác nhận kết quả:')
        self.assertEqual(prompt['field_kind'], 'instruction')
        self.assertIsNone(prompt['value_text'])
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)

    def test_numbered_report_topics_scope_tables_and_colon_subfields(self):
        table = ('<table><tr><th>TT</th><th>Dữ liệu</th></tr>'
                 '<tr><td>1</td><td></td></tr></table>')
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p>'
                             '<p>1. Thông tin hoạt động</p><p>a) Thông tin trong kỳ</p>' + table +
                             '<p>b) Thông tin bổ sung</p>' + table +
                             '<p>2. Tình hình thực hiện các yêu cầu chuyên môn</p>'
                             '<p>a) Đánh giá rủi ro:</p><p>b) Kế hoạch dự phòng:</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        parents = [n for n in nodes(result, 'form_field') if n.get('number')]
        self.assertEqual([n['number'] for n in parents], ['1', '2'])
        self.assertTrue(all(n['field_kind'] == 'composite' for n in parents))
        self.assertEqual([n['marker'] for n in nodes(result, 'form_subfield')], ['a', 'b', 'a', 'b'])
        self.assertEqual(len(nodes(result, 'table')), 2)

    def test_decimal_counters_in_replacement_quote_keep_local_parent(self):
        result = parse_forms('<p>Điều 1. Đính chính</p><p>1. Văn bản đã phát hành:</p>'
                             '<p>“3. Trình tự xử lý</p><p>3.1. Bước đầu.</p>'
                             '<p>3.2. Bước cuối.”</p><p>Điều 2. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        from vietnam_legal_rag.ingestion.validation.extract import walk
        counters = [(n, pa) for n, pa in walk([result['document']])
                    if n.get('number') in {'3.1', '3.2'}]
        self.assertEqual([n['number'] for n, _ in counters], ['3.1', '3.2'])
        self.assertTrue(all(any(a.get('number') == '3' for a in pa) for _, pa in counters))
        self.assertEqual([n['number'] for n in nodes(result, 'article')], ['1', '2'])

    def test_header_table_prose_ellipses_are_not_completion_blanks(self):
        result = parse_forms('<p>PHỤ LỤC</p><table><tr><td><b>STT</b></td><td><b>Nội dung</b></td>'
                             '<td><b>Cơ quan</b></td></tr><tr><td>1</td>'
                             '<td><p>Các nhóm dữ liệu: sản xuất, đăng ký, ...</p>'
                             '<p>Thông tin các đơn vị:</p><p>- Dữ liệu đầu.</p>'
                             '<p>- Dữ liệu sau.</p></td><td></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual(nodes(result, 'table')[0]['table_kind'], 'data')
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)
        template = parse_forms('<p>PHỤ LỤC</p><table><tr><th>Thông tin</th><th>Giá trị</th></tr>'
                               '<tr><td>Họ tên: ...</td><td></td></tr>'
                               '<tr><td>Địa chỉ: ...</td><td></td></tr></table>')
        self.assert_integrity(template)
        self.assertEqual(nodes(template, 'table')[0]['table_kind'], 'annex_form')

    def test_attached_table_topic_counters_preserve_physical_text(self):
        result = parse_forms('<p>Điều 1. Danh mục</p><table><tr><th>Nội dung</th></tr>'
                             '<tr><td><p>1. Nhóm đầu:</p><p>- Thành phần đầu.</p>'
                             '<p>- Thành phần sau.</p><p>2.Nhóm kế tiếp:</p>'
                             '<p>- Chi tiết đầu.</p><p>- Chi tiết sau.</p>'
                             '<p>3.Nhóm cuối.</p></td></tr></table>')
        self.assert_integrity(result)
        table = nodes(result, 'table')[0]
        cell = table['cells'][1]
        self.assertEqual(cell['effective_text'],
                         '1. Nhóm đầu: - Thành phần đầu. - Thành phần sau. '
                         '2.Nhóm kế tiếp: - Chi tiết đầu. - Chi tiết sau. 3.Nhóm cuối.')
        from vietnam_legal_rag.ingestion.semantics.tables import effective_cell_text
        self.assertEqual(effective_cell_text(cell)[1], cell['effective_text'])
        items = [n for n in nodes(result, 'list_item') if n.get('number')]
        self.assertEqual([n['number'] for n in items], ['1', '2', '3'])
        self.assertEqual(items[1]['text'], '2.Nhóm kế tiếp:')
        self.assertEqual(items[2]['text'], '3.Nhóm cuối.')

    def test_terminal_request_prompt_before_input_keeps_unknown_semantics(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu số 1</p><p>BIÊN BẢN</p>'
                             '<p>Kết luận và đề nghị:</p><p>Ông (bà): ...</p>'
                             '<p>Hội đồng đề nghị giải quyết như sau:</p><p>Ngày sinh: ...</p>')
        self.assert_integrity(result)
        prompt = next(n for n in nodes(result, 'form_field')
                      if n.get('text') == 'Kết luận và đề nghị:')
        self.assertEqual(prompt['field_kind'], 'unknown')
        self.assertEqual(prompt['field_evidence'], 'source_colon_prompt_before_form_input')
        self.assertIsNone(prompt['value_text'])
        self.assertTrue(any(n.get('text') == 'Hội đồng đề nghị giải quyết như sau:'
                            for n in nodes(result, 'paragraph')))
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)

    def test_lower_html_heading_does_not_extend_existing_chapter_title(self):
        result = parse_forms('<h1>Chương I</h1><h1>QUY ĐỊNH</h1><h1>CHUNG</h1>'
                             '<h2>Phạm vi điều chỉnh</h2><p>Nội dung áp dụng.</p>'
                             '<h2>Giải thích từ ngữ</h2><p>1. Thuật ngữ đầu.</p>')
        self.assert_integrity(result)
        chapter = nodes(result, 'chapter')[0]
        self.assertEqual(chapter['title'], 'QUY ĐỊNH\nCHUNG')
        self.assertEqual([n['text'] for n in nodes(result, 'heading')],
                         ['Phạm vi điều chỉnh', 'Giải thích từ ngữ'])
        self.assertFalse(nodes(result, 'article'))

    def test_linked_note_evidence_must_be_terminal_and_paired(self):
        prefix = '<p>Điều 1. Nội dung<a href="#footnote-1">[1]</a></p>'
        note = '<ol><li id="id_footnote-1"><p>Nội dung chú dẫn.</p>'
        for html in (prefix + note + '</li></ol>',
                     prefix + note + '<a href="#footnote-ref-1">↑</a></li></ol><p>Điều 2. Thi hành</p>'):
            with self.subTest(html=html):
                result = parse_forms(html)
                self.assert_integrity(result)
                self.assertFalse(nodes(result, 'footnote'))

    def test_terminal_note_markup_in_physical_cell_keeps_table_scope(self):
        result = parse_forms('<p>Điều 1. Phạm vi<a href="#footnote-1">[1]</a></p>'
                             '<table><tr><th>Nội dung</th></tr><tr><td>'
                             '<ol><li id="id_footnote-1"><p>Chú dẫn ô.</p>'
                             '<a href="#footnote-ref-1">↑</a></li></ol></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'table')), 1)
        table = nodes(result, 'table')[0]
        self.assertTrue(any(c.get('content') for c in table['cells']))
        self.assertEqual(table['cells'][1]['effective_text'], 'Chú dẫn ô.')
        self.assertFalse(nodes(result, 'footnote_group'))

    def test_abbreviated_currency_equation_is_literal_calculation(self):
        result = parse_forms('<p>Điều 1. Mức hỗ trợ</p><p>- Mức tháng:</p>'
                             '<p>1.400.000 đ/tháng x 12 tháng = 16.800.000 đồng.</p>'
                             '<p>- Mức khác.</p><p>Điều 2. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        self.assertFalse(any(i['code'] == 'structured_paragraph_unresolved' for i in result['issues']))
        self.assertEqual(nodes(result, 'list_item')[0]['children'][0]['text'],
                         '1.400.000 đ/tháng x 12 tháng = 16.800.000 đồng.')

    def test_linked_terminal_note_list_keeps_quoted_provisions_local(self):
        result = parse_forms('<p>Điều 1. Nội dung<sup>'
                             '<a id="id_footnote-ref-1" href="#footnote-1">[1]</a></sup></p>'
                             '<ol><li id="id_footnote-1"><p>Quy định dẫn chiếu như sau:</p>'
                             '<p><b>“Điều 8. Thi hành</b></p><p>1. Trường hợp đầu.</p>'
                             '<p>2. Trường hợp sau.” <a href="#footnote-ref-1">↑</a></p>'
                             '</li></ol>')
        self.assert_integrity(result)
        self.assertEqual([n['marker'] for n in nodes(result, 'footnote')], ['1'])
        self.assertEqual(len(nodes(result, 'article')), 1)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        from vietnam_legal_rag.ingestion.validation.extract import walk
        numbered = [(n, ancestors) for n, ancestors in walk([result['document']])
                    if n.get('number') in {'1', '2'} and n['type'] == 'list_item']
        self.assertEqual(len(numbered), 2)
        self.assertTrue(all(any(a.get('type') == 'footnote' for a in ancestors)
                            for n, ancestors in numbered))

    def test_standing_deputy_signing_title_preserves_role_and_name(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><table><tr><td>'
                             '<p>Nơi nhận:</p><p>- Cơ quan;</p></td><td>'
                             '<p>KT. BỘ TRƯỞNG</p><p>THỨ TRƯỞNG THƯỜNG TRỰC</p>'
                             '<p>Nguyễn Văn An</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['THỨ TRƯỞNG THƯỜNG TRỰC'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn An'])

    def test_verification_closing_does_not_absorb_attached_numbered_procedures(self):
        result = parse_forms('<p>Điều 1. Ban hành tài liệu</p><table><tr><td>'
                             '<p>BỘ TƯ PHÁP</p><p>Số: /VBHN-BTP</p></td><td>'
                             '<p>XÁC THỰC VĂN BẢN HỢP NHẤT</p>'
                             '<p>Hà Nội, ngày tháng năm 2026</p></td></tr></table>'
                             '<p>KT. BỘ TRƯỞNG</p><p>THỨ TRƯỞNG</p><p>Nguyễn Văn An</p>'
                             '<table><tr><td>BỘ TƯ PHÁP</td><td>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p>'
                             '<p>Độc lập - Tự do - Hạnh phúc</p></td></tr></table>'
                             '<p align="center"><b>HƯỚNG DẪN SỐ 1</b></p>'
                             '<p align="center"><b>THỦ TỤC HÀNH CHÍNH</b></p>'
                             '<p>(Ban hành kèm theo Quyết định số 12/QĐ-BTP)</p>'
                             '<p><b>I. CHUẨN BỊ</b></p><p>- Hồ sơ.</p><p>- Tài liệu.</p>'
                             '<p><b>II. THỰC HIỆN</b></p><p>- Tiếp nhận.</p><p>- Xử lý.</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        self.assertEqual([n['text'] for n in nodes(result, 'list_item') if n.get('marker')],
                         ['Hồ sơ.', 'Tài liệu.', 'Tiếp nhận.', 'Xử lý.'])
        self.assertEqual([n['number'] for n in nodes(result, 'list_item') if n.get('number')], ['I', 'II'])
        self.assertEqual(len(nodes(result, 'body')), 1)

    def test_consolidated_verification_header_can_precede_separate_signature(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><table><tr><td>'
                             '<p>BỘ TƯ PHÁP</p><p>Số: /VBHN-BTP</p></td><td>'
                             '<p>XÁC THỰC VĂN BẢN HỢP NHẤT</p>'
                             '<p>Hà Nội, ngày tháng năm 2026</p></td></tr></table>'
                             '<p>KT. BỘ TRƯỞNG</p><p>THỨ TRƯỞNG</p><p>Nguyễn Văn An</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'table'))
        self.assertEqual([n['text'] for n in nodes(result, 'place_and_date')],
                         ['Hà Nội, ngày tháng năm 2026'])
        self.assertTrue(any(i['code'] == 'incomplete_source_document_date' for i in result['issues']))
        self.assertTrue(nodes(result, 'closing'))

    def test_type_prefixed_document_numbers_keep_literal_unicode(self):
        import unicodedata
        label = unicodedata.normalize('NFD', 'Luật số: 24/2026/QH16')
        result = parse_forms('<p>QUỐC HỘI</p><p>' + label + '</p>'
                             '<p>LUẬT</p><p>Về tổ chức</p><p>Điều 1. Phạm vi</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'document_number')], [label])
        self.assertEqual(nodes(result, 'document_number')[0]['number'], '24/2026/QH16')
        citation = parse_forms('<p>Điều 1. Phạm vi</p><p>Luật số 24/2026/QH16 được áp dụng.</p>')
        self.assertFalse(nodes(citation, 'document_number'))

    def test_symbol_lists_continue_through_presentation_grid_columns(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>- Nhóm đầu:</p>'
                             '<div style="display: grid; grid-template-columns: 1fr 1fr">'
                             '<div><span>+</span><span>Mục đầu</span></div>'
                             '<div>+ Mục sau</div></div><p>- Nhóm cuối.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'list_item')],
                         ['Nhóm đầu:', 'Mục đầu', 'Mục sau', 'Nhóm cuối.'])
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_form_checkbox_prompt_owns_source_choices(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 8</p>'
                             '<p>Phương thức liên hệ:</p><p>- Qua thư: □</p>'
                             '<p>- Qua điện thoại: □</p><p>Đoạn độc lập.</p>')
        self.assert_integrity(result)
        fields = nodes(result, 'form_field')
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0]['field_kind'], 'composite')
        self.assertEqual(len(nodes(result, 'list_item')), 2)
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)
        self.assertTrue(any(n['text'] == 'Đoạn độc lập.' for n in nodes(result, 'paragraph')))

    def test_form_components_own_nested_input_lists_and_decimal_topics(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 7</p>'
                             '<p><b>1. Nhóm tài sản</b></p><p>- Số lượng: ...</p>'
                             '<p>- Giá trị: ...</p><p><b>2. Nhóm đơn vị</b></p>'
                             '<p>- Tổng số: ...</p><p><b>3. Nhóm thành viên</b></p>'
                             '<p><b>3.1. Thành viên đầu</b></p><p>- Tên: ...</p>'
                             '<p>- Địa chỉ: ...</p><p><b>3.2. Thành viên sau</b></p>'
                             '<p>- Tổng số: ...</p>')
        self.assert_integrity(result)
        fields = [n for n in nodes(result, 'form_field') if n.get('number')]
        self.assertEqual([n['number'] for n in fields], ['1', '2', '3'])
        self.assertEqual([n['number'] for n in nodes(result, 'form_subfield')], ['3.1', '3.2'])
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_form_topics_without_input_evidence_remain_literal(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 7</p>'
                             '<p>1. Nhóm đầu</p><p>Nội dung giải thích.</p>'
                             '<p>2. Nhóm sau</p><p>Nội dung độc lập.</p>'
                             '<p>Phương thức:</p><p>- Qua thư.</p><p>- Qua điện thoại.</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'form_field'))

    def test_presentation_grid_lists_do_not_cross_physical_cells(self):
        result = parse_forms('<p>Điều 1. Phạm vi</p><table><tr><td>'
                             '<div style="display: grid"><div>+ Mục đầu</div></div>'
                             '</td><td><p>+ Mục sau</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'list'))
        self.assertEqual(len(nodes(result, 'table')), 1)

    def test_standalone_form_keeps_preceding_letterhead_separators(self):
        result = parse_forms('<p>PHỤ LỤC</p><table><tr><td>'
                             '<p>TÊN DOANH NGHIỆP<span><br></span>-------</p></td><td>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM<span><br></span>'
                             'Độc lập - Tự do - Hạnh phúc<span><br></span>---------------</p>'
                             '</td></tr><tr><td><p>Số: /ĐĐN-…</p></td><td>'
                             '<p>Hà Nội, ngày ... tháng ... năm 20...</p></td></tr></table>'
                             '<p><b>ĐƠN ĐỀ NGHỊ</b></p><p>Họ tên: ...</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'form')), 1)
        from vietnam_legal_rag.ingestion.validation.extract import walk
        headers = [(n, ancestors) for n, ancestors in walk([result['document']])
                   if n['type'] == 'national_heading']
        self.assertEqual(len(headers), 1)
        self.assertTrue(any(a['type'] == 'form_header' for a in headers[0][1]))
        self.assertEqual([n['text'] for n in nodes(result, 'form_number')], ['Số: /ĐĐN-…'])

    def test_wrapped_separator_does_not_end_template_letterhead_scope(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 4</p><table><tr><td>'
                             '<p>......................<span><br></span>........................(1)'
                             '<span><br></span>-------</p></td><td>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM<span><br></span>'
                             'Độc lập - Tự do - Hạnh phúc<span><br></span>---------------</p>'
                             '</td></tr><tr><td><p>Số: .../...</p></td><td>'
                             '<p>Hà Nội, ngày ... tháng ... năm 20...</p></td></tr></table>'
                             '<p><b>BẢN KHAI</b></p>'
                             '<p>Họ tên: ...</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'national_heading')), 1)
        self.assertEqual(len(nodes(result, 'national_motto')), 1)
        self.assertEqual([n['text'] for n in nodes(result, 'form_number')], ['Số: .../...'])
        self.assertTrue(nodes(result, 'form_header'))
        from vietnam_legal_rag.ingestion.validation.extract import walk
        self.assertTrue(all(any(a['type'] == 'form_header' for a in ancestors)
                            for n, ancestors in walk([result['document']]) if n['type'] == 'separator'))

    def test_wrapped_breaks_preserve_compact_letterhead_number_and_date(self):
        result = parse_forms('<table><tr><td><p>CHÍNH PHỦ<span><br></span>_______Số: 16/2026/NĐ-CP</p>'
                             '</td><td><p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM<span><br></span>'
                             'Độc lập - Tự do - Hạnh phúc<span><br></span>________'
                             '<span><br></span>Hà Nội, ngày 1 tháng 2 năm 2026</p></td></tr></table>'
                             '<p>NGHỊ ĐỊNH</p><p>Điều 1. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'document_number')], ['Số: 16/2026/NĐ-CP'])
        self.assertEqual(len(nodes(result, 'national_heading')), 1)
        self.assertEqual(len(nodes(result, 'national_motto')), 1)
        self.assertEqual([n['text'] for n in nodes(result, 'place_and_date')],
                         ['Hà Nội, ngày 1 tháng 2 năm 2026'])

    def test_explanatory_note_labels_survive_dash_body_refinement(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p><p>Họ tên: ...(1)</p>'
                             '<p>Địa chỉ: ...(2)</p><p>Ghi chú:</p>'
                             '<p>(1)- Ghi đầy đủ tên.</p><p>(2)- Ghi nơi cư trú.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['label'] for n in nodes(result, 'footnote')], ['(1)', '(2)'])
        self.assertEqual([n['text'] for n in nodes(result, 'footnote')],
                         ['- Ghi đầy đủ tên.', '- Ghi nơi cư trú.'])

    def test_wrapped_source_breaks_keep_separate_recipient_items(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><table><tr><td><p>Nơi nhận:</p>'
                             '<p><span>- Đơn vị A;</span><span><br></span>'
                             '<span>- Đơn vị B;</span><span><em><br></em></span>'
                             '<span>- Đơn vị C.</span></p></td><td>'
                             '<p>CHỦ TỊCH</p><p>Nguyễn Văn Bình</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'recipient')],
                         ['- Đơn vị A;', '- Đơn vị B;', '- Đơn vị C.'])
        from vietnam_legal_rag.ingestion.html.source import parse_html
        source = parse_html('<p>A<span><br></span>B</p><p><span><br></span></p>')
        self.assertEqual(source.find('p')[0].text(blocks=True), 'A\nB')
        self.assertEqual(source.find('p')[1].text(blocks=True), '')

    def test_compact_numbered_form_labels_keep_their_source_counters(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 3</p>'
                             '<p>1.Danh sách thiết bị:</p><table><tr><th>Tên</th><th>Số lượng</th></tr>'
                             '<tr><td>...</td><td>...</td></tr></table>'
                             '<p>2.Danh sách đơn vị:</p><table><tr><th>Tên</th><th>Địa chỉ</th></tr>'
                             '<tr><td>...</td><td>...</td></tr></table>')
        self.assert_integrity(result)
        fields = [n for n in nodes(result, 'form_field') if n.get('number')]
        self.assertEqual([n['number'] for n in fields], ['1', '2'])
        self.assertEqual([n['label'] for n in fields], ['1.', '2.'])
        self.assertTrue(all(n['value_text'] is None for n in fields))
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)

    def test_outer_clause_resumes_after_letter_decimal_point_subdivisions(self):
        result = parse_forms('<p>Điều 1. Tổ chức</p><p>1. Các đơn vị:</p>'
                             '<p>a) Nhóm đầu:</p><p>a.1) Đơn vị cấp trên.</p><p>a.2) Đơn vị cấp dưới.</p>'
                             '<p>2. Trách nhiệm của các đơn vị:</p><p>a) Tiếp nhận hồ sơ.</p>'
                             '<p>b) Giải quyết hồ sơ.</p>')
        self.assert_integrity(result)
        clauses = nodes(result, 'clause')
        self.assertEqual([n['number'] for n in clauses], ['1', '2'])
        self.assertEqual([n['number'] for n in clauses[1]['children'] if n['type'] == 'point'], ['a', 'b'])
        self.assertFalse(any(i['code'] in {'duplicate_legal_number', 'ambiguous_clause_candidate'}
                             for i in result['issues']))

    def test_parenthesized_template_explanations_are_notes_not_inputs(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 5</p><p>Cơ quan: ...(1)</p>'
                             '<p>Địa chỉ: ...(2)</p><p><b>NGƯỜI LẬP</b></p>'
                             '<p>(Ký và ghi rõ họ tên)</p><p>(1) Ghi tên cơ quan.</p>'
                             '<p>(2) Ghi địa chỉ liên hệ.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['marker'] for n in nodes(result, 'footnote')], ['1', '2'])
        self.assertFalse(any((n.get('text') or '').startswith(('(1)', '(2)'))
                             for n in nodes(result, 'form_field')))
        # Parenthesized counters with actual input placeholders remain inputs.
        unrelated = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 5</p>'
                                '<p>(1) Họ tên: ...</p><p>(2) Địa chỉ: ...</p>')
        self.assertFalse(nodes(unrelated, 'footnote'))

    def test_explicit_nested_footer_preserves_notes_and_ignores_return_controls(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 6</p><p>Họ tên: ...</p>'
                             '<hr class="footnotes-sep"><section class="footnotes">'
                             '<ol class="footnotes-list"><li class="footnote-item" id="fn-1">'
                             '<p>Giải thích thuật ngữ.</p><p><em>↩</em></p></li>'
                             '<li class="footnote-item" id="fn-2"><p>Tham chiếu văn bản. '
                             '<em>↩</em></p></li></ol></section>')
        self.assert_integrity(result)
        self.assertEqual([n['marker'] for n in nodes(result, 'footnote')], ['1', '2'])
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        from vietnam_legal_rag.ingestion.validation.extract import walk
        self.assertTrue(all(not any(a['type'] == 'form' for a in ancestors)
                            for n, ancestors in walk([result['document']]) if n['type'] == 'footnote'))
        self.assertTrue(any(i['reason'] == 'navigation_artifact' and i['text'] == '↩'
                            for i in result['ignored_elements']))

    def test_verification_without_recipients_is_not_an_input_form(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><table><tr><td>'
                             '<p>VĂN PHÒNG QUỐC HỘI________</p><p>Số: 17/VBHN-VPQH</p></td><td>'
                             '<p><b>XÁC THỰC VĂN BẢN HỢP NHẤT</b></p>'
                             '<p>Hà Nội, ngày 2 tháng 3 năm 2026</p>'
                             '<p>CHỦ NHIỆM<br><br>Nguyễn Văn Bình</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'form_field'))
        self.assertFalse(nodes(result, 'table'))
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn Bình'])
        self.assertTrue(any(n['text'] == 'Số: 17/VBHN-VPQH' for n in nodes(result, 'document_number')))

    def test_numbered_form_topics_own_their_confirmed_input_fields(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 4</p>'
                             '<p>1. Phần khai về người nộp</p><p>Họ tên: ...</p><p>Địa chỉ: ...</p>'
                             '<p>2. Phần khai về người đại diện</p><p>Họ tên: ...</p><p>Điện thoại: ...</p>')
        self.assert_integrity(result)
        parents = [n for n in nodes(result, 'form_field') if n.get('number') in {'1', '2'}]
        self.assertEqual([n['field_kind'] for n in parents], ['composite', 'composite'])
        self.assertEqual([[c.get('field_name') for c in n['children']] for n in parents],
                         [['Họ tên', 'Địa chỉ'], ['Họ tên', 'Điện thoại']])

    def test_referenced_form_citation_does_not_start_another_form(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 4</p><p>Họ tên: ...</p>'
                             '<p>Mẫu 7B[12] của văn bản này được sử dụng.</p>')
        self.assertEqual(len(nodes(result, 'form')), 1)

    def test_bare_annex_and_form_identifiers_keep_attached_note_references(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><p>CHỦ TỊCH</p><p>Nguyễn Văn Bình</p>'
                             '<p>Phụ lục[8]</p><p>Mẫu 7B[12]</p><p><b>BẢN KHAI</b></p>'
                             '<p>Họ tên: ...</p><p>Mẫu 08</p><p><b>BẢN ĐỀ NGHỊ</b></p><p>Địa chỉ: ...</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'annex')), 1)
        self.assertIsNone(nodes(result, 'annex')[0]['number'])
        self.assertEqual([n['number'] for n in nodes(result, 'form')], ['7B', '08'])
        self.assertEqual(nodes(result, 'form')[0]['label'], 'Mẫu 7B[12]')
        self.assertEqual(nodes(result, 'form')[0]['title'], 'BẢN KHAI')

    def test_th_markup_cannot_invent_axes_for_single_signing_cell(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><table><tr><th></th><th>'
                             '<p>CHỦ TỊCH QUỐC HỘI</p><p>Nguyễn Văn Bình</p>'
                             '</th></tr></table>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'table'))
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn Bình'])

    def test_note_excerpt_dash_sequence_gets_common_list_refinement(self):
        result = parse_forms('<p>Điều 1. Thi hành</p>'
                             '<div><a name="_ftn1" href="#_ftnref1">[1]</a> Nội dung thay thế:'
                             '<p>Điều 2. Phạm vi</p><p>1. Nội dung:</p>'
                             '<p>- Tài liệu thứ nhất;</p><p>- Tài liệu thứ hai.</p></div>')
        self.assert_integrity(result)
        note = nodes(result, 'footnote')[0]
        from vietnam_legal_rag.ingestion.validation.extract import walk_content
        self.assertEqual(len([n for n in walk_content([note]) if n['type'] == 'list_item' and n.get('marker') == '-']), 2)

    def test_bold_table_header_band_accepts_source_currency_units(self):
        result = parse_forms('<p>Điều 1. Mức thưởng</p><table>'
                             '<tr><td><b>Nội dung</b></td><td><b>Giá trị giải thưởng</b></td></tr>'
                             '<tr><td>Giải nhất</td><td>15 triệu đồng/giải</td></tr>'
                             '<tr><td>Giải nhì</td><td>8 triệu đồng/giải</td></tr></table>')
        self.assert_integrity(result)
        table = nodes(result, 'table')[0]
        self.assertEqual([c['role'] for c in table['cells'][:2]], ['column_header', 'column_header'])
        self.assertEqual(table['cells'][3]['effective_text'], '15 triệu đồng/giải')
        self.assertEqual(table['cells'][3]['association_status'], 'supported')

    def test_compact_multiple_delegations_preserve_signer_roles(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><p>TM. CHÍNH PHỦKT. THỦ TƯỚNG'
                             'PHÓ THỦ TƯỚNGNguyễn Văn Bình</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'delegation_title')],
                         ['TM. CHÍNH PHỦ', 'KT. THỦ TƯỚNG'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['PHÓ THỦ TƯỚNG'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn Bình'])

    def test_compact_official_header_preserves_all_source_roles(self):
        result = parse_forms('<p>CHÍNH PHỦ_____Số: 13/2026/NĐ-CP</p>'
                             '<p>CỘNG HÒAXÃ HỘI CHỦ NGHĨA VIỆT NAM'
                             'Độc lập - Tự do - Hạnh phúc_____Hà Nội, ngày 2 tháng 3 năm 2026</p>'
                             '<p>NGHỊ ĐỊNH</p><p>Điều 1. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'national_heading')],
                         ['CỘNG HÒAXÃ HỘI CHỦ NGHĨA VIỆT NAM'])
        self.assertEqual(len(nodes(result, 'national_motto')), 1)
        self.assertEqual([n['text'] for n in nodes(result, 'document_number')], ['Số: 13/2026/NĐ-CP'])
        self.assertEqual([n['text'] for n in nodes(result, 'place_and_date')], ['Hà Nội, ngày 2 tháng 3 năm 2026'])

    def test_letterhead_table_with_blank_authority_is_layout(self):
        result = parse_forms('<table><tr><td></td><td>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM'
                             'Độc lập - Tự do - Hạnh phúc</td></tr></table>'
                             '<p>THÔNG TƯ</p><p>Điều 1. Thi hành</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'table'))
        self.assertEqual(len(nodes(result, 'national_heading')), 1)
        self.assertEqual(len(nodes(result, 'national_motto')), 1)
        self.assertFalse(nodes(result, 'issuing_authority'))

    def test_numbered_phu_bieu_are_separate_annexes(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><p>PHỤ BIỂU 01</p>'
                             '<p>(Kèm theo Quyết định số 03/QĐ)</p><p><b>BÁO CÁO</b></p>'
                             '<p>1. Tên: ...</p><p>PHỤ BIỂU 02</p><p>Nội dung</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'annex')], ['01', '02'])
        self.assertFalse(any((n.get('text') or '').startswith('PHỤ BIỂU') for n in nodes(result, 'document_title')))

    def test_form_column_explanations_do_not_become_input_values(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 3</p><p>Họ tên: ...</p>'
                             '<p>Giải thích:</p><p>(1) Tên đơn vị: tên trên giấy phép.</p>'
                             '<p>Từ (2) đến (7): Ghi dấu vào ô tương ứng.</p>'
                             '<p>(9): Ghi phương thức thực hiện:</p><p>Hợp nhất:</p>'
                             '<p>Chia tách;</p><p><b>Điều 1. Nội dung mẫu</b></p>'
                             '<p>Địa chỉ: ...</p>')
        self.assert_integrity(result)
        note = next(n for n in nodes(result, 'note') if n.get('text') == 'Giải thích:')
        self.assertEqual([n['text'] for n in note['children']],
                         ['(1) Tên đơn vị: tên trên giấy phép.', 'Từ (2) đến (7): Ghi dấu vào ô tương ứng.',
                          '(9): Ghi phương thức thực hiện:', 'Hợp nhất:', 'Chia tách;'])
        self.assertFalse(any((n.get('text') or '').startswith(('(1)', 'Từ (2)', '(9)', 'Hợp nhất'))
                             for n in nodes(result, 'form_field')))
        self.assertTrue(any(n.get('field_name') == 'Địa chỉ' for n in nodes(result, 'form_field')))

    def test_explanation_heading_without_references_does_not_absorb_inputs(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 3</p><p>Họ tên: ...</p>'
                             '<p>Giải thích:</p><p>Địa chỉ: ...</p>')
        self.assertTrue(any(n.get('field_name') == 'Địa chỉ' for n in nodes(result, 'form_field')))
        self.assertFalse(any(n.get('text') == 'Giải thích:' and n.get('children')
                             for n in nodes(result, 'note')))

    def test_form_confirmation_request_leadin_is_instruction_without_value(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 5</p><p>Họ tên: ...</p>'
                             '<p>Xác nhận và đề nghị:</p><p>Ngày sinh: ...</p>')
        self.assert_integrity(result)
        lead = next(n for n in nodes(result, 'form_field') if n.get('text') == 'Xác nhận và đề nghị:')
        self.assertEqual(lead['field_kind'], 'instruction')
        self.assertIsNone(lead['value_text'])

    def test_unfilled_authority_lines_keep_placeholders_and_header_phase(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p><p>……….</p><p>……….(1)--------</p>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p>'
                             '<p style="text-align:center">ĐƠN ĐỀ NGHỊ</p><p>Họ tên: ...</p>')
        self.assert_integrity(result)
        self.assertEqual(nodes(result, 'form')[0]['title'], 'ĐƠN ĐỀ NGHỊ')
        self.assertTrue(any(n.get('text') == '……….' for n in nodes(result, 'form_placeholder')))
        self.assertEqual(len(nodes(result, 'national_heading')), 1)
        self.assertEqual(len(nodes(result, 'national_motto')), 1)
        self.assertFalse(any(n.get('text') == '……….' for n in nodes(result, 'issuing_authority')))

    def test_authority_header_input_labels_keep_their_literal_blank_values(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p><p><b>Công ty dịch vụ:……….</b></p>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p>'
                             '<p style="text-align:center">ĐƠN ĐỀ NGHỊ</p><p>Họ tên: ...</p>')
        self.assert_integrity(result)
        field = next(n for n in nodes(result, 'form_field') if n.get('field_name') == 'Công ty dịch vụ')
        self.assertEqual(field['value_text'], '……….')
        self.assertEqual(field['field_kind'], 'input')
        self.assertFalse(any(n.get('text') == 'Công ty dịch vụ:……….' for n in nodes(result, 'issuing_authority')))

    def test_header_acronym_placeholder_does_not_assert_authority_identity(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p><p><b>ABC……….</b></p>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p>'
                             '<p style="text-align:center">ĐƠN ĐỀ NGHỊ</p><p>Họ tên: ...</p>')
        self.assert_integrity(result)
        self.assertTrue(any(n.get('text') == 'ABC……….' for n in nodes(result, 'form_field')))
        self.assertFalse(any(n.get('text') == 'ABC……….' for n in nodes(result, 'issuing_authority')))

    def test_emphasized_cited_law_subject_does_not_become_document_title(self):
        result = parse_forms('<p>Số: 07/VBHN</p><p>NGHỊ ĐỊNH</p><p>Về tổ chức hoạt động</p>'
                             '<p><b>Luật Phòng cháy và chữa cháy số 27/2001/QH10 có hiệu lực</b></p>'
                             '<p>Căn cứ Luật tổ chức;</p><p>Điều 1. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'document_type_heading')], ['NGHỊ ĐỊNH'])

    def test_form_signing_prompt_keeps_mixed_case_role_and_instruction(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p><p>Họ tên: ...</p>'
                             '<p>Người đứng đầu đơn vị</p><p>Ký, ghi rõ họ tên và đóng dấu (nếu có)</p>')
        self.assert_integrity(result)
        signature = nodes(result, 'form_signature')[0]
        self.assertEqual(signature['children'][0]['type'], 'signer_title')
        self.assertEqual(signature['children'][0]['text'], 'Người đứng đầu đơn vị')
        self.assertEqual(signature['children'][1]['field_kind'], 'instruction')
        self.assertIsNone(signature['children'][1]['value_text'])
        self.assertFalse(nodes(result, 'signature_marker'))

    def test_unstyled_template_article_ends_dash_input_continuation(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p>'
                             '<p>Điều 1.Cho phép: ...</p><p>- Tên thương nhân: ...</p><p>- Địa chỉ:</p>'
                             '<p>được đặt chi nhánh tại địa phương</p>'
                             '<p>Điều 2.Tên chi nhánh</p><p>- Tên đầy đủ: ...</p><p>- Tên viết tắt: ...</p>'
                             '<p>Điều 3.Địa chỉ trụ sở</p><p>Địa chỉ: ...</p>'
                             '<p>Điều 4.Nội dung hoạt động</p><p>1.</p><p>2.</p>')
        self.assert_integrity(result)
        headings = [n for n in nodes(result, 'heading') if n.get('evidence') == 'explicit_article_heading_in_source_template']
        self.assertEqual([n['text'].split('.')[0] for n in headings], ['Điều 1', 'Điều 2', 'Điều 3', 'Điều 4'])
        self.assertFalse(any((n.get('text') or '').startswith('Điều ') for n in nodes(result, 'form_field')))
        self.assertEqual([n['number'] for n in nodes(result, 'list_item') if n.get('number')], ['1', '2'])

    def test_wrapped_signer_authority_qualifier_is_not_a_person(self):
        from vietnam_legal_rag.ingestion.semantics.hierarchy import logical_blocks
        text = 'GIÁM ĐỐC\nNGÂN HÀNG QUỐCGIA VIỆT NAM'
        block = {'type': 'layout_block', 'source_layout': {'table_id': 'table_1'},
                 'children': [{'type': 'paragraph', 'text': text, 'children': [], 'order': 2,
                               'source_ref': {'tag': 'p', 'dom_order': 2}}]}
        self.assertEqual([n['text'] for n in logical_blocks([block])], [text])

    def test_declared_heading_continuation_is_not_a_roman_legal_label(self):
        result = parse_forms('<p class="prov-chapter">Chương I</p>'
                             '<p class="prov-chapter">CHI TIẾT VỀ TỔ CHỨC</p><p>Điều 1. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'chapter')], ['I'])
        self.assertTrue(any('CHI TIẾT' in (n.get('title') or '') for n in nodes(result, 'chapter')))

    def test_emphasized_document_number_line_does_not_start_title_block(self):
        result = parse_forms('<p><b>Luật số: 07/2026/QH16</b></p><p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p>'
                             '<p>Độc lập - Tự do - Hạnh phúc</p><p>LUẬT</p><p>Về tổ chức</p><p>Điều 1. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'document_type_heading')), 1)
        self.assertEqual(len(nodes(result, 'national_heading')), 1)

    def test_emphasized_mixed_case_type_and_title_preserve_source_case(self):
        result = parse_forms('<p>Số: 07/NĐ-CP</p><p><b>Nghị Định<br>Về tổ chức hoạt động</b></p>'
                             '<p>Căn cứ Luật tổ chức;</p><p>Điều 1. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual(nodes(result, 'document_type_heading')[0]['text'], 'Nghị Định')
        self.assertEqual(nodes(result, 'document_title')[0]['text'], 'Về tổ chức hoạt động')

    def test_emphasized_joined_type_heading_keeps_literal_missing_space(self):
        result = parse_forms('<p>Số: 07/NQ-HĐND</p><p><b>NGHỊQUYẾT</b></p>'
                             '<p><b>Về tổ chức hoạt động</b></p><p>Căn cứ Luật tổ chức;</p><p>Điều 1. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual(nodes(result, 'document_type_heading')[0]['text'], 'NGHỊQUYẾT')
        self.assertEqual(nodes(result, 'document_title')[0]['text'], 'Về tổ chức hoạt động')

    def test_internal_spanning_heading_has_no_invented_table_axis(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><table><tr><th>STT</th><th>Nội dung</th></tr>'
                             '<tr><td colspan="2"><b>Nhóm hồ sơ</b></td></tr><tr><td>1</td><td>Hồ sơ</td></tr></table>')
        self.assert_integrity(result)
        cell = next(c for t in nodes(result, 'table') for c in t['cells'] if c['text'] == 'Nhóm hồ sơ')
        self.assertEqual(cell['role'], 'unknown')
        self.assertEqual(cell['colspan'], 2)
        self.assertFalse(cell.get('header_refs'))
        self.assertTrue(any(i['code'] == 'table_semantics_unresolved' for i in result['issues']))

    def test_joined_delegation_title_name_splits_inside_source_layout(self):
        from vietnam_legal_rag.ingestion.semantics.hierarchy import logical_blocks
        text = 'KT. CHỦ TỊCHPHÓ CHỦ TỊCHNguyễn Văn Bình'
        block = {'type': 'layout_block', 'source_layout': {'table_id': 'table_1'},
                 'children': [{'type': 'paragraph', 'text': text, 'children': [], 'order': 2,
                               'source_ref': {'tag': 'p', 'dom_order': 2}}]}
        units = list(logical_blocks([block]))
        self.assertEqual([n['text'] for n in units], ['KT. CHỦ TỊCH', 'PHÓ CHỦ TỊCH', 'Nguyễn Văn Bình'])
        self.assertEqual(''.join(n['text'] for n in units), text)

    def test_interleaved_recipient_emphasis_keeps_signing_fragments(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><p>Nơi nhận:</p><p>TM. ỦY BAN NHÂN DÂN</p>'
                             '<p>- Cơ quan A; <b>KT. CHỦ TỊCH</b></p><p>- Cơ quan B; <b>PHÓ CHỦ TỊCH</b></p>'
                             '<p>- Cơ quan C; <b>Nguyễn Văn Bình</b></p><p>- Lưu hồ sơ;</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn Bình'])
        self.assertEqual([n['text'] for n in nodes(result, 'recipient')], ['- Cơ quan A;', '- Cơ quan B;', '- Cơ quan C;', '- Lưu hồ sơ;'])

    def test_centered_signer_after_interleaved_recipient_run_keeps_signature(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><p>Nơi nhận:</p><p>PHÓ CHỦ TỊCH</p>'
                             '<p>- Cơ quan A;</p><p>- Cơ quan B;</p><p style="text-align:center"><b>Nguyễn Văn Bình</b></p>'
                             '<p>- Lưu hồ sơ;</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn Bình'])
        self.assertFalse(any(n.get('text') == 'Nguyễn Văn Bình' for n in nodes(result, 'recipient')))

    def test_partial_signature_marker_preserves_fragment_and_signer_context(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><p>PHÓ CHỦ TỊCH</p><p>[daky]</p><p>aky]</p><p>Nguyễn Văn Bình</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn Bình'])
        self.assertTrue(any(n.get('text') == 'aky]' for n in nodes(result, 'paragraph')))
        self.assertTrue(any(i['code'] == 'source_partial_signature_marker' for i in result['issues']))
        self.assertFalse(result['hierarchy_validation']['semantic_complete'])

    def test_preclassified_template_fields_still_expose_article_sequence(self):
        from vietnam_legal_rag.ingestion.refinement.forms import refine_form
        form = {'type': 'form', 'title': None, 'children': [
            {'type': 'form_field' if i == 1 else 'paragraph', 'order': i, 'text': t,
             'source_ref': {'tag': 'p', 'dom_order': i}, 'children': []}
            for i, t in enumerate(['Điều 1.Người nhận: ...', 'Điều 2.Tên đơn vị'], 1)]}
        refine_form(form)
        self.assertEqual([n['type'] for n in form['children']], ['heading', 'heading'])
        self.assertEqual([n['text'] for n in form['children']], ['Điều 1.Người nhận: ...', 'Điều 2.Tên đơn vị'])

    def test_form_roman_outline_keeps_local_numeric_and_alpha_children(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p><p>I. Thông tin</p>'
                             '<p>1. Tên đơn vị: ...</p><p>II. Hoạt động</p><p>1. Hoạt động thương mại</p>'
                             '<p>a) Hoạt động chủ yếu:</p><table><tr><td>...</td></tr></table>'
                             '<p>b) Kết quả hoạt động:</p><p>III. Kiến nghị</p>'
                             '<p>Chúng tôi cam kết:</p>')
        self.assert_integrity(result)
        roman = [n for n in nodes(result, 'list_item') if n.get('number') in ['I', 'II', 'III']]
        self.assertEqual([n['number'] for n in roman], ['I', 'II', 'III'])
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)
        self.assertFalse(nodes(result, 'clause'))

    def test_joined_form_alpha_counters_keep_subfields_across_table(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p><p>3. Nội dung hoạt động:</p>'
                             '<p>a. Thống kê:</p><table><tr><td>...</td></tr></table>'
                             '<p>b.Kết quả hoạt động</p><p>c. Nhận xét</p><p>4. Địa chỉ: ...</p>')
        self.assert_integrity(result)
        field = nodes(result, 'form_field')[0]
        self.assertEqual([n['marker'] for n in field['children']], ['a', 'b', 'c'])
        self.assertEqual(field['children'][1]['label'], 'b.')
        self.assertEqual(field['children'][1]['text'], 'Kết quả hoạt động')
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)

    def test_form_table_prompt_owns_literal_numbered_blank_slots(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p>'
                             '<table><tr><td><p>Lĩnh vực hoạt động:</p><p>1….</p><p>2….</p></td><td></td></tr></table>')
        self.assert_integrity(result)
        prompt = nodes(result, 'form_field')[0]
        self.assertEqual(prompt['field_name'], 'Lĩnh vực hoạt động')
        self.assertIsNone(prompt['value_text'])
        self.assertEqual([n['text'] for n in nodes(result, 'form_placeholder')], ['1….', '2….'])
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)

    def test_form_decimal_inputs_keep_their_actual_numbered_parent(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu AB-1</p>'
                             '<p>2. Hoạt động khác (nêu công việc cụ thể)</p><p>2.1.</p><p>2.2.</p>')
        self.assert_integrity(result)
        field = nodes(result, 'form_field')[0]
        self.assertEqual(field['number'], '2')
        self.assertEqual([n['number'] for n in field['children']], ['2.1', '2.2'])
        self.assertTrue(all(n['value_text'] is None for n in field['children']))
        self.assertEqual(result['hierarchy_validation']['unresolved']['orphan_nodes'], 0)

    def test_form_bounded_colon_prompt_chain_preserves_unknown_semantics(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p><p>Họ tên: ...</p>'
                             '<p>Quốc tịch:</p><p>Mã số thuế:</p><p>Lý do điều chỉnh:</p>'
                             '<p>Chúng tôi cam kết:</p><p>1. Chịu trách nhiệm.</p><p>2. Chấp hành quy định.</p>')
        self.assert_integrity(result)
        prompts = [n for n in nodes(result, 'form_field') if n.get('field_kind') == 'unknown']
        self.assertEqual([n['field_name'] for n in prompts], ['Quốc tịch', 'Mã số thuế', 'Lý do điều chỉnh'])
        self.assertTrue(all(n['value_text'] is None for n in prompts))
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)
        self.assertTrue(any(n.get('field_kind') == 'display' and n.get('field_evidence') == 'source_form_declaration'
                            for n in nodes(result, 'form_field')))

    def test_form_completion_qualifier_is_not_a_value_or_second_prompt(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p>'
                             '<p>Họ tên: (ghi bằng chữ in hoa) ........ Giới tính:</p>'
                             '<p>Tên đơn vị: (ghi bằng chữ in hoa):</p>')
        self.assert_integrity(result)
        fields = nodes(result, 'form_field')
        self.assertEqual(fields[0]['value_text'], '........')
        self.assertEqual(nodes(result, 'form_subfield')[0]['field_name'], 'Giới tính')
        self.assertIsNone(fields[1]['value_text'])
        self.assertEqual(result['form_validation']['suspicious_value_text'], 0)

    def test_form_layout_cannot_absorb_titles_or_template_provisions(self):
        # The HTML layout pass has already unwrapped these source blocks.
        # A surviving physical form table is a different parsing scope.
        from vietnam_legal_rag.ingestion.refinement.forms import refine_form
        texts = ['CƠ QUAN QUẢN LÝ', 'CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM',
                 'Độc lập - Tự do - Hạnh phúc', 'GIẤY PHÉP',
                 'Điều 1.Cho phép: ...', 'Điều 2.Tên đơn vị: ...']
        children = [{'type': 'paragraph', 'text': t, 'order': i, 'children': [],
                     'source_ref': {'tag': 'p', 'dom_order': i}, '_source_layout': 1,
                     **({'_alignment': 'center'} if t == 'GIẤY PHÉP' else {})}
                    for i, t in enumerate(texts, 1)]
        form = {'type': 'form', 'title': None, 'children': children}
        refine_form(form)
        self.assertEqual(form['title'], 'GIẤY PHÉP')
        headings = [n for n in form['children'] if n.get('evidence') == 'explicit_article_heading_in_source_template']
        self.assertEqual(len(headings), 2)
        self.assertFalse(any(n['type'] == 'heading' for h in form['children'] if h['type'] == 'form_header' for n in h['children']))
        self.assertEqual([n['order'] for h in form['children'] for n in (h['children'] if h['type'] == 'form_header' else [h])], list(range(1, 7)))

    def test_split_authority_header_precedes_placeholder_form_title(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p>'
                             '<p style="text-align:center">Cơ quan quản lý/</p><p style="text-align:center">Ban quản lý…</p>'
                             '<p>CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p>'
                             '<p style="text-align:center">BÁO CÁO HOẠT ĐỘNG TẠI…</p><p>Họ tên: ...</p>')
        self.assert_integrity(result)
        self.assertEqual(nodes(result, 'form')[0]['title'], 'BÁO CÁO HOẠT ĐỘNG TẠI…')
        self.assertEqual(len(nodes(result, 'issuing_authority')), 2)

    def test_letter_prefixed_form_codes_keep_independent_templates(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu AB-1</p><p>Họ tên: ...</p>'
                             '<p>Mẫu CD-2</p><p>Địa chỉ: ...</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'form')], ['AB-1', 'CD-2'])
        self.assertEqual(len(nodes(result, 'form_field')), 2)

    def test_declared_roman_chapter_retains_joined_title(self):
        result = parse_forms('<p class="prov-chapter">Chương IVĐIỀU KHOẢN THI HÀNH</p>'
                             '<p>Điều 1. Nội dung</p>')
        self.assert_integrity(result)
        chapter = nodes(result, 'chapter')[0]
        self.assertEqual(chapter['number'], 'IV')
        self.assertEqual(chapter['title'], 'ĐIỀU KHOẢN THI HÀNH')
        self.assertEqual(nodes(result, 'article')[0]['number'], '1')

    def test_joined_title_and_name_preserve_exact_source_offsets(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><p>KT. CHỦ TỊCH</p>'
                             '<p>PHÓ CHỦ TỊCHNguyễn Văn Bình</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['PHÓ CHỦ TỊCH'])
        name = nodes(result, 'signer_name')[0]
        self.assertEqual(name['text'], 'Nguyễn Văn Bình')
        self.assertEqual(name['source_offset'], len('PHÓ CHỦ TỊCH'))
        self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_flat_recipient_context_ends_at_unrelated_closing_prose(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><p>Nơi nhận:</p><p>CHỦ TỊCH</p>'
                             '<p>Nội dung giải thích khác.</p><p>GIÁM ĐỐC</p>'
                             '<p>- Một đề mục khác;</p><p>- Đề mục tiếp theo.</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'recipient'))

    def test_numbered_form_provisions_do_not_become_whole_line_input_labels(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu số 03-TT18-10</p>'
                             '<p>Điều 1. Người nhận: ...</p><p>1. Khoản hưởng: ...</p><p>2. Địa chỉ: ...</p>'
                             '<p>Điều 2. Thi hành quyết định.</p>')
        self.assert_integrity(result)
        headings = [n for n in nodes(result, 'heading') if n.get('evidence') == 'explicit_article_heading_in_source_template']
        self.assertEqual([n['text'] for n in headings], ['Điều 1. Người nhận: ...', 'Điều 2. Thi hành quyết định.'])
        self.assertFalse(any((n.get('field_name') or '').startswith('Điều ') for n in nodes(result, 'form_field')))
        self.assertEqual([n['number'] for n in nodes(result, 'form_field')], ['1', '2'])

    def test_template_article_list_keeps_introductory_input_prompt(self):
        result = parse_forms('<p>Điều 1. Ban hành</p><p>PHỤ LỤC</p><p>Mẫu số 01-NĐ42-09</p>'
                             '<p>Điều 1. Người nhận: ...</p><p>Thay mặt thân nhân nhận:</p>'
                             '<p>a) Khoản trợ cấp: ... đồng;</p><p>b) Khoản hỗ trợ: ... đồng;</p>'
                             '<p>Điều 2. Thi hành mẫu quyết định.</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)
        prompt = next(n for n in nodes(result, 'form_field') if n['text'] == 'Thay mặt thân nhân nhận:')
        self.assertEqual(prompt['field_kind'], 'unknown')
        self.assertEqual([n['marker'] for n in prompt['children'] if n['type'] == 'form_subfield'], ['a', 'b'])

    def test_form_directory_outline_stops_before_numbered_templates(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><p>PHỤ LỤC</p><p>Danh mục và mẫu kèm theo</p><p><b>I. BIỂN BÁO</b></p><p>1. Biển báo</p>'
                             '<p><b>II. THÔNG BÁO</b></p><p>1. Thông báo</p>'
                             '<p>Mẫu số 01a. BIỂN BÁO</p><p>Địa điểm: ...</p>'
                             '<p>Mẫu số 02. THÔNG BÁO</p><p>Nội dung: ...</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'form')], ['01a', '02'])
        self.assertEqual(len(nodes(result, 'list_item')), 4)
        self.assertEqual(len(nodes(result, 'form_field')), 2)

    def test_compound_form_identifiers_keep_separate_template_scopes(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu số 01-NĐ42-09</p><p>Họ tên: ...</p>'
                             '<p>Mẫu số 02-NĐ42-09</p><p>Địa chỉ: ...</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'form')], ['01-NĐ42-09', '02-NĐ42-09'])
        self.assertEqual([len(n['children']) for n in nodes(result, 'form')], [1, 1])

    def test_duplicated_note_prefix_does_not_destroy_evidenced_note_series(self):
        result = parse_forms('<p>Điều 1. Nội dung[1][2]</p><p>1[1]Ghi chú thứ nhất.</p>'
                             '<p>22[2]Ghi chú thứ hai.</p><p>Tiếp tục chú thích.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['marker'] for n in nodes(result, 'footnote')], ['1', '2'])
        self.assertEqual([n['label'] for n in nodes(result, 'footnote')], ['1[1]', '22[2]'])
        self.assertEqual(len(nodes(result, 'footnote_group')), 1)
        self.assertEqual([i['code'] for i in result['issues'] if i['severity'] == 'warning'],
                         ['inconsistent_source_footnote_prefix'])
        self.assertFalse(result['hierarchy_validation']['semantic_complete'])

    def test_point_quantity_is_not_an_unresolved_decimal_outline(self):
        result = parse_forms('<p>Điều 1. Định mức</p><p>1. Vật dụng:</p>'
                             '<p>k) 3,6 kg xà phòng/năm;</p><p>l) 1.000 ml dầu gội/năm;</p>'
                             '<p>m) 01 màn/03 năm;</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        from vietnam_legal_rag.ingestion.validation.forms import structured_paragraphs
        probe = {'type': 'legal_document', 'children': [{'type': 'paragraph', 'text': '1.000 Mục nội dung',
                 'order': 1, 'source_ref': {'dom_order': 1}}]}
        self.assertFalse(structured_paragraphs(probe)[0]['justified'])

    def test_recipients_continue_after_explicit_multiline_delegation(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><p>Nơi nhận:</p>'
                             '<p>TM. ỦY BAN NHÂN DÂN<br>KT. CHỦ TỊCH<br>PHÓ CHỦ TỊCH</p>'
                             '<p>- Cơ quan A;</p><p>- Lưu: VT.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'recipient')], ['- Cơ quan A;', '- Lưu: VT.'])
        self.assertEqual([n['text'] for n in nodes(result, 'delegation_title')],
                         ['TM. ỦY BAN NHÂN DÂN', 'KT. CHỦ TỊCH'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['PHÓ CHỦ TỊCH'])
        self.assertEqual([n['type'] for n in nodes(result, 'closing')[0]['children']],
                         ['recipients', 'signature', 'recipients'])

    def test_incomplete_verification_date_retains_unknown_source_components(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><table><tr><td><p>Nơi nhận:</p><p>- Lưu: VT.</p></td>'
                             '<td><p>XÁC THỰC VĂN BẢN HỢP NHẤT</p>'
                             '<p>Bắc Ninh, ngày tháng năm 2026</p><p>CHỦ TỊCH</p>'
                             '<p>Nguyễn Văn Bình</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'place_and_date')],
                         ['Bắc Ninh, ngày tháng năm 2026'])
        self.assertEqual([n['text'] for n in nodes(result, 'recipient')], ['- Lưu: VT.'])
        self.assertTrue(result['validation']['meaningful_text_preserved'])
        self.assertFalse(result['hierarchy_validation']['semantic_complete'])
        self.assertEqual([i['code'] for i in result['issues'] if i['severity'] == 'warning'],
                         ['incomplete_source_document_date'])

    def test_verifier_heading_and_date_do_not_extend_recipient_column(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><p>1. Nội dung.</p>'
                             '<table><tr><td><p>Nơi nhận:</p><p>- Cơ quan A;</p><p>- Lưu: VT.</p></td>'
                             '<td><p>BỘ TÀI CHÍNH</p><p>XÁC THỰC VĂN BẢN HỢP NHẤT</p>'
                             '<p>Hà Nội, ngày 3 tháng 4 năm 2026</p><p>KT. BỘ TRƯỞNG</p>'
                             '<p>THỨ TRƯỞNG</p><p>Nguyễn Văn Bình</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'recipient')], ['- Cơ quan A;', '- Lưu: VT.'])
        self.assertEqual([n['text'] for n in nodes(result, 'place_and_date')],
                         ['Hà Nội, ngày 3 tháng 4 năm 2026'])
        self.assertEqual([n['text'] for n in nodes(result, 'issuing_authority')], ['BỘ TÀI CHÍNH'])
        self.assertEqual([n['text'] for n in nodes(result, 'heading')], ['XÁC THỰC VĂN BẢN HỢP NHẤT'])
        local = parse_forms('<p>Điều 1. Thi hành</p><table><tr><td><p>Nơi nhận:</p><p>- Lưu: VT.</p></td>'
                            '<td><p>ỦY BAN NHÂN DÂN</p><p>TỈNH BẮC NINH</p>'
                            '<p>XÁC THỰC VĂN BẢN HỢP NHẤT</p><p>CHỦ TỊCH</p>'
                            '<p>Nguyễn Văn Bình</p></td></tr></table>')
        self.assert_integrity(local)
        self.assertEqual([n['text'] for n in nodes(local, 'issuing_authority')],
                         ['ỦY BAN NHÂN DÂN', 'TỈNH BẮC NINH'])
        self.assertEqual([n['text'] for n in nodes(local, 'recipient')], ['- Lưu: VT.'])

    def test_consolidated_verification_table_has_closing_scope(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>1. Thi hành.</p><table><tr><td>'
                             '<p>VĂN PHÒNG QUỐC HỘI</p><p>Số: 12/VBHN-VPQH</p><p>Nơi nhận:- Cơ quan liên quan;</p>'
                             '</td><td><p>XÁC THỰC VĂN BẢN HỢP NHẤT</p><p>Hà Nội, ngày 2 tháng 3 năm 2026</p>'
                             '<p>CHỦ NHIỆM<br>Nguyễn Văn An</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'form_field'))
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['CHỦ NHIỆM'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn An'])
        closing = nodes(result, 'closing')[0]
        self.assertEqual(closing['children'][0]['type'], 'issuing_authority')
        self.assertEqual(len(nodes(result, 'article')[0]['children'][0]['children']), 1)

    def test_blank_template_recipient_retains_input_field_inside_address_scope(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Họ tên: ...</p><p>Nơi nhận: ....</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'form_field')), 2)
        recipients = nodes(result, 'recipients')
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]['children'][0]['field_kind'], 'input')

    def test_inline_template_recipient_heading_keeps_following_list(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Họ tên: ...</p>'
                             '<p>Nơi nhận:- Công ty;</p><p>- Cơ quan quản lý;</p><p>BỘ TRƯỞNG</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'recipients')], ['Nơi nhận:- Công ty;'])
        self.assertEqual(len(nodes(result, 'recipient')), 1)

    def test_form_label_before_next_annex_does_not_create_empty_form(self):
        result = parse_forms('<p>PHỤ LỤC 1</p><p>Mẫu 1</p><p>Họ tên: ...</p>'
                             '<p>Mẫu số 19</p><p>PHỤ LỤC 2</p><p align="center"><b>BÁO CÁO</b></p><p>Tên: ...</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'form')), 2)
        self.assertTrue(any(n['text'] == 'Mẫu số 19' for n in nodes(result, 'heading')))
        self.assertTrue(any(i['code'] == 'form_label_before_annex_boundary' for i in result['issues']))

    def test_revoked_annex_parenthesis_keeps_distinct_boundaries(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>PHỤ LỤC 1(được bãi bỏ)</p>'
                             '<p>PHỤ LỤC 2(được bãi bỏ)</p><p>PHỤ LỤC 3</p><p>Nội dung phụ lục</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'annex')], ['1', '2', '3'])
        self.assertEqual(nodes(result, 'annex')[0]['title'], '(được bãi bỏ)')

    def test_untitled_letter_template_has_evidenced_form_scope(self):
        result = parse_forms('<p>PHỤ LỤC 1</p><p>(Kèm theo Thông tư)</p><p>BỘ TÀI CHÍNH</p>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p>'
                             '<p>Số: /...</p><p>..., ngày...tháng...năm...</p>'
                             '<p>Kính gửi: Công ty ...(1)...</p><p>Nội dung đề nghị ...(2)...</p>'
                             '<p>Nơi nhận:</p><p>- Công ty;</p><p>BỘ TRƯỞNG</p><p>(Ký tên, đóng dấu)</p>')
        self.assert_integrity(result)
        forms = nodes(result, 'form')
        self.assertEqual(len(forms), 1)
        self.assertIsNone(forms[0]['title'])
        self.assertTrue(nodes(result, 'form_header'))
        self.assertTrue(nodes(result, 'recipients'))

    def test_form_signing_title_with_joined_instruction_is_scoped(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1</p><p>Họ tên: ...</p><p>CHỦ TỊCH(Ký tên, đóng dấu)</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['CHỦ TỊCH(Ký tên, đóng dấu)'])
        self.assertTrue(nodes(result, 'form_signature'))

    def test_repeated_literal_terminal_note_prefix_is_preserved(self):
        result = parse_forms('<p>Điều 1. Quy định[1][2][3]</p>'
                             '<p>[1] Ghi chú thứ nhất.</p><p>[2] Ghi chú thứ hai.</p>'
                             '<p>3[3] Ghi chú thứ ba.</p>')
        self.assert_integrity(result)
        notes = nodes(result, 'footnote')
        self.assertEqual([n['marker'] for n in notes], ['1', '2', '3'])
        self.assertEqual(notes[-1]['label'], '3[3]')

    def test_compact_opening_tokens_preserve_wording_and_source_roles(self):
        result = parse_forms('<p>ỦYBAN NHÂN DÂN</p><p>TỈNH AN BÌNH</p>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p>'
                             '<p>Độc lập - Tự do - Hạnh phúc</p><p>Số: 1/QĐ-UBND</p>'
                             '<p>An Bình, ngày09tháng 9năm2026</p><p>QUYẾT ĐỊNH</p>'
                             '<p align="center">Ban hành quy định</p><p>Căn cứLuật tổ chức chính quyền;</p>'
                             '<p>Điều 1. Nội dung</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'issuing_authority')],
                         ['ỦYBAN NHÂN DÂN', 'TỈNH AN BÌNH'])
        self.assertEqual([n['text'] for n in nodes(result, 'place_and_date')], ['An Bình, ngày09tháng 9năm2026'])
        self.assertEqual([n['text'] for n in nodes(result, 'legal_basis')], ['Căn cứLuật tổ chức chính quyền;'])

    def test_issuing_title_after_motivation_retains_preamble_role(self):
        result = parse_forms('<p>QUYẾT ĐỊNH</p><p align="center">Ban hành quy định</p>'
                             '<p>' + 'Nội dung đề nghị và căn cứ thực tế của cơ quan. ' * 4 + '</p>'
                             '<p>CHỦ TỊCH ỦY BAN NHÂN DÂN TỈNH</p><p>Căn cứ Luật tổ chức chính quyền;</p>'
                             '<p>QUYẾT ĐỊNH:</p><p>Điều 1. Nội dung</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'issuing_authority_title')],
                         ['CHỦ TỊCH ỦY BAN NHÂN DÂN TỈNH'])

    def test_attached_house_rules_leave_outer_closing_scope(self):
        result = parse_forms('<p>Điều 1. Ban hành</p><p>Điều 2. Thi hành</p>'
                             '<p>CHỦ TỊCH</p><p>Nguyễn Văn An</p>'
                             '<p align="center"><b>NỘI QUY</b></p><p align="center">Kỳ họp của hội đồng</p>'
                             '<p align="center">(Ban hành kèm theo Nghị quyết)</p>'
                             '<p>Chương I</p><p>Điều 1. Phạm vi</p><p>1. Đối tượng</p><p>2. Yêu cầu</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'article')], ['1', '2', '1'])
        self.assertEqual([n['number'] for n in nodes(result, 'clause')], ['1', '2'])
        self.assertFalse(any(i['code'] == 'duplicate_legal_number' for i in result['issues']))
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn An'])

    def test_compact_signing_status_and_name_have_independent_source_roles(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>CHỦ TỊCH(Đã ký)Nguyễn Văn An</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['CHỦ TỊCH'])
        self.assertEqual([n['text'] for n in nodes(result, 'signature_status')], ['(Đã ký)'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn An'])

    def test_form_header_date_without_comma_does_not_end_title_scope(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 1A</p>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p>'
                             '<p>---------------</p><p>Ngày……tháng……năm20…</p><p align="center"><b>BẢN KHAI</b></p>'
                             '<p>Họ tên: ...</p>')
        self.assert_integrity(result)
        self.assertEqual(nodes(result, 'form')[0]['title'], 'BẢN KHAI')
        self.assertEqual([n['text'] for n in nodes(result, 'place_and_date')], ['Ngày……tháng……năm20…'])

    def test_standalone_form_owns_contiguous_source_template_letterhead(self):
        result = parse_forms('<p>PHỤ LỤC</p><p align="center">TÊN DOANH NGHIỆP -------</p>'
                             '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p>'
                             '<p>---------------</p>'
                             '<p>Số: ...</p><p>..., ngày...tháng...năm...</p>'
                             '<p align="center"><b>ĐƠN ĐỀ NGHỊ</b></p><p>Họ tên: ...</p>')
        self.assert_integrity(result)
        form = nodes(result, 'form')[0]
        self.assertTrue(any(n['type'] == 'form_header' for n in form['children']))
        self.assertEqual(form['title'], 'ĐƠN ĐỀ NGHỊ')

    def test_alphanumeric_form_identifiers_preserve_separate_scopes(self):
        result = parse_forms('<p>PHỤ LỤC I</p><p>Mẫu 1A</p><p>Họ tên: ...</p>'
                             '<p>Mẫu 1B</p><p>Địa chỉ: ...</p><p>Mẫu 3A-1</p><p>Ngày: ...</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'form')], ['1A', '1B', '3A-1'])
        self.assertEqual([len(n['children']) for n in nodes(result, 'form')], [1, 1, 1])

    def test_reference_annotated_counter_keeps_source_prefix_parent(self):
        result = parse_forms('<p>Phần II</p><p>2[7]. Hồ sơ</p><p>2.1. Yêu cầu</p><p>2.2. Trình tự</p>')
        self.assert_integrity(result)
        numbered = nodes(result, 'numbered_paragraph')
        self.assertEqual([n['number'] for n in numbered], ['2', '2.1', '2.2'])
        self.assertEqual([n.get('parent_number') for n in numbered], [None, '2', '2'])
        self.assertFalse(any(i['code'] == 'unresolved_decimal_prefix' for i in result['issues']))

    def test_single_decimal_counter_in_table_cell_remains_local(self):
        result = parse_forms('<p>Điều 1. Tiêu chí</p><table><tr><th>Nội dung</th><th>Kết quả</th></tr>'
                             '<tr><td><p>2.5. Cơ sở hạ tầng</p><p>Nội dung tiêu chí</p></td><td>Đạt</td></tr>'
                             '<tr><td><p>3.1.</p><p>Yêu cầu tiếp theo</p></td><td>Đạt</td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['2.5', '3.1'])
        self.assertFalse(nodes(result, 'clause'))
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_three_row_spanned_letterhead_has_source_layout_evidence(self):
        result = parse_forms('<table><tr><td rowspan="2"><p>ỦY BAN NHÂN DÂN</p><p>TỈNH AN BÌNH</p></td>'
                             '<td colspan="2">CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</td></tr>'
                             '<tr><td>Độc lập - Tự do - Hạnh phúc</td><td></td></tr>'
                             '<tr><td>Số:12/QĐ-UBND</td><td>Tỉnh, ngày24tháng04năm2026</td><td></td></tr></table>'
                             '<p>QUYẾT ĐỊNH</p><p>Điều 1. Nội dung</p>')
        self.assert_integrity(result)
        self.assertFalse(any(i['code'] == 'table_semantics_unresolved' for i in result['issues']))
        self.assertTrue(nodes(result, 'national_heading'))
        self.assertTrue(nodes(result, 'issuing_authority'))

    def test_alphanumeric_form_directory_preserves_label_value_pairs(self):
        result = parse_forms('<p>PHỤ LỤC</p><table><tr><td>Mẫu 1A</td><td>Bản khai cá nhân</td></tr>'
                             '<tr><td>Mẫu 3B-1</td><td>Bản khai thân nhân</td></tr></table>')
        self.assert_integrity(result)
        table = nodes(result, 'table')[0]
        self.assertEqual(table['table_kind'], 'key_value')
        self.assertFalse(nodes(result, 'form'))
        self.assertTrue(all(not c.get('header_refs') and not c.get('row_axis') and not c.get('column_axis')
                            for c in table['cells']))

    def test_long_numbered_form_component_before_table_is_instruction(self):
        caption = 'Kế hoạch sử dụng nguyên liệu trong nước và nhập khẩu để sản xuất sản phẩm tiêu thụ trong nước của doanh nghiệp trong năm tiếp theo'
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 5</p><p>9. ' + caption + '</p>'
                             '<table><tr><th>Sản phẩm</th><th>Số lượng</th></tr><tr><td>...</td><td>...</td></tr></table>')
        self.assert_integrity(result)
        fields = nodes(result, 'form_field')
        self.assertEqual(fields[0]['number'], '9')
        self.assertEqual(fields[0]['field_kind'], 'instruction')
        self.assertIsNone(fields[0]['value_text'])
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_terminal_bracket_notes_close_form_and_bound_quoted_counters(self):
        result = parse_forms('<p>Điều 1. Quy định[1]</p><p>Điều 2. Thực hiện[2]</p>'
                             '<p>PHỤ LỤC</p><p>Mẫu 06</p><p>Họ tên: ...</p><hr>'
                             '<p>[1] Nội dung được bổ sung như sau: “</p><p>1. Yêu cầu</p><p>2. Thực hiện.”</p>'
                             '<p>[2] Điều này được sửa đổi theo văn bản nguồn.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['marker'] for n in nodes(result, 'footnote')], ['1', '2'])
        form = nodes(result, 'form')[0]
        self.assertFalse(any(n['type'] == 'footnote' for n in form['children']))
        self.assertEqual(result['form_validation']['suspicious_value_text'], 0)
        self.assertFalse(any((n.get('text') or '').startswith('[1]') for n in nodes(result, 'form_field')))

    def test_unfamiliar_colon_prompts_before_form_inputs_keep_unknown_kind(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 4</p><p>Trụ sở tại:</p><p>Điện thoại: ...</p>'
                             '<p>Họ, tên các con:</p><p>... sinh: ...</p><p>Nhất trí xác nhận:</p><p>Ông (bà): ...</p>')
        self.assert_integrity(result)
        prompts = [n for n in nodes(result, 'form_field') if n.get('field_kind') == 'unknown']
        self.assertEqual([n['field_name'] for n in prompts], ['Trụ sở tại', 'Họ, tên các con', 'Nhất trí xác nhận'])
        self.assertTrue(all(n['value_text'] is None for n in prompts))
        self.assertEqual(result['form_validation']['unexplained_form_label_paragraphs'], 0)

    def test_verification_lead_in_before_form_input_remains_prose(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 2</p><p>Thông tin kiểm tra:</p><p>Họ tên: ...</p>')
        self.assert_integrity(result)
        self.assertTrue(any(n.get('text') == 'Thông tin kiểm tra:' for n in nodes(result, 'paragraph')))
        self.assertFalse(any(n.get('field_name') == 'Thông tin kiểm tra' for n in nodes(result, 'form_field')))

    def test_numbered_form_component_continues_after_previous_table(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu 4</p><p>8. Danh mục sản phẩm:</p>'
                             '<table><tr><td>Sản phẩm</td><td>...</td></tr></table>'
                             '<p>9. Kế hoạch sử dụng nguyên liệu trong năm tiếp theo</p>'
                             '<p>... xin cam kết thực hiện đúng quy định.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'form_field') if n.get('number')], ['8', '9'])
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_terminal_note_quote_continuations_remain_in_single_counter_scope(self):
        result = parse_forms('<p>Điều 1. Quy định[1]</p><p>Điều 2. Thực hiện[2]</p><hr>'
                             '<p>[1] Nội dung bổ sung như sau: “1. Yêu cầu</p><p>Văn bản bổ sung.</p>'
                             '<p>2. Thực hiện</p><p>Diễn giải tiếp.</p><p>3. Kết thúc.” theo nguồn.</p>'
                             '<p>[2] Chú giải nguồn tiếp theo.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['1', '2', '3'])
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_inline_quotation_close_retains_unquoted_source_suffix(self):
        result = parse_forms('<p>Điều 1. Sửa đổi</p><p>1. Sửa đổi nội dung như sau:</p>'
                             '<p>“1. Yêu cầu</p><p>2. Thi hành.” theo văn bản nguồn.</p><p>Điều 2. Hiệu lực</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['1', '2'])
        self.assertTrue(any(n.get('text') == 'theo văn bản nguồn.' for n in nodes(result, 'paragraph')))
        self.assertEqual([n['number'] for n in nodes(result, 'article')], ['1', '2'])

    def test_centered_attachment_note_is_not_attached_document_title(self):
        result = parse_forms('<p>Điều 1. Ban hành quy định</p><p>Điều 2. Thi hành</p>'
                             '<p align="center">QUY ĐỊNH</p><p align="center">Về hoạt động giám sát</p>'
                             '<p align="center">(Ban hành kèm theo Quyết định về giám sát</p>'
                             '<p align="center">của cơ quan có thẩm quyền)</p><p>Chương I</p><p>Điều 1. Phạm vi</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'document_title')], ['Về hoạt động giám sát'])
        self.assertTrue(any((n.get('text') or '').startswith('(Ban hành kèm theo') for n in nodes(result, 'paragraph')))

    def test_legacy_standard_letterhead_without_category_starts_new_scope(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN NGÀNH</p><p>22 TCN 100 - 02</p>'
                             '<p>1. Nội dung trước</p><p>1.1 Nhánh trước</p>'
                             '<table><tr><td><p align="center"><b>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</b></p>'
                             '<p align="center"><b>BỘ GIAO THÔNG VẬN TẢI</b></p></td>'
                             '<td><p align="center"><b>THIẾT BỊ ĐO - YÊU CẦU VÀ PHƯƠNG PHÁP THỬ</b></p></td>'
                             '<td><p align="center">22 TCN 101 - 2002</p></td></tr></table>'
                             '<p>1. Nội dung sau</p><p>1.1 Nhánh sau</p>')
        self.assert_integrity(result)
        scopes = [n for n in nodes(result, 'layout_block') if n.get('evidence') == 'source_technical_standard_scope']
        self.assertEqual(len(scopes), 2)
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['1', '1.1', '1', '1.1'])
        self.assertFalse(any(i['code'] == 'duplicate_source_outline_number' for i in result['issues']))

    def test_standard_identifier_with_national_heading_but_no_issuer_is_not_cover(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p>'
                             '<p>TCVN 1234:2001</p><p>NỘI DUNG THAM CHIẾU</p>')
        self.assert_integrity(result)
        self.assertFalse(any(n.get('evidence') == 'source_technical_standard_scope' for n in nodes(result, 'layout_block')))

    def test_technical_contents_counters_are_citations_before_actual_body(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p>TCVN 1234:2001</p>'
                             '<p align="center"><b>MỤC LỤC</b></p><p>1 Phạm vi áp dụng.</p><p>2 Phương pháp thử.</p>'
                             '<p>Phụ lục A Thiết bị.</p><p>Phụ lục B Mẫu.</p><p>Các hình vẽ.</p>'
                             '<p align="center">TCVN 1234:2001</p><p>1 Phạm vi áp dụng</p><p>1.1 Yêu cầu</p>'
                             '<p>2 Phương pháp thử</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['1', '2', 'A', 'B'])
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['1', '1.1', '2'])
        self.assertFalse(nodes(result, 'annex_heading'))
        self.assertFalse(any(i['code'] == 'duplicate_source_outline_number' for i in result['issues']))

    def test_figure_legend_lists_do_not_restart_technical_counter_scope(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p>TCVN 1234:2001</p>'
                             '<p>5. Thiết bị</p><p align="center"><img src="diagram.png"></p>'
                             '<p align="center">Hình 1. Thiết bị</p><p>1 - Thân</p><p>2 - Vỏ</p>'
                             '<p align="center"><img src="section.png"></p><p align="center">Mặt cắt A - A</p>'
                             '<p>1 - Ống</p><p>2 - Nắp</p><p>5.1 Yêu cầu</p>'
                             '<p align="center"><img src="explanation.png"></p><p><b>Giải thích</b></p>'
                             '<p>h - chiều cao</p><p>d - đường kính</p><p>1 - van</p><p>2 - nguồn</p>'
                             '<p align="center">Hình 2 - Phép thử</p><p>6. Thử nghiệm</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['1', '2', '1', '2', '1', '2'])
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['5', '5.1', '6'])
        self.assertFalse(any(i['code'] == 'duplicate_source_outline_number' for i in result['issues']))

    def test_unillustrated_technical_sections_do_not_become_figure_legend(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p>TCVN 1234:2001</p>'
                             '<p>1 - Phạm vi</p><p>2 - Yêu cầu</p><p>2.1 Thiết bị</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'list_item'))
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['1', '2', '2.1'])

    def test_compact_technical_annex_paths_keep_literal_parent_labels(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p>TCVN 1234:2001</p>'
                             '<p align="center">PHỤ LỤC B</p><p>B1 Thiết bị</p><p>B1.1 Yêu cầu</p>'
                             '<p>B1.1.1 Phương pháp</p><p>B2 Đo lường</p><p>B2.1 Điều kiện</p>')
        self.assert_integrity(result)
        items = nodes(result, 'numbered_paragraph')
        self.assertEqual([n['number'] for n in items], ['B1', 'B1.1', 'B1.1.1', 'B2', 'B2.1'])
        self.assertEqual([n.get('parent_number') for n in items], ['B', 'B1', 'B1.1', 'B', 'B2'])
        self.assertFalse(any(i['code'] == 'unresolved_counter_prefix' for i in result['issues']))

    def test_bare_technical_source_number_remains_ambiguous_text(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p>TCVN 1234:2001</p>'
                             '<p>3. Phương pháp</p><p>1</p><p>3.1 Thử nghiệm</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['3', '3.1'])
        self.assertTrue(any(n.get('text') == '1' for n in nodes(result, 'paragraph')))
        self.assertTrue(any(i['code'] == 'possible_page_number' for i in result['issues']))

    def test_technical_variable_subscripts_are_not_compact_appendix_counters(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p>TCVN 1234:2001</p>'
                             '<p>3. Thử nghiệm</p><p>P1 - tải trọng</p><p>v2 tốc độ</p>'
                             '<p align="center">PHỤ LỤC B</p><p>B1 Thiết bị</p><p>d1 - đường kính</p>'
                             '<p>B1.1 Yêu cầu</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['3', 'B1', 'B1.1'])
        self.assertFalse(any(i['code'] == 'unresolved_counter_prefix' for i in result['issues']))

    def test_technical_duplicate_displayed_number_is_retained_with_source_warning(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p align="center">TCVN 1234:2001</p>'
                             '<p>3. Định nghĩa</p><p>3.1 Nội dung</p><p>3. Tài liệu kỹ thuật</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['3', '3.1', '3'])
        self.assertTrue(any(i['code'] == 'duplicate_source_outline_number' for i in result['issues']))
        self.assertFalse(result['hierarchy_validation']['semantic_complete'])

    def test_technical_cited_paths_are_reference_list_not_missing_local_sections(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p align="center">TCVN 1234:2001</p>'
                             '<p align="center">PHỤ LỤC A</p><p>Thông tin theo tiêu chuẩn viện dẫn.</p>'
                             '<p>- Phần B.1, điều :</p><p>B.1.1.1</p><p>B.1.1.2</p>'
                             '<p>B.1.1.4 đến B.1.1.6</p><p>A.1 Nội dung phụ lục</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['B.1.1.1', 'B.1.1.2', 'B.1.1.4'])
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['A.1'])
        self.assertFalse(any(i['code'] == 'unresolved_counter_prefix' for i in result['issues']))
        self.assertEqual(nodes(result, 'list_item')[-1]['text'], 'đến B.1.1.6')

    def test_compact_article_citations_in_footer_do_not_start_provision_excerpt(self):
        result = parse_forms('<p>Điều1: Nội dung<a name="_ftnref1" href="#_ftn1">[1]</a></p><p>CHỦ TỊCH</p><p>Nguyễn Văn An</p>'
                             '<div><p><a name="_ftn1" href="#_ftnref1">[1]</a> Điều5 vàĐiều6của Quyết định số 12/QĐ được sửa đổi như sau:</p>'
                             '<p>Điều 5. Điều khoản chuyển tiếp</p><p>1. Yêu cầu</p><p>Điều 6. Hiệu lực</p><p>1. Thi hành</p></div>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['5', '1', '6', '1'])
        self.assertTrue(any((n.get('text') or '').startswith('Điều5 vàĐiều6của') for n in nodes(result, 'footnote') + nodes(result, 'paragraph')))

    def test_technical_source_superscript_notes_do_not_close_decimal_scope(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p align="center">TCVN 1234:2001</p>'
                             '<p>5. Thử nghiệm</p><p>5.3 Điều kiện</p><p>5.3.12 Nhiên liệu<sup>3)</sup></p>'
                             '<p><sup>3)</sup> Chú giải nguồn.</p><p>5.3.13 Điều kiện tiếp</p>')
        self.assert_integrity(result)
        self.assertEqual([n['marker'] for n in nodes(result, 'footnote')], ['3'])
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['5', '5.3', '5.3.12', '5.3.13'])
        self.assertFalse(any(i['code'] == 'unresolved_counter_prefix' for i in result['issues']))

    def test_technical_scalar_formula_and_digit_alphabet_leave_scope_active(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p align="center">TCVN 1234:2001</p>'
                             '<p>6. Điều kiện</p><p>6.2 Khí quyển</p><p>283 K ≤ T ≤ 310 K</p>'
                             '<p>0 ≤ Pa ≤ 0,05Pv</p><p align="center">1 2 3 4 5 6 7 8 9 0</p><p>6.3 Hệ số</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['6', '6.2', '6.3'])
        self.assertFalse(any(i['code'] == 'unresolved_counter_prefix' for i in result['issues']))

    def test_technical_unmatched_source_counter_does_not_close_actual_prefix(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p align="center">TCVN 1234:2001</p>'
                             '<p>7. Kiểm tra</p><p>7.3 Nội dung</p><p>7.3.2 Yêu cầu</p>'
                             '<p>3.2.6 Nhãn nguồn lệch</p><p>7.3.3.1 Thiếu cấp nguồn</p><p>7.4 Phần tiếp</p>')
        self.assert_integrity(result)
        self.assertEqual([i['details']['number'] for i in result['issues'] if i['code'] == 'unresolved_counter_prefix'], ['3.2.6', '7.3.3.1'])
        self.assertEqual(nodes(result, 'numbered_paragraph')[-1]['parent_number'], '7')

    def test_technical_spaced_alpha_counter_preserves_displayed_number(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p align="center">TCVN 1234:2001</p>'
                             '<p align="center">PHỤ LỤC E</p><p>E.2 Thiết bị</p>'
                             '<p>E .2.3 Thông số</p><p>E.2.3.1 Yêu cầu</p><p>E.2.4 Phần tiếp</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['E.2', 'E .2.3', 'E.2.3.1', 'E.2.4'])
        self.assertEqual(nodes(result, 'numbered_paragraph')[2]['parent_number'], 'E .2.3')
        self.assertFalse(any(i['code'] == 'unresolved_counter_prefix' for i in result['issues']))

    def test_technical_lettered_sublist_preserves_decimal_ancestor_scope(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p align="center">TCVN 1234:2001</p>'
                             '<p>3. Yêu cầu</p><p>3.3 Phương pháp</p><p>3.3.3 Các phép thử:</p>'
                             '<p>a) Phép thử đầu</p><p>b) Phép thử sau</p><p>3.4 Kiểm tra</p>')
        self.assert_integrity(result)
        self.assertFalse(any(i['code'] == 'unresolved_counter_prefix' for i in result['issues']))
        numbered = nodes(result, 'numbered_paragraph')
        self.assertEqual([n['number'] for n in numbered], ['3', '3.3', '3.3.3', 'a', 'b', '3.4'])
        self.assertEqual([n['number'] for n in numbered[2]['children']], ['a', 'b'])
        self.assertEqual(numbered[-1]['parent_number'], '3')

    def test_technical_subordinate_numeric_conditions_do_not_restart_standard(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p align="center">TCVN 1234:2001</p>'
                             '<p>5. Thử nghiệm</p><p>5.3 Điều kiện</p><p>5.3.2 Phương án</p>'
                             '<p>a) Phương án đầu</p><p>b) Phương án sau</p>'
                             '<p>1) Điều kiện đầu</p><p>Phần tiếp của điều kiện đầu.</p>'
                             '<p>2) Điều kiện sau</p><p>5.3.3 Phương án tiếp</p>')
        self.assert_integrity(result)
        self.assertFalse(any(i['code'] == 'unresolved_counter_prefix' for i in result['issues']))
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['1', '2'])
        numbered = nodes(result, 'numbered_paragraph')
        self.assertEqual(numbered[-1]['number'], '5.3.3')
        self.assertEqual(numbered[-1]['parent_number'], '5.3')
        second = next(n for n in numbered if n['number'] == 'b')
        self.assertTrue(any(n['type'] == 'layout_block' for n in second['children']))

    def test_technical_narrative_component_list_keeps_standard_section_scope(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p align="center">TCVN 1234:2001</p>'
                             '<p>2. Cấu tạo</p><p>Gồm các chi tiết sau đây:</p>'
                             '<p>1- Chi tiết đầu</p><p>2- Chi tiết sau</p>'
                             '<p>2.1 Yêu cầu</p><p>3. Phần sau</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['1', '2'])
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['2', '2.1', '3'])
        self.assertFalse(any(i['code'] == 'unresolved_counter_prefix' for i in result['issues']))

    def test_plain_cell_standard_cover_closes_previous_appendix_scope(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN NGÀNH</p><p align="center">22 TCN 100 - 02</p>'
                             '<p>1. Nội dung</p><p align="center">PHỤ LỤC A</p><p>(Quy định)</p>'
                             '<p>A.1 Nội dung phụ lục</p><p>A.2 Mục sau</p>'
                             '<table><tr><td>TIÊU CHUẨN VIỆT NAM</td></tr><tr><td>TCVN 1234:2001</td></tr></table>'
                             '<p>1. Nội dung tiêu chuẩn sau</p><p>1.1 Mục sau</p>')
        self.assert_integrity(result)
        self.assertTrue(result['hierarchy_validation']['order_valid'])
        self.assertEqual(len([n for n in nodes(result, 'layout_block')
                              if n.get('evidence') == 'source_technical_standard_scope']), 2)
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['1', 'A.1', 'A.2', '1', '1.1'])

    def test_explicit_missing_source_line_retains_text_and_quality_warning(self):
        result = parse_forms('<p>CHỈ THỊ</p><p>VỀ NỘI DUNG</p><p>1. Yêu cầu</p><p>(mất dòng)</p>')
        self.assert_integrity(result)
        self.assertTrue(any(n.get('text') == '(mất dòng)' for n in nodes(result, 'paragraph')))
        self.assertTrue(any(i['code'] == 'source_declared_missing_text' for i in result['issues']))
        self.assertFalse(result['hierarchy_validation']['semantic_complete'])

    def test_joint_resolution_type_heading_is_not_split_as_subject(self):
        result = parse_forms('<p>NGHỊ QUYẾT LIÊN TỊCH</p><p>VỀ PHỐI HỢP</p><p>Điều 1. Nội dung</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'document_type_heading')], ['NGHỊ QUYẾT LIÊN TỊCH'])
        self.assertEqual([n['text'] for n in nodes(result, 'document_title')], ['VỀ PHỐI HỢP'])

    def test_compound_counter_in_cell_keeps_its_displayed_prefix(self):
        result = parse_forms('<table><tr><th>Nhóm</th></tr><tr><td><p>1. Nhóm nguồn</p>'
                             '<p>1.1. Nhánh nguồn</p></td></tr></table>')
        self.assert_integrity(result)
        parent = nodes(result, 'numbered_paragraph')[0]
        self.assertEqual(parent['number'], '1')
        self.assertEqual(parent['children'][0]['number'], '1.1')
        self.assertEqual(parent['children'][0]['parent_number'], '1')
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_scalar_cell_quantity_does_not_become_compound_counter(self):
        result = parse_forms('<table><tr><th>Nhóm</th></tr><tr><td><p>1. Nhóm nguồn</p>'
                             '<p>1.500 kg</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['1'])

    def test_technical_heading_does_not_break_counter_source_intervals(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN NGÀNH</p><p align="center">22 TCN 100 - 02</p>'
                             '<p>4. Yêu cầu</p><p>4.1 Nội dung trước</p><p align="center">HÌNH MINH HỌA</p>'
                             '<p>4.2.Nội dung sau</p><p>5- Thử nghiệm</p><p>5.1 Phương pháp</p>')
        self.assert_integrity(result)
        counters = [n['number'] for n in nodes(result, 'numbered_paragraph')]
        self.assertEqual(counters, ['4', '4.1', '4.2', '5', '5.1'])
        self.assertTrue(result['hierarchy_validation']['order_valid'])

    def test_technical_missing_intermediate_prefix_is_not_invented(self):
        result = parse_forms('<p align="center">TIÊU CHUẨN VIỆT NAM</p><p align="center">TCVN 1234:2001</p>'
                             '<p>3. Nội dung</p><p>3.1.1 Nhánh thiếu cấp nguồn</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['3', '3.1.1'])
        self.assertEqual(nodes(result, 'numbered_paragraph')[1]['parent_number'], '3')
        self.assertTrue(any(i['code'] == 'unresolved_counter_prefix' for i in result['issues']))

    def test_source_declared_member_list_stays_local_inside_article(self):
        result = parse_forms('<p>Điều 1. Hội đồng gồm các thành viên sau đây:</p>'
                             '<p>1/ Ông Nguyễn Văn An, Chủ tịch;</p><p>2/ Bà Lê Thị Bình, Thành viên.</p>'
                             '<p>Điều 2. Nhiệm vụ</p><p>1. Nhiệm vụ đầu.</p><p>2. Nhiệm vụ sau.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'clause')], ['1', '2'])
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['1', '2'])

    def test_source_supported_single_dash_under_local_lead_in(self):
        result = parse_forms('<p>CHỈ THỊ</p><p>1. Nội dung:</p><p>- Yêu cầu duy nhất.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'list_item')], ['Yêu cầu duy nhất.'])

    def test_national_motto_keeps_decorative_suffix_as_source_text(self):
        text = 'Độc lập - Tự do - Hạnh phúc----------------'
        result = parse_forms('<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>' + text + '</p><p>THÔNG TƯ</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'national_motto')], [text])

    def test_qualified_bank_signer_title_and_status_keep_source_slices(self):
        result = parse_forms('<p>Điều 1. Nội dung</p>'
                             '<p>TỔNG GIÁM ĐỐC NGÂN HÀNG NHÀ NƯỚC (Đã ký)</p><p>Nguyễn Văn An</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['TỔNG GIÁM ĐỐC NGÂN HÀNG NHÀ NƯỚC'])
        self.assertEqual([n['text'] for n in nodes(result, 'signature_status')], ['(Đã ký)'])

    def test_split_table_caption_is_heading_without_invented_axes(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p align="center">BẢNG TỔNG HỢP</p>'
                             '<p align="center">KHỐI LƯỢNG CÔNG TRÌNH</p><table><tr><td>X</td><td>7</td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'heading')], ['BẢNG TỔNG HỢP', 'KHỐI LƯỢNG CÔNG TRÌNH'])
        self.assertEqual(nodes(result, 'table')[0]['table_kind'], 'ambiguous')

    def test_attached_standards_have_separate_local_counter_and_appendix_scopes(self):
        result = parse_forms('<p>Điều 1. Danh mục</p><p>THỨ TRƯỞNG</p><p>Nguyễn Văn An</p>'
                             '<p align="center">DANH MỤC</p>'
                             '<p align="center">CÁC TIÊU CHUẨN (Ban hành kèm theo Quyết định số 12/QĐ)</p>'
                             '<table><tr><th>Mã</th></tr><tr><td>TCVN 1234:2001</td></tr></table>'
                             '<p align="center">TIÊU CHUẨN NGÀNH</p><p align="center">22 TCN 100 - 02</p>'
                             '<p>1. Phạm vi</p><p>1.1 Nội dung đầu</p><p>1.1.1 Nội dung sâu</p>'
                             '<p>Phụ lục A cho biết các thông số.</p>'
                             '<p align="center">PHỤ LỤC A</p><p>1. Nội dung phụ lục</p>'
                             '<p align="center">TIÊU CHUẨN VIỆT NAM</p><p align="center">TCVN 5678:2003</p>'
                             '<p>1 Phạm vi sau</p><p>1.1 Nội dung sau</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'article')), 1)
        self.assertFalse(nodes(result, 'clause'))
        self.assertFalse(nodes(result, 'point'))
        scopes = [n for n in nodes(result, 'layout_block')
                  if n.get('evidence') == 'source_technical_standard_scope']
        self.assertEqual(len(scopes), 2)
        self.assertEqual([n['number'] for n in scopes[0]['children'] if n['type'] == 'numbered_paragraph'], ['1'])
        self.assertEqual([n['number'] for n in scopes[1]['children'] if n['type'] == 'numbered_paragraph'], ['1'])
        first = next(n for n in scopes[0]['children'] if n['type'] == 'numbered_paragraph')
        self.assertEqual(first['children'][0]['number'], '1.1')
        self.assertEqual(first['children'][0]['children'][0]['number'], '1.1.1')
        self.assertEqual([n['number'] for n in nodes(result, 'annex_heading')], ['A'])
        self.assertFalse(nodes(result, 'annex'))
        self.assertFalse(any(i['code'] == 'duplicate_legal_number' for i in result['issues']))

    def test_nested_table_standard_cover_keeps_physical_geometry_and_local_scope(self):
        result = parse_forms('<p>Điều 1. Nội dung</p>'
                             '<table><tr><td><table><tr><td>'
                             '<p align="center">TIÊU CHUẨN VIỆT NAM</p>'
                             '<p align="center">TCVN 1234:2001</p></td></tr></table></td></tr></table>'
                             '<p>1. Phạm vi</p><p>1.1 Yêu cầu</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'table')), 2)
        self.assertFalse(nodes(result, 'clause'))
        self.assertTrue(any(n.get('evidence') == 'source_technical_standard_scope'
                            for n in nodes(result, 'layout_block')))
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['1', '1.1'])

    def test_technical_reference_in_prose_does_not_create_standard_scope(self):
        result = parse_forms('<p>Điều 1. Nội dung</p>'
                             '<p>Áp dụng TIÊU CHUẨN VIỆT NAM TCVN 1234:2001.</p><p>1. Khoản</p>')
        self.assert_integrity(result)
        self.assertFalse(any(n.get('evidence') == 'source_technical_standard_scope'
                             for n in nodes(result, 'layout_block')))
        self.assertEqual(len(nodes(result, 'clause')), 1)

    def test_compact_explicit_article_label_keeps_literal_source_label(self):
        result = parse_forms('<p>Điều1: Nội dung</p><p>Điều 2. Sau</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'article')], ['1', '2'])
        self.assertEqual(nodes(result, 'article')[0]['label'], 'Điều1')

    def test_declared_article_with_malformed_word_preserves_source_label(self):
        result = parse_forms('<p>Điều 1. Trước</p><p class="prov-article">Articl 2. Sau</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'article')], ['1', '2'])
        self.assertEqual(nodes(result, 'article')[1]['label'], 'Articl 2')
        self.assertTrue(any(i['code'] == 'source_structural_label_conflict' for i in result['issues']))

    def test_leading_named_act_citation_is_prose_not_an_article(self):
        result = parse_forms('<p>THÔNG TƯ</p><p><b>I. GIẢI THÍCH</b></p><p>1. Nội dung:</p>'
                             '<p>Điều 4 Sắc lệnh 168 ghi rõ là: "Nội dung nguồn".</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'article'))

    def test_legacy_proposal_and_enactment_are_distinct_opening_roles(self):
        result = parse_forms('<p align="center">LUẬT</p><p align="center">VỀ TỔ CHỨC</p>'
                             '<p>Chiểu đề nghị của Bộ trưởng;</p>'
                             '<p>Chiểu sắc lệnh về tổ chức;</p><p>Nay ra luật về tổ chức như sau:</p>'
                             '<p>Điều 1. Nội dung</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'proposal_basis')], ['Chiểu đề nghị của Bộ trưởng;'])
        self.assertEqual([n['text'] for n in nodes(result, 'legal_basis')], ['Chiểu sắc lệnh về tổ chức;'])
        self.assertEqual([n['text'] for n in nodes(result, 'enacting_formula')], ['Nay ra luật về tổ chức như sau:'])

    def test_promulgated_act_heading_after_explicit_full_text_lead_in(self):
        result = parse_forms('<p align="center">SẮC LỆNH</p><p align="center">RA SẮC LỆNH:</p>'
                             '<p>Nay ban bố luật đã được biểu quyết; nguyên văn như sau:</p>'
                             '<p align="center">LUẬT</p><p align="center">VỀ TỔ CHỨC</p>'
                             '<p>Để quy định tổ chức.</p><p>Nay ra luật về tổ chức như sau:</p>'
                             '<p>Chương I. Quy định chung</p>'
                             '<p>Điều 1. Nội dung</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'document_type_heading')], ['SẮC LỆNH', 'LUẬT'])
        self.assertEqual([n['text'] for n in nodes(result, 'document_title')], ['VỀ TỔ CHỨC'])
        self.assertEqual(len(nodes(result, 'article')), 1)
        self.assertEqual(len(nodes(result, 'enacting_formula')), 1)
        self.assertEqual([n['text'] for n in nodes(result, 'heading')
                          if n.get('evidence') == 'source_embedded_enacting_formula'],
                         ['Nay ra luật về tổ chức như sau:'])
        self.assertTrue(any(n.get('evidence') == 'attached_legal_act_header'
                            for n in nodes(result, 'layout_block')))

    def test_unintroduced_body_type_word_does_not_create_attached_act(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p align="center">LUẬT</p>'
                             '<p>Từ xuất hiện trong nội dung nguồn.</p>')
        self.assert_integrity(result)
        self.assertFalse(any(n.get('evidence') == 'attached_legal_act_header'
                             for n in nodes(result, 'layout_block')))

    def test_declared_unusual_clause_counter_exits_previous_local_list(self):
        result = parse_forms('<p>Điều 4. Giải thích</p><p>6. Nội dung:</p>'
                             '<p>- Một nội dung.</p><p>- Nội dung khác.</p>'
                             '<p class="prov-clause">7.14<a href="#">[14]</a>Khái niệm nguồn.</p>'
                             '<p>8. Khái niệm sau.</p>')
        self.assert_integrity(result)
        self.assertIn('7.14', [n['number'] for n in nodes(result, 'clause')])
        self.assertEqual(result['hierarchy_validation']['unresolved']['numbered_candidates'], 0)

    def test_declared_clause_retains_unusual_literal_counter_with_warning(self):
        result = parse_forms('<p>Điều 4. Giải thích</p><p>6. Khái niệm trước.</p>'
                             '<p class="prov-clause">7.14<a href="#">[14]</a>Khái niệm nguồn.</p>'
                             '<p>8. Khái niệm sau.</p>')
        self.assert_integrity(result)
        clauses = nodes(result, 'clause')
        self.assertEqual([n['number'] for n in clauses], ['6', '7.14', '8'])
        self.assertEqual(clauses[1]['label'], '7.14')
        self.assertFalse(result['hierarchy_validation']['semantic_complete'])
        self.assertTrue(any(i['code'] == 'source_counter_role_conflict' for i in result['issues']))
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_untyped_undelimited_decimal_does_not_invent_clause(self):
        result = parse_forms('<p>Điều 4. Giải thích</p><p>7.14[14]Khái niệm chưa rõ.</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'clause'))
        self.assertTrue(any(n.get('text') == '7.14[14]Khái niệm chưa rõ.' for n in nodes(result, 'paragraph')))

    def test_compound_local_counter_children_stay_under_literal_prefix(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>1. Nhóm:</p><p>a) Chủ đề:</p>'
                             '<p>a.1. Nhánh đầu:</p><p>- Yêu cầu đầu.</p><p>- Yêu cầu sau.</p>'
                             '<p>a.2. Nhánh sau:</p><p>Diễn giải của nhánh sau.</p><p>b) Chủ đề khác.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'point')], ['a', 'b'])
        parent = nodes(result, 'point')[0]
        local = [n for n in parent['children'] if n['type'] == 'numbered_paragraph']
        self.assertEqual([n['number'] for n in local], ['a.1', 'a.2'])
        self.assertTrue(any(n['type'] == 'list' for n in local[0]['children']))
        self.assertTrue(any(n.get('text') == 'Diễn giải của nhánh sau.' for n in local[1]['children']))
        self.assertFalse(any(i['code'] == 'duplicate_legal_number' for i in result['issues']))

    def test_decimal_outline_owns_compound_children_and_continuations(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>3. Nhóm:</p><p>3.4. Chủ đề:</p>'
                             '<p>a) Nhánh:</p><p>a.1. Mục:</p><p>a.1.1. Mục sâu:</p>'
                             '<p>Diễn giải sâu.</p><p>a.2. Mục sau.</p><p>b) Nhánh sau.</p>'
                             '<p>4. Khoản kế tiếp.</p>')
        self.assert_integrity(result)
        local = {n['number']: n for n in nodes(result, 'numbered_paragraph')}
        self.assertEqual([n['number'] for n in local['3.4']['children']], ['a', 'b'])
        self.assertEqual([n['number'] for n in local['a']['children']], ['a.1', 'a.2'])
        self.assertEqual(local['a.1']['children'][0]['number'], 'a.1.1')
        self.assertEqual(local['a.1.1']['children'][0]['text'], 'Diễn giải sâu.')
        self.assertEqual([n['number'] for n in nodes(result, 'clause')], ['3', '4'])
        self.assertFalse(nodes(result, 'point'))

    def test_article_free_compound_counter_retains_real_prefix(self):
        result = parse_forms('<p>CHỈ THỊ</p><p>a) Chủ đề:</p><p>a.1. Mục đầu.</p><p>a.2. Mục sau.</p>')
        self.assert_integrity(result)
        local = {n['number']: n for n in nodes(result, 'numbered_paragraph')}
        self.assertEqual([n['number'] for n in local['a']['children']], ['a.1', 'a.2'])
        self.assertFalse(nodes(result, 'point'))

    def test_missing_compound_prefix_is_preserved_without_invented_parent(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>a.2. Mục không có cha nguồn.</p>')
        self.assert_integrity(result)
        self.assertEqual(nodes(result, 'numbered_paragraph')[0]['number'], 'a.2')
        self.assertFalse(nodes(result, 'point'))
        self.assertTrue(any(i['code'] == 'unresolved_counter_prefix' for i in result['issues']))

    def test_space_after_alpha_dot_still_supplies_legal_point(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>1. Khoản</p><p>a. 1. Nội dung điểm.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'point')], ['a'])
        self.assertFalse(any(n.get('number') == 'a.1' for n in nodes(result, 'numbered_paragraph')))

    def test_adjacent_national_header_motto_are_literal_source_slices(self):
        text = 'CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAMĐộc lập - Tự do - Hạnh phúc'
        boundary = text.index('Độc')
        result = parse_forms('<p>' + text + '</p><p>THÔNG TƯ</p><p>Điều 1. Nội dung</p>')
        self.assert_integrity(result)
        self.assertEqual(nodes(result, 'national_heading')[0]['text'], text[:boundary])
        self.assertEqual(nodes(result, 'national_motto')[0]['text'], text[boundary:])
        self.assertEqual(nodes(result, 'national_motto')[0]['source_offset'], boundary)

    def test_english_chair_signing_scope_preserves_uppercase_person(self):
        result = parse_forms('<p>Article 1. Scope</p><p>On behalf of the National Assembly Standing Committee</p>'
                             '<p>Chairman</p><p>TRAN VAN AN</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['Chairman'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['TRAN VAN AN'])

    def test_chairman_implementation_prose_remains_body(self):
        result = parse_forms('<p>Article 1. Implementation</p><p>Chairman shall direct implementation.</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'signature'))

    def test_legacy_chair_authority_is_distinct_from_document_title(self):
        result = parse_forms('<p>QUYẾT ĐỊNH</p><p>VỀ TIÊU CHUẨN</p>'
                             '<p>CHỦ NHIỆM UỶ BAN KHOA HỌC NHÀ NƯỚC</p>'
                             '<p>Căn cứ Luật;</p><p>Điều 1. Nội dung</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'issuing_authority_title')],
                         ['CHỦ NHIỆM UỶ BAN KHOA HỌC NHÀ NƯỚC'])
        self.assertEqual([n['text'] for n in nodes(result, 'document_title')], ['VỀ TIÊU CHUẨN'])

    def test_issuer_prefixed_numbered_subject_is_document_title(self):
        title = 'HỘI ĐỒNG BỘ TRƯỞNG SỐ 12/CT NGÀY 3-5-1982 VỀ VIỆC QUẢN LÝ VẬT TƯ'
        result = parse_forms('<p>THÔNG TƯ</p><p>' + title + '</p><p>1. Nội dung đầu.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'document_title')], [title])
        self.assertFalse(nodes(result, 'issuing_authority_title'))

    def test_legacy_enactment_opening_roles_preserve_source(self):
        result = parse_forms('<p>SẮC LỆNH</p><p>SỐ 12/SL NGÀY 2 THÁNG 3 NĂM 1948</p>'
                             '<p>CHỦ TỊCH CHÍNH PHỦ</p><p>Chiểu sắc lệnh số 10-SL;</p>'
                             '<p>RA SẮC LỆNH:</p><p>Điều 1</p><p>Nội dung nguồn.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'document_type_heading')], ['SẮC LỆNH'])
        self.assertEqual([n['text'] for n in nodes(result, 'legal_basis')], ['Chiểu sắc lệnh số 10-SL;'])
        self.assertEqual([n['text'] for n in nodes(result, 'enacting_formula')], ['RA SẮC LỆNH:'])

    def test_legacy_authority_prefixes_and_wrapped_fragments_keep_header_scope(self):
        for prefix, fragment in [('UBND TỈNH LÂM', 'ĐỒNG'), ('HỘI ĐỒNG CHÍNH', 'PHỦ')]:
            result = parse_forms('<table><tr><td><p align="center"><b>' + prefix + '</b></p>'
                                 '<p align="center"><b>' + fragment + '</b></p></td><td>'
                                 '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p>'
                                 '</td></tr></table><p>QUYẾT ĐỊNH</p><p>Điều 1. Nội dung</p>')
            self.assert_integrity(result)
            self.assertEqual([n['text'] for n in nodes(result, 'issuing_authority')], [prefix, fragment])

    def test_joint_organizational_authority_prefix_keeps_actual_header(self):
        text = 'BAN TỔ CHỨC-CÁN BỘ CHÍNH PHỦ-UỶ BAN BẢO VỆ VÀ CHĂM SÓC TRẺ EM VIỆT NAM'
        result = parse_forms('<p><b>' + text + '</b></p><p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p>'
                             '<p>THÔNG TƯ LIÊN TỊCH</p><p>Điều 1. Nội dung</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'issuing_authority')], [text])

    def test_emphasized_local_heading_fragments_keep_outline_scope(self):
        result = parse_forms('<p>NGHỊ QUYẾT</p><p><b>I. NỘI DUNG VỀ SẢN XUẤT NÔNG</b></p>'
                             '<p><b>NGHIỆP.</b></p><p>1. Nội dung đầu.</p>'
                             '<p><b>II. NỘI DUNG VỀ QUẢN LÝ TÀI</b></p><p><b>CHÍNH.</b></p><p>1. Nội dung sau.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'heading')], ['NGHIỆP.', 'CHÍNH.'])
        self.assertFalse(nodes(result, 'article'))

    def test_alpha_local_heading_fragments_keep_outline_scope(self):
        result = parse_forms('<p>THÔNG TƯ</p><p><b>A. NỘI DUNG VỀ SẢN XUẤT NÔNG</b></p>'
                             '<p><b>NGHIỆP.</b></p><p>1. Nội dung đầu.</p>'
                             '<p><b>B. NỘI DUNG VỀ QUẢN LÝ TÀI</b></p><p><b>CHÍNH.</b></p><p>1. Nội dung sau.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'heading')], ['NGHIỆP.', 'CHÍNH.'])
        self.assertFalse(nodes(result, 'article'))

    def test_case_varied_signing_title_retains_role_before_status(self):
        for title in ['Chủ tịch', 'Phó Chủ tịch']:
            result = parse_forms('<p>Điều 1. Nội dung</p><p>' + title +
                                 '</p><p>(Đã ký)</p><p>Nguyễn Văn An</p>')
            self.assert_integrity(result)
            self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], [title])

    def test_minister_implementation_sentence_does_not_start_signing(self):
        text = 'Bộ trưởng Bộ Nội vụ, Bộ trưởng Bộ Quốc phòng chịu trách nhiệm hướng dẫn, kiểm tra việc thi hành Nghị định này'
        result = parse_forms('<p>Điều 1. Thi hành</p><p>' + text + '</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'signature'))
        self.assertTrue(any(n.get('text') == text for n in nodes(result, 'paragraph')))

    def test_roman_heading_case_variation_uses_restarting_child_evidence(self):
        result = parse_forms('<p>DIRECTIVE</p><p>I. FIRST GROUP</p><p>1. First requirement.</p>'
                             '<p>II. REVising EXISTING DOCUMENTS</p><p>1. Second requirement.</p>'
                             '<p>III. FINAL GROUP</p><p>1. Final requirement.</p>')
        self.assert_integrity(result)
        self.assertTrue(any(n.get('number') == 'II' for n in nodes(result, 'list_item')))
        self.assertFalse(any(n.get('text') == 'II. REVising EXISTING DOCUMENTS' for n in nodes(result, 'paragraph')))

    def test_source_parent_scope_preserves_isolated_dash_markers(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p parent-id="group">- Quyền lợi đầu.</p>'
                             '<p parent-id="group">Chi tiết quyền lợi đầu.</p>'
                             '<p parent-id="group">- Quyền lợi sau.</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'list_item')), 2)
        self.assertFalse(nodes(result, 'list_item')[0]['children'])
        self.assertTrue(any(n.get('text') == 'Chi tiết quyền lợi đầu.' for n in nodes(result, 'paragraph')))

    def test_different_source_parent_does_not_absorb_dash_continuations(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p parent-id="a">- Quyền lợi đầu.</p>'
                             '<p parent-id="b">Nội dung độc lập.</p><p parent-id="a">- Quyền lợi sau.</p>')
        self.assert_integrity(result)
        self.assertTrue(any(n.get('text') == 'Nội dung độc lập.' for n in nodes(result, 'paragraph')))

    def test_uppercase_title_continuation_stays_before_preamble(self):
        continuation = 'NỘI DUNG TIẾP THEO CỦA TIÊU ĐỀ VỀ CHÍNH SÁCH ÁP DỤNG CHO NGƯỜI LAO ĐỘNG TRONG CÁC NGÀNH NGHỀ VÀ CÁC ĐỊA PHƯƠNG TRÊN TOÀN QUỐC'
        result = parse_forms('<p>QUYẾT ĐỊNH</p><p align="center">VỀ CHÍNH SÁCH</p><p>' +
                             continuation + '</p><p>HỘI ĐỒNG CHÍNH PHỦ</p>'
                             '<p>Căn cứ văn bản hiện hành;</p><p>Điều 1. Nội dung</p>')
        self.assert_integrity(result)
        self.assertTrue(any(n.get('text') == continuation for n in nodes(result, 'document_title')))
        self.assertTrue(nodes(result, 'preamble'))

    def test_historical_and_compact_literal_national_headers_preserve_text(self):
        for text in ['VIỆT NAM DÂN CHỦ CỘNG HÒA', 'CỘNG HÒA XÃ HỘI CHỦNGHĨA VIỆT NAM']:
            result = parse_forms('<p>HỘI ĐỒNG CHÍNH PHỦ</p><p>' + text + '</p><p>QUYẾT ĐỊNH</p><p>Điều 1. Nội dung</p>')
            self.assert_integrity(result)
            self.assertEqual([n['text'] for n in nodes(result, 'national_heading')], [text])

    def test_compact_signed_status_after_layout_line_break_is_split(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><table><tr><td><p>TM. CHÍNH PHỦ<br>'
                             'BỘ TRƯỞNG PHỦ THỦ TƯỚNG<br>(Đã ký)</p><p>Nguyễn Văn An</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['BỘ TRƯỞNG PHỦ THỦ TƯỚNG'])
        self.assertEqual([n['text'] for n in nodes(result, 'signature_status')], ['(Đã ký)'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn An'])

    def test_article_free_outline_stops_before_name_with_signed_evidence(self):
        result = parse_forms('<p>NGHỊ QUYẾT</p><p><b>I- NỘI DUNG ĐẦU</b></p><p>1. Phần đầu.</p>'
                             '<p><b>II- NỘI DUNG SAU</b></p><p>1. Phần sau.</p>'
                             '<p><b>Nguyễn Văn An</b></p><p>(Đã ký)</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn An'])
        self.assertEqual(len(nodes(result, 'closing')), 1)
        self.assertFalse(nodes(result, 'article'))

    def test_compact_delegation_and_signed_status_preserve_person(self):
        title = 'T.M. VÀ THỪA ỦY NHIỆM CỦA HỘI ĐỒNG CHÍNH PHỦ BỘ TRƯỞNG PHỦ THỦ TƯỚNG'
        result = parse_forms('<p>Điều 1. Nội dung</p><table><tr><td><p>' + title +
                             '(Đã ký)</p><p>Nguyễn Văn An</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'delegation_title')], [title])
        self.assertEqual([n['text'] for n in nodes(result, 'signature_status')], ['(Đã ký)'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn An'])
        self.assertFalse(nodes(result, 'signer_title'))

    def test_prose_with_parenthetical_signed_status_is_not_split(self):
        text = 'Bản sao chứng nhận văn bản (Đã ký)'
        result = parse_forms('<p>Điều 1. Nội dung</p><p>' + text + '</p>')
        self.assert_integrity(result)
        self.assertTrue(any(n.get('text') == text for n in nodes(result, 'paragraph')))
        self.assertFalse(nodes(result, 'signature_status'))

    def test_qualified_signing_roles_are_titles_rather_than_names(self):
        for title in ['THỨ TRƯỞNG THỨ NHẤT', 'QUYỀN THỦ TƯỚNG CHÍNH PHỦ', 'CHỦ TỊCH ỦY BAN NHÂN DÂN']:
            with self.subTest(title=title):
                result = parse_forms('<p>Điều 1. Nội dung</p><p>KT. BỘ TRƯỞNG</p><p>' + title +
                                     '</p><p>(Đã ký)</p><p>Nguyễn Văn An</p>')
                self.assert_integrity(result)
                self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], [title])
                self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn An'])

    def test_attached_letterhead_does_not_start_at_previous_signed_title(self):
        result = parse_forms('<p>Điều 1. Ban hành</p><p>Điều 2. Thi hành</p>'
                             '<p>TM. ỦY BAN NHÂN DÂN</p>'
                             '<p><b>CHỦ TỊCH</b></p><p>(Đã ký)</p><p>Nguyễn Văn An</p>'
                             '<table><tr><td><p><b>HỘI ĐỒNG NHÂN DÂN</b></p></td>'
                             '<td><p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p>'
                             '<p>Độc lập - Tự do - Hạnh phúc</p></td></tr></table>'
                             '<p><b>QUY ĐỊNH</b></p><p>(Ban hành kèm theo quyết định trên)</p>'
                             '<p>Điều 1. Phạm vi</p><p>Điều 2. Nội dung</p>')
        self.assert_integrity(result)
        wrappers = [n for n in nodes(result, 'layout_block') if n.get('evidence') == 'attached_legal_act_header']
        self.assertEqual(wrappers[0]['children'][0]['text'], 'HỘI ĐỒNG NHÂN DÂN')
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn An'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['CHỦ TỊCH'])
        self.assertEqual(len(nodes(result, 'article')), 4)

    def test_annex_reference_marker_keeps_number_and_boundary(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p><b>Phụ lục số 01</b></p>'
                             '<p><b>BẢNG MỨC HƯỞNG</b></p><p>Nội dung phụ lục đầu.</p>'
                             '<p><b>Phụ lục số 02</b><a href="#fn12">[12]</a></p>'
                             '<p><b>BIỂU BÁO CÁO</b></p><p>Nội dung phụ lục sau.</p>')
        self.assert_integrity(result)
        annexes = nodes(result, 'annex')
        self.assertEqual([a['number'] for a in annexes], ['01', '02'])
        self.assertEqual(annexes[1]['label'], 'Phụ lục số 02[12]')
        self.assertEqual(annexes[1]['title'], 'BIỂU BÁO CÁO')
        self.assertEqual(annexes[1]['references'][0]['href'], '#fn12')

    def test_annex_reference_in_prose_does_not_start_an_annex(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>Phụ lục số 02[12] của hợp đồng còn hiệu lực.</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'annex'))

    def test_compound_form_national_header_does_not_become_form_title(self):
        result = parse_forms('<p>PHỤ LỤC</p><p>Mẫu số 01</p>'
                             '<p align="center">CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM<br>'
                             'Độc lập - Tự do - Hạnh phúc<br>---------------</p>'
                             '<p align="center"><b>ĐƠN ĐỀ NGHỊ</b></p><p>Họ tên: ............</p>')
        self.assert_integrity(result)
        self.assertEqual(nodes(result, 'form')[0]['title'], 'ĐƠN ĐỀ NGHỊ')
        self.assertEqual([n['text'] for n in nodes(result, 'national_heading')],
                         ['CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM'])
        self.assertEqual([n['text'] for n in nodes(result, 'national_motto')], ['Độc lập - Tự do - Hạnh phúc'])
        self.assertEqual(len(nodes(result, 'form_header')), 1)

    def test_split_authorities_keep_separate_delegated_signatures(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>KT. BỘ TRƯỞNG</p><p>BỘ CÔNG AN</p>'
                             '<p>THỨ TRƯỞNG</p><p>Trung tướng Nguyễn Văn An</p>'
                             '<p>KT. BỘ TRƯỞNG</p><p>BỘ TƯ PHÁP</p><p>THỨ TRƯỞNG</p><p>Lê Văn Bình</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'signature')), 2)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')],
                         ['Trung tướng Nguyễn Văn An', 'Lê Văn Bình'])
        self.assertEqual([n['text'] for n in nodes(result, 'paragraph') if n.get('text', '').startswith('BỘ ')],
                         ['BỘ CÔNG AN', 'BỘ TƯ PHÁP'])

    def test_compact_signer_title_and_status_keep_distinct_source_roles(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><table><tr><td>'
                             '<p>THỦ TƯỚNG(Đã ký)</p><p>Nguyễn Văn An</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['THỦ TƯỚNG'])
        self.assertEqual([n['text'] for n in nodes(result, 'signature_status')], ['(Đã ký)'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn An'])

    def test_capitalized_status_before_signed_marker_is_not_inferred_as_name(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>CHỜ XÁC NHẬN</p><p>(Đã ký)</p>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'signer_name'))
        self.assertTrue(any(n.get('text') == 'CHỜ XÁC NHẬN' for n in nodes(result, 'paragraph')))

    def test_name_before_signed_status_starts_closing_without_invented_title(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p>Trần Văn An</p><p>(Đã ký)</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Trần Văn An'])
        self.assertEqual(len(nodes(result, 'closing')), 1)
        self.assertFalse(nodes(result, 'signer_title'))

    def test_academic_qualifiers_preserved_in_evidenced_signer_name(self):
        for name in ['PGS. TS. Nguyễn Văn Bình', 'Gs.Ts Kh. Nguyễn Văn Bình', 'Trung tướng Nguyễn Văn Bình']:
            with self.subTest(name=name):
                result = parse_forms('<p>Điều 1. Nội dung</p><table><tr><td>'
                                     '<p>KT. TỔNG CỤC TRƯỞNG</p><p>PHÓ TỔNG CỤC TRƯỞNG</p>'
                                     '<p>(Đã ký)</p><p>' + name + '</p></td></tr></table>')
                self.assert_integrity(result)
                self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], [name])
                self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['PHÓ TỔNG CỤC TRƯỞNG'])

    def test_calculations_continue_a_repeated_dash_list_without_absorbing_prose(self):
        result = parse_forms('<p>Điều 1. Cách tính</p><p>Các giai đoạn:</p>'
                             '<p>- Giai đoạn đầu có hệ số 2,</p><p>100.000 đồng x 2 = 200.000 đồng.</p>'
                             '<p>- Giai đoạn sau có hệ số 3,</p><p>100.000 đồng x 3 = 300.000 đồng.</p>'
                             '<p>Đoạn giải thích độc lập sau danh sách.</p>')
        self.assert_integrity(result)
        items = nodes(result, 'list_item')
        self.assertEqual(len(items), 2)
        self.assertEqual([[c['text'] for c in n['children']] for n in items],
                         [['100.000 đồng x 2 = 200.000 đồng.'], ['100.000 đồng x 3 = 300.000 đồng.']])
        self.assertFalse(any(c.get('text', '').startswith('Đoạn giải thích') for n in items for c in n['children']))

    def test_signing_note_before_delegation_is_not_a_person_name(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><table><tr><td>'
                             '<p>THOẢ THUẬN</p><p>KT. BỘ TRƯỞNG BỘ NỘI VỤ</p>'
                             '<p>THỨ TRƯỞNG</p><p>(Đã ký)</p><p>Nguyễn Văn An</p>'
                             '</td><td><p>KT. BỘ TRƯỞNG BỘ TÀI CHÍNH</p>'
                             '<p>THỨ TRƯỞNG</p><p>(Đã ký)</p><p>Lê Văn Bình</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn An', 'Lê Văn Bình'])
        self.assertTrue(any(n.get('text') == 'THOẢ THUẬN' for n in nodes(result, 'paragraph')))
        self.assertEqual(len(nodes(result, 'delegation_title')), 2)

    def test_dotted_year_identifier_preserves_source_punctuation(self):
        from vietnam_legal_rag.ingestion.html.structure import document_number_roles
        self.assertEqual(document_number_roles('Nghị quyết số 17.2020.NQ-HĐND về nhiệm vụ'),
                         {'primary_document_number_candidate': '17.2020.NQ-HĐND',
                          'mentioned_document_numbers': []})
        from tests.support import metadata_tab
        result = metadata_tab('<div class="ant-card-body">Văn bản liên quan (1)<ul>'
                              '<li><a>Nghị quyết số 17.2020.NQ-HĐND về nhiệm vụ</a></li></ul></div>', 'relations')
        item = result['groups'][0]['items'][0]
        self.assertEqual(item['primary_document_number_candidate'], '17.2020.NQ-HĐND')
        self.assertFalse(item.get('url'))

    def test_decimal_quantities_do_not_become_document_identifiers(self):
        from vietnam_legal_rag.ingestion.html.structure import document_numbers
        self.assertEqual(document_numbers('17.2020.12 triệu đồng; 3.14; 12.500.000 đồng'), [])

    def test_long_addressee_table_keeps_local_recipient_scope(self):
        recipients = [f'- Các cơ quan phụ trách lĩnh vực số {i} tại các địa phương.' for i in range(8)]
        result = parse_forms('<table><tr><td>Kính gửi:</td><td>' +
                             ''.join('<p>' + text + '</p>' for text in recipients) +
                             '</td></tr></table><p>Điều 1. Phạm vi áp dụng</p><p>1. Nội dung.</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'recipients')), 1)
        self.assertEqual([n['text'] for n in nodes(result, 'recipient')], recipients)
        self.assertEqual(len(nodes(result, 'article')), 1)
        self.assertEqual(len(nodes(result, 'clause')), 1)
        self.assertFalse(nodes(result, 'closing'))
        self.assertFalse(any(i['code'] == 'table_semantics_unresolved' for i in result['issues']))

    def test_long_unlabelled_table_retains_ambiguous_axes(self):
        text = 'Nội dung nguồn chưa có nhãn cột. ' * 12
        result = parse_forms('<table><tr><td>' + text + '</td><td>- Một mục</td></tr></table>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'recipients'))
        self.assertEqual(nodes(result, 'table')[0]['table_kind'], 'ambiguous')
        self.assertTrue(any(i['code'] == 'table_semantics_unresolved' for i in result['issues']))

    def assert_integrity(self, result):
        self.assertTrue(result['validation']['schema_valid'])
        self.assertTrue(result['validation']['meaningful_text_preserved'])
        self.assertEqual(result['issue_summary']['error'], 0)
        self.assertEqual(result['issue_summary']['fatal'], 0)

    def test_grouped_money_calculation_is_not_a_decimal_outline(self):
        result = parse_forms('<p>Điều 1. Cách tính</p><p>Ví dụ về mức hưởng:</p>'
                             '<p>125.000 đồng x 6 x 12 tháng = 9.000.000 đồng.</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        self.assertEqual([n['text'] for n in nodes(result, 'paragraph') if '=' in n.get('text', '')],
                         ['125.000 đồng x 6 x 12 tháng = 9.000.000 đồng.'])
        self.assertFalse(nodes(result, 'numbered_paragraph'))

    def test_calculation_evidence_does_not_justify_decimal_headings(self):
        from vietnam_legal_rag.ingestion.validation.forms import structured_paragraphs
        paragraph = {'type': 'paragraph', 'text': '1.1. Tính mức hưởng X = A x B.',
                     'order': 1, 'source_ref': {'tag': 'p', 'dom_order': 1}}
        audit = structured_paragraphs({'type': 'legal_document', 'children': [paragraph]})
        self.assertEqual(len(audit), 1)
        self.assertFalse(audit[0]['justified'])

    def test_ratified_statute_after_english_signature_resets_legal_scope(self):
        result = parse_forms(
            '<p>DECREE</p><p>Ratifying an attached act</p>'
            '<p>Article 1. Ratification.</p><p>Article 2. Entry into force.</p>'
            '<p>On behalf of the Government</p><p>Prime Minister</p><p>LE VAN AN</p>'
            '<p><b>STATUTE ON THE ORGANIZATION OF AN ENTERPRISE</b></p>'
            '<p>(Ratified together with the above decree)</p>'
            '<p>Chapter I</p><p>GENERAL PROVISIONS</p>'
            '<p>Article 1. Status.</p><p>1. Registered office.</p><p>2. Seal.</p>'
            '<p>Prime Minister</p><p>LE VAN AN</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'article')), 3)
        self.assertEqual(len(nodes(result, 'chapter')), 1)
        self.assertEqual(len(nodes(result, 'clause')), 2)
        self.assertEqual(len(nodes(result, 'signature')), 2)
        self.assertEqual(len(nodes(result, 'signer_name')), 2)
        self.assertEqual(len(nodes(result, 'delegation_title')), 1)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        self.assertFalse(any(i['code'] == 'duplicate_legal_number' for i in result['issues']))

    def test_statute_title_without_attachment_evidence_keeps_closing_scope(self):
        result = parse_forms('<p>Article 1. Entry into force.</p><p>Prime Minister</p>'
                             '<p>LE VAN AN</p><p><b>STATUTE ON ANOTHER MATTER</b></p>'
                             '<p>Explanatory closing text.</p>')
        self.assert_integrity(result)
        self.assertFalse(any(n.get('evidence') == 'attached_legal_act_header'
                             for n in nodes(result, 'layout_block')))

    def test_combined_english_type_title_does_not_absorb_first_body_list(self):
        result = parse_forms('<p>DECISION No. 12/QD-TTg on membership appointments</p><p>Those named below shall cease their membership of the advisory council established to consider applications and report its findings:</p><p>- Member A;</p><p>- Member B.</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'body')), 1)
        self.assertEqual(len(nodes(result, 'list_item')), 2)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_translated_attached_regulation_keeps_counter_scopes(self):
        html = ('<b><p>DECISION No. 18/QD-BXD on business conditions</p></b>'
                '<p>THE MINISTER OF CONSTRUCTION</p><p>Pursuant to the governing law;</p>'
                '<p>At the proposal of the competent department,</p><p>DECIDES:</p>'
                '<p><b>Article 1.-</b> Issue the regulation.</p>'
                '<p><b>Article 2.-</b> This decision takes effect.</p>'
                '<p>Minister of Construction<br><i>TRAN VAN BINH</i></p>'
                '<b><p>REGULATION ON BUSINESS CONDITIONS</p>'
                '<i><p>(Issued together with Decision No. 18/QD-BXD)</p></i></b>'
                '<p>The business lines are:</p><p>1. Survey.</p><p>2. Design.</p>'
                '<p>I. Survey conditions:</p><p>1. Registration.</p><p>2. Qualified staff.</p>'
                '<p>II. Design conditions:</p><p>1. Registration.</p><p>2. Inspection.</p>'
                '<p>Minister of Construction<br><i>TRAN VAN BINH</i></p>')
        result = parse_forms(html)
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'article')), 2)
        self.assertFalse(nodes(result, 'clause'))
        self.assertFalse(nodes(result, 'point'))
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')
                          if n.get('number') in {'I', 'II'}], ['I', 'II'])
        self.assertEqual(len(nodes(result, 'signature')), 2)
        self.assertEqual(len(nodes(result, 'signer_name')), 2)
        self.assertEqual(len(nodes(result, 'proposal_basis')), 1)
        self.assertEqual(len(nodes(result, 'enacting_formula')), 1)
        self.assertFalse(any(i['code'] == 'duplicate_legal_number' for i in result['issues']))
        self.assertEqual(result, parse_forms(html))

    def test_plain_roman_outlines_require_consecutive_counter_resets(self):
        result = parse_forms('<p>CHỈ THỊ</p><p>Về nhiệm vụ.</p>'
                             '<p>I. Nhóm đầu:</p><p>1. Cơ quan.</p><p>2. Tổ chức.</p>'
                             '<p>II. Nhóm sau:</p><p>1. Theo dõi.</p><p>2. Kiểm tra.</p>')
        self.assert_integrity(result)
        outer = [n for n in nodes(result, 'list_item') if n.get('number') in {'I', 'II'}]
        self.assertEqual([n['number'] for n in outer], ['I', 'II'])
        self.assertEqual([[c['number'] for listing in n['children'] if listing['type'] == 'list'
                           for c in listing['children']] for n in outer], [['1', '2'], ['1', '2']])
        self.assertFalse(nodes(result, 'part'))
        for second in ['III. Nhóm sau:', 'II. Nhóm sau không có dấu dẫn']:
            ambiguous = parse_forms('<p>CHỈ THỊ</p><p>Về nhiệm vụ.</p><p>I. Nhóm đầu:</p>'
                                    '<p>1. Cơ quan.</p><p>2. Tổ chức.</p><p>' + second + '</p>'
                                    '<p>2. Theo dõi.</p><p>3. Kiểm tra.</p>')
            self.assertFalse([n for n in nodes(ambiguous, 'list_item')
                              if n.get('number') in {'I', 'II', 'III'}])

    def test_bold_block_wrapper_preserves_inherited_heading_evidence(self):
        result = parse_forms('<b><div><p>Nội dung được nhấn mạnh</p></div></b>')
        self.assert_integrity(result)
        paragraph = nodes(result, 'paragraph')[0]
        self.assertEqual(paragraph['heading_evidence'], 'ancestor_emphasis')

    def test_quoted_footnote_excerpt_keeps_first_article_local(self):
        result = parse_forms('<p>Điều 1. Nội dung<a name="_ftnref1" href="#_ftn1">[1]</a></p>'
                             '<p>CHỦ TỊCH</p><p>Nguyễn Văn An</p><div>'
                             '<p><a name="_ftn1" href="#_ftnref1">[1]</a> Văn bản quy định như sau:</p>'
                             '<p>“Điều 5. Chuyển tiếp</p><p>1. Trường hợp đầu.</p>'
                             '<p>2. Trường hợp sau.</p><p>Điều 6. Thi hành</p><p>1. Trách nhiệm.”</p></div>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'article')), 1)
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['5', '1', '2', '6', '1'])
        self.assertEqual(nodes(result, 'list_item')[0]['label'], '“Điều 5.')
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_signature_linebreaks_require_role_and_name_evidence(self):
        result = parse_forms('<p>Article 1. Implementation.</p>'
                             '<p>Minister of Construction<br>TRAN VAN BINH</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['Minister of Construction'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['TRAN VAN BINH'])
        prose = parse_forms('<p>Article 1. Implementation.</p>'
                            '<p>Minister of Construction<br>shall oversee implementation.</p>')
        self.assertFalse(nodes(prose, 'signature'))

    def test_source_replacement_glyph_is_retained_as_ambiguity(self):
        result = parse_forms('<p>Article 1. The agency�s responsibility.</p>')
        self.assert_integrity(result)
        self.assertTrue(any(i['code'] == 'source_text_encoding_ambiguity' for i in result['issues']))
        self.assertIn('agency�s', nodes(result, 'paragraph')[0]['text'])
        self.assertEqual(result['status'], 'success_with_warnings')
        ignored = parse_forms('<style>/* � */</style><p>Article 1. Implementation.</p>')
        self.assertFalse(any(i['code'] == 'source_text_encoding_ambiguity' for i in ignored['issues']))

    def test_compact_hyphen_counters_keep_continuations_and_exclude_dates(self):
        result = parse_forms('<p>CHỈ THỊ</p><p>Về thủ tục</p><p>Công việc gồm:</p><p>1-Thực hiện.</p><p>Đoạn tiếp theo.</p><p>2- Kiểm tra.</p><p>3-Báo cáo.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'numbered_paragraph')], ['1', '2', '3'])
        date = parse_forms('<p>31-12-2000</p>')
        self.assertFalse(nodes(date, 'numbered_paragraph'))

    def test_dotted_delegation_initials_preserve_source_spelling(self):
        result = parse_forms('<p>Điều 1. Thi hành.</p><table><tr><td></td><td><p>T.M. HỘI ĐỒNG CHÍNH PHỦ</p><p>K.T. THỦ TƯỚNG CHÍNH PHỦ</p><p>PHÓ THỦ TƯỚNG</p><p>Nguyễn Văn An</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'table'))
        self.assertEqual([n['text'] for n in nodes(result, 'delegation_title')], ['T.M. HỘI ĐỒNG CHÍNH PHỦ', 'K.T. THỦ TƯỚNG CHÍNH PHỦ'])

    def test_inline_symbol_runs_preserve_source_offsets_and_punctuation(self):
        result = parse_forms('<p>Điều 1. Phạm vi:</p><p>- Cơ quan; - Tổ chức.</p><p>Tổng số: - Ba trường hợp;</p><p>- Hai trường hợp.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'list_item')], ['Cơ quan;', 'Tổ chức.', 'Ba trường hợp;', 'Hai trường hợp.'])

    def test_attached_act_without_letterhead_resets_outer_roman_and_legal_scope(self):
        result = parse_forms('<p>Điều 1. Ban hành quy định.</p><p>Điều 2. Thi hành.</p><p>Nguyễn Văn An</p><p>(Đã ký)</p><p align="center">QUI ĐỊNH</p><p align="center">Về thực hiện thủ tục</p><p align="center">(Ban hành kèm theo Nghị định số 12-HĐBT)</p><p><b>I. Nội dung chung</b></p><p>Điều 1. Trường hợp đầu.</p><p><b>II. Nội dung khác</b></p><p>Điều 2. Trường hợp sau.</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'article')), 4)
        self.assertEqual([n['text'] for n in nodes(result, 'heading')], ['I. Nội dung chung', 'II. Nội dung khác'])
        self.assertEqual(result['hierarchy_validation']['unresolved']['orphan_nodes'], 0)
        self.assertFalse(any(i['code'] == 'duplicate_legal_number' for i in result['issues']))
        wrapped = parse_forms('<p>Điều 1. Ban hành.</p><table><tr><td></td><td><p>Nguyễn Văn An</p><p>(Đã ký)</p></td></tr></table><p align="center">QUY ĐỊNH</p><p align="center">(Ban hành kèm theo Nghị định số 12-HĐBT)</p><p><b>I. Nội dung đầu</b></p><p>Điều 1. Phạm vi:</p><p>a) Cơ quan.</p><p>b) Tổ chức.</p><p><b>II. Nội dung sau</b></p><p>Điều 2. Thi hành.</p>')
        self.assert_integrity(wrapped)
        self.assertEqual(len(nodes(wrapped, 'article')), 3)
        self.assertEqual(len(nodes(wrapped, 'heading')), 2)
        self.assertEqual(wrapped['hierarchy_validation']['unresolved']['orphan_nodes'], 0)

    def test_replacement_outline_without_quote_marks_keeps_local_scope(self):
        result = parse_forms('<p><b>I. Nội dung đầu</b></p><p>Điều 1. Thay thế mục VII trong bảng kèm theo Nghị định bằng mục VII mới như sau:</p><p><b>VII. Nội dung thay thế</b></p><p>1. Trường hợp một.</p><p>2. Trường hợp hai.</p><p><b>II. Nội dung sau</b></p><p>Điều 2. Thi hành.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'heading')], ['I. Nội dung đầu', 'II. Nội dung sau'])
        self.assertEqual([n['number'] for n in nodes(result, 'article')], ['1', '2'])
        self.assertEqual([n['number'] for n in nodes(result, 'list_item')], ['VII', '1', '2'])

    def test_legacy_authority_qualified_signer_title_is_source_layout(self):
        result = parse_forms('<p>Điều 1. Thi hành.</p><table><tr><td></td><td><p>CHỦ TỊCH HỘI ĐỒNG NHÀ NƯỚC</p><p>Nguyễn Văn An</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertFalse(nodes(result, 'table'))
        self.assertEqual([n['text'] for n in nodes(result, 'signer_title')], ['CHỦ TỊCH HỘI ĐỒNG NHÀ NƯỚC'])
        self.assertEqual([n['text'] for n in nodes(result, 'signer_name')], ['Nguyễn Văn An'])

    def test_source_declared_roman_outline_preserves_literal_labels(self):
        result = parse_forms('<p>THÔNG TƯ</p><p>Về hệ thống đo đạc</p><p class="prov-part">I. Phạm vi áp dụng.</p><p>Nội dung tiếp theo.</p><p class="prov-part">II.Tham số gồm:</p><p>1. Tham số đầu.</p><p>2. Tham số sau.</p>')
        self.assert_integrity(result)
        roman = [n for n in nodes(result, 'list_item') if n.get('number') in {'I', 'II'}]
        self.assertEqual([n['number'] for n in roman], ['I', 'II'])
        self.assertEqual([n['label'] for n in roman], ['I.', 'II.'])
        self.assertEqual(len(nodes(result, 'part')), 0)
        self.assertEqual(len(nodes(result, 'clause')), 0)

    def test_labeled_symbol_assignment_columns_do_not_invent_axes(self):
        result = parse_forms('<p>Điều 1. Tham số:</p><table><tr><td>a. Bán trục:</td><td>a =</td><td>1234,0m</td></tr><tr><td>b. Tốc độ:</td><td>w=</td><td>12x10-3rad/s</td></tr></table>')
        self.assert_integrity(result)
        table = nodes(result, 'table')[0]
        self.assertEqual(table['table_kind'], 'key_value')
        self.assertEqual(table['semantics']['status'], 'not_applicable')
        self.assertEqual([c['effective_text'] for c in table['cells'][1::3]], ['a =', 'w='])

    def test_inline_topic_label_bounds_list_continuation(self):
        result = parse_forms('<p>Điều 1. Nhiệm vụ:</p><p>- Quản lý công việc: Thực hiện việc lập kế hoạch cho từng cơ quan và từng đơn vị.</p><p>Bảo đảm quyền chủ động của đơn vị.</p><p>- Kiểm tra công việc: Theo dõi việc thực hiện.</p><p>Đoạn cuối độc lập.</p>')
        self.assert_integrity(result)
        items = nodes(result, 'list_item')
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]['children'][0]['text'], 'Bảo đảm quyền chủ động của đơn vị.')
        self.assertEqual(nodes(result, 'article')[0]['children'][-1]['text'], 'Đoạn cuối độc lập.')

    def test_compact_dash_items_are_scoped_by_a_source_run(self):
        result = parse_forms('<p>Điều 1. Nội dung:</p><p>- Cơ quan quản lý.</p><p>-Các đơn vị thực hiện.</p><p>-Tổ chức kiểm tra.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'list_item')], ['Cơ quan quản lý.', 'Các đơn vị thực hiện.', 'Tổ chức kiểm tra.'])

    def test_header_authority_title_does_not_disable_roman_outline_scope(self):
        result = parse_forms('<table><tr><td><p>BỘ TRƯỞNG TỔNG THƯ KÝ</p><p>Số: 8-BT</p></td>'
                             '<td><p>CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM</p></td></tr></table>'
                             '<p>THÔNG TƯ</p><p>Về chế độ báo cáo.</p>'
                             '<p class="prov-part">I. NỘI DUNG BÁO CÁO</p><p>1. Nội dung đầu.</p>'
                             '<p>2. Nội dung sau.</p><p class="prov-part">II. TRÁCH NHIỆM</p>'
                             '<p>Cơ quan thực hiện.</p><p class="prov-part">III. THI HÀNH</p>'
                             '<p>1. Ngày thực hiện.</p><p>2. Nơi tiếp nhận.</p>')
        self.assert_integrity(result)
        roman = [n for n in nodes(result, 'list_item') if n.get('number') in {'I', 'II', 'III'}]
        self.assertEqual([n['number'] for n in roman], ['I', 'II', 'III'])
        self.assertFalse(nodes(result, 'part'))
        self.assertEqual([n['text'] for n in nodes(result, 'issuing_authority')], ['BỘ TRƯỞNG TỔNG THƯ KÝ'])
        self.assertFalse(nodes(result, 'signer_title'))

    def test_inline_colons_do_not_merge_value_or_prose_lists(self):
        cases = [
            '<p>- Khu vực A: 25.000 triệu đồng.</p><p>- Khu vực B: 9.000 triệu đồng.</p>'
            '<p>Ngoài ra, hỗ trợ riêng gồm:</p><p>- Kinh phí đầu.</p><p>- Kinh phí sau.</p>',
            '<p>- Xây dựng quy hoạch.</p><p>- Kiểm tra định kỳ: trực tiếp kiểm tra.</p>'
            '<p>Trước khi kiểm tra, thông báo lịch.</p><p>- Tham gia ý kiến.</p><p>- Đào tạo cán bộ.</p>',
        ]
        for source in cases:
            with self.subTest(source=source):
                result = parse_forms('<p>Điều 1. Nhiệm vụ.</p>' + source)
                self.assert_integrity(result)
                self.assertEqual(len(nodes(result, 'list')), 2)
                self.assertEqual(len(nodes(result, 'list_item')), 4)
                self.assertTrue(all(not n['children'] for n in nodes(result, 'list_item')))

    def test_bold_label_band_with_unit_bearing_quantities(self):
        result = parse_forms('<p>Điều 1. Phân cấp.</p><table><tr><td><b>Cấp</b></td>'
                             '<td><b>Vùng bảo vệ</b></td><td><b>Độ sâu</b></td></tr>'
                             '<tr><td>Đặc biệt</td><td>Nội thành</td><td>Trên 2m</td></tr>'
                             '<tr><td>I</td><td>Hai tỉnh</td><td>1,5 m</td></tr></table>')
        self.assert_integrity(result)
        table = nodes(result, 'table')[0]
        self.assertEqual(table['table_kind'], 'data')
        self.assertEqual([c['cell_type'] for c in table['cells'][:3]], ['header'] * 3)
        self.assertEqual([c['effective_text'] for c in table['cells'][:3]], ['Cấp', 'Vùng bảo vệ', 'Độ sâu'])
        self.assertTrue(all(c.get('header_refs') for c in table['cells'][3:]))
        self.assertEqual(table['grid_shape'], {'rows': 3, 'columns': 3})

    def test_article_local_letters_keep_tables_and_nested_continuations(self):
        result = parse_forms('<p>Điều 1.</p><p>a) Đất chịu thuế:</p><p>- Đất ở.</p><p>- Đất sản xuất.</p><p>b) Đất miễn thuế:</p><table><tr><td>Loại đất</td><td>Mức miễn</td></tr><tr><td>Đất rừng</td><td>100%</td></tr></table><p>c) Cơ quan thực hiện.</p><p>Điều 2. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual(result['hierarchy_validation']['unresolved']['orphan_nodes'], 0)
        items = [n for n in nodes(result, 'list_item') if n.get('number')]
        self.assertEqual([n['number'] for n in items], ['a', 'b', 'c'])
        self.assertTrue(any(n['type'] == 'table' for n in items[1]['children']))
        self.assertEqual(len(nodes(result, 'article')), 2)

    def test_uppercase_article_outline_bounds_numeric_restarts_and_gaps(self):
        result = parse_forms('<p>Điều 1. Các trường hợp:</p><p>A. Dùng dấu chung.</p><p>1. Cơ quan.</p><p>2. Tổ chức.</p><p>B. Dùng dấu riêng.</p><p>1. Doanh nghiệp.</p><p>Nội dung tiếp theo không đánh số.</p><p>3. Liên doanh.</p><p>4. Cá nhân.</p><p>Điều 2. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual(result['hierarchy_validation']['unresolved']['orphan_nodes'], 0)
        self.assertFalse(any(i['code'] == 'duplicate_legal_number' for i in result['issues']))
        outer = [n for n in nodes(result, 'list_item') if n.get('number') in {'A', 'B'}]
        self.assertEqual([n['number'] for n in outer], ['A', 'B'])
        self.assertEqual([[c['number'] for listing in n['children'] if listing['type'] == 'list' for c in listing['children']] for n in outer], [['1', '2'], ['1', '3', '4']])

    def test_article_free_decimal_hyphens_preserve_prefix_and_source_order(self):
        result = parse_forms('<p>THÔNG TƯ</p><p>Hướng dẫn thực hiện</p><p>Phần I. Nội dung</p><p>1- Trách nhiệm chung</p><p>1.1. Những nhiệm vụ:</p><p>a) Nhiệm vụ đầu.</p><p>b) Nhiệm vụ sau.</p><p>1.2- Trách nhiệm bổ sung.</p><p>2- Trách nhiệm riêng</p><p>2.1- Thực hiện.</p><p>Nội dung tiếp theo.</p><p>2.2. Kiểm tra.</p>')
        self.assert_integrity(result)
        self.assertTrue(result['hierarchy_validation']['order_valid'])
        numbered = {n['number']: n for n in nodes(result, 'numbered_paragraph')}
        self.assertEqual([n.get('number') for n in numbered['1']['children']], ['1.1', '1.2'])
        self.assertEqual([n.get('number') for n in numbered['1.1']['children']], ['a', 'b'])
        self.assertEqual([n.get('number') for n in numbered['2']['children']], ['2.1', '2.2'])
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_legacy_eth_issuer_letter_is_preserved_without_transliteration(self):
        from vietnam_legal_rag.ingestion.html.structure import document_number_roles
        roles = document_number_roles('Quyết định số 08 TC/QÐ/VP Về việc thi hành')
        self.assertEqual(roles['primary_document_number_candidate'], '08 TC/QÐ/VP')
        self.assertEqual(roles['mentioned_document_numbers'], [])

    def test_dash_prefixed_source_legal_bases_keep_preamble_role(self):
        result = parse_forms('<p>NGHỊ QUYẾT</p><p>Về mức thu</p><p>- Căn cứ Luật số 12/2020/QH14;</p><p>- Căn cứ Nghị định số 10/2021/NĐ-CP;</p><p>- Sau khi Tờ trình của Ủy ban;</p><p>QUYẾT NGHỊ</p><p>1/ Mức thu chung.</p><p>2/ Thi hành.</p>')
        self.assert_integrity(result)
        self.assertEqual([n['text'] for n in nodes(result, 'legal_basis')], ['- Căn cứ Luật số 12/2020/QH14;', '- Căn cứ Nghị định số 10/2021/NĐ-CP;'])
        self.assertEqual(len(nodes(result, 'proposal_basis')), 1)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_body_basis_citation_cannot_pull_prior_numeric_outline_into_preamble(self):
        result = parse_forms('<p>CHỈ THỊ</p><p>Về quản lý</p><p>Thời gian qua, công tác quản lý tại địa phương cần được tăng cường nhằm thực hiện đầy đủ các yêu cầu theo quy định của cơ quan có thẩm quyền.</p><p>1. Nhiệm vụ chung:</p><p>- Chủ trì thực hiện.</p><p>- Phối hợp kiểm tra.</p><p>- Căn cứ Quyết định số 12/2020/QĐ-UBND để lập kế hoạch.</p><p>2. Nhiệm vụ khác.</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'preamble')), 0)
        self.assertEqual(len(nodes(result, 'body')), 1)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_long_recipient_table_with_spanned_signer_is_closing_layout(self):
        result = parse_forms('<p>Điều 1. Thi hành</p><table><tr><td>Nơi nhận:</td><td rowspan="4"><p>CHỦ TỊCH</p><p>(Đã ký)</p><p>Nguyễn Văn An</p></td></tr><tr><td>- Cơ quan A;</td></tr><tr><td>- Cơ quan B;</td></tr><tr><td>- Lưu.</td></tr></table><p>PHỤ LỤC</p><p>1. Nội dung.</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'table')), 0)
        self.assertEqual(len(nodes(result, 'closing')), 1)
        self.assertEqual(len(nodes(result, 'annex')), 1)

    def test_colon_value_column_declares_key_value_table(self):
        result = parse_forms('<p>Điều 1. Mức thu</p><table><tr><td>Tiểu học</td><td>: 10.000/thí sinh</td></tr><tr><td>Trung học</td><td>: 30.000/thí sinh</td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual(nodes(result, 'table')[0]['table_kind'], 'key_value')
        self.assertEqual(nodes(result, 'table')[0]['semantics']['status'], 'not_applicable')

    def test_source_declared_clause_keeps_conflicting_letter_counter(self):
        result = parse_forms('<p>Điều 1. Phạm vi</p><p class="prov-clause">l. Phạm vi điều chỉnh</p><p>Nội dung.</p><p class="prov-clause">2. Đối tượng</p><p>Điều 2. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'clause')], ['l', '2'])
        self.assertTrue(any(i['code'] == 'source_counter_role_conflict' for i in result['issues']))
        self.assertEqual(result['status'], 'success_with_warnings')
        ordinary = parse_forms('<p>Điều 1. Phạm vi</p><p>l. Phạm vi điều chỉnh</p><p>2. Đối tượng</p>')
        self.assertTrue(any(i['code'] == 'orphan_point' for i in ordinary['issues']))

    def test_replacement_article_prefix_and_unclosed_quote_stay_local(self):
        result = parse_forms('<p>Điều 1. Sửa đổi:</p><p>Điều 4 trong chương I được sửa đổi và thay bằng điều mới như sau:</p><p>Điều 4 mới: "Nội dung:</p><p>1. Trường hợp đầu.</p><p>2. Trường hợp sau.</p><p>Điều 7 trong chương II được sửa đổi và thay bằng điều mới như sau:</p><p>Điều 7 mới: "Nội dung khác".</p><p>Điều 2. Thi hành</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'article')], ['1', '2'])
        self.assertFalse(any(i['code'] == 'duplicate_legal_number' for i in result['issues']))
        self.assertTrue(any(i['code'] == 'incomplete_source_quotation' for i in result['issues']))
        self.assertTrue(any(n.get('number') == '4' for n in nodes(result, 'list_item')))

    def test_article_free_numbered_body_follows_legal_bases_without_formula(self):
        result = parse_forms('<p>THÔNG TƯ</p><p>Hướng dẫn sử dụng kinh phí</p><p>Căn cứ Nghị định số 12/2020/NĐ-CP;</p><p>1. Sửa đổi nội dung chung.</p><p>2. Kinh phí gồm:</p><p>- Hỗ trợ tài liệu.</p><p>- Hỗ trợ kiểm tra.</p><p>3. Thi hành.</p>')
        self.assert_integrity(result)
        self.assertEqual([n.get('number') for n in nodes(result, 'body')[0]['children']], ['1', '2', '3'])
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        self.assertFalse(any(n['type'] == 'numbered_paragraph' for n in nodes(result, 'preamble')[0]['children']))

    def test_roman_headings_above_articles_close_prior_article_scope(self):
        result = parse_forms('<p>NGHỊ ĐỊNH</p><p>Về mức thu</p><p><b>I. MỨC THU CHUNG</b></p><p>Điều 1. Nội dung</p><p><b>II. MỨC THU RIÊNG</b></p><p>Điều 2. Nội dung khác</p><p><b>V. NỘI DUNG CUỐI</b></p><p>Điều 3. Thi hành</p>')
        self.assert_integrity(result)
        body = nodes(result, 'body')[0]
        self.assertEqual([n['type'] for n in body['children']], ['heading', 'article', 'heading', 'article', 'heading', 'article'])
        self.assertEqual([n.get('number') for n in nodes(result, 'heading')], ['I', 'II', 'V'])
        self.assertEqual(result['hierarchy_validation']['unresolved']['orphan_nodes'], 0)

    def test_roman_outlines_do_not_cross_explicit_part_boundaries(self):
        result = parse_forms('<p>THÔNG TƯ</p><p>Hướng dẫn kinh phí</p><p>Phần I. Nội dung chung</p><p><b>I. NỘI DUNG ĐẦU</b></p><p>1. Kinh phí:</p><table><tr><th>Loại</th><th>Mức</th></tr><tr><td>A</td><td>100</td></tr></table><p><b>II. NỘI DUNG SAU</b></p><p>1. Nội dung khác.</p><p>Phần II. Nội dung riêng</p><p><b>I. CÔNG TÁC ĐẦU</b></p><p>1. Thực hiện.</p><p><b>II. CÔNG TÁC SAU</b></p><p>1. Kiểm tra.</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'part')), 2)
        self.assertEqual(len(nodes(result, 'heading')), 0)
        self.assertEqual([len(p['children']) for p in nodes(result, 'part')], [1, 1])

    def test_hyphenated_roman_article_outline_bounds_numeric_restarts(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><p><b>I- Trường hợp chung</b></p><p>1- Một.</p><p>2- Hai.</p><p><b>II- Trường hợp khác</b></p><p>1- Ba.</p><p>2- Bốn.</p><p>Điều 2. Thi hành</p>')
        self.assert_integrity(result)
        self.assertFalse(any(i['code'] == 'duplicate_legal_number' for i in result['issues']))
        self.assertEqual([n.get('number') for n in nodes(result, 'list_item')], ['I', '1', '2', 'II', '1', '2'])

    def test_multi_signatory_delegation_cells_are_source_layout(self):
        row = '<tr><td><p>KT. CHÁNH ÁN TÒA ÁN NHÂN DÂN TỐI CAO</p><p>PHÓ CHÁNH ÁN THƯỜNG TRỰC</p><p>Nguyễn Văn An</p></td><td><p>KT. VIỆN TRƯỞNG VIỆN KIỂM SÁT NHÂN DÂN TỐI CAO</p><p>PHÓ VIỆN TRƯỞNG</p><p>Trần Văn Bình</p></td></tr>'
        result = parse_forms('<p>Điều 1. Thi hành</p><table>' + row * 2 + '</table>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'table')), 0)
        self.assertEqual(len(nodes(result, 'delegation_title')), 4)
        styled = parse_forms('<p>Điều 1. Thi hành</p><table>' + row.replace('<td>', '<th>').replace('</td>', '</th>') + row + '</table>')
        self.assert_integrity(styled)
        self.assertEqual(len(nodes(styled, 'table')), 0)
        self.assertEqual(len(nodes(styled, 'delegation_title')), 4)

    def test_unbold_ordinal_header_row_has_source_counter_evidence(self):
        result = parse_forms('<p>Điều 1. Bảng</p><table><tr><td>STT</td><td>Đơn vị hành chính</td><td>Số đại biểu</td></tr><tr><td>1</td><td>Huyện A</td><td>03 đại biểu</td></tr><tr><td>2</td><td>Huyện B</td><td>02 đại biểu</td></tr></table>')
        self.assert_integrity(result)
        table = nodes(result, 'table')[0]
        self.assertEqual([c['role'] for c in table['cells'][:3]], ['column_header'] * 3)
        self.assertFalse(any(i['code'] == 'table_semantics_unresolved' for i in result['issues']))
        unmarked = parse_forms('<p>Điều 1. Bảng</p><table><tr><td>Khu A</td><td>100</td></tr><tr><td>Khu B</td><td>200</td></tr></table>')
        self.assertEqual(nodes(unmarked, 'table')[0]['table_kind'], 'ambiguous')
        self.assertFalse(any(c.get('role') == 'column_header' for c in nodes(unmarked, 'table')[0]['cells']))
        template = parse_forms('<p>Mẫu số 01</p><table><tr><td>STT</td><td>Tên cơ sở</td></tr><tr><td>1.</td><td>……</td></tr><tr><td>2.</td><td>……</td></tr></table>')
        self.assertTrue(all(c['cell_type'] == 'data' for c in nodes(template, 'table')[0]['cells']))
        blank_ordinals = parse_forms('<p>Điều 1. Bảng</p><table><tr><td>STT</td><td>Địa bàn</td><td>Số lượng</td></tr><tr><td></td><td>Huyện A</td><td>3</td></tr><tr><td></td><td>Huyện B</td><td>2</td></tr></table>')
        table = nodes(blank_ordinals, 'table')[0]
        self.assertEqual([c['role'] for c in table['cells'][:3]], ['column_header'] * 3)
        self.assertEqual([c['effective_text'] for c in table['cells'][3::3]], ['', ''])

    def test_centered_label_band_uses_contrasting_populated_body_evidence(self):
        html = '<p>Điều 1. Bảng</p><table><tr><td rowspan="2" align="center">Khoản thu</td><td colspan="2" align="center">Mức thu</td></tr><tr><td align="center">Ngành A</td><td align="center">Ngành B</td></tr><tr><td>Trên 100 đồng</td><td>5</td><td>10</td></tr></table>'
        result = parse_forms(html)
        self.assert_integrity(result)
        table = nodes(result, 'table')[0]
        self.assertEqual([c['role'] for c in table['cells'][:4]], ['column_header'] * 4)
        self.assertEqual([len(c['header_refs']['column']) for c in table['cells'][4:]], [1, 2, 2])
        self.assertEqual(table['semantics']['row_headers'], [])
        data = parse_forms('<p>Điều 1. Bảng</p><table><tr><td align="center">Khu A</td><td align="center">100</td></tr><tr><td>Khu B</td><td>200</td></tr></table>')
        self.assertEqual(nodes(data, 'table')[0]['table_kind'], 'ambiguous')

    def test_split_signature_containers_preserve_source_offsets(self):
        result = parse_forms('<p>Điều 1. Thi hành.</p><table><tr><td><p>KT. BỘ TRƯỞNG<br>BỘ A<br>THỨ TRƯỞNG<br>Nguyễn Văn An</p></td><td><p>KT. BỘ TRƯỞNG<br>BỘ B<br>THỨ TRƯỞNG<br>Trần Văn Bình</p></td></tr></table>')
        self.assert_integrity(result)
        signatures = nodes(result, 'signature')
        self.assertEqual(len(signatures), 2)
        self.assertEqual([s.get('source_offset', 0) for s in signatures], [0, 0])
        self.assertEqual([n.get('source_offset', 0) for n in nodes(result, 'signer_title')], [19, 19])
        self.assertTrue(result['hierarchy_validation']['order_valid'])

    def test_inline_amendment_quote_keeps_composite_counter_and_missing_close(self):
        result = parse_forms('<p>THÔNG TƯ</p><p>Hướng dẫn sửa đổi</p><p>Căn cứ Luật số 12/2020/QH14;</p><p>1. Nội dung chung.</p><p>2. Nội dung khác.</p><p>3. Sửa đổi điểm như sau: "3.a. Các nội dung:</p><p>- Tài liệu.</p><p>- Kiểm tra.</p><p>4. Thi hành.</p>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        self.assertTrue(any(n.get('number') == '3.a' for n in nodes(result, 'list_item')))
        self.assertTrue(any(i['code'] == 'incomplete_source_quotation' for i in result['issues']))
        self.assertTrue(any(n.get('number') == '4' for n in nodes(result, 'numbered_paragraph')))

    def test_decimal_subdivisions_under_actual_clause_keep_prefix_scope(self):
        html = '<p>Điều 1. Trách nhiệm</p><p>1. Nghĩa vụ chung.</p><p>2. Trách nhiệm cụ thể:</p><p>2.1.Cứu chữa.</p><p>2.2.Bảo lưu quyền.</p>'
        result = parse_forms(html)
        self.assert_integrity(result)
        clause = next(n for n in nodes(result, 'clause') if n['number'] == '2')
        self.assertEqual([n['number'] for n in clause['children'] if n['type'] == 'numbered_paragraph'], ['2.1', '2.2'])
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_english_appendix_roman_scopes_do_not_become_outer_clauses(self):
        result = parse_forms('<p>Article 1. Scope</p><p>Text.</p><p>APPENDIX</p><p>MEMBER UNITS</p><p>I. INDEPENDENT UNITS:</p><p>1. Unit A.</p><p>2. Unit B.</p><p>II. OTHER UNITS:</p><p>1. Unit C.</p><p>2. Unit D.</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'annex')), 1)
        self.assertEqual(result['hierarchy_validation']['unresolved']['orphan_nodes'], 0)
        self.assertFalse(any(i['code'] == 'duplicate_legal_number' for i in result['issues']))
        self.assertEqual(len(nodes(result, 'article')), 1)
        roman = [n for n in nodes(result, 'list_item') if n.get('number') in {'I', 'II'}]
        self.assertEqual([n['number'] for n in roman], ['I', 'II'])
        self.assertEqual([[c['number'] for c in n['children'][0]['children']] for n in roman],
                         [['1', '2'], ['1', '2']])

    def test_account_classification_labels_are_local_to_article_free_outline(self):
        result = parse_forms('<p>THÔNG TƯ</p><p>Hướng dẫn ngân sách</p><p>A. VỀ THU:</p><p>1.Loại I: Thu.</p><p>Khoản 10: Thu khác:</p><p>- Hạng 1: Công nghiệp.</p><p>- Hạng 2: Nông nghiệp.</p><p>B. VỀ CHI:</p><p>1.Loại I: Chi.</p><p>Khoản 29: Chi khác.</p>')
        self.assert_integrity(result)
        self.assertEqual(result['hierarchy_validation']['unresolved']['orphan_nodes'], 0)
        self.assertEqual(len(nodes(result, 'clause')), 0)
        self.assertTrue(any(n.get('number') == '10' for n in nodes(result, 'list_item')))

    def test_bare_signer_title_with_person_name_is_signing_layout(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><table><tr><td></td><td><p><b>THỨ TRƯỞNG</b></p><p><b>Nguyễn Văn An</b></p></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'table')), 0)
        self.assertEqual(len(nodes(result, 'signature')), 1)
        self.assertEqual(len(nodes(result, 'signer_name')), 1)

    def test_empty_table_placeholders_are_audited_without_invented_axes(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><table style="width:20%"></table>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'table')), 0)
        self.assertTrue(any(i['reason'] == 'empty_source_table' for i in result['ignored_elements']))

    def test_attached_act_restart_is_distinct_from_real_duplicate_number(self):
        result = parse_forms('<p>Điều 1. Ban hành</p><p>Điều 2. Thi hành</p><p>CHỦ TỊCH</p><p>(Đã ký)</p><p>Nguyễn Văn An</p><table><tr><td><p><b>HỘI ĐỒNG NHÂN DÂN</b></p></td><td><p>CỘNG HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p></td></tr></table><p><b>QUY ĐỊNH</b></p><p><b>Nội dung thực hiện</b></p><p>Điều 1. Phạm vi</p><p>Điều 2. Nội dung</p>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'article')), 4)
        self.assertFalse(any(i['code'] == 'duplicate_legal_number' for i in result['issues']))
        duplicate = parse_forms('<p>Điều 1. Một</p><p>Điều 1. Hai</p>')
        self.assertTrue(any(i['code'] == 'duplicate_legal_number' for i in duplicate['issues']))

    def test_numeric_cell_values_and_single_row_counters_are_distinguished(self):
        result = parse_forms('<p>Điều 1. Bảng</p><table><tr><td><p>1. Vốn vay</p></td><td><p>410.000</p><p>130.000</p><p>10.5</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        table = nodes(result, 'table')[0]
        self.assertEqual(table['cells'][1]['effective_text'], '410.000 130.000 10.5')

    def test_bold_td_header_band_without_ordinal_retains_spanned_geometry(self):
        result = parse_forms('<p>Điều 1. Bảng</p><table><tr><td rowspan="2"><b>Diễn giải</b></td><td colspan="2"><b>Mức hỗ trợ</b></td></tr><tr><td><b>Miền núi</b></td><td><b>Đồng bằng</b></td></tr><tr><td>Hạng A</td><td>100</td><td>80</td></tr></table>')
        self.assert_integrity(result)
        table = nodes(result, 'table')[0]
        self.assertEqual(table['table_kind'], 'data')
        self.assertEqual([c['role'] for c in table['cells'][:4]], ['column_header'] * 4)
        self.assertEqual(table['cells'][0]['rowspan'], 2)
        self.assertEqual(table['cells'][1]['colspan'], 2)
        self.assertTrue(table['cells'][-1]['header_refs']['column'])

    def test_linked_footer_note_keeps_provision_excerpt_counters_local(self):
        result = parse_forms('<p>Điều 1. Nội dung<a name="_ftnref1" href="#_ftn1">[1]</a></p><p>CHỦ TỊCH</p><p>Nguyễn Văn An</p><div><p><a name="_ftn1" href="#_ftnref1">[1]</a> Văn bản sửa đổi quy định như sau:</p><p>1. Hiệu lực.</p><p>2. Trách nhiệm.</p></div>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'footnote')), 1)
        self.assertEqual(len(nodes(result, 'list_item')), 2)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)

    def test_source_mixed_quotation_marks_close_without_inserting_punctuation(self):
        result = parse_forms('<p>Điều 1. Sửa đổi</p><p>1. Sửa đổi như sau:</p><p>"Điều 2.</p><p>1. Nội dung.”</p><p>2. Bổ sung như sau:</p><p>“Điều 3.</p><p>1. Nội dung.”</p>')
        self.assert_integrity(result)
        self.assertFalse(any(i['code'] == 'incomplete_source_quotation' for i in result['issues']))
        self.assertTrue(any(i['code'] == 'mixed_source_quotation_marks' for i in result['issues']))
        self.assertEqual(len(nodes(result, 'article')), 1)

    def test_table_numeric_topics_keep_nested_dash_list_continuations(self):
        result = parse_forms('<p>Điều 1. Bảng</p><table><tr><td><p>1. Chủ đề một</p><p>- Dòng một</p><p>- Dòng hai</p><p>2. Chủ đề hai</p><p>- Dòng ba</p><p>- Dòng bốn</p></td><td>100</td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual(result['form_validation']['unexplained_structured_paragraphs'], 0)
        cell = nodes(result, 'table')[0]['cells'][0]
        wrapper = cell['content'][0]
        self.assertEqual(wrapper['type'], 'layout_block')
        self.assertEqual(len(cell['content']), 1)
        listing = wrapper['children'][0]
        self.assertEqual(listing['type'], 'list')
        self.assertEqual([n['number'] for n in listing['children']], ['1', '2'])
        self.assertEqual([n['children'][0]['type'] for n in listing['children']], ['list', 'list'])
        self.assertEqual([[c['text'] for c in n['children'][0]['children']] for n in listing['children']],
                         [['Dòng một', 'Dòng hai'], ['Dòng ba', 'Dòng bốn']])

    def test_named_bold_spanning_table_caption_precedes_column_labels(self):
        result = parse_forms('<p>Điều 1. Bảng</p><table><tr><td colspan="2"><b>Biểu 1</b></td></tr><tr><td><b>Tỉnh</b></td><td><b>Mức kế hoạch</b></td></tr><tr><td>Tỉnh A</td><td><b>100</b></td></tr></table>')
        self.assert_integrity(result)
        table = nodes(result, 'table')[0]
        self.assertEqual(table['table_kind'], 'data')
        self.assertEqual(table['cells'][0]['role'], 'column_group_header')
        self.assertTrue(table['cells'][-1]['header_refs']['column'])

    def test_decimal_cell_values_do_not_form_numeric_topic_sequence(self):
        result = parse_forms('<p>Điều 1. Bảng</p><table><tr><td><p>1.53</p><p>2.53</p><p>2.10</p></td><td>Giá trị</td></tr></table>')
        self.assert_integrity(result)
        cell = nodes(result, 'table')[0]['cells'][0]
        self.assertEqual(cell['effective_text'], '1.53 2.53 2.10')
        self.assertEqual([n['type'] for n in cell['content']], ['paragraph'] * 3)

    def test_wrapped_bold_td_labels_and_years_remain_one_column_axis(self):
        result = parse_forms('<p>Điều 1. Bảng</p><table><tr><td colspan="3"><b>Biểu 2</b></td></tr>'
                             '<tr><td rowspan="2"><p><b>Số thứ</b></p><p><b>tự</b></p></td>'
                             '<td colspan="2"><p><b>Số lượng</b></p><p><b>thiết bị</b></p></td></tr>'
                             '<tr><td><b>2024</b></td><td><b>2025</b></td></tr>'
                             '<tr><td>1</td><td>10</td><td>12</td></tr></table>')
        self.assert_integrity(result)
        table = nodes(result, 'table')[0]
        self.assertEqual(table['cells'][0]['role'], 'column_group_header')
        self.assertEqual([c['role'] for c in table['cells'][1:5]], ['column_header'] * 4)
        self.assertEqual(table['cells'][-1]['header_refs']['column'],
                         [table['cells'][2]['cell_id'], table['cells'][4]['cell_id']])
        self.assertFalse(any(i['code'] == 'table_semantics_unresolved' for i in result['issues']))

    def test_parliament_signer_title_is_closing_with_actual_name(self):
        result = parse_forms('<p>Điều 1. Nội dung</p><table><tr><td></td><td>'
                             '<p>CHỦ TỊCH QUỐC HỘI</p><p>Nguyễn Văn An</p></td></tr></table>')
        self.assert_integrity(result)
        self.assertEqual(len(nodes(result, 'table')), 0)
        self.assertEqual(nodes(result, 'signer_title')[0]['text'], 'CHỦ TỊCH QUỐC HỘI')
        self.assertEqual(nodes(result, 'signer_name')[0]['text'], 'Nguyễn Văn An')

    def test_hyphenated_explicit_article_separator_keeps_source_label(self):
        result = parse_forms('<p>Article 33. Scope</p><p>Article 34- Duties</p><p>1. Duty.</p><p>Article 35. End</p>')
        self.assert_integrity(result)
        self.assertEqual([n['number'] for n in nodes(result, 'article')], ['33', '34', '35'])
        self.assertEqual(nodes(result, 'article')[1]['label'], 'Article 34')
        self.assertEqual(nodes(result, 'article')[1]['label_suffix'], '-')

    def test_legacy_space_separated_issuer_code_is_exact_reference_candidate(self):
        from vietnam_legal_rag.ingestion.html.structure import document_number_roles, document_numbers
        roles = document_number_roles('Thông tư số 03 TTLB-CS hướng dẫn nghị quyết số 1181 TVQH/K6')
        self.assertEqual(roles['primary_document_number_candidate'], '03 TTLB-CS')
        self.assertEqual(roles['mentioned_document_numbers'], ['1181 TVQH/K6'])
        self.assertEqual(document_numbers('Thông tư số 03 tháng 5 năm 1981; 2 triệu đồng'), [])

    def test_outer_alpha_heading_closes_article_free_legal_chapter(self):
        result = parse_forms('<p>A. TỔ CHỨC:</p><p>Chương I. Các đơn vị</p><p>1. Đơn vị một.</p>'
                             '<p>Chương II. Trách nhiệm</p><p>B. BIÊN CHẾ</p><p>Có bốn chức danh.</p>')
        self.assert_integrity(result)
        body = nodes(result, 'body')[0]
        self.assertEqual([n['type'] for n in body['children']], ['heading', 'chapter', 'chapter', 'heading', 'paragraph'])
        self.assertEqual([n['number'] for n in body['children'] if n['type'] == 'heading'], ['A', 'B'])


if __name__ == '__main__':
    unittest.main()
