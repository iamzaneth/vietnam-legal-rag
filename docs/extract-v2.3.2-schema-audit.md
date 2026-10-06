# Extract V2.3.2 freeze audit

Schema version **2.3.2**; parser version **2.3.2**; baseline **2.3.1**. This is an incremental consistency cleanup.

**Extract schema V2.3.2 is ready to freeze.** All acceptance checks use actual generated JSON. The current Circular 60 fixture has no warnings/errors/fatals. Two existing source ambiguities remain explicit in separate fixtures; their semantic_complete stays false.

All five representative captures were extracted. Independent verification validates 25 JSON files against Draft 2020-12, reparses 20 source tabs twice and compares artifact bytes. Source hashes, legal and annex ancestry, 1,123 physical cells, text/effective_text/text_segments, spans, source links and all 15 properties/history/relations payloads match V2.3.1.

| Fixture | Articles | Clauses | Points | Annexes | Numbered sections / items | Forms | Orphans / ambiguous | W / E / F | Text / deterministic / schema / order | Complete |
| --- | ---: | ---: | ---: | ---: | --- | ---: | --- | --- | --- | --- |
| 16111 /QĐ-BCT | 3 | 2 | 0 | 0 | 0 / 0 | 0 | 0 / 0 | 1 / 0 / 0 | true / true / true / true | false |
| 365/2026/NĐ-CP | 28 | 80 | 110 | 1 | 0 / 0 | 11 | 0 / 0 | 0 / 0 / 0 | true / true / true / true | true |
| 59/2026/TT-BCT | 45 | 145 | 142 | 0 | 0 / 0 | 0 | 0 / 0 | 1 / 0 / 0 | true / true / true / true | false |
| 60/2026/TT-BCT | 15 | 36 | 5 | 4 | 5 / 26 | 16 | 0 / 0 | 0 / 0 / 0 | true / true / true / true | true |
| 34/2026/NQ-CP | 3 | 4 | 0 | 0 | 0 / 0 | 0 | 0 / 0 | 0 / 0 / 0 | true / true / true / true | true |

## Before → after

| Metric | V2.3.1 | V2.3.2 |
| --- | ---: | ---: |
| forms | 27 | 27 |
| fields | 200 | 202 |
| subfields | 39 | 40 |
| placeholders | 6 | 6 |
| footnotes | 54 | 54 |
| placeholder_references | 65 | 65 |
| unresolved_numbered_form_items | 0 | 0 |
| split_form_candidates | 0 | 0 |
| inconsistent_footnote_sequences | 0 | 0 |
| bibliography_fields_misclassified | 0 | 0 |
| structured_table_cell_lists | 4 | 4 |
| generic_structured_paragraphs | 2 | 2 |
| suspicious_value_text | 17 | 0 |
| semantic_empty_string_fields | 0 | 0 |
| physical_empty_cells | 420 | 420 |
| unexplained_form_label_paragraphs | 2 | 0 |
| unexplained_structured_paragraphs | 0 | 0 |
| ignored_ui_artifacts | 4 | 4 |
| orphan_nodes | 0 | 0 |
| numbered_paragraph_candidates | 0 | 0 |
| generic_decimal_paragraphs | 0 | 0 |
| ambiguous_tables | 0 | 0 |
| warnings | 2 | 2 |
| errors | 0 | 0 |
| generic_form_label_paragraphs | 2 | 0 |
| generic_form_fields_including_values | 2 | 0 |
| duplicated_references | 0 | 0 |
| singleton_source_refs | 0 | 0 |
| title_ref_occurrences | 12 | 0 |
| meaningless_axis_cell_metadata | 1092 | 0 |

## Inspected semantic changes

Chức vụ (nếu có) and Số CCCD/Hộ chiếu become input labels through a bounded form-input sequence. The optional qualifier remains in source display, while the source field name is Chức vụ. The issue-date/place fragment remains verbatim as a continuation child of the identification field; the source does not explicitly label Ngày cấp/Nơi cấp, so no such names are invented.

Người đại diện/Người yêu cầu: Ông (bà): is split at the source prompt boundary into a composite field and input-label subfield. Both have null value_text and share provenance with offsets. Completion instructions have null value_text. Where a source blank precedes another prompt/declaration, value_text keeps only the actual initial blank; full display remains in text. Actual values and date/range placeholders remain source-faithful.

Form title aliases and coalesced legal titles use title_source_ref. A displayed form-title child owns the text once; contributing references remain traceable. No new node types or field-kind enum members are added. Cells of layout/form/annex_form/key_value tables omit inapplicable role/confidence; data/matrix classifications remain intact. Real empty cells stay empty strings.

