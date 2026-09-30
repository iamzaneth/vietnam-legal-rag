"""Capture one public vbpl.vn document using the site's browser interface."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

SITEMAP_URL = "https://vbpl.vn/sitemap.xml"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
DOCUMENT_PATH = "/van-ban/chi-tiet/"


class CrawlError(RuntimeError):
    """The capture could not be verified as complete."""


def parse_sitemap(data: bytes) -> tuple[str, list[str]]:
    """Reject error/HTML pages; read only loc entries, not language alternates."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise CrawlError("Sitemap không phải XML hợp lệ") from exc
    kind = root.tag.rsplit("}", 1)[-1]
    if kind not in {"sitemapindex", "urlset"}:
        raise CrawlError(f"Phản hồi không phải sitemap: {kind}")
    return kind, [el.text.strip() for el in root.findall("./{*}*/{*}loc") if el.text]


def is_document_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == "vbpl.vn" and parsed.path.startswith(DOCUMENT_PATH)


def safe_filename(name: str) -> str:
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    return re.sub(r'[\x00-\x1f<>:"|?*]', "_", name).strip(". ") or "attachment.bin"


def file_record(path: Path, root: Path, **extra) -> dict:
    data = path.read_bytes()
    return {"path": path.relative_to(root).as_posix(), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), **extra}


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_public(url: str) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as response:
        return response.read()


def discover_one(requested_url: str | None = None) -> tuple[str, dict]:
    """Read the sitemap index and stop at the first matching document."""
    robots_data = fetch_public("https://vbpl.vn/robots.txt")
    robots = RobotFileParser()
    robots.parse(robots_data.decode("utf-8").splitlines())
    pending = [SITEMAP_URL]
    seen = set()
    records = []
    while pending:
        url = pending.pop(0)
        if url in seen:
            continue
        if urlparse(url).hostname != "vbpl.vn" or not robots.can_fetch("*", url):
            raise CrawlError(f"Sitemap không được phép: {url}")
        seen.add(url)
        data = fetch_public(url)
        kind, urls = parse_sitemap(data)
        records.append({"url": url, "kind": kind, "entries": len(urls)})
        if kind == "sitemapindex":
            pending.extend(urls)
        else:
            for candidate in urls:
                if is_document_url(candidate) and (requested_url is None or candidate == requested_url):
                    if not robots.can_fetch("*", candidate):
                        raise CrawlError(f"robots.txt không cho phép crawl {candidate}")
                    return candidate, {"source": SITEMAP_URL, "selected_from": url, "sitemaps": records}
        time.sleep(0.5)
    raise CrawlError("Không tìm thấy URL văn bản phù hợp trong sitemap")


def validate_attachment(path: Path) -> None:
    """Catch empty/error responses masquerading as downloaded documents."""
    import zipfile

    data = path.read_bytes()
    if not data or data.lstrip().lower().startswith((b"<!doctype html", b"<html", b'{"error')):
        raise CrawlError(f"Tệp rỗng hoặc trang lỗi: {path.name}")
    suffix = path.suffix.lower()
    if suffix == ".pdf" and (not data.startswith(b"%PDF-") or b"%%EOF" not in data[-4096:]):
        raise CrawlError(f"PDF không hợp lệ hoặc bị cắt: {path.name}")
    if suffix in {".docx", ".xlsx", ".zip"}:
        try:
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is not None:
                    raise CrawlError(f"ZIP bị hỏng: {path.name}")
                if suffix == ".docx" and "word/document.xml" not in archive.namelist():
                    raise CrawlError(f"Thiếu nội dung DOCX: {path.name}")
        except zipfile.BadZipFile as exc:
            raise CrawlError(f"ZIP không hợp lệ: {path.name}") from exc


def wait_for_panel(page, panel, pending: set, timeout_ms: int) -> str:
    """Require real, stable panel content and completed application requests."""
    deadline = time.monotonic() + timeout_ms / 1000
    previous = None
    stable_since = time.monotonic()
    while time.monotonic() < deadline:
        text = panel.inner_text().strip()
        loading = panel.locator(
            '.ant-spin-spinning:visible, .ant-skeleton:visible, '
            '.rpv-core__spinner:visible, [aria-busy="true"]:visible'
        ).count()
        if text != previous or pending or loading or not text:
            stable_since = time.monotonic()
            previous = text
        elif time.monotonic() - stable_since >= 1.5:
            if re.search(r"Đang tải|Vui lòng chờ|Sorry, you have been blocked|Lỗi tải dữ liệu", text, re.I):
                raise CrawlError("Tab còn màn hình tải hoặc báo lỗi")
            return text
        page.wait_for_timeout(250)
    raise CrawlError("Hết thời gian chờ nội dung tab và các yêu cầu dữ liệu hoàn tất")


