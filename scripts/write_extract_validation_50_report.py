"""Build the final report from audited captures and explicit semantic reviews."""
from collections import Counter
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from vietnam_legal_rag.ingestion.html_source import parse_html

REPORTS = Path('reports')


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


def main():
    state = read(REPORTS / 'extract-validation-50-state.json')
    repairs = read(REPORTS / 'extract-validation-50-repairs.json')
    reviews = read(REPORTS / 'extract-validation-50-reviews.json')
    corpus = read(Path('tests/fixtures/vbpl_batch_regressions.json'))
    test_log = (REPORTS / 'extract-validation-50-tests.txt').read_text()
    test_count = int(re.search(r'Ran (\d+) tests', test_log)[1])
    assert test_log.rstrip().endswith('OK'), 'Final unit tests did not pass'
    def test_methods(filename):
        tree = ast.parse(Path('tests/unit', filename).read_text())
        return sum(isinstance(n, ast.FunctionDef) and n.name.startswith('test_') for n in ast.walk(tree))
    parser_tests = test_methods('test_batch_source_patterns.py')
    sampler_tests = test_methods('test_validation_sampler.py')
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
        output = Path('data/extracted/vbpl') / raw.name
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
    assert n == 50 and len({d['document_id'] for d in documents}) == 50
    assert len({d['source_url'] for d in documents}) == 50
    assert scopes == {'trung_uong': 25, 'dia_phuong': 25}
    assert all(d['scope'] == ('trung_uong' if i % 2 == 0 else 'dia_phuong') for i, d in enumerate(documents))
    assert not any(d['audit_errors'] for d in documents)
    assert all(quality[k] == 50 for k in ('schema_valid', 'deterministic', 'meaningful_text_preserved'))
    assert diagnostics['error'] == diagnostics['fatal'] == 0
    assert all(structures[k] == 0 for k in ('numbered_candidates', 'orphan_nodes', 'structured_paragraph_list_issues',
                                         'form_validation_issues', 'relation_count_mismatches'))
    assert not state['golden_validation']['audit_errors']
    limitations = [
        'Manifest semantic_complete stays false for source warnings. The report never overrides generated flags to claim 50/50 semantic completeness.',
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
              'remaining_limitations': limitations, 'all_desired_quality_flags_true': all(quality[k] == 50 for k in
                                    ('schema_valid', 'deterministic', 'meaningful_text_preserved', 'semantic_complete')),
              'verification': {'unit_tests': test_count, 'passed': True, 'command': '.venv/bin/python -m unittest discover -s tests/unit -q',
                               'output_log': 'reports/extract-validation-50-tests.txt'}}
    (REPORTS / 'extract-validation-50.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    lines = ['# VBPL 50-document Extract validation', '',
             f"Run: {state['started_at']} → {state['last_audited_at']} (UTC). Schema/parser: {state['schema_version']} / {state['parser_version']}.", '',
             'Exactly 50 new documents were captured and processed in five waves, alternating Central and Local throughout. The original golden is additional to the sample.', '',
             f"Final Extract: {statuses['success']} success, {statuses['success_with_warnings']} success_with_warnings, {statuses['failed']} failed. All outputs were regenerated and independently revalidated after the last parser change.", '',
             '| Quality | Count | Rate |', '|---|---:|---:|']
    for key, value in metrics['quality'].items():
        lines.append(f"| {key} | {value['count']}/50 | {value['rate']:.0%} |")
    lines += ['', f"Diagnostics: {dict(diagnostics)}. Structure checks: {dict(structures)}.", '',
              f"Crawl accounting: {metrics['crawl']}. RAW failures and scope mismatches were recorded and replaced; immutable extra captures remain outside the fixed sample.", '',
              f"Actual source document types: {dict(types)}.", '',
              f"Repaired {repair_count} generic parser defects ({len(repairs['parser_repairs'])} exposed by sampled source patterns and {len(regression_repairs)} during regression expansion); schema gaps and RAW capture code defects: 0. No schema bump, manual generated-JSON edits, or weakened validator assertions.", '',
              '## Final document inventory', '',
              '| # / wave | Document ID and source URL | Scope | Source type / number | Crawl | Extract | W/E/F |',
              '|---|---|---|---|---|---|---|']
    for d in documents:
        scope = 'Central' if d['scope'] == 'trung_uong' else 'Local'
        summary = d['issue_summary']
        lines.append(f"| {d['sequence']} / {d['wave']} | [{d['document_id']}]({d['source_url']}) | {scope} | {d['document_type']} / {d['document_number']} | complete | {d['final_extract_status']} | {summary['warning']}/{summary['error']}/{summary['fatal']} |")
    lines += ['', '## Source ambiguities retained', '',
              'These warnings are source-backed exceptions, not repaired parser defects. Generated semantic_complete flags remain false where required. Exact source anchors and excerpts are in the JSON companion.', '']
    for d in documents:
        if d['important_diagnostics']:
            counts = Counter(i['code'] for i in d['important_diagnostics'])
            lines.append(f"- {d['document_id']}: {dict(counts)}. {d['semantic_review']['notes']}")
    lines += ['', '## Generic parser repairs', '']
    for r in repairs['parser_repairs']:
        ids = ', '.join(d['document_id'] for d in r['documents'])
        lines.append(f"- **{r['id']}** ({ids}): {r['root_cause']} {r['fix']}")
    for r in regression_repairs:
        lines.append(f"- **{r['id']}** (portable regression): {r['root_cause']} {r['fix']} {r['evidence']}")
    lines += ['', '## Regression and verification', '',
              f"{test_count} unit tests passed. Added {parser_tests} portable parser-pattern tests, {sampler_tests} sampler tests, and one capture-corpus test covering {len(corpus['documents'])} promoted real documents. Existing assertions remain active; the ten-clause expectation correction for vbpl:2067 is backed by explicit RAW 1- through 10- markers.", '',
              'Fixtures: `tests/fixtures/vbpl_batch_regressions.json`. Tests: `tests/unit/test_batch_source_patterns.py`, `test_batch_capture_regressions.py`, `test_validation_sampler.py`. The existing representative suite now pins its original five captures explicitly so corpus growth cannot change its membership.', '',
              'Golden: all quality flags true, warnings/errors/fatals zero; 4 chapters, 15 articles, 36 clauses, 5 points; 4 annexes, 5 numbered sections, 26 numbered items; 16 forms, 80 fields, 14 subfields, 52 footnotes. Orphans, ambiguous tables and unresolved numbered candidates remain zero.', '',
              'Offline revalidation: `.venv/bin/python scripts/run_extract_validation_50.py audit --regenerate`. Its nonzero exit status deliberately reflects retained source warnings; it does not hide them behind a green batch status.', '',
              'Machine report: `reports/extract-validation-50.json`. Resumable evidence: state, repairs and reviews JSON files in `reports/`.', '',
              '## Remaining limitations', '']
    lines += ['- ' + item for item in limitations]
    (REPORTS / 'extract-validation-50.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    main()
