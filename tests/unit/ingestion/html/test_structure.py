"""Regression tests for legal fidelity and conservative table associations."""
import unittest
import unicodedata

from vietnam_legal_rag.ingestion.validation.quality import compact_text, text_units

from vietnam_legal_rag.ingestion.extract_legal_documents import parse_source
from vietnam_legal_rag.ingestion.validation.extract import walk_content

URL = "https://vbpl.vn/van-ban/chi-tiet/source--13205"
SOURCE = {"layer": "raw", "path": "content.html", "sha256": "a" * 64}


def parse(html, key="content"):
    return parse_source(html, key, key, URL, "vbpl:13205", SOURCE)


def body(result):
    return next(n["children"] for n in result["document"]["children"] if n["type"] == "body")


def table(html):
    return next(n for n in walk_content([parse(html)["document"]]) if n["type"] == "table")


def cell(t, row, column):
    return next(c for c in t["cells"] if c["row"] == row and c["column"] == column)


class LegalStructureTests(unittest.TestCase):
    def test_full_hierarchy_preserves_source_order_and_all_closing_text(self):
        source = ("TIÊU ĐỀ", "Căn cứ văn bản số 001/2026", "Phần thứ nhất. QUY ĐỊNH", "Chương IV",
                  "Mục 2. Áp dụng", "Tiểu mục 1. Thủ tục", "Điều 10. Nội dung", "3. Khoản thứ ba",
                  "đ) Điểm đ", "Đoạn tiếp theo", "a) Điểm a", "1. Khoản thứ nhất",
                  "Điều 2. Điều thứ hai", "Điều 2. Điều trùng số", "Nơi nhận:", "Ký tên", "PHỤ LỤC",
                  "Mẫu số 02", "Ghi chú: 1/3; 15%; 01/02/2026")
        result = parse(''.join(f'<p>{s}</p>' for s in source))
        nodes = list(walk_content([result["document"]]))
        self.assertEqual(compact_text("".join(t for _, t in sorted(text_units(result)))), compact_text("".join(source)))
        self.assertEqual([n["number"] for n in nodes if n["type"] == "article"], ["10", "2", "2"])
        self.assertEqual([n["number"] for n in nodes if n["type"] == "clause"], ["3", "1"])
        self.assertEqual([n["number"] for n in nodes if n["type"] == "point"], ["đ", "a"])
        self.assertTrue(result["validation"]["meaningful_text_preserved"])
        self.assertIn("duplicate_legal_number", {i["code"] for i in result["issues"]})
        self.assertFalse({"blocks", "structure", "pages"}.intersection(result))

    def test_missing_levels_and_orphan_explicit_clause(self):
        result = parse('<p>Điều 1. Áp dụng</p><p>a) Điểm không có Khoản</p><p>Điều 7. Khác</p>')
        self.assertEqual([n["type"] for n in body(result)], ["article", "article"])
        self.assertEqual(body(result)[0]["children"][-1]["type"], "point")
        self.assertEqual(body(result)[0]["children"][-1]["parent_status"], "unresolved")
        self.assertIn("orphan_point", {i["code"] for i in result["issues"]})
        orphan = parse('<p>Khoản 01. Khoản không có Điều</p><p>a) Nội dung</p>')
        self.assertEqual(body(orphan)[0]["parent_status"], "unresolved")
        self.assertNotIn("invalid_parent", {i["code"] for i in orphan["issues"]})

    def test_long_article_body_is_not_a_title(self):
        prose = 'Điều 1. Quyết định này có hiệu lực kể từ ngày 01 tháng 7 năm 2026 và thay thế Quyết định số 906/QĐ-BCT ngày 15 tháng 4 năm 2026.'
        result = parse(f'<p>{prose}</p><p>Điều 3. Tổ chức thực hiện</p>')
        self.assertIsNone(body(result)[0]["title"])
        self.assertEqual(body(result)[0]["children"][0]["text"], prose.split(". ", 1)[1])
        self.assertIsNone(body(result)[1]["title"])
        self.assertEqual(body(result)[1]["children"][0]["text"], "Tổ chức thực hiện")

    def test_reference_and_numbers_outside_article_remain_unknown(self):
        result = parse('<p>2</p><p>1. Đoạn mở đầu</p><p>Điều 5 của Luật số 01 quy định như sau.</p><p>1.000 kg; 10,5%; 01/02/2026</p>')
        self.assertEqual([n["type"] for n in body(result)], ["paragraph", "numbered_paragraph", "paragraph", "paragraph"])
        self.assertIn("possible_page_number", {i["code"] for i in result["issues"]})

    def test_empty_spacing_removed_and_unknown_meaningful_text_preserved(self):
        result = parse('<p>&nbsp;</p><p></p><p> </p><unfamiliar data-document-id="77">Chữ nguồn</unfamiliar>')
        self.assertEqual(len(body(result)), 1)
        self.assertEqual(body(result)[0]["type"], 'unknown')
        self.assertEqual(body(result)[0]["source_identifiers"][0]["value"], '77')
        self.assertTrue(result["validation"]["meaningful_text_preserved"])

    def test_unicode_spelling_values_and_paragraphs_are_not_rewritten(self):
        heading = unicodedata.normalize("NFD", "Điều 01. Hiệu lực")
        result = parse('<p>' + heading + '</p><p>1. số 01/2026; 0,5 kg; 1/3; 20%; 01/02/2026; sai chín tả</p><p>Đoạn độc lập</p>')
        article = body(result)[0]
        self.assertEqual(article["label"] + article["label_suffix"], heading.split(" ", 2)[0] + " 01.")
        self.assertEqual(article["number"], "01")
        self.assertIn('sai chín tả', article["children"][0]["children"][0]["text"])
        self.assertEqual(article["children"][0]["children"][1]["text"], 'Đoạn độc lập')
        self.assertTrue(result["validation"]["meaningful_text_preserved"])

    def test_textual_part_number_and_br_heading(self):
        result = parse('<p>Phần thứ mười hai<br>NĂM VÀ THỜI HẠN</p><p>Điều 01. Áp dụng</p>')
        self.assertEqual(body(result)[0]["number"], 'thứ mười hai')
        self.assertEqual(body(result)[0]["title"], 'NĂM VÀ THỜI HẠN')

    def test_html_lists_and_nested_counters_are_semantic_and_ordered(self):
        result = parse('<p>Điều 1. Danh sách</p><ol start="3"><li><p>Khoản ba</p><ol type="a">'
                       '<li>Điểm a</li><li value="4">Điểm d</li></ol></li><li value="1">'
                       '<p>Khoản một</p><p>Đoạn độc lập</p></li></ol><ul><li>Nội dung không đánh số</li></ul>')
        nodes = list(walk_content([result['document']]))
        self.assertEqual([n['number'] for n in nodes if n['type']=='clause'], ['3','1'])
        self.assertEqual([n['number'] for n in nodes if n['type']=='point'], ['a','d'])
        self.assertEqual(sum(n['type']=='list' for n in nodes), 3)
        self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_inline_whitespace_and_links_retained_without_dom_tree(self):
        result = parse('<p><strong>15</strong> <em>%</em><br>Ngày&nbsp; 01/02/2026 '
                       '<a href="/van-ban/chi-tiet/law--99">Luật</a></p>')
        p = body(result)[0]
        self.assertEqual(p['text'], '15 %\nNgày 01/02/2026 Luật')
        self.assertEqual(p['children'], [])
        self.assertEqual(p['references'][0]['url'], 'https://vbpl.vn/van-ban/chi-tiet/law--99')
        self.assertNotIn('attributes', p)
        self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_malformed_optional_endings_and_declarations_remain_parseable(self):
        result = parse('<p>Đoạn một<p>Đoạn hai<table><tr><td>A<td>B<tr><td>C<td>D</table><weird>E')
        self.assertEqual([n['text'] for n in body(result)[:2]], ['Đoạn một','Đoạn hai'])
        t = next(n for n in body(result) if n['type']=='table')
        self.assertEqual([c['text'] for c in t['cells']], ['A','B','C','D'])
        self.assertTrue(result['validation']['meaningful_text_preserved'])
        declaration = parse('<![CDATA[Chữ nguồn trong declaration]]>')
        self.assertIn('Chữ nguồn', body(declaration)[0]['text'])
        self.assertIn('unknown_declaration', {i['code'] for i in declaration['issues']})

    def test_super_and_subscript_offsets_do_not_match_earlier_equal_numbers(self):
        result = parse('<p>2 kg/m<sup>2</sup>; 2 CO<sub>2</sub></p>')
        unit = body(result)[0]
        self.assertEqual(unit['text'], '2 kg/m2; 2 CO2')
        self.assertEqual([(a['type'], a['start'], a['end']) for a in unit['annotations']],
                         [('superscript', 6, 7), ('subscript', 13, 14)])


