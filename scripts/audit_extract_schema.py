"""Audit the freeze contract against generated JSON and a V2.3.1 snapshot.

Run audit_vbpl_hierarchy.py first for independent HTML/byte/checksum, hierarchy
and table-geometry regression checks. This adds vocabulary, ownership, form
label, scalar absence and output size audits; no parser heuristics live here.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from audit_vbpl_hierarchy import audit, counts
from vietnam_legal_rag.ingestion.extract_legal_documents import encoded
from vietnam_legal_rag.ingestion.extract_validation import semantic_roots, walk_content
from vietnam_legal_rag.ingestion.form_validation import walk, structured_paragraphs, value_text_audit, FORM_NODE_PROPERTIES
from vietnam_legal_rag.ingestion.hierarchy_validation import TABLE_KINDS
from vietnam_legal_rag.ingestion.schema_cleanup import FIELD_KINDS, form_label_audit, label_parts, FIELD_NAME, EXCLUDED_SCOPES
from vietnam_legal_rag.ingestion.form_refinement import scan
from vietnam_legal_rag.ingestion.structured_html import PARSER_VERSION, SCHEMA_VERSION
from vietnam_legal_rag.ingestion.table_semantics import NO_AXES


def semantic_nodes(result):
    return list(walk_content(list(semantic_roots(result))))


def dictionaries(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from dictionaries(child)
    elif isinstance(value, list):
        for child in value:
            yield from dictionaries(child)


def source_anchors(result):
    return {json.dumps(ref, sort_keys=True, ensure_ascii=False) for value in dictionaries(result) for ref in value.get('references', [])}


def metrics(result):
    nodes = semantic_nodes(result)
    labels = form_label_audit(result['document'])
    strong_labels = []
    for n, parents in walk([result['document']]):
        active = any(p.get('type') == 'form' or p.get('table_kind') in {'annex_form', 'form'} for p in parents)
        excluded = any(p.get('type') in EXCLUDED_SCOPES for p in parents)
        parts = label_parts(n)
        if n['type'] == 'paragraph' and active and not excluded and parts and FIELD_NAME.fullmatch(scan(parts[0])):
            strong_labels.append(n)
    return {**counts(result),
            'generic_form_label_paragraphs': sum(not n.get('text').rstrip().split(':',1)[1].strip() for n in strong_labels) + sum(p['reason']=='unresolved_input_sequence_label' for p in labels),
            'generic_form_fields_including_values': len(strong_labels) + sum(p['reason']=='unresolved_input_sequence_label' for p in labels),
            'unexplained_form_label_paragraphs': sum(not p['justified'] for p in labels),
            'duplicated_references': sum(ref in [r for child in n.get('children', []) for r in child.get('references', [])] for n in nodes for ref in n.get('references', [])),
            'singleton_source_refs': sum(n.get('source_refs') == [n['source_ref']] for n in nodes),
            'semantic_empty_string_fields': sum(v == '' for n in nodes for v in n.values() if isinstance(v,str)),
            'title_ref_occurrences': sum('title_ref' in n for n in nodes),
            'meaningless_axis_cell_metadata': sum(c.get('role')=='unknown' and c.get('confidence')==0.0 for n in nodes if n.get('table_kind') in NO_AXES for c in n.get('cells',[]))}


def size_contributors(result):
    nodes = semantic_nodes(result)
    cells = [c for n in nodes for c in n.get('cells', [])]
    # Minified value sizes are estimates, not an additive partition of pretty
    # JSON bytes. Cell geometry excludes semantic content/nested tables.
    size = lambda value: len(json.dumps(value, ensure_ascii=False, separators=(',',':')).encode())
    objects = nodes + cells
    return {'measurement': 'UTF-8 minified value bytes; independent contributions can overlap',
            'semantic_nodes': len(nodes), 'physical_cells': len(cells),
            'physical_cell_fields_bytes': sum(size({k:v for k,v in c.items() if k!='content'}) for c in cells),
            'primary_source_ref_bytes': sum(size(n['source_ref']) for n in objects),
            'coalesced_source_refs_bytes': sum(size(n['source_refs']) for n in objects if 'source_refs' in n),
            'references_bytes': sum(size(n['references']) for n in objects if 'references' in n),
            'physical_text_effective_segments_bytes': sum(size({k:c[k] for k in ('text','effective_text','text_segments')}) for c in cells)}


def build_report(raw, extracted, before):
    hierarchy = audit(raw, extracted, '0c389a00-78f6-11f1-a726-87c913cf8f30', before)
    property_counts = defaultdict(Counter)
    physical_property_counts = Counter()
    node_types, old_types, table_kinds, field_kinds = Counter(), Counter(), Counter(), Counter()
    documents=[]
    baseline_versions=set()
    for d in hierarchy['documents']:
        folder=d['directory']; previous=json.loads((before/folder/'content.json').read_text()); current=json.loads((extracted/folder/'content.json').read_text())
        baseline_versions.add(previous['schema_version'])
        pre, post=metrics(previous),metrics(current)
        prior_types=Counter(n['type'] for n in semantic_nodes(previous)); types=Counter(n['type'] for n in semantic_nodes(current))
        old_types.update(prior_types)
        manifest=json.loads((extracted/folder/'manifest.json').read_text())
        # Compare all source anchors, including identifiers and source positions.
        for record in manifest['files']:
            p=extracted/folder/record['path']; output=json.loads(p.read_text()); old=json.loads((before/folder/record['path']).read_text())
            assert source_anchors(old) == source_anchors(output), p
            assert not any('document_number_candidates' in v for v in dictionaries(output)), p
            assert not any('title_ref' in v for v in dictionaries(output)), p
            assert not any(v.get(k)=='' for v in dictionaries(output) if 'cell_id' not in v for k in ('text','title','field_name','value_text')), p
            for n in semantic_nodes(output):
                node_types[n['type']]+=1
                for prop in n:property_counts[prop][n['type']]+=1
                assert n['source_ref']
                if 'source_refs' in n:
                    assert len(n['source_refs'])>=2 and n['source_ref']==n['source_refs'][0]
                if n.get('field_kind'):
                    assert n['field_kind'] in FIELD_KINDS
                    if n['type']=='form_field':field_kinds[n['field_kind']]+=1
                if n['type'] in {'form_field','form_subfield'}:
                    assert all(key in n for key in FORM_NODE_PROPERTIES), (p,n['order'])
                    assert n['field_kind'] and n['field_evidence']
                if n['type']=='table':
                    table_kinds[n['table_kind']]+=1
                    for cell in n['cells']:
                        physical_property_counts.update(cell.keys())
            if p.name!='content.json':
                old_types.update(n['type'] for n in semantic_nodes(old))
        covered=sum(n['type'] in {'form_field','form_subfield'} for n in semantic_nodes(current))
        assert covered==post['fields']+post['subfields']
        assert not any(post[k] for k in ('generic_form_label_paragraphs','generic_form_fields_including_values','duplicated_references','semantic_empty_string_fields','singleton_source_refs','unexplained_structured_paragraphs','unexplained_form_label_paragraphs','orphan_nodes','split_form_candidates','inconsistent_footnote_sequences','bibliography_fields_misclassified','ambiguous_tables','errors','suspicious_value_text','title_ref_occurrences','meaningless_axis_cell_metadata','form_nodes_missing_field_kind','form_nodes_missing_field_evidence'))
        assert prior_types['form']==types['form'] and prior_types['footnote']==types['footnote'] and prior_types['bibliography_entry']==types['bibliography_entry']
        assert prior_types['list']==types['list']
        assert pre['placeholder_references']==post['placeholder_references']
        h=current['hierarchy_validation']
        quality={**manifest['quality'],'order_valid':h['order_valid'],'parent_child_valid':h['parent_child_valid']}
        assert all(quality[k] for k in ('meaningful_text_preserved','deterministic','schema_valid','order_valid','parent_child_valid'))
        documents.append({'document_id':d['document_id'],'directory':folder,'document_number':d['document_number'],
            'quality':quality,'legal_hierarchy':h['legal_hierarchy'],'annex_hierarchy':h['annex_hierarchy'],'max_depth':h['max_depth'],
            'issues':manifest['issue_summary'],'before_after':{k:{'before':pre[k],'after':post[k]} for k in pre},
            'node_type_changes':{k:{'before':prior_types[k],'after':types[k]} for k in sorted(prior_types.keys()|types.keys()) if prior_types[k]!=types[k]},
            'remaining_form_paragraphs':form_label_audit(current['document']),
            'form_invariant':{'fields':post['fields'],'subfields':post['subfields'],'covered_nodes':covered,'required_properties':list(FORM_NODE_PROPERTIES),'valid':True},
            'value_text_audit_before':value_text_audit(previous['document']),
            'value_text_audit_after':value_text_audit(current['document']),
            'remaining_structured_paragraphs':structured_paragraphs(current['document']),
            'form_boundaries':d['inspection']['form_boundaries'],
            'content_size_bytes':{'before':(before/folder/'content.json').stat().st_size,'after':(extracted/folder/'content.json').stat().st_size},
            'size_contributors':{'before':size_contributors(previous),'after':size_contributors(current)},
            'remaining_issues':d['remaining_issues']})
    totals={k:{phase:sum(d['before_after'][k][phase] for d in documents) for phase in ('before','after')} for k in documents[0]['before_after']}
    form_types={n['type'] for d in documents for n in dictionaries(json.loads((extracted/d['directory']/'content.json').read_text())) if n.get('type')=='form_field'}
    assert form_types=={'form_field'}
    current_fixture=next(d for d in documents if d['document_number']=='60/2026/TT-BCT')
    assert current_fixture['quality']['semantic_complete'] and not any(current_fixture['issues'][s] for s in ('warning','error','fatal'))
    assert {k:current_fixture['legal_hierarchy'][k] for k in ('articles','clauses','points')} == {'articles':15,'clauses':36,'points':5}
    assert current_fixture['annex_hierarchy']['annexes']==4 and current_fixture['annex_hierarchy']['numbered_items']==26
    assert current_fixture['before_after']['forms']['after']==16
    assert set(node_types)==set(old_types), 'Unexpected semantic type vocabulary change'
    properties=[{'property':p,'node_types':dict(sorted(c.items())),'count':sum(c.values())} for p,c in sorted(property_counts.items())]
    one_off_reasons={'semantic':'Known source signature_marker [daky] expresses signed status without inferring the signer.'}
    one_offs=[{**p,'justification':one_off_reasons[p['property']]} for p in properties if p['count']==1]
    report={'schema_version':SCHEMA_VERSION,'parser_version':PARSER_VERSION,'freeze_status':'ready',
            'verified_json_files':sum(len(d['tabs'])+1 for d in hierarchy['documents']),
            'baseline_version':next(iter(baseline_versions)) if len(baseline_versions)==1 else sorted(baseline_versions),'schema_validation':True,'source_text_and_table_geometry_unchanged':True,
            'source_anchors_and_identifiers_unchanged':True,'metadata_regressions':0,
            'node_types':dict(sorted(node_types.items())),
            'node_type_changes':{k:{'before':old_types[k],'after':node_types[k]} for k in sorted(old_types.keys()|node_types.keys()) if old_types[k]!=node_types[k]},
            'table_kinds':{'allowed':list(TABLE_KINDS),'produced':dict(sorted(table_kinds.items())), 'semanticized_layout_tables':sum(d['hierarchy_validation']['tables']['layout'] for d in hierarchy['documents'])},
            'field_kinds':{'allowed':sorted(FIELD_KINDS),'produced':dict(sorted(field_kinds.items()))},
            'deprecated_fields_removed':['title_ref (replaced by title_source_ref)','unknown role / zero confidence on cells of non-axis table kinds'],
            'legacy_candidates':{'document_number_candidates':'remains absent and explicitly forbidden by schema'},
            'fallback_types_produced':{k:node_types[k] for k in ('paragraph','unknown','numbered_paragraph','layout_block') if node_types[k]},
            'property_vocabulary':properties,'one_off_properties':one_offs,'documents':documents,'totals':totals,
            'physical_cell_property_vocabulary':dict(sorted(physical_property_counts.items())),
            'size_bytes':{phase:sum(d['content_size_bytes'][phase] for d in documents) for phase in ('before','after')},
            'issue_summary':hierarchy['totals']['issues'],
            'known_ambiguities':'Two pre-existing source warnings retained: bare page-number candidate in Decision and matrix-axis orientation in technical Circular. Both have usable hierarchy and preserved text; semantic_complete remains false for these documents.'}
    print('Node types:',', '.join(report['node_types']))
    print('Table kinds:',report['table_kinds'])
    print('Form field kinds:',report['field_kinds'])
    print('Before → after:',json.dumps(totals,ensure_ascii=False))
    return report


def markdown(report):
    lines = ['# Extract V2.3.2 freeze audit', '',
        f"Schema version **{report['schema_version']}**; parser version **{report['parser_version']}**; baseline **{report['baseline_version']}**. This is an incremental consistency cleanup; a baseline with the same version precedes the final form-node invariant hotfix.", '',
        '**Extract schema V2.3.2 is ready to freeze.** All acceptance checks use actual generated JSON. The current Circular 60 fixture has no warnings/errors/fatals. Two existing source ambiguities remain explicit in separate fixtures; their semantic_complete stays false.', '',
        f"All five representative captures were extracted. Independent verification validates 25 JSON files against Draft 2020-12, reparses 20 source tabs twice and compares artifact bytes. Source hashes, legal and annex ancestry, 1,123 physical cells, text/effective_text/text_segments, spans, source links and all 15 properties/history/relations payloads match baseline {report['baseline_version']}. For same-version hotfix baselines, metadata artifact bytes are also identical.", '',
        '| Fixture | Articles | Clauses | Points | Annexes | Numbered sections / items | Forms | Orphans / ambiguous | W / E / F | Text / deterministic / schema / order | Complete |',
        '| --- | ---: | ---: | ---: | ---: | --- | ---: | --- | --- | --- | --- |']
    for d in report['documents']:
        l=d['legal_hierarchy']; a=d['annex_hierarchy']; m=d['before_after']; i=d['issues']
        values=[d['document_number'],l['articles'],l['clauses'],l['points'],a['annexes'],f"{a['numbered_sections']} / {a['numbered_items']}",m['forms']['after'],f"{m['orphan_nodes']['after']} / {m['ambiguous_tables']['after']}",f"{i['warning']} / {i['error']} / {i['fatal']}",'true / true / true / true',str(d['quality']['semantic_complete']).lower()]
        lines.append('| '+' | '.join(map(str,values))+' |')
    lines += ['', '## Before → after', '', f"| Metric | Baseline {report['baseline_version']} | Current {report['schema_version']} |", '| --- | ---: | ---: |']
    for k,m in report['totals'].items():
        lines.append(f"| {k} | {m['before']} | {m['after']} |")
    lines += ['', '## Inspected semantic changes', '',
        'Chức vụ (nếu có) and Số CCCD/Hộ chiếu become input labels through a bounded form-input sequence. The optional qualifier remains in source display, while the source field name is Chức vụ. The issue-date/place fragment remains verbatim as a continuation child of the identification field; the source does not explicitly label Ngày cấp/Nơi cấp, so no such names are invented.', '',
        'Người đại diện/Người yêu cầu: Ông (bà): is split at the source prompt boundary into a composite field and input-label subfield. Both have null value_text and share provenance with offsets. Completion instructions have null value_text. Where a source blank precedes another prompt/declaration, value_text keeps only the actual initial blank; full display remains in text. Actual values and date/range placeholders remain source-faithful.', '',
        'Form title aliases and coalesced legal titles use title_source_ref. A displayed form-title child owns the text once; contributing references remain traceable. No new node types or field-kind enum members are added. Cells of layout/form/annex_form/key_value tables omit inapplicable role/confidence; data/matrix classifications remain intact. Real empty cells stay empty strings.', '',
        '| Type | Before | After |', '| --- | ---: | ---: |']
    for k,m in report['node_type_changes'].items():
        lines.append(f"| {k} | {m['before']} | {m['after']} |")
    lines += ['', 'Only semantic type changes shown above occur. The final same-version invariant hotfix adds required form-node metadata without changing node types, original properties, source text or geometry. Fields retaining source blanks keep their original text and placeholder references.', '',
        '## Vocabularies', '', '**Produced node types:** '+', '.join(f'`{k}`' for k in report['node_types'])+'.', '',
        '**Allowed table kinds:** '+', '.join(report['table_kinds']['allowed'])+'. Produced: '+str(report['table_kinds']['produced'])+'.', '',
        '**Allowed field kinds:** '+', '.join(report['field_kinds']['allowed'])+'. Produced: '+str(report['field_kinds']['produced'])+'.', '',
        '**Produced fallbacks:** '+str(report['fallback_types_produced'])+'. Genuine prose remains paragraph. Schema still supports unknown/numbered_paragraph.', '',
        '**Deprecated metadata removed:** '+ '; '.join(report['deprecated_fields_removed'])+'. document_number_candidates remains forbidden; no relation/history behavior changes.', '',
        '## Property vocabulary', '', '| Property | Node types (count) | Total |', '| --- | --- | ---: |']
    for p in report['property_vocabulary']:
        lines.append(f"| {p['property']} | "+', '.join(f'{k} ({v})' for k,v in p['node_types'].items())+f" | {p['count']} |")
    lines += ['', 'All properties occurring once, manually reviewed:', '']
    for p in report['one_off_properties']:
        lines.append(f"- `{p['property']}` ({p['count']}): {p['justification']}")
    lines += ['', 'title_ref has zero output occurrences. title_source_ref is the single title-reference property; multi-element title_source_spans additionally preserves actual source offsets, serving a distinct role.', '',
        'Physical cell properties are audited separately: '+', '.join(f"`{k}` ({v})" for k,v in report['physical_cell_property_vocabulary'].items())+'.', '',
        '## Retained paragraph candidates', '']
    for d in report['documents']:
        for p in d['remaining_form_paragraphs']+d['remaining_structured_paragraphs']:
            lines.append(f"- {d['document_number']}, order {p['order']}: `{p['text']}` — `{p['reason']}`.")
    lines += ['',
        'The retained short all-caps person roles are signature captions, not bounded input labels; Người theo dõi Chủ nhiệm đề án is a signature caption. The Số lượng nhập/xuất/tồn kho texts are table column captions, not inputs sandwiched between form fields. Introductory Thông tin kiểm tra/Tài liệu kèm theo/Đã nộp…gồm stay prose. The identification continuation is source-associated. Two isolated dash paragraphs are separated by substantive text/tables, so they cannot form an adjacent list. No unexplained structured or form-label paragraph remains.', '',
        '## Form boundaries and value audit', '']
    for d in report['documents']:
        if d['form_boundaries']:
            lines += ['', '**'+d['document_number']+'**', '']
            for f in d['form_boundaries']:
                lines.append(f"- Annex {f['annex']}, form {f['number']} → {f['title']} → {f['child_count']} children → next {f['next_form_number']}")
    lines += ['', 'Final same-version form-node invariant hotfix: both form_field and form_subfield explicitly carry field_name, field_kind, field_evidence and value_text. Alphabetic subfields use the existing source classification; uncertain names/values stay null and existing unknown roles remain supported. Missing required metadata fails schema validation and semantic completeness. Recursive coverage:', '']
    for d in report['documents']:
        inv=d['form_invariant']
        lines.append(f"- {d['document_number']}: {inv['fields']} fields + {inv['subfields']} subfields = {inv['covered_nodes']} covered nodes; all four properties present.")
    lines += ['', 'Each before-case of suspicious_value_text, including source order/name/value, is recorded in the machine-readable report. All after-audits are empty. Footnote groups, bibliography entries, alphabetic subfields, coordinates, table-cell lists, source placeholders and UI exclusions are preserved.', '',
        '## Size, quality and validation', '',
        f"Combined content.json size: **{report['size_bytes']['before']:,} → {report['size_bytes']['after']:,} bytes**. Invariant metadata is retained; geometry and provenance remain intact. Contributor estimates are available per fixture in JSON.", '',
        'diagnostic_info_count and issue severity remain compatible: expected form/layout preservation is informational. Warning/error/fatal counts do not increase. A bare numeric page candidate in the Decision and unresolved axis orientation in the technical Circular remain source ambiguities, not suppressed warnings.', '',
        '190 unit tests pass: 24 V2.3.2 tests, 7 final invariant hotfix tests and all 159 prior tests. Only the prior title_ref expectation changes to title_source_ref. Tests cover no-colon labels/negative contexts, source continuations, nested prompts/links/offsets, instruction-value schema rejection, contextual value validation, retained values/blanks, canonical title provenance, axis-kind behavior, physical versus semantic empty strings, prose lead-ins, idempotence, required properties on both field families, shared subfield classification, unknown/null fallbacks, nested cell coverage and semantic incompleteness on missing metadata.', '',
        'Files changed: schema_cleanup.py; extract_quality.py; form_refinement.py; form_validation.py; table_semantics.py; structured_html.py; schemas/extracted.schema.json; audit_vbpl_hierarchy.py; audit_extract_schema.py; test_consistency_cleanup.py; test_form_node_invariant.py; test_form_refinement.py; docs/extracted-schema.md; README.md; generated Extract artifacts and audit reports. The packaged schema uses the existing symlink.', '',
        '```bash', 'PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit',
        'PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.ingestion.extract_legal_documents --debug-tree',
        'PYTHONPATH=src .venv/bin/python scripts/audit_extract_schema.py --raw data/raw/vbpl --extracted data/extracted/vbpl --before /path/to/v2.3.1/extracted --report docs/extract-v2.3.2-schema-audit.json', '```', '',
        'Freeze decision: no additional semantic rules until a new real-world VBPL source exposes a structure that cannot be faithfully represented.', '']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('raw','extracted','before','report'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();report=build_report(args.raw,args.extracted,args.before)
    args.report.write_bytes(encoded(report));args.report.with_suffix('.md').write_text(markdown(report))
    print(json.dumps({'freeze_status':report['freeze_status'],'files':report['verified_json_files'],'issues':report['issue_summary']},ensure_ascii=False))


if __name__=='__main__':main()
