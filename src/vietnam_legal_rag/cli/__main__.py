"""Unified stdlib CLI: vlr or python -m vietnam_legal_rag.cli."""
import argparse
from importlib import import_module


def main(argv=None):
    parser = argparse.ArgumentParser(prog='vlr', description='VBPL capture, extraction and evaluation tools')
    commands = parser.add_subparsers(dest='command', required=True)
    for name, help_text in [('crawl', 'Capture one VBPL document'), ('extract', 'Extract retained RAW offline'),
                            ('validate', 'Run configured sampling, audits and reporting'),
                            ('audit', 'Audit hierarchy or the schema freeze contract'),
                            ('compare', 'Compare two Extract corpora')]:
        commands.add_parser(name, add_help=False, help=help_text)
    args, remaining = parser.parse_known_args(argv)
    module = import_module(f'vietnam_legal_rag.cli.{args.command}')
    return module.main(remaining)


if __name__ == '__main__':
    raise SystemExit(main())