| Type | Before | After |
| --- | ---: | ---: |
| form_field | 200 | 202 |
| form_subfield | 39 | 40 |
| paragraph | 829 | 827 |

The two promoted labels account for paragraph −2 / form_field +2. The source nested prompt accounts for form_subfield +1. All other type counts remain unchanged. Fields retaining source blanks keep their original text and placeholder references.

## Vocabularies

**Produced node types:** `annex`, `annex_heading`, `annex_note`, `annexes`, `article`, `bibliography`, `bibliography_entry`, `body`, `chapter`, `clause`, `closing`, `delegation_title`, `document_number`, `document_title`, `document_type_heading`, `enacting_formula`, `footnote`, `footnote_group`, `form`, `form_field`, `form_header`, `form_number`, `form_placeholder`, `form_signature`, `form_subfield`, `form_subtitle`, `form_title`, `header`, `heading`, `issuing_authority`, `issuing_authority_title`, `legal_basis`, `legal_document`, `list`, `list_item`, `national_heading`, `national_motto`, `note`, `numbered_item`, `numbered_section`, `paragraph`, `place_and_date`, `point`, `preamble`, `proposal_basis`, `recipient`, `recipients`, `signature`, `signature_marker`, `signature_status`, `signer_name`, `signer_title`, `table`, `title_block`.

**Allowed table kinds:** layout, data, matrix, form, key_value, annex_form, ambiguous. Produced: {'annex_form': 59, 'key_value': 2, 'matrix': 1}.

**Allowed field kinds:** composite, display, input, input_label, instruction, unknown. Produced: {'composite': 4, 'display': 2, 'input': 126, 'input_label': 29, 'instruction': 41}.

**Produced fallbacks:** {'paragraph': 827}. Genuine prose remains paragraph. Schema still supports unknown/numbered_paragraph.

**Deprecated metadata removed:** title_ref (replaced by title_source_ref); unknown role / zero confidence on cells of non-axis table kinds. document_number_candidates remains forbidden; no relation/history behavior changes.

## Property vocabulary

