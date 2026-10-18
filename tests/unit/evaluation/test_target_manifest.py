"""Total-corpus counting includes source identities once, preserving extras."""
from copy import deepcopy
import unittest

from vietnam_legal_rag.evaluation.target_manifest import assemble_target


class TargetManifestTests(unittest.TestCase):
    def inventory(self, count):
        return {'local_raw_distinct_total': count, 'documents': [
            {'document_id': f'vbpl:{i}', 'usable': True, 'capture_path': f'raw/{i}',
             'source_url': f'https://vbpl.vn/doc--{i}', 'source_scope': 'trung_uong' if i % 2 else 'dia_phuong',
             'roles': []} for i in range(count)]}

    def test_existing_roles_count_once_and_extras_remain_untouched(self):
        inventory = self.inventory(12)
        before = deepcopy(inventory)
        target = assemble_target(inventory, 8, [{'document_id': 'vbpl:0', 'origin': 'golden'},
                                               {'document_id': 'vbpl:9', 'origin': 'previous_validation'}])
        self.assertTrue(target['complete'])
        self.assertEqual(target['assembled_documents'], 8)
        self.assertEqual(target['local_documents_outside_target'], 4)
        self.assertEqual(len({d['document_id'] for d in target['documents']}), 8)
        self.assertIn('vbpl:9', [d['document_id'] for d in target['documents']])
        self.assertEqual(inventory, before)
        self.assertEqual(target, assemble_target(inventory, 8, [{'document_id': 'vbpl:0', 'origin': 'golden'},
                                                              {'document_id': 'vbpl:9', 'origin': 'previous_validation'}]))

    def test_unavailable_deficit_is_reported_without_padding(self):
        target = assemble_target(self.inventory(3), 5, [{'document_id': 'vbpl:0'}])
        self.assertFalse(target['complete'])
        self.assertEqual(target['documents_needed'], 2)
        self.assertEqual(target['assembled_documents'], 3)

    def test_duplicate_required_roles_and_missing_source_are_rejected(self):
        for required in ([{'document_id': 'vbpl:0'}] * 2, [{'document_id': 'vbpl:99'}]):
            with self.subTest(required=required), self.assertRaises(ValueError):
                assemble_target(self.inventory(3), 5, required)
