"""Regressions for document phases, legal parents, coalescing and source fidelity."""
from copy import deepcopy
import unittest
import unicodedata
from tests.support import parse_tab as parse

from vietnam_legal_rag.ingestion.extract_legal_documents import encoded
from vietnam_legal_rag.ingestion.validation.quality import Quality
from vietnam_legal_rag.ingestion.validation.extract import schema_validator, validate_result, walk_content
from vietnam_legal_rag.ingestion.html.structure import document_number_roles


def body(result):
    return next(n for n in result["document"]["children"] if n["type"] == "body")


class DocumentHierarchyTests(unittest.TestCase):
    def assert_preserved(self, result):
        self.assertTrue(result["validation"]["meaningful_text_preserved"])
        self.assertEqual(result["validation"]["source_text_sha256"], result["validation"]["extracted_text_sha256"])
        self.assertNotEqual(result["hierarchy_validation"]["status"], "invalid", result["issues"])
        self.assertFalse(list(schema_validator().iter_errors(result)))

    def test_document_sections_header_title_preamble_body_and_closing(self):
        html = ('<table><tr><td><p>BỘ CÔNG THƯƠNG</p><p>Số: 16111/QĐ-BCT</p></td><td>'
                '<p>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p><p>Độc lập - Tự do - Hạnh phúc</p>'
                '<p>Hà Nội, ngày 01 tháng 7 năm 2026</p></td></tr></table>'
                '<p>QUYẾT ĐỊNH</p><p>Tạm ngưng hiệu lực ...</p><p>BỘ TRƯỞNG BỘ CÔNG THƯƠNG</p>'
                '<p>Căn cứ Luật ...;</p><p>Căn cứ Nghị định ...;</p><p>Xét kiến nghị ...</p>'
                '<p>QUYẾT ĐỊNH:</p><p>Điều 1. Nội dung này có hiệu lực.</p>'
                '<p>Điều 2. Nội dung này thay thế văn bản.</p><p>Điều 3. Tổ chức thực hiện</p>'
                '<p>1. Có hiệu lực.</p><p>2. Trách nhiệm.</p>'
                '<table><tr><td><p>Nơi nhận:</p><p>- Như Điều 3;</p><p>- Lưu VT.</p></td><td>'
                '<p>KT. BỘ TRƯỞNG</p><p>THỨ TRƯỞNG</p><p>Đã ký</p><p>Trương Thanh Hoài</p></td></tr></table>')
        result = parse(html)
        sections = result["document"]["children"]
        self.assertNotIn("content", result)
        self.assertEqual([n["type"] for n in sections], ["header", "title_block", "preamble", "enacting_formula", "body", "closing"])
        self.assertEqual([n["type"] for n in sections[0]["children"]], ["issuing_authority", "document_number", "national_heading", "national_motto", "place_and_date"])
        self.assertEqual(sections[0]["children"][1]["number"], "16111/QĐ-BCT")
        self.assertEqual([n["type"] for n in sections[1]["children"]], ["document_type_heading", "document_title", "issuing_authority_title"])
        self.assertEqual([n["type"] for n in sections[2]["children"]], ["legal_basis", "legal_basis", "proposal_basis"])
        self.assertEqual([n["type"] for n in sections[-1]["children"]], ["recipients", "signature"])
        signature = sections[-1]["children"][1]
        self.assertEqual([n["type"] for n in signature["children"]], ["delegation_title", "signer_title", "signature_status", "signer_name"])
        self.assertFalse(any(n["type"] == "table" for n in walk_content([result["document"]])))
        self.assertEqual(result["hierarchy_validation"]["legal_hierarchy"], {"parts": 0, "chapters": 0, "sections": 0, "subsections": 0, "articles": 3, "clauses": 2, "points": 0})
        self.assertEqual(result["hierarchy_validation"]["status"], "valid")
        self.assert_preserved(result)
        self.assertEqual(encoded(result), encoded(parse(html)))

    def test_full_stack_and_skipped_levels_do_not_depend_on_html_containers(self):
        html = ('<div><p>PHẦN II</p><p>CHƯƠNG I</p></div><div><p>MỤC 1</p>'
                '<p>TIỂU MỤC 2</p><p>Điều 5. Phạm vi điều chỉnh</p><p>1. Một</p></div>'
                '<section><p>a) A</p><p>đ) Đ</p><p>2. Hai</p><p>Điều 6. Khác.</p></section>')
        result = parse(html)
        part = body(result)["children"][0]
        chapter = part["children"][0]
        section = chapter["children"][0]
        subsection = section["children"][0]
        article = subsection["children"][0]
        self.assertEqual([n["type"] for n in (part, chapter, section, subsection, article)], ["part", "chapter", "section", "subsection", "article"])
        self.assertEqual([n["number"] for n in article["children"]], ["1", "2"])
        self.assertEqual([n["number"] for n in article["children"][0]["children"] if n["type"] == "point"], ["a", "đ"])
        self.assertEqual([n["number"] for n in subsection["children"]], ["5", "6"])
        self.assertEqual(result["hierarchy_validation"]["max_depth"], 8)
        self.assert_preserved(result)
        skipped = parse('<p>Chương II</p><p>Điều 5. Nội dung.</p>')
        self.assertEqual(body(skipped)["children"][0]["children"][0]["type"], "article")
        self.assert_preserved(skipped)

    def test_numbered_lists_outside_article_and_prose_lists_stay_generic(self):
        for html in ('<p>1. Một</p><p>2. Hai</p>',
                     '<p>Điều 1. Thực hiện các bước:</p><p>1. Một</p><p>2. Hai</p>',
                     '<p>Điều 1.</p><p>Các bước:</p><ol><li>Một</li><li>Hai</li></ol>',
                     '<p>Căn cứ ...</p><p>1. Một</p><p>2. Hai</p><p>QUYẾT ĐỊNH:</p><p>Điều 1.</p>'):
            with self.subTest(html=html):
                result = parse(html)
                self.assertEqual(result["hierarchy_validation"]["legal_hierarchy"]["clauses"], 0)
                self.assert_preserved(result)
        ambiguous = parse('<p>Điều 1. Các bước:</p><p>1. Một</p><p>2. Hai</p>')
        numbers = [n for n in walk_content([ambiguous["document"]]) if n["type"] == "numbered_paragraph"]
        self.assertEqual([n["number"] for n in numbers], ["1", "2"])
        self.assertTrue(all("candidate_role" not in n for n in numbers))
        decimal = parse('<p>Điều 1.</p><p>1.000 kg; 1.2; 10,5%</p>')
        self.assertEqual(decimal["hierarchy_validation"]["legal_hierarchy"]["clauses"], 0)
        self.assert_preserved(decimal)

    def test_orphans_are_preserved_without_fabricated_parents(self):
        result = parse('<p>Khoản 1. Một</p><p>a) A</p><p>Điều 2.</p><p>b) B</p>')
        self.assertEqual(result["hierarchy_validation"]["unresolved"]["orphan_nodes"], 3)
        self.assertEqual(result["hierarchy_validation"]["legal_hierarchy"]["articles"], 1)
        orphans = [n for n in walk_content([result["document"]]) if n.get("parent_status") == "unresolved"]
        self.assertEqual([n["type"] for n in orphans], ["clause", "point", "point"])
        self.assertEqual({i["code"] for i in result["issues"]}, {"orphan_clause", "orphan_point"})
        self.assert_preserved(result)

    def test_bare_clause_and_point_labels_keep_split_content_as_children(self):
        result = parse('<p>Điều 5:</p><p>1.</p><p>Nội dung khoản</p><p>đ)</p><p>Nội dung điểm</p>'
                       '<p>2) Nội dung khoản hai</p><p>a. Nội dung điểm a</p>')
        article = body(result)["children"][0]
        self.assertEqual([n["number"] for n in article["children"]], ["1", "2"])
        clause = article["children"][0]
        self.assertEqual([n["type"] for n in clause["children"]], ["paragraph", "point"])
        self.assertEqual(clause["children"][1]["number"], "đ")
        self.assertEqual(clause["children"][1]["children"][0]["text"], "Nội dung điểm")
        self.assert_preserved(result)

    def test_split_headings_merge_with_all_source_refs_and_notation(self):
        html = ('<p align="center">CHƯƠNG II</p><p align="center">PHẠM VI ÁP DỤNG</p>'
                '<p><b>Điều 5.</b></p><p><b>Giới hạn m<sup>2</sup></b></p>'
                '<p>1. Một</p><p>a) A</p>')
        result = parse(html)
        chapter = body(result)["children"][0]
        article = chapter["children"][0]
        for node, title in ((chapter, "PHẠM VI ÁP DỤNG"), (article, "Giới hạn m2")):
            self.assertEqual(node["title"], title)
            self.assertEqual(len(node["source_refs"]), 2)
            self.assertEqual(node["title_source_ref"], node["source_refs"][1])
        self.assertEqual(article["title_annotations"][0]["start"], 10)
        self.assert_preserved(result)
        self.assertEqual(encoded(result), encoded(parse(html)))

    def test_coalescing_requires_evidence_and_cannot_cross_a_boundary(self):
        cases = ('<p>Điều 5.</p><p>Áp dụng ngay hôm nay</p>',
                 '<div><p><b>Điều 5.</b></p></div><div><p><b>Phạm vi</b></p></div>',
                 '<p><b>Điều 5.</b></p><table><tr><th>Tên</th></tr><tr><td>A</td></tr></table><p><b>Phạm vi</b></p>',
                 '<p><b>Điều 5.</b></p><p>Căn cứ văn bản ...</p>')
        for html in cases:
            result = parse(html)
            article = body(result)["children"][0]
            self.assertIsNone(article["title"])
            self.assertNotIn("source_refs", article)
            self.assert_preserved(result)

    def test_nfd_labels_and_annotations_on_body_survive_splitting(self):
        heading = unicodedata.normalize("NFD", "Điều 01.")
        result = parse(f'<p>{heading} Có 2 kg/m<sup>2</sup>; CO<sub>2</sub>.</p>')
        article = body(result)["children"][0]
        self.assertEqual(article["label"] + article["label_suffix"], heading)
        self.assertIsNone(article["title"])
        paragraph = article["children"][0]
        self.assertEqual(paragraph["text"], "Có 2 kg/m2; CO2.")
        for annotation in paragraph["annotations"]:
            self.assertEqual(paragraph["text"][annotation["start"]:annotation["end"]], "2")
        self.assert_preserved(result)

    def test_inline_title_notation_uses_offsets_inside_the_title(self):
        result = parse('<p><b>Điều 1. Giới hạn m<sup>2</sup></b></p>')
        article = body(result)["children"][0]
        annotation = article["title_annotations"][0]
        self.assertEqual(article["title"][annotation["start"]:annotation["end"]], "2")
        self.assert_preserved(result)

    def test_all_enacting_formulas_and_missing_sections(self):
        for formula in ("QUYẾT ĐỊNH:", "NGHỊ ĐỊNH:", "QUYẾT NGHỊ:", "BAN HÀNH:"):
            result = parse(f'<p>Căn cứ Luật ...</p><p>{formula}</p><p>Điều 1. Thi hành.</p>')
            self.assertEqual([n["type"] for n in result["document"]["children"]], ["preamble", "enacting_formula", "body"])
            self.assert_preserved(result)
        for html in ('<p>BAN HÀNH:</p><p>Đoạn khác</p>', '<p>BAN HÀNH:</p><p>1. Đoạn khác</p>'):
            uncertain = parse(html)
            self.assertFalse(any(n["type"] == "enacting_formula" for n in walk_content([uncertain["document"]])))
            self.assert_preserved(uncertain)

    def test_data_table_stays_under_active_point_without_inheriting_cell_counters(self):
        html = ('<p>Điều 1.</p><p>1. Một</p><p>a) A</p><table><caption>Bảng 1</caption>'
                '<tr><th>Tên</th></tr><tr><td><p>1. Dòng</p><p>2. Dòng</p></td></tr></table>'
                '<p>b) B</p><p>2. Hai</p>')
        result = parse(html)
        article = body(result)["children"][0]
        point = article["children"][0]["children"][1]
        table = point["children"][1]
        self.assertEqual(table["type"], "table")
        self.assertEqual(table["table_kind"], "data")
        self.assertEqual(result["hierarchy_validation"]["legal_hierarchy"]["clauses"], 2)
        self.assertEqual(result["hierarchy_validation"]["legal_hierarchy"]["points"], 2)
        self.assertEqual([n["number"] for n in article["children"]], ["1", "2"])
        self.assert_preserved(result)

    def test_list_legal_context_ends_at_the_list_boundary(self):
        result = parse('<p>Điều 1.</p><ol><li><p>1. Một</p><ol type="a"><li>a) A</li></ol></li>'
                       '<li>2. Hai</li></ol><table><tr><th>Tên</th></tr><tr><td>A</td></tr></table>'
                       '<p>a) Điểm thiếu khoản</p>')
        article = body(result)["children"][0]
        self.assertEqual([n["type"] for n in article["children"]], ["list", "table", "point"])
        self.assertEqual(article["children"][-1]["parent_status"], "unresolved")
        self.assert_preserved(result)

    def test_validator_rejects_lost_provenance_reparented_table_and_dual_representation(self):
        html = ('<p><b>Điều 1.</b></p><p><b>Phạm vi</b></p><p>1. Một</p>'
                '<table><tr><th>Tên</th></tr><tr><td>A</td></tr></table>')
        result = parse(html)
        broken = deepcopy(result)
        article = body(broken)["children"][0]
        article["source_refs"].pop()
        quality = Quality()
        validate_result(broken, "vbpl:1", quality)
        self.assertIn("invalid_provenance", {i["code"] for i in quality.issues})
        self.assertEqual(broken["hierarchy_validation"]["status"], "invalid")
        broken = deepcopy(result)
        article = body(broken)["children"][0]
        table = article["children"][0]["children"].pop()
        body(broken)["children"].append(table)
        quality = Quality()
        validate_result(broken, "vbpl:1", quality)
        self.assertIn("invalid_table_parent", {i["code"] for i in quality.issues})
        self.assertEqual(broken["hierarchy_validation"]["status"], "invalid")
        broken = deepcopy(result)
        broken["content"] = []
        self.assertTrue(list(schema_validator().iter_errors(broken)))

    def test_validator_rejects_article_under_clause_and_resolved_point_without_clause(self):
        result = parse('<p>Điều 1.</p><p>1. Một</p><p>Điều 2.</p><p>a) A</p>')
        broken = deepcopy(result)
        first, second = body(broken)["children"]
        body(broken)["children"].pop()
        first["children"][0]["children"].append(second)
        second["children"][0].pop("parent_status")
        quality = Quality()
        validate_result(broken, "vbpl:1", quality)
        self.assertIn("invalid_parent", {i["code"] for i in quality.issues})
        self.assertEqual(broken["hierarchy_validation"]["status"], "invalid")

    def test_hierarchy_validator_rechecks_text_after_a_subtree_is_removed(self):
        result = parse('<p>Điều 1.</p><p>1. Nội dung quan trọng</p>')
        body(result)["children"][0]["children"] = []
        quality = Quality()
        validate_result(result, "vbpl:1", quality)
        self.assertFalse(result["validation"]["meaningful_text_preserved"])
        self.assertEqual(result["hierarchy_validation"]["status"], "invalid")
        self.assertIn("semantic_text_mismatch", {i["code"] for i in quality.issues})


