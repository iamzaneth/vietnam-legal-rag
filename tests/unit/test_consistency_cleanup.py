"""V2.3.2 source-faithful consistency and safe fallback regressions."""
from copy import deepcopy
import json
import unittest

from test_form_refinement import nodes, parse
from vietnam_legal_rag.ingestion.extract_legal_documents import encoded
from vietnam_legal_rag.ingestion.extract_quality import Quality, text_units
from vietnam_legal_rag.ingestion.extract_validation import schema_validator, validate_result
from vietnam_legal_rag.ingestion.form_validation import value_text_audit, form_metrics, walk
from vietnam_legal_rag.ingestion.schema_cleanup import clean_contract, form_label_audit
from vietnam_legal_rag.ingestion.table_semantics import suppress_axes


class ConsistencyCleanupTests(unittest.TestCase):
    def check(self, html):
        result = json.loads(encoded(parse(html)))
        schema_validator().validate(result)
        self.assertTrue(result['validation']['meaningful_text_preserved'], result['issues'])
        self.assertTrue(result['hierarchy_validation']['order_valid'])
        self.assertEqual(encoded(result), encoded(parse(html)))
        return result

    def form(self, body):
        return self.check('<p>Phụ lục I</p><p>Mẫu số 01. Báo cáo</p>' + body)

    def test_no_colon_labels_need_bounded_input_sequence(self):
        r = self.form('<p>Họ tên: ………</p><p>Chức vụ (nếu có)</p><p>Số CCCD/Hộ chiếu</p><p>Địa chỉ:</p>')
        f = nodes(r, 'form_field')
        self.assertEqual([n['field_name'] for n in f], ['Họ tên', 'Chức vụ', 'Số CCCD/Hộ chiếu', 'Địa chỉ'])
        self.assertTrue(all(n['field_kind'] == 'input_label' and n['value_text'] is None for n in f[1:]))
        self.assertEqual(f[1]['text'], 'Chức vụ (nếu có)')
        self.assertEqual(r['form_validation']['unexplained_form_label_paragraphs'], 0)

    def test_no_colon_rule_generalizes_to_other_noun_labels(self):
        r = self.form('<p>Tên: ……</p><p>Ngày kiểm tra (không bắt buộc)</p><p>Số hồ sơ</p><p>Người lập:</p>')
        self.assertEqual([n['field_name'] for n in nodes(r, 'form_field')], ['Tên', 'Ngày kiểm tra', 'Số hồ sơ', 'Người lập'])

    def test_labels_without_input_neighbors_remain_generic(self):
        r = self.form('<p>Chức vụ (nếu có)</p><p>Nội dung được trình bày ở trang sau.</p>')
        self.assertIn('Chức vụ (nếu có)', [n['text'] for n in nodes(r, 'paragraph')])
        audit = form_label_audit(r['document'])
        self.assertEqual(audit[0]['reason'], 'short_label_outside_confirmed_input_sequence')
        self.assertTrue(audit[0]['justified'])

    def test_prose_and_heading_boundaries_are_not_skipped(self):
        r = self.form('<p>Tên: ……</p><p>Số hồ sơ</p><p>Người lập phải ghi đúng thông tin.</p><p>Địa chỉ:</p>')
        self.assertIn('Số hồ sơ', [p['text'] for p in nodes(r, 'paragraph')])
        r = self.form('<p>Tên: ……</p><p>Số hồ sơ</p><p><b>THÔNG TIN KHÁC</b></p><p>Địa chỉ:</p>')
        self.assertIn('Số hồ sơ', [p['text'] for p in nodes(r, 'paragraph')])

    def test_no_colon_labels_outside_form_are_not_fields(self):
        r = self.check('<p>Điều 1.</p><p>Chức vụ (nếu có)</p><p>Số CCCD/Hộ chiếu</p>')
        self.assertFalse(nodes(r, 'form_field'))

    def test_identification_continuation_is_attached_without_invented_labels(self):
        r = self.form('<p>Tên: ……</p><p>Số CCCD/Hộ chiếu</p><div>cấp ngày tháng năm .Tại:</div><p>Địa chỉ:</p>')
        f = next(n for n in nodes(r, 'form_field') if n['field_name'] == 'Số CCCD/Hộ chiếu')
        child = f['children'][0]
        self.assertEqual(child['text'], 'cấp ngày tháng năm .Tại:')
        self.assertEqual(child['evidence'], 'adjacent_source_field_continuation')
        self.assertGreater(child['order'], f['order'])
        self.assertNotIn('field_name', child)
        self.assertTrue(form_label_audit(r['document'])[0]['justified'])

    def test_continuation_does_not_cross_unrelated_parent(self):
        r = self.form('<p>Tên:</p><p>cấp ngày tháng năm .Tại:</p>')
        self.assertFalse(nodes(r, 'form_field')[0]['children'])

    def test_nested_prompt_is_source_backed_subfield_not_value(self):
        r = self.form('<p>Người đại diện/Người yêu cầu: Ông (bà):</p>')
        f = nodes(r, 'form_field')[0]; s = f['children'][0]
        self.assertEqual(f['field_kind'], 'composite')
        self.assertIsNone(f['value_text']); self.assertIsNone(s['value_text'])
        self.assertEqual(s['field_name'], 'Ông (bà)')
        self.assertEqual(s['type'], 'form_subfield')
        self.assertEqual(f['source_ref'], s['source_ref'])
        self.assertEqual(f['source_offset'], 0)
        self.assertEqual(s['source_offset'], 30)
        self.assertEqual(r['form_validation']['suspicious_value_text'], 0)

    def test_nested_prompt_link_has_one_text_owner(self):
        r = self.form('<p>Người đại diện: <a href="https://vbpl.vn/a">Ông (bà):</a></p>')
        f = nodes(r, 'form_field')[0]
        self.assertNotIn('references', f)
        self.assertEqual(f['children'][0]['references'][0]['url'], 'https://vbpl.vn/a')

    def test_blank_followed_by_declaration_is_not_whole_value(self):
        r = self.form('<p>Do người ký: ……làm đại diện tiến hành giao nhận:</p>')
        f = nodes(r, 'form_field')[0]
        self.assertEqual(f['value_text'], '……')
        self.assertEqual(f['text'], 'Do người ký: ……làm đại diện tiến hành giao nhận:')

    def test_instruction_body_is_not_value(self):
        r = self.form('<p>1. Trang đầu tiên: ghi tên cơ quan và thông tin.</p>')
        f = nodes(r, 'form_field')[0]
        self.assertEqual(f['field_kind'], 'instruction')
        self.assertIsNone(f['value_text'])
        self.assertIn('ghi tên cơ quan', f['text'])

    def test_placeholder_value_excludes_later_prompt_or_fixed_prose(self):
        r = self.form('<p>Địa chỉ: ……Số điện thoại: ……Số fax: ……</p><p>Do người ký: ……làm đại diện.</p>')
        self.assertEqual([f['value_text'] for f in nodes(r, 'form_field')], ['……', '……'])
        self.assertEqual(nodes(r, 'form_field')[0]['text'], 'Địa chỉ: ……Số điện thoại: ……Số fax: ……')
        self.assertFalse(value_text_audit(r['document']))

    def test_mutated_instruction_value_fails_schema_and_form_validation(self):
        r = self.form('<p>1. Trang đầu tiên: ghi tên cơ quan.</p>')
        nodes(r, 'form_field')[0]['value_text'] = 'ghi tên cơ quan.'
        self.assertFalse(schema_validator().is_valid(r))
        q = Quality(); validate_result(r, r['document_id'], q)
        self.assertEqual(r['form_validation']['suspicious_value_text'], 1)
        self.assertTrue(any(i['code'] == 'suspicious_value_text' for i in q.issues))
        self.assertFalse(r['form_validation']['semantic_complete'])

    def test_value_audit_flags_prompt_without_literal_exception(self):
        r = self.form('<p>Tên: ……</p>')
        nodes(r, 'form_field')[0]['value_text'] = 'Người liên hệ:'
        self.assertEqual(value_text_audit(r['document'])[0]['reason'], 'prompt_in_value_text')
        nodes(r, 'form_field')[0].update(value_text='Tên báo cáo', field_kind='input_label')
        self.assertEqual(value_text_audit(r['document'])[0]['reason'], 'input_label_in_value_text')

    def test_values_and_placeholders_remain_source_strings(self):
        r = self.form('<p>Tên: Nguyễn Văn A</p><p>Ngày: 01/01/2026</p><p>Địa chỉ: ……(3)……</p>')
        self.assertEqual([f['value_text'] for f in nodes(r, 'form_field')], ['Nguyễn Văn A', '01/01/2026', '……(3)……'])
        self.assertFalse(value_text_audit(r['document']))

    def test_form_title_alias_has_one_canonical_ref_and_one_text_owner(self):
        r = self.form('<p><b>BIÊN BẢN</b></p>')
        # A standalone title is also supported without a catalog caption.
        r = self.check('<p>Phụ lục I</p><p><b>BIÊN BẢN</b></p><p>Nội dung.</p>')
        f = nodes(r, 'form')[0]
        self.assertIn('title_source_ref', f)
        self.assertNotIn('title_ref', f)
        self.assertEqual(sum(text == 'BIÊN BẢN' for _, text in text_units(r)), 1)

    def test_split_form_title_ref_keeps_all_contributing_sources(self):
        r = self.check('<p>Phụ lục I</p><p>Mẫu số 01</p><p><b>BIÊN BẢN</b></p><p>Nội dung.</p>')
        f = nodes(r, 'form')[0]
        self.assertEqual(f['source_refs'], [f['source_ref'], f['title_source_ref']])

    def test_schema_forbids_title_ref(self):
        r = self.form('<p>Tên:</p>'); f = nodes(r, 'form')[0]
        f['title_ref'] = f['source_ref']
        self.assertFalse(schema_validator().is_valid(r))

    def test_axisless_cells_omit_unknown_zero_pair(self):
        for kind in ('form', 'annex_form', 'key_value'):
            with self.subTest(kind=kind):
                r = self.form(f'<table data-table-kind="{kind}"><tr><td>Tên:</td><td></td></tr></table>')
                for c in nodes(r, 'table')[0]['cells']:
                    self.assertNotIn('role', c); self.assertNotIn('confidence', c)

    def test_suppress_axes_preserves_every_physical_cell_field(self):
        table = {'table_kind': 'layout', 'cells': [{'row': 0, 'column': 0, 'rowspan': 2, 'colspan': 3, 'text': '', 'effective_text': '', 'text_segments': [], 'cell_id': 'c', 'source_ref': {'dom_order': 1}, 'role': 'unknown', 'confidence': 0.0}], 'semantics': {}}
        physical = deepcopy({k:v for k,v in table['cells'][0].items() if k not in {'role','confidence'}})
        suppress_axes(table)
        self.assertEqual(table['cells'][0], physical)

    def test_data_table_roles_remain_meaningful(self):
        r = self.check('<p>Điều 1.</p><table data-table-kind="data"><tr><th>Mục</th><th>Giá trị</th></tr><tr><td>A</td><td>1</td></tr></table>')
        self.assertTrue(any(c.get('role') != 'unknown' and c.get('confidence', 0) > 0 for c in nodes(r, 'table')[0]['cells']))

    def test_real_empty_cells_are_distinct_from_semantic_absence(self):
        r = self.form('<table data-table-kind="form"><tr><td><p>Tên:</p></td><td></td></tr></table>')
        cells = nodes(r, 'table')[0]['cells']
        self.assertEqual(cells[1]['text'], ''); self.assertEqual(cells[1]['effective_text'], '')
        self.assertEqual(form_metrics(r['document'])['physical_empty_cells'], 1)
        self.assertEqual(form_metrics(r['document'])['semantic_empty_string_fields'], 0)
        nodes(r, 'form_field')[0]['text'] = ''
        self.assertEqual(form_metrics(r['document'])['semantic_empty_string_fields'], 1)

    def test_cleanup_is_idempotent_after_nested_prompt_and_continuation(self):
        r = self.form('<p>Người đại diện: Ông (bà):</p><p>Số hồ sơ</p><p>cấp ngày tháng năm .Tại:</p><p>Địa chỉ:</p>')
        original = encoded(r); clean_contract(r); self.assertEqual(encoded(r), original)

    def test_section_leadins_stay_justified_prose(self):
        r = self.form('<p>Thông tin kiểm tra:</p><p>Tài liệu kèm theo:</p><p>Đã nộp mẫu vật vào cơ quan lưu trữ gồm:</p>')
        self.assertEqual(len(nodes(r, 'paragraph')), 3)
        self.assertTrue(all(p['justified'] for p in form_label_audit(r['document'])))


if __name__ == '__main__':
    unittest.main()
