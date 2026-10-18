"""Atomic progress evidence for validation across interruption boundaries."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix='.' + path.name, suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def record_progress(report_dir: Path, step: str, **updates):
    evidence = report_dir / 'evidence'
    path = evidence / 'state.json'
    state = json.loads(path.read_text()) if path.exists() else {
        'run_identifier': report_dir.name, 'target_total': updates.get('target_total', 0),
        'target_manifest': [], 'selected_ids': [], 'successfully_captured_ids': [],
        'extracted_ids': [], 'validated_ids': [], 'audited_ids': [],
        'parser_bug_ids': [], 'source_ambiguity_ids': [], 'unresolved_ids': [],
        'interruption_history': [], 'latest_test_status': None,
    }
    state.update(updates, timestamp=datetime.now(timezone.utc).isoformat(), last_completed_atomic_step=step)
    target_ids = {d['document_id'] for d in state.get('target_manifest', [])}
    pending = (list(dict.fromkeys(d for d in state.get('successfully_captured_ids', []) if d not in target_ids))
               if len(target_ids) < state.get('target_total', 0) else [])
    state.update(target_manifest_stale=bool(pending), target_manifest_pending_ids=pending)
    atomic_json(path, state)
    # This instruction is stable; state.json always holds the latest operation.
    resume = evidence / 'resume.md'
    if not resume.exists():
        resume.write_text(
            '# Resume VBPL validation\n\n'
            'Read AGENTS.md, state.json, target_manifest.json when present, and checkpoint.md. '
            'Inspect git status/diff and the interrupted RAW/Extract artifact. Reconcile saved '
            'progress with actual manifests and parser fingerprints. Never restart completed '
            'work or recrawl complete RAW. Regenerate stale derived output offline and continue '
            'from the first unfinished atomic operation. Use the configured target and sample '
            'manifests. Gate each hardening wave before acquisition.\n')
    checkpoint = evidence / 'checkpoint.md'
    checkpoint.write_text(
        '# Current resumable validation progress\n\n'
        f"Updated: {state['timestamp']}\n\n"
        f"Phase: {state.get('current_phase')}\n\n"
        f"Wave: {state.get('current_wave')}\n\n"
        f"Local distinct RAW: {state.get('current_local_distinct_raw_count')}\n\n"
        f"Last completed atomic step: {step}\n\n"
        f"Current document: {state.get('current_document')}\n\n"
        f"Next operation: {state.get('next_required_step')}\n\n"
        'Read state.json for parser fingerprints, test status, unresolved findings, target '
        'membership and interruption history. Preserve all completed work and unique evidence '
        'until the configured target has passed its acceptance gates.\n')
    return state
