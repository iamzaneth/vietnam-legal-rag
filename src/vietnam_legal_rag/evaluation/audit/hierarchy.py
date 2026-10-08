"""Inspect actual EXTRACT artifacts, raw fidelity, scoped form repairs and regressions."""
from __future__ import annotations

from copy import deepcopy
import json
import re
from vietnam_legal_rag.evaluation.audit.extract import sha

from vietnam_legal_rag.ingestion.extract_legal_documents import encoded, parse_source
from vietnam_legal_rag.ingestion.validation.quality import Quality, issue_summary, text_units, compact_text
from vietnam_legal_rag.ingestion.validation.forms import form_metrics, structured_paragraphs
from vietnam_legal_rag.ingestion.validation.extract import schema_validator, validate_result, walk_content
from vietnam_legal_rag.ingestion.validation.hierarchy import format_hierarchy
from vietnam_legal_rag.ingestion.semantics.hierarchy import LEVELS
from vietnam_legal_rag.ingestion.html.source import parse_html
from vietnam_legal_rag.ingestion.refinement.semantic import walk
from vietnam_legal_rag.ingestion.html.structure import PARSER_VERSION, SCHEMA_VERSION, document_numbers
from vietnam_legal_rag.ingestion.semantics.tables import effective_cell_text, NO_AXES


def counts(content):
    units = list(walk_content([content["document"]]))
    return {**form_metrics(content["document"]),
            "ignored_ui_artifacts": sum(i["reason"] == "navigation_artifact" for i in content.get("ignored_elements", [])),
            "orphan_nodes": sum(n.get("parent_status") == "unresolved" for n in units),
            "numbered_paragraph_candidates": sum(n["type"] == "numbered_paragraph" and n.get("candidate_role") == "clause" for n in units),
            "generic_decimal_paragraphs": sum(n["type"] == "paragraph" and bool(re.match(r"^\d+(?:\.\d+)+\.?\s+", n.get("text", ""))) for n in units),
            "ambiguous_tables": sum(n["type"] == "table" and n["table_kind"] == "ambiguous" for n in units),
            "warnings": content["issue_summary"]["warning"],
            "errors": content["issue_summary"]["error"] + content["issue_summary"]["fatal"]}


def text_projection(result):
    # Migration belongs in the comparison tool, never in the final text
    # projection. Historical snapshots can still carry the obsolete alias.
    if result["parser_version"] in {"2.3.0", "2.3.1"}:
        result = deepcopy(result)
        for node in walk_content([result["document"]] if result.get("document") else result.get("content", [])):
            if "title_ref" in node:
                node["title_source_ref"] = node.pop("title_ref")
    return compact_text("".join(t for _, t in sorted(text_units(result), key=lambda item: item[0])))


def audit_removed_navigation(previous, result, root):
    """Allow only the exact source leaves independently audited as navigation.

    Raw bytes/checksums never change. New UI exclusions deliberately change the
    meaningful-text checksum, while every other source character must match.
    """
    before = {i["order"] for i in previous.get("ignored_elements", [])}
    added = [i for i in result.get("ignored_elements", []) if i["order"] not in before]
    assert all(i["reason"] == "navigation_artifact" for i in added), added
    sources = {n.dom_order: n for n in root.find()}
    for item in added:
        source = sources[item["order"]]
        assert source.ref == item["source_ref"] and source.text() == item["text"]
    previous_quality = Quality(); previous_quality.ignored = previous.get("ignored_elements", [])
    assert previous_quality.conservation(root, previous)["meaningful_text_preserved"]
    excluded = {i["order"] for i in result.get("ignored_elements", [])}
    segments = []
    def visit(node):
        from vietnam_legal_rag.ingestion.html.source import Node, NON_CONTENT
        if node.tag in NON_CONTENT or node.dom_order in excluded:
            return
        for i, child in enumerate(node.children):
            if isinstance(child, Node):
                visit(child)
            elif node.text_refs.get(i, node.ref)["dom_order"] not in excluded:
                segments.append(child)
    visit(root)
    assert compact_text("".join(segments)) == text_projection(result)
    return added


