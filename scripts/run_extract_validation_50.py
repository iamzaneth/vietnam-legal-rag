"""Resumable, throttled VBPL sampling and offline extraction audit.

Discovery uses public, robots-permitted sitemaps. Scope hints only select
candidates; the crawler's document breadcrumb establishes final scope.
RAW is captured with the existing crawler and never edited by this runner.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from vietnam_legal_rag.ingestion.crawl_legal_documents import (
    CrawlError, SITEMAP_URL, canonical_document_url, capture_document,
    fetch_public, file_record, is_document_url, parse_sitemap, publish_capture,
    write_json,
)
from vietnam_legal_rag.ingestion.extract_legal_documents import (
    encoded, extract_document, parse_source,
)
from vietnam_legal_rag.ingestion.extract_quality import Quality, issue_summary, status, compact_text
from vietnam_legal_rag.ingestion.extract_validation import (
    schema_validator, semantic_roots, validate_result, walk_content,
)
from vietnam_legal_rag.ingestion.html_source import parse_html
from vietnam_legal_rag.ingestion.structured_html import PARSER_VERSION, SCHEMA_VERSION

INVENTORY = Path("data/interim/discovered_urls.jsonl")
STATE = Path("reports/extract-validation-50-state.json")
RAW = Path("data/raw/vbpl")
EXTRACTED = Path("data/extracted/vbpl")
GOLDEN = "a9bea550-bbe3-11f1-a338-51a5cc429fc7"
TYPES = {"luat": "Luật", "nghi-dinh": "Nghị định", "nghi-quyet": "Nghị quyết",
         "quyet-dinh": "Quyết định", "thong-tu": "Thông tư", "chi-thi": "Chỉ thị",
         "phap-lenh": "Pháp lệnh", "van-ban-hop-nhat": "Văn bản hợp nhất"}


def now():
    return datetime.now(timezone.utc).isoformat()


def robots():
    data = fetch_public("https://vbpl.vn/robots.txt")
    policy = RobotFileParser()
    policy.parse(data.decode("utf-8").splitlines())
    return policy, data.decode("utf-8")


def candidate_metadata(url, sitemap, index):
    slug = urlparse(url).path.rsplit("/", 1)[-1]
    kind = next((label for prefix, label in TYPES.items() if slug.startswith(prefix + "-")), None)
    year = re.search(r"(?<!\d)(?:19|20)\d{2}(?!\d)", slug.split('--', 1)[0])
    # Read the issuing body's token in the leading identifier, rather than
    # council/committee mentions later in a Central document's title.
    identifier_slug = re.split(r"-(?:ve|v-v|sua-doi|huong-dan|thuc-hien|trien-khai|ban-hanh|quy-dinh)-", slug.split("--", 1)[0], maxsplit=1)[0][:100]
    local = bool(re.search(r"(?:^|-)(?:ubnd|hdnd|ub)(?:-|$)", identifier_slug))
    central = kind in {"Luật", "Nghị định", "Thông tư", "Pháp lệnh"} or bool(
        re.search(r"(?:^|-)(?:cp|qh\d+|ttg|bct|btc|bxd|bgtvt|bnnptnt|bca|bqp|byt|bkhdt)(?:-|$)", identifier_slug))
    return {"url": canonical_document_url(url), "sitemap_url": sitemap, "sitemap_index": index,
            "scope_hint": "dia_phuong" if local else "trung_uong" if central else None,
            "document_type_hint": kind, "year_hint": int(year[0]) if year else None}


def discover():
    policy, text = robots()
    if not policy.can_fetch("*", SITEMAP_URL):
        raise CrawlError("robots.txt disallows sitemap")
    kind, maps = parse_sitemap(fetch_public(SITEMAP_URL))
    if kind != "sitemapindex":
        maps = [SITEMAP_URL]
    INVENTORY.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    records = []
    with INVENTORY.open("w", encoding="utf-8") as output:
        for index, sitemap in enumerate(maps):
            if urlparse(sitemap).hostname != "vbpl.vn" or not policy.can_fetch("*", sitemap):
                raise CrawlError(f"Sitemap outside source policy: {sitemap}")
            time.sleep(0.5)
            kind, urls = parse_sitemap(fetch_public(sitemap))
            if kind != "urlset":
                raise CrawlError(f"Unexpected nested sitemap: {sitemap}")
            count = 0
            for url in urls:
                canonical = canonical_document_url(url)
                if canonical in seen or not is_document_url(url) or not policy.can_fetch("*", url):
                    continue
                seen.add(canonical)
                output.write(json.dumps(candidate_metadata(url, sitemap, index), ensure_ascii=False) + "\n")
                count += 1
            output.flush()
            records.append({"url": sitemap, "kind": kind, "entries": len(urls), "document_urls": count})
            print(f"{sitemap}: {count} documents", flush=True)
    write_json(INVENTORY.with_suffix(".discovery.json"), {
        "retrieved_at": now(), "source": SITEMAP_URL, "robots": text,
        "sitemaps": records, "distinct_documents": len(seen),
        "classification_note": "URL hints select candidates; captured breadcrumb is authoritative."})


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"started_at": now(), "schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
            "target": 50, "documents": [], "attempts": [], "waves": [], "repairs": []}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    write_json(STATE, state)


def choose_candidate(state, scope):
    attempted = {a["url"] for a in state["attempts"]}
    existing = {json.loads(p.read_text())["source_url"] for p in RAW.rglob("manifest.json")}
    used = [d for d in state["documents"] if d["document_scope"] == scope]
    type_counts = Counter(d.get("document_type_hint") for d in used)
    failed_types = Counter(a.get("document_type_hint") for a in state["attempts"]
                           if a["requested_scope"] == scope and a["result"] != "complete")
    bucket_counts = Counter(d.get("sitemap_index") for d in used)
    year_counts = Counter((d.get("year_hint") or 0) // 10 for d in used)
    failed = [a for a in state['attempts'] if a['requested_scope'] == scope and a['result'] in {'failed', 'scope_hint_mismatch'}]
    failed_buckets = Counter(a.get('sitemap_index') for a in failed)
    failed_decades = Counter((a.get('year_hint') or 0) // 10 for a in failed)
    candidates = (json.loads(line) for line in INVENTORY.open(encoding="utf-8"))
    candidates = [d for d in candidates if d["scope_hint"] == scope and d["url"] not in attempted
                  and d["url"] not in existing and not d["url"].endswith("--" + GOLDEN)]
    if not candidates:
        raise CrawlError(f"No unused candidate for {scope}")
    # Balance actual encountered types, sitemap generations and decades;
    # deterministic URL hash breaks ties without selecting only the newest.
    return min(candidates, key=lambda d: (
        type_counts[d["document_type_hint"]] + failed_types[d["document_type_hint"]] / 2,
        bucket_counts[d["sitemap_index"]] + failed_buckets[d['sitemap_index']] / 2,
        year_counts[(d.get("year_hint") or 0) // 10] + failed_decades[(d.get('year_hint') or 0) // 10] / 2,
        hashlib.sha256(d["url"].encode()).hexdigest()))


def capture(candidate, policy, discovery, channel, timeout):
    url = candidate["url"]
    if not is_document_url(url) or not policy.can_fetch("*", url):
        raise CrawlError(f"Document outside source/robots policy: {url}")
    identifier = urlparse(url).path.rsplit("--", 1)[-1]
    if not re.fullmatch(r"(?:[0-9a-fA-F-]{36}|\d+)", identifier):
        identifier = hashlib.sha256(url.encode()).hexdigest()[:32]
    manifest = {"source": "vbpl.vn", "document_id": f"vbpl:{identifier}", "retrieved_at": now(),
                "discovery": {"source": SITEMAP_URL, "selected_from": candidate["sitemap_url"],
                              "sitemaps": discovery["sitemaps"]}}
    RAW.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".crawl-", dir=RAW) as temporary:
        staged = Path(temporary) / "document"
        staged.mkdir()
        capture_document(url, staged, manifest, channel, False, timeout * 1000)
        destination = RAW / manifest["document_scope"] / identifier
        if destination.exists():
            raise CrawlError(f"Refusing to overwrite immutable RAW: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        manifest.update(status="complete", completed_at=now())
        write_json(staged / "manifest.json", manifest)
        publish_capture(staged, destination)
    return manifest, destination


def crawl_wave(wave, channel, timeout):
    state = load_state()
    policy, _ = robots()
    discovery = json.loads(INVENTORY.with_suffix(".discovery.json").read_text())
    target = min(wave * 10, 50)
    attempts_this_run = 0
    while len(state["documents"]) < target:
        if attempts_this_run >= 60:
            raise CrawlError("Wave attempted 60 candidates; inspect source failures before continuing")
        scope = "trung_uong" if len(state["documents"]) % 2 == 0 else "dia_phuong"
        candidate = choose_candidate(state, scope)
        attempt = {**candidate, "requested_scope": scope, "started_at": now(), "result": "running"}
        state["attempts"].append(attempt)
        save_state(state)
        print(f"Candidate {len(state['documents']) + 1}/50 {scope}: {candidate['url']}", flush=True)
        try:
            manifest, directory = capture(candidate, policy, discovery, channel, timeout)
            attempt.update(result="complete", document_id=manifest["document_id"], raw_directory=str(directory),
                           actual_scope=manifest["document_scope"])
            if manifest["document_scope"] != scope:
                attempt["result"] = "scope_hint_mismatch"
                attempt["reason"] = "Captured breadcrumb differs from URL hint; immutable capture retained."
            else:
                document = {**candidate, "document_id": manifest["document_id"], "document_scope": scope,
                            "raw_directory": str(directory), "crawl_result": "complete",
                            "sequence": len(state["documents"]) + 1, "wave": wave}
                state["documents"].append(document)
                save_state(state)
                result = extract_document(directory, EXTRACTED / directory.name)
                document["initial_extract_status"] = result["status"]
                document["initial_issue_summary"] = result["issue_summary"]
                print(f"Extract: {result['status']} {result['issue_summary']}", flush=True)
        except Exception as exc:
            attempt.update(result="failed", reason=f"{type(exc).__name__}: {exc}")
            print(attempt["reason"], flush=True)
        attempt["completed_at"] = now()
        save_state(state)
        attempts_this_run += 1
        time.sleep(3)
    print(f"Wave {wave}: {len(state['documents'])} successful distinct RAW captures", flush=True)


def audit_document(directory, regenerate=False):
    if regenerate:
        extract_document(directory, EXTRACTED / directory.name)
    output = EXTRACTED / directory.name
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


def audit_wave(regenerate):
    state = load_state()
    for document in state["documents"]:
        result = audit_document(Path(document["raw_directory"]), regenerate)
        document["final_validation"] = result
        print(f"{document['sequence']:02} {document['document_id']} {result['status']} {result['quality']} "
              f"{result['issue_summary']} audit_errors={len(result['audit_errors'])}", flush=True)
        save_state(state)
    golden = audit_document(RAW / "trung_uong" / GOLDEN, regenerate)
    expected = {"chapter": 4, "article": 15, "clause": 36, "point": 5, "annex": 4,
                "numbered_section": 5, "numbered_item": 26, "form": 16, "form_subfield": 14, "footnote": 52}
    golden["invariants"] = {kind: {"expected": count, "actual": golden["node_types"].get(kind, 0)}
                            for kind, count in expected.items()}
    if any(v["actual"] != v["expected"] for v in golden["invariants"].values()):
        golden["audit_errors"].append("Golden structural count regression")
    if not all(golden["quality"].values()) or any(golden["issue_summary"][s] for s in ("warning", "error", "fatal")):
        golden["audit_errors"].append("Golden quality regression")
    state["golden_validation"] = golden
    state["last_audited_at"] = now()
    state["waves"].append({"audited_at": now(), "documents": len(state["documents"]), "regenerated": regenerate})
    save_state(state)
    print("Golden:", golden["quality"], golden["issue_summary"], "audit_errors=", golden["audit_errors"], flush=True)
    return int(bool(golden["audit_errors"]) or any(d["final_validation"]["audit_errors"] or
               not all(d["final_validation"]["quality"].values()) for d in state["documents"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["discover", "crawl", "audit", "inspect"])
    parser.add_argument("--url", help="Robots-permitted document URL for source inspection")
    parser.add_argument("--wave", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--channel", default="chrome")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--regenerate", action="store_true")
    args = parser.parse_args()
    if args.action == "discover":
        discover()
    elif args.action == "crawl":
        crawl_wave(args.wave, args.channel, args.timeout)
    elif args.action == "inspect":
        policy, _ = robots()
        if not args.url or not is_document_url(args.url) or not policy.can_fetch("*", args.url):
            parser.error("inspect requires a permitted VBPL document --url")
        from playwright.sync_api import sync_playwright
        from vietnam_legal_rag.ingestion.crawl_legal_documents import USER_AGENT
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=args.channel, headless=True)
            try:
                page = browser.new_context(locale="vi-VN", user_agent=USER_AGENT).new_page()
                response = page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
                page.wait_for_timeout(4000)
                print("HTTP", response.status, "URL", page.url, "TITLE", page.title())
                print("TABS", page.get_by_role("tab").all_inner_texts())
                print(page.locator("body").inner_text()[:6000])
            finally:
                browser.close()
    else:
        return audit_wave(args.regenerate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