| Property | Node types (count) | Total |
| --- | --- | ---: |
| annotations | form_field (1), form_number (1) | 2 |
| cells | table (62) | 62 |
| children | annex (5), annex_heading (1), annex_note (7), annexes (2), article (94), bibliography (1), bibliography_entry (3), body (5), chapter (15), clause (267), closing (5), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (10), form (27), form_field (202), form_header (19), form_number (13), form_placeholder (6), form_signature (3), form_subfield (40), form_subtitle (14), form_title (21), header (5), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), legal_document (5), list (19), list_item (66), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (827), place_and_date (20), point (257), preamble (5), proposal_basis (5), recipient (86), recipients (17), signature (5), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62), title_block (5) | 2368 |
| classification_evidence | table (62) | 62 |
| evidence | article (94), chapter (15), clause (267), form (27), paragraph (1), point (257) | 661 |
| field_evidence | form_field (202), form_subfield (10) | 212 |
| field_kind | form_field (202), form_subfield (13) | 215 |
| field_name | form_field (202), form_subfield (25) | 227 |
| grid_shape | table (62) | 62 |
| heading_evidence | annex (5), annex_heading (1), article (88), chapter (15), delegation_title (4), document_title (3), document_type_heading (3), form (26), form_field (9), form_placeholder (1), form_subtitle (14), form_title (21), heading (8), issuing_authority (14), national_heading (15), national_motto (15), note (15), numbered_section (5), paragraph (78), recipients (15), signature_marker (1), signer_name (3), signer_title (6) | 365 |
| issues | table (62) | 62 |
| label | annex (5), article (94), bibliography_entry (3), chapter (15), clause (267), footnote (52), form (26), form_field (91), form_subfield (30), list_item (32), numbered_item (26), numbered_section (5), point (257), recipient (22) | 925 |
| label_suffix | article (94) | 94 |
| level | numbered_item (26), numbered_section (5) | 31 |
| list_kind | bibliography (1), list (19) | 20 |
| marker | footnote (54), form_field (30), form_subfield (30), list_item (62), recipient (22) | 198 |
| number | annex (5), article (94), bibliography_entry (3), chapter (15), clause (267), document_number (5), form (27), form_field (61), list_item (4), numbered_item (26), numbered_section (5), point (257) | 769 |
| number_path | numbered_item (26), numbered_section (5) | 31 |
| numbering | bibliography (1), list (19) | 20 |
| order | annex (5), annex_heading (1), annex_note (7), annexes (2), article (94), bibliography (1), bibliography_entry (3), body (5), chapter (15), clause (267), closing (5), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (10), form (27), form_field (202), form_header (19), form_number (13), form_placeholder (6), form_signature (3), form_subfield (40), form_subtitle (14), form_title (21), header (5), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), legal_document (5), list (19), list_item (66), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (827), place_and_date (20), point (257), preamble (5), proposal_basis (5), recipient (86), recipients (17), signature (5), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62), title_block (5) | 2368 |
| parent_number | numbered_item (26) | 26 |
| placeholder_refs | form_field (29), form_placeholder (3), form_subfield (2), paragraph (17), place_and_date (5) | 56 |
| promotion_evidence | clause (42) | 42 |
| references | annex_note (1), document_number (1), legal_basis (15), paragraph (10) | 27 |
| row_groups | table (62) | 62 |
| semantic | signature_marker (1) | 1 |
| semantics | table (62) | 62 |
| source_layouts | annexes (2), closing (5), header (5) | 12 |
| source_offset | delegation_title (2), document_title (1), document_type_heading (1), form_field (3), form_subfield (1), issuing_authority (1), national_heading (3), national_motto (3), paragraph (534), signer_name (1), signer_title (3) | 553 |
| source_ref | annex (5), annex_heading (1), annex_note (7), annexes (2), article (94), bibliography (1), bibliography_entry (3), body (5), chapter (15), clause (267), closing (5), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (10), form (27), form_field (202), form_header (19), form_number (13), form_placeholder (6), form_signature (3), form_subfield (40), form_subtitle (14), form_title (21), header (5), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), legal_document (5), list (19), list_item (66), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (827), place_and_date (20), point (257), preamble (5), proposal_basis (5), recipient (86), recipients (17), signature (5), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62), title_block (5) | 2368 |
| source_refs | chapter (11), form (11) | 22 |
| style | bibliography (1), list (19) | 20 |
| table_id | table (62) | 62 |
| table_kind | table (62) | 62 |
| text | annex_heading (1), annex_note (7), bibliography_entry (3), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (1), form (26), form_field (202), form_number (13), form_placeholder (6), form_subfield (40), form_subtitle (14), form_title (21), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), list_item (66), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (827), place_and_date (20), proposal_basis (5), recipient (86), recipients (17), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62) | 1641 |
| title | annex (5), article (94), chapter (15), clause (267), form (27), numbered_item (26), numbered_section (5), point (257) | 696 |
| title_evidence | article (86), chapter (15), numbered_item (12) | 113 |
| title_source_offset | article (7), chapter (1) | 8 |
| title_source_ref | article (7), chapter (12), form (12) | 31 |
| title_source_spans | chapter (2) | 2 |
| type | annex (5), annex_heading (1), annex_note (7), annexes (2), article (94), bibliography (1), bibliography_entry (3), body (5), chapter (15), clause (267), closing (5), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (10), form (27), form_field (202), form_header (19), form_number (13), form_placeholder (6), form_signature (3), form_subfield (40), form_subtitle (14), form_title (21), header (5), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), legal_document (5), list (19), list_item (66), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (827), place_and_date (20), point (257), preamble (5), proposal_basis (5), recipient (86), recipients (17), signature (5), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62), title_block (5) | 2368 |
| unit | form_subfield (3) | 3 |
| value_text | form_field (202), form_subfield (25) | 227 |

All properties occurring once, manually reviewed:

- `semantic` (1): Known source signature_marker [daky] expresses signed status without inferring the signer.

title_ref has zero output occurrences. title_source_ref is the single title-reference property; multi-element title_source_spans additionally preserves actual source offsets, serving a distinct role.

Physical cell properties are audited separately: `association_status` (30), `cell_id` (1123), `cell_type` (1123), `colspan` (1123), `column` (1123), `column_axis` (1), `confidence` (31), `content` (85), `effective_text` (1123), `evidence` (705), `labels` (1), `order` (1123), `orientation` (1), `original_colspan` (1123), `original_rowspan` (1123), `role` (31), `row` (1123), `row_axis` (1), `row_group_id` (1123), `rowspan` (1123), `section` (1123), `source_ref` (1123), `text` (1123), `text_segments` (1123).

## Retained paragraph candidates

