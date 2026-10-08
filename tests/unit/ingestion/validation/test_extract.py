"""ValidatorTests for the extraction pipeline."""
from copy import deepcopy
import unittest
from vietnam_legal_rag.ingestion.validation.quality import Quality
from vietnam_legal_rag.ingestion.validation.extract import validate_result
from vietnam_legal_rag.ingestion.html.source import parse_html
from tests.support import metadata_tab as tab


class ValidatorTests(unittest.TestCase):
    def test_validator_detects_missing_text_from_actual_output(self):
        html='<p>Điều 1. Áp dụng</p><p>Nội dung quan trọng</p>'; result=tab(html,'content')
        result['document']['children'][0]['children']=[]
        quality=Quality(); evidence=quality.conservation(parse_html(html),result)
        self.assertFalse(evidence['meaningful_text_preserved'])
        self.assertEqual(quality.issues[0]['severity'],'fatal')

    def test_validator_detects_identity_schema_order_parent_and_duplicates(self):
        result=tab('<p>Điều 1. A</p><p>Điều 2. B</p>','content')
        broken=deepcopy(result); broken['document_id']='other'; broken['source_ref']['sha256']='bad'
        nodes=broken['document']['children'][0]['children']
        nodes.reverse(); nodes.append(deepcopy(nodes[0]))
        nodes.append({'type':'clause','number':'1','title':None,'text':'1. Orphan','order':999,'children':[],'source_ref':{'dom_order':999}})
        quality=Quality(); validate_result(broken,'vbpl:99',quality)
        self.assertTrue({'invalid_document_id','invalid_source_ref','invalid_order','invalid_parent','duplicate_semantic_block','invalid_schema'} <= {i['code'] for i in quality.issues})

    def test_empty_content_is_fatal_and_info_does_not_change_status(self):
        result=tab('<p>&nbsp;</p>','content')
        self.assertEqual(result['status'],'failed')
        self.assertIn(('fatal','source_content_missing'),{(i['severity'],i['code']) for i in result['issues']})


if __name__ == "__main__":
    unittest.main()
