"""Schema cleanup and source-faithful consistency regressions."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from vietnam_legal_rag.ingestion.extract_legal_documents import encoded
from vietnam_legal_rag.ingestion.validation.quality import Quality
from vietnam_legal_rag.ingestion.validation.extract import schema_validator, validate_result, walk_content
from vietnam_legal_rag.ingestion.refinement.schema import clean_contract, FIELD_KINDS, form_label_audit
import json
from vietnam_legal_rag.ingestion.validation.quality import Quality, text_units
from vietnam_legal_rag.ingestion.validation.extract import schema_validator, validate_result
from vietnam_legal_rag.ingestion.validation.forms import value_text_audit, form_metrics
from vietnam_legal_rag.ingestion.refinement.schema import clean_contract, form_label_audit
from vietnam_legal_rag.ingestion.semantics.tables import suppress_axes
from tests.support import parse_forms as parse, nodes


class SchemaCleanupTests(unittest.TestCase):
    def check(self, html):
        result = parse(html)
        schema_validator().validate(result)
        self.assertTrue(result['validation']['meaningful_text_preserved'], result['issues'])
        self.assertTrue(result['hierarchy_validation']['order_valid'])
        self.assertEqual(encoded(result), encoded(parse(html)))
        return result

    def form(self, body):
        return self.check('<p>Phụ lục I</p><p>Mẫu số 01. Mẫu báo cáo</p>'+body)

    def test_source_labels_and_empty_values_are_scoped_form_fields(self):
        labels=['Chủ biên','Đơn vị chủ đầu tư','Tỷ lệ','Tên công trình','Tọa độ','Địa điểm','Ngày lập','Người lập','Đơn vị thi công','Người kiểm tra']
        r=self.form(''.join(f'<p>{x}:</p>' for x in labels))
        fields=nodes(r,'form_field')
        self.assertEqual([f['field_name'] for f in fields],labels)
        self.assertTrue(all(f['value_text'] is None and f['field_kind']=='input_label' and f['children']==[] for f in fields))
        self.assertFalse(form_label_audit(r['document']))

    def test_source_values_and_placeholders_do_not_canonicalize_fields(self):
        r=self.form('<p>Tên báo cáo: …..(3)………</p><p>Số: 123</p><p>Ngày: 01/01/2026</p>')
        f=nodes(r,'form_field');self.assertEqual(f[0]['placeholder_refs'],['3'])
        self.assertEqual([x['value_text'] for x in f],['…..(3)………','123','01/01/2026'])
        self.assertEqual(f[0]['field_name'],'Tên báo cáo')
        self.assertEqual(f[0]['text'],'Tên báo cáo: …..(3)………')

    def test_label_outside_forms_remains_prose(self):
        r=self.check('<p>Điều 1.</p><p>Chủ biên:</p><p>Các dữ liệu gồm:</p>')
        self.assertFalse(nodes(r,'form_field'))
        self.assertEqual([n['text'] for n in nodes(r,'paragraph')],['Chủ biên:','Các dữ liệu gồm:'])

    def test_form_prose_with_colon_is_not_input(self):
        r=self.form('<p>Lý do đề nghị sửa đổi như sau:</p><p>Các dữ liệu được xem xét:</p>')
        self.assertFalse(nodes(r,'form_field'))
        self.assertTrue(all(p['justified'] for p in form_label_audit(r['document'])))

    def test_form_prompt_followed_by_explicit_blank_is_input_label(self):
        r=self.form('<p>Lý do đề nghị sửa đổi như sau:</p><p>…………</p>')
        f=nodes(r,'form_field')[0]
        self.assertEqual(f['field_name'],'Lý do đề nghị sửa đổi như sau')
        self.assertIsNone(f['value_text'])
        self.assertEqual(f['field_evidence'],'adjacent_source_placeholder')
        self.assertEqual(nodes(r,'form_placeholder')[0]['text'],'…………')

    def test_unfamiliar_label_is_audited_instead_of_silently_justified(self):
        r=self.form('<p>Thông số tùy chọn:</p><p>Nội dung khác.</p>')
        self.assertFalse(nodes(r,'form_field'))
        audit=form_label_audit(r['document'])
        self.assertFalse(audit[0]['justified'])
        self.assertEqual(r['form_validation']['unexplained_form_label_paragraphs'],1)
        self.assertFalse(r['form_validation']['semantic_complete'])
        self.assertEqual(sum(i['code']=='form_label_unresolved' for i in r['issues']),1)

    def test_emphasized_formula_inside_form_is_heading_without_new_form(self):
        r=self.form('<p>Tên: ...</p><p><b>CHỨNG NHẬN:</b></p><p>Địa chỉ: ...</p>')
        self.assertEqual(len(nodes(r,'form')),1)
        self.assertEqual([n['text'] for n in nodes(r,'heading')],['CHỨNG NHẬN:'])

    def test_note_and_bibliography_labels_are_explanatory(self):
        r=self.form('<p>Ghi chú:</p><p>1 Tên báo cáo: tên đầy đủ</p><p>2 Người lập: họ và tên</p>')
        self.assertFalse(nodes(r,'form_field'))
        self.assertEqual([n['marker'] for n in nodes(r,'footnote')],['1','2'])

    def test_coordinate_children_preserve_physical_cell_and_unit(self):
        html='<table data-table-kind="form"><tr><td><p>Tọa độ:</p><p>X…….;</p><p>Y…….;</p><p>H…….(m)</p></td><td><p>Tỷ lệ:</p></td></tr></table>'
        r=self.form(html);t=nodes(r,'table')[0];c=t['cells'][0];f=c['content'][0]
        self.assertEqual(f['field_kind'],'composite')
        self.assertEqual([n['field_name'] for n in f['children']],list('XYH'))
        self.assertEqual(f['children'][2]['unit'],'m')
        self.assertEqual(f['children'][2]['value_text'],'…….');self.assertEqual(c['text'],'')
        self.assertEqual(c['text_segments'],['Tọa độ:','X…….;','Y…….;','H…….(m)'])
        self.assertEqual(c['effective_text'],'Tọa độ: X…….; Y…….; H…….(m)')
        self.assertEqual([(x['row'],x['column'],x['rowspan'],x['colspan']) for x in t['cells']],[(0,0,1,1),(0,1,1,1)])

    def test_coordinate_scope_cannot_cross_prose_or_table_cell(self):
        r=self.form('<p>Tọa độ:</p><p>X…….;</p><p>Nội dung khác.</p><p>Y…….;</p>')
        self.assertFalse(nodes(r,'form_subfield'))
        r=self.form('<table data-table-kind="form"><tr><td>Tọa độ:</td><td>X…….; Y…….;</td></tr></table>')
        self.assertFalse(nodes(r,'form_subfield'))

    def test_simple_physical_cell_gains_semantics_without_double_projection(self):
        r=self.form('<table data-table-kind="form"><tr><td>Tỷ lệ: 1:50</td><td>Tên: ……</td></tr></table>')
        c=nodes(r,'table')[0]['cells'][0]
        self.assertEqual(c['text'],'Tỷ lệ: 1:50');self.assertEqual(c['effective_text'],'Tỷ lệ: 1:50')
        self.assertEqual(c['content'][0]['field_name'],'Tỷ lệ')
        self.assertEqual(c['content'][0]['value_text'],'1:50')

    def test_multiline_physical_cell_has_ordered_source_offsets(self):
        r=self.form('<table data-table-kind="form"><tr><td>Người lập:<br>Người kiểm tra:</td></tr></table>')
        c=nodes(r,'table')[0]['cells'][0];f=c['content']
        self.assertEqual(len(f),2);self.assertEqual([n['source_offset'] for n in f],[0,11])
        self.assertEqual([n['order'] for n in f],[c['order'],c['order']])

    def test_legal_references_have_one_textual_owner(self):
        r=self.check('<p>Điều 1.</p><p>1. Áp dụng <a href="https://vbpl.vn/doc--64">Luật số 64/2025/QH15</a>.</p><p>2. Nội dung.</p>')
        c=nodes(r,'clause')[0];self.assertNotIn('references',c)
        ref=c['children'][0]['references'][0]
        self.assertEqual(ref['url'],'https://vbpl.vn/doc--64');self.assertTrue(ref['source_ref'])

    def test_linked_legal_marker_keeps_its_source_anchor_owner(self):
        r=self.check('<p>Điều 1.</p><p><a href="https://vbpl.vn/doc--64">1.</a> Nội dung.</p><p>2. Nội dung khác.</p>')
        c=nodes(r,'clause')[0]
        self.assertEqual(c['references'][0]['url'],'https://vbpl.vn/doc--64')
        self.assertNotIn('references',c['children'][0])

    def test_singleton_provenance_and_unsplit_zero_offset_are_removed(self):
        r=self.check('<p>Điều 1. Nội dung.</p>')
        self.assertTrue(all(n.get('source_refs')!=[n['source_ref']] for n in walk_content([r['document']])))
        p=nodes(r,'paragraph')[0];p.update(source_refs=[p['source_ref']],source_offset=0)
        clean_contract(r);self.assertNotIn('source_refs',p);self.assertNotIn('source_offset',p)

    def test_true_split_title_offsets_are_kept(self):
        r=self.check('<p>THÔNG TƯ Quy định về dữ liệu</p><p>Căn cứ Luật số 1/2026/QH15;</p><p>Bộ trưởng ban hành Thông tư.</p><p>Điều 1.</p>')
        h=nodes(r,'document_type_heading')[0];t=nodes(r,'document_title')[0]
        self.assertEqual(h['source_offset'],0);self.assertGreater(t['source_offset'],0)
        self.assertEqual(h['source_ref'],t['source_ref'])

    def test_contract_is_idempotent(self):
        r=self.form('<p>Tọa độ:</p><p>X…….;</p><p>Y…….;</p><p>Ghi chú:</p><p>1 Một</p><p>2 Hai</p>')
        original=encoded(r);clean_contract(r);self.assertEqual(encoded(r),original)

    def test_missing_semantic_scalars_are_null_and_blanks_preserved(self):
        r=self.form('<p>……</p><p>Chủ biên:</p>')
        self.assertEqual(nodes(r,'form_placeholder')[0]['text'],'……')
        self.assertIsNone(nodes(r,'form')[0]['text'])
        for n in walk_content([r['document']]):
            self.assertFalse(any(n.get(k)=='' for k in ['title','text','field_name','value_text']))

    def test_form_evidence_and_field_kind_enum(self):
        r=self.form('<p>1. Tôi xin chịu trách nhiệm về thông tin.</p>')
        f=nodes(r,'form')[0];self.assertEqual(f['evidence'],'explicit_form_number');self.assertNotIn('boundary_evidence',f)
        self.assertEqual(nodes(r,'form_field')[0]['field_kind'],'display')
        for kind in FIELD_KINDS:
            copy=deepcopy(r);nodes(copy,'form_field')[0]['field_kind']=kind;schema_validator().validate(copy)
        nodes(r,'form_field')[0]['field_kind']='declaration'
        self.assertFalse(schema_validator().is_valid(r))

    def test_schema_rejects_empty_semantic_text_and_legacy_candidates(self):
        r=self.form('<p>Chủ biên:</p>');nodes(r,'form_field')[0]['text']=''
        self.assertFalse(schema_validator().is_valid(r))
        r=self.check('<p>Điều 1.</p>');nodes(r,'article')[0]['document_number_candidates']=['1/QĐ']
        self.assertFalse(schema_validator().is_valid(r))

    def test_schema_requires_source_backed_nodes(self):
        r=self.check('<p>Điều 1.</p>');a=nodes(r,'article')[0];a.pop('source_ref')
        self.assertFalse(schema_validator().is_valid(r))

    def test_schema_checks_all_metadata_and_manifest_families(self):
        schema_validator().check_schema(schema_validator().schema)
        from tests.support import metadata_tab as tab
        for key,html in [('properties','<table><tr><td>Nhãn</td><td>--</td></tr></table>'),('relations','<p>Căn cứ (1)</p><ul><li>Luật Địa chất số 54/2024/QH15</li></ul>'),('history','<table><tr><th>Ngày</th><th>Trạng thái</th></tr><tr><td>15/09/2026</td><td>Văn bản có hiệu lực</td></tr><tr><td>15/09/2026</td><td>Văn bản được ban hành</td></tr></table>')]:
            r=tab(html,key);schema_validator().validate(r);self.assertTrue(r['validation']['meaningful_text_preserved'])
            if key=='history':self.assertEqual(len(r['events']),2)
            if key=='properties':self.assertEqual([f['value'] for f in r['fields']][-1],'--')

    def test_schema_quality_is_rechecked_on_mutated_artifact(self):
        r=self.form('<p>Chủ biên:</p>');nodes(r,'form_field')[0]['field_kind']='accidental'
        q=Quality();self.assertFalse(validate_result(r,r['document_id'],q))
        self.assertFalse(r['validation']['schema_valid'])
        self.assertFalse(r['hierarchy_validation']['schema_valid'])

    def test_manifest_contract_distinguishes_diagnostics_and_quality(self):
        from tests.support import create_raw
        from vietnam_legal_rag.ingestion.extract_legal_documents import extract_document
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);raw=create_raw(root)
            manifest=extract_document(raw,root/'extracted'/'doc-id')
            self.assertTrue(all(manifest['quality'].values()))
            self.assertEqual(manifest['diagnostic_info_count'],manifest['issue_summary']['info'])
            self.assertEqual(manifest['warning_count'],0)
            self.assertEqual(manifest['error_count'],0)
            self.assertEqual(manifest['fatal_count'],0)
            self.assertEqual(manifest['issues'],[])
            mutated=deepcopy(manifest);mutated.pop('quality')
            self.assertFalse(schema_validator().is_valid(mutated))
            mutated=deepcopy(manifest);mutated['quality']['schema_valid']='true'
            self.assertFalse(schema_validator().is_valid(mutated))

    def test_grid_gap_is_info_only_without_asserted_factual_associations(self):
        body='<table data-table-kind="form"><tr><td>A</td><td>B</td></tr><tr><td>C</td></tr></table>'
        r=self.form(body);gap=next(i for i in r['issues'] if i['code']=='table_grid_gap')
        self.assertEqual(gap['severity'],'info')
        self.assertEqual(gap['details']['axis_associations'],'not_applicable')
        self.assertFalse(gap['details']['missing_values_filled'])
        r=self.check('<p>Điều 1.</p><table data-table-kind="data"><tr><th>A</th><th>B</th></tr><tr><td>C</td></tr></table>')
        self.assertEqual(next(i for i in r['issues'] if i['code']=='table_grid_gap')['severity'],'warning')


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


if __name__ == "__main__":
    unittest.main()