- 365/2026/NĐ-CP, order 1729: `NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT CỦA THƯƠNG NHÂN` — `short_label_outside_confirmed_input_sequence`.
- 365/2026/NĐ-CP, order 2396: `NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT CỦA THƯƠNG NHÂN` — `short_label_outside_confirmed_input_sequence`.
- 365/2026/NĐ-CP, order 4688: `NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT` — `short_label_outside_confirmed_input_sequence`.
- 365/2026/NĐ-CP, order 4719: `TÊN THƯƠNG NHÂN` — `short_label_outside_confirmed_input_sequence`.
- 365/2026/NĐ-CP, order 5048: `NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT` — `short_label_outside_confirmed_input_sequence`.
- 365/2026/NĐ-CP, order 5267: `NGƯỜI ĐẠI DIỆN THEO` — `short_label_outside_confirmed_input_sequence`.
- 365/2026/NĐ-CP, order 5742: `NGƯỜI ĐẠI DIỆN THEO` — `short_label_outside_confirmed_input_sequence`.
- 365/2026/NĐ-CP, order 5991: `Số lượng nhập kho` — `short_label_outside_confirmed_input_sequence`.
- 365/2026/NĐ-CP, order 6001: `Số lượng xuất kho` — `short_label_outside_confirmed_input_sequence`.
- 365/2026/NĐ-CP, order 6011: `Số lượng tồn kho` — `short_label_outside_confirmed_input_sequence`.
- 365/2026/NĐ-CP, order 6413: `NGƯỜI ĐẠI DIỆN THEO` — `short_label_outside_confirmed_input_sequence`.
- 365/2026/NĐ-CP, order 6669: `NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT CỦA THƯƠNG NHÂN` — `short_label_outside_confirmed_input_sequence`.
- 60/2026/TT-BCT, order 1311: `NGƯỜI RÀ SOÁT` — `short_label_outside_confirmed_input_sequence`.
- 60/2026/TT-BCT, order 1437: `Thông tin kiểm tra:` — `introductory_prose_for_following_content`.
- 60/2026/TT-BCT, order 1616: `NGƯỜI KIỂM TRA` — `short_label_outside_confirmed_input_sequence`.
- 60/2026/TT-BCT, order 2745: `Đã nộp mẫu vật vào cơ quan lưu trữ gồm:` — `introductory_prose_for_following_content`.
- 60/2026/TT-BCT, order 2905: `Tài liệu kèm theo:` — `introductory_prose_for_following_content`.
- 60/2026/TT-BCT, order 5120: `Người theo dõi Chủ nhiệm đề án` — `short_label_outside_confirmed_input_sequence`.
- 60/2026/TT-BCT, order 5468: `Người theo dõi Chủ nhiệm đề án` — `short_label_outside_confirmed_input_sequence`.
- 60/2026/TT-BCT, order 5741: `cấp ngày tháng năm .Tại:` — `attached_source_field_continuation`.
- 60/2026/TT-BCT, order 5789: `NGƯỜI YÊU CẦU` — `short_label_outside_confirmed_input_sequence`.
- 60/2026/TT-BCT, order 4133: `- Tài liệu công trình khai đào.` — `isolated_marker_without_adjacent_sequence`.
- 60/2026/TT-BCT, order 4172: `- Tài liệu công trình khoan` — `isolated_marker_without_adjacent_sequence`.

The retained short all-caps person roles are signature captions, not bounded input labels; Người theo dõi Chủ nhiệm đề án is a signature caption. The Số lượng nhập/xuất/tồn kho texts are table column captions, not inputs sandwiched between form fields. Introductory Thông tin kiểm tra/Tài liệu kèm theo/Đã nộp…gồm stay prose. The identification continuation is source-associated. Two isolated dash paragraphs are separated by substantive text/tables, so they cannot form an adjacent list. No unexplained structured or form-label paragraph remains.

## Form boundaries and value audit


**365/2026/NĐ-CP**

- Annex None, form 01 → ĐƠN ĐỀ NGHỊ → 18 children → next 02
- Annex None, form 02 → GIẤY CHỨNG NHẬN → 21 children → next 03
- Annex None, form 03 → ĐƠN ĐỀ NGHỊ → 20 children → next 04
- Annex None, form 04 → GIẤY CHỨNG NHẬN → 22 children → next 05
- Annex None, form 05 → GIẤY CHỨNG NHẬN → 22 children → next 06
- Annex None, form 06 → BÁO CÁO TÌNH HÌNH KÝ KẾT VÀ THỰC HIỆN HỢP ĐỒNG XUẤT KHẨU GẠO → 14 children → next 07
- Annex None, form 07 → BÁO CÁO LƯỢNG THÓC, GẠO THỰC TẾ TỒN KHO → 16 children → next 08
- Annex None, form 08 → BÁO CÁO → 15 children → next 09
- Annex None, form 09 → THÔNG BÁO → 19 children → next 10
- Annex None, form 10 → BÁO CÁO → 16 children → next 11
- Annex None, form 11 → VĂN BẢN ĐỀ NGHỊ → 16 children → next None

