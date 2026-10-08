"""Capture one VBPL document."""
import argparse
from pathlib import Path
import sys

from vietnam_legal_rag.ingestion import crawl_legal_documents as crawler

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='vlr crawl', description="Crawl mọi tab văn bản vbpl.vn, trừ Tải về và Văn bản gốc")
    parser.add_argument("--output", type=Path, default=Path("data/raw/vbpl"))
    parser.add_argument("--url", help="URL có trong sitemap (mặc định chọn văn bản đầu tiên)")
    parser.add_argument("--channel", default="chrome", help="chrome (đã cài) hoặc chromium (Playwright)")
    parser.add_argument("--headed", action="store_true", help="Hiển thị cửa sổ trình duyệt")
    parser.add_argument("--timeout", type=int, default=60, help="Thời gian chờ mỗi bước, tính bằng giây")
    args = parser.parse_args(argv)
    if args.url and not crawler.is_document_url(args.url):
        parser.error("--url phải là URL https://vbpl.vn/van-ban/chi-tiet/...")
    if args.timeout <= 0:
        parser.error("--timeout phải lớn hơn 0")
    try:
        destination = crawler.crawl_one(args.output, args.url, args.channel, args.headed, args.timeout)
        print(f"Kết quả: {destination}", flush=True)
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
