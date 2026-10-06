"""V2.2 structural evidence, scope barriers and actual serialized fidelity."""
from copy import deepcopy
import unittest

from vietnam_legal_rag.ingestion.extract_legal_documents import encoded, parse_source
from vietnam_legal_rag.ingestion.extract_quality import Quality
from vietnam_legal_rag.ingestion.extract_validation import schema_validator, validate_result, walk_content
from vietnam_legal_rag.ingestion.structured_html import document_number_roles

SOURCE = {"layer": "raw", "path": "content.html", "sha256": "a" * 64}


def parse(html, key="content"):
    return parse_source(html, key, key, "https://vbpl.vn/doc--1", "vbpl:1", SOURCE)


def nodes(result, kind):
    return [n for n in walk_content([result["document"]]) if n["type"] == kind]


class SemanticRefinementTests(unittest.TestCase):
    def assert_fidelity(self, html, result):
        # Verify final JSON after serialization, including schema, ordered text,
        # parent relationships and repeatability, not a transient parser ledger.
        import json
        actual = json.loads(encoded(result))
        quality = Quality()
        validate_result(actual, "vbpl:1", quality)
        self.assertFalse(any(i["severity"] in {"error", "fatal"} for i in quality.issues), quality.issues)
        self.assertTrue(actual["validation"]["meaningful_text_preserved"], actual["issues"])
        self.assertTrue(actual["hierarchy_validation"]["order_valid"])
        schema_validator().validate(actual)
        self.assertEqual(encoded(result), encoded(parse(html)))
        for n in walk_content([actual["document"]]):
            self.assertTrue(n.get("source_ref") or n.get("source_refs"))

    def test_annex_after_signature_and_decimal_prefix_tree(self):
        html = ('<p>Điều 1. Nội dung.</p><p>Nơi nhận:</p><p>- Lưu.</p>'
                '<p>KT. BỘ TRƯỞNG</p><p>THỨ TRƯỞNG</p><p>[daky]</p><p>Nguyễn Văn A</p>'
                '<p><b>Phụ lục II<br>QUY CÁCH TÀI LIỆU</b></p>'
                '<p>(Ban hành kèm theo Thông tư số 01/2026/TT-BCT)</p>'
                '<p><b>1. Hồ sơ giấy</b></p><p>1.1. Văn bản pháp lý</p><p>1.2. Thuyết minh</p>'
                '<p><b>2. Hồ sơ điện tử</b></p><p>2.1. Tài liệu</p><p>2.1.1. Định dạng</p>'
                '<p>2.1.1.1. Nội dung sâu</p><p>2.2 Quy cách</p><p>2.3. Bàn giao</p>')
        result = parse(html)
        annex = nodes(result, "annex")[0]
        self.assertEqual(annex["number"], "II")
        self.assertEqual(annex["title"], "QUY CÁCH TÀI LIỆU")
        self.assertEqual([n["type"] for n in annex["children"]], ["annex_note", "numbered_section", "numbered_section"])
        section = annex["children"][2]
        self.assertEqual([n["number"] for n in section["children"]], ["2.1", "2.2", "2.3"])
        deep = section["children"][0]["children"][0]["children"][0]
        self.assertEqual(deep["number_path"], [2, 1, 1, 1])
        self.assertEqual(deep["parent_number"], "2.1.1")
        closing = nodes(result, "closing")[0]
        self.assertFalse(any(n["type"] == "annex" for n in walk_content([closing])))
        self.assertEqual(nodes(result, "signature_marker")[0]["semantic"], "signed")
        self.assertEqual(nodes(result, "signer_name")[0]["text"], "Nguyễn Văn A")
        self.assertEqual(result["hierarchy_validation"]["annex_hierarchy"]["max_depth"], 4)
        self.assertFalse(nodes(result, "clause"))
        self.assert_fidelity(html, result)

    def test_annex_prefix_cannot_cross_annex_form_or_numbered_boundary(self):
        html = ('<p>Phụ lục I</p><p>2. Phần đầu</p><p>2.1. Một</p>'
                '<p>Phụ lục II</p><p>2.1. Không có cha</p><p>3. Phần khác</p>'
                '<p>2.2. Không được mượn cha trước ranh giới</p>'
                '<p>Mẫu số 01</p><p>2.1. Không được mượn cha từ phụ lục I</p>')
        result = parse(html)
        orphan = [n for n in nodes(result, "numbered_item") if n.get("parent_status")]
        self.assertEqual(len(orphan), 3)
        self.assertTrue(all(n["unresolved_reason"] == "prefix_parent_missing_in_current_annex_scope" for n in orphan))
        validation = result["hierarchy_validation"]
        self.assertEqual(validation["status"], "valid_with_warnings")
        self.assertFalse(validation["semantic_complete"])
        self.assertTrue(validation["parent_child_valid"])
        self.assert_fidelity(html, result)
        html = '<p>Điều 1. Nội dung.</p><p>Phụ lục II của Thông tư này được áp dụng.</p>'
        result = parse(html)
        self.assertFalse(nodes(result, "annex"))
        self.assert_fidelity(html, result)

    def test_numbered_candidate_with_points_promotes_existing_source_node(self):
        html = ('<p>Điều 23. Trách nhiệm:</p><p>1. Cơ quan chủ trì</p>'
                '<p>a) Nội dung A</p><p>b) Nội dung B</p><p>c) Nội dung C</p>'
                '<p>2. Cơ quan phối hợp</p><p>Điều 24. Khác.</p>')
        result = parse(html)
        first = nodes(result, "article")[0]
        clause = next(n for n in first["children"] if n["type"] == "clause")
        self.assertEqual(clause["number"], "1")
        self.assertEqual(clause["promotion_evidence"]["signals"]["following_point_a"], .30)
        self.assertEqual([p["number"] for p in clause["children"] if p["type"] == "point"], ["a", "b", "c"])
        self.assertFalse(any(n.get("candidate_role") for n in walk_content([clause])))
        self.assertEqual(result["hierarchy_validation"]["unresolved"]["orphan_nodes"], 0)
        self.assert_fidelity(html, result)

    def test_annex_backward_counter_and_structured_heading_are_unresolved(self):
        html = ('<p>Phụ lục III</p><p>2. Phần</p><p>2.3. Trước</p><p>2.1. Sau</p>'
                '<p><b>Chương I</b></p><p>2.2. Sau ranh giới heading</p>')
        result = parse(html)
        orphan = [n for n in nodes(result, "numbered_item") if n.get("parent_status")]
        self.assertEqual([n["unresolved_reason"] for n in orphan],
                         ["numbering_sequence_conflict", "prefix_parent_missing_in_current_annex_scope"])
        self.assert_fidelity(html, result)
        for html in ('<p>Phụ lục I</p><p>2. Phần</p><p>2.123. Mục số lớn</p><p>2.124. Mục tiếp</p>',
                     '<p>Phụ lục I</p><p>02. Phần</p><p>02.01. Mục số có zero</p>'):
            result = parse(html)
            self.assertTrue(nodes(result, "numbered_item"))
            self.assertFalse(any(n.get("parent_status") for n in nodes(result, "numbered_item")))
            self.assert_fidelity(html, result)

    def test_child_points_in_html_list_promote_without_scope_leak(self):
        html = ('<p>Điều 1. Trách nhiệm:</p><ol><li><p>1. Cơ quan</p><ul>'
                '<li>a) Một</li><li>b) Hai</li></ul></li><li>2. Cơ quan hai</li></ol>'
                '<p>a) Điểm ngoài danh sách, thiếu khoản</p>')
        result = parse(html)
        self.assertEqual([n["number"] for n in nodes(result, "clause")], ["1", "2"])
        self.assertFalse(nodes(result, "point")[0].get("parent_status"))
        self.assertEqual(nodes(result, "point")[-1]["parent_status"], "unresolved")
        self.assertEqual(result["hierarchy_validation"]["unresolved"]["orphan_nodes"], 1)
        self.assert_fidelity(html, result)

    def test_separator_is_preserved_and_blocks_title_coalescing(self):
        html = '<p><b>Điều 1.</b></p><hr><p><b>Tên sau boundary</b></p><p>1. Nội dung</p>'
        result = parse(html)
        self.assertIsNone(nodes(result, "article")[0]["title"])
        self.assertEqual(nodes(result, "separator")[0]["source_ref"]["tag"], "hr")
        self.assertNotIn("unknown_element", {i["code"] for i in result["issues"]})
        self.assert_fidelity(html, result)

    def test_sibling_sequences_promote_but_procedural_lists_do_not(self):
        html = '<p>Điều 2. Các định nghĩa:</p><p>1. Một định nghĩa</p><p>2. Hai định nghĩa</p><p>3. Ba định nghĩa</p>'
        result = parse(html)
        self.assertEqual([n["number"] for n in nodes(result, "clause")], ["1", "2", "3"])
        self.assert_fidelity(html, result)
        procedural = parse('<p>Điều 2. Các bước:</p><p>1. Bước thứ nhất</p><p>2. Bước thứ hai</p>')
        self.assertFalse(nodes(procedural, "clause"))
        outside = parse('<p>1. Một</p><p>2. Hai</p><p>3. Ba</p>')
        self.assertFalse(nodes(outside, "clause"))

    def test_table_barrier_and_single_counter_do_not_manufacture_clause(self):
        html = ('<p>Điều 1. Danh mục:</p><p>1. Một</p>'
                '<table><tr><th>Tên</th></tr><tr><td>A</td></tr></table><p>2. Hai</p>')
        result = parse(html)
        self.assertFalse(any(n["number"] == "1" for n in nodes(result, "clause")))
        self.assertEqual(nodes(result, "numbered_paragraph")[0]["number"], "1")
        self.assert_fidelity(html, result)
        single = parse('<p>Điều 1. Danh mục:</p><p>1. Một</p>')
        self.assertFalse(nodes(single, "clause"))
        orphan = parse('<p>Điều 1.</p><p>a) Nguồn không có khoản</p>')
        self.assertEqual(nodes(orphan, "point")[0]["parent_status"], "unresolved")
        self.assertFalse(nodes(orphan, "clause"))

    def test_split_long_titles_merge_source_spans_without_crossing_table(self):
        html = ('<p><b>Chương III</b></p><p><b>PHÂN CẤP TRỮ LƯỢNG</b></p>'
                '<p><b>Điều 19.</b></p><p><b>Giao dịch, đàm phán, dự thầu...</b></p>'
                '<p>1. Nội dung.</p><p><b>Điều 20.</b></p>'
                '<table><tr><th>Tên</th></tr><tr><td>A</td></tr></table>'
                '<p><b>Không được lấy làm title</b></p>')
        result = parse(html)
        chapter = nodes(result, "chapter")[0]
        article = nodes(result, "article")[0]
        self.assertEqual(chapter["title"], "PHÂN CẤP TRỮ LƯỢNG")
        self.assertEqual(article["title"], "Giao dịch, đàm phán, dự thầu...")
        self.assertEqual(article["title_evidence"], "adjacent_heading")
        self.assertEqual(len(article["source_refs"]), 2)
        self.assertIsNone(nodes(result, "article")[1]["title"])
        self.assert_fidelity(html, result)

    def test_multi_block_title_preserves_each_source_span(self):
        html = '<p><b>Chương II</b></p><p><b>DÒNG MỘT</b></p><p><b>DÒNG HAI</b></p><p>Điều 1.</p>'
        result = parse(html)
        chapter = nodes(result, "chapter")[0]
        self.assertEqual(chapter["title"], "DÒNG MỘT\nDÒNG HAI")
        self.assertEqual(len(chapter["source_refs"]), 3)
        self.assertEqual(len(chapter["title_source_spans"]), 2)
        self.assert_fidelity(html, result)

    def test_document_type_and_title_split_for_supported_prefixes(self):
        for prefix in ('LUẬT', 'BỘ LUẬT', 'NGHỊ ĐỊNH', 'NGHỊ QUYẾT', 'QUYẾT ĐỊNH', 'THÔNG TƯ',
                       'THÔNG TƯ LIÊN TỊCH', 'CHỈ THỊ', 'PHÁP LỆNH', 'LỆNH'):
            with self.subTest(prefix=prefix):
                html = f'<p><b>{prefix}</b> Quy định nội dung nguồn</p><p>Điều 1.</p>'
                result = parse(html)
                title = nodes(result, "title_block")[0]["children"]
                self.assertEqual([n["type"] for n in title], ["document_type_heading", "document_title"])
                self.assertEqual(title[0]["text"], prefix)
                self.assertEqual(title[1]["text"], "Quy định nội dung nguồn")
                self.assertEqual(title[0]["source_ref"], title[1]["source_ref"])
                self.assert_fidelity(html, result)

    def test_sentence_enacting_formula_is_a_boundary(self):
        for sentence in ('Chính phủ ban hành Nghị định quy định nội dung.',
                         'Bộ trưởng Bộ Công Thương ban hành Thông tư quy định nội dung.',
                         'Ủy ban nhân dân ban hành Quyết định quy định nội dung.'):
            html = f'<p>Căn cứ Luật số 01/2026/QH15;</p><p>{sentence}</p><p>Điều 1.</p>'
            result = parse(html)
            self.assertEqual(nodes(result, "enacting_formula")[0]["text"], sentence)
            self.assertEqual(len(nodes(result, "preamble")[0]["children"]), 1)
            self.assert_fidelity(html, result)

    def test_effective_text_before_matrix_classification_and_unknown_axes(self):
        html = ('<p>Điều 1.</p><table><tr><td rowspan="2"><p>Mức độ</p><p>nghiên</p>'
                '<p>cứu địa</p><p>chất</p><p>Mức độ</p><p>hiệu quả</p><p>kinh tế</p></td>'
                '<td>Chắc chắn</td><td>Tin cậy</td></tr><tr><td>111</td><td>122</td></tr>'
                '<tr><td>Có tiềm năng</td><td>211</td><td>222</td></tr></table>')
        result = parse(html)
        table = nodes(result, "table")[0]
        corner = table["cells"][0]
        self.assertEqual(table["table_kind"], "matrix")
        self.assertEqual(corner["text"], "")
        self.assertEqual(corner["effective_text"], "Mức độ nghiên cứu địa chất Mức độ hiệu quả kinh tế")
        self.assertEqual(corner["labels"], ["Mức độ nghiên cứu địa chất", "Mức độ hiệu quả kinh tế"])
        self.assertEqual(corner["role"], "compound_header")
        self.assertIsNone(corner["row_axis"])
        self.assertIsNone(corner["column_axis"])
        self.assertEqual(corner["orientation"], "unknown")
        self.assertEqual([i["code"] for i in result["issues"]], ["table_semantics_unresolved"])
        independent = deepcopy(result)
        validate_result(independent, "vbpl:1", Quality())
        self.assertEqual(independent["hierarchy_validation"]["status"], "valid_with_warnings")
        self.assertFalse(independent["hierarchy_validation"]["semantic_complete"])
        self.assert_fidelity(html, result)

    def test_effective_text_recurses_lists_and_nested_tables(self):
        html = ('<table><tr><td><p>Dòng đầu</p><ul><li>Nội dung A</li><li>Nội dung B</li></ul>'
                '<table><tr><td>Dòng sâu</td></tr></table></td></tr></table>')
        result = parse(html)
        outer = nodes(result, "table")[0]["cells"][0]
        self.assertEqual(outer["effective_text"], "Dòng đầu Nội dung A Nội dung B Dòng sâu")
        self.assert_fidelity(html, result)
        broken = deepcopy(result)
        nodes(broken, "table")[0]["cells"][0]["effective_text"] = ""
        quality = Quality()
        validate_result(broken, "vbpl:1", quality)
        self.assertIn("lost_cell_content", {i["code"] for i in quality.issues})
        self.assertEqual(broken["hierarchy_validation"]["status"], "invalid")

    def test_nested_header_does_not_classify_outer_table_as_data(self):
        html = '<table><tr><td><table><tr><th>Tên</th></tr><tr><td>A</td></tr></table></td></tr></table>'
        result = parse(html)
        outer, inner = nodes(result, "table")
        self.assertEqual(outer["table_kind"], "ambiguous")
        self.assertEqual(inner["table_kind"], "data")
        self.assert_fidelity(html, result)
        from vietnam_legal_rag.ingestion.table_semantics import effective_cell_text
        cell = {"text": " \n ", "content": [{"type": "paragraph", "order": 3, "text": "Text nguồn", "children": []}]}
        self.assertEqual(effective_cell_text(cell), (["Text nguồn"], "Text nguồn"))
        self.assertEqual(cell["text"], " \n ")

    def test_annex_form_has_no_forced_axes_and_info_severity(self):
        html = ('<p>Phụ lục I</p><p>Mẫu số 01</p><p>ĐƠN ĐỀ NGHỊ</p>'
                '<table><tr><th>Tên cơ quan</th><th>Địa chỉ</th></tr>'
                '<tr><td>.........</td><td>.........</td></tr></table>')
        result = parse(html)
        table = nodes(result, "table")[0]
        self.assertEqual(table["table_kind"], "annex_form")
        self.assertEqual(table["semantics"]["status"], "not_applicable")
        self.assertFalse(any(c.get("header_refs") for c in table["cells"]))
        self.assertTrue(all(i["severity"] == "info" for i in result["issues"]))
        self.assertEqual(result["hierarchy_validation"]["status"], "valid")
        self.assert_fidelity(html, result)

    def test_dash_sequences_and_form_footnotes_use_context(self):
        html = ('<p>Phụ lục I</p><p>1. Nội dung</p><p>- Dòng A;</p><p>- Dòng B.</p>'
                '<p>Ngắt danh sách</p><p>- Một dòng riêng</p><p>Mẫu số 01</p>'
                '<table><tr><td>Tên cơ quan: ......</td></tr></table>'
                '<p><small>1 Tên cơ quan giao nộp</small></p><p><small>2 Tên đơn vị</small></p>')
        result = parse(html)
        listing = nodes(result, "list")[0]
        self.assertEqual(listing["style"], "dash")
        self.assertEqual(len(listing["children"]), 2)
        self.assertTrue(any(p["text"] == "- Một dòng riêng" for p in nodes(result, "paragraph")))
        self.assertEqual([n["marker"] for n in nodes(result, "footnote")], ["1", "2"])
        self.assertFalse(nodes(result, "clause"))
        self.assert_fidelity(html, result)

    def test_only_repeated_page_edge_numbers_are_audited_artifacts(self):
        html = ('<div data-page="1"><p>Nội dung đầu</p><p>1</p></div>'
                '<div data-page="2"><p>Nội dung sau</p><p>2</p></div>')
        result = parse(html)
        self.assertEqual([n["text"] for n in result["ignored_elements"]], ["1", "2"])
        self.assertTrue(all(n["reason"] == "page_number" for n in result["ignored_elements"]))
        self.assert_fidelity(html, result)
        unproven = parse('<p>Nội dung</p><p>2</p>')
        self.assertFalse(unproven.get("ignored_elements"))
        self.assertTrue(any(n.get("text") == "2" for n in nodes(unproven, "paragraph")))

    def test_named_law_primary_and_later_reference_are_not_equivalent_targets(self):
        for name, number in (("Ban hành văn bản quy phạm pháp luật", "64/2025/QH15"),
                             ("Địa chất và Khoáng sản", "54/2024/QH15")):
            title = f'Luật {name} số {number} sửa Luật số 01/2026/QH15'
            self.assertEqual(document_number_roles(title), {"primary_document_number_candidate": number,
                                                           "mentioned_document_numbers": ["01/2026/QH15"]})
            relation = parse(f'<div>Căn cứ (1)<ul><li>{title}</li></ul></div>', 'relations')
            item = relation["groups"][0]["items"][0]
            self.assertEqual(item["primary_document_number_candidate"], number)
            self.assertEqual(item["resolution_status"], "candidate_only")
            self.assertFalse(relation["issues"])
            self.assertNotIn("document_number_candidates", item)


if __name__ == "__main__":
    unittest.main()
