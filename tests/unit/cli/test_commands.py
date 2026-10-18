"""CLI dispatch, configuration forwarding and preservation of legacy adapters."""
import contextlib
import io
import json
import tempfile
import zipfile
from pathlib import Path
import unittest
from unittest.mock import patch

from vietnam_legal_rag.cli.__main__ import main
from vietnam_legal_rag.cli import audit, validate


class ToolingCLITests(unittest.TestCase):
    def test_canonical_defaults_resolve_saved_sample_baselines_and_total_report(self):
        from vietnam_legal_rag.evaluation.validation_runner import load_state
        from vietnam_legal_rag.evaluation.wave_gate import baseline_documents
        with tempfile.TemporaryDirectory() as temporary, contextlib.chdir(temporary):
            root = Path('reports/validation')
            evidence = root / 'evidence'
            evidence.mkdir(parents=True)
            baseline_member = 'reports/original/evidence/state.json'
            baseline_locator = str(root / 'history.zip') + '!/' + baseline_member
            baseline = [{'document_id': 'vbpl:' + str(i), 'url': 'url:' + str(i),
                         'raw_directory': 'raw/' + str(i), 'document_scope': 'trung_uong'}
                        for i in range(1, 151)]
            with zipfile.ZipFile(root / 'history.zip', 'w') as history:
                history.writestr(baseline_member, json.dumps({'documents': baseline}))
            scopes = ['trung_uong', 'dia_phuong'] * 170 + ['trung_uong'] * 9
            selected = [{'document_id': 'vbpl:' + str(i + 151), 'document_scope': scope}
                        for i, scope in enumerate(scopes)]
            state = {'target': 349, 'scope_targets': {'trung_uong': 179, 'dia_phuong': 170},
                     'documents': selected, 'baseline_validations': baseline,
                     'run_configuration': {'wave_size': 20, 'require_wave_gates': True,
                                           'baseline_manifests': [baseline_locator],
                                           'scope_prefix': scopes}}
            (evidence / 'state.json').write_text(json.dumps({'target_total': 500}))
            (evidence / 'corpus_validation_state.json').write_text(json.dumps(state))
            (evidence / 'target_manifest.json').write_text(json.dumps({
                'target_total': 500, 'documents': [{'document_id': 'vbpl:' + str(i)} for i in range(1, 500)] +
                [{'document_id': 'vbpl:a9bea550-bbe3-11f1-a338-51a5cc429fc7'}]}))
            (evidence / 'cumulative_reviews.json').write_text(json.dumps({'documents': []}))

            def audit_config(regenerate, config):
                loaded = load_state(config)
                previous = baseline_documents(config)
                self.assertEqual(config.batch_size, 349)
                self.assertEqual(config.wave_size, 20)
                self.assertTrue(config.require_wave_gates)
                self.assertEqual(config.scope_prefix, tuple(scopes))
                # The actual audit includes saved baselines plus the golden,
                # never just the last selected subrun.
                self.assertEqual(len(loaded['documents']) + len(previous) + 1, 500)
                self.assertEqual(previous, baseline)
                self.assertFalse(regenerate)
                return 0

            with patch.object(validate.runner, 'audit_wave', side_effect=audit_config):
                self.assertEqual(main(['validate', 'audit']), 0)
            output = Path('rebuilt')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['validate', 'report', '--output-dir', str(output)]), 0)
            report = json.loads((output / 'report.json').read_text())
            self.assertEqual(report['metrics']['target_total'], 500)
            self.assertFalse(report['metrics']['acceptance_complete'])
            self.assertEqual(json.loads((evidence / 'corpus_validation_state.json').read_text()), state)
            with patch.object(validate.runner, 'audit_wave', return_value=0) as explicit:
                self.assertEqual(main(['validate', 'audit', '--sample-manifest', 'explicit.json',
                                       '--batch-size', '12', '--central-target', '8']), 0)
            config = explicit.call_args.args[1]
            self.assertEqual(config.sample_manifest, Path('explicit.json'))
            self.assertEqual(config.batch_size, 12)
            self.assertEqual(config.scope_targets, {'trung_uong': 8, 'dia_phuong': 4})
            self.assertEqual(config.baseline_manifests, ())

    def test_explicit_saved_scope_override_is_not_replaced_by_inferred_quotas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / 'evidence'
            evidence.mkdir()
            (evidence / 'corpus_validation_state.json').write_text(json.dumps({
                'target': 3, 'scope_targets': {'trung_uong': 1, 'dia_phuong': 2}}))
            with patch.object(validate.runner, 'audit_wave', return_value=0) as operation:
                self.assertEqual(main(['validate', 'audit', '--report-dir', str(root),
                                       '--central-target', '2', '--wave-size', '1']), 0)
            config = operation.call_args.args[1]
            self.assertEqual(config.scope_targets, {'trung_uong': 2, 'dia_phuong': 1})
            self.assertEqual(config.wave_size, 1)

    def test_help_for_every_command_avoids_operational_work(self):
        for arguments in (['--help'], ['crawl', '--help'], ['extract', '--help'],
                          ['validate', '--help'], ['audit', '--help'],
                          ['audit', 'schema', '--help'], ['audit', 'hierarchy', '--help'],
                          ['compare', '--help']):
            with self.subTest(arguments=arguments), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main(arguments)
                self.assertEqual(result.exception.code, 0)

    def test_audit_alias_forwards_config_and_regenerate_without_network(self):
        with patch.object(validate.runner, 'audit_wave', return_value=1) as operation:
            self.assertEqual(main(['validate', '--audit', '--batch-size', '12', '--central-target', '8',
                                   '--sample-manifest', 'selected.json', '--report-dir', 'reports/example',
                                   '--regenerate']), 1)
        regenerate, config = operation.call_args.args
        self.assertTrue(regenerate)
        self.assertEqual(config.batch_size, 12)
        self.assertEqual(config.scope_targets, {'trung_uong': 8, 'dia_phuong': 4})
        self.assertEqual(config.sample_manifest, Path('selected.json'))
        self.assertEqual(config.report_dir, Path('reports/example'))

    def test_invalid_configuration_fails_before_operational_work(self):
        with patch.object(validate.runner, 'crawl_wave') as operation, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                main(['validate', 'crawl', '--batch-size', '3', '--central-target', '4'])
            self.assertEqual(result.exception.code, 2)
            operation.assert_not_called()

    def test_report_forwards_input_and_separate_output_paths(self):
        with patch.object(validate, 'write_report', return_value={'metrics': {}}) as operation:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['validate', 'report', '--report-dir', 'reports/input',
                                       '--output-dir', 'reports/output']), 0)
        self.assertEqual(operation.call_args.args[0].report_dir, Path('reports/input'))
        self.assertEqual(operation.call_args.args[1], Path('reports/output'))

    def test_old_ingestion_main_delegates_to_cli(self):
        from vietnam_legal_rag.ingestion import crawl_legal_documents, extract_legal_documents
        for module, command in ((crawl_legal_documents, 'crawl'), (extract_legal_documents, 'extract')):
            with patch(f'vietnam_legal_rag.cli.{command}.main', return_value=7) as adapter:
                self.assertEqual(module.main(['--help']), 7)
                adapter.assert_called_once_with(['--help'])

    def test_legacy_audit_adapters_forward_kind(self):
        for adapter, kind in ((audit.schema_main, 'schema'), (audit.hierarchy_main, 'hierarchy')):
            with patch.object(audit, 'main', return_value=0) as command:
                self.assertEqual(adapter(['--help']), 0)
                command.assert_called_once_with([kind, '--help'])


if __name__ == '__main__':
    unittest.main()
