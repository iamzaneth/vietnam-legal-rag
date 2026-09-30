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



# Use the document breadcrumb, never navigation menus or mentions in its text.
DOCUMENT_SCOPES = {
    "/van-ban/trung-uong": "trung_uong",
    "/van-ban/dia-phuong": "dia_phuong",
}


def classify_document_scope(breadcrumb_urls: list[str]) -> str:
    scopes = {
        DOCUMENT_SCOPES[parsed.path.rstrip("/")]
        for url in breadcrumb_urls
        if (parsed := urlparse(urljoin("https://vbpl.vn/", url))).hostname == "vbpl.vn"
        and parsed.path.rstrip("/") in DOCUMENT_SCOPES
    }
    if len(scopes) != 1:
        raise CrawlError("Không xác định được duy nhất nhóm trung ương/địa phương từ breadcrumb")
    return scopes.pop()

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



METADATA_TABS = (("properties", "Thuộc tính"), ("relations", "Lược đồ"), ("history", "Lịch sử"))

# Retain source labels and values instead of inferring dates or legal status.
TAB_DATA_SCRIPT = r"""panel => {
    const text = e => e ? e.innerText.trim() : '';
    const link = a => a && a.hasAttribute('href') && /^https?:/.test(a.href) ? a.href : null;
    return {
        fields: Array.from(panel.querySelectorAll('.ant-descriptions-item-container')).map(e => ({
            label: text(e.querySelector('.ant-descriptions-item-label')),
            value: text(e.querySelector('.ant-descriptions-item-content'))
        })),
        groups: Array.from(panel.querySelectorAll('.ant-card-body')).map(e => ({
            label: text(e.querySelector(':scope > span')),
            items: Array.from(e.querySelectorAll('li')).filter(li => text(li) !== '--').map(li => ({
                title: text(li.querySelector('a')), text: text(li), url: link(li.querySelector('a'))
            }))
        })),
        columns: Array.from(panel.querySelectorAll('thead th')).map(text),
        rows: Array.from(panel.querySelectorAll('tbody tr.ant-table-row')).map(row => ({
            source_key: row.getAttribute('data-row-key'),
            cells: Array.from(row.querySelectorAll('td')).map(text),
            links: Array.from(row.querySelectorAll('a')).map(a => ({text: text(a), url: link(a)}))
        })),
        empty: !!panel.querySelector('.ant-empty'),
        links: Array.from(panel.querySelectorAll('a')).map(a => ({text: text(a), url: link(a)}))
    };
}"""


def validate_tab_data(key: str, data: dict) -> None:
    if key == "properties" and not data["fields"]:
        raise CrawlError("Tab Thuộc tính thiếu các trường dữ liệu")
    if key == "relations":
        if not data["groups"] and not data["empty"]:
            raise CrawlError("Không xác nhận được dữ liệu Lược đồ")
        for group in data["groups"]:
            count = re.search(r"\((\d+)\)\s*$", group["label"])
            if not count or int(count[1]) != len(group["items"]):
                raise CrawlError(f"Lược đồ chưa đủ mục: {group['label']}")
    if key == "history" and not data["rows"] and not data["empty"]:
        raise CrawlError("Không xác nhận được dữ liệu Lịch sử")


