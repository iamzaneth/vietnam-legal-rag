"""Build batch-independent reports from audits and explicit semantic reviews."""
from collections import Counter
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from vietnam_legal_rag.ingestion.html.source import parse_html

from .config import ValidationConfig

def read(path):
    return json.loads(path.read_text())


def source_evidence(raw, diagnostic):
    root = parse_html((raw / (diagnostic['tab'] + '.html')).read_text())
    order = diagnostic['source_ref']['dom_order']
    node = next((n for n in root.find() if n.dom_order == order), None)
    text, ref = None, None
    if node is None:
        for owner in root.find():
            for index, source_ref in owner.text_refs.items():
                if source_ref == diagnostic['source_ref'] and isinstance(owner.children[index], str):
                    node, text, ref = owner, owner.children[index], source_ref
                    break
            if node is not None:
                break
    if not node:
        raise ValueError(f'Missing source anchor: {diagnostic}')
    attributes = {k: (v[:100] + '…' if len(v) > 100 else v)
                  for k, v in node.attrs.items() if k in {'href', 'src', 'alt', 'rowspan', 'colspan', 'style'}}
    return {'source_ref': ref or node.ref, 'source_text_excerpt': (text if text is not None else node.text())[:400], 'source_attributes': attributes}


def acquisition_accounting(state):
    """Separate network collection from selection of already captured RAW."""
    network = [a for a in state['attempts'] if a['result'] not in {'reused_capture', 'existing_capture'}]
    results = Counter(a['result'] for a in network)
    source_attempts = [a for a in network
                       if a.get('failure_classification') != 'execution_environment_network_failure']
    source_results = Counter(a['result'] for a in source_attempts)
    local = sum(d.get('sampling_origin') == 'existing_local_raw' for d in state['documents'])
    collected = len(state['documents']) - local
    return {'candidate_attempts': len(network), 'candidate_selections': len(state['attempts']),
            'successfully_crawled_sample': collected, 'existing_local_sample_additions': local,
            'usable_sample_captures': len(state['documents']),
            'successful_captures_including_scope_mismatches': results['complete'] + results['scope_hint_mismatch'],
            'reused_scope_mismatch_captures': sum(a['result'] == 'reused_capture' for a in state['attempts']),
            'crawl_failures': results['failed'], 'interrupted_candidates': results['interrupted'],
            'scope_mismatches': results['scope_hint_mismatch'], 'duplicates': results['duplicate'],
            'replacements': results['failed'] + results['scope_hint_mismatch'],
            'acceptance_rate': collected / len(network) if network else None,
            'execution_environment_failures': len(network) - len(source_attempts),
            'source_candidate_attempts': len(source_attempts),
            'source_crawl_failures': source_results['failed'],
            'source_acceptance_rate': collected / len(source_attempts) if source_attempts else None}


