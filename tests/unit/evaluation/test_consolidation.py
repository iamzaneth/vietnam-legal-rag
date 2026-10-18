"""Canonical migration preserves accepted identities and immutable proof."""
import hashlib
from copy import deepcopy
import json
import re
from pathlib import Path
import unittest
import zipfile

from tests.support import ROOT
from vietnam_legal_rag.evaluation.config import ValidationConfig
from vietnam_legal_rag.evaluation.wave_gate import parser_fingerprint


class ConsolidationTests(unittest.TestCase):
    def test_defaults_do_not_partition_storage_by_sample_size(self):
        for size in (12, 50, 100, 500):
            config = ValidationConfig(batch_size=size)
            self.assertEqual(config.extracted_dir, Path('data/extracted/vbpl'))
            self.assertEqual(config.report_dir, Path('reports/validation'))
            self.assertEqual(config.sample_manifest, Path('reports/validation/evidence/state.json'))

    def test_available_accepted_collection_matches_frozen_identity_and_hashes(self):
        proof = ROOT / 'reports/validation/evidence/final-parser-candidate.json'
        if not proof.exists():
            self.skipTest('Local accepted corpus proof is unavailable')
        frozen = json.loads(proof.read_text())
        collection = ROOT / 'data/extracted/vbpl'
        if not collection.exists():
            self.skipTest('Local accepted corpus is unavailable')
        bundles = frozen['approved_current_outputs']
        self.assertEqual(parser_fingerprint(), frozen['parser_fingerprint'])
        self.assertTrue({identity.removeprefix('vbpl:') for identity in bundles}.issubset(
            {p.name for p in collection.iterdir() if p.is_dir()}))
        for identity, record in bundles.items():
            folder = collection / identity.removeprefix('vbpl:')
            actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
            self.assertEqual(actual, record['extract_hashes'], identity)
            self.assertEqual(json.loads((folder / 'manifest.json').read_text())['document_id'], identity)

    def test_frozen_target_hash_maps_to_identical_migrated_membership_and_provenance(self):
        ledger = ROOT / 'reports/consolidation/migration.json'
        if not ledger.exists():
            self.skipTest('Local migration evidence is unavailable')
        mapping = json.loads(ledger.read_text())['target_manifest_migration']
        with zipfile.ZipFile(ROOT / mapping['original_archive']) as history:
            original = history.read(mapping['original_member'])
        current = (ROOT / mapping['current_path']).read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), mapping['original_sha256'])
        self.assertEqual(hashlib.sha256(current).hexdigest(), mapping['current_sha256'])
        frozen = json.loads((ROOT / 'reports/validation/evidence/final-parser-candidate.json').read_text())
        self.assertEqual(frozen['target_manifest_sha256'], mapping['original_sha256'])
        expected = deepcopy(json.loads(original))
        for document in expected['documents']:
            for role in document['roles']:
                path = role.get('manifest')
                if path in mapping['role_manifest_path_mappings']:
                    role['manifest'] = mapping['role_manifest_path_mappings'][path]
        self.assertEqual(expected, json.loads(current))

    def test_live_archive_locators_resolve_after_pruning(self):
        root = ROOT / 'reports/validation'
        index_path = root / 'history-index.json'
        if not index_path.exists():
            self.skipTest('Local report archive index is unavailable')
        members = json.loads(index_path.read_text())['members']
        for path in [*root.glob('evidence/*.json'), root / 'report.json', root / 'report.md']:
            for member in re.findall(r'history.zip!/(reports/[^\s";]+?\.(?:json|md|txt))', path.read_text()):
                self.assertIn(member, members, str(path))

    def test_available_history_archive_matches_member_hash_index(self):
        root = ROOT / 'reports/validation'
        archive = root / 'history.zip'
        if not archive.exists():
            self.skipTest('Local historical acceptance archive is unavailable')
        index = json.loads((root / 'history-index.json').read_text())['members']
        with zipfile.ZipFile(archive) as history:
            self.assertEqual(set(history.namelist()), set(index))
            for name, record in index.items():
                content = history.read(name)
                self.assertEqual(len(content), record['bytes'], name)
                self.assertEqual(hashlib.sha256(content).hexdigest(), record['sha256'], name)