def capture_metadata_tabs(page, run_dir: Path, manifest: dict, pending: set, timeout_ms: int) -> None:
    """Save each metadata tab, including all history pages, before publishing."""
    manifest["tabs"] = {"content": {"label": "Nội dung", "status": "complete",
                                    "files": ["content.html", "content.txt"]}}
    for key, label in METADATA_TABS:
        tab = page.get_by_role("tab", name=label, exact=True)
        tab.wait_for(state="visible")
        tab.click()
        panel = page.locator('[role="tabpanel"]:visible')
        panel.wait_for(state="visible")
        pages = []
        seen = set()
        while True:
            text = clean_content_text(wait_for_panel(page, panel, pending, timeout_ms))
            data = panel.evaluate(TAB_DATA_SCRIPT)
            validate_tab_data(key, data)
            signature = json.dumps(data, ensure_ascii=False, sort_keys=True)
            if signature in seen:
                raise CrawlError(f"Phân trang {label} không tiến tới trang tiếp theo")
            seen.add(signature)
            pages.append({"text": text, "html": panel.inner_html(), "data": data})
            next_page = panel.locator('.ant-pagination-next:not(.ant-pagination-disabled)')
            if not next_page.count():
                break
            previous_text = panel.inner_text().strip()
            next_page.click()
            # Wait for the actual rows to change, not just a spinner to disappear.
            deadline = time.monotonic() + timeout_ms / 1000
            while panel.inner_text().strip() == previous_text:
                if time.monotonic() >= deadline:
                    raise CrawlError(f"Hết thời gian chờ trang tiếp theo của {label}")
                page.wait_for_timeout(250)
        paths = []
        html = "\n".join(f"<section><h2>{escape(label)} — {i}</h2>{item['html']}</section>"
                         for i, item in enumerate(pages, 1))
        for suffix, value in (("html", clean_content_html(html.replace("</span>", "</span> "),
                                                        f"{manifest['title']} — {label}",
                                                        manifest["source_url"])),
                              ("txt", "\n\n".join(item["text"] for item in pages))):
            path = run_dir / f"{key}.{suffix}"
            path.write_text(value, encoding="utf-8")
            paths.append(path.name)
            manifest["files"].append(file_record(path, run_dir))
        path = run_dir / f"{key}.json"
        write_json(path, {"source_url": manifest["source_url"], "tab": label,
                          "retrieved_at": datetime.now(timezone.utc).isoformat(),
                          "pages": [item["data"] for item in pages]})
        paths.append(path.name)
        manifest["files"].append(file_record(path, run_dir))
        manifest["tabs"][key] = {"label": label, "status": "complete", "pages": len(pages), "files": paths}
        print(f"  Tab: {label} ({len(pages)} trang)", flush=True)

def capture_document(url: str, run_dir: Path, manifest: dict, channel: str, headed: bool, timeout_ms: int,
                     download_attachments: bool = False) -> None:
    from playwright.sync_api import sync_playwright

    pending = set()
    manifest.update({"attachments": [], "files": [],
                     "attachment_policy": "download" if download_attachments else "skip",
                     "expected_attachments": None})

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
                                          viewport={"width": 1440, "height": 1000}, accept_downloads=download_attachments)
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
            breadcrumb_urls = page.locator(".ant-breadcrumb a[href]").evaluate_all(
                "elements => elements.map(element => element.href)")
            manifest.update({"document_scope": classify_document_scope(breadcrumb_urls),
                             "classification": {"method": "source_breadcrumb",
                                                "breadcrumb_urls": breadcrumb_urls}})
            manifest.update({"title": page.title(), "source_url": url,
                             "full_text_characters": len(full_text.strip())})
            html_file = run_dir / "content.html"
            html_file.write_text(clean_content_html(preview.inner_html(), page.title(), url), encoding="utf-8")
            text_file = run_dir / "content.txt"
            text_file.write_text(full_text, encoding="utf-8")
            manifest["files"] = [file_record(html_file, run_dir), file_record(text_file, run_dir)]

            capture_metadata_tabs(page, run_dir, manifest, pending, timeout_ms)

            if download_attachments:
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
            manifest["validation"] = {
                "content_stable": True,
                "metadata_tabs_complete": True,
                "all_listed_attachments_downloaded": True if download_attachments else None,
            }
        finally:
            browser.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crawl một văn bản vbpl.vn: toàn văn, thuộc tính, lược đồ, lịch sử; mặc định không tải tệp đính kèm")
    parser.add_argument("--output", type=Path, default=Path("data/raw/vbpl"))
    parser.add_argument("--url", help="URL có trong sitemap (mặc định chọn văn bản đầu tiên)")
    parser.add_argument("--channel", default="chrome", help="chrome (đã cài) hoặc chromium (Playwright)")
    parser.add_argument("--download-attachments", action="store_true",
                        help="Tải thêm tệp đính kèm (mặc định bỏ qua để tiết kiệm dung lượng)")
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
        print(f"Văn bản duy nhất: {url}", flush=True)
        # Failed attempts leave no partial document folder. A previous successful
        # result remains intact until the replacement is fully downloaded.
        with tempfile.TemporaryDirectory(prefix=".crawl-", dir=args.output) as temporary:
            staged = Path(temporary) / "document"
            staged.mkdir()
            capture_document(url, staged, manifest, args.channel, args.headed, args.timeout * 1000,
                             args.download_attachments)
            scope = manifest.get("document_scope")
            if scope not in DOCUMENT_SCOPES.values():
                raise CrawlError("Kết quả crawl thiếu nhóm trung ương/địa phương hợp lệ")
            destination = args.output / scope / identifier
            destination.parent.mkdir(parents=True, exist_ok=True)
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
