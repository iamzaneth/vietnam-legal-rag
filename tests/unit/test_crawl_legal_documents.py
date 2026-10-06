import unittest
from pathlib import Path
import tempfile
import zipfile

from vietnam_legal_rag.ingestion.crawl_legal_documents import (
    CrawlError, is_document_url, parse_sitemap, safe_filename, validate_attachment,
)


class DiscoveryTests(unittest.TestCase):
    def test_sitemap_ignores_alternate_language_links(self):
        data = b'''<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
            xmlns:xhtml="http://www.w3.org/1999/xhtml"><url>
            <loc>https://vbpl.vn/van-ban/chi-tiet/example</loc>
            <xhtml:link href="https://vbpl.vn/en/van-ban/chi-tiet/example" />
            </url></urlset>'''
        self.assertEqual(parse_sitemap(data), ("urlset", ["https://vbpl.vn/van-ban/chi-tiet/example"]))

    def test_block_page_is_not_a_sitemap(self):
        for body in [b"<html><body>403 Forbidden</body></html>", b"Not XML"]:
            with self.subTest(body=body), self.assertRaises(CrawlError):
                parse_sitemap(body)

    def test_only_canonical_document_urls(self):
        self.assertTrue(is_document_url("https://vbpl.vn/van-ban/chi-tiet/example"))
        for url in ["https://example.org/van-ban/chi-tiet/example", "https://vbpl.vn/",
                    "https://vbpl.vn/en/van-ban/chi-tiet/example"]:
            self.assertFalse(is_document_url(url))

    def test_untrusted_download_names_stay_inside_output(self):
        self.assertEqual(safe_filename("../../example.pdf"), "example.pdf")
        self.assertEqual(safe_filename("..\\..\\example.pdf"), "example.pdf")
        self.assertEqual(safe_filename(".."), "attachment.bin")


class DocumentScopeTests(unittest.TestCase):
    def test_classifies_only_source_category_links(self):
        from vietnam_legal_rag.ingestion.crawl_legal_documents import classify_document_scope
        for path, scope in (("trung-uong", "trung_uong"), ("dia-phuong", "dia_phuong")):
            with self.subTest(scope=scope):
                self.assertEqual(classify_document_scope([
                    "https://vbpl.vn/", f"/van-ban/{path}",
                    f"https://vbpl.vn/van-ban/{path}/?page=1",
                    "https://vbpl.vn/van-ban/chi-tiet/mentions-trung-uong-dia-phuong",
                ]), scope)

    def test_missing_conflicting_or_foreign_categories_fail(self):
        from vietnam_legal_rag.ingestion.crawl_legal_documents import classify_document_scope
        for urls in ([], ["https://example.org/van-ban/trung-uong"],
                     ["/van-ban/trung-uong", "/van-ban/dia-phuong"],
                     ["/van-ban/chi-tiet/nghi-quyet-dia-phuong"]):
            with self.subTest(urls=urls), self.assertRaises(CrawlError):
                classify_document_scope(urls)

    def test_cli_routes_both_scopes_and_replaces_existing_document(self):
        import contextlib
        import io
        import json
        from unittest.mock import patch
        from vietnam_legal_rag.ingestion.crawl_legal_documents import main
        identifier = "0c389a00-78f6-11f1-a726-87c913cf8f30"
        url = "https://vbpl.vn/van-ban/chi-tiet/test--" + identifier
        for scope in ("trung_uong", "dia_phuong", None):
            with self.subTest(scope=scope), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                destination = root / (scope or "trung_uong") / identifier
                destination.mkdir(parents=True)
                (destination / "content.html").write_text("old")
                def capture(url, staged, manifest, *args):
                    manifest["document_scope"] = scope
                    (staged / "content.html").write_text("new")
                with patch("vietnam_legal_rag.ingestion.crawl_legal_documents.discover_one",
                           return_value=(url, {})), \
                     patch("vietnam_legal_rag.ingestion.crawl_legal_documents.capture_document",
                           side_effect=capture), \
                     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(["--output", tmp]), 0 if scope else 1)
                self.assertEqual((destination / "content.html").read_text(), "new" if scope else "old")
                self.assertFalse(list(root.glob(".crawl-*")))
                self.assertFalse((root / identifier).exists())
                if scope:
                    self.assertEqual(json.loads((destination / "manifest.json").read_text())
                                     ["document_scope"], scope)


