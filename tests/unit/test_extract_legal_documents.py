"""End-to-end offline extraction, direct metadata values and validation."""
import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest

from vietnam_legal_rag.ingestion.crawl_legal_documents import CrawlError, file_record, source_content_html, write_json
from vietnam_legal_rag.ingestion.extract_legal_documents import extract_document, main, parse_source
from vietnam_legal_rag.ingestion.extract_quality import Quality
from vietnam_legal_rag.ingestion.extract_validation import schema_validator, validate_result
from vietnam_legal_rag.ingestion.html_source import parse_html

URL = 'https://vbpl.vn/van-ban/chi-tiet/doc--99'
SOURCE = {'layer':'raw','path':'content.html','sha256':'a'*64}


def tab(html,key):
    return parse_source(html,key,key,URL,'vbpl:99',SOURCE)


class MetadataTests(unittest.TestCase):
    def test_properties_duplicate_labels_unknown_fields_and_dates_stay_raw(self):
        html = '<div class="ant-descriptions-item-container"><span class="ant-descriptions-item-label">Số hiệu</span><span class="ant-descriptions-item-content">16111/QĐ-BCT</span></div>'
        html += html + '<div class="ant-descriptions-item-container"><span class="ant-descriptions-item-label">Ngày ban hành</span><span class="ant-descriptions-item-content">01/07/2026</span></div>'
        result = tab(html,'properties')
        self.assertEqual([f['label'] for f in result['fields']],['Số hiệu','Số hiệu','Ngày ban hành'])
        self.assertEqual(result['fields'][2]['value'],'01/07/2026')
        self.assertNotIn('context', result)
        self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_legacy_and_unknown_properties_are_kept_without_canonicalization(self):
        result = tab('<h2>Thuộc tính — 1</h2><table><tr><td>Số hiệu 01/2026/QH15</td><td>Nhãn mới giá trị 10%</td></tr></table>','properties')
        self.assertEqual(result['fields'][0]['label'],'Số hiệu')
        self.assertEqual(result['fields'][1]['label'],None)
        self.assertEqual(result['fields'][1]['value'],'Nhãn mới giá trị 10%')
        self.assertTrue(result['validation']['meaningful_text_preserved'])
        self.assertFalse(result.get('context'))

    def test_unknown_field_markup_preserves_extra_semantic_text(self):
        result = tab('<div class="ant-descriptions-item-container"><span class="ant-descriptions-item-label">Số hiệu</span>'
                     ': <span class="ant-descriptions-item-content">01/QĐ-BCT</span> bổ sung</div>','properties')
        self.assertIsNone(result['fields'][0]['label'])
        self.assertIn('bổ sung',result['fields'][0]['value'])
        self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_history_direct_values_follow_source_headers_even_when_columns_reordered(self):
        result = tab('<table><thead><tr><th>Văn bản nguồn</th><th>Trạng thái</th><th>Thời gian</th><th>Ghi chú nguồn</th></tr></thead><tbody>'
                     '<tr><td><a href="/van-ban/chi-tiet/q--12">Quyết định 16111/QĐ-BCT sửa Thông tư 11/2026/TT-BCT</a></td>'
                     '<td>Văn bản có hiệu lực</td><td>01/07/2026</td><td>Không sửa chính tả</td></tr></tbody></table>','history')
        event = result['events'][0]
        self.assertEqual(event['date'],'01/07/2026')
        self.assertEqual(event['status'],'Văn bản có hiệu lực')
        self.assertEqual(event['source_document']['mentioned_document_numbers'],['16111/QĐ-BCT','11/2026/TT-BCT'])
        self.assertEqual(event['source_document']['url'],'https://vbpl.vn/van-ban/chi-tiet/q--12')
        self.assertEqual(event['other_values'][0]['value'],'Không sửa chính tả')
        self.assertNotIn('identifier',event)
        self.assertTrue(result['validation']['meaningful_text_preserved'])
        self.assertFalse(result.get('context'))

    def test_ambiguous_history_keeps_a_table_instead_of_flat_text_or_guessed_events(self):
        result = tab('<table><thead><tr><th>Thời gian</th><th>Trạng thái</th></tr></thead><tbody>'
                     '<tr><td rowspan="2">01/01/2026</td><td>Hiệu lực</td></tr><tr><td>Bãi bỏ</td></tr></tbody></table>','history')
        self.assertEqual(result['events'],[])
        self.assertEqual(result['context'][0]['type'],'table')
        self.assertEqual(result['context'][0]['cells'][2]['rowspan'],2)
        self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_zero_relation_count_discards_placeholder_and_preserves_raw_label(self):
        result = tab('<div>Văn bản hợp nhất (0)<ul><li><a>--</a></li></ul></div>','relations')
        group = result['groups'][0]
        self.assertEqual(group['label_raw'],'Văn bản hợp nhất (0)')
        self.assertEqual(group['relation_type_raw'],'Văn bản hợp nhất')
        self.assertEqual(group['declared_count'],0)
        self.assertEqual(group['items'],[])
        self.assertTrue(result['validation']['meaningful_text_preserved'])
        self.assertEqual(result['status'],'success')
        self.assertEqual(result['ignored_elements'][0]['reason'],'empty_relation_placeholder')

    def test_zero_relation_without_placeholder_is_still_a_group(self):
        result = tab('<div>Căn cứ ban hành (0)</div>','relations')
        self.assertEqual(result['groups'][0]['items'],[])
        self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_relation_candidates_are_all_kept_and_not_resolved(self):
        result = tab('<div class="ant-card-body"><span>Căn cứ ban hành (1)</span><ul><li>'
                     'Luật số 64/2025/QH15 sửa Luật số 87/2025/QH15</li></ul></div>','relations')
        item = result['groups'][0]['items'][0]
        self.assertEqual(item['primary_document_number_candidate'], '64/2025/QH15')
        self.assertEqual(item['mentioned_document_numbers'], ['87/2025/QH15'])
        self.assertEqual(item['resolution_status'], 'candidate_only')
        self.assertNotIn('document_number_candidates', item)
        self.assertIsNone(item['resolved_document_id'])
        self.assertIsNone(item['url'])
        self.assertNotIn('unresolved_document_reference',{i['code'] for i in result['issues']})
        self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_relation_declared_mismatch_keeps_every_real_item(self):
        result = tab('<div>Căn cứ (3)<ul><li><a href="/doc?ItemID=12">Luật 64/2025/QH15</a></li></ul></div>','relations')
        group = result['groups'][0]
        self.assertEqual(len(group['items']),1)
        self.assertEqual(group['items'][0]['references'][0]['identifiers'][0]['value'],'12')
        self.assertIn('relation_count_mismatch',{i['code'] for i in result['issues']})
        self.assertEqual(result['status'],'success_with_warnings')

    def test_consolidated_cards_are_records_with_all_text_and_candidates(self):
        result = tab('<h2>Các văn bản hợp nhất</h2><button><div>Văn bản hợp nhất số 08/VBHN-BTC</div>'
                     '<div>Ngày xác thực: 22/04/2022</div></button><button data-document-id="12">'
                     'Quyết định 05/2022/QĐ-TTg sửa Quyết định 157/2007/QĐ-TTg</button>','consolidated')
        self.assertEqual(len(result['items']),2)
        self.assertIn('Ngày xác thực: 22/04/2022',result['items'][0]['text'])
        self.assertEqual(result['items'][1]['mentioned_document_numbers'],['05/2022/QĐ-TTg','157/2007/QĐ-TTg'])
        self.assertIsNone(result['items'][1]['resolved_document_id'])
        self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_content_outside_numbered_metadata_pages_is_retained_once(self):
        result = tab('<p>Trước trang</p><h2>Thuộc tính — 1</h2><section data-page="1"><table>'
                     '<tr><td>Số hiệu 01/QĐ-BCT</td></tr></table></section><p>Sau trang</p>','properties')
        self.assertEqual([p['text'] for p in result['context']],['Trước trang','Sau trang'])
        self.assertTrue(result['validation']['meaningful_text_preserved'])

    def test_tables_and_lists_inside_metadata_records_are_never_flattened(self):
        cases = [
            ('properties', '<div class="ant-descriptions-item-container"><span class="ant-descriptions-item-label">Nhãn</span>'
             '<span class="ant-descriptions-item-content"><ul><li>Một</li><li>Hai</li></ul></span></div>', 'value_content', 'list'),
            ('properties', '<table><tr><td>Nhãn chưa rõ<table><tr><td>Giá trị</td></tr></table></td></tr></table>', 'value_content', 'table'),
            ('relations', '<div>Căn cứ (1)<ul><li><p>Văn bản</p><table><tr><td>A</td><td>B</td></tr></table></li></ul></div>', 'content', 'table'),
            ('consolidated', '<button data-document-id="12"><p>Văn bản</p><table><tr><td>A</td></tr></table></button>', 'children', 'table'),
        ]
        for key, html, attribute, expected_type in cases:
            with self.subTest(key=key, expected_type=expected_type):
                result = tab(html, key)
                record = result['fields'][0] if key == 'properties' else result['groups'][0]['items'][0] if key == 'relations' else result['context'][0]
                self.assertTrue(any(n['type'] == expected_type for n in record[attribute]))
                self.assertIsNone(record.get('value', record.get('text')))
                self.assertTrue(result['validation']['meaningful_text_preserved'])


