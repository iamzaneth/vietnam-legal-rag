"""ValidatorTests for the extraction pipeline."""
from copy import deepcopy
import unittest
from vietnam_legal_rag.ingestion.validation.quality import Quality
from vietnam_legal_rag.ingestion.validation.extract import validate_result, validate_table
from vietnam_legal_rag.ingestion.html.source import parse_html
from tests.support import metadata_tab as tab


class ValidatorTests(unittest.TestCase):
    @staticmethod
    def rectangle_table(rectangles):
        cells = []
        for i, (row, column, rowspan, colspan) in enumerate(rectangles):
            cells.append({'row': row, 'column': column, 'rowspan': rowspan, 'colspan': colspan,
                          'order': i, 'cell_id': f'cell_{i}', 'text': '', 'effective_text': '',
                          'source_ref': {'tag': 'td', 'dom_order': i, 'line': 1, 'column': i}})
        return {'cells': cells, 'table_kind': 'data', 'source_ref': {'tag': 'table', 'dom_order': 999}}

    def test_table_overlap_validation_does_not_rescan_expired_cells(self):
        class CountedCells(list):
            sliced = 0

            def __getitem__(self, key):
                value = super().__getitem__(key)
                if isinstance(key, slice):
                    self.sliced += len(value)
                return value

        table = self.rectangle_table([(row, column, 1, 1) for row in range(100) for column in range(4)])
        table['cells'] = CountedCells(table['cells'])
        quality = Quality()
        validate_table(table, quality)
        self.assertFalse(quality.issues)
        self.assertLessEqual(table['cells'].sliced, len(table['cells']))

    def test_table_overlap_sweep_preserves_naive_diagnostics_for_unordered_spans(self):
        import random
        rng = random.Random(17)
        for _ in range(30):
            rectangles = [(rng.randrange(12), rng.randrange(8), rng.randrange(1, 5), rng.randrange(1, 4))
                          for _ in range(35)]
            expected = []
            for i, (r, c, rs, cs) in enumerate(rectangles):
                if any(r < pr + prs and pr < r + rs and c < pc + pcs and pc < c + cs
                       for pr, pc, prs, pcs in rectangles[:i]):
                    expected.append(i)
            table = self.rectangle_table(rectangles)
            quality = Quality()
            validate_table(table, quality)
            self.assertEqual([issue['source_ref']['dom_order'] for issue in quality.issues
                              if issue['code'] == 'table_grid_overlap'], expected)
            previous = deepcopy(quality.issues)
            validate_table(table, quality)
            self.assertEqual(quality.issues, previous)

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