class AttachmentTests(unittest.TestCase):
    def test_rejects_error_page_disguised_as_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attachment.pdf"
            path.write_bytes(b"<!doctype html><html>403 Forbidden</html>")
            with self.assertRaises(CrawlError):
                validate_attachment(path)

    def test_rejects_truncated_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attachment.pdf"
            path.write_bytes(b"%PDF-1.7 truncated transfer")
            with self.assertRaises(CrawlError):
                validate_attachment(path)

    def test_docx_requires_actual_word_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attachment.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("unrelated.txt", "Not a Word document")
            with self.assertRaises(CrawlError):
                validate_attachment(path)
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", "<document/>")
            validate_attachment(path)


class CapturePolicyTests(unittest.TestCase):
    def test_capture_saves_only_source_html_without_downloads(self):
        from unittest.mock import MagicMock, patch
        from vietnam_legal_rag.ingestion.crawl_legal_documents import capture_document
        page = MagicMock()
        preview = MagicMock()
        panel = MagicMock()
        page.locator.side_effect = lambda selector: (
            MagicMock(first=preview) if selector == ".preview-content" else panel)
        panel.evaluate_all.return_value = ["https://vbpl.vn/van-ban/trung-uong"]
        preview.inner_text.return_value = "Nội dung văn bản. " * 30
        preview.inner_html.return_value = "<p>" + preview.inner_text.return_value + "</p>"
        page.get_by_role.return_value.evaluate.return_value = [
            {"label": label, "source_id": None}
            for label in ("Nội dung", "Thuộc tính", "Lược đồ", "Lịch sử", "Tải về", "Văn bản gốc")
        ]
        page.title.return_value = "Văn bản thử nghiệm"
        page.get_by_role.return_value.filter.return_value.count.return_value = 0
        panel.inner_html.return_value = "<p>Dữ liệu tab</p>"
        panel.evaluate.return_value = {
            "fields": [{"label": "Số hiệu", "value": "01/2026"}],
            "groups": [{"label": "Căn cứ ban hành (1)", "items": [{"title": "Luật mẫu", "url": None}]}],
            "rows": [{"cells": ["01/01/2026", "Ban hành", "Văn bản mẫu"]}], "empty": False,
        }
        panel.locator.side_effect = lambda selector: MagicMock(
            count=MagicMock(return_value=1 if selector == "button" else 0))
        browser = MagicMock()
        browser.new_context.return_value.new_page.return_value = page
        manifest = {}
        with tempfile.TemporaryDirectory() as tmp, \
             patch("playwright.sync_api.sync_playwright") as factory, \
             patch("vietnam_legal_rag.ingestion.crawl_legal_documents.wait_for_panel", return_value="Tệp"):
            factory.return_value.__enter__.return_value.chromium.launch.return_value = browser
            capture_document("https://vbpl.vn/van-ban/chi-tiet/test", Path(tmp), manifest,
                             "chrome", False, 1000)
            self.assertTrue((Path(tmp) / "content.html").exists())
            self.assertFalse((Path(tmp) / "content.txt").exists())
            for key in ("properties", "relations", "history"):
                self.assertTrue((Path(tmp) / f"{key}.html").is_file())
                for suffix in ("txt", "json"):
                    self.assertFalse((Path(tmp) / f"{key}.{suffix}").exists())
                self.assertEqual(manifest["tabs"][key]["status"], "complete")
            self.assertEqual(len(manifest["files"]), 4)
            self.assertFalse((Path(tmp) / "attachments").exists())
            self.assertFalse(browser.new_context.call_args.kwargs["accept_downloads"])
            download_tabs = [call for call in page.get_by_role.call_args_list
                             if call.kwargs.get("name") == "Tải về"]
            self.assertEqual(len(download_tabs), 0)
            self.assertEqual(manifest["attachment_policy"], "skip")
            self.assertEqual(len(manifest["attachments"]), 0)
            self.assertIsNone(manifest["expected_attachments"])
            self.assertIs(manifest["validation"]["all_listed_attachments_downloaded"],
                          None)
            browser.close.assert_called_once()
            page.expect_download.assert_not_called()



