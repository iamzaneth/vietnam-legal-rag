"""An interrupted progress write must preserve the prior committed state."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vietnam_legal_rag.evaluation.progress import atomic_json, record_progress


class ProgressTests(unittest.TestCase):
    def test_new_capture_marks_target_manifest_pending_until_assembled(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary)
            state = record_progress(report, 'capture completed', target_total=2,
                                    target_manifest=[{'document_id': 'vbpl:1'}],
                                    successfully_captured_ids=['vbpl:1', 'vbpl:2', 'vbpl:2'])
            self.assertTrue(state['target_manifest_stale'])
            self.assertEqual(state['target_manifest_pending_ids'], ['vbpl:2'])
            state = record_progress(report, 'target assembled',
                                    target_manifest=[{'document_id': 'vbpl:1'}, {'document_id': 'vbpl:2'}])
            self.assertFalse(state['target_manifest_stale'])
            self.assertEqual(state['target_manifest_pending_ids'], [])

    def test_extra_local_raw_does_not_stale_a_complete_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = record_progress(Path(temporary), 'complete target preserved', target_total=1,
                                    target_manifest=[{'document_id': 'vbpl:1'}],
                                    successfully_captured_ids=['vbpl:1', 'vbpl:2'])
            self.assertFalse(state['target_manifest_stale'])
            self.assertEqual(state['target_manifest_pending_ids'], [])

    def test_failed_publish_retains_previous_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'state.json'
            atomic_json(path, {'step': 'capture complete'})
            with patch('vietnam_legal_rag.evaluation.progress.os.replace', side_effect=OSError('interrupted')):
                with self.assertRaises(OSError):
                    atomic_json(path, {'step': 'audit pending'})
            self.assertEqual(json.loads(path.read_text()), {'step': 'capture complete'})

    def test_resume_evidence_preserves_atomic_progress_and_prior_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary)
            record_progress(report, 'repair tested', target_total=3, unresolved_ids=['vbpl:1'], current_phase='hardening',
                            next_required_step='Regenerate from existing RAW')
            state = record_progress(report, 'document extracted', current_document='vbpl:2')
            self.assertEqual(state['unresolved_ids'], ['vbpl:1'])
            self.assertEqual(state['last_completed_atomic_step'], 'document extracted')
            self.assertEqual(state['target_total'], 3)
            self.assertIn('Never restart completed', (report / 'evidence/resume.md').read_text())
            self.assertIn('Regenerate from existing RAW', (report / 'evidence/checkpoint.md').read_text())
