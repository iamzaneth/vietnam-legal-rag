"""Compatibility wrapper; implementation lives in vietnam_legal_rag.cli.audit."""
from vietnam_legal_rag.cli.audit import schema_main as main


if __name__ == '__main__':
    raise SystemExit(main())
