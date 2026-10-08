"""Form refinement and the shared field/subfield contract."""
from copy import deepcopy
import json
import unittest
import unicodedata
from vietnam_legal_rag.ingestion.extract_legal_documents import encoded
from vietnam_legal_rag.ingestion.validation.quality import Quality
from vietnam_legal_rag.ingestion.validation.extract import schema_validator, validate_result, walk_content
from vietnam_legal_rag.ingestion.validation.forms import validate_forms
from vietnam_legal_rag.ingestion.extract_legal_documents import encoded
from vietnam_legal_rag.ingestion.validation.extract import schema_validator
from vietnam_legal_rag.ingestion.validation.forms import FORM_NODE_PROPERTIES, validate_forms, walk
from vietnam_legal_rag.ingestion.refinement.schema import clean_contract
from tests.support import parse_forms as parse, nodes


class FormRefinementTests(unittest.TestCase):
    def check(self, html):
        result = json.loads(encoded(parse(html)))
        schema_validator().validate(result)
        quality = Quality()
        validate_result(result, "vbpl:1", quality)
        self.assertFalse(any(i["severity"] in {"fatal", "error"} for i in quality.issues), quality.issues)
        self.assertTrue(result["validation"]["meaningful_text_preserved"], result["issues"])
        self.assertTrue(result["hierarchy_validation"]["order_valid"])
        self.assertEqual(encoded(result), encoded(parse(html)))
        for node in walk_content([result["document"]]):
            self.assertTrue(node.get("source_ref") or node.get("source_refs"))
        return result

    def test_note_sequence_ignores_alternating_typography(self):
        html = '<p>Phụ lục I</p><p>Mẫu số 01. Báo cáo</p><p>Ghi chú:</p>' + ''.join(
            f'<p>{"<small>" if i % 2 else ""}{i} Nội dung {i}.{"</small>" if i % 2 else ""}</p>' for i in range(1, 6))
        result = self.check(html)
        notes = nodes(result, "footnote")
        self.assertEqual([n["marker"] for n in notes], list("12345"))
        self.assertEqual([n["text"] for n in notes], [f"Nội dung {i}." for i in range(1, 6)])
        self.assertEqual(len(nodes(result, "footnote_group")), 1)
        self.assertEqual(result["form_validation"]["inconsistent_footnote_sequences"], 0)

    def test_notes_do_not_cross_new_form_boundary(self):
        html = ('<p>Phụ lục II</p><p>Mẫu số 01</p><p>Ghi chú:</p><p>1 Tên cơ quan</p><p>2 Địa danh.</p>'
                '<p>Mẫu số 02</p><p>1. Tên: ....</p><p>2. Địa chỉ: ....</p>')
        result = self.check(html)
        self.assertEqual(len(nodes(result, "footnote")), 2)
        self.assertEqual(len(nodes(result, "form_field")), 2)

    def test_note_alphabetic_and_dash_sequences_are_scoped(self):
        html = ('<p>Phụ lục I</p><p>Mẫu số 01</p><p>Ghi chú:</p><p>a) Giải thích A</p><p>b) Giải thích B</p>'
                '<p>Văn bản khác.</p><p>Chú thích:</p><p>- Một</p><p>- Hai</p>')
        result = self.check(html)
        self.assertEqual([n["children"][0]["type"] for n in nodes(result, "note")], ["list", "list"])
        self.assertEqual([n["text"] for n in nodes(result, "list_item")], ["Giải thích A", "Giải thích B", "Một", "Hai"])

    def test_form_subfields_attach_to_instruction_and_not_next_field(self):
        html = ('<p>Phụ lục I</p><p>Mẫu số 01. Nhật ký</p><p>2. Trang đầu tiên phải ghi cụ thể các thông tin:</p>'
                '<p>a) Đơn vị: ...</p><p>b) Người lập: ...</p><p>c) Thời gian: ...</p><p>d) Số hiệu: ...</p>'
                '<p>3. Tên: ...</p>')
        result = self.check(html)
        fields = nodes(result, "form_field")
        self.assertEqual([n["number"] for n in fields], ["2", "3"])
        self.assertEqual([n["marker"] for n in fields[0]["children"]], list("abcd"))
        self.assertEqual(fields[1]["children"], [])
        self.assertFalse(nodes(result, "point"))

    def test_subfields_support_dot_markers_and_vietnamese_sequence(self):
        html = '<p>Phụ lục I</p><p>Mẫu số 01</p><p>1. Các thông tin gồm:</p>' + ''.join(f'<p>{m}. Nội dung</p>' for m in 'abcdđe')
        result = self.check(html)
        self.assertEqual([n["marker"] for n in nodes(result, "form_subfield")], list('abcdđe'))

    def test_subfield_tables_do_not_change_source_geometry_or_order(self):
        html = ('<p>Phụ lục I</p><p>Mẫu số 01</p><p>1. Thông tin gồm:</p><p>a) Kho</p>'
                '<table data-table-kind="form"><tr><td>Tên: ...</td><td>...</td></tr></table>'
                '<p>b) Cơ sở</p><table data-table-kind="form"><tr><td>Địa chỉ: ...</td></tr></table>'
                '<p>2. Tên người lập: ...</p>')
        result = self.check(html)
        self.assertEqual([n["children"][0]["type"] for n in nodes(result, "form_subfield")], ["table", "table"])
        self.assertEqual(len(nodes(result, "form_field")), 4)

    def test_single_or_discontinuous_alpha_marker_does_not_create_subfield(self):
        html = '<p>Phụ lục I</p><p>Mẫu số 01</p><p>1. Tên: ...</p><p>a) Một</p><p>c) Ba</p>'
        result = self.check(html)
        self.assertFalse(nodes(result, "form_subfield"))
        self.assertTrue(all(p["justified"] for p in result["structured_paragraph_audit"]))

    def test_displayed_title_stays_in_catalog_form(self):
        html = ('<p>Phụ lục I</p><p>Mẫu số 04. Biên bản giao nhận</p><p><b>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</b></p>'
                '<p><b>Độc lập - Tự do - Hạnh phúc</b></p><p><b>BIÊN BẢN</b></p><p><b>GIAO NHẬN THÔNG TIN</b></p>'
                '<p>Hôm nay, chúng tôi...</p><p>Mẫu số 05. Thông báo</p><p><b>THÔNG BÁO</b></p>')
        result = self.check(html)
        self.assertEqual([n["number"] for n in nodes(result, "form")], ["04", "05"])
        self.assertEqual(nodes(result, "form")[0]["title"], "Biên bản giao nhận")
        self.assertEqual([n["text"] for n in nodes(result, "form_title")], ["BIÊN BẢN", "THÔNG BÁO"])
        self.assertEqual(nodes(result, "form_subtitle")[0]["text"], "GIAO NHẬN THÔNG TIN")
        self.assertEqual(result["form_validation"]["split_form_candidates"], 0)

    def test_combining_unicode_catalog_markers_are_source_faithful(self):
        heading = unicodedata.normalize('NFD', 'Mẫu số 01. Tên mẫu')
        html = f'<p>Phụ lục I</p><p>{heading}</p><p><b>BÁO CÁO</b></p><p>Mẫu số 02</p>'
        result = self.check(html)
        self.assertEqual([n["number"] for n in nodes(result, "form")], ["01", "02"])
        self.assertEqual(nodes(result, "form")[0]["title"], unicodedata.normalize('NFD', 'Tên mẫu'))

    def test_unstyled_prose_report_mention_is_not_a_form_boundary(self):
        html = '<p>Phụ lục I</p><p>Mẫu số 01</p><p>Báo cáo này gồm các nội dung...</p><p>Phiếu ghi chép được lưu.</p><p>Mẫu số 02 được nhắc trong hướng dẫn.</p>'
        result = self.check(html)
        self.assertEqual(len(nodes(result, "form")), 1)

    def test_superscript_note_marker_keeps_label_annotation_provenance(self):
        result = self.check('<p>Phụ lục I</p><p>Mẫu số 01</p><p>Ghi chú:</p><p><sup>1</sup> Tên cơ quan.</p><p>2 Địa danh.</p>')
        note = nodes(result, 'footnote')[0]
        self.assertEqual(note['text'], 'Tên cơ quan.')
        self.assertEqual(note['label_annotations'][0]['source_ref']['tag'], 'sup')
        self.assertEqual(note['label_annotations'][0]['end'], 1)

    def test_header_date_placeholder_does_not_end_title_phase(self):
        html = ('<p>Phụ lục I</p><p>Mẫu số 01</p><p><b>TÊN CƠ QUAN</b></p><p>Số: ...</p>'
                '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p>'
                '<p>..., ngày... tháng... năm...</p><p><b>ĐƠN ĐỀ NGHỊ</b></p><p><b>Cấp giấy</b></p><p>1. Tên: ...</p>')
        result = self.check(html)
        header = nodes(result, "form_header")[0]
        self.assertEqual([n["type"] for n in header["children"]], ['issuing_authority','form_number','national_heading','national_motto','place_and_date'])
        self.assertEqual(nodes(result, "form")[0]["title"], "ĐƠN ĐỀ NGHỊ")
        self.assertIn("title_source_ref", nodes(result, "form")[0])

    def test_blank_authority_header_does_not_hide_displayed_form_titles(self):
        html = ('<p>Phụ lục I</p><p>Mẫu số 04. Biên bản giao nhận</p>'
                '<p>........(1)........</p><p><b>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</b></p>'
                '<p><b>Độc lập - Tự do - Hạnh phúc</b></p><p>Số: /CN-</p>'
                '<p>…(2)..., ngày tháng năm</p><p><b>BIÊN BẢN</b></p>'
                '<p><b>GIAO NHẬN THÔNG TIN</b></p><p>Hôm nay, chúng tôi...</p>')
        result = self.check(html)
        header = nodes(result, 'form_header')[0]
        self.assertEqual([n['type'] for n in header['children']], ['form_placeholder','national_heading','national_motto','form_number','place_and_date'])
        self.assertEqual(nodes(result, 'form_title')[0]['text'], 'BIÊN BẢN')
        self.assertEqual(nodes(result, 'form_subtitle')[0]['text'], 'GIAO NHẬN THÔNG TIN')
        self.assertEqual(len(nodes(result, 'form')), 1)

    def test_header_subject_in_same_layout_table_keeps_title_boundary(self):
        html = ('<p>Phụ lục I</p><p>Mẫu số 01. Danh mục</p><table role="presentation">'
                '<tr><td><p>....(1)....</p></td><td><p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p></td></tr>'
                '<tr><td><p>Số: /</p><p>V/v giao nộp báo cáo...</p></td><td><p>...(2)..., ngày tháng năm</p></td></tr></table>'
                '<p><b>DANH MỤC THÔNG TIN</b></p><p>1. Tên: ...</p>')
        result = self.check(html)
        self.assertEqual(nodes(result, 'form_title')[0]['text'], 'DANH MỤC THÔNG TIN')
        self.assertEqual(nodes(result, 'place_and_date')[0]['placeholder_refs'], ['2'])
        self.assertEqual(nodes(result, 'form_header')[0]['children'][-1]['type'], 'place_and_date')

    def test_bibliography_is_a_list_and_never_input_fields(self):
        html = ('<p>Phụ lục II</p><p>Mẫu số 03. Danh mục tài liệu tham khảo</p>'
                '<p>1. Nguyễn Văn A, Tài liệu 2026.</p><p>2. B. Nguyen, Các nghiên cứu...</p><p>3. C. Tran, 2025.</p>')
        result = self.check(html)
        self.assertEqual(len(nodes(result, "bibliography_entry")), 3)
        self.assertFalse(nodes(result, "form_field"))
        self.assertEqual(result["form_validation"]["bibliography_fields_misclassified"], 0)

    def test_factual_numbered_list_is_not_automatically_a_field(self):
        html = '<p>Phụ lục I</p><p>Mẫu số 02. Danh mục</p><p>1. Tài liệu A.</p><p>2. Tài liệu B.</p>'
        result = self.check(html)
        self.assertFalse(nodes(result, "form_field"))
        self.assertEqual(len(nodes(result, "list_item")), 2)

    def test_cell_lists_preserve_effective_text_grid_and_raw_cell_text(self):
        html = ('<p>Phụ lục I</p><p>Mẫu số 02</p><table data-table-kind="form"><tr><td rowspan="2">'
                '<p>1. Dọn vết lộ</p><p>2. Hào</p><p>3. Giếng</p></td><td><p>- Một</p><p>- Hai</p></td></tr>'
                '<tr><td><p>- Đơn lẻ</p></td></tr></table>')
        result = self.check(html)
        cells = nodes(result, "table")[0]["cells"]
        self.assertEqual(cells[0]["rowspan"], 2)
        self.assertEqual(cells[0]["text"], '')
        self.assertEqual(cells[0]["effective_text"], '1. Dọn vết lộ 2. Hào 3. Giếng')
        self.assertEqual(cells[0]["text_segments"], ['1. Dọn vết lộ','2. Hào','3. Giếng'])
        self.assertEqual(cells[0]["content"][0]["type"], 'list')
        self.assertEqual(cells[1]["content"][0]["style"], 'dash')
        self.assertEqual(result["form_validation"]["structured_table_cell_lists"], 2)

    def test_nonsequential_cell_counters_remain_audited_candidates(self):
        html = '<table role="table"><tr><td><p>1. Một</p><p>3. Ba</p></td></tr></table>'
        result = self.check(html)
        self.assertFalse(nodes(result, "list"))
        self.assertEqual(result["form_validation"]["unexplained_structured_paragraphs"], 2)

    def test_annex_heading_body_evidence_does_not_promote_full_sentences(self):
        html = ('<p>Phụ lục II</p><p>1. Hồ sơ</p><p>1.1. Văn bản pháp lý</p><p>Các văn bản được lưu.</p>'
                '<p>1.2. Thuyết minh</p><p>Phần thuyết minh được trình bày.</p>'
                '<p>2. Nội dung</p><p>2.1. Tất cả tài liệu phải được số hóa.</p>')
        result = self.check(html)
        items = nodes(result, "numbered_item")
        self.assertEqual([n["title"] for n in items], ['Văn bản pháp lý','Thuyết minh',None])
        self.assertTrue(items[2]["text"].endswith('số hóa.'))

    def test_navigation_backlinks_are_audited_without_losing_notes(self):
        html = ('<p>Phụ lục I</p><p>Mẫu số 01</p><p>1. Tên: ...</p><hr><ol>'
                '<li><p>Giải thích thứ nhất. <em>↩</em></p></li><li><p>Giải thích thứ hai. <em>↩</em></p></li></ol>')
        result = self.check(html)
        self.assertEqual([n["text"] for n in nodes(result, "footnote")], ['Giải thích thứ nhất.','Giải thích thứ hai.'])
        self.assertEqual(len([i for i in result['ignored_elements'] if i['reason']=='navigation_artifact']), 2)
        self.assertFalse(any('↩' in (n.get('text') or '') for n in walk_content([result['document']])))

    def test_empty_terminal_backlink_list_disappears_only_with_audit(self):
        result = self.check('<p>Điều 1. Nội dung.</p><hr><ol><li><p><em>↩</em></p></li></ol>')
        self.assertFalse(nodes(result, "list_item"))
        self.assertEqual(result['ignored_elements'][0]['text'], '↩')

    def test_plain_symbols_in_legal_content_are_retained(self):
        html = '<p>Điều 1. Các ký hiệu:</p><p>↩</p><p>↑</p><p>Quay lại</p>'
        result = self.check(html)
        self.assertEqual([n['text'] for n in nodes(result,'paragraph')][-3:], ['↩','↑','Quay lại'])
        self.assertFalse(result['ignored_elements'])

    def test_linked_navigation_symbol_is_removed_with_source_reference(self):
        result = self.check('<p>Điều 1. Nội dung.</p><a href="#top">↑</a>')
        self.assertEqual(result['ignored_elements'][0]['reason'], 'navigation_artifact')
        self.assertIn('source_ref',result['ignored_elements'][0])

    def test_placeholders_and_references_are_preserved_without_resolution(self):
        html = '<p>Phụ lục I</p><p>Mẫu số 01</p><p>........(1)........</p><p>1. Tên báo cáo: …(3)…</p><p>Ghi chú:</p><p>3 Tên báo cáo.</p>'
        result = self.check(html)
        self.assertEqual(nodes(result,'form_placeholder')[0]['placeholder_refs'],['1'])
        self.assertEqual(nodes(result,'form_field')[0]['placeholder_refs'],['3'])
        self.assertEqual(nodes(result,'footnote')[0]['marker'],'3')
        self.assertNotIn('placeholder_meaning',nodes(result,'form_field')[0])

    def test_validator_detects_partially_classified_note_sequence(self):
        result = self.check('<p>Phụ lục I</p><p>Mẫu số 01</p><p>Ghi chú:</p><p>1 Nội dung.</p><p>2 Địa danh.</p>')
        broken = deepcopy(result['document'])
        group = next(n for n in walk_content([broken]) if n['type']=='footnote_group')
        group['children'][1]['type']='paragraph'
        quality=Quality(); metrics,_=validate_forms(broken,quality)
        self.assertEqual(metrics['inconsistent_footnote_sequences'],1)
        self.assertFalse(metrics['semantic_complete'])
        self.assertEqual(quality.issues[0]['code'],'inconsistent_footnote_sequence')

    def test_validator_detects_split_form_and_bibliography_fields(self):
        result = self.check('<p>Phụ lục I</p><p>Mẫu số 04</p><p>1. Tên: ...</p><p>Mẫu số 05</p>')
        broken=deepcopy(result['document'])
        forms=[n for n in walk_content([broken]) if n['type']=='form']
        forms[1]['number']=None
        forms[0]['title']='TÀI LIỆU THAM KHẢO'; forms[0].pop('title_source_ref',None)
        quality=Quality(); metrics,_=validate_forms(broken,quality)
        self.assertEqual(metrics['split_form_candidates'],1)
        self.assertEqual(metrics['bibliography_fields_misclassified'],1)
        self.assertFalse(metrics['semantic_complete'])


