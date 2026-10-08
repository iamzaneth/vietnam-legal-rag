"""CLI dispatch, configuration forwarding and preservation of legacy adapters."""
import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from vietnam_legal_rag.cli.__main__ import main
from vietnam_legal_rag.cli import audit, validate


class ToolingCLITests(unittest.TestCase):
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
