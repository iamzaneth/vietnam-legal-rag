"""Deterministic VBPL candidate hints and balanced selection."""
from collections import Counter
import hashlib
import json
import re
from urllib.parse import urlparse

from vietnam_legal_rag.ingestion.crawl_legal_documents import CrawlError, canonical_document_url

TYPES = {"luat": "Luật", "nghi-dinh": "Nghị định", "nghi-quyet": "Nghị quyết",
         "quyet-dinh": "Quyết định", "thong-tu": "Thông tư", "chi-thi": "Chỉ thị",
         "phap-lenh": "Pháp lệnh", "van-ban-hop-nhat": "Văn bản hợp nhất"}


def document_identity(url):
    identifier = urlparse(url).path.rsplit('--', 1)[-1]
    if not re.fullmatch(r'(?:[0-9a-fA-F-]{36}|\d+)', identifier):
        identifier = hashlib.sha256(canonical_document_url(url).encode()).hexdigest()[:32]
    return 'vbpl:' + identifier


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


def source_family(url):
    """A URL-format availability hint, never a document or source-scope identity."""
    token = urlparse(url).path.rsplit('--', 1)[-1]
    if token.isdigit():
        return 'numeric'
    if re.fullmatch(r'[0-9a-fA-F-]{32,36}', token):
        return 'opaque'
    return re.sub(r'[_-]?\d+$', '', token)


def choose_candidate(state, scope, config):
    source_attempts = [a for a in state['attempts']
                       if a.get('failure_classification') != 'execution_environment_network_failure']
    attempted = {a["url"] for a in source_attempts}
    captures = [json.loads(p.read_text()) for p in config.raw_dir.rglob('manifest.json')]
    existing = {canonical_document_url(c['source_url']) for c in captures}
    identities = {c['document_id'] for c in captures} | {d['document_id'] for d in state['documents']} | set(config.excluded_ids)
    used = [d for d in state["documents"] if d["document_scope"] == scope]
    type_counts = Counter(d.get("document_type_hint") for d in used)
    failed_types = Counter(a.get("document_type_hint") for a in source_attempts
                           if a["requested_scope"] == scope and a["result"] != "complete")
    bucket_counts = Counter(d.get("sitemap_index") for d in used)
    year_counts = Counter((d.get("year_hint") or 0) // 10 for d in used)
    failed = [a for a in source_attempts if a['requested_scope'] == scope and a['result'] in {'failed', 'scope_hint_mismatch'}]
    failed_buckets = Counter(a.get('sitemap_index') for a in failed)
    failed_decades = Counter((a.get('year_hint') or 0) // 10 for a in failed)
    available_families, unavailable_families = Counter(), Counter()
    for attempt in source_attempts:
        family = source_family(attempt['url'])
        if attempt['result'] in {'complete', 'scope_hint_mismatch'}:
            available_families[family] += 1  # Captured source is available in its actual scope.
        elif attempt['result'] == 'failed':
            unavailable_families[family] += 1
    # Issuer-derived URL hints can disagree with the actual source breadcrumb.
    # Learn priority from distinct captured documents, without changing either
    # classification or excluding an otherwise permitted candidate.
    scope_matches, scope_mismatches, observed_ids = Counter(), Counter(), set()
    for record in state['documents'] + source_attempts:
        identity = record.get('document_id')
        actual = record.get('document_scope') or record.get('actual_scope')
        if (not identity or identity in observed_ids or record.get('scope_hint') != scope or
                actual not in {'trung_uong', 'dia_phuong'}):
            continue
        observed_ids.add(identity)
        key = (record.get('document_type_hint'), (record.get('year_hint') or 0) // 10)
        (scope_matches if actual == scope else scope_mismatches)[key] += 1
    with config.inventory.open(encoding='utf-8') as inventory:
        candidates = [d for line in inventory if (d := json.loads(line))["scope_hint"] == scope
                      and d["url"] not in attempted and d["url"] not in existing
                      and document_identity(d['url']) not in identities
                      and document_identity(d['url']) != 'vbpl:' + config.golden_id]
    if not candidates:
        raise CrawlError(f"No unused candidate for {scope}")
    # Balance actual encountered types, sitemap generations and decades;
    # deterministic URL hash breaks ties without selecting only the newest.
    return min(candidates, key=lambda d: (
        scope_mismatches[(d['document_type_hint'], (d.get('year_hint') or 0) // 10)] /
        (scope_matches[(d['document_type_hint'], (d.get('year_hint') or 0) // 10)] +
         scope_mismatches[(d['document_type_hint'], (d.get('year_hint') or 0) // 10)] + 2),
        unavailable_families[source_family(d['url'])] /
        (available_families[source_family(d['url'])] + unavailable_families[source_family(d['url'])] + 2),
        type_counts[d["document_type_hint"]] + failed_types[d["document_type_hint"]] / 2,
        bucket_counts[d["sitemap_index"]] + failed_buckets[d['sitemap_index']] / 2,
        year_counts[(d.get("year_hint") or 0) // 10] + failed_decades[(d.get('year_hint') or 0) // 10] / 2,
        hashlib.sha256(d["url"].encode()).hexdigest()))


def choose_existing(state, scope, config):
    """Select an unused complete local capture without a network operation."""
    from .local_inventory import inspect_capture
    from .wave_gate import baseline_documents
    excluded = {d['document_id'] for d in state['documents'] + baseline_documents(config)}
    excluded |= set(config.excluded_ids) | {'vbpl:' + config.golden_id}
    candidates = []
    for path in sorted(config.raw_dir.rglob('manifest.json')):
        manifest = json.loads(path.read_text())
        if manifest.get('document_scope') != scope or manifest.get('document_id') in excluded:
            continue
        if not inspect_capture(path)['usable']:
            continue
        candidate = candidate_metadata(manifest['source_url'], '', 0)
        candidates.append({**candidate, 'document_id': manifest['document_id'], 'raw_directory': str(path.parent),
                           'document_scope': scope, 'sampling_origin': 'existing_local_raw'})
    if not candidates:
        raise CrawlError(f'No unused complete local RAW for {scope}')
    used = [d for d in state['documents'] if d['document_scope'] == scope]
    types = Counter(d.get('document_type_hint') for d in used)
    decades = Counter((d.get('year_hint') or 0) // 10 for d in used)
    return min(candidates, key=lambda d: (types[d['document_type_hint']], decades[(d['year_hint'] or 0) // 10],
                                           hashlib.sha256(d['url'].encode()).hexdigest()))