class MetadataTabTests(unittest.TestCase):
    def test_discovers_present_tabs_with_safe_stable_keys(self):
        from unittest.mock import MagicMock
        from vietnam_legal_rag.ingestion.crawl_legal_documents import discover_document_tabs
        page = MagicMock()
        page.get_by_role.return_value.evaluate.return_value = [
            {"label": label, "source_id": f"tab-{i}"} for i, label in enumerate((
                "Nội dung", "Các văn bản hợp nhất", "Một tab mới", "Tải về", "Văn bản gốc",
            ))
        ]
        records = discover_document_tabs(page)
        self.assertEqual([r["key"] for r in records[:3]], ["content", "consolidated", "tab_mot_tab_moi"])
        self.assertEqual(records[1]["source_id"], "tab-1")

    def test_captures_all_present_tabs_except_downloads_and_original(self):
        from unittest.mock import MagicMock, patch
        from vietnam_legal_rag.ingestion.crawl_legal_documents import capture_metadata_tabs
        page = MagicMock()
        page.get_by_role.return_value.evaluate.return_value = [
            {"label": label, "source_id": None} for label in (
                "Nội dung", "Các văn bản hợp nhất", "Thông tin bổ sung", "  TẢI VỀ  ", "Văn bản gốc (2)",
            )
        ]
        panel = page.locator.return_value
        panel.evaluate.return_value = {"fields": [], "groups": [], "rows": [], "links": [], "empty": False}
        panel.inner_html.return_value = '<ul><li><a href="/van-ban/chi-tiet/other">VBHN mẫu</a></li></ul>'
        panel.locator.return_value.count.return_value = 0
        manifest = {"files": [], "title": "Test", "source_url": "https://vbpl.vn/test"}
        with tempfile.TemporaryDirectory() as tmp, patch(
                "vietnam_legal_rag.ingestion.crawl_legal_documents.wait_for_panel", return_value="VBHN mẫu"):
            capture_metadata_tabs(page, Path(tmp), manifest, set(), 1000)
            self.assertEqual({p.name for p in Path(tmp).iterdir()},
                             {"consolidated.html", "tab_thong_tin_bo_sung.html"})
            self.assertEqual(set(manifest["tabs"]), {"content", "consolidated", "tab_thong_tin_bo_sung"})
            self.assertEqual(len(manifest["excluded_tabs"]), 2)
            opened = [call.kwargs["name"] for call in page.get_by_role.call_args_list[1:]]
            self.assertEqual(opened, ["Các văn bản hợp nhất", "Thông tin bổ sung"])

    def test_duplicate_tab_keys_fail_instead_of_overwriting_html(self):
        from unittest.mock import MagicMock
        from vietnam_legal_rag.ingestion.crawl_legal_documents import discover_document_tabs
        page = MagicMock()
        page.get_by_role.return_value.evaluate.return_value = [
            {"label": label} for label in ("Nội dung", "Một tab", "MỘT TAB")
        ]
        with self.assertRaises(CrawlError):
            discover_document_tabs(page)

    def test_rejects_partial_relations(self):
        from vietnam_legal_rag.ingestion.crawl_legal_documents import validate_tab_data
        with self.assertRaises(CrawlError):
            validate_tab_data("relations", {"empty": False, "groups": [
                {"label": "Căn cứ ban hành (2)", "items": [{"title": "Một văn bản"}]}]})

    def test_accepts_explicit_empty_but_rejects_unloaded_tabs(self):
        from vietnam_legal_rag.ingestion.crawl_legal_documents import validate_tab_data
        for key in ("relations", "history"):
            data = {"groups": [], "rows": [], "empty": True}
            validate_tab_data(key, data)
            data["empty"] = False
            with self.assertRaises(CrawlError):
                validate_tab_data(key, data)
        with self.assertRaises(CrawlError):
            validate_tab_data("properties", {"fields": []})

    def test_history_pagination_keeps_every_page(self):
        import json
        from unittest.mock import MagicMock, patch
        from vietnam_legal_rag.ingestion.crawl_legal_documents import capture_metadata_tabs
        page = MagicMock()
        panel = page.locator.return_value
        panel.inner_html.side_effect = ["<p>First event</p>", "<p>Second event</p>"]
        panel.inner_text.side_effect = ["First event", "Second event"]
        panel.evaluate.side_effect = [
            {"rows": [{"cells": ["First event"]}], "empty": False},
            {"rows": [{"cells": ["Second event"]}], "empty": False},
        ]
        panel.locator.return_value.count.side_effect = [1, 0]
        manifest = {"files": [], "title": "Test", "source_url": "https://vbpl.vn/test"}
        with tempfile.TemporaryDirectory() as tmp, \
             patch("vietnam_legal_rag.ingestion.crawl_legal_documents.discover_document_tabs", return_value=[
                 {"key": "history", "label": "Lịch sử", "source_id": None}]), \
             patch("vietnam_legal_rag.ingestion.crawl_legal_documents.wait_for_panel",
                   side_effect=["First event", "Second event"]):
            capture_metadata_tabs(page, Path(tmp), manifest, set(), 1000)
            html = (Path(tmp) / "history.html").read_text()
            self.assertIn('data-page="1"', html)
            self.assertIn('data-page="2"', html)
            self.assertIn("First event", html)
            self.assertIn("Second event", html)
            self.assertFalse((Path(tmp) / "history.json").exists())
            self.assertEqual(manifest["tabs"]["history"]["pages"], 2)
            panel.locator.return_value.click.assert_called_once()

    def test_zero_relations_is_complete(self):
        from vietnam_legal_rag.ingestion.crawl_legal_documents import validate_tab_data
        validate_tab_data("relations", {"groups": [{"label": "Văn bản thay thế (0)", "items": []}],
                                        "empty": False})


