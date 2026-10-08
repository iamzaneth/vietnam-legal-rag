"""Compare JSON sizes and independently audit a regenerated extracted corpus."""
from __future__ import annotations

import json
from vietnam_legal_rag.evaluation.audit.extract import sha

from vietnam_legal_rag.ingestion.validation.quality import Quality, issue_summary
from vietnam_legal_rag.ingestion.validation.extract import schema_validator, semantic_count
from vietnam_legal_rag.ingestion.html.source import parse_html
from vietnam_legal_rag.ingestion.html.structure import PARSER_VERSION


def compare(before, after, raw):
    old = {json.loads(p.read_text())["document_id"]: p.parent for p in before.rglob("manifest.json")}
    sources = {json.loads(p.read_text())["document_id"]: p.parent for p in raw.rglob("manifest.json")}
    documents = []
    validator = schema_validator()
    for manifest_path in sorted(after.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text())
        identifier = manifest["document_id"]
        previous, source = old[identifier], sources[identifier]
        validator.validate(manifest)
        assert manifest['source_ref']['sha256'] == sha(source/'manifest.json')
        tabs, issues = [], []
        for record in manifest["files"]:
            path = manifest_path.parent / record["path"]
            result = json.loads(path.read_text())
            validator.validate(result)
            assert result['document_id'] == identifier
            assert record['sha256'] == sha(path)
            html = source / (path.stem + '.html')
            assert result['source_ref']['sha256'] == sha(html)
            quality = Quality(); quality.ignored = result.get('ignored_elements', [])
            evidence = quality.conservation(parse_html(html.read_text()), result)
            assert evidence['meaningful_text_preserved'], (identifier, path.name)
            assert evidence['source_text_sha256'] == result['validation']['source_text_sha256']
            assert semantic_count(result) == result['validation']['semantic_elements']
            tabs.append({'file':path.name,'before_bytes':(previous/path.name).stat().st_size,
                         'after_bytes':path.stat().st_size,'semantic_elements':semantic_count(result),
                         'meaningful_characters':evidence['source_characters'],
                         'meaningful_text_sha256':evidence['source_text_sha256'],
                         'meaningful_text_preserved':True,'deterministic':result['validation']['deterministic'],
                         'issues':issue_summary(result['issues'])})
            issues.extend(result['issues'])
        old_bytes = sum(p.stat().st_size for p in previous.glob('*.json'))
        new_bytes = sum(p.stat().st_size for p in manifest_path.parent.glob('*.json'))
        documents.append({'document_id':identifier,'before_bytes':old_bytes,'after_bytes':new_bytes,
                          'reduction_percent':round((old_bytes-new_bytes)/old_bytes*100,2),
                          'semantic_elements':sum(t['semantic_elements'] for t in tabs),
                          'issues':issue_summary(issues),'status':manifest['status'],'tabs':tabs})
    old_total = sum(d['before_bytes'] for d in documents)
    new_total = sum(d['after_bytes'] for d in documents)
    old_versions = sorted({json.loads((directory/'manifest.json').read_text())['parser_version'] for directory in old.values()})
    return {'before_parser_version':old_versions[0] if len(old_versions)==1 else old_versions,'after_parser_version':PARSER_VERSION,
            'byte_measure':'UTF-8 JSON bytes including manifest; no filesystem allocation rounding',
            'text_measure':'Ordered Unicode characters after removing formatting whitespace; UI placeholders/page headings audited separately',
            'semantic_element_measure':'Legal/paragraph/list/table units + cells + fields + events + relation groups/items + source history column labels',
            'documents':documents,'totals':{'documents':len(documents),'json_files':sum(len(d['tabs'])+1 for d in documents),
            'before_bytes':old_total,'after_bytes':new_total,'reduction_percent':round((old_total-new_total)/old_total*100,2),
            'semantic_elements':sum(d['semantic_elements'] for d in documents),
            'issues':{key:sum(d['issues'][key] for d in documents) for key in ('info','warning','error','fatal')},
            'all_meaningful_text_preserved':True,'all_deterministic':all(t['deterministic'] for d in documents for t in d['tabs'])}}
