"""Generic reporting preserves reviewed evidence and scales its denominator."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from vietnam_legal_rag.evaluation.config import ValidationConfig
from vietnam_legal_rag.evaluation.report_writer import build_report, markdown

from tests.support import ROOT
BASELINE = ROOT / 'reports/extract-validation-50'


class ValidationReportTests(unittest.TestCase):
    def setUp(self):
        if not BASELINE.is_dir():
            self.skipTest('Historical batch evidence is not available')
        self.state = json.loads((BASELINE / 'evidence/state.json').read_text())
        if not all((ROOT / d['raw_directory']).is_dir() for d in self.state['documents']):
            self.skipTest('Immutable batch RAW captures are not available locally')

    def test_batch_baseline_metrics_and_documents_are_preserved(self):
        result = build_report(ValidationConfig(report_dir=BASELINE))
        expected = json.loads((BASELINE / 'report.json').read_text())
        for key in ('metrics', 'documents', 'repairs', 'golden_validation', 'wave_audits', 'unsuccessful_candidates'):
            self.assertEqual(result[key], expected[key], key)

    def test_small_batch_and_custom_quotas_use_sample_target(self):
        for size, central, selected in ((3, 2, [0, 1, 2]), (2, 2, [0, 2])):
            with self.subTest(size=size, central=central), tempfile.TemporaryDirectory() as temporary:
                state = deepcopy(self.state)
                state['target'] = size
                state['documents'] = [state['documents'][i] for i in selected]
                path = Path(temporary) / 'selected.json'
                path.write_text(json.dumps(state))
                result = build_report(ValidationConfig(batch_size=size, central_target=central,
                                                       sample_manifest=path, report_dir=BASELINE))
                self.assertEqual(result['metrics']['crawl']['selected'], size)
                self.assertEqual(result['metrics']['crawl']['central'], central)
                self.assertEqual(result['metrics']['quality']['schema_valid']['evaluated'], size)
                text = markdown(result, Path(temporary))
                self.assertIn(f'# VBPL {size}-document', text)
                self.assertIn(f'{size}/{size}', text)
                self.assertNotIn('50/50', text)

    def test_report_rejects_incomplete_sample_and_unfinished_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = ValidationConfig(batch_size=51, report_dir=BASELINE)
            with self.assertRaises(AssertionError):
                build_report(config)
            evidence = Path(temporary)
            for name in ('repairs.json', 'tests.txt'):
                (evidence / name).write_bytes((BASELINE / 'evidence' / name).read_bytes())
            reviews = json.loads((BASELINE / 'evidence/reviews.json').read_text())
            reviews['documents'][0]['reviewed'] = False
            (evidence / 'reviews.json').write_text(json.dumps(reviews))
            with self.assertRaisesRegex(ValueError, 'unfinished'):
                build_report(ValidationConfig(report_dir=BASELINE), evidence_dir=evidence)


if __name__ == '__main__':
    unittest.main()
