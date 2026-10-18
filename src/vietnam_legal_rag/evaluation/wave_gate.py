"""Review gates for incremental hardening against immutable previous corpora."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

from vietnam_legal_rag.ingestion.crawl_legal_documents import CrawlError


def parser_fingerprint():
    """Identify implementation changes even within a parser release milestone."""
    root = Path(__file__).parents[1] / 'ingestion'
    digest = hashlib.sha256()
    for path in sorted([*root.rglob('*.py'), *root.rglob('*.json')]):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def read_manifest(path):
    """Read state from a file or an immutable ``archive.zip!/member`` locator."""
    archive, separator, member = str(path).partition('!/')
    if not separator:
        return json.loads(Path(path).read_text())
    location = PurePosixPath(member)
    if not archive or not member or location.is_absolute() or '..' in location.parts:
        raise CrawlError('Invalid archived manifest locator: ' + str(path))
    try:
        with zipfile.ZipFile(archive) as history:
            return json.loads(history.read(member))
    except zipfile.BadZipFile as exc:
        raise CrawlError('Invalid manifest archive: ' + archive) from exc


def baseline_documents(config):
    documents, identities, urls = [], set(), set()
    for path in config.baseline_manifests:
        state = read_manifest(path)
        for original in state['documents']:
            identity, url = original['document_id'], original['url']
            if identity in identities or url in urls:
                raise CrawlError('Duplicate identity or URL in baseline manifests')
            identities.add(identity); urls.add(url)
            documents.append({k: original[k] for k in ('document_id', 'url', 'raw_directory', 'document_scope')})
    return documents


def check_acquisition_gate(wave, state, config):
    if wave == 1:
        if len(state['documents']) > config.wave_size:
            raise CrawlError('Cannot acquire an earlier wave after later samples were selected')
        return
    gate = next((g for g in state.get('wave_completions', []) if g['wave'] == wave - 1), None)
    if not gate or gate['parser_fingerprint'] != parser_fingerprint():
        raise CrawlError('Previous wave requires a completed review/test/cumulative-audit gate with the current parser')
    expected = min((wave - 1) * config.wave_size, config.batch_size)
    if gate['new_documents'] != expected or len(state['documents']) < expected:
        raise CrawlError('Previous wave sample is incomplete')
    if gate['baseline_manifests'] != [str(p) for p in config.baseline_manifests]:
        raise CrawlError('Baseline manifests differ from the completed wave gate')


def validation_failures(validation):
    failures = list(validation['audit_errors'])
    failures.extend(k for k in ('schema_valid', 'deterministic', 'meaningful_text_preserved')
                    if not validation['quality'][k])
    if validation['issue_summary']['error'] or validation['issue_summary']['fatal']:
        failures.append('error/fatal diagnostics')
    unresolved = validation['hierarchy']['unresolved']
    if unresolved['numbered_candidates'] or unresolved['orphan_nodes']:
        failures.append('unresolved legal hierarchy')
    forms = validation['forms']
    if any(forms[k] for k in ('unexplained_structured_paragraphs', 'unexplained_form_label_paragraphs',
                             'suspicious_value_text', 'semantic_empty_string_fields',
                             'form_nodes_missing_field_kind', 'form_nodes_missing_field_evidence',
                             'unresolved_numbered_form_items', 'split_form_candidates',
                             'inconsistent_footnote_sequences', 'bibliography_fields_misclassified')):
        failures.append('unresolved form/list semantics')
    return failures


def complete_wave(wave, config):
    from .validation_runner import load_state, save_state, now
    state = load_state(config)
    expected = min(wave * config.wave_size, config.batch_size)
    if len(state['documents']) != expected:
        raise CrawlError('Wave must contain exactly its configured cumulative sample')
    if expected % config.wave_size and config.progress_dir:
        progress_path = config.progress_dir / 'evidence/state.json'
        progress = json.loads(progress_path.read_text()) if progress_path.exists() else {}
        if progress.get('target_assembled_documents', 0) < progress.get('target_total', 0):
            raise CrawlError('Partial wave cannot complete before the overall target is assembled')
    if state.get('audited_parser_fingerprint') != parser_fingerprint():
        raise CrawlError('Cumulative audit is stale after a parser change')
    baseline = baseline_documents(config)
    audited = state.get('baseline_validations', [])
    if {d['document_id'] for d in audited} != {d['document_id'] for d in baseline}:
        raise CrawlError('Previous corpus has not been fully audited')
    documents = state['documents'] + audited
    if len({d['document_id'] for d in documents}) != len(documents):
        raise CrawlError('New sample overlaps the previous corpus')
    for document in documents:
        if validation_failures(document['final_validation']):
            raise CrawlError(f"Unresolved validation failures: {document['document_id']}")
    if validation_failures(state['golden_validation']) or not all(state['golden_validation']['quality'].values()):
        raise CrawlError('Golden regression remains')
    evidence = config.report_dir / 'evidence'
    reviews = json.loads((evidence / 'reviews.json').read_text())
    by_id = {d['document_id']: d for d in reviews['documents']}
    for document in state['documents']:
        review = by_id.get(document['document_id'], {})
        if not review.get('reviewed') or review.get('parser_fingerprint') != parser_fingerprint():
            raise CrawlError(f"Current source semantic review missing: {document['document_id']}")
        warnings = {i['issue_id'] for i in document['final_validation']['diagnostics'] if i['severity'] == 'warning'}
        retained = {f['issue_id'] for f in review.get('findings', [])
                    if f['classification'] in {'source_ambiguity', 'expected_non_semantic_source_artifact'}}
        if not warnings <= retained:
            raise CrawlError(f"Unreviewed source warnings: {document['document_id']}")
        if review.get('parser_failure', 0) or review.get('unexplained_semantic_failure', 0):
            raise CrawlError('Semantic parser failure remains')
    log = (evidence / 'tests.txt').read_text()
    if not re.search(r'Ran \d+ tests', log) or not log.rstrip().endswith('OK'):
        raise CrawlError('Passing regression test evidence missing')
    test_evidence = json.loads((evidence / 'test-state.json').read_text())
    if test_evidence['parser_fingerprint'] != parser_fingerprint():
        raise CrawlError('Regression tests are stale after a parser change')
    repairs = json.loads((evidence / 'repairs.json').read_text())
    bugs = [r['id'] for r in repairs['parser_repairs'] if r['wave'] == wave]
    gate = {'wave': wave, 'completed_at': now(), 'new_documents': expected,
            'accumulated_documents': len(documents) + 1, 'parser_fingerprint': parser_fingerprint(),
            'baseline_manifests': [str(p) for p in config.baseline_manifests],
            'new_parser_bug_classes': bugs, 'parser_failure': 0, 'unexplained_semantic_failure': 0}
    state['wave_completions'] = [g for g in state.get('wave_completions', []) if g['wave'] != wave] + [gate]
    save_state(state, config)
    print(json.dumps(gate, indent=2))
    return gate