def metadata_facts(result):
    """Compare source records, ignoring only derived inference/envelope fields."""
    inference = {"primary_document_number_candidate", "mentioned_document_numbers", "document_number_candidates",
                 "effective_text", "text_segments", "classification_evidence", "table_kind", "semantics", "issues",
                 "role", "confidence", "association_status", "header_refs", "header_candidates", "header_evidence",
                 "labels", "orientation", "row_axis", "column_axis", "evidence"}
    def clean(value):
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, dict):
            output = {k: clean(v) for k, v in value.items() if k not in inference}
            if "mentioned_document_numbers" in value:
                output["source_document_numbers"] = document_numbers(value["text"])
            return output
        return value
    return clean({k: v for k, v in result.items() if k not in {"schema_version", "parser_version", "validation", "status", "issue_summary", "issues"}})


def table_geometry(content):
    keys = ("cell_id", "row", "column", "rowspan", "colspan", "original_rowspan", "original_colspan", "cell_type", "order", "source_ref")
    return {n["table_id"]: {"grid_shape": n["grid_shape"], "cells": [{k: c[k] for k in keys} for c in n["cells"]]}
            for n in walk_content([content["document"]]) if n["type"] == "table"}


def hierarchy_facts(content):
    legal, annex = [], []
    for node, parents in walk([content["document"]]):
        if node["type"] in LEVELS:
            facts = {k: node.get(k) for k in ("type", "number", "label", "label_suffix", "title", "source_ref", "source_refs", "title_source_ref", "title_source_spans", "promotion_evidence")}
            if facts["source_refs"] == [facts["source_ref"]]:
                facts["source_refs"] = None
            legal.append({"node": facts,
                          "parents": [(p["type"], p["order"]) for p in parents if p.get("type") in LEVELS or p.get("type") == "list"]})
        if node["type"] in {"annex", "numbered_section", "numbered_item"}:
            annex.append({"node": {k: node.get(k) for k in ("type", "number", "number_path", "parent_number", "level", "source_ref")},
                          "parents": [(p["type"], p["order"]) for p in parents if p.get("type") in {"annexes", "annex", "numbered_section", "numbered_item"}]})
    return legal, annex