class DocumentNumberRoleTests(unittest.TestCase):
    def test_primary_number_is_only_the_leading_deterministic_citation(self):
        text = ('Nghị quyết số 15/2026/NQ-CP về Nghị định số 46/2026/NĐ-CP '
                'và Nghị quyết số 66.13/2026/NQ-CP')
        self.assertEqual(document_number_roles(text), {"primary_document_number_candidate": "15/2026/NQ-CP", "mentioned_document_numbers": ["46/2026/NĐ-CP", "66.13/2026/NQ-CP"]})
        for text in ("Quyết định 16111/QĐ-BCT sửa Thông tư số 11/2026/TT-BCT", "Tạm ngưng Thông tư số 11/2026/TT-BCT"):
            result = document_number_roles(text)
            self.assertIsNone(result["primary_document_number_candidate"])
            self.assertTrue(result["mentioned_document_numbers"])
            self.assertNotIn("document_number_candidates", result)

    def test_history_and_relations_extract_primary_and_mentions(self):
        title = "Quyết định số 16111/QĐ-BCT về Thông tư số 11/2026/TT-BCT"
        history = parse('<table><tr><th>Thời gian</th><th>Trạng thái</th><th>Văn bản nguồn</th></tr>'
                        f'<tr><td>01/07/2026</td><td>Hiệu lực</td><td>{title}</td></tr></table>', "history")
        relation = parse(f'<div>Căn cứ (1)<ul><li>{title}</li></ul></div>', "relations")
        for item in (history["events"][0]["source_document"], relation["groups"][0]["items"][0]):
            self.assertEqual(item["primary_document_number_candidate"], "16111/QĐ-BCT")
            self.assertEqual(item["mentioned_document_numbers"], ["11/2026/TT-BCT"])
        self.assertEqual(relation["groups"][0]["items"][0]["resolution_status"], "candidate_only")
        self.assertEqual(relation["issue_summary"]["warning"], 0)
        self.assertTrue(history["validation"]["meaningful_text_preserved"])
        self.assertTrue(relation["validation"]["meaningful_text_preserved"])

    def test_unidentified_relation_and_count_mismatch_warn_but_candidates_do_not(self):
        cases = (("Văn bản chưa rõ", "unresolved_document_reference"),
                 ("11/2026/TT-BCT", None))
        for title, code in cases:
            result = parse(f'<div>Căn cứ (1)<ul><li>{title}</li></ul></div>', "relations")
            codes = {i["code"] for i in result["issues"]}
            if code:
                self.assertIn(code, codes)
            else:
                self.assertNotIn("unresolved_document_reference", codes)
                self.assertEqual(result["groups"][0]["items"][0]["resolution_status"], "candidate_only")
        mismatch = parse('<div>Căn cứ (2)<ul><li>Luật số 01/2026/QH15</li></ul></div>', "relations")
        self.assertEqual({i["code"] for i in mismatch["issues"]}, {"relation_count_mismatch"})


if __name__ == "__main__":
    unittest.main()
