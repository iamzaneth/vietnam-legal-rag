"""Shared synthetic parser fixtures and repository paths; no test cases."""
from pathlib import Path

from vietnam_legal_rag.ingestion.crawl_legal_documents import file_record, source_content_html, write_json
from vietnam_legal_rag.ingestion.extract_legal_documents import parse_source
from vietnam_legal_rag.ingestion.validation.extract import walk_content

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://vbpl.vn/van-ban/chi-tiet/doc--99'
SOURCE = {"layer": "raw", "path": "content.html", "sha256": "a" * 64}


def parse_forms(html):
    return parse_source(html, "content", "Toàn văn", "https://vbpl.vn/doc--1", "vbpl:1", SOURCE)


def parse_tab(html, key="content"):
    return parse_source(html, key, key, "https://vbpl.vn/doc--1", "vbpl:1", SOURCE)


def metadata_tab(html, key):
    return parse_source(html, key, key, "https://vbpl.vn/van-ban/chi-tiet/doc--99", "vbpl:99", SOURCE)


def nodes(result, kind):
    return [n for n in walk_content([result["document"]]) if n["type"] == kind]


def create_raw(root,scope='trung_uong',name='doc-id'):
    raw = root/'raw'/'vbpl'/scope/name; raw.mkdir(parents=True)
    fragments = {
        'content':'<p>Điều 1. Phạm vi</p><p>A &amp; B, 1 &lt; 2.</p><script>ignored()</script>',
        'properties':'<section data-page="1"><table><tr><td>Số hiệu 01/2026/QH15</td></tr></table></section>',
        'relations':'<section data-page="1"><div class="ant-card-body"><span>Căn cứ ban hành (1)</span><ul>'
                    '<li><a href="/van-ban/chi-tiet/law--12">Luật 64/2025/QH15</a></li></ul></div></section>',
        'history':''.join(f'<section data-page="{i}"><table><thead><tr><th>Thời gian</th><th>Trạng thái</th><th>Văn bản nguồn</th></tr></thead>'
                         f'<tbody><tr data-row-key="event-{i}"><td>0{i}/01/2026</td><td>Có hiệu lực</td><td>Quyết định 01/QĐ-BCT</td></tr></tbody></table></section>' for i in (1,2)),
    }
    for key,html in fragments.items():
        (raw/f'{key}.html').write_text(source_content_html(html,'Title'))
    write_json(raw/'manifest.json',{'document_id':'vbpl:'+name,'source_url':URL,'document_scope':scope,
               'retrieved_at':'2026-10-04','files':[file_record(raw/f'{key}.html',raw) for key in fragments],
               'tabs':{'history':{'pages':2}}})
    return raw
