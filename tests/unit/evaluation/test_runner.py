"""Configured runs must preserve sample membership and explicit quotas."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vietnam_legal_rag.evaluation.config import ValidationConfig
from vietnam_legal_rag.evaluation.validation_runner import crawl_wave, load_state
from vietnam_legal_rag.ingestion.crawl_legal_documents import CrawlError
from vietnam_legal_rag.evaluation.wave_gate import baseline_documents, check_acquisition_gate, complete_wave, validation_failures
from vietnam_legal_rag.evaluation.audit.extract import audit_physical_tables
from vietnam_legal_rag.ingestion.html.source import parse_html
from tests.support import parse_forms, nodes


class ValidationRunnerTests(unittest.TestCase):
    def test_archived_manifest_locator_rejects_ambiguous_member_paths(self):
        from vietnam_legal_rag.evaluation.wave_gate import read_manifest
        for locator in ('history.zip!/', 'history.zip!/../state.json', 'history.zip!//state.json'):
            with self.subTest(locator=locator), self.assertRaisesRegex(CrawlError, 'Invalid archived'):
                read_manifest(locator)

    def test_first_progress_uses_configured_target_without_assuming_milestone_size(self):
        from vietnam_legal_rag.evaluation.validation_runner import save_state
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = ValidationConfig(batch_size=12, report_dir=root, progress_dir=root,
                                      sample_manifest=root / 'selected.json')
            state = {'documents': [{'document_id': 'vbpl:1'}]}
            save_state(state, config)
            progress = json.loads((root / 'evidence/state.json').read_text())
            self.assertEqual(progress['target_total'], 12)
            self.assertEqual(progress['target_manifest_pending_ids'], ['vbpl:1'])

    def test_dns_failure_persists_environment_classification_and_stops_collection(self):
        import socket
        from urllib.error import URLError
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = ValidationConfig(batch_size=1, wave_size=1, central_target=1,
                                      sample_manifest=root / 'sample.json', raw_dir=root / 'raw')
            candidate = {'url': 'https://vbpl.vn/van-ban/chi-tiet/luat--9'}
            with patch('vietnam_legal_rag.evaluation.validation_runner.choose_candidate', return_value=candidate), \
                    patch('vietnam_legal_rag.evaluation.validation_runner.robots',
                          side_effect=URLError(socket.gaierror(-3, 'Temporary failure in name resolution'))) as network, \
                    patch('vietnam_legal_rag.evaluation.validation_runner.time.sleep'):
                with self.assertRaisesRegex(CrawlError, 'environment.*DNS'):
                    crawl_wave(1, 'chrome', 30, config)
            self.assertEqual(network.call_count, 1)
            state = load_state(config)
            self.assertEqual(state['documents'], [])
            self.assertEqual(len(state['attempts']), 1)
            self.assertEqual(state['attempts'][0]['failure_classification'], 'execution_environment_network_failure')
            self.assertEqual(state['attempts'][0]['result'], 'failed')
            self.assertIn('completed_at', state['attempts'][0])

    def test_crawl_wave_reuses_complete_local_raw_before_network(self):
        from tests.unit.evaluation.test_local_inventory import LocalInventoryTests
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture = LocalInventoryTests().complete_capture(root, 'trung_uong', '9')
            before = {p.name: p.read_bytes() for p in capture.iterdir()}
            evidence = root / 'report/evidence'
            evidence.mkdir(parents=True)
            (evidence / 'state.json').write_text(json.dumps({'target_total': 500}))
            config = ValidationConfig(batch_size=1, wave_size=1, central_target=1,
                                      sample_manifest=root / 'sample.json', raw_dir=root / 'raw',
                                      extracted_dir=root / 'extracted', report_dir=root / 'report',
                                      progress_dir=root / 'report', inventory=root / 'missing-inventory.jsonl')
            with patch('vietnam_legal_rag.evaluation.validation_runner.robots') as policy, \
                    patch('vietnam_legal_rag.evaluation.validation_runner.capture') as network, \
                    patch('vietnam_legal_rag.evaluation.validation_runner.time.sleep'):
                crawl_wave(1, 'chrome', 30, config)
                policy.assert_not_called()
                network.assert_not_called()
            state = load_state(config)
            self.assertEqual(state['documents'][0]['document_id'], 'vbpl:9')
            self.assertEqual(state['attempts'][0]['result'], 'existing_capture')
            self.assertEqual({p.name: p.read_bytes() for p in capture.iterdir()}, before)

    def test_scope_prefix_preserves_prior_order_and_fills_remaining_quotas(self):
        config = ValidationConfig(batch_size=6, central_target=3,
                                  scope_prefix=('trung_uong', 'dia_phuong', 'dia_phuong'))
        self.assertEqual(config.expected_scopes(), ['trung_uong', 'dia_phuong', 'dia_phuong',
                                                    'trung_uong', 'dia_phuong', 'trung_uong'])

    def test_scope_prefix_cannot_falsify_scope_or_exceed_quota(self):
        for prefix in [('trung_uong', 'trung_uong'), ('unknown',)]:
            with self.subTest(prefix=prefix), self.assertRaisesRegex(ValueError, 'scope prefix'):
                ValidationConfig(batch_size=3, central_target=1, scope_prefix=prefix)

    def test_total_raw_target_stops_crawl_before_any_network_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); evidence = root / 'evidence'; evidence.mkdir()
            progress = evidence / 'state.json'
            progress.write_text(json.dumps({'target_total': 500}))
            config = ValidationConfig(batch_size=20, sample_manifest=root / 'sample.json', progress_dir=root)
            inventory = {'local_raw_distinct_total': 500,
                         'documents': [{'document_id': f'vbpl:{i}'} for i in range(500)]}
            with patch('vietnam_legal_rag.evaluation.local_inventory.inventory_raw', return_value=inventory), \
                    patch('vietnam_legal_rag.evaluation.validation_runner.robots') as network:
                crawl_wave(1, 'chrome', 30, config)
                network.assert_not_called()
            self.assertEqual(json.loads(progress.read_text())['current_local_distinct_raw_count'], 500)
            self.assertEqual(json.loads(progress.read_text())['documents_needed'], 0)

    def test_partial_subrun_cannot_complete_wave_before_overall_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / 'evidence'; evidence.mkdir()
            (evidence / 'state.json').write_text(json.dumps({'target_total': 500, 'target_assembled_documents': 183}))
            config = ValidationConfig(batch_size=12, wave_size=20, progress_dir=root)
            with patch('vietnam_legal_rag.evaluation.validation_runner.load_state',
                       return_value={'documents': [{} for _ in range(12)]}):
                with self.assertRaisesRegex(CrawlError, 'Partial wave'):
                    complete_wave(1, config)

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
        self.assertEqual(config.report_dir, Path('reports/validation'))
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

    def test_acquisition_requires_previous_wave_gate_with_current_parser(self):
        config = ValidationConfig(batch_size=100, wave_size=20, require_wave_gates=True)
        state = {'documents': [{}] * 20}
        with patch('vietnam_legal_rag.evaluation.wave_gate.parser_fingerprint', return_value='current'):
            with self.assertRaisesRegex(CrawlError, 'Previous wave'):
                check_acquisition_gate(2, state, config)
            state['wave_completions'] = [{'wave': 1, 'new_documents': 20, 'parser_fingerprint': 'old', 'baseline_manifests': []}]
            with self.assertRaisesRegex(CrawlError, 'current parser'):
                check_acquisition_gate(2, state, config)
            state['wave_completions'][0]['parser_fingerprint'] = 'current'
            check_acquisition_gate(2, state, config)
            with self.assertRaises(CrawlError):
                check_acquisition_gate(3, state, config)

    def test_baseline_membership_is_read_only_and_rejects_overlap(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'baseline.json'
            original = {'documents': [{'document_id': 'vbpl:9', 'url': 'https://vbpl.vn/doc--9',
                                      'raw_directory': 'raw/9', 'document_scope': 'trung_uong'}]}
            path.write_text(json.dumps(original))
            before = path.read_bytes()
            self.assertEqual(baseline_documents(ValidationConfig(baseline_manifests=(path,))), original['documents'])
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaisesRegex(CrawlError, 'Duplicate'):
                baseline_documents(ValidationConfig(baseline_manifests=(path, path)))

    def test_source_warning_does_not_hide_integrity_or_semantic_failure(self):
        validation = {'audit_errors': [], 'quality': {'schema_valid': True, 'deterministic': True,
                      'meaningful_text_preserved': True, 'semantic_complete': False},
                      'issue_summary': {'warning': 1, 'error': 0, 'fatal': 0},
                      'hierarchy': {'unresolved': {'numbered_candidates': 0, 'orphan_nodes': 0}},
                      'forms': dict.fromkeys(('unexplained_structured_paragraphs', 'unexplained_form_label_paragraphs',
                          'suspicious_value_text', 'semantic_empty_string_fields', 'form_nodes_missing_field_kind',
                          'form_nodes_missing_field_evidence', 'unresolved_numbered_form_items', 'split_form_candidates',
                          'inconsistent_footnote_sequences', 'bibliography_fields_misclassified'), 0)}
        self.assertEqual(validation_failures(validation), [])
        validation['forms']['unexplained_structured_paragraphs'] = 1
        self.assertIn('unresolved form/list semantics', validation_failures(validation))
        validation['quality']['deterministic'] = False
        self.assertIn('deterministic', validation_failures(validation))

    def test_independent_physical_audit_rejects_changed_span_and_invented_cell_text(self):
        html = '<p>Điều 1. Bảng</p><table><tr><td rowspan="2">A</td><td>100</td></tr><tr><td>200</td></tr></table>'
        result = parse_forms(html)
        self.assertEqual(audit_physical_tables(parse_html(html), result), [])
        cell = nodes(result, 'table')[0]['cells'][0]
        cell['original_rowspan'] = '3'
        cell['effective_text'] = 'Invented'
        errors = audit_physical_tables(parse_html(html), result)
        self.assertIn('Physical source span attribute changed', errors)
        self.assertIn('Effective cell text differs from physical source text', errors)


if __name__ == '__main__':
    unittest.main()