def inspect_content(content):
    """No fixture-specific parser rules: assert source structure in every tree."""
    unresolved, promoted, titles, table_review = [], [], [], []
    annex_decimal_generic = []
    for node, parents in walk([content["document"]]):
        assert node.get("source_ref") or node.get("source_refs"), node
        annex = any(p.get("type") == "annex" for p in parents)
        if node["type"] == "annex":
            assert parents[-1]["type"] == "annexes"
            assert not any(p.get("type") == "closing" for p in parents)
        if node["type"] in {"clause", "point"}:
            assert not annex, node
        if node["type"] == "paragraph" and annex and re.match(r"^\d+(?:\.\d+)+\.?\s+", node.get("text", "")):
            annex_decimal_generic.append({"order": node["order"], "text": node["text"]})
        if node.get("parent_status") or node.get("candidate_role"):
            unresolved.append({"type": node["type"], "order": node["order"], "number": node.get("number"),
                               "text": node.get("text"), "reason": node.get("unresolved_reason"),
                               "evidence": node.get("candidate_evidence"), "source_ref": node["source_ref"]})
        if node.get("promotion_evidence"):
            promoted.append({"number": node["number"], "order": node["order"], "source_ref": node["source_ref"],
                             "evidence": node["promotion_evidence"],
                             "points": [n["number"] for n in node["children"] if n["type"] == "point"]})
        if node.get("title_evidence") == "adjacent_heading":
            titles.append({"type": node["type"], "number": node.get("number"), "title": node["title"],
                           "source_refs": node.get("source_refs", [node["source_ref"]])})
        if node["type"] == "table":
            for cell in node["cells"]:
                assert cell["effective_text"] == effective_cell_text(cell)[1]
                if cell.get("content") and effective_cell_text(cell)[1]:
                    assert cell["effective_text"], cell
                if node["table_kind"] in NO_AXES:
                    assert not cell.get("header_refs") and not cell.get("row_axis") and not cell.get("column_axis")
                    assert "role" not in cell and "confidence" not in cell
            issue_ids = set(node["issues"])
            table_issues = [i for i in content["issues"] if i["issue_id"] in issue_ids]
            assert sum(i["code"] == "table_semantics_unresolved" for i in table_issues) <= 1
            table_review.append({"table_id": node["table_id"], "table_kind": node["table_kind"],
                                 "classification_evidence": node["classification_evidence"], "grid_shape": node["grid_shape"],
                                 "effective_cell_text_verified": True, "source_ref": node["source_ref"],
                                 "compound_headers": [{k: c.get(k) for k in ("cell_id", "effective_text", "labels", "orientation", "row_axis", "column_axis", "source_ref")}
                                                      for c in node["cells"] if c.get("role") == "compound_header"],
                                 "issues": table_issues})
    assert not annex_decimal_generic, annex_decimal_generic
    metrics = form_metrics(content["document"])
    assert metrics == {k: v for k, v in content["form_validation"].items() if k != "semantic_complete"}
    assert content["form_validation"]["semantic_complete"]
    assert not any(metrics[k] for k in ("split_form_candidates", "inconsistent_footnote_sequences", "bibliography_fields_misclassified", "unexplained_structured_paragraphs")), metrics
    boundaries = []
    for annex, _ in walk([content["document"]]):
        if annex["type"] != "annex":
            continue
        forms = [n for n in annex["children"] if n["type"] == "form"]
        for index, form in enumerate(forms):
            item = {"annex": annex.get("number"), "number": form.get("number"), "title": form.get("title"),
                    "order": form["order"], "child_count": len(form["children"]),
                    "next_form_number": forms[index + 1].get("number") if index + 1 < len(forms) else None,
                    "displayed_titles": [{"type": n["type"], "text": n["text"], "source_ref": n["source_ref"]} for n in form["children"] if n["type"] in {"form_title", "form_subtitle"}],
                    "evidence": form.get("evidence", form.get("boundary_evidence")), "source_ref": form["source_ref"]}
            boundaries.append(item)
            print(f'form {item["number"]} → {item["title"]} → {item["child_count"]} children → next {item["next_form_number"]}')
    assert all(n["reason"] or n["evidence"] for n in unresolved), unresolved
    return {"unresolved_nodes": unresolved, "promoted_clauses": promoted, "coalesced_titles": titles,
            "generic_decimal_paragraphs_in_annex": annex_decimal_generic, "table_review": table_review,
            "form_validation": content["form_validation"], "form_boundaries": boundaries,
            "remaining_structured_paragraphs": structured_paragraphs(content["document"]),
            "footnote_groups": [{"order": n["order"], "markers": [c.get("marker") for c in n["children"]],
                                 "source_ref": n["source_ref"]} for n in walk_content([content["document"]]) if n["type"] == "footnote_group"]}


