"""Resumable, throttled VBPL sampling and offline extraction audit.

Discovery uses public, robots-permitted sitemaps. Scope hints only select
candidates; the crawler's document breadcrumb establishes final scope.
RAW is captured with the existing crawler and never edited by this runner.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import tempfile
import time
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from vietnam_legal_rag.ingestion.crawl_legal_documents import (
    CrawlError, SITEMAP_URL, canonical_document_url, capture_document,
    fetch_public, is_document_url, parse_sitemap, publish_capture, write_json,
)
from vietnam_legal_rag.ingestion.extract_legal_documents import extract_document
from vietnam_legal_rag.ingestion.html.structure import PARSER_VERSION, SCHEMA_VERSION

from .config import ValidationConfig
from .validation_sampler import candidate_metadata, choose_candidate, document_identity
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


def run_configuration(config):
    result = {'baseline_manifests': [str(p) for p in config.baseline_manifests],
              'require_wave_gates': config.require_wave_gates, 'wave_size': config.wave_size}
    if config.scope_prefix:
        result['scope_prefix'] = list(config.scope_prefix)
    return result


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
        configuration = run_configuration(config)
        if state.get('run_configuration', configuration) != configuration:
            raise CrawlError('Run baseline/wave gate configuration differs; preserve the original run configuration')
        return state
    return {"started_at": now(), "schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
            "target": config.batch_size, "scope_targets": config.scope_targets, "documents": [], "attempts": [], "waves": [], "repairs": []}


def save_state(state, config: ValidationConfig, step='validation state persisted', document=None):
    from .progress import atomic_json, record_progress
    config.sample_manifest.parent.mkdir(parents=True, exist_ok=True)
    state['last_completed_atomic_step'] = step
    if document is not None:
        state['current_document'] = document
    atomic_json(config.sample_manifest, state)
    if config.progress_dir:
        from .wave_gate import parser_fingerprint
        fingerprint = parser_fingerprint()
        documents = state['documents'] + state.get('baseline_validations', [])
        audited = [d['document_id'] for d in documents if d.get('audited_parser_fingerprint') == fingerprint]
        if state.get('audited_parser_fingerprint') == fingerprint and state.get('golden_validation'):
            audited.append('vbpl:' + config.golden_id)
        progress_path = config.progress_dir / 'evidence/state.json'
        previous = json.loads(progress_path.read_text()) if progress_path.exists() else {}
        captured = list(dict.fromkeys(previous.get('successfully_captured_ids', []) +
                                      [d['document_id'] for d in documents]))
        record_progress(config.progress_dir, step,
                        target_total=previous.get('target_total', config.batch_size),
                        active_validation_state=str(config.sample_manifest),
                        current_wave=config.wave_offset + ((len(state['documents']) - 1) // config.wave_size + 1 if state['documents'] else 1),
                        current_document=state.get('current_document'),
                        selected_ids=[d['document_id'] for d in documents],
                        successfully_captured_ids=captured,
                        extracted_ids=[d['document_id'] for d in documents if d.get('initial_extract_status') or d.get('final_validation')],
                        validated_ids=audited, audited_ids=audited,
                        schema_version=SCHEMA_VERSION, parser_version=PARSER_VERSION,
                        parser_fingerprint=fingerprint,
                        derived_outputs_stale=state.get('audited_parser_fingerprint') != fingerprint)
        if step == 'RAW capture completed':
            collection_needed(config)


def collection_needed(config):
    """Count all usable local identities before network collection, including mismatches."""
    if not config.progress_dir:
        return True
    path = config.progress_dir / 'evidence/state.json'
    progress = json.loads(path.read_text()) if path.exists() else {}
    target = progress.get('target_total')
    if not target:
        return True
    from .local_inventory import inventory_raw
    from .progress import record_progress
    inventory = inventory_raw(config.raw_dir)
    count = inventory['local_raw_distinct_total']
    record_progress(config.progress_dir, 'local RAW count checked before further capture',
                    current_local_distinct_raw_count=count, documents_needed=max(0, target - count),
                    successfully_captured_ids=[d['document_id'] for d in inventory['documents']])
    if count >= target:
        print('Overall usable local RAW target reached; assemble/reuse the target without another capture.', flush=True)
    return count < target


def capture(candidate, policy, discovery, channel, timeout, config: ValidationConfig):
    url = candidate["url"]
    if not is_document_url(url) or not policy.can_fetch("*", url):
        raise CrawlError(f"Document outside source/robots policy: {url}")
    identity = document_identity(url)
    identifier = identity.removeprefix('vbpl:')
    manifest = {"source": "vbpl.vn", "document_id": identity, "retrieved_at": now(),
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


def retained_candidate(state, scope, wave):
    """Use a new capture's actual scope later in the same acquisition wave.

    Historical extras remain excluded. A scope mismatch is not a capture
    defect and need not trigger another network request for that document.
    """
    used = {d['document_id'] for d in state['documents']}
    return next((a for a in state['attempts'] if a['result'] == 'scope_hint_mismatch'
                 and a.get('wave') == wave and a['actual_scope'] == scope
                 and a['document_id'] not in used), None)


def crawl_wave(wave, channel, timeout, config: ValidationConfig):
    if not 1 <= wave <= config.waves:
        raise ValueError('wave must be within the configured batch')
    state = load_state(config)
    if config.require_wave_gates:
        from .wave_gate import check_acquisition_gate
        check_acquisition_gate(wave, state, config)
    if not collection_needed(config):
        return
    policy, discovery = None, None
    target = min(wave * config.wave_size, config.batch_size)
    attempts_this_run = 0
    while len(state["documents"]) < target:
        if not collection_needed(config):
            return
        if attempts_this_run >= 60:
            raise CrawlError("Wave attempted 60 candidates; inspect source failures before continuing")
        scope = config.scope_at(len(state["documents"]))
        retained = retained_candidate(state, scope, wave)
        existing = None
        if config.progress_dir:
            from .validation_sampler import choose_existing
            try:
                existing = choose_existing(state, scope, config)
            except CrawlError as exc:
                if not str(exc).startswith('No unused complete local RAW'):
                    raise
        candidate = existing or retained or choose_candidate(state, scope, config)
        attempt = {**candidate, "requested_scope": scope, "started_at": now(), "result": "running", 'wave': wave}
        state["attempts"].append(attempt)
        save_state(state, config, 'candidate selected', candidate['url'])
        print(f"Candidate {len(state['documents']) + 1}/{config.batch_size} {scope}: {candidate['url']}", flush=True)
        try:
            if existing or retained:
                directory = Path(candidate['raw_directory'])
                manifest = json.loads((directory / 'manifest.json').read_text())
            else:
                if policy is None:
                    policy, _ = robots()
                    discovery = json.loads(config.inventory.with_suffix(".discovery.json").read_text())
                manifest, directory = capture(candidate, policy, discovery, channel, timeout, config)
            attempt.update(result="complete", document_id=manifest["document_id"], raw_directory=str(directory),
                           actual_scope=manifest["document_scope"])
            save_state(state, config, 'RAW capture completed', manifest['document_id'])
            if manifest["document_scope"] != scope:
                attempt["result"] = "scope_hint_mismatch"
                attempt["reason"] = "Captured breadcrumb differs from URL hint; immutable capture retained."
            else:
                if existing:
                    attempt['result'] = 'existing_capture'
                elif retained:
                    attempt['result'] = 'reused_capture'
                document = {**candidate, "document_id": manifest["document_id"], "document_scope": scope,
                            "raw_directory": str(directory), "crawl_result": "complete",
                            "sequence": len(state["documents"]) + 1, "wave": wave}
                for key in ('requested_scope', 'started_at', 'completed_at', 'result', 'reason', 'actual_scope'):
                    document.pop(key, None)
                state["documents"].append(document)
                save_state(state, config, 'sample document added', document['document_id'])
                result = extract_document(directory, config.extracted_dir / directory.name)
                document["initial_extract_status"] = result["status"]
                document["initial_issue_summary"] = result["issue_summary"]
                save_state(state, config, 'document extracted', document['document_id'])
                print(f"Extract: {result['status']} {result['issue_summary']}", flush=True)
        except Exception as exc:
            attempt.update(result="failed", reason=f"{type(exc).__name__}: {exc}")
            print(attempt["reason"], flush=True)
            reason = exc.reason if isinstance(exc, URLError) else exc
            if isinstance(reason, socket.gaierror):
                attempt.update(failure_classification='execution_environment_network_failure', completed_at=now())
                save_state(state, config, 'execution environment DNS failure persisted', candidate['url'])
                raise CrawlError('Execution environment DNS failure; retry with permitted network access') from exc
        attempt["completed_at"] = now()
        save_state(state, config)
        attempts_this_run += 1
        time.sleep(3)
    print(f"Wave {wave}: {len(state['documents'])} successful distinct RAW captures", flush=True)


def audit_wave(regenerate, config: ValidationConfig):
    state = load_state(config)
    state['run_configuration'] = run_configuration(config)
    from .wave_gate import parser_fingerprint, baseline_documents
    fingerprint = parser_fingerprint()
    state['baseline_validations'] = []
    for document in baseline_documents(config):
        result = audit_document(Path(document['raw_directory']), regenerate, config.extracted_dir)
        state['baseline_validations'].append({**document, 'final_validation': result, 'audited_parser_fingerprint': fingerprint})
        print(f"Baseline {document['document_id']}: {result['status']} audit_errors={result['audit_errors']}", flush=True)
        save_state(state, config, 'baseline document audited', document['document_id'])
    for document in state["documents"]:
        result = audit_document(Path(document["raw_directory"]), regenerate, config.extracted_dir)
        document["final_validation"] = result
        document['audited_parser_fingerprint'] = fingerprint
        print(f"{document['sequence']:02} {document['document_id']} {result['status']} {result['quality']} "
              f"{result['issue_summary']} audit_errors={len(result['audit_errors'])}", flush=True)
        save_state(state, config, 'sample document audited', document['document_id'])
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
    state['audited_parser_fingerprint'] = fingerprint
    state['schema_version'], state['parser_version'] = SCHEMA_VERSION, PARSER_VERSION
    state["waves"].append({"audited_at": now(), "documents": len(state["documents"]), "regenerated": regenerate})
    save_state(state, config, 'cumulative corpus revalidation completed', 'vbpl:' + config.golden_id)
    print("Golden:", golden["quality"], golden["issue_summary"], "audit_errors=", golden["audit_errors"], flush=True)
    return int(bool(golden["audit_errors"]) or any(d["final_validation"]["audit_errors"] or
               not all(d["final_validation"]["quality"].values()) for d in state["documents"] + state['baseline_validations']))


def select_local_wave(wave, config):
    from .validation_sampler import choose_existing
    from .wave_gate import check_acquisition_gate
    state = load_state(config)
    if config.require_wave_gates:
        check_acquisition_gate(wave, state, config)
    target = min(wave * config.wave_size, config.batch_size)
    while len(state['documents']) < target:
        scope = config.scope_at(len(state['documents']))
        document = choose_existing(state, scope, config)
        document.update(sequence=len(state['documents']) + 1, wave=wave, crawl_result='complete')
        state['documents'].append(document)
        state['attempts'].append({**document, 'requested_scope': scope, 'result': 'existing_capture',
                                  'completed_at': now(), 'reason': 'Verified complete existing RAW; no network capture.'})
        save_state(state, config, 'existing local RAW selected', document['document_id'])
        result = extract_document(Path(document['raw_directory']), config.extracted_dir / Path(document['raw_directory']).name)
        document.update(initial_extract_status=result['status'], initial_issue_summary=result['issue_summary'])
        save_state(state, config, 'existing document extracted', document['document_id'])
        print(f"{document['sequence']:02} {document['document_id']} {result['status']} {result['issue_summary']}", flush=True)


def write_local_inventory(config):
    from .local_inventory import inventory_raw
    from .progress import atomic_json
    memberships = {'vbpl:' + config.golden_id: [{'role': 'golden'}]}
    for path in config.baseline_manifests:
        for document in json.loads(path.read_text())['documents']:
            memberships.setdefault(document['document_id'], []).append({'role': 'validated_baseline', 'manifest': str(path)})
    for path in config.capture_fixtures:
        fixture = json.loads(path.read_text())
        identities = fixture.get('document_ids', [d['document_id'] for d in fixture.get('documents', [])])
        for identity in identities:
            memberships.setdefault(identity, []).append({'role': 'reviewed_regression_capture', 'fixture': str(path)})
    inventory = inventory_raw(config.raw_dir, memberships)
    atomic_json(config.report_dir / 'evidence/local_raw_inventory.json', inventory)
    print(json.dumps({k: v for k, v in inventory.items() if k not in {'documents', 'captures'}}, ensure_ascii=False, indent=2))
    return inventory


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
    from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeoutError
    from vietnam_legal_rag.ingestion.crawl_legal_documents import USER_AGENT
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=channel, headless=True)
        try:
            page = browser.new_context(locale='vi-VN', user_agent=USER_AGENT).new_page()
            response = page.goto(url, wait_until='domcontentloaded', timeout=timeout * 1000)
            try:
                page.wait_for_function(
                    "() => document.querySelector('[role=tab]') || "
                    "document.body.innerText.includes('Văn bản không tồn tại')",
                    timeout=timeout * 1000)
            except BrowserTimeoutError:
                print('SOURCE_STATE unresolved after bounded loading wait')
            print('HTTP', response.status, 'URL', page.url, 'TITLE', page.title())
            print('TABS', page.get_by_role('tab').all_inner_texts())
            print(page.locator('body').inner_text()[:6000])
        finally:
            browser.close()
