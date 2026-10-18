"""Pinned real captures complement the portable source-pattern regressions."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from vietnam_legal_rag.ingestion.extract_legal_documents import extract_document
from vietnam_legal_rag.ingestion.validation.extract import schema_validator, walk, walk_content

from tests.support import ROOT
CORPUS = json.loads((ROOT / 'tests/fixtures/vbpl_batch_regressions.json').read_text())


class BatchCaptureRegressionTests(unittest.TestCase):
    corpus = CORPUS

    def test_promoted_captures_preserve_reviewed_structure_and_source_ambiguities(self):
        for case in self.corpus['documents']:
            with self.subTest(document_id=case['document_id']):
                raw = ROOT / case['raw_directory']
                if not raw.is_dir():
                    self.skipTest('Immutable batch RAW captures are not available locally')
                for record in case['source_files']:
                    source = raw / record['path']
                    self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), record['sha256'])
                with tempfile.TemporaryDirectory() as temporary:
                    output = Path(temporary) / raw.name
                    manifest = extract_document(raw, output)
                    self.assertEqual(manifest['quality'], case['expected']['quality'])
                    self.assertEqual(manifest['issue_summary']['error'], 0)
                    self.assertEqual(manifest['issue_summary']['fatal'], 0)
                    content = json.loads((output / 'content.json').read_text())
                    for key in ('legal_hierarchy', 'annex_hierarchy'):
                        self.assertEqual(content['hierarchy_validation'][key], case['expected'][key])
                    counts = Counter(n['type'] for n in walk_content([content['document']]))
                    self.assertEqual({k: counts[k] for k in case['expected']['node_types']}, case['expected']['node_types'])
                    for anchor in case['expected'].get('source_nodes', []):
                        matches = [(node, ancestors) for node, ancestors in walk([content['document']])
                                   if node['source_ref']['dom_order'] == anchor['source_order'] and
                                   node['type'] == anchor['type'] and
                                   ('source_offset' not in anchor or node.get('source_offset', 0) == anchor['source_offset'])]
                        self.assertEqual(len(matches), 1, anchor)
                        node, ancestors = matches[0]
                        for key, value in anchor.get('properties', {}).items():
                            self.assertEqual(node.get(key), value, anchor)
                        if 'ancestor_source_order' in anchor:
                            self.assertTrue(any(a.get('source_ref', {}).get('dom_order') ==
                                                anchor['ancestor_source_order'] for a in ancestors), anchor)
                        for excluded in anchor.get('excluded_ancestor_types', []):
                            self.assertFalse(any(a.get('type') == excluded for a in ancestors), anchor)
                        for excluded in anchor.get('excluded_ancestor_source_orders', []):
                            self.assertFalse(any(a.get('source_ref', {}).get('dom_order') == excluded
                                                 for a in ancestors), anchor)
                        if pattern := anchor.get('excluded_ancestor_number_pattern'):
                            self.assertFalse(any(re.fullmatch(pattern, a.get('number') or '')
                                                 for a in ancestors), anchor)
                    warnings = Counter()
                    for path in output.glob('*.json'):
                        artifact = json.loads(path.read_text())
                        schema_validator().validate(artifact)
                        warnings.update(i['code'] for i in artifact.get('issues', []) if i['severity'] == 'warning')
                    self.assertEqual(dict(warnings), case['expected']['warning_codes'])


class HardeningCaptureRegressionTests(BatchCaptureRegressionTests):
    corpus = json.loads((ROOT / 'tests/fixtures/vbpl_hardening_regressions.json').read_text())


if __name__ == '__main__':
    unittest.main()