class ContentHTMLParser(HTMLParser):
    """Keep text structure, dropping presentation attributes and executable markup."""

    KEEP = {
        "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "br", "hr",
        "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption",
        "ul", "ol", "li", "dl", "dt", "dd", "blockquote", "pre",
        "strong", "em", "b", "i", "u", "s", "sub", "sup", "a",
    }
    DROP = {"head", "script", "style", "template", "noscript", "iframe",
            "object", "svg", "canvas", "button", "form"}
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, source_url: str):
        super().__init__(convert_charrefs=True)
        self.source_url = source_url
        self.parts: list[str] = []
        self.skipped: list[str] = []

    def handle_starttag(self, tag, attrs):
        if self.skipped or tag in self.DROP:
            if tag not in self.VOID:
                self.skipped.append(tag)
            return
        if tag not in self.KEEP:
            return
        allowed_attrs = {"colspan", "rowspan"} if tag in {"td", "th"} else set()
        if tag == "ol":
            allowed_attrs = {"start"}
        elif tag == "li":
            allowed_attrs = {"value"}
        attributes = "".join(
            f' {key}="{value}"' for key, value in attrs
            if key in allowed_attrs and value and re.fullmatch(r"-?\d+", value)
        )
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                absolute = urljoin(self.source_url, href)
                if urlparse(absolute).scheme in {"http", "https"}:
                    attributes += f' href="{escape(absolute, quote=True)}"'
        self.parts.append(f"<{tag}{attributes}>")

    def handle_endtag(self, tag):
        if self.skipped:
            if tag in self.skipped:
                # Drop everything through this matching closing tag.
                index = len(self.skipped) - 1 - self.skipped[::-1].index(tag)
                del self.skipped[index:]
            return
        if tag in self.KEEP and tag not in self.VOID:
            self.parts.append(f"</{tag}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if not self.skipped:
            self.parts.append(escape(data, quote=False))


def clean_content_html(fragment: str, title: str, source_url: str = "https://vbpl.vn/") -> str:
    parser = ContentHTMLParser(source_url)
    parser.feed(fragment)
    parser.close()
    return ('<!doctype html>\n<html lang="vi">\n<head><meta charset="utf-8">'
            f'<title>{escape(title)}</title></head>\n<body>\n'
            + "".join(parser.parts) + "\n</body>\n</html>\n")


def clean_content_text(text: str) -> str:
    lines = [line.strip() for line in text.replace("\xa0", " ").splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"


def publish_capture(staged: Path, destination: Path) -> None:
    """Replace only after a complete capture; restore the old result on failure."""
    backup = staged.parent / "previous"
    had_previous = destination.exists()
    if had_previous:
        destination.rename(backup)
    try:
        staged.rename(destination)
    except BaseException:
        if had_previous:
            backup.rename(destination)
        raise


def capture_document(url: str, run_dir: Path, manifest: dict, channel: str, headed: bool, timeout_ms: int) -> None:
    from playwright.sync_api import sync_playwright

    pending = set()
    manifest.update({"attachments": [], "files": []})

    def requested(request):
        host = urlparse(request.url).hostname or ""
        if (host == "vbpl.vn" or host.endswith(".moj.gov.vn")) and request.resource_type in {"xhr", "fetch"}:
            pending.add(request)

    def finished(request):
        pending.discard(request)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=channel or None, headless=not headed)
        try:
            context = browser.new_context(locale="vi-VN", user_agent=USER_AGENT,
                                          viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            page = context.new_page()
            page.set_default_timeout(timeout_ms)
            page.on("request", requested)
            page.on("requestfinished", finished)
            page.on("requestfailed", finished)
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if response is None or not response.ok:
                raise CrawlError(f"Trang văn bản trả HTTP {response.status if response else 'unknown'}")
            content_tab = page.get_by_role("tab", name="Nội dung", exact=True)
            content_tab.wait_for(state="visible")
            preview = page.locator(".preview-content").first
            preview.wait_for(state="visible")
            panel = page.locator('[role="tabpanel"]:visible')
            wait_for_panel(page, panel, pending, timeout_ms)
            preview.evaluate('(e) => e.scrollIntoView({block: "end"})')
            wait_for_panel(page, panel, pending, timeout_ms)
            full_text = clean_content_text(preview.inner_text())
            if len(full_text.strip()) < 300:
                raise CrawlError("Chưa có toàn văn đủ để xác nhận")
            reject = page.get_by_role("button", name="Từ chối", exact=True).filter(visible=True)
            if reject.count():
                reject.last.click()
            manifest.update({"title": page.title(), "source_url": url,
                             "full_text_characters": len(full_text.strip())})
            html_file = run_dir / "content.html"
            html_file.write_text(clean_content_html(preview.inner_html(), page.title(), url), encoding="utf-8")
            text_file = run_dir / "content.txt"
            text_file.write_text(full_text, encoding="utf-8")
            manifest["files"] = [file_record(html_file, run_dir), file_record(text_file, run_dir)]

            page.get_by_role("tab", name="Tải về", exact=True).click()
            panel = page.locator('[role="tabpanel"]:visible')
            panel.wait_for(state="visible")
            panel_text = wait_for_panel(page, panel, pending, timeout_ms)
            buttons = panel.locator("button")
            count = buttons.count()
            manifest["expected_attachments"] = count
            if count == 0 and not re.search(r"Không có|Chưa có|No data", panel_text, re.I):
                raise CrawlError("Không xác nhận được danh sách tệp đính kèm")
            if count:
                (run_dir / "attachments").mkdir()
            for i in range(count):
                with page.expect_download(timeout=timeout_ms) as event:
                    buttons.nth(i).click()
                download = event.value
                name = safe_filename(download.suggested_filename)
                target = run_dir / "attachments" / name
                suffix = 2
                while target.exists():
                    target = run_dir / "attachments" / f"{suffix}-{name}"
                    suffix += 1
                download.save_as(target)
                if download.failure():
                    raise CrawlError(f"Không tải được {name}: {download.failure()}")
                validate_attachment(target)
                manifest["attachments"].append(file_record(
                    target, run_dir, original_filename=download.suggested_filename))
                print(f"  Tệp: {name} ({target.stat().st_size:,} bytes)", flush=True)
                page.wait_for_timeout(500)
            if len(manifest["attachments"]) != count:
                raise CrawlError("Chưa tải đủ tệp đính kèm")
            content_tab.click()
            wait_for_panel(page, page.locator('[role="tabpanel"]:visible'), pending, timeout_ms)
            if clean_content_text(preview.inner_text()) != full_text:
                raise CrawlError("Toàn văn thay đổi trong lần thu thập; cần chạy lại")
            manifest["validation"] = {"content_stable": True, "all_listed_attachments_downloaded": True}
        finally:
            browser.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crawl một văn bản vbpl.vn: nội dung HTML/TXT sạch và tệp đính kèm")
    parser.add_argument("--output", type=Path, default=Path("data/raw/vbpl"))
    parser.add_argument("--url", help="URL có trong sitemap (mặc định chọn văn bản đầu tiên)")
    parser.add_argument("--channel", default="chrome", help="chrome (đã cài) hoặc chromium (Playwright)")
    parser.add_argument("--headed", action="store_true", help="Hiển thị cửa sổ trình duyệt")
    parser.add_argument("--timeout", type=int, default=60, help="Thời gian chờ mỗi bước, tính bằng giây")
    args = parser.parse_args(argv)
    if args.url and not is_document_url(args.url):
        parser.error("--url phải là URL https://vbpl.vn/van-ban/chi-tiet/...")
    if args.timeout <= 0:
        parser.error("--timeout phải lớn hơn 0")
    try:
        print("Đọc sitemap...", flush=True)
        url, discovery = discover_one(args.url)
        identifier = url.rsplit("--", 1)[-1]
        if not re.fullmatch(r"[0-9a-fA-F-]{36}", identifier):
            identifier = hashlib.sha256(url.encode()).hexdigest()[:32]
        manifest = {"source": "vbpl.vn", "document_id": f"vbpl:{identifier}",
                    "retrieved_at": datetime.now(timezone.utc).isoformat(), "discovery": discovery}
        args.output.mkdir(parents=True, exist_ok=True)
        destination = args.output / identifier
        print(f"Văn bản duy nhất: {url}", flush=True)
        # Failed attempts leave no partial document folder. A previous successful
        # result remains intact until the replacement is fully downloaded.
        with tempfile.TemporaryDirectory(prefix=".crawl-", dir=args.output) as temporary:
            staged = Path(temporary) / "document"
            staged.mkdir()
            capture_document(url, staged, manifest, args.channel, args.headed, args.timeout * 1000)
            manifest.update({"status": "complete", "completed_at": datetime.now(timezone.utc).isoformat()})
            write_json(staged / "manifest.json", manifest)
            publish_capture(staged, destination)
        print(f"Kết quả: {destination}", flush=True)
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
