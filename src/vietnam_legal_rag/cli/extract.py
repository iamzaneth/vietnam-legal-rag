"""Extract semantic JSON from retained RAW HTML offline."""
import argparse
from pathlib import Path

from vietnam_legal_rag.ingestion.extract_legal_documents import extract_corpus

def main(argv=None):
    parser = argparse.ArgumentParser(prog='vlr extract', description="Extract semantic JSON từ HTML raw; không truy cập mạng")
    parser.add_argument("--input", type=Path, default=Path("data/raw/vbpl"))
    parser.add_argument("--output", type=Path, default=Path("data/extracted/vbpl"))
    parser.add_argument("--debug-tree", action="store_true", help="In cây semantic ra console để audit; không lưu TXT")
    args = parser.parse_args(argv)
    try:
        return extract_corpus(args.input, args.output, args.debug_tree)
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
