"""Resumable, throttled VBPL sampling and offline extraction audit.

Discovery uses public, robots-permitted sitemaps. Scope hints only select
candidates; the crawler's document breadcrumb establishes final scope.
RAW is captured with the existing crawler and never edited by this runner.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from vietnam_legal_rag.ingestion.crawl_legal_documents import (
    CrawlError, SITEMAP_URL, canonical_document_url, capture_document,
    fetch_public, is_document_url, parse_sitemap, publish_capture, write_json,
)
from vietnam_legal_rag.ingestion.extract_legal_documents import extract_document
from vietnam_legal_rag.ingestion.html.structure import PARSER_VERSION, SCHEMA_VERSION

from .config import ValidationConfig
from .validation_sampler import candidate_metadata, choose_candidate
from vietnam_legal_rag.evaluation.audit.extract import audit_document


def now():
    return datetime.now(timezone.utc).isoformat()


def robots():
    data = fetch_public("https://vbpl.vn/robots.txt")
    policy = RobotFileParser()
    policy.parse(data.decode("utf-8").splitlines())
    return policy, data.decode("utf-8")


def discover(config: ValidationConfig):
    policy, text = robots()
    if not policy.can_fetch("*", SITEMAP_URL):
        raise CrawlError("robots.txt disallows sitemap")
    kind, maps = parse_sitemap(fetch_public(SITEMAP_URL))
    if kind != "sitemapindex":
        maps = [SITEMAP_URL]
    config.inventory.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    records = []
    with config.inventory.open("w", encoding="utf-8") as output:
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
    write_json(config.inventory.with_suffix(".discovery.json"), {
        "retrieved_at": now(), "source": SITEMAP_URL, "robots": text,
        "sitemaps": records, "distinct_documents": len(seen),
        "classification_note": "URL hints select candidates; captured breadcrumb is authoritative."})


def load_state(config: ValidationConfig):
    if config.sample_manifest.exists():
        state = json.loads(config.sample_manifest.read_text())
        if state["target"] != config.batch_size:
            raise CrawlError("State target differs from --batch-size; use a separate state file for a new batch")
        if len(state['documents']) > config.batch_size:
            raise CrawlError('State contains more documents than the configured target')
        if any(d['document_scope'] != config.scope_at(i) for i, d in enumerate(state['documents'])):
            raise CrawlError('State sample order differs from configured scope targets')
        if state.get('scope_targets', config.scope_targets) != config.scope_targets:
            raise CrawlError('State scope targets differ from configured targets')
        return state
    return {"started_at": now(), "schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
            "target": config.batch_size, "scope_targets": config.scope_targets, "documents": [], "attempts": [], "waves": [], "repairs": []}


def save_state(state, config: ValidationConfig):
    config.sample_manifest.parent.mkdir(parents=True, exist_ok=True)
    write_json(config.sample_manifest, state)


def capture(candidate, policy, discovery, channel, timeout, config: ValidationConfig):
    url = candidate["url"]
    if not is_document_url(url) or not policy.can_fetch("*", url):
        raise CrawlError(f"Document outside source/robots policy: {url}")
    identifier = urlparse(url).path.rsplit("--", 1)[-1]
    if not re.fullmatch(r"(?:[0-9a-fA-F-]{36}|\d+)", identifier):
        identifier = hashlib.sha256(url.encode()).hexdigest()[:32]
    manifest = {"source": "vbpl.vn", "document_id": f"vbpl:{identifier}", "retrieved_at": now(),
                "discovery": {"source": SITEMAP_URL, "selected_from": candidate["sitemap_url"],
                              "sitemaps": discovery["sitemaps"]}}
    config.raw_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".crawl-", dir=config.raw_dir) as temporary:
        staged = Path(temporary) / "document"
        staged.mkdir()
        capture_document(url, staged, manifest, channel, False, timeout * 1000)
        destination = config.raw_dir / manifest["document_scope"] / identifier
        if destination.exists():
            raise CrawlError(f"Refusing to overwrite immutable config.raw_dir: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        manifest.update(status="complete", completed_at=now())
        write_json(staged / "manifest.json", manifest)
        publish_capture(staged, destination)
    return manifest, destination


def crawl_wave(wave, channel, timeout, config: ValidationConfig):
    if not 1 <= wave <= config.waves:
        raise ValueError('wave must be within the configured batch')
    state = load_state(config)
    policy, _ = robots()
    discovery = json.loads(config.inventory.with_suffix(".discovery.json").read_text())
    target = min(wave * config.wave_size, config.batch_size)
    attempts_this_run = 0
    while len(state["documents"]) < target:
        if attempts_this_run >= 60:
            raise CrawlError("Wave attempted 60 candidates; inspect source failures before continuing")
        scope = config.scope_at(len(state["documents"]))
        candidate = choose_candidate(state, scope, config)
        attempt = {**candidate, "requested_scope": scope, "started_at": now(), "result": "running"}
        state["attempts"].append(attempt)
        save_state(state, config)
        print(f"Candidate {len(state['documents']) + 1}/{config.batch_size} {scope}: {candidate['url']}", flush=True)
        try:
            manifest, directory = capture(candidate, policy, discovery, channel, timeout, config)
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
                save_state(state, config)
                result = extract_document(directory, config.extracted_dir / directory.name)
                document["initial_extract_status"] = result["status"]
                document["initial_issue_summary"] = result["issue_summary"]
                print(f"Extract: {result['status']} {result['issue_summary']}", flush=True)
        except Exception as exc:
            attempt.update(result="failed", reason=f"{type(exc).__name__}: {exc}")
            print(attempt["reason"], flush=True)
        attempt["completed_at"] = now()
        save_state(state, config)
        attempts_this_run += 1
        time.sleep(3)
    print(f"Wave {wave}: {len(state['documents'])} successful distinct RAW captures", flush=True)


def audit_wave(regenerate, config: ValidationConfig):
    state = load_state(config)
    for document in state["documents"]:
        result = audit_document(Path(document["raw_directory"]), regenerate, config.extracted_dir)
        document["final_validation"] = result
        print(f"{document['sequence']:02} {document['document_id']} {result['status']} {result['quality']} "
              f"{result['issue_summary']} audit_errors={len(result['audit_errors'])}", flush=True)
        save_state(state, config)
    golden = audit_document(config.raw_dir / "trung_uong" / config.golden_id, regenerate, config.extracted_dir)
    expected = golden_expectations(config.golden_id)
    golden["invariants"] = {kind: {"expected": count, "actual": golden["node_types"].get(kind, 0)}
                            for kind, count in expected.items()}
    if any(v["actual"] != v["expected"] for v in golden["invariants"].values()):
        golden["audit_errors"].append("Golden structural count regression")
    if not all(golden["quality"].values()) or any(golden["issue_summary"][s] for s in ("warning", "error", "fatal")):
        golden["audit_errors"].append("Golden quality regression")
    state["golden_validation"] = golden
    state["last_audited_at"] = now()
    state["waves"].append({"audited_at": now(), "documents": len(state["documents"]), "regenerated": regenerate})
    save_state(state, config)
    print("Golden:", golden["quality"], golden["issue_summary"], "audit_errors=", golden["audit_errors"], flush=True)
    return int(bool(golden["audit_errors"]) or any(d["final_validation"]["audit_errors"] or
               not all(d["final_validation"]["quality"].values()) for d in state["documents"]))


def golden_expectations(identifier):
    fixture = Path(__file__).with_name('golden_invariants.json')
    expectations = json.loads(fixture.read_text())
    if identifier not in expectations:
        raise ValueError(f'No golden invariants configured for {identifier}')
    return expectations[identifier]


def inspect_source(url, channel='chrome', timeout=60):
    """Inspect a robots-permitted source page using the existing browser flow."""
    policy, _ = robots()
    if not url or not is_document_url(url) or not policy.can_fetch('*', url):
        raise CrawlError('inspect requires a permitted VBPL document URL')
    from playwright.sync_api import sync_playwright
    from vietnam_legal_rag.ingestion.crawl_legal_documents import USER_AGENT
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=channel, headless=True)
        try:
            page = browser.new_context(locale='vi-VN', user_agent=USER_AGENT).new_page()
            response = page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
            page.wait_for_timeout(4000)
            print('HTTP', response.status, 'URL', page.url, 'TITLE', page.title())
            print('TABS', page.get_by_role('tab').all_inner_texts())
            print(page.locator('body').inner_text()[:6000])
        finally:
            browser.close()
