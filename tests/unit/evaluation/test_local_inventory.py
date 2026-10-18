"""Count source documents once and reject unverified capture evidence."""
import json
from pathlib import Path
import tempfile
import unittest

from tests.support import create_raw
from vietnam_legal_rag.evaluation.local_inventory import inventory_raw


class LocalInventoryTests(unittest.TestCase):
    def complete_capture(self, root, scope, name):
        raw = create_raw(root, scope, name)
        path = raw / 'manifest.json'
        m = json.loads(path.read_text())
        m.update(status='complete', source_url='https://vbpl.vn/van-ban/chi-tiet/document--' + name,
                 validation={'content_stable': True, 'metadata_tabs_complete': True},
                 tabs={k: {'status': 'complete', 'files': [k + '.html']} for k in ('content', 'properties', 'history', 'relations')})
        path.write_text(json.dumps(m))
        return raw

    def test_same_document_in_multiple_roles_paths_or_scopes_counts_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.complete_capture(root, 'trung_uong', '9')
            self.complete_capture(root, 'dia_phuong', '9')
            result = inventory_raw(root / 'raw', {'vbpl:9': ['golden', 'baseline']})
            self.assertEqual(result['local_raw_distinct_total'], 1)
            self.assertEqual(result['usable_capture_total'], 2)
            self.assertEqual(result['duplicate_capture_total'], 1)
            self.assertEqual(len(result['documents'][0]['roles']), 2)

    def test_corrupt_missing_or_unfinished_capture_does_not_fill_deficit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = self.complete_capture(root, 'trung_uong', '9')
            (raw / 'content.html').write_text('Changed source')
            result = inventory_raw(root / 'raw')
            self.assertEqual(result['local_raw_distinct_total'], 0)
            self.assertIn('source hash/size mismatch: content.html', result['captures'][0]['issues'])

    def test_manifest_url_identity_conflict_remains_reviewable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = self.complete_capture(root, 'trung_uong', '9')
            path = raw / 'manifest.json'
            m = json.loads(path.read_text());m['source_url'] = 'https://vbpl.vn/van-ban/chi-tiet/document--10'
            path.write_text(json.dumps(m))
            result = inventory_raw(root / 'raw')
            self.assertEqual(result['local_raw_distinct_total'], 0)
            self.assertIn('manifest/URL identity conflict', result['captures'][0]['issues'])

    def test_unpublished_staging_directory_does_not_count_as_usable_raw(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / '.crawl-interrupted' / 'document').mkdir(parents=True)
            result = inventory_raw(root)
            self.assertEqual(result['local_raw_distinct_total'], 0)
            self.assertEqual(result['unusable_capture_total'], 1)
            self.assertFalse(result['captures'][0]['manifest_valid'])
