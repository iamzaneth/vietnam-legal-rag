"""Deterministic HTML → semantic JSON; raw is the only HTML source of truth."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

from .crawl_legal_documents import CrawlError, TAB_LABELS, file_record, is_excluded_tab, publish_capture, write_json
from vietnam_legal_rag.ingestion.validation.quality import Quality, issue_summary, status
from vietnam_legal_rag.ingestion.validation.extract import schema_validator, semantic_count, validate_result
from vietnam_legal_rag.ingestion.html.source import parse_html
from vietnam_legal_rag.ingestion.semantics.hierarchy import strip_private
from vietnam_legal_rag.ingestion.html.structure import PARSER_VERSION, SCHEMA_VERSION, parse_content
from vietnam_legal_rag.ingestion.semantics.vbpl import extract_tab_data


class ExtractionError(CrawlError):
    """Integrity error with a failed diagnostic manifest; previous output is intact."""
    def __init__(self, message, raw_manifest, source_ref, code, tab="manifest"):
        super().__init__(message)
        quality = Quality()
        quality.add(code, message, source_ref)
        self.report = {"schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
                       "document_id": raw_manifest["document_id"], "tab": tab,
                       "source_url": raw_manifest["source_url"], "source_ref": source_ref,
                       "stage": "extracted", "status": "failed", "issues": quality.issues,
                       "issue_summary": issue_summary(quality.issues), "files": []}


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def raw_reference(path):
    absolute = path.resolve()
    root = next((p for p in absolute.parents if p.name == "raw"), absolute.parent)
    return {"layer": "raw", "path": absolute.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def parse_source(html, key, label, source_url, document_id, source_ref):
    quality = Quality()
    result = {"schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
              "document_id": document_id, "tab": label, "source_url": source_url,
              "source_ref": source_ref, "issues": quality.issues}
    try:
        root = parse_html(html)
        result.update(parse_content(root, source_url, quality) if key == "content" else
                      extract_tab_data(root, key, source_url, quality))
        from vietnam_legal_rag.ingestion.refinement.schema import clean_contract
        clean_contract(result, root)
        strip_private(result)
        result["validation"] = quality.conservation(root, result)
    except (AssertionError, ValueError, RecursionError) as exc:
        quality.add("html_parse_failure", f"{type(exc).__name__}: parser could not interpret HTML; raw source remains available", source_ref)
        # Do not fabricate a DOM backup or facts; retain all source bytes in raw.
        result["document" if key == "content" else "context"] = None if key == "content" else []
        result["validation"] = {"meaningful_text_preserved": False, "unparsed_source": True}
    validate_result(result, document_id, quality)
    result["validation"]["semantic_elements"] = semantic_count(result)
    result["issue_summary"] = issue_summary(quality.issues)
    result["status"] = status(result["issue_summary"])
    return result


def extract_document(raw_dir: Path, destination: Path) -> dict:
    """Validate every tab, then atomically publish a JSON-only document directory."""
    raw_path, output_path = raw_dir.resolve(), destination.resolve()
    if raw_path == output_path or raw_path in output_path.parents or output_path in raw_path.parents:
        raise CrawlError("Thư mục extracted phải khác thư mục raw")
    manifest_path = raw_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_url, document_id = manifest["source_url"], manifest["document_id"]
    manifest_ref = raw_reference(manifest_path)
    html_records = [record for record in manifest["files"] if record["path"].endswith(".html")]
    if not any(record["path"] == "content.html" for record in html_records):
        raise ExtractionError("Manifest thiếu HTML toàn văn", manifest, manifest_ref, "source_content_missing")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".extract-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "document"
        staged.mkdir()
        sources, outputs, tabs, all_issues = [], [], {}, []
        for expected in html_records:
            filename = expected["path"]
            if not re.fullmatch(r"[a-z0-9_]+\.html", filename):
                raise ExtractionError(f"Tên tệp HTML không hợp lệ: {filename}", manifest, manifest_ref, "invalid_source_ref")
            key = Path(filename).stem
            tab_info = manifest.get("tabs", {}).get(key, {})
            label = tab_info.get("label", TAB_LABELS.get(key, key))
            if is_excluded_tab(label):
                continue
            source = raw_dir / filename
            # A corrupt capture must not replace an existing valid extraction.
            if not source.is_file():
                raise ExtractionError(f"Thiếu HTML nguồn: {filename}", manifest, manifest_ref, "source_missing", label)
            record = file_record(source, raw_dir)
            if record["sha256"] != expected["sha256"]:
                raise ExtractionError(f"HTML không khớp SHA-256 trong manifest: {source.name}",
                                      manifest, manifest_ref, "source_checksum_mismatch", label)
            source_ref = raw_reference(source)
            sources.append(source_ref)
            tab_url = tab_info.get("url") or source_url
            try:
                html = source.read_text(encoding="utf-8")
            except UnicodeError:
                quality = Quality()
                quality.add("html_parse_failure", "Source is not valid UTF-8; raw bytes retained", source_ref)
                result = {"schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
                          "document_id": document_id, "tab": label, "source_url": tab_url,
                          "source_ref": source_ref, "issues": quality.issues,
                          **({"document": None} if key == "content" else {"context": []}),
                          "validation": {"meaningful_text_preserved": False, "unparsed_source": True}}
                validate_result(result, document_id, quality)
                result["validation"]["semantic_elements"] = semantic_count(result)
                result["issue_summary"] = issue_summary(quality.issues)
                result["status"] = "failed"
            else:
                result = parse_source(html, key, label, tab_url, document_id, source_ref)
                repeated = parse_source(html, key, label, tab_url, document_id, source_ref)
                deterministic = encoded(result) == encoded(repeated)
                if not deterministic:
                    quality = Quality()
                    result["issues"].append({"issue_id": quality.add("non_deterministic_output", "Repeated parsing of the same input differs", source_ref, "error"),
                                             **quality.issues[-1]})
                    result["issue_summary"] = issue_summary(result["issues"])
                    result["status"] = "failed"
                result["validation"]["deterministic"] = deterministic
            output = staged / f"{key}.json"
            write_json(output, result)
            outputs.append(file_record(output, staged))
            tabs[key] = {"label": label, "status": result["status"], "source_ref": source_ref,
                         "output": output.name, "issue_summary": result["issue_summary"],
                         "issue_refs": [i["issue_id"] for i in result["issues"]],
                         "validation": {k: v for k, v in result["validation"].items() if k in
                                        {"meaningful_text_preserved", "semantic_elements", "deterministic", "schema_valid"}}}
            if key == "content":
                tabs[key]["validation"]["semantic_complete"] = result.get("hierarchy_validation", {}).get("semantic_complete", False)
            all_issues.extend(result["issues"])
        summary = issue_summary(all_issues)
        extracted_manifest = {"schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
                              "document_id": document_id, "tab": "manifest", "source_url": source_url,
                              "source_ref": manifest_ref, "stage": "extracted", "status": status(summary),
                              "issue_summary": summary, "source_files": sources, "files": outputs,
                              "tabs": tabs, "issues": []}
        extracted_manifest["quality"] = {
            "meaningful_text_preserved": all(t["validation"].get("meaningful_text_preserved", False) for t in tabs.values()),
            "deterministic": all(t["validation"].get("deterministic", False) for t in tabs.values()),
            "schema_valid": all(t["validation"].get("schema_valid", False) for t in tabs.values()),
            "semantic_complete": tabs.get("content", {}).get("validation", {}).get("semantic_complete", False) and not any(summary[k] for k in ("warning", "error", "fatal")),
        }
        extracted_manifest.update(diagnostic_info_count=summary["info"], warning_count=summary["warning"],
                                  error_count=summary["error"], fatal_count=summary["fatal"])
        errors = list(schema_validator().iter_errors(extracted_manifest))
        if errors:
            raise CrawlError("Extracted manifest không hợp lệ theo schema: " + errors[0].message)
        # Validate what will actually be published, including identity and hashes.
        for output in outputs:
            path = staged / output["path"]
            if file_record(path, staged)["sha256"] != output["sha256"]:
                raise CrawlError("Output checksum thay đổi trước khi publish")
            if json.loads(path.read_text())["document_id"] != document_id:
                raise CrawlError("document_id không khớp giữa các tab")
        write_json(staged / "manifest.json", extracted_manifest)
        publish_capture(staged, destination)
        return extracted_manifest


def extract_corpus(input_root: Path, output_root: Path, debug_tree: bool = False) -> int:
    """Extract selected RAW directories offline with the existing CLI workflow."""
    raw_root, resolved_output = input_root.resolve(), output_root.resolve()
    if raw_root == resolved_output or raw_root in resolved_output.parents or resolved_output in raw_root.parents:
        raise ValueError("--input và --output phải là hai cây thư mục riêng biệt")
    manifests = ([input_root / "manifest.json"] if (input_root / "manifest.json").is_file()
                 else sorted(input_root.rglob("manifest.json")))
    if not manifests:
        raise ValueError("Không tìm thấy raw manifest.json")
    failed = False
    destinations = [output_root / manifest.parent.name for manifest in manifests]
    if len(set(destinations)) != len(destinations):
        raise ValueError("Trùng document directory giữa các manifest raw")
    for manifest in manifests:
        raw_dir = manifest.parent
        target = output_root / raw_dir.name
        try:
            result = extract_document(raw_dir, target)
            failed |= result["status"] == "failed"
            print(f"{raw_dir.name}: {result['status']}; {result['issue_summary']}")
            if debug_tree:
                from vietnam_legal_rag.ingestion.validation.hierarchy import format_hierarchy
                content = json.loads((target / "content.json").read_text())
                if content.get("document"):
                    print(format_hierarchy(content["document"]))
                    print(json.dumps(content["hierarchy_validation"], ensure_ascii=False))
        except ExtractionError as exc:
            failed = True
            print(encoded(exc.report).decode("utf-8"), file=sys.stderr)
        except (CrawlError, OSError, ValueError, KeyError) as exc:
            failed = True
            print(f"{raw_dir.name}: {exc}", file=sys.stderr)
    return int(failed)


def main(argv=None):
    """Compatibility adapter for the former ingestion-module CLI."""
    from vietnam_legal_rag.cli.extract import main as cli_main
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
