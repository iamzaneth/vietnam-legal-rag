"""ExtractionTests for the extraction pipeline."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from vietnam_legal_rag.ingestion.crawl_legal_documents import CrawlError, file_record, write_json
from vietnam_legal_rag.ingestion.extract_legal_documents import extract_document, main
from vietnam_legal_rag.ingestion.validation.extract import schema_validator

from tests.support import create_raw


class ExtractionTests(unittest.TestCase):
    def test_offline_json_only_extraction_keeps_raw_and_verifiable_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); raw=create_raw(root); original={p.name:p.read_bytes() for p in raw.iterdir()}
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
            root=Path(tmp); raw=create_raw(root); output=root/'extracted'/'doc-id'
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
            root=Path(tmp); raw=create_raw(root); manifest=json.loads((raw/'manifest.json').read_text())
            for key,label in [('tab_moi','Tab mới'),('original','Văn bản gốc'),('downloads','Tải về')]:
                p=raw/f'{key}.html'; p.write_text('<p>Nội dung đặc thù</p><ul><li>Mục mới</li></ul>')
                manifest['files'].append(file_record(p,raw)); manifest['tabs'][key]={'label':label}
            write_json(raw/'manifest.json',manifest); output=root/'extracted'/'doc-id'; result=extract_document(raw,output)
            self.assertIn('tab_moi',result['tabs'])
            self.assertNotIn('original',result['tabs']); self.assertNotIn('downloads',result['tabs'])
            self.assertTrue(json.loads((output/'tab_moi.json').read_text())['validation']['meaningful_text_preserved'])

    def test_parse_failure_publishes_failed_manifest_with_source_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); raw=create_raw(root); html='<div>'*1200+'Chữ nguồn'+'</div>'*1200
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
                root=Path(tmp); raw=create_raw(root); output=root/'extracted'/'doc-id'; extract_document(raw,output)
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
            root=Path(tmp); raw=create_raw(root); create_raw(root,'dia_phuong','other-id'); output=root/'extracted'/'vbpl'
            self.assertEqual(main(['--input',str(root/'raw'/'vbpl'),'--output',str(output)]),0)
            self.assertEqual(main(['--input',str(raw),'--output',str(output)]),0)
            self.assertTrue((output/'doc-id'/'content.json').is_file())
            self.assertTrue((output/'other-id'/'content.json').is_file())

    def test_cli_rejects_overlapping_paths_and_colliding_output_ids(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stderr(io.StringIO()),contextlib.redirect_stdout(io.StringIO()):
            for output in (tmp,str(Path(tmp)/'nested')):
                with self.assertRaises(SystemExit):
                    main(['--input',tmp,'--output',output])
            root=Path(tmp); create_raw(root); create_raw(root,'dia_phuong')
            with self.assertRaises(SystemExit):
                main(['--input',str(root/'raw'/'vbpl'),'--output',str(root/'extracted')])


if __name__ == "__main__":
    unittest.main()
