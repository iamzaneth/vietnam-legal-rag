import unittest
from pathlib import Path
import tempfile
import zipfile

from vietnam_legal_rag.ingestion.vbpl import (
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


class CleanContentTests(unittest.TestCase):
    def test_removes_presentation_and_scripts_but_keeps_legal_structure(self):
        from vietnam_legal_rag.ingestion.vbpl import clean_content_html
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
        from vietnam_legal_rag.ingestion.vbpl import clean_content_html
        source = '<p><a class="ref" href="/van-ban/chi-tiet/123?a=1&amp;b=2">Luật 123</a>' \
                 '<a href="javascript:alert(1)" onclick="alert(2)">Nội dung</a></p>'
        result = clean_content_html(source, 'Văn bản')
        self.assertIn('href="https://vbpl.vn/van-ban/chi-tiet/123?a=1&amp;b=2"', result)
        self.assertIn('>Luật 123</a>', result)
        self.assertIn('<a>Nội dung</a>', result)
        self.assertNotIn('javascript:', result)
        self.assertNotIn('onclick=', result)

    def test_escapes_text_without_turning_it_into_markup(self):
        from vietnam_legal_rag.ingestion.vbpl import clean_content_html
        result = clean_content_html('<p>A &amp; B; 1 &lt; 2; &lt;script&gt;</p>', 'Tiêu đề')
        self.assertIn('<p>A &amp; B; 1 &lt; 2; &lt;script&gt;</p>', result)
        self.assertNotIn('<script>', result)

    def test_plain_text_preserves_paragraphs_and_vietnamese(self):
        from vietnam_legal_rag.ingestion.vbpl import clean_content_text
        self.assertEqual(clean_content_text('  Điều 1.\n\n\xa0\n\nNội dung.  \n'), 'Điều 1.\n\nNội dung.\n')


class OutputLifecycleTests(unittest.TestCase):
    def test_success_replaces_previous_document_instead_of_creating_another_run(self):
        from vietnam_legal_rag.ingestion.vbpl import publish_capture
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / 'document-id'
            destination.mkdir()
            (destination / 'content.txt').write_text('old')
            with tempfile.TemporaryDirectory(dir=root, prefix='.crawl-') as work:
                staged = Path(work) / 'document'
                staged.mkdir()
                (staged / 'content.txt').write_text('new')
                publish_capture(staged, destination)
            self.assertEqual((destination / 'content.txt').read_text(), 'new')
            self.assertEqual(list(root.iterdir()), [destination])

    def test_failed_capture_cleans_staging_and_preserves_previous_result(self):
        import contextlib
        import io
        from unittest.mock import patch
        from vietnam_legal_rag.ingestion.vbpl import main
        identifier = '0c389a00-78f6-11f1-a726-87c913cf8f30'
        url = 'https://vbpl.vn/van-ban/chi-tiet/sample--' + identifier
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / identifier
            destination.mkdir()
            (destination / 'content.txt').write_text('existing result')
            def fail_capture(url, staged, *args):
                (staged / 'content.txt').write_text('incomplete')
                raise CrawlError('download failed')
            with patch('vietnam_legal_rag.ingestion.vbpl.discover_one', return_value=(url, {})), \
                 patch('vietnam_legal_rag.ingestion.vbpl.capture_document', side_effect=fail_capture), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--output', str(root)]), 1)
            self.assertEqual((destination / 'content.txt').read_text(), 'existing result')
            self.assertEqual(list(root.iterdir()), [destination])

    def test_failed_publish_restores_previous_result(self):
        from unittest.mock import patch
        from vietnam_legal_rag.ingestion.vbpl import publish_capture
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / 'document-id'
            destination.mkdir()
            (destination / 'content.txt').write_text('old')
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
            self.assertEqual((destination / 'content.txt').read_text(), 'old')


if __name__ == "__main__":
    unittest.main()