class TabURLTests(unittest.TestCase):
    def test_requested_tab_url_matches_canonical_sitemap_entry(self):
        from unittest.mock import patch
        from vietnam_legal_rag.ingestion.crawl_legal_documents import discover_one
        url = "https://vbpl.vn/van-ban/chi-tiet/example--13205"
        with patch("vietnam_legal_rag.ingestion.crawl_legal_documents.fetch_public", side_effect=[
                b"User-agent: *\nAllow: /\n", f'<urlset><url><loc>{url}</loc></url></urlset>'.encode()]):
            self.assertEqual(discover_one(url + "?tabs=hop-nhat")[0], url)

    def test_numeric_source_id_is_used_for_output(self):
        import contextlib
        import io
        from unittest.mock import patch
        from vietnam_legal_rag.ingestion.crawl_legal_documents import main
        url = "https://vbpl.vn/van-ban/chi-tiet/example--13205?tabs=hop-nhat"
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()), \
             patch("vietnam_legal_rag.ingestion.crawl_legal_documents.discover_one", return_value=(url, {})), \
             patch("vietnam_legal_rag.ingestion.crawl_legal_documents.capture_document",
                   side_effect=lambda url, staged, manifest, *args: manifest.update(document_scope="trung_uong")):
            self.assertEqual(main(["--url", url, "--output", tmp]), 0)
            self.assertTrue((Path(tmp) / "trung_uong" / "13205" / "manifest.json").is_file())


