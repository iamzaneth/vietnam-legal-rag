"""Sample, audit or report a configured VBPL validation run."""
import argparse
import json
from pathlib import Path
import sys

from vietnam_legal_rag.evaluation.config import ValidationConfig
from vietnam_legal_rag.evaluation import validation_runner as runner
from vietnam_legal_rag.evaluation.report_writer import write_report, write_target_report
from vietnam_legal_rag.ingestion.crawl_legal_documents import CrawlError


def main(argv=None):
    parser = argparse.ArgumentParser(prog='vlr validate', description=__doc__)
    parser.add_argument('action', choices=['discover', 'crawl', 'select-local', 'inventory-local', 'audit', 'complete-wave', 'inspect', 'report'], nargs='?')
    parser.add_argument('--audit', action='store_true', help='Alias for the offline audit action')
    parser.add_argument('--batch-size', type=int, help='Sample size; defaults to saved canonical run or 50')
    parser.add_argument('--wave-size', type=int, help='Wave size; defaults to saved canonical run or 10')
    parser.add_argument('--wave-offset', type=int, default=0, help='Offset for continuous milestone progress wave numbering')
    parser.add_argument('--sample-manifest', '--state', dest='sample_manifest', type=Path)
    parser.add_argument('--report-dir', type=Path, help='Run reports/evidence directory; defaults to reports/validation')
    parser.add_argument('--target-manifest', type=Path, help='Total-corpus target for the report action; reads cumulative source reviews')
    parser.add_argument('--scope-prefix-manifest', type=Path, help='Preserve actual source-scope order from an earlier selected sample')
    parser.add_argument('--central-target', type=int)
    parser.add_argument('--local-target', type=int)
    parser.add_argument('--baseline-manifest', type=Path, action='append', default=[],
                        help='Previous fixed sample state; audit its RAW without changing historical evidence')
    parser.add_argument('--require-wave-gates', action='store_true', default=None,
                        help='Require reviewed cumulative audits and passing tests before acquiring the next wave')
    parser.add_argument('--progress-dir', type=Path, help='Overall milestone progress and recovery evidence directory')
    parser.add_argument('--exclude-document-id', action='append', default=[], help='Additional already-reviewed identity excluded from new samples')
    parser.add_argument('--capture-fixture', type=Path, action='append', default=[], help='Reviewed real-capture fixture membership for the local inventory')
    parser.add_argument('--inventory', type=Path, default=Path('data/interim/discovered_urls.jsonl'))
    parser.add_argument('--raw-dir', type=Path, default=Path('data/raw/vbpl'))
    parser.add_argument('--extracted-dir', type=Path, default=Path('data/extracted/vbpl'))
    parser.add_argument('--wave', type=int, default=1)
    parser.add_argument('--channel', default='chrome')
    parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--url')
    parser.add_argument('--regenerate', action='store_true', help='Re-extract selected RAW during audit')
    parser.add_argument('--output-dir', type=Path, help='Report output override; reads evidence from --report-dir')
    parser.add_argument('--evidence-dir', type=Path, help='Report evidence override (repairs, reviews and tests)')
    parser.add_argument('--regression-fixtures', type=Path, default=Path('tests/fixtures/vbpl_batch_regressions.json'))
    parser.add_argument('--tests-dir', type=Path, default=Path('tests'), help='Test root containing unit/ and regression/')
    args = parser.parse_args(argv)
    action = args.action or ('audit' if args.audit else None)
    if action is None or args.audit and action != 'audit':
        parser.error('choose an action; --audit can only select audit')
    try:
        # The canonical root contains both overall progress and the accumulated
        # audit sample. Resolve action inputs before constructing strict config;
        # explicit selected-state/configuration arguments retain their behavior.
        report_dir = args.report_dir or Path('reports/validation')
        canonical_state = report_dir / 'evidence/corpus_validation_state.json'
        saved = {}
        if action in {'audit', 'report'} and args.sample_manifest is None and canonical_state.is_file():
            saved = json.loads(canonical_state.read_text())
            args.sample_manifest = canonical_state
            if action == 'report' and args.target_manifest is None:
                args.target_manifest = report_dir / 'evidence/target_manifest.json'
        stored = saved.get('run_configuration', {})
        scopes = saved.get('scope_targets', {})
        config = ValidationConfig(batch_size=args.batch_size if args.batch_size is not None else saved.get('target', 50),
                                  wave_size=args.wave_size if args.wave_size is not None else stored.get('wave_size', 10),
                                  wave_offset=args.wave_offset,
                                  scope_prefix=tuple(d['document_scope'] for d in json.loads(
                                      args.scope_prefix_manifest.read_text())['documents']) if args.scope_prefix_manifest else tuple(stored.get('scope_prefix', ())),
                                  sample_manifest=args.sample_manifest, report_dir=args.report_dir,
                                  central_target=args.central_target if args.central_target is not None or args.local_target is not None else scopes.get('trung_uong'),
                                  local_target=args.local_target if args.central_target is not None or args.local_target is not None else scopes.get('dia_phuong'),
                                  baseline_manifests=tuple(args.baseline_manifest or [Path(p) for p in stored.get('baseline_manifests', [])]),
                                  require_wave_gates=args.require_wave_gates if args.require_wave_gates is not None else stored.get('require_wave_gates', False),
                                  progress_dir=args.progress_dir,
                                  excluded_ids=tuple(args.exclude_document_id),
                                  capture_fixtures=tuple(args.capture_fixture),
                                  inventory=args.inventory, raw_dir=args.raw_dir, extracted_dir=args.extracted_dir)
        if not 1 <= args.wave <= config.waves or args.timeout <= 0:
            raise ValueError('wave must be within the configured batch and timeout must be positive')
    except ValueError as exc:
        parser.error(str(exc))
    try:
        if action == 'discover':
            runner.discover(config)
        elif action == 'crawl':
            runner.crawl_wave(args.wave, args.channel, args.timeout, config)
        elif action == 'select-local':
            runner.select_local_wave(args.wave, config)
        elif action == 'inventory-local':
            runner.write_local_inventory(config)
        elif action == 'inspect':
            runner.inspect_source(args.url, args.channel, args.timeout)
        elif action == 'audit':
            return runner.audit_wave(args.regenerate, config)
        elif action == 'complete-wave':
            from vietnam_legal_rag.evaluation.wave_gate import complete_wave
            complete_wave(args.wave, config)
        else:
            if args.target_manifest:
                report = write_target_report(config, args.target_manifest, args.output_dir)
            else:
                report = write_report(config, args.output_dir, evidence_dir=args.evidence_dir,
                                      regression_fixture=args.regression_fixtures, tests_dir=args.tests_dir)
            print(json.dumps(report['metrics'], ensure_ascii=False, indent=2))
    except (CrawlError, OSError, ValueError, KeyError, AssertionError) as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