def build_report(config, evidence_dir=None,
                 regression_fixture=Path('tests/fixtures/vbpl_batch_regressions.json'),
                 tests_dir=Path('tests')):
    evidence_dir = evidence_dir or config.report_dir / 'evidence'
    state_path = config.sample_manifest
    state = read(state_path)
    repairs = read(evidence_dir / 'repairs.json')
    reviews = read(evidence_dir / 'reviews.json')
    corpus = read(regression_fixture)
    test_log = (evidence_dir / 'tests.txt').read_text()
    test_count = int(re.search(r'Ran (\d+) tests', test_log)[1])
    assert test_log.rstrip().endswith('OK'), 'Final unit tests did not pass'
    def test_methods(filename):
        tree = ast.parse((tests_dir / filename).read_text())
        return sum(isinstance(n, ast.FunctionDef) and n.name.startswith('test_') for n in ast.walk(tree))
    parser_tests = test_methods('regression/test_source_patterns.py')
    sampler_tests = test_methods('unit/evaluation/test_sampler.py')
    regression_repairs = repairs.get('regression_discovered_repairs', [])
    repair_count = len(repairs['parser_repairs']) + len(regression_repairs)
    review_by_id = {r['document_id']: r for r in reviews['documents']}
    documents, diagnostics, statuses, types, scopes, structures = [], Counter(), Counter(), Counter(), Counter(), Counter()
    quality = Counter()
    for d in state['documents']:
        review = review_by_id[d['document_id']]
        if not review['reviewed']:
            raise ValueError('Semantic review remains unfinished')
        v = d['final_validation']
        raw = Path(d['raw_directory'])
        output = config.extracted_dir / raw.name
        raw_manifest = read(raw / 'manifest.json')
        manifest = read(output / 'manifest.json')
        properties = read(output / 'properties.json')
        fields = {f['label']: f['value'] for f in properties['fields']}
        warnings = [{**i, 'source_evidence': source_evidence(raw, i)}
                    for i in v['diagnostics'] if i['severity'] != 'info']
        types[fields.get('Loại văn bản', 'Unknown')] += 1
        scopes[d['document_scope']] += 1
        statuses[v['status']] += 1
        quality.update(k for k, value in v['quality'].items() if value)
        diagnostics.update(v['issue_summary'])
        unresolved = v['hierarchy']['unresolved']
        structures.update(unresolved)
        structures['structured_paragraph_list_issues'] += v['forms']['unexplained_structured_paragraphs']
        form_checks = ('unresolved_numbered_form_items', 'split_form_candidates', 'inconsistent_footnote_sequences',
                       'bibliography_fields_misclassified', 'unexplained_form_label_paragraphs', 'suspicious_value_text',
                       'semantic_empty_string_fields', 'form_nodes_missing_field_kind', 'form_nodes_missing_field_evidence')
        structures['form_validation_issues'] += sum(v['forms'][k] for k in form_checks)
        structures['relation_count_mismatches'] += sum(i['code'] == 'relation_count_mismatch' for i in v['diagnostics'])
        documents.append({
            'sequence': d['sequence'], 'wave': d['wave'], 'document_id': d['document_id'], 'source_url': d['url'],
            'scope': d['document_scope'], 'scope_evidence': raw_manifest['classification'],
            'document_type': fields.get('Loại văn bản'), 'document_number': fields.get('Số hiệu'),
            'issued_at_source': fields.get('Ngày ban hành'), 'issuing_authority_source': fields.get('Cơ quan ban hành'),
            'title': raw_manifest['title'], 'crawl_result': d['crawl_result'],
            'retrieved_at': raw_manifest['retrieved_at'], 'raw_directory': d['raw_directory'],
            'initial_extract_status': d['initial_extract_status'], 'initial_issue_summary': d['initial_issue_summary'],
            'final_extract_status': v['status'], 'quality': v['quality'], 'issue_summary': v['issue_summary'],
            'audit_errors': v['audit_errors'], 'hierarchy': v['hierarchy'], 'forms': v['forms'],
            'table_features': v['table_features'], 'node_types': v['node_types'],
            'text_hashes': {f['path']: read(output / f['path'])['validation'] for f in manifest['files']},
            'raw_files': raw_manifest['files'], 'extracted_files': manifest['files'],
            'captured_tabs': raw_manifest['tabs'], 'excluded_tabs': raw_manifest['excluded_tabs'],
            'important_diagnostics': warnings, 'semantic_review': review,
            'parser_repairs': [r['id'] for r in repairs['parser_repairs']
                               if any(a['document_id'] == d['document_id'] for a in r['documents'])],
            'regression_fixture': any(c['document_id'] == d['document_id'] for c in corpus['documents'])})
    n = len(documents)
    assert n == config.batch_size and state['target'] == config.batch_size, 'Incomplete or mismatched sample target'
    attempts = Counter(a['result'] for a in state['attempts'])
    metrics = {
        'crawl': {'selected': n, 'successfully_crawled_sample': n, 'central': scopes['trung_uong'], 'local': scopes['dia_phuong'],
                  'candidate_attempts': len(state['attempts']), 'successful_captures_including_scope_mismatches': attempts['complete'] + attempts['scope_hint_mismatch'],
                  'replaced_due_to_crawl_source_failure': attempts['failed'], 'replaced_due_to_scope_hint_mismatch': attempts['scope_hint_mismatch']},
        'extract': {k: statuses[k] for k in ('success', 'success_with_warnings', 'failed')},
        'quality': {k: {'count': quality[k], 'evaluated': n, 'rate': quality[k] / n} for k in
                    ('schema_valid', 'deterministic', 'meaningful_text_preserved', 'semantic_complete')},
        'structure': dict(structures), 'diagnostics': dict(diagnostics),
        'repair': {'parser_bugs_discovered': repair_count, 'parser_repairs': repair_count,
                   'sample_discovered_parser_bugs': len(repairs['parser_repairs']), 'regression_discovered_parser_bugs': len(regression_repairs),
                   'schema_gaps': len(repairs['schema_gaps']), 'raw_capture_code_defects': len(repairs['raw_capture_defects']),
                   'portable_parser_test_methods': parser_tests, 'sampler_test_methods': sampler_tests, 'captured_corpus_test_methods': 1,
                   'documents_promoted_to_regression_fixtures': len(corpus['documents'])},
        'actual_document_types': dict(types)}
    assert len({d['document_id'] for d in documents}) == n
    assert len({d['source_url'] for d in documents}) == n
    assert all(scopes[k] == v for k, v in config.scope_targets.items())
    assert [d['scope'] for d in documents] == config.expected_scopes()
    assert not any(d['audit_errors'] for d in documents)
    assert all(quality[k] == n for k in ('schema_valid', 'deterministic', 'meaningful_text_preserved'))
    assert diagnostics['error'] == diagnostics['fatal'] == 0
    assert all(structures[k] == 0 for k in ('numbered_candidates', 'orphan_nodes', 'structured_paragraph_list_issues',
                                         'form_validation_issues', 'relation_count_mismatches'))
    assert not state['golden_validation']['audit_errors']
    limitations = [
        'Manifest semantic_complete stays false for source warnings. The report never overrides generated flags to claim full semantic completeness.',
        'Missing relation numbers/links are retained as unresolved; no external lookup or invented link is used.',
        'Formula images remain media with original source URLs/data URLs; no OCR or invented mathematical expression is supplied.',
        'Isolated bare source numbers without page-transition evidence remain visible and warned.',
        'Headerless table axes and actual duplicated legal numbers retain their source ambiguity and diagnostics.',
        'A quotation missing its closing mark stays local to the next explicit amendment boundary and retains an incomplete_source_quotation warning; no missing punctuation is inserted.',
        'Central/Local follows the existing crawler’s VBPL breadcrumb contract. Some legacy national issuers appear in the Local source category; issuing-authority source values are reported separately.',
        'The existing crawler explicitly excludes Tải về and Văn bản gốc and captures rendered HTML tabs only. Attachments were not downloaded or validated; excluded tab metadata is preserved.',
        'Some English VBPL pages are summaries and some contain source encoding artifacts. Validation covers the actual captured HTML, not missing full text or attachment content.',
        'Real capture regressions reference immutable local RAW rather than copying large HTML into Git. Portable synthetic regressions run without those local captures.']
    result = {'generated_at': datetime.now(timezone.utc).isoformat(), 'started_at': state['started_at'],
              'last_full_audit_at': state['last_audited_at'], 'schema_version': state['schema_version'], 'parser_version': state['parser_version'],
              'source': 'https://vbpl.vn', 'metrics': metrics, 'documents': documents, 'repairs': repairs,
              'golden_validation': state['golden_validation'], 'wave_audits': state['waves'],
              'unsuccessful_candidates': [a for a in state['attempts'] if a['result'] != 'complete'],
              'remaining_limitations': limitations, 'all_desired_quality_flags_true': all(quality[k] == n for k in
                                    ('schema_valid', 'deterministic', 'meaningful_text_preserved', 'semantic_complete')),
              'verification': {'unit_tests': test_count, 'passed': True, 'command': '.venv/bin/python -m unittest discover -s tests -t . -q',
                               'output_log': str(evidence_dir / 'tests.txt')}}
    if config.require_wave_gates:
        from .wave_gate import parser_fingerprint, validation_failures
        gates = state.get('wave_completions', [])
        assert {g['wave'] for g in gates} == set(range(1, config.waves + 1)), 'Not all wave gates completed'
        assert state['audited_parser_fingerprint'] == parser_fingerprint(), 'Final parser audit is stale'
        assert state['waves'][-1]['regenerated'], 'Final uniform re-extraction is mandatory'
        baseline = state['baseline_validations']
        cumulative = [d['final_validation'] for d in state['documents'] + baseline] + [state['golden_validation']]
        assert not any(validation_failures(v) for v in cumulative), 'Cumulative parser regression'
        assert all(r.get('parser_fingerprint') == parser_fingerprint() for r in review_by_id.values()), 'Stale semantic review'
        metrics['crawl'].update(acquisition_accounting(state))
        metrics['repair']['new_portable_hardening_test_methods'] = test_methods('regression/test_hardening_patterns.py')
        result['verification']['command'] = read(evidence_dir / 'test-state.json')['command']
        metrics['quality'].update(source_ambiguity_retained=sum(bool(r.get('source_ambiguity_retained')) for r in review_by_id.values()),
                                  source_warning_documents=sum(bool(d['important_diagnostics']) for d in documents),
                                  expected_source_artifact_documents=sum(any(f['classification'] == 'expected_non_semantic_source_artifact'
                                      for f in r.get('findings', [])) for r in review_by_id.values()),
                                  parser_failure=sum(r.get('parser_failure', 0) for r in review_by_id.values()),
                                  unexplained_semantic_failure=sum(r.get('unexplained_semantic_failure', 0) for r in review_by_id.values()))
        cumulative_quality = {k: sum(v['quality'][k] for v in cumulative) for k in
                              ('schema_valid', 'deterministic', 'meaningful_text_preserved', 'semantic_complete')}
        result['cumulative_validation'] = {'documents': len(cumulative), 'previous_documents': len(baseline),
            'new_documents': n, 'golden': 1, 'quality_counts': cumulative_quality,
            'statuses': dict(Counter(v['status'] for v in cumulative)),
            'issue_summary': dict(sum((Counter(v['issue_summary']) for v in cumulative), Counter())),
            'baseline_validations': baseline, 'parser_fingerprint': parser_fingerprint()}
        result['wave_completions'] = gates
        result['wave_findings'] = [{'wave': g['wave'], 'documents_processed': min(config.wave_size, n - (g['wave'] - 1) * config.wave_size),
            'new_parser_bug_classes': len(g['new_parser_bug_classes']), 'generic_repairs': g['new_parser_bug_classes'],
            'source_ambiguity_documents': sum(r.get('source_ambiguity_retained', False) for r in review_by_id.values() if r['wave'] == g['wave']),
            'raw_capture_defects': sum(r.get('wave') == g['wave'] for r in repairs['raw_capture_defects']),
            'schema_gaps': sum(r.get('wave') == g['wave'] for r in repairs['schema_gaps']),
            'unexplained_failures': sum(r.get('unexplained_semantic_failure', 0) for r in review_by_id.values() if r['wave'] == g['wave'])}
            for g in sorted(gates, key=lambda g: g['wave'])]
        curve = [len(g['new_parser_bug_classes']) for g in sorted(gates, key=lambda g: g['wave'])]
        converged = len(curve) >= 2 and max(curve[-2:]) <= 2 and curve[-1] <= curve[-2]
        result['convergence'] = {'new_bug_classes_by_wave': curve, 'cumulative_bug_classes': sum(curve),
                                'sufficient_for_larger_validation': converged,
                                'criterion': 'At most two new bug classes in each final wave, with no increase in the last wave; all acceptance gates pass.'}
        result['recommendation'] = 'B: scale to a larger validation batch' if converged else 'A: continue with another hardening batch'
    return result


