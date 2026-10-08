"""Offline per-document schema, fidelity, provenance and determinism checks."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse

from vietnam_legal_rag.ingestion.crawl_legal_documents import file_record
from vietnam_legal_rag.ingestion.extract_legal_documents import (
    encoded, extract_document, parse_source,
)
from vietnam_legal_rag.ingestion.validation.quality import Quality, issue_summary, status, compact_text
from vietnam_legal_rag.ingestion.validation.extract import (
    schema_validator, semantic_roots, validate_result, walk_content,
)
from vietnam_legal_rag.ingestion.html.source import parse_html


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_document(directory, regenerate=False, extracted_dir=Path("data/extracted/vbpl")):
    if regenerate:
        extract_document(directory, extracted_dir / directory.name)
    output = extracted_dir / directory.name
    manifest = json.loads((output / "manifest.json").read_text())
    raw_manifest = json.loads((directory / "manifest.json").read_text())
    errors = []
    schema = schema_validator()
    for error in schema.iter_errors(manifest):
        errors.append("Manifest schema: " + error.message)
    if manifest["document_id"] != raw_manifest["document_id"]:
        errors.append("Manifest identity differs from RAW")
    if manifest["source_ref"]["sha256"] != file_record(directory / "manifest.json", directory)["sha256"]:
        errors.append("RAW manifest checksum mismatch")
    tabs, diagnostics, all_nodes = {}, [], []
    summaries = Counter()
    for record in manifest["files"]:
        path = output / record["path"]
        data = json.loads(path.read_text())
        source = directory / (path.stem + ".html")
        html = source.read_text()
        root = parse_html(html)
        if file_record(path, output) != record:
            errors.append(f"{path.name}: output file hash/size mismatch")
        expected = next(r for r in raw_manifest["files"] if r["path"] == source.name)
        if file_record(source, directory) != expected or data["source_ref"]["sha256"] != expected["sha256"]:
            errors.append(f"{path.name}: source file hash/size mismatch")
        for error in schema.iter_errors(data):
            errors.append(f"{path.name}: schema {error.message}")
        quality = Quality()
        quality.ignored = data.get("ignored_elements", [])
        evidence = quality.conservation(root, data)
        validate_result(data, raw_manifest["document_id"], quality)
        repeated = parse_source(html, path.stem, data["tab"], data["source_url"], data["document_id"], data["source_ref"])
        repeated["validation"]["deterministic"] = True
        deterministic = encoded(repeated) == path.read_bytes()
        if not deterministic:
            errors.append(f"{path.name}: published bytes differ from repeated extraction")
        if issue_summary(data["issues"]) != data["issue_summary"]:
            errors.append(f"{path.name}: issue summary mismatch")
        if issue_summary(quality.issues) != data["issue_summary"]:
            errors.append(f"{path.name}: independent validation added diagnostics")
        if not evidence["meaningful_text_preserved"]:
            errors.append(f"{path.name}: meaningful source text differs")
        errors.extend(f"{path.name}: {error}" for error in audit_source_records(root, data))
        if data['status'] != status(data['issue_summary']):
            errors.append(f"{path.name}: status differs from diagnostics")
        tab_manifest = manifest['tabs'][path.stem]
        for key in ('status', 'issue_summary', 'source_ref'):
            if tab_manifest[key] != data[key]:
                errors.append(f"{path.name}: manifest {key} mismatch")
        if tab_manifest['issue_refs'] != [i['issue_id'] for i in data['issues']]:
            errors.append(f"{path.name}: manifest issue references mismatch")
        for key, value in tab_manifest['validation'].items():
            actual = data.get('hierarchy_validation', {}).get(key) if key == 'semantic_complete' else data['validation'].get(key)
            if value != actual:
                errors.append(f"{path.name}: manifest validation {key} mismatch")
        summaries.update(data["issue_summary"])
        diagnostics.extend({"tab": path.stem, **i} for i in data["issues"])
        tabs[path.stem] = {**data["validation"], "status": data["status"]}
        if path.stem == 'content':
            tabs[path.stem]['semantic_complete'] = data['hierarchy_validation']['semantic_complete']
        all_nodes.extend(walk_content(list(semantic_roots(data))))
    if dict(summaries) != manifest["issue_summary"]:
        errors.append("Aggregate issue summary mismatch")
    if manifest['status'] != status(manifest['issue_summary']):
        errors.append('Manifest status differs from aggregate diagnostics')
    if {p.name for p in output.glob('*.json')} != {r['path'] for r in manifest['files']} | {'manifest.json'}:
        errors.append('Published file set differs from manifest')
    expected_quality = {k: all(t[k] for t in tabs.values()) for k in ('meaningful_text_preserved', 'deterministic', 'schema_valid')}
    expected_quality['semantic_complete'] = tabs['content']['semantic_complete'] and not any(summaries[s] for s in ('warning', 'error', 'fatal'))
    if manifest['quality'] != expected_quality:
        errors.append('Manifest quality differs from per-tab validation/diagnostics')
    content = json.loads((output / "content.json").read_text())
    nodes = list(walk_content([content["document"]])) if content.get("document") else []
    hierarchy = content.get("hierarchy_validation", {})
    forms = content.get("form_validation", {})
    suspicious = [{"type": n["type"], "text": n.get("text"), "source_ref": n["source_ref"]}
                  for n in nodes if n["type"] in {"paragraph", "unknown", "numbered_paragraph"}
                  and re.match(r"^(?:Điều\s+\d|Chương\s+|Article\s+\d|Chapter\s+|Section\s+|Phụ\s+lục|Mẫu\s+số|[IVXLCDM]+[.)]\s|\d+(?:\.\d+)+\.?\s|\d+[-/]\s+(?=[^\d\s])|[a-zđ][/)\.]\s|[-+]\s+)", n.get("text") or "", re.I)]
    return {"status": manifest["status"], "quality": manifest["quality"], "issue_summary": manifest["issue_summary"],
            "audit_errors": errors, "tabs": tabs, "hierarchy": hierarchy, "forms": forms,
            "node_types": dict(Counter(n["type"] for n in nodes)),
            "diagnostics": diagnostics, "suspicious_paragraphs": suspicious,
            "structured_paragraph_audit": content.get("structured_paragraph_audit", []),
            "table_features": {"physical_cells": sum(len(n.get("cells", [])) for n in all_nodes),
                               "rowspan_cells": sum(c["rowspan"] > 1 for n in all_nodes for c in n.get("cells", [])),
                               "colspan_cells": sum(c["colspan"] > 1 for n in all_nodes for c in n.get("cells", []))}}


def audit_source_records(root, data):
    """Check original anchors, source slices and references in metadata tabs."""
    errors, anchors, nodes = [], {0: root.ref}, {0: root}
    def index(node):
        anchors[node.dom_order] = node.ref
        nodes[node.dom_order] = node
        for ref in node.text_refs.values():
            anchors[ref['dom_order']] = ref
        for child in node.children:
            if hasattr(child, 'tag'):
                index(child)
    index(root)
    def dictionaries(value):
        if isinstance(value, dict):
            yield value
            for v in value.values():
                yield from dictionaries(v)
        elif isinstance(value, list):
            for v in value:
                yield from dictionaries(v)
    for value in dictionaries(data):
        if {'tag', 'dom_order', 'line', 'column'} <= value.keys() and value != anchors.get(value['dom_order']):
            errors.append(f"Source anchor differs from RAW: {value}")
        if 'primary_document_number_candidate' in value:
            text = value.get('text') or ''
            numbers = [value.get('primary_document_number_candidate')] + value.get('mentioned_document_numbers', [])
            if any(n and n not in text for n in numbers):
                errors.append('Document-number candidate is not an exact source text slice')
        if 'href' in value and value.get('source_ref', {}).get('dom_order') in nodes:
            node = nodes[value['source_ref']['dom_order']]
            if value['href'] != node.attrs.get('href'):
                errors.append('Reference href differs from source anchor')
            target = urljoin(data['source_url'], value['href']) if value['href'] else None
            target = target if target and urlparse(target).scheme in {'http', 'https'} else None
            if value.get('url') != target:
                errors.append('Reference URL does not resolve its actual source href')
    for key in ('fields', 'events'):
        records = data.get(key, [])
        if [r['order'] for r in records] != sorted(r['order'] for r in records):
            errors.append(f'{key} source order differs')
        for record in records:
            node = nodes.get(record['source_ref']['dom_order'])
            source_text = compact_text(node.text()) if node else ''
            for field in ('label', 'value', 'date', 'status'):
                value = record.get(field)
                if isinstance(value, str) and compact_text(value) not in source_text:
                    errors.append(f'{key} {field} is not source-backed')
            for cell in record.get('source_cells', []):
                source_cell = nodes.get(cell['source_ref']['dom_order'])
                value = record.get(cell['field'])
                if isinstance(value, dict):
                    value = value.get('text')
                if value and source_cell and compact_text(value) not in compact_text(source_cell.text()):
                    errors.append('History field differs from its explicit source cell')
    return errors