class FormNodeInvariantTests(unittest.TestCase):
    def form(self, body):
        html='<p>Phụ lục I</p><p>Mẫu số 01. Báo cáo</p>'+body
        r=parse(html)
        schema_validator().validate(r)
        self.assertTrue(r['validation']['meaningful_text_preserved'],r['issues'])
        self.assertTrue(r['hierarchy_validation']['order_valid'])
        self.assertEqual(encoded(r),encoded(parse(html)))
        fields=[n for n,_ in walk([r['document']]) if n['type'] in {'form_field','form_subfield'}]
        self.assertEqual(len(fields),r['form_validation']['fields']+r['form_validation']['subfields'])
        self.assertTrue(all(all(k in n for k in FORM_NODE_PROPERTIES) for n in fields))
        self.assertEqual(r['form_validation']['form_nodes_missing_field_kind'],0)
        self.assertEqual(r['form_validation']['form_nodes_missing_field_evidence'],0)
        return r

    def alpha_form(self):
        return self.form('<p>1. Trang đầu tiên: ghi các thông tin:</p>'
                         '<p>a) Đơn vị thi công: ……(3)……</p>'
                         '<p>b) Người thành lập (nhóm trưởng): ……(10)……</p>'
                         '<p>c) Thời gian thành lập: từ ngày... tháng...năm... đến ngày ...tháng...năm...</p>'
                         '<p>d) Số hiệu: từ điểm .... đến điểm ....</p>')

    def test_alphabetic_subfields_use_shared_label_value_classification(self):
        r=self.alpha_form(); s=nodes(r,'form_subfield')
        self.assertEqual(len(s),4)
        self.assertTrue(all(n['field_kind']=='input' for n in s))
        self.assertTrue(all(n['field_evidence'] for n in s))
        self.assertEqual(s[2]['field_name'],'Thời gian thành lập')
        self.assertEqual(s[2]['value_text'],'từ ngày... tháng...năm... đến ngày ...tháng...năm...')
        self.assertTrue(r['form_validation']['semantic_complete'])

    def test_unknown_subfield_keeps_explicit_nulls_and_sequence_evidence(self):
        r=self.form('<p>1. Ghi các hạng mục:</p><p>a) Hạng mục thứ nhất</p><p>b) Hạng mục thứ hai</p>')
        for n in nodes(r,'form_subfield'):
            self.assertEqual(n['field_kind'],'unknown')
            self.assertEqual(n['field_evidence'],'source_alphabetic_subfield_sequence')
            self.assertIsNone(n['field_name']); self.assertIsNone(n['value_text'])

    def test_subfield_instruction_uses_existing_rule_and_null_value(self):
        r=self.form('<p>1. Ghi nội dung:</p><p>a) Nội dung: ghi rõ các mục.</p><p>b) Nội dung: liệt kê tài liệu.</p>')
        for n in nodes(r,'form_subfield'):
            self.assertEqual(n['field_kind'],'instruction')
            self.assertEqual(n['field_evidence'],'source_completion_instruction')
            self.assertIsNone(n['value_text'])

    def test_missing_any_required_property_fails_schema_and_semantic_validation(self):
        original=self.alpha_form()
        for kind in ('form_field','form_subfield'):
            for key in FORM_NODE_PROPERTIES:
                with self.subTest(kind=kind,key=key):
                    r=deepcopy(original); nodes(r,kind)[0].pop(key)
                    self.assertFalse(schema_validator().is_valid(r))
                    q=Quality();metrics,_=validate_forms(r['document'],q)
                    self.assertFalse(metrics['semantic_complete'])
                    self.assertTrue(any(i['code']=='invalid_form_node' for i in q.issues))
                    if key in {'field_kind','field_evidence'}:
                        self.assertEqual(metrics['form_nodes_missing_'+key],1)

    def test_subfield_kind_and_evidence_cannot_be_null_or_empty(self):
        original=self.alpha_form()
        for key in ('field_kind','field_evidence'):
            for value in (None,''):
                with self.subTest(key=key,value=value):
                    r=deepcopy(original); nodes(r,'form_subfield')[0][key]=value
                    self.assertFalse(schema_validator().is_valid(r))

    def test_nested_table_cell_subfields_are_covered(self):
        r=self.form('<table data-table-kind="form"><tr><td><p>Tọa độ:</p><p>X…….;</p><p>Y…….;</p><p>H…….(m)</p></td></tr></table>')
        self.assertEqual(len(nodes(r,'form_subfield')),3)
        self.assertEqual(r['form_validation']['fields']+r['form_validation']['subfields'],4)
        self.assertTrue(all(n['field_evidence']=='source_coordinate_axis' for n in nodes(r,'form_subfield')))

    def test_final_contract_remains_idempotent(self):
        r=self.alpha_form();before=encoded(r);clean_contract(r)
        self.assertEqual(encoded(r),before)


if __name__ == "__main__":
    unittest.main()