class ExtractionTests(unittest.TestCase):
    def create_raw(self,root,scope='trung_uong',name='doc-id'):
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

    def test_offline_json_only_extraction_keeps_raw_and_verifiable_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); raw=self.create_raw(root); original={p.name:p.read_bytes() for p in raw.iterdir()}
            output=root/'extracted'/'doc-id'; manifest=extract_document(raw,output)
            self.assertEqual({p.name:p.read_bytes() for p in raw.iterdir()},original)
            self.assertEqual({p.name for p in output.iterdir()},{'content.json','properties.json','relations.json','history.json','manifest.json'})
            for p in output.iterdir():
                result=json.loads(p.read_text()); self.assertEqual(result['document_id'],'vbpl:doc-id')
                self.assertFalse(list(schema_validator().iter_errors(result)))
                self.assertEqual(len(result['source_ref']['sha256']),64)
                if p.name!='manifest.json':
                    self.assertTrue(result['validation']['meaningful_text_preserved'])
                    self.assertTrue(result['validation']['deterministic'])
                    self.assertFalse({'blocks','pages','structure'}.intersection(result))
            for record in manifest['files']:
                self.assertEqual(record,file_record(output/record['path'],output))
            history=json.loads((output/'history.json').read_text())
            self.assertEqual([e['source_key'] for e in history['events']],['event-1','event-2'])
            self.assertEqual(history['events'][1]['date'],'02/01/2026')
            self.assertEqual(manifest['issues'],[])

    def test_byte_determinism_raw_identity_and_changed_manifest_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); raw=self.create_raw(root); output=root/'extracted'/'doc-id'
            extract_document(raw,output); first={p.name:p.read_bytes() for p in output.iterdir()}
            extract_document(raw,output)
            self.assertEqual({p.name:p.read_bytes() for p in output.iterdir()},first)
            original=json.loads((raw/'manifest.json').read_text()); original['retrieved_at']='2026-10-05'; write_json(raw/'manifest.json',original)
            extract_document(raw,output)
            for name,content in first.items():
                if name!='manifest.json':
                    self.assertEqual((output/name).read_bytes(),content)
            self.assertNotEqual((output/'manifest.json').read_bytes(),first['manifest.json'])
            self.assertEqual(json.loads((output/'manifest.json').read_text())['source_ref']['sha256'],file_record(raw/'manifest.json',raw)['sha256'])

    def test_dynamic_tabs_are_extracted_and_original_download_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); raw=self.create_raw(root); manifest=json.loads((raw/'manifest.json').read_text())
            for key,label in [('tab_moi','Tab mới'),('original','Văn bản gốc'),('downloads','Tải về')]:
                p=raw/f'{key}.html'; p.write_text('<p>Nội dung đặc thù</p><ul><li>Mục mới</li></ul>')
                manifest['files'].append(file_record(p,raw)); manifest['tabs'][key]={'label':label}
            write_json(raw/'manifest.json',manifest); output=root/'extracted'/'doc-id'; result=extract_document(raw,output)
            self.assertIn('tab_moi',result['tabs'])
            self.assertNotIn('original',result['tabs']); self.assertNotIn('downloads',result['tabs'])
            self.assertTrue(json.loads((output/'tab_moi.json').read_text())['validation']['meaningful_text_preserved'])

    def test_parse_failure_publishes_failed_manifest_with_source_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); raw=self.create_raw(root); html='<div>'*1200+'Chữ nguồn'+'</div>'*1200
            (raw/'content.html').write_text(html); manifest=json.loads((raw/'manifest.json').read_text())
            manifest['files']=[file_record(raw/record['path'],raw) for record in manifest['files']]; write_json(raw/'manifest.json',manifest)
            output=root/'extracted'/'doc-id'; result=extract_document(raw,output)
            self.assertEqual(result['status'],'failed')
            self.assertGreater(result['issue_summary']['fatal'],0)
            data=json.loads((output/'content.json').read_text())
            self.assertIsNone(data['document'])
            self.assertNotIn('content', data)
            self.assertTrue(data['validation']['unparsed_source'])
            self.assertEqual((raw/'content.html').read_text(),html)

    def test_integrity_failure_preserves_previous_extraction(self):
        for failure in ('missing_html','hash_mismatch'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); raw=self.create_raw(root); output=root/'extracted'/'doc-id'; extract_document(raw,output)
                previous={p.name:p.read_bytes() for p in output.iterdir()}
                if failure=='missing_html':
                    (raw/'history.html').unlink()
                else:
                    (raw/'content.html').write_text('modified')
                with self.assertRaises(CrawlError) as raised:
                    extract_document(raw,output)
                self.assertEqual(raised.exception.report['status'], 'failed')
                self.assertFalse(list(schema_validator().iter_errors(raised.exception.report)))
                self.assertEqual(raised.exception.report['issues'][0]['severity'],
                                 'fatal' if failure == 'missing_html' else 'error')
                self.assertEqual({p.name:p.read_bytes() for p in output.iterdir()},previous)
                self.assertFalse(list(output.parent.glob('.extract-*')))

    def test_cli_writes_flat_document_directories_across_raw_scopes(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp); raw=self.create_raw(root); self.create_raw(root,'dia_phuong','other-id'); output=root/'extracted'/'vbpl'
            self.assertEqual(main(['--input',str(root/'raw'/'vbpl'),'--output',str(output)]),0)
            self.assertEqual(main(['--input',str(raw),'--output',str(output)]),0)
            self.assertTrue((output/'doc-id'/'content.json').is_file())
            self.assertTrue((output/'other-id'/'content.json').is_file())

    def test_cli_rejects_overlapping_paths_and_colliding_output_ids(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stderr(io.StringIO()),contextlib.redirect_stdout(io.StringIO()):
            for output in (tmp,str(Path(tmp)/'nested')):
                with self.assertRaises(SystemExit):
                    main(['--input',tmp,'--output',output])
            root=Path(tmp); self.create_raw(root); self.create_raw(root,'dia_phuong')
            with self.assertRaises(SystemExit):
                main(['--input',str(root/'raw'/'vbpl'),'--output',str(root/'extracted')])


class ValidatorTests(unittest.TestCase):
    def test_validator_detects_missing_text_from_actual_output(self):
        html='<p>Điều 1. Áp dụng</p><p>Nội dung quan trọng</p>'; result=tab(html,'content')
        result['document']['children'][0]['children']=[]
        quality=Quality(); evidence=quality.conservation(parse_html(html),result)
        self.assertFalse(evidence['meaningful_text_preserved'])
        self.assertEqual(quality.issues[0]['severity'],'fatal')

    def test_validator_detects_identity_schema_order_parent_and_duplicates(self):
        result=tab('<p>Điều 1. A</p><p>Điều 2. B</p>','content')
        broken=deepcopy(result); broken['document_id']='other'; broken['source_ref']['sha256']='bad'
        nodes=broken['document']['children'][0]['children']
        nodes.reverse(); nodes.append(deepcopy(nodes[0]))
        nodes.append({'type':'clause','number':'1','title':None,'text':'1. Orphan','order':999,'children':[],'source_ref':{'dom_order':999}})
        quality=Quality(); validate_result(broken,'vbpl:99',quality)
        self.assertTrue({'invalid_document_id','invalid_source_ref','invalid_order','invalid_parent','duplicate_semantic_block','invalid_schema'} <= {i['code'] for i in quality.issues})

    def test_empty_content_is_fatal_and_info_does_not_change_status(self):
        result=tab('<p>&nbsp;</p>','content')
        self.assertEqual(result['status'],'failed')
        self.assertIn(('fatal','source_content_missing'),{(i['severity'],i['code']) for i in result['issues']})


if __name__=='__main__':
    unittest.main()
