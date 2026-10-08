"""Sample, audit or report a configured VBPL validation run."""
import argparse
from pathlib import Path
import sys

from vietnam_legal_rag.evaluation.config import ValidationConfig
from vietnam_legal_rag.evaluation import validation_runner as runner
from vietnam_legal_rag.evaluation.report_writer import write_report
from vietnam_legal_rag.ingestion.crawl_legal_documents import CrawlError


def main(argv=None):
    parser = argparse.ArgumentParser(prog='vlr validate', description=__doc__)
    parser.add_argument('action', choices=['discover', 'crawl', 'audit', 'inspect', 'report'], nargs='?')
    parser.add_argument('--audit', action='store_true', help='Alias for the offline audit action')
    parser.add_argument('--batch-size', type=int, default=50)
    parser.add_argument('--wave-size', type=int, default=10)
    parser.add_argument('--sample-manifest', '--state', dest='sample_manifest', type=Path)
    parser.add_argument('--report-dir', type=Path, help='Run reports/evidence directory; defaults to reports/extract-validation-N')
    parser.add_argument('--central-target', type=int)
    parser.add_argument('--local-target', type=int)
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
        config = ValidationConfig(batch_size=args.batch_size, wave_size=args.wave_size,
                                  sample_manifest=args.sample_manifest, report_dir=args.report_dir,
                                  central_target=args.central_target, local_target=args.local_target,
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
        elif action == 'inspect':
            runner.inspect_source(args.url, args.channel, args.timeout)
        elif action == 'audit':
            return runner.audit_wave(args.regenerate, config)
        else:
            report = write_report(config, args.output_dir, evidence_dir=args.evidence_dir,
                                  regression_fixture=args.regression_fixtures, tests_dir=args.tests_dir)
            import json
            print(json.dumps(report['metrics'], ensure_ascii=False, indent=2))
    except (CrawlError, OSError, ValueError, KeyError, AssertionError) as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
