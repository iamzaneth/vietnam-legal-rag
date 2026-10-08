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


def choose_candidate(state, scope, config):
    attempted = {a["url"] for a in state["attempts"]}
    existing = {json.loads(p.read_text())["source_url"] for p in config.raw_dir.rglob("manifest.json")}
    used = [d for d in state["documents"] if d["document_scope"] == scope]
    type_counts = Counter(d.get("document_type_hint") for d in used)
    failed_types = Counter(a.get("document_type_hint") for a in state["attempts"]
                           if a["requested_scope"] == scope and a["result"] != "complete")
    bucket_counts = Counter(d.get("sitemap_index") for d in used)
    year_counts = Counter((d.get("year_hint") or 0) // 10 for d in used)
    failed = [a for a in state['attempts'] if a['requested_scope'] == scope and a['result'] in {'failed', 'scope_hint_mismatch'}]
    failed_buckets = Counter(a.get('sitemap_index') for a in failed)
    failed_decades = Counter((a.get('year_hint') or 0) // 10 for a in failed)
    candidates = (json.loads(line) for line in config.inventory.open(encoding="utf-8"))
    candidates = [d for d in candidates if d["scope_hint"] == scope and d["url"] not in attempted
                  and d["url"] not in existing and not d["url"].endswith("--" + config.golden_id)]
    if not candidates:
        raise CrawlError(f"No unused candidate for {scope}")
    # Balance actual encountered types, sitemap generations and decades;
    # deterministic URL hash breaks ties without selecting only the newest.
    return min(candidates, key=lambda d: (
        type_counts[d["document_type_hint"]] + failed_types[d["document_type_hint"]] / 2,
        bucket_counts[d["sitemap_index"]] + failed_buckets[d['sitemap_index']] / 2,
        year_counts[(d.get("year_hint") or 0) // 10] + failed_decades[(d.get('year_hint') or 0) // 10] / 2,
        hashlib.sha256(d["url"].encode()).hexdigest()))