def markdown(report, report_dir):
    """Render reviewed evidence without batch-specific claims or thresholds."""
    metrics = report['metrics']
    n = metrics['crawl']['selected']
    waves = len({d['wave'] for d in report['documents']})
    lines = [f'# VBPL {n}-document Extract validation', '',
             f"Run: {report['started_at']} → {report['last_full_audit_at']} (UTC). "
             f"Schema/parser: {report['schema_version']} / {report['parser_version']}.", '',
             f'{n} selected documents were audited across {waves} capture waves. '
             'The golden is additional to the sample.', '',
             f"Extract results: {metrics['extract']}. Crawl accounting: {metrics['crawl']}.", '',
             '| Quality | Count | Rate |', '|---|---:|---:|']
    for key, value in metrics['quality'].items():
        if isinstance(value, dict):
            lines.append(f"| {key} | {value['count']}/{value['evaluated']} | {value['rate']:.0%} |")
    lines += ['', f"Diagnostics: {metrics['diagnostics']}. Structure checks: {metrics['structure']}.", '',
              f"Actual source document types: {metrics['actual_document_types']}.", '',
              '## Final document inventory', '',
              '| # / wave | Document ID and source URL | Scope | Source type / number | Crawl | Extract | W/E/F |',
              '|---|---|---|---|---|---|---|']
    for d in report['documents']:
        scope = 'Central' if d['scope'] == 'trung_uong' else 'Local'
        issues = d['issue_summary']
        lines.append(f"| {d['sequence']} / {d['wave']} | [{d['document_id']}]({d['source_url']}) | "
                     f"{scope} | {d['document_type']} / {d['document_number']} | {d['crawl_result']} | "
                     f"{d['final_extract_status']} | {issues['warning']}/{issues['error']}/{issues['fatal']} |")
    lines += ['', '## Source ambiguities retained', '',
              'Generated quality flags retain source warnings. Exact anchors and excerpts are in the JSON companion.', '']
    for d in report['documents']:
        if d['important_diagnostics']:
            counts = Counter(i['code'] for i in d['important_diagnostics'])
            lines.append(f"- {d['document_id']}: {dict(counts)}. {d['semantic_review']['notes']}")
    lines += ['', '## Recorded repairs', '']
    for r in report['repairs']['parser_repairs']:
        ids = ', '.join(d['document_id'] for d in r['documents'])
        lines.append(f"- **{r['id']}** ({ids}): {r['root_cause']} {r['fix']}")
    for r in report['repairs'].get('regression_discovered_repairs', []):
        lines.append(f"- **{r['id']}**: {r['root_cause']} {r['fix']} {r['evidence']}")
    lines += ['', '## Regression and verification', '',
              f"{report['verification']['unit_tests']} unit tests passed according to "
              f"`{report['verification']['output_log']}`.", '',
              f"Golden quality: {report['golden_validation']['quality']}. "
              f"Invariants: {report['golden_validation']['invariants']}.", '',
              f"Machine report: `{report_dir / 'report.json'}`.", '',
              '## Remaining limitations', '']
    lines += ['- ' + item for item in report['remaining_limitations']]
    if 'cumulative_validation' in report:
        cumulative = report['cumulative_validation']
        lines += ['', '## Final uniform cumulative validation', '',
                  f"{cumulative['documents']} documents: {cumulative['golden']} golden + "
                  f"{cumulative['previous_documents']} previous + {cumulative['new_documents']} new.",
                  f"Quality counts: {cumulative['quality_counts']}. Statuses: {cumulative['statuses']}.",
                  f"Diagnostics: {cumulative['issue_summary']}. Final implementation SHA-256: `{cumulative['parser_fingerprint']}`.", '',
                  '## Wave gates and convergence', '', '| Wave | New bug classes | Accumulated documents |', '|---|---|---:|']
        for gate in sorted(report['wave_completions'], key=lambda g: g['wave']):
            lines.append(f"| {gate['wave']} | {', '.join(gate['new_parser_bug_classes']) or 'None'} | {gate['accumulated_documents']} |")
        lines += ['', f"Convergence: {report['convergence']}.", '', f"Recommendation: {report['recommendation']}.", '',
                  f"Reviewed source ambiguity documents: {metrics['quality']['source_ambiguity_retained']}; "
                  f"parser failures: {metrics['quality']['parser_failure']}; unexplained semantic failures: "
                  f"{metrics['quality']['unexplained_semantic_failure']}."]
    return '\n'.join(lines) + '\n'


