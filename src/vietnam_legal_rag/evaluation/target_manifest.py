"""Assemble a distinct total-corpus target from verified local source inventory."""
from collections import Counter
import hashlib


def assemble_target(inventory, target_total, required):
    """Keep required baselines, then select diverse local captures deterministically.

    An incomplete target explicitly records its deficit; it is never padded
    with duplicate roles or unavailable source documents. Extra RAW stays intact.
    """
    if target_total < 1 or len(required) > target_total:
        raise ValueError('Target must be positive and cover every required document')
    available = {d['document_id']: d for d in inventory['documents'] if d['usable']}
    if len(available) != len(inventory['documents']):
        raise ValueError('Canonical inventory must contain distinct usable documents')
    identities = [d['document_id'] for d in required]
    if len(identities) != len(set(identities)):
        raise ValueError('Required roles must be combined for each source identity')
    missing = set(identities) - set(available)
    if missing:
        raise ValueError('Required documents lack usable RAW: ' + ', '.join(sorted(missing)))
    selected, counts, types, decades = [], Counter(), Counter(), Counter()
    def append(source, membership):
        record = {'document_id': source['document_id'], 'raw_path': source['capture_path'],
                  'source_url': source['source_url'], 'source_scope': source['source_scope'],
                  'origin': membership.get('origin', 'existing_local_raw'),
                  'roles': source['roles'], 'validation_status': membership.get('validation_status', 'pending'),
                  'validation_wave': membership.get('validation_wave'),
                  'validation_parser_fingerprint': membership.get('validation_parser_fingerprint')}
        selected.append(record)
        counts[source['source_scope']] += 1
        types[source.get('document_type_hint')] += 1
        decades[(source.get('year_hint') or 0) // 10] += 1
    for member in required:
        append(available.pop(member['document_id']), member)
    while available and len(selected) < target_total:
        # Actual source scope supplies balance; URL text is only a stable
        # diversity hint. No source scope or metadata is rewritten.
        source = min(available.values(), key=lambda d: (
            counts[d['source_scope']],
            types[d.get('document_type_hint')], decades[(d.get('year_hint') or 0) // 10],
            hashlib.sha256(d['source_url'].encode()).hexdigest(), d['document_id']))
        append(source, {})
        del available[source['document_id']]
    return {'target_total': target_total, 'assembled_documents': len(selected),
            'complete': len(selected) == target_total,
            'local_raw_distinct_total': inventory['local_raw_distinct_total'],
            'documents_needed': max(0, target_total - inventory['local_raw_distinct_total']),
            'local_documents_outside_target': len(available),
            'scope_counts': dict(counts), 'documents': selected}