def audit(raw, extracted, sample, before=None):
    documents = []
    schema = schema_validator()
    for manifest_path in sorted(raw.rglob("manifest.json")):
        source_dir = manifest_path.parent
        output_dir = extracted / source_dir.name
        manifest = json.loads((output_dir / "manifest.json").read_text())
        schema.validate(manifest)
        assert manifest["document_id"] == json.loads(manifest_path.read_text())["document_id"]
        assert manifest["source_ref"]["sha256"] == sha(manifest_path)
        tabs, content, previous_content = [], None, None
        for record in manifest["files"]:
            path = output_dir / record["path"]
            result = json.loads(path.read_text())
            schema.validate(result)
            assert sha(path) == record["sha256"]
            source = source_dir / (path.stem + ".html")
            html = source.read_text()
            assert result["source_ref"]["sha256"] == sha(source)
            quality = Quality()
            quality.ignored = result.get("ignored_elements", [])
            evidence = quality.conservation(parse_html(html), result)
            assert evidence["meaningful_text_preserved"], str(path)
            assert evidence["source_text_sha256"] == result["validation"]["source_text_sha256"]
            validate_result(result, manifest["document_id"], quality)
            assert not any(i["severity"] in {"error", "fatal"} for i in quality.issues), quality.issues
            repeated = [parse_source(html, path.stem, result["tab"], result["source_url"], result["document_id"], result["source_ref"]) for _ in range(2)]
            assert encoded(repeated[0]) == encoded(repeated[1]), str(path)
            repeated[0]["validation"]["deterministic"] = True
            assert encoded(repeated[0]) == path.read_bytes(), str(path)
            tab = {"file": path.name, "meaningful_text_preserved": True, "deterministic": True,
                   "source_text_sha256": evidence["source_text_sha256"], "extracted_text_sha256": evidence["extracted_text_sha256"],
                   "issue_summary": issue_summary(result["issues"])}
            if before:
                previous = json.loads((before / source_dir.name / path.name).read_text())
                assert previous["source_ref"] == result["source_ref"]
                if previous["validation"]["source_text_sha256"] != evidence["source_text_sha256"]:
                    tab["new_audited_navigation_exclusions"] = audit_removed_navigation(previous, result, parse_html(html))
                else:
                    assert text_projection(previous) == text_projection(result)
                if path.stem in {"properties", "history", "relations"}:
                    assert metadata_facts(previous) == metadata_facts(result), f'Metadata regression: {path}'
                    if previous["parser_version"] in {"2.3.0", "2.3.1", "2.3.2"}:
                        excluded = {"parser_version", "schema_version", "validation", "status", "issue_summary", "issues"}
                        assert {k:v for k,v in previous.items() if k not in excluded} == {k:v for k,v in result.items() if k not in excluded}, f'Metadata payload changed: {path}'
                        if previous["parser_version"] == result["parser_version"]:
                            assert (before / source_dir.name / path.name).read_bytes() == path.read_bytes(), f'Metadata bytes changed: {path}'
                    if previous["parser_version"] == "2.2.0":
                        assert {k: v for k, v in previous.items() if k not in {"parser_version", "schema_version"}} == {k: v for k, v in result.items() if k not in {"parser_version", "schema_version"}}, f'V2.2 metadata semantics changed: {path}'
                    tab["source_records_unchanged"] = True
                elif path.stem == "content":
                    previous_content = previous
            tabs.append(tab)
            if path.stem == "content":
                assert "content" not in result
                assert result["hierarchy_validation"]["status"] != "invalid"
                content = result
        document = {"document_id": manifest["document_id"], "directory": source_dir.name,
                    "document_number": next((n["number"] for n in walk_content([content["document"]]) if n["type"] == "document_number"), None),
                    "hierarchy_validation": content["hierarchy_validation"], "content_issues": content["issue_summary"],
                    "all_tab_issues": manifest["issue_summary"], "tabs": tabs, "inspection": inspect_content(content),
                    "remaining_issues": [i for i in content["issues"] if i["severity"] in {"warning", "error", "fatal"}]}
        if previous_content:
            assert table_geometry(previous_content) == table_geometry(content), f'Table grid regression: {source_dir.name}'
            previous_tables = {n["table_id"]: n for n in walk_content([previous_content["document"]]) if n["type"] == "table"}
            for table in walk_content([content["document"]]):
                if table["type"] != "table":
                    continue
                previous_table = previous_tables[table["table_id"]]
                assert previous_table["table_kind"] == table["table_kind"]
                assert [(c["text"], c["text_segments"], c["effective_text"]) for c in previous_table["cells"]] == [(c["text"], c["text_segments"], c["effective_text"]) for c in table["cells"]]
                if table["table_kind"] in {"data", "matrix"}:
                    assert previous_table["semantics"] == table["semantics"]
                    assert [{k:v for k,v in c.items() if k != "content"} for c in previous_table["cells"]] == [{k:v for k,v in c.items() if k != "content"} for c in table["cells"]]
            assert previous_content["hierarchy_validation"]["legal_hierarchy"] == content["hierarchy_validation"]["legal_hierarchy"]
            assert previous_content["hierarchy_validation"]["annex_hierarchy"] == content["hierarchy_validation"]["annex_hierarchy"]
            assert previous_content["hierarchy_validation"]["document_sections"] == content["hierarchy_validation"]["document_sections"]
            assert hierarchy_facts(previous_content) == hierarchy_facts(content)
            document["legal_and_annex_relationships_unchanged"] = True
            document["source_table_geometry_unchanged"] = True
            document["before_after"] = {k: {"before": value, "after": counts(content)[k]} for k, value in counts(previous_content).items()}
        print(f'\n{document["document_number"]} ({source_dir.name})')
        print(format_hierarchy(content["document"]))
        print(json.dumps(document["hierarchy_validation"], ensure_ascii=False))
        if source_dir.name == sample:
            document["tree"] = format_hierarchy(content["document"])
        documents.append(document)
    assert any(d["directory"] == sample for d in documents)
    totals = {"documents": len(documents), "tabs": sum(len(d["tabs"]) for d in documents),
              "all_hierarchies_usable": True, "all_meaningful_text_preserved": True, "all_deterministic": True,
              "metadata_regressions": 0,
              "issues": {s: sum(d["all_tab_issues"][s] for d in documents) for s in ("info", "warning", "error", "fatal")}}
    if before:
        totals["before_after"] = {k: {phase: sum(d["before_after"][k][phase] for d in documents) for phase in ("before", "after")}
                                  for k in documents[0]["before_after"]}
    return {"schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION, "sample": sample,
            "scope": "Every available raw capture, every generated JSON tab, serialized artifacts independently reparsed",
            "depth_definition": "Edges from document through sections and legal/annex numbered nodes; paragraph/list/table/form wrappers excluded. Annex max_depth counts number_path components.",
            "before_after_scope": "content.json; numbered_paragraph_candidates require candidate_role clause; generic decimals counted across the whole tree",
            "documents": documents, "totals": totals}


