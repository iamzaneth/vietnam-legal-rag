"""Pinned real captures complement the portable source-pattern regressions."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from vietnam_legal_rag.ingestion.extract_legal_documents import extract_document
from vietnam_legal_rag.ingestion.extract_validation import schema_validator, walk_content

ROOT = Path(__file__).resolve().parents[2]
CORPUS = json.loads((ROOT / 'tests/fixtures/vbpl_batch_regressions.json').read_text())


class BatchCaptureRegressionTests(unittest.TestCase):
    def test_promoted_captures_preserve_reviewed_structure_and_source_ambiguities(self):
        for case in CORPUS['documents']:
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
                    warnings = Counter()
                    for path in output.glob('*.json'):
                        artifact = json.loads(path.read_text())
                        schema_validator().validate(artifact)
                        warnings.update(i['code'] for i in artifact.get('issues', []) if i['severity'] == 'warning')
                    self.assertEqual(dict(warnings), case['expected']['warning_codes'])


if __name__ == '__main__':
    unittest.main()
