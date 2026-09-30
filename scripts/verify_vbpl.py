"""Compare saved content with the live DOM and re-download every attachment."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from vietnam_legal_rag.ingestion.vbpl import (
    USER_AGENT, clean_content_html, clean_content_text, file_record,
    validate_attachment, wait_for_panel, write_json,
)

# This comparison is independent of the HTML sanitizer. It reads ordered text,
# paragraphs, table cells, list numbering, and links from the browser's DOM.
SIGNATURE = r'''(element, base) => {
    const e = element.cloneNode(true);
    e.querySelectorAll('script,style,meta,link,template,noscript').forEach(n => n.remove());
    const text = n => (n.textContent || '').normalize('NFC').replace(/\s+/gu, ' ').trim();
    return {
        text: text(e),
        blocks: [...e.querySelectorAll('p,h1,h2,h3,h4,h5,h6,li,dt,dd,blockquote,pre,caption')]
            .map(n => [n.tagName, text(n)]),
        tables: [...e.querySelectorAll('table')].map(t => [...t.rows].map(r =>
            [...r.cells].map(c => [c.tagName, c.rowSpan, c.colSpan, text(c)]))),
        lists: [...e.querySelectorAll('ol,ul,li')]
            .map(n => [n.tagName, n.getAttribute('start'), n.getAttribute('value')]),
        inline: [...e.querySelectorAll('sup,sub,br,hr')].map(n => [n.tagName, text(n)]),
        links: [...e.querySelectorAll('a[href]')].map(n =>
            [text(n), new URL(n.getAttribute('href'), base).href]),
        unsupported: [...e.querySelectorAll('img,svg,canvas,iframe,object,math,video,audio')]
            .map(n => n.tagName)
    };
}'''


def digest(value) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def verify(folder: Path, browser, local_page, repair_links: bool) -> dict:
    path = folder / 'manifest.json'
    manifest = json.loads(path.read_text())
    assert manifest['status'] == 'complete', 'Capture is not complete'
    url = manifest['source_url']
    for record in manifest['files'] + manifest['attachments']:
        data = (folder / record['path']).read_bytes()
        assert len(data) == record['bytes'], record['path']
        assert hashlib.sha256(data).hexdigest() == record['sha256'], record['path']
    print('VERIFY:', manifest['title'].split(' | ')[0], flush=True)
    context = browser.new_context(user_agent=USER_AGENT, locale='vi-VN', accept_downloads=True)
    page = context.new_page()
    page.set_default_timeout(90000)
    pending = set()
    def requested(request):
        host = urlparse(request.url).hostname or ''
        if (host == 'vbpl.vn' or host.endswith('.moj.gov.vn')) and request.resource_type in {'xhr', 'fetch'}:
            pending.add(request)
    def finished(request):
        pending.discard(request)
    page.on('request', requested)
    page.on('requestfinished', finished)
    page.on('requestfailed', finished)
    try:
        response = page.goto(url, wait_until='domcontentloaded')
        assert response and response.ok, f'HTTP {response.status if response else None}'
        preview = page.locator('.preview-content').first
        preview.wait_for()
        panel = page.locator('[role=tabpanel]:visible')
        wait_for_panel(page, panel, pending, 90000)
        reject = page.get_by_role('button', name='Từ chối', exact=True).filter(visible=True)
        if reject.count():
            reject.last.click()
        before = preview.evaluate(SIGNATURE, url)
        # Visit the full height instead of checking only the first viewport.
        preview.evaluate('''async e => {
            const parts = [...e.querySelectorAll('p,tr')];
            for (let i=0; i<parts.length; i+=20) {
                parts[i].scrollIntoView({block:'end'});
                await new Promise(resolve => setTimeout(resolve, 30));
            }
            e.scrollIntoView({block:'end'});
        }''')
        wait_for_panel(page, panel, pending, 90000)
        live = preview.evaluate(SIGNATURE, url)
        assert before == live, 'Content changed while scrolling; re-crawl required'
        assert not live['unsupported'], f'Uncaptured content types: {live["unsupported"]}'
        source_fragment = preview.inner_html()
        source_text = clean_content_text(preview.inner_text())
        assert source_text == (folder / 'content.txt').read_text(), 'Saved TXT differs from current source'
        local_page.goto((folder / 'content.html').resolve().as_uri())
        saved = local_page.locator('body').evaluate(SIGNATURE, url)
        different = [key for key in live if live[key] != saved[key]]
        repaired_links = 0
        replacement = None
        if different:
            assert repair_links and different == ['links'], f'Source mismatches: {different}'
            replacement = clean_content_html(source_fragment, manifest['title'], url)
            local_page.set_content(replacement)
            saved = local_page.locator('body').evaluate(SIGNATURE, url)
            assert saved == live, 'Repaired HTML still differs from source'
            repaired_links = len(live['links'])
        assert local_page.locator('style,script,link,[style],[class],iframe').count() == 0

        page.get_by_role('tab', name='Tải về', exact=True).click()
        panel = page.locator('[role=tabpanel]:visible')
        wait_for_panel(page, panel, pending, 90000)
        buttons = panel.locator('button')
        assert buttons.count() == len(manifest['attachments']), 'Attachment list has changed'
        expected = [(a['original_filename'], a['bytes'], a['sha256']) for a in manifest['attachments']]
        received = []
        with tempfile.TemporaryDirectory(prefix='vbpl-verify-') as temporary:
            for i in range(buttons.count()):
                with page.expect_download(timeout=90000) as event:
                    buttons.nth(i).click()
                download = event.value
                suffix = Path(download.suggested_filename).suffix
                target = Path(temporary) / f'{i}{suffix}'
                download.save_as(target)
                assert download.failure() is None, download.failure()
                validate_attachment(target)
                data = target.read_bytes()
                received.append((download.suggested_filename, len(data), hashlib.sha256(data).hexdigest()))
                print('  Download verified:', download.suggested_filename, flush=True)
        assert sorted(expected) == sorted(received), 'Attachment bytes differ from live download'
        page.get_by_role('tab', name='Nội dung', exact=True).click()
        wait_for_panel(page, page.locator('[role=tabpanel]:visible'), pending, 90000)
        assert preview.evaluate(SIGNATURE, url) == live, 'Content changed during verification'

        result = {
            'document_id': manifest['document_id'], 'title': manifest['title'].split(' | ')[0],
            'source_url': url, 'verified_at': datetime.now(timezone.utc).isoformat(),
            'status': 'passed', 'source_and_saved_signature_sha256': digest(live),
            'canonical_text_characters': len(live['text']), 'blocks': len(live['blocks']),
            'tables': len(live['tables']),
            'table_cells': sum(len(row) for table in live['tables'] for row in table),
            'reference_links': len(live['links']), 'reference_links_restored': repaired_links,
            'attachments_redownloaded_identical': len(received),
            'checks': {'text_exact_after_whitespace_normalization': True,
                       'saved_txt_exact_to_cleaned_live_inner_text': True,
                       'ordered_blocks_tables_lists_inline_and_links_exact': True,
                       'stable_before_after_scrolling_and_downloads': True,
                       'no_missing_embedded_images_or_other_media': True,
                       'no_css_or_javascript_in_saved_html': True,
                       'local_file_hashes_valid': True},
        }
        if replacement is not None:
            (folder / 'content.html').write_text(replacement, encoding='utf-8')
            manifest['files'] = [file_record(folder / f['path'], folder) for f in manifest['files']]
            manifest['content_updated_at'] = result['verified_at']
        manifest['verification'] = result
        write_json(path, manifest)
        print('  PASSED:', result['blocks'], 'blocks,', result['tables'], 'tables,', result['reference_links'], 'links', flush=True)
        return result
    finally:
        context.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('data/raw/vbpl'))
    parser.add_argument('--report', type=Path, default=Path('evaluation/results/vbpl-verification.json'))
    parser.add_argument('--repair-links', action='store_true', help='Restore missing reference links only if all text and tables already match')
    args = parser.parse_args()
    folders = sorted(p.parent for p in args.root.glob('*/manifest.json'))
    if not folders:
        parser.error('No documents found')
    report = {'scope': 'Clean full-text HTML in the Noi dung tab; excludes source CSS/JS and site navigation. Not byte-identical raw website HTML.',
              'started_at': datetime.now(timezone.utc).isoformat(), 'documents': []}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        local_context = browser.new_context(offline=True)
        local_page = local_context.new_page()
        for folder in folders:
            try:
                report['documents'].append(verify(folder, browser, local_page, args.repair_links))
            except Exception as exc:
                print('FAILED:', folder.name, str(exc), flush=True)
                report['documents'].append({'folder': folder.name, 'status': 'failed', 'error': str(exc)})
        browser.close()
    report['completed_at'] = datetime.now(timezone.utc).isoformat()
    report['passed'] = sum(d['status'] == 'passed' for d in report['documents'])
    report['failed'] = len(folders) - report['passed']
    args.report.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.report, report)
    print(f'Report: {args.report}; passed={report["passed"]}, failed={report["failed"]}', flush=True)
    return 1 if report['failed'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
