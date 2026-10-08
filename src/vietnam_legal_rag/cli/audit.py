"""Independent hierarchy and schema freeze audits."""
import argparse
import json
from pathlib import Path
import sys

from vietnam_legal_rag.evaluation.audit import hierarchy as hierarchy_audit, schema as schema_audit
from vietnam_legal_rag.ingestion.extract_legal_documents import encoded


def main(argv=None):
    parser = argparse.ArgumentParser(prog='vlr audit', description=__doc__)
    subparsers = parser.add_subparsers(dest='kind', required=True)
    hierarchy = subparsers.add_parser('hierarchy', description=hierarchy_audit.__doc__)
    schema = subparsers.add_parser('schema', description=schema_audit.__doc__)
    for command in (hierarchy, schema):
        for name in ('raw', 'extracted', 'report'):
            command.add_argument('--' + name, type=Path, required=True)
    hierarchy.add_argument('--sample', required=True)
    hierarchy.add_argument('--before', type=Path)
    schema.add_argument('--before', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.kind == 'hierarchy':
        report = hierarchy_audit.audit(args.raw, args.extracted, args.sample, args.before)
        text = hierarchy_audit.markdown(report)
        summary = report['totals']
    else:
        report = schema_audit.build_report(args.raw, args.extracted, args.before)
        text = schema_audit.markdown(report)
        summary = {'freeze_status': report['freeze_status'], 'files': report['verified_json_files'],
                   'issues': report['issue_summary']}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_bytes(encoded(report))
    args.report.with_suffix('.md').write_text(text, encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def hierarchy_main(argv=None):
    return main(['hierarchy', *(sys.argv[1:] if argv is None else argv)])


def schema_main(argv=None):
    return main(['schema', *(sys.argv[1:] if argv is None else argv)])


if __name__ == '__main__':
    raise SystemExit(main())
