"""Compare JSON sizes and independently audit an Extract corpus."""
import argparse
import json
from pathlib import Path

from vietnam_legal_rag.evaluation.extract_comparison import compare


def main(argv=None):
    parser = argparse.ArgumentParser(prog='vlr compare', description=__doc__)
    for name in ('before', 'after', 'raw', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args(argv)
    report = compare(args.before, args.after, args.raw)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['totals'], ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
