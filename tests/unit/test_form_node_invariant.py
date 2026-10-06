"""Both source-backed form node families carry the same explicit contract."""
from copy import deepcopy
import unittest

from test_form_refinement import nodes, parse
from vietnam_legal_rag.ingestion.extract_legal_documents import encoded
from vietnam_legal_rag.ingestion.extract_quality import Quality
from vietnam_legal_rag.ingestion.extract_validation import schema_validator
from vietnam_legal_rag.ingestion.form_validation import FORM_NODE_PROPERTIES, validate_forms, walk
from vietnam_legal_rag.ingestion.schema_cleanup import clean_contract


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


if __name__=='__main__':
    unittest.main()