class TableGeometryTests(unittest.TestCase):
    def test_layout_heading_and_closing_tables_have_only_info_issues(self):
        for html, kind in (('<table><tr><td>BỘ CÔNG THƯƠNG<br>Số: 01/QĐ-BCT</td><td>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</td></tr></table>', 'header'),
                           ('<table><tr><td>Nơi nhận:<p>- Lưu VT</p></td><td>KT. BỘ TRƯỞNG<p>THỨ TRƯỞNG</p></td></tr></table>', 'closing')):
            result = parse(html)
            section = result['document']['children'][0]
            self.assertEqual(section['type'], kind)
            self.assertEqual(section['source_layouts'][0]['table_kind'], 'layout')
            self.assertFalse(any(n['type']=='table' for n in walk_content([result['document']])))
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['issue_summary'], {'info':1,'warning':0,'error':0,'fatal':0})
            self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_rowspan_colspan_multilevel_headers_associate_correctly(self):
        t = table('<table><thead><tr><th rowspan="2" scope="col">Chỉ tiêu</th><th colspan="2" scope="col">Năm</th></tr>'
                  '<tr><th scope="col">2025</th><th scope="col">2026</th></tr></thead><tbody>'
                  '<tr><th scope="row" rowspan="2">Gạo</th><td>10</td><td>20</td></tr><tr><td>30</td><td>40</td></tr></tbody></table>')
        self.assertEqual(t['grid_shape'], {'rows':4,'columns':3})
        value = cell(t,3,2)
        self.assertEqual(value['text'],'40')
        self.assertEqual(value['header_refs']['row'], [cell(t,2,0)['cell_id']])
        self.assertEqual(value['header_refs']['column'], [cell(t,0,1)['cell_id'],cell(t,1,2)['cell_id']])
        self.assertEqual(t['table_kind'],'data')
        self.assertNotIn('rows',t); self.assertNotIn('grid',t)

    def test_rowspan_zero_stops_at_its_row_group(self):
        t = table('<table><tbody><tr><th rowspan="0" scope="row">A</th><td>1</td></tr><tr><td>2</td></tr></tbody>'
                  '<tbody><tr><th scope="row">B</th><td>3</td></tr></tbody></table>')
        self.assertEqual(cell(t,0,0)['rowspan'],2)
        self.assertEqual(cell(t,0,0)['original_rowspan'],'0')
        self.assertEqual(cell(t,2,1)['header_refs']['row'], [cell(t,2,0)['cell_id']])

    def test_explicit_headers_and_colgroup_associations(self):
        t = table('<table><colgroup span="1"></colgroup><colgroup span="2"></colgroup><thead><tr>'
                  '<th id="category" scope="col">Loại</th><th id="years" scope="colgroup" colspan="2">Năm</th>'
                  '</tr></thead><tbody><tr><th id="rice" scope="row">Gạo</th><td headers="rice years">10</td><td>20</td></tr></tbody></table>')
        self.assertEqual(cell(t,1,1)['header_evidence'],'headers_attribute')
        self.assertEqual(cell(t,1,1)['header_refs']['row'],[cell(t,1,0)['cell_id']])
        self.assertEqual(cell(t,1,2)['header_refs']['column'],[cell(t,0,1)['cell_id']])

    def test_compound_headers_keep_labels_without_axis_guesses(self):
        for html in ('<table><thead><tr><td><p>Chỉ tiêu</p><p>Năm</p></td><th scope="col">2026</th></tr></thead>'
                     '<tbody><tr><th scope="row">Gạo</th><td>20</td></tr></tbody></table>',
                     '<table><tr><td><p>Mức độ nghiên cứu địa chất</p><p>Mức độ hiệu quả kinh tế</p></td><td>A</td></tr><tr><td>B</td><td>1</td></tr></table>'):
            result = parse(html); corner = body(result)[0]['cells'][0]
            self.assertEqual(corner['role'],'compound_header')
            self.assertEqual(len(corner['labels']),2)
            self.assertIsNone(corner['row_axis']); self.assertIsNone(corner['column_axis'])
            self.assertEqual(corner['orientation'],'unknown')
            self.assertIn('table_semantics_unresolved', {i['code'] for i in result['issues']})

    def test_explicit_dual_axis_header_keeps_declared_orientation(self):
        t = table('<table><tr><td><span data-axis="row">Chỉ tiêu</span><br><span data-axis="column">Năm</span></td>'
                  '<td>2026</td></tr><tr><td>Gạo</td><td>20</td></tr></table>')
        corner = cell(t,0,0)
        self.assertEqual(corner['role'],'dual_axis_header')
        self.assertEqual(corner['row_axis'],['Chỉ tiêu']); self.assertEqual(corner['column_axis'],['Năm'])
        self.assertFalse(cell(t,1,1).get('header_refs'))

    def test_overlaps_disable_associations_and_report_error_without_dropping(self):
        result = parse('<table><tr><th scope="col">A</th><th rowspan="2" scope="col">B</th></tr><tr><td colspan="2">20</td></tr></table>')
        t = body(result)[0]
        self.assertEqual(len(t['cells']),3)
        self.assertFalse(cell(t,1,0).get('header_refs'))
        self.assertEqual(result['status'],'failed')
        self.assertIn(('error','table_grid_overlap'), {(i['severity'],i['code']) for i in result['issues']})
        self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_invalid_spans_large_grids_and_gaps_preserve_original_values(self):
        result = parse('<table><tr><td rowspan="bad">Tên</td><td colspan="0">20%</td></tr><tr><td>Gốc</td></tr></table>')
        t = body(result)[0]
        self.assertEqual(t['cells'][0]['original_rowspan'],'bad')
        self.assertIn('table_grid_gap',{i['code'] for i in result['issues']})
        large = parse('<table><tr><td colspan="1000" rowspan="65534">Nội dung gốc</td></tr></table>')
        self.assertEqual(body(large)[0]['cells'][0]['rowspan'],65534)
        self.assertIn('grid_resource_limit',{i['code'] for i in large['issues']})

    def test_missing_headers_partial_axes_and_repeated_header_bands_do_not_make_facts(self):
        htmls = ('<table><tr><th id="year" scope="col">Năm</th></tr><tr><td headers="year missing">20</td></tr></table>',
                 '<table><thead><tr><th scope="col">A</th><th scope="col">B</th></tr></thead><tbody><tr><td colspan="2">20</td></tr></tbody></table>',
                 '<table><tr><th scope="col">Năm 2025</th></tr><tr><td>10</td></tr><tr><th scope="col">Năm 2026</th></tr><tr><td>20</td></tr></table>')
        for html in htmls:
            t = table(html); value = t['cells'][-1]
            self.assertFalse(value.get('header_refs'))
            self.assertEqual(value['association_status'],'unknown')
            self.assertTrue(value.get('header_candidates'))

    def test_nested_tables_lists_caption_and_footer_source_order(self):
        result = parse('<table><caption>Phụ lục 1</caption><tfoot><tr><td>Cuối nguồn trước</td></tr></tfoot><tbody>'
                       '<tr><td>Trước<table><tr><td>Bảng con</td></tr></table><ol><li>Ý một</li><li>Ý hai</li></ol>Sau</td></tr></tbody></table>')
        t = body(result)[0]
        self.assertEqual([c['section'] for c in t['cells']],['tfoot','tbody'])
        self.assertEqual(t['cells'][1]['text'],'')
        self.assertEqual([n['type'] for n in t['cells'][1]['content']],['paragraph','table','list','paragraph'])
        self.assertEqual(t['children'][0]['text'],'Phụ lục 1')
        self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_presentation_table_legal_flow_joins_document_body(self):
        result = parse('<table role="presentation"><tr><td><p>Điều 1. Áp dụng</p>'
                       '<p>2. Khoản hai</p><p>1. Khoản một</p><p>Đoạn tiếp</p></td></tr></table>')
        article = body(result)[0]
        self.assertEqual(article['type'], 'article')
        self.assertEqual([n['number'] for n in article['children']], ['2', '1'])
        self.assertEqual(article['children'][1]['children'][1]['text'], 'Đoạn tiếp')
        self.assertFalse(any(n['type']=='table' for n in walk_content([result['document']])))
        self.assertTrue(result['validation']['meaningful_text_preserved'])


if __name__ == '__main__':
    unittest.main()