**60/2026/TT-BCT**

- Annex I, form 01 → Danh mục thông tin, dữ liệu giao nộp → 12 children → next 02
- Annex I, form 02 → Thông báo kết quả kiểm tra, đối chiếu
thông tin, dữ liệu giao nộp → 13 children → next 03
- Annex I, form 03 → Thông báo kết quả kiểm tra mẫu vật địa chất, khoáng sản,
mẫu vật bảo tàng giao nộp → 13 children → next 04
- Annex I, form 04 → Biên bản giao nhận thông tin, dữ liệu
địa chất, khoáng sản nộp lưu trữ → 20 children → next 05
- Annex I, form 05 → Biên bản giao nhận mẫu vậtđịa chất, khoáng sản, mẫuvậtbảo tàng → 21 children → next None
- Annex II, form 01 → Bìa 1 Thuyết minh tài liệu, báo cáo → 2 children → next 02
- Annex II, form 02 → Bìa 2 Thuyết minh tài liệu, báo cáo → 11 children → next 03
- Annex II, form 03 → Danh mục tài liệu tham khảo → 3 children → next 04
- Annex II, form 04 → Danh mục các phụ lục kèm theo → 2 children → next 05
- Annex II, form 05 → Danh mục bản vẽ kèm theo → 3 children → next 06
- Annex II, form 06 → Danh mục tài liệu nguyên thủy → 3 children → next None
- Annex III, form 01 → Nhật ký địa chất → 10 children → next 02
- Annex III, form 02 → Sổ mô tả công trình khai đào (dọn vết lộ, hào, hố, lò, giếng) → 7 children → next 03
- Annex III, form 03 → Thiết đồ theo dõi, mô tả công trình khoan → 5 children → next 04
- Annex III, form 04 → Thiết đồ tổng hợp công trình khoan → 5 children → next None
- Annex IV, form None → PHIẾU YÊU CẦU CUNG CẤP THÔNG TIN, DỮ LIỆU ĐỊA CHẤT, KHOÁNG SẢN → 16 children → next None

Each before-case of suspicious_value_text, including source order/name/value, is recorded in the machine-readable report. All after-audits are empty. Footnote groups, bibliography entries, alphabetic subfields, coordinates, table-cell lists, source placeholders and UI exclusions are preserved.

## Size, quality and validation

Combined content.json size: **2,931,475 → 2,838,613 bytes**. Removed inapplicable cell metadata accounts for the reduction; geometry and provenance remain intact. Contributor estimates are available per fixture in JSON.

diagnostic_info_count and issue severity remain compatible: expected form/layout preservation is informational. Warning/error/fatal counts do not increase. A bare numeric page candidate in the Decision and unresolved axis orientation in the technical Circular remain source ambiguities, not suppressed warnings.

183 unit tests pass: 24 new V2.3.2 tests and all 159 prior tests. Only the prior title_ref expectation changes to title_source_ref. New tests cover no-colon labels/negative contexts, source continuations, nested prompts/links/offsets, instruction-value schema rejection, contextual value validation, retained values/blanks, canonical title provenance, axis-kind behavior, physical versus semantic empty strings, prose lead-ins and idempotence.

Files changed: schema_cleanup.py; extract_quality.py; form_refinement.py; form_validation.py; table_semantics.py; structured_html.py; schemas/extracted.schema.json; audit_vbpl_hierarchy.py; audit_extract_schema.py; test_consistency_cleanup.py; test_form_refinement.py; docs/extracted-schema.md; README.md; generated Extract artifacts and audit reports. The packaged schema uses the existing symlink.

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit
PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.ingestion.extract_legal_documents --debug-tree
PYTHONPATH=src .venv/bin/python scripts/audit_extract_schema.py --raw data/raw/vbpl --extracted data/extracted/vbpl --before /path/to/v2.3.1/extracted --report docs/extract-v2.3.2-schema-audit.json
```

Freeze decision: no additional semantic rules until a new real-world VBPL source exposes a structure that cannot be faithfully represented.