def markdown(report):
    lines = [f'# Kiểm tra EXTRACT {report["schema_version"]}', '',
             'Đọc lại toàn bộ JSON đã ghi, đối chiếu raw SHA-256, source text, source order, provenance, schema và parent. Parse lại từng tab hai lần rồi so bytes với artifact.', '',
             '| Văn bản | Điều | Khoản | Điểm | Phụ lục | Section phụ lục | Item phụ lục | Depth | Orphan | Bảng ambiguous | Warning | Error/fatal | Text | Deterministic |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |']
    for d in report['documents']:
        h = d['hierarchy_validation']; l = h['legal_hierarchy']; a = h['annex_hierarchy']; u = h['unresolved']; s = d['content_issues']
        row = [d['document_number'], l['articles'], l['clauses'], l['points'], a['annexes'], a['numbered_sections'], a['numbered_items'], h['max_depth'], u['orphan_nodes'], u['ambiguous_tables'], s['warning'], s['error'] + s['fatal'], 'true', 'true']
        lines.append('| ' + ' | '.join(map(str, row)) + ' |')
    lines += ['', 'Counts/warnings trong bảng lấy từ content.json. JSON report còn giữ counts tất cả tab, evidence promotion, title refs và review từng table.', '']
    if 'before_after' in report['totals']:
        lines += ['| Metric content | Trước | Sau |', '| --- | ---: | ---: |']
        for k, v in report['totals']['before_after'].items():
            lines.append(f'| {k} | {v["before"]} | {v["after"]} |')
    lines += ['', 'Cây debug được in ra console cho mọi document; không tạo TXT trong extracted. Mẫu nhỏ:', '']
    sample = next(d for d in report['documents'] if d['directory'] == report['sample'])
    lines += ['```text', sample['tree'], '```', '', 'Các issue còn giữ:', '']
    for d in report['documents']:
        for i in d['remaining_issues']:
            lines.append(f'- {d["document_number"]}: {i["code"]} ({i["severity"]}), source order {i["source_ref"]["dom_order"]}. {i["message"]}')
    lines += ['', 'Bảng matrix giữ compound labels và orientation unknown vì nguồn không khai báo trục đủ rõ. Dòng số đơn lẻ của Quyết định được giữ vì thiếu evidence page transition. Không có orphan/candidate khoản hoặc decimal paragraph chưa xử lý trong các phụ lục của corpus.', '',
              f'{report["totals"]["tabs"]} tab bảo toàn text và deterministic. Properties/history/relations giữ source records, URL, identifier, ngày, số hiệu và provenance so với baseline. Table kind/grid/raw cell text/text_segments/effective_text và legal/annex counts giữ nguyên.', '',
              '```bash', 'PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -t .',
              'PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.ingestion.extract_legal_documents --debug-tree',
              'PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.cli audit hierarchy --raw data/raw/vbpl --extracted data/extracted/vbpl --sample 0c389a00-78f6-11f1-a726-87c913cf8f30 --report docs/extract-hierarchy.json', '```', '']
    return '\n'.join(lines)
