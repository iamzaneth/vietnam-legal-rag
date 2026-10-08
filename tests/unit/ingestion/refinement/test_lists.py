"""Source-backed symbol lists and serialized-output checks."""
from copy import deepcopy
import json
import unittest
from vietnam_legal_rag.ingestion.extract_legal_documents import encoded
from vietnam_legal_rag.ingestion.validation.quality import Quality
from vietnam_legal_rag.ingestion.validation.extract import schema_validator, walk_content
from vietnam_legal_rag.ingestion.validation.forms import FORM_NODE_PROPERTIES, validate_forms, walk
from tests.support import parse_forms as parse, nodes


class SymbolListTests(unittest.TestCase):
    def check(self, html):
        result = json.loads(encoded(parse(html)))
        schema_validator().validate(result)
        self.assertTrue(result["validation"]["meaningful_text_preserved"], result["issues"])
        self.assertTrue(result["validation"]["schema_valid"], result["issues"])
        self.assertTrue(result["hierarchy_validation"]["order_valid"], result["issues"])
        self.assertTrue(result["hierarchy_validation"]["semantic_complete"], result["issues"])
        self.assertFalse(any(result["issue_summary"][s] for s in ("warning", "error", "fatal")), result["issues"])
        self.assertEqual(encoded(result), encoded(parse(html)))
        for n in walk_content([result["document"]]):
            self.assertTrue(n.get("source_ref"))
        return result

    def test_flat_dash_list_preserves_labels_links_and_annotations(self):
        result = self.check('<p>Phụ lục I</p><p>1. Hồ sơ</p>'
                            '<p>- <a href="https://vbpl.vn/doc--2">Tài liệu A</a><sup>1</sup>;</p><p>- Tài liệu B.</p><p>- Tài liệu C.</p>')
        listing = nodes(result, "list")[0]
        self.assertEqual(listing["style"], "dash")
        self.assertEqual([n["label"] for n in listing["children"]], ["-"] * 3)
        self.assertEqual([n["text"] for n in listing["children"]], ["Tài liệu A1;", "Tài liệu B.", "Tài liệu C."])
        self.assertTrue(listing["children"][0]["references"])
        self.assertEqual(listing["children"][0]["annotations"][0]["start"], len("Tài liệu A"))

    def test_nested_markers_use_source_backed_parent_and_continuations(self):
        result = self.check('<p>Phụ lục II</p><p>1. Hồ sơ</p><p>1.1. Tài liệu</p>'
                            '<p>- Công trình A</p><p>Nội dung bao gồm:</p>'
                            '<p>+ Bản vẽ.</p><p>Bản vẽ thể hiện địa hình.</p><p>Thể hiện vị trí các mẫu.</p>'
                            '<p>+ Ảnh chụp công trình.</p><p>- Công trình B</p>'
                            '<p>+ Sổ theo dõi.</p><p>+ Kết quả phân tích.</p><p>Kết thúc phần hướng dẫn.</p>')
        outer = nodes(result, "list")[0]
        self.assertEqual(outer["style"], "dash")
        self.assertEqual(len(outer["children"]), 2)
        first = outer["children"][0]
        self.assertEqual([n["type"] for n in first["children"]], ["paragraph", "list"])
        inner = first["children"][1]
        self.assertEqual(inner["style"], "plus")
        self.assertEqual([n["text"] for n in inner["children"]], ["Bản vẽ.", "Ảnh chụp công trình."])
        self.assertEqual(len(inner["children"][0]["children"]), 2)
        item = nodes(result, "numbered_item")[0]
        self.assertEqual(item["children"][-1]["text"], "Kết thúc phần hướng dẫn.")
        self.assertEqual(result["form_validation"]["unexplained_structured_paragraphs"], 0)

    def test_single_parent_and_child_are_not_synthetic_legal_units(self):
        result = self.check('<p>Phụ lục I</p><p>- Nhóm A</p><p>+ Tài liệu A.</p>')
        self.assertEqual([len(n["children"]) for n in nodes(result, "list")], [1, 1])
        self.assertFalse(nodes(result, "clause"))
        self.assertFalse(nodes(result, "point"))

    def test_body_list_stays_with_its_article_and_not_the_next_article(self):
        result = self.check('<p>Điều 1. Yêu cầu hồ sơ.</p><p>- Nhóm A</p><p>+ Tài liệu A.</p><p>+ Tài liệu B.</p>'
                            '<p>Điều 2. Thời hạn nộp hồ sơ.</p>')
        articles = nodes(result, "article")
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]["children"][-1]["type"], "list")
        self.assertFalse(any(n["type"] == "list" for n in walk_content([articles[1]])))
        self.assertFalse(nodes(result, "clause"))
        self.assertFalse(nodes(result, "point"))

    def test_flat_plus_topics_can_own_explanation(self):
        result = self.check('<p>Phụ lục I</p><p>+ Bản vẽ:</p><p>Thể hiện đầy đủ địa hình.</p><p>+ Ảnh chụp.</p>')
        self.assertEqual(nodes(result, "list")[0]["style"], "plus")
        self.assertEqual(nodes(result, "list_item")[0]["children"][0]["text"], "Thể hiện đầy đủ địa hình.")

    def test_unrelated_flat_prose_is_not_a_continuation(self):
        result = self.check('<p>Phụ lục I</p><p>- Mục A</p><p>- Mục B</p>'
                            '<p>Đoạn văn độc lập.</p><p>- Mục riêng lẻ</p>')
        self.assertEqual(len(nodes(result, "list")), 1)
        self.assertEqual([n["text"] for n in nodes(result, "paragraph")], ["Đoạn văn độc lập.", "- Mục riêng lẻ"])
        self.assertTrue(result["structured_paragraph_audit"][0]["justified"])

    def test_isolated_markers_and_inline_arithmetic_remain_prose(self):
        result = self.check('<p>Phụ lục I</p><p>+ Chú dẫn riêng lẻ</p><p>Nội dung khác.</p>'
                            '<p>- Chú dẫn riêng lẻ</p><p>x + y - z = 5.</p><p>Nhiệt độ -5 °C; sai số ± 2.</p>'
                            '<p>+ 2.5</p><p>- 3.5</p>')
        self.assertFalse(nodes(result, "list"))
        self.assertEqual(len(nodes(result, "paragraph")), 7)
        self.assertTrue(all(p["justified"] for p in result["structured_paragraph_audit"]))

    def test_sequences_do_not_cross_tables_headings_forms_or_annexes(self):
        result = self.check('<p>Phụ lục I</p><p>- Nhóm A</p><p><b>TIÊU ĐỀ KHÁC</b></p><p>+ Mục A</p>'
                            '<table data-table-kind="form"><tr><td>...</td></tr></table><p>+ Mục B</p>'
                            '<p>Mẫu số 01</p><p>+ Mục C</p><p>Mẫu số 02</p><p>+ Mục D</p>'
                            '<p>Phụ lục II</p><p>+ Mục E</p>')
        self.assertFalse(nodes(result, "list"))
        self.assertEqual(len(nodes(result, "form")), 2)
        self.assertEqual(len(nodes(result, "annex")), 2)

    def test_form_plus_instructions_are_list_items_not_unrelated_fields(self):
        result = self.check('<p>Phụ lục I</p><p>Mẫu số 01. Biên bản</p><p>Tài liệu kèm theo:</p>'
                            '<p>+ Phiếu tài liệu: (ghi rõ số lượng).</p><p>+ Ảnh: (số lượng).</p>'
                            '<p>Biên bản được lập thành hai bản.</p><p>Mẫu số 02. Thông báo</p>')
        form = nodes(result, "form")[0]
        self.assertEqual([n["type"] for n in form["children"]], ["paragraph", "list", "paragraph"])
        self.assertEqual(len(form["children"][1]["children"]), 2)
        self.assertFalse(nodes(result, "form_field"))

    def test_form_list_input_prompts_keep_fields_and_contract(self):
        result = self.check('<p>Phụ lục I</p><p>Mẫu số 01</p><p>- Tên cơ quan: ...(1)...</p>'
                            '<p>- Địa chỉ: ....</p><p>+ Tên người lập: ....</p><p>+ Số: 123</p>')
        self.assertEqual(len(nodes(result, "form_field")), 4)
        self.assertEqual(len(nodes(result, "list_item")), 4)
        for field in nodes(result, "form_field"):
            self.assertTrue(all(key in field for key in FORM_NODE_PROPERTIES))
            self.assertNotIn("label", field)
        self.assertEqual(nodes(result, "form_field")[0]["placeholder_refs"], ["1"])
        self.assertEqual(result["form_validation"]["suspicious_value_text"], 0)

    def test_notes_consume_all_nested_source_nodes_once(self):
        result = self.check('<p>Phụ lục I</p><p>Mẫu số 01</p><p>Ghi chú:</p>'
                            '<p>- Nhóm A</p><p>+ Nội dung A:</p><p>Phần giải thích.</p><p>+ Nội dung B.</p>'
                            '<p>- Nhóm B</p><p>+ Nội dung C.</p><p>Đoạn văn sau ghi chú.</p>')
        self.assertEqual(len(nodes(result, "list_item")), 5)
        note = nodes(result, "note")[0]
        self.assertEqual(len(note["children"]), 1)
        self.assertEqual(nodes(result, "form")[0]["children"][-1]["text"], "Đoạn văn sau ghi chú.")

    def test_note_lookahead_does_not_mutate_later_unconsumed_nested_list(self):
        result = self.check('<p>Phụ lục I</p><p>Mẫu số 01</p><p>Ghi chú:</p><p>- Một</p><p>- Hai</p>'
                            '<p>Đoạn độc lập.</p><p>- Nhóm B</p><p>+ Mục B1</p><p>+ Mục B2</p>')
        self.assertEqual(len(nodes(result, "list_item")), 5)
        self.assertEqual(len(nodes(result, "list")), 3)
        note = nodes(result, "note")[0]
        self.assertEqual([n["text"] for n in note["children"][0]["children"]], ["Một", "Hai"])
        self.assertEqual(len([n for n in nodes(result, "list_item") if n["text"] == "Mục B1"]), 1)

    def test_nested_cell_lists_preserve_all_physical_text_and_geometry(self):
        result = self.check('<p>Phụ lục I</p><p>Mẫu số 01</p><table data-table-kind="form"><tr>'
                            '<td rowspan="2"><p>- Nhóm A</p><p>+ Mục A:</p><p>Phần giải thích.</p><p>+ Mục B</p></td>'
                            '<td><p>+ Mục C</p><p>+ Mục D</p></td></tr><tr><td></td></tr></table>')
        table = nodes(result, "table")[0]
        first = table["cells"][0]
        self.assertEqual(first["rowspan"], 2)
        self.assertEqual(first["text_segments"], ["- Nhóm A", "+ Mục A:", "Phần giải thích.", "+ Mục B"])
        self.assertEqual(first["effective_text"], " ".join(first["text_segments"]))
        self.assertEqual(first["content"][0]["style"], "dash")
        self.assertEqual(table["cells"][-1]["text"], "")
        self.assertEqual(table["cells"][-1]["effective_text"], "")
        self.assertEqual(result["form_validation"]["structured_table_cell_lists"], 3)

    def test_recipient_heading_keeps_tight_inline_dash_and_blank_recipients(self):
        result = self.check('<p>Phụ lục I</p><p>Mẫu số 01</p><table data-table-kind="form"><tr><td>'
                            '<p><strong>Đồng kính gửi:</strong></p><p><strong>- </strong>Cơ quan A;</p>'
                            '<p>- Cơ quan B…;</p><p>- Đơn vị C….</p></td></tr></table>'
                            '<p>-Văn bản ngoài nơi nhận.</p>')
        recipients = nodes(result, "recipients")[0]
        self.assertEqual([n["type"] for n in recipients["children"]], ["recipient"] * 3)
        self.assertFalse(nodes(result, "form_field"))
        self.assertFalse(nodes(result, "list"))
        self.assertEqual(nodes(result, "paragraph")[-1]["text"], "-Văn bản ngoài nơi nhận.")
        broken = deepcopy(result["document"])
        group = next(n for n in walk_content([broken]) if n["type"] == "recipients")
        cell = next(p for n, ps in walk([broken]) if n is group for p in ps if "cell_id" in p)
        first = {**group["children"][0], "type": "paragraph"}
        group["children"] = []
        cell["content"].append(first)
        metrics, audit = validate_forms(broken, Quality())
        self.assertEqual(metrics["unexplained_structured_paragraphs"], 1)
        self.assertEqual(audit[0]["reason"], "unresolved_recipient_marker")
        self.assertFalse(metrics["semantic_complete"])

    def test_serialized_audit_detects_nested_markers_and_misclassified_neighbor(self):
        result = self.check('<p>Phụ lục I</p><p>- Nhóm A</p><p>+ Mục A:</p><p>Phần giải thích.</p><p>+ Mục B.</p>')
        broken = deepcopy(result["document"])
        annex = next(n for n in walk_content([broken]) if n["type"] == "annex")
        flattened = []
        for n, _ in walk(annex["children"]):
            if n["type"] == "list_item":
                flattened.append({**n, "type": "paragraph", "text": n["label"] + " " + n["text"], "children": []})
                flattened[-1].pop("label")
            elif n["type"] == "paragraph":
                flattened.append(deepcopy(n))
        flattened.sort(key=lambda n: n["order"])
        # Reproduce the old form-first classification blind spot as well.
        flattened[1]["type"] = "form_field"
        flattened[1].update(field_name=None, field_kind="instruction", field_evidence="source_completion_instruction", value_text=None)
        annex["children"] = flattened
        quality = Quality()
        metrics, audit = validate_forms(broken, quality)
        self.assertEqual(metrics["unexplained_structured_paragraphs"], 2)
        self.assertFalse(metrics["semantic_complete"])
        self.assertTrue(all(not p["justified"] for p in audit))
        self.assertTrue(all(i["severity"] == "warning" for i in quality.issues))


if __name__ == "__main__":
    unittest.main()
