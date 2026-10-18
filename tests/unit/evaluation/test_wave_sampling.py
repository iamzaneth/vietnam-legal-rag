"""Identity exclusion and reuse of newly captured scope mismatches."""
import json
from pathlib import Path
import tempfile
import unittest

from vietnam_legal_rag.evaluation.config import ValidationConfig
from vietnam_legal_rag.evaluation.validation_sampler import choose_candidate, choose_existing, candidate_metadata, document_identity
from vietnam_legal_rag.evaluation.validation_runner import retained_candidate


class WaveSamplingTests(unittest.TestCase):
    def test_environment_failure_allows_candidate_retry_without_source_penalty(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); inventory = root / 'urls.jsonl'
            candidate = candidate_metadata('https://vbpl.vn/van-ban/chi-tiet/luat-2025--9', '', 1)
            inventory.write_text(json.dumps(candidate))
            attempt = {**candidate, 'result': 'failed', 'requested_scope': 'trung_uong',
                       'failure_classification': 'execution_environment_network_failure'}
            config = ValidationConfig(inventory=inventory, raw_dir=root / 'raw')
            state = {'documents': [], 'attempts': [attempt]}
            self.assertEqual(choose_candidate(state, 'trung_uong', config)['url'], candidate['url'])
            attempt.pop('failure_classification')
            with self.assertRaisesRegex(Exception, 'No unused candidate'):
                choose_candidate(state, 'trung_uong', config)

    def test_unavailable_source_identifier_family_lowers_priority_without_exclusion(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventory = root / 'urls.jsonl'
            named = candidate_metadata('https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-1985-cp--archive_11', '', 1)
            numeric = candidate_metadata('https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-1985-cp--12', '', 1)
            inventory.write_text('\n'.join(json.dumps(r) for r in (named, numeric)))
            failed = {**named, 'url': 'https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-1985-cp--archive_10',
                      'result': 'failed', 'requested_scope': 'trung_uong'}
            used = {**numeric, 'url': 'https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-1984-cp--20',
                    'document_id': 'vbpl:20', 'document_scope': 'trung_uong'}
            config = ValidationConfig(inventory=inventory, raw_dir=root / 'raw')
            state = {'documents': [used], 'attempts': [failed]}
            self.assertEqual(choose_candidate(state, 'trung_uong', config)['url'], numeric['url'])
            inventory.write_text(json.dumps(named))
            self.assertEqual(choose_candidate(state, 'trung_uong', config)['url'], named['url'])

    def test_family_success_counts_scope_mismatch_as_available_source(self):
        from vietnam_legal_rag.evaluation.validation_sampler import source_family
        self.assertEqual(source_family('https://vbpl.vn/van-ban/chi-tiet/doc--archive_19'),
                         source_family('https://vbpl.vn/van-ban/chi-tiet/other--archive_20'))
        self.assertNotEqual(source_family('https://vbpl.vn/van-ban/chi-tiet/doc--archive_19'),
                            source_family('https://vbpl.vn/van-ban/chi-tiet/doc--19'))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary);inventory = root / 'urls.jsonl'
            candidate = candidate_metadata('https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-1985-cp--archive_21', '', 1)
            inventory.write_text(json.dumps(candidate))
            observed = {**candidate, 'url': 'https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-1985-cp--archive_20',
                        'result': 'scope_hint_mismatch', 'requested_scope': 'trung_uong', 'actual_scope': 'dia_phuong',
                        'document_id': 'vbpl:observed'}
            chosen = choose_candidate({'documents': [], 'attempts': [observed]}, 'trung_uong',
                                      ValidationConfig(inventory=inventory, raw_dir=root/'raw'))
            self.assertEqual(chosen['url'], candidate['url'])
            self.assertEqual(chosen['scope_hint'], 'trung_uong')
            self.assertEqual(observed['actual_scope'], 'dia_phuong')

    def test_observed_scope_mismatches_lower_sampling_priority_without_reclassification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inventory = root / 'urls.jsonl'
            old = candidate_metadata('https://vbpl.vn/van-ban/chi-tiet/nghi-dinh-1985-cp--11', '', 1)
            fresh = candidate_metadata('https://vbpl.vn/van-ban/chi-tiet/nghi-dinh-2025-cp--12', '', 2)
            inventory.write_text('\n'.join(json.dumps(r) for r in (old, fresh)))
            observed = {**old, 'url': 'https://vbpl.vn/van-ban/chi-tiet/nghi-dinh-1984-cp--10',
                        'document_id': 'vbpl:10', 'result': 'scope_hint_mismatch',
                        'requested_scope': 'trung_uong', 'actual_scope': 'dia_phuong'}
            used = {**fresh, 'url': 'https://vbpl.vn/van-ban/chi-tiet/nghi-dinh-2024-cp--20',
                    'document_id': 'vbpl:20', 'document_scope': 'trung_uong'}
            state = {'documents': [used], 'attempts': [observed]}
            chosen = choose_candidate(state, 'trung_uong', ValidationConfig(inventory=inventory, raw_dir=root / 'raw'))
            self.assertEqual(chosen['url'], fresh['url'])
            self.assertEqual(old['scope_hint'], 'trung_uong')
            self.assertEqual(observed['actual_scope'], 'dia_phuong')

    def test_existing_identity_excludes_alternate_slug(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw = root / 'raw' / '1'; raw.mkdir(parents=True)
            (raw / 'manifest.json').write_text(json.dumps({'document_id': 'vbpl:1', 'source_url': 'https://vbpl.vn/van-ban/chi-tiet/old--1'}))
            inventory = root / 'urls.jsonl'
            urls = ['https://vbpl.vn/van-ban/chi-tiet/luat-new--1', 'https://vbpl.vn/van-ban/chi-tiet/luat-new--2']
            inventory.write_text('\n'.join(json.dumps(candidate_metadata(u, '', 0)) for u in urls))
            chosen = choose_candidate({'documents': [], 'attempts': []}, 'trung_uong', ValidationConfig(inventory=inventory, raw_dir=root / 'raw'))
            self.assertEqual(document_identity(chosen['url']), 'vbpl:2')

    def test_mismatch_capture_is_reused_only_in_its_own_wave_and_actual_scope(self):
        attempt = {'result': 'scope_hint_mismatch', 'wave': 1, 'actual_scope': 'trung_uong', 'document_id': 'vbpl:9'}
        state = {'attempts': [attempt], 'documents': []}
        self.assertIs(retained_candidate(state, 'trung_uong', 1), attempt)
        self.assertIsNone(retained_candidate(state, 'dia_phuong', 1))
        self.assertIsNone(retained_candidate(state, 'trung_uong', 2))
        state['documents'].append({'document_id': 'vbpl:9'})
        self.assertIsNone(retained_candidate(state, 'trung_uong', 1))

    def test_local_selection_excludes_reviewed_ids_and_rejects_corrupt_evidence(self):
        from tests.unit.evaluation import test_local_inventory as helpers
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = helpers.LocalInventoryTests()
            fixture.complete_capture(root, 'trung_uong', '9')
            fixture.complete_capture(root, 'trung_uong', '10')
            raw = fixture.complete_capture(root, 'trung_uong', '11')
            (raw / 'content.html').write_text('Corrupt')
            config = ValidationConfig(raw_dir=root / 'raw', excluded_ids=('vbpl:10',))
            chosen = choose_existing({'documents': [], 'attempts': []}, 'trung_uong', config)
            self.assertEqual(chosen['document_id'], 'vbpl:9')
            self.assertEqual(chosen['sampling_origin'], 'existing_local_raw')