def write_report(config: ValidationConfig, output_dir: Path | None = None, **inputs):
    """Build both artifacts; use a separate output directory to retain history."""
    report = build_report(config, **inputs)
    destination = output_dir or config.report_dir
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (destination / 'report.md').write_text(markdown(report, destination), encoding='utf-8')
    return report


def total_corpus_metrics(target, validations, fingerprint):
    """Count source identities once and distinguish partial evidence from acceptance."""
    target_ids = [d['document_id'] for d in target['documents']]
    if len(target_ids) != len(set(target_ids)) or len(target_ids) > target['target_total']:
        raise ValueError('Target contains duplicates or exceeds its total')
    identities = [d['document_id'] for d in validations]
    if len(identities) != len(set(identities)) or not set(identities) <= set(target_ids):
        raise ValueError('Validation records must be distinct target source identities')
    current = [d for d in validations if d.get('parser_fingerprint') == fingerprint]
    statuses = Counter(d['validation']['status'] for d in current)
    quality = Counter(k for d in current for k, v in d['validation']['quality'].items() if v)
    diagnostics = sum((Counter(d['validation']['issue_summary']) for d in current), Counter())
    from .wave_gate import validation_failures
    failures = [d['document_id'] for d in current if validation_failures(d['validation']) or d.get('semantic_review', {}).get('parser_failure', 0)]
    reviewed = [d for d in current if d.get('semantic_review', {}).get('reviewed')
                and d['semantic_review'].get('parser_fingerprint') == fingerprint]
    complete = (len(target_ids) == target['target_total'] == len(current) == len(reviewed)
                and not failures and not any(d.get('semantic_review', {}).get('unexplained_semantic_failure', 0) for d in current)
                and all(quality[k] == len(current) for k in
                    ('schema_valid', 'deterministic', 'meaningful_text_preserved')))
    return {'target_total': target['target_total'], 'target_assembled': len(target_ids),
            'current_parser_validated': len(current), 'source_reviewed': len(reviewed),
            'pending_target_assembly': target['target_total'] - len(target_ids),
            'pending_current_parser_validation': len(target_ids) - len(current),
            'acceptance_complete': complete, 'statuses': {
                **dict(statuses), **{k: statuses[k] for k in ('success', 'success_with_warnings', 'failed')}},
            'quality': {k: {'count': quality[k], 'evaluated': len(current),
                           'rate': quality[k] / len(current) if current else None} for k in
                        ('schema_valid', 'deterministic', 'meaningful_text_preserved', 'semantic_complete')},
            'source_ambiguity_retained': sum(d.get('semantic_review', {}).get('source_ambiguity_retained', False) for d in current),
            'parser_failure': len(failures),
            'unexplained_semantic_failure': sum(d.get('semantic_review', {}).get('unexplained_semantic_failure', 0) for d in current),
            'diagnostics': {k: diagnostics[k] for k in ('info', 'warning', 'error', 'fatal')},
            'unresolved_ids': failures}


