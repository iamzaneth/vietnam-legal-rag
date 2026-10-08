"""MetadataTests for the extraction pipeline."""
import unittest
from tests.support import metadata_tab as tab


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


if __name__ == "__main__":
    unittest.main()