class CleanContentTests(unittest.TestCase):
    def test_removes_presentation_and_scripts_but_keeps_legal_structure(self):
        from vietnam_legal_rag.ingestion.crawl_legal_documents import clean_content_html
        source = '''<style>body{display:none}</style><script>location.reload()</script>
        <div class="hidden" style="display:none" onclick="alert(1)">
          <h2>Điều 1. Phạm vi</h2><p>Nội dung <span style="color:white">tiếng Việt</span>.</p>
          <table width="900"><tr><td colspan="2" style="color:red">Phụ lục</td></tr></table>
          <ol start="3"><li value="4">Khoản 4</li></ol><sup>1</sup>
          <iframe src="https://example.org">unwanted</iframe>
          <img src="https://example.org/tracker.png"><link rel="stylesheet" href="a.css">
        </div>'''
        result = clean_content_html(source, "Văn bản <mẫu>")
        for forbidden in ('<style', '<script', 'style=', 'class=', 'onclick=', '<iframe', '<img', '<link', 'unwanted'):
            self.assertNotIn(forbidden, result)
        self.assertIn('<h2>Điều 1. Phạm vi</h2>', result)
        self.assertIn('Nội dung tiếng Việt.', result)
        self.assertIn('<td colspan="2">Phụ lục</td>', result)
        self.assertIn('<ol start="3"><li value="4">Khoản 4</li></ol>', result)
        self.assertIn('Văn bản &lt;mẫu&gt;', result)

    def test_preserves_reference_links_without_allowing_executable_urls(self):
        from vietnam_legal_rag.ingestion.crawl_legal_documents import clean_content_html
        source = '<p><a class="ref" href="/van-ban/chi-tiet/123?a=1&amp;b=2">Luật 123</a>' \
                 '<a href="javascript:alert(1)" onclick="alert(2)">Nội dung</a></p>'
        result = clean_content_html(source, 'Văn bản')
        self.assertIn('href="https://vbpl.vn/van-ban/chi-tiet/123?a=1&amp;b=2"', result)
        self.assertIn('>Luật 123</a>', result)
        self.assertIn('<a>Nội dung</a>', result)
        self.assertNotIn('javascript:', result)
        self.assertNotIn('onclick=', result)

    def test_escapes_text_without_turning_it_into_markup(self):
        from vietnam_legal_rag.ingestion.crawl_legal_documents import clean_content_html
        result = clean_content_html('<p>A &amp; B; 1 &lt; 2; &lt;script&gt;</p>', 'Tiêu đề')
        self.assertIn('<p>A &amp; B; 1 &lt; 2; &lt;script&gt;</p>', result)
        self.assertNotIn('<script>', result)

    def test_plain_text_preserves_paragraphs_and_vietnamese(self):
        from vietnam_legal_rag.ingestion.crawl_legal_documents import clean_content_text
        self.assertEqual(clean_content_text('  Điều 1.\n\n\xa0\n\nNội dung.  \n'), 'Điều 1.\n\nNội dung.\n')


class OutputLifecycleTests(unittest.TestCase):
    def test_success_replaces_previous_document_instead_of_creating_another_run(self):
        from vietnam_legal_rag.ingestion.crawl_legal_documents import publish_capture
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / 'document-id'
            destination.mkdir()
            (destination / 'content.html').write_text('old')
            with tempfile.TemporaryDirectory(dir=root, prefix='.crawl-') as work:
                staged = Path(work) / 'document'
                staged.mkdir()
                (staged / 'content.html').write_text('new')
                publish_capture(staged, destination)
            self.assertEqual((destination / 'content.html').read_text(), 'new')
            self.assertEqual(list(root.iterdir()), [destination])

    def test_failed_capture_cleans_staging_and_preserves_previous_result(self):
        import contextlib
        import io
        from unittest.mock import patch
        from vietnam_legal_rag.ingestion.crawl_legal_documents import main
        identifier = '0c389a00-78f6-11f1-a726-87c913cf8f30'
        url = 'https://vbpl.vn/van-ban/chi-tiet/sample--' + identifier
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / 'trung_uong' / identifier
            destination.mkdir(parents=True)
            (destination / 'content.html').write_text('existing result')
            def fail_capture(url, staged, *args):
                (staged / 'content.html').write_text('incomplete')
                raise CrawlError('download failed')
            with patch('vietnam_legal_rag.ingestion.crawl_legal_documents.discover_one', return_value=(url, {})), \
                 patch('vietnam_legal_rag.ingestion.crawl_legal_documents.capture_document', side_effect=fail_capture), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--output', str(root)]), 1)
            self.assertEqual((destination / 'content.html').read_text(), 'existing result')
            self.assertEqual(list(root.iterdir()), [root / 'trung_uong'])

    def test_failed_publish_restores_previous_result(self):
        from unittest.mock import patch
        from vietnam_legal_rag.ingestion.crawl_legal_documents import publish_capture
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / 'document-id'
            destination.mkdir()
            (destination / 'content.html').write_text('old')
            work = root / '.crawl-test'
            work.mkdir()
            staged = work / 'document'
            staged.mkdir()
            original_rename = Path.rename
            def fail_staged_rename(path, target):
                if path == staged:
                    raise OSError('simulated filesystem failure')
                return original_rename(path, target)
            with patch.object(Path, 'rename', fail_staged_rename), self.assertRaises(OSError):
                publish_capture(staged, destination)
            self.assertEqual((destination / 'content.html').read_text(), 'old')


if __name__ == "__main__":
    unittest.main()
