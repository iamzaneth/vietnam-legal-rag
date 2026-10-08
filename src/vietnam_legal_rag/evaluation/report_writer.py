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
    if not node:
        raise ValueError(f'Missing source anchor: {diagnostic}')
    attributes = {k: (v[:100] + '…' if len(v) > 100 else v)
                  for k, v in node.attrs.items() if k in {'href', 'src', 'alt', 'rowspan', 'colspan', 'style'}}
    return {'source_ref': node.ref, 'source_text_excerpt': node.text()[:400], 'source_attributes': attributes}


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
    return '\n'.join(lines) + '\n'


def write_report(config: ValidationConfig, output_dir: Path | None = None, **inputs):
    """Build both artifacts; use a separate output directory to retain history."""
    report = build_report(config, **inputs)
    destination = output_dir or config.report_dir
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (destination / 'report.md').write_text(markdown(report, destination), encoding='utf-8')
    return report
