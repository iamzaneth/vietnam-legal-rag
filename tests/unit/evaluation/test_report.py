"""Generic reporting preserves reviewed evidence and scales its denominator."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from vietnam_legal_rag.evaluation.config import ValidationConfig
from vietnam_legal_rag.evaluation.report_writer import (
    acquisition_accounting, build_report, markdown, source_evidence, total_corpus_metrics,
    write_target_report, write_total_report,
)

from tests.support import ROOT
from vietnam_legal_rag.ingestion.html.source import parse_html
HISTORY = ROOT / 'reports/validation/history.zip'


class SourceEvidenceTests(unittest.TestCase):
    def test_text_leaf_evidence_uses_exact_source_ref_and_text(self):
        html = '<p>Before <b>People\ufffds Council</b> after.</p>'
        root = parse_html(html)
        owner = next(n for n in root.find() if n.tag == 'b')
        ref = owner.text_refs[0]
        with tempfile.TemporaryDirectory() as temporary:
            raw = Path(temporary)
            (raw / 'content.html').write_text(html)
            evidence = source_evidence(raw, {'tab': 'content', 'source_ref': ref})
            self.assertEqual(evidence['source_ref'], ref)
            self.assertEqual(evidence['source_text_excerpt'], 'People\ufffds Council')
            with self.assertRaisesRegex(ValueError, 'Missing source anchor'):
                source_evidence(raw, {'tab': 'content', 'source_ref': {**ref, 'dom_order': 999}})


class AcquisitionAccountingTests(unittest.TestCase):
    def test_environment_failures_remain_attempts_without_claiming_source_failures(self):
        state = {'documents': [{}], 'attempts': [
            {'result': 'failed', 'failure_classification': 'execution_environment_network_failure'},
            {'result': 'failed'}, {'result': 'complete'}]}
        counts = acquisition_accounting(state)
        self.assertEqual(counts['candidate_attempts'], 3)
        self.assertEqual(counts['crawl_failures'], 2)
        self.assertEqual(counts['execution_environment_failures'], 1)
        self.assertEqual(counts['source_candidate_attempts'], 2)
        self.assertEqual(counts['source_crawl_failures'], 1)
        self.assertEqual(counts['acceptance_rate'], 1 / 3)
        self.assertEqual(counts['source_acceptance_rate'], 1 / 2)

    def test_target_report_keeps_pending_total_distinct_from_subrun_size(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / 'evidence'; evidence.mkdir()
            (evidence / 'cumulative_reviews.json').write_text(json.dumps({'documents': []}))
            state = evidence / 'local.json'; state.write_text(json.dumps({'documents': []}))
            target = evidence / 'target.json'
            target.write_text(json.dumps({'target_total': 500, 'documents': [{'document_id': 'vbpl:1'}]}))
            report = write_target_report(ValidationConfig(batch_size=32, sample_manifest=state, report_dir=root), target)
            self.assertEqual(report['metrics']['target_assembled'], 1)
            self.assertEqual(report['metrics']['pending_target_assembly'], 499)
            self.assertEqual(report['metrics']['current_parser_validated'], 0)
            self.assertEqual(report['status'], 'incomplete')
            self.assertTrue((root / 'report.md').is_file())

    def test_partial_total_corpus_is_never_reported_as_complete(self):
        target = {'target_total': 500, 'documents': [{'document_id': 'vbpl:1'}]}
        metrics = total_corpus_metrics(target, [], 'current')
        self.assertFalse(metrics['acceptance_complete'])
        self.assertEqual(metrics['pending_target_assembly'], 499)
        self.assertEqual(metrics['pending_current_parser_validation'], 1)
        self.assertIsNone(metrics['quality']['schema_valid']['rate'])
        self.assertEqual(metrics['statuses']['failed'], 0)
        self.assertEqual(metrics['diagnostics']['error'], 0)
        self.assertEqual(metrics['diagnostics']['fatal'], 0)

    def test_total_corpus_rejects_duplicate_role_records(self):
        target = {'target_total': 500, 'documents': [{'document_id': 'vbpl:1'}] * 2}
        with self.assertRaisesRegex(ValueError, 'duplicates'):
            total_corpus_metrics(target, [], 'current')

    def test_reusing_local_raw_is_not_a_new_network_capture(self):
        state = {'documents': [{'sampling_origin': 'existing_local_raw'}, {}, {}],
                 'attempts': [{'result': r} for r in ('complete', 'scope_hint_mismatch', 'reused_capture', 'existing_capture', 'failed')]}
        counts = acquisition_accounting(state)
        self.assertEqual(counts['candidate_attempts'], 3)
        self.assertEqual(counts['successfully_crawled_sample'], 2)
        self.assertEqual(counts['existing_local_sample_additions'], 1)
        self.assertEqual(counts['acceptance_rate'], 2 / 3)

    def test_entirely_local_sample_has_no_network_acceptance_rate(self):
        counts = acquisition_accounting({'documents': [{'sampling_origin': 'existing_local_raw'}],
                                         'attempts': [{'result': 'existing_capture'}]})
        self.assertEqual(counts['candidate_attempts'], 0)
        self.assertEqual(counts['successfully_crawled_sample'], 0)
        self.assertIsNone(counts['acceptance_rate'])


class ValidationReportTests(unittest.TestCase):
    def setUp(self):
        if not HISTORY.is_file():
            self.skipTest('Historical batch evidence archive is not available')
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        with zipfile.ZipFile(HISTORY) as archive:
            prefix = 'reports/extract-validation-50/'
            for name in archive.namelist():
                if name.startswith(prefix):
                    archive.extract(name, temporary.name)
        self.baseline = Path(temporary.name) / prefix
        self.state = json.loads((self.baseline / 'evidence/state.json').read_text())
        if not all((ROOT / d['raw_directory']).is_dir() for d in self.state['documents']):
            self.skipTest('Immutable batch RAW captures are not available locally')

    def test_batch_baseline_metrics_and_documents_are_preserved(self):
        result = build_report(ValidationConfig(report_dir=self.baseline))
        expected = json.loads((self.baseline / 'report.json').read_text())
        # Historical legal/source/audit decisions are immutable. The report also
        # describes current serialized bundles, which were upgraded uniformly.
        # Assert those two fields against actual canonical artifacts separately.
        for document in expected['documents']:
            output = ROOT / 'data/extracted/vbpl' / document['document_id'].removeprefix('vbpl:')
            manifest = json.loads((output / 'manifest.json').read_text())
            document['extracted_files'] = manifest['files']
            document['text_hashes'] = {
                f['path']: json.loads((output / f['path']).read_text())['validation']
                for f in manifest['files']}
        for key in ('metrics', 'documents', 'repairs', 'golden_validation', 'wave_audits', 'unsuccessful_candidates'):
            self.assertEqual(result[key], expected[key], key)

    def test_stale_source_review_and_missing_completion_checks_block_acceptance(self):
        document = self.state['documents'][0]
        target = {'target_total': 1, 'documents': [{'document_id': document['document_id']}]}
        review = {'reviewed': True, 'parser_fingerprint': 'old'}
        records = [{'document_id': document['document_id'], 'parser_fingerprint': 'current',
                    'validation': document['final_validation'], 'semantic_review': review}]
        metrics = total_corpus_metrics(target, records, 'current')
        self.assertEqual(metrics['source_reviewed'], 0)
        self.assertFalse(metrics['acceptance_complete'])
        review['parser_fingerprint'] = 'current'
        with tempfile.TemporaryDirectory() as temporary:
            report = write_total_report(Path(temporary), target, records, 'current')
            self.assertTrue(report['metrics']['corpus_validation_complete'])
            self.assertFalse(report['metrics']['acceptance_complete'])
            self.assertEqual(report['status'], 'incomplete')

    def test_small_batch_and_custom_quotas_use_sample_target(self):
        for size, central, selected in ((3, 2, [0, 1, 2]), (2, 2, [0, 2])):
            with self.subTest(size=size, central=central), tempfile.TemporaryDirectory() as temporary:
                state = deepcopy(self.state)
                state['target'] = size
                state['documents'] = [state['documents'][i] for i in selected]
                path = Path(temporary) / 'selected.json'
                path.write_text(json.dumps(state))
                result = build_report(ValidationConfig(batch_size=size, central_target=central,
                                                       sample_manifest=path, report_dir=self.baseline))
                self.assertEqual(result['metrics']['crawl']['selected'], size)
                self.assertEqual(result['metrics']['crawl']['central'], central)
                self.assertEqual(result['metrics']['quality']['schema_valid']['evaluated'], size)
                text = markdown(result, Path(temporary))
                self.assertIn(f'# VBPL {size}-document', text)
                self.assertIn(f'{size}/{size}', text)
                self.assertNotIn('50/50', text)

    def test_report_rejects_incomplete_sample_and_unfinished_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = ValidationConfig(batch_size=51, report_dir=self.baseline)
            with self.assertRaises(AssertionError):
                build_report(config)
            evidence = Path(temporary)
            for name in ('repairs.json', 'tests.txt'):
                (evidence / name).write_bytes((self.baseline / 'evidence' / name).read_bytes())
            reviews = json.loads((self.baseline / 'evidence/reviews.json').read_text())
            reviews['documents'][0]['reviewed'] = False
            (evidence / 'reviews.json').write_text(json.dumps(reviews))
            with self.assertRaisesRegex(ValueError, 'unfinished'):
                build_report(ValidationConfig(report_dir=self.baseline), evidence_dir=evidence)


if __name__ == '__main__':
    unittest.main()