def write_total_report(report_dir, target, validations, fingerprint, **context):
    """Publish resumable total-corpus evidence, including an explicitly incomplete run."""
    from .progress import atomic_json
    metrics = total_corpus_metrics(target, validations, fingerprint)
    completion = context.get('completion_checks', {})
    metrics['corpus_validation_complete'] = metrics['acceptance_complete']
    metrics['acceptance_complete'] &= all(completion.get(k) is True for k in (
        'uniform_revalidation', 'wave_gates', 'tests', 'repository_hygiene'))
    report = {'generated_at': datetime.now(timezone.utc).isoformat(),
              'status': 'complete' if metrics['acceptance_complete'] else 'incomplete',
              'parser_fingerprint': fingerprint, 'metrics': metrics,
              'target_manifest': target, 'documents': validations, **context}
    atomic_json(report_dir / 'report.json', report)
    lines = [f"# VBPL total-{target['target_total']} validation", '',
             f"Status: **{report['status']}**. This is a total local source-document target; it is not a newly crawled-document count.", '',
             f"Target assembled: {metrics['target_assembled']}/{metrics['target_total']}. "
             f"Current-parser validated: {metrics['current_parser_validated']}. Source-reviewed: {metrics['source_reviewed']}.", '',
             f"Documents still needed: {metrics['pending_target_assembly']}. "
             f"Final total-{target['target_total']} acceptance: {metrics['acceptance_complete']}.", '',
             f"Implementation fingerprint: `{fingerprint}`.", '',
             f"Extract: {metrics['statuses']}. Quality: {metrics['quality']}.", '',
             f"Source ambiguity documents: {metrics['source_ambiguity_retained']}; parser failures: {metrics['parser_failure']}; "
             f"unexplained semantic failures: {metrics['unexplained_semantic_failure']}. Diagnostics: {metrics['diagnostics']}.", '']
    for key, value in context.items():
        if key == 'previous_milestone':
            lines += ['## Preserved first milestone', '', str(value), '']
        else:
            lines += [f"## {key.replace('_', ' ').capitalize()}", '', '```json',
                      json.dumps(value, ensure_ascii=False, indent=2), '```', '']
    lines += ['## Resume', '', 'Read evidence/state.json, checkpoint.md, target_manifest.json and resume.md. '
              'Preserve complete RAW and reviewed fixtures; regenerate stale outputs offline. '
              'Resume the first unfinished operation; preserve unique evidence during cleanup.', '']
    (report_dir / 'report.md').write_text('\n'.join(lines), encoding='utf-8')
    return report


def write_target_report(config, target_path, output_dir=None):
    """Reuse stored cumulative audits and explicit source reviews for a total target."""
    from .wave_gate import parser_fingerprint
    evidence = config.report_dir / 'evidence'
    state = read(config.sample_manifest)
    target = read(target_path)
    reviews = {d['document_id']: d for d in read(evidence / 'cumulative_reviews.json')['documents']}
    records = [
        {'document_id': d['document_id'], 'parser_fingerprint': d.get('audited_parser_fingerprint'),
         'validation': d['final_validation'], 'semantic_review': reviews.get(d['document_id'], {})}
        for d in state.get('baseline_validations', []) + state['documents'] if 'final_validation' in d
    ]
    if 'golden_validation' in state:
        identity = 'vbpl:' + config.golden_id
        records.append({'document_id': identity, 'parser_fingerprint': state.get('audited_parser_fingerprint'),
                        'validation': state['golden_validation'], 'semantic_review': reviews.get(identity, {})})
    context_path = evidence / 'report-context.json'
    context = read(context_path) if context_path.exists() else {}
    return write_total_report(output_dir or config.report_dir, target, records, parser_fingerprint(), **context)
