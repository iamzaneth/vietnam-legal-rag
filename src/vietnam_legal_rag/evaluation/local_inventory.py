"""Canonical usable local RAW inventory; never repairs or deletes evidence."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse

from vietnam_legal_rag.ingestion.crawl_legal_documents import canonical_document_url
from .validation_sampler import candidate_metadata, document_identity


def inspect_capture(manifest_path: Path, memberships=None):
    record = {'capture_path': str(manifest_path.parent), 'manifest_path': str(manifest_path),
              'usable': False, 'issues': [], 'roles': []}
    try:
        manifest = json.loads(manifest_path.read_text())
        identity = manifest.get('document_id')
        url = manifest.get('source_url')
        record.update(document_id=identity, source_url=url, source_scope=manifest.get('document_scope'),
                      manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                      captured_at=manifest.get('completed_at', manifest.get('retrieved_at')))
        record['roles'] = (memberships or {}).get(identity, [])
        if not isinstance(identity, str) or not identity.startswith('vbpl:'):
            record['issues'].append('missing/invalid source document identity')
        if not isinstance(url, str) or urlparse(url).hostname != 'vbpl.vn':
            record['issues'].append('missing/invalid VBPL source URL')
        else:
            record['canonical_url'] = canonical_document_url(url)
            hints = candidate_metadata(url, '', 0)
            record.update(document_type_hint=hints['document_type_hint'], year_hint=hints['year_hint'])
            if '/van-ban/chi-tiet/' in urlparse(url).path and document_identity(url) != identity:
                record['issues'].append('manifest/URL identity conflict')
        if manifest.get('status') != 'complete':
            record['issues'].append('capture is not complete')
        for key in ('content_stable', 'metadata_tabs_complete'):
            if manifest.get('validation', {}).get(key) is not True:
                record['issues'].append('capture completeness evidence missing: ' + key)
        files = manifest.get('files', [])
        names = [f.get('path') for f in files]
        if not files or 'content.html' not in names or len(names) != len(set(names)):
            record['issues'].append('missing content or duplicate file records')
        for item in files:
            name = item.get('path')
            if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9_]+\.html', name):
                record['issues'].append('invalid local source file path'); continue
            path = manifest_path.parent / name
            if not path.is_file():
                record['issues'].append('missing source file: ' + name); continue
            data = path.read_bytes()
            if len(data) != item.get('bytes') or hashlib.sha256(data).hexdigest() != item.get('sha256'):
                record['issues'].append('source hash/size mismatch: ' + name)
        tabs = manifest.get('tabs', {})
        if 'content' not in tabs:
            record['issues'].append('content tab completeness missing')
        for name, tab in tabs.items():
            if tab.get('status') != 'complete' or not tab.get('files') or not set(tab['files']) <= set(names):
                record['issues'].append('incomplete tab: ' + name)
        record['manifest_valid'] = not record['issues']
        record['usable'] = record['manifest_valid']
    except (OSError, ValueError, KeyError, TypeError) as exc:
        record['issues'].append(type(exc).__name__ + ': ' + str(exc))
        record['manifest_valid'] = False
    return record


def inventory_raw(raw_dir: Path, memberships=None):
    manifests = set(raw_dir.rglob('manifest.json'))
    # An interrupted crawler may leave staged content, or even an empty
    # staging document directory, without a published manifest.
    manifests.update(p.parent / 'manifest.json' for p in raw_dir.rglob('content.html'))
    manifests.update(p / 'document' / 'manifest.json' for p in raw_dir.glob('.crawl-*')
                     if (p / 'document').is_dir())
    captures = [inspect_capture(p, memberships) for p in sorted(manifests)]
    by_url = {}
    for capture in captures:
        if capture['usable']:
            by_url.setdefault(capture['canonical_url'], set()).add(capture['document_id'])
    conflicting_urls = {url for url, ids in by_url.items() if len(ids) > 1}
    by_id = {}
    for capture in captures:
        if capture.get('canonical_url') in conflicting_urls:
            capture['usable'] = False
            capture['issues'].append('same source URL has conflicting identities; review required')
        if capture['usable']:
            by_id.setdefault(capture['document_id'], []).append(capture)
    documents = []
    for identity, group in sorted(by_id.items()):
        # Prefer the capture already referenced by a reviewed corpus. Preserve
        # every other complete capture and retain its conflicting/version data.
        preferred = min(group, key=lambda c: (not bool(c['roles']), c['capture_path']))
        for capture in group:
            capture['duplicate_of'] = None if capture is preferred else preferred['capture_path']
        documents.append({**preferred, 'capture_paths': [c['capture_path'] for c in group],
                          'duplicate_captures': len(group) - 1,
                          'already_validated': bool(preferred['roles'])})
    return {'counting_rule': 'Each distinct usable source document identity counts once; complete duplicate captures remain preserved.',
            'local_raw_distinct_total': len(documents), 'capture_total': len(captures),
            'usable_capture_total': sum(c['usable'] for c in captures),
            'unusable_capture_total': sum(not c['usable'] for c in captures),
            'duplicate_capture_total': sum(d['duplicate_captures'] for d in documents),
            'scope_counts': dict(Counter(d['source_scope'] for d in documents)),
            'documents': documents, 'captures': captures}
