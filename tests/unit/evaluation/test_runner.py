"""Configured runs must preserve sample membership and explicit quotas."""
import json
from pathlib import Path
import tempfile
import unittest

from vietnam_legal_rag.evaluation.config import ValidationConfig
from vietnam_legal_rag.evaluation.validation_runner import load_state
from vietnam_legal_rag.ingestion.crawl_legal_documents import CrawlError


class ValidationRunnerTests(unittest.TestCase):
    def test_new_state_uses_configured_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = ValidationConfig(batch_size=12, sample_manifest=Path(temporary) / 'state.json')
            self.assertEqual(load_state(config)['target'], 12)
            self.assertEqual(load_state(config)['scope_targets'], {'trung_uong': 6, 'dia_phuong': 6})

    def test_existing_state_requires_matching_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / 'state.json'
            original = {'target': 50, 'documents': [{'document_id': 'vbpl:99', 'document_scope': 'trung_uong'}]}
            state.write_text(json.dumps(original))
            with self.assertRaises(CrawlError):
                load_state(ValidationConfig(batch_size=12, sample_manifest=state))
            self.assertEqual(json.loads(state.read_text()), original)

    def test_matching_state_preserves_selected_sample(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / 'state.json'
            original = {'target': 50, 'documents': [{'document_id': 'vbpl:99', 'document_scope': 'trung_uong'}]}
            state.write_text(json.dumps(original))
            self.assertEqual(load_state(ValidationConfig(sample_manifest=state)), original)

    def test_odd_and_unbalanced_targets(self):
        self.assertEqual(ValidationConfig(batch_size=3).expected_scopes(), ['trung_uong', 'dia_phuong', 'trung_uong'])
        self.assertEqual(ValidationConfig(batch_size=5, local_target=1).expected_scopes(),
                         ['trung_uong', 'dia_phuong', 'trung_uong', 'trung_uong', 'trung_uong'])
        self.assertEqual(ValidationConfig(batch_size=2, central_target=0).expected_scopes(), ['dia_phuong'] * 2)

    def test_invalid_quota_totals_and_wave_sizes_are_rejected(self):
        for values in ({'batch_size': 0}, {'wave_size': 0}, {'central_target': -1},
                       {'batch_size': 4, 'central_target': 2, 'local_target': 1}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                ValidationConfig(**values)

    def test_default_paths_follow_batch_size(self):
        config = ValidationConfig(batch_size=12, wave_size=5)
        self.assertEqual(config.report_dir, Path('reports/extract-validation-12'))
        self.assertEqual(config.sample_manifest, config.report_dir / 'evidence/state.json')
        self.assertEqual(config.waves, 3)

    def test_existing_state_cannot_change_scope_quotas(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / 'state.json'
            original = {'target': 3, 'scope_targets': {'trung_uong': 2, 'dia_phuong': 1}, 'documents': []}
            state.write_text(json.dumps(original))
            with self.assertRaises(CrawlError):
                load_state(ValidationConfig(batch_size=3, local_target=0, sample_manifest=state))
            self.assertEqual(json.loads(state.read_text()), original)


if __name__ == '__main__':
    unittest.main()
