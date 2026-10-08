# Extract V2.3.2 finalization audit

Schema **2.3.2**; parser **2.3.2**. Compared with the captured pre-finalization 2.3.2 output. All 25 artifacts were regenerated from RAW and validated against the existing JSON Schema. No Extract artifact was manually repaired.

## Root causes and repairs

- Separate dash-only, adjacent-only list rules missed plus markers, nested lists and continuation paragraphs. One shared source-flow rule now uses list/list_item for dash parents and plus children; heading/lead-in evidence and a compatible following marker are required for continuations.
- Form fields were classified before lists. Lists now take precedence, with actual input prompts preserved as nested source-backed form_field nodes. Inline completion commentary remains list-item text.
- The output audit omitted plus markers and justified dash parents solely from immediate neighbors. The serialized audit now examines both directions across bounded prose, including prematurely classified field neighbors; unresolved sequences fail semantic completeness.
- Note lookahead could mutate an unconsumed candidate through a shared children array. Marker/body conversion now copies that array, preventing duplicated source content when a later nested list is rebuilt.
- Recipient paragraphs with inline-emphasized dashes could become tight -Body text. Explicit recipient context now keeps the whole sequence under recipients, avoiding false fields for recipient blanks. Tight source displays remain intact so effective_text does not change.

## Actual output metrics

| Fixture | Chapters / articles / clauses / points | Annexes / sections / items | Forms / fields / subfields | Footnotes | Orphans / ambiguous / candidates | W / E / F | Complete |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| 16111 /QĐ-BCT | 0 / 3 / 2 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | 0 / 0 / 0 | 1 / 0 / 0 | false |
| 365/2026/NĐ-CP | 5 / 28 / 80 / 110 | 1 / 0 / 0 | 11 / 121 / 26 | 2 | 0 / 0 / 0 | 0 / 0 / 0 | true |
| 59/2026/TT-BCT | 6 / 45 / 145 / 142 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | 0 / 0 / 0 | 1 / 0 / 0 | false |
| 60/2026/TT-BCT | 4 / 15 / 36 / 5 | 4 / 5 / 26 | 16 / 80 / 14 | 52 | 0 / 0 / 0 | 0 / 0 / 0 | true |
| 34/2026/NQ-CP | 0 / 3 / 4 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | 0 / 0 / 0 | 0 / 0 / 0 | true |

All fixtures: meaningful_text_preserved, deterministic, schema_valid, order_valid and parent_child_valid are true. The primary fixture has semantic_complete=true, hierarchy status=valid and zero warning/error/fatal issues. Two pre-existing ambiguities remain explicit elsewhere: a bare page-number candidate in the Decision and unresolved matrix-axis orientation in the technical Circular. Their semantic_complete remains false.

The primary fixture retains 16 forms, 14 subfields, 52 footnotes and 65 placeholder references. Fields change 81 → 80: the first plus-prefixed attachment instruction is now a list_item alongside its sibling. Annex III item 1.6 has two dash parents with five/four plus children and eight source-backed continuation paragraphs. Its unmarked concluding prose stays at the numbered-item level because no unique last-child attachment is evidenced.

Three table-cell lists in the Decree were recipient lists broken by tight inline dashes. They are now recipients/recipient, with all cell text and geometry preserved; this is a corrected role, not loss of a structured list. Input fields elsewhere in the Decree survive added list wrappers.

## Before → after audits

Baseline metrics below are recomputed with the strengthened audit. The previous stored audit did not count plus markers or tight recipient markers.

| Metric | Before | After |
| --- | ---: | ---: |
| forms | 27 | 27 |
| fields | 202 | 201 |
| subfields | 40 | 40 |
| placeholders | 6 | 6 |
| footnotes | 54 | 54 |
| placeholder_references | 65 | 65 |
| unresolved_numbered_form_items | 1 | 0 |
| split_form_candidates | 0 | 0 |
| inconsistent_footnote_sequences | 0 | 0 |
| bibliography_fields_misclassified | 0 | 0 |
| structured_table_cell_lists | 4 | 1 |
| generic_structured_paragraphs | 15 | 0 |
| form_nodes_missing_field_kind | 0 | 0 |
| form_nodes_missing_field_evidence | 0 | 0 |
| suspicious_value_text | 0 | 0 |
| semantic_empty_string_fields | 0 | 0 |
| physical_empty_cells | 420 | 420 |
| unexplained_form_label_paragraphs | 0 | 0 |
| unexplained_structured_paragraphs | 15 | 0 |
| ignored_ui_artifacts | 4 | 4 |
| orphan_nodes | 0 | 0 |
| numbered_paragraph_candidates | 0 | 0 |
| generic_decimal_paragraphs | 0 | 0 |
| ambiguous_tables | 0 | 0 |
| warnings | 2 | 2 |
| errors | 0 | 0 |
| generic_form_label_paragraphs | 0 | 0 |
| generic_form_fields_including_values | 0 | 0 |
| duplicated_references | 0 | 0 |
| singleton_source_refs | 0 | 0 |
| title_ref_occurrences | 0 | 0 |
| meaningless_axis_cell_metadata | 0 | 0 |

## Semantic type changes

| Type | Before | After |
| --- | ---: | ---: |
| form_field | 202 | 201 |
| list | 19 | 26 |
| list_item | 66 | 98 |
| paragraph | 827 | 812 |
| recipient | 86 | 96 |

## Schema and provenance

No schema-version change or new semantic type was needed. Every prior list item retains its source display/marker, either as list_item or a source-backed recipient under its explicit heading. Legal and annex ancestry, source order, links/identifiers, table geometry and data/matrix associations match baseline. All 15 properties/history/relations files are byte-identical to baseline.

**Node types:** annex, annex_heading, annex_note, annexes, article, bibliography, bibliography_entry, body, chapter, clause, closing, delegation_title, document_number, document_title, document_type_heading, enacting_formula, footnote, footnote_group, form, form_field, form_header, form_number, form_placeholder, form_signature, form_subfield, form_subtitle, form_title, header, heading, issuing_authority, issuing_authority_title, legal_basis, legal_document, list, list_item, national_heading, national_motto, note, numbered_item, numbered_section, paragraph, place_and_date, point, preamble, proposal_basis, recipient, recipients, signature, signature_marker, signature_status, signer_name, signer_title, table, title_block.

**Table kinds:** {'allowed': ['layout', 'data', 'matrix', 'form', 'key_value', 'annex_form', 'ambiguous'], 'produced': {'annex_form': 59, 'key_value': 2, 'matrix': 1}, 'semanticized_layout_tables': 23}.

**Field kinds:** {'allowed': ['composite', 'display', 'input', 'input_label', 'instruction', 'unknown'], 'produced': {'composite': 4, 'display': 2, 'input': 126, 'input_label': 29, 'instruction': 40}}.

All form fields/subfields explicitly carry field_name, field_kind, field_evidence and value_text. Required coverage is fields + subfields, including cells. Missing metadata, suspicious values, semantic empty strings, deprecated title_ref/relation candidate fields, duplicated references, inapplicable cell-axis metadata, unexplained structured/form-label paragraphs, orphans and numbered candidates are all zero.

## Property vocabulary

| Property | Node types (count) | Total |
| --- | --- | ---: |
| annotations | form_field (1), form_number (1) | 2 |
| cells | table (62) | 62 |
| children | annex (5), annex_heading (1), annex_note (7), annexes (2), article (94), bibliography (1), bibliography_entry (3), body (5), chapter (15), clause (267), closing (5), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (10), form (27), form_field (201), form_header (19), form_number (13), form_placeholder (6), form_signature (3), form_subfield (40), form_subtitle (14), form_title (21), header (5), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), legal_document (5), list (26), list_item (98), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (812), place_and_date (20), point (257), preamble (5), proposal_basis (5), recipient (96), recipients (17), signature (5), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62), title_block (5) | 2401 |
| classification_evidence | table (62) | 62 |
| evidence | article (94), chapter (15), clause (267), form (27), paragraph (1), point (257) | 661 |
| field_evidence | form_field (201), form_subfield (40) | 241 |
| field_kind | form_field (201), form_subfield (40) | 241 |
| field_name | form_field (201), form_subfield (40) | 241 |
| grid_shape | table (62) | 62 |
| heading_evidence | annex (5), annex_heading (1), article (88), chapter (15), delegation_title (4), document_title (3), document_type_heading (3), form (26), form_field (9), form_placeholder (1), form_subtitle (14), form_title (21), heading (8), issuing_authority (14), national_heading (15), national_motto (15), note (15), numbered_section (5), paragraph (78), recipients (15), signature_marker (1), signer_name (3), signer_title (6) | 365 |
| issues | table (62) | 62 |
| label | annex (5), article (94), bibliography_entry (3), chapter (15), clause (267), footnote (52), form (26), form_field (65), form_subfield (30), list_item (98), numbered_item (26), numbered_section (5), point (257), recipient (29) | 972 |
| label_suffix | article (94) | 94 |
| level | numbered_item (26), numbered_section (5) | 31 |
| list_kind | bibliography (1), list (26) | 27 |
| marker | footnote (54), form_field (4), form_subfield (30), list_item (94), recipient (32) | 214 |
| number | annex (5), article (94), bibliography_entry (3), chapter (15), clause (267), document_number (5), form (27), form_field (61), list_item (4), numbered_item (26), numbered_section (5), point (257) | 769 |
| number_path | numbered_item (26), numbered_section (5) | 31 |
| numbering | bibliography (1), list (26) | 27 |
| order | annex (5), annex_heading (1), annex_note (7), annexes (2), article (94), bibliography (1), bibliography_entry (3), body (5), chapter (15), clause (267), closing (5), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (10), form (27), form_field (201), form_header (19), form_number (13), form_placeholder (6), form_signature (3), form_subfield (40), form_subtitle (14), form_title (21), header (5), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), legal_document (5), list (26), list_item (98), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (812), place_and_date (20), point (257), preamble (5), proposal_basis (5), recipient (96), recipients (17), signature (5), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62), title_block (5) | 2401 |
| parent_number | numbered_item (26) | 26 |
| placeholder_refs | form_field (29), form_placeholder (3), form_subfield (2), paragraph (17), place_and_date (5) | 56 |
| promotion_evidence | clause (42) | 42 |
| references | annex_note (1), document_number (1), legal_basis (15), paragraph (10) | 27 |
| row_groups | table (62) | 62 |
| semantic | signature_marker (1) | 1 |
| semantics | table (62) | 62 |
| source_layouts | annexes (2), closing (5), header (5) | 12 |
| source_offset | delegation_title (2), document_title (1), document_type_heading (1), form_field (29), form_subfield (1), issuing_authority (1), national_heading (3), national_motto (3), paragraph (534), signer_name (1), signer_title (3) | 579 |
| source_ref | annex (5), annex_heading (1), annex_note (7), annexes (2), article (94), bibliography (1), bibliography_entry (3), body (5), chapter (15), clause (267), closing (5), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (10), form (27), form_field (201), form_header (19), form_number (13), form_placeholder (6), form_signature (3), form_subfield (40), form_subtitle (14), form_title (21), header (5), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), legal_document (5), list (26), list_item (98), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (812), place_and_date (20), point (257), preamble (5), proposal_basis (5), recipient (96), recipients (17), signature (5), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62), title_block (5) | 2401 |
| source_refs | chapter (11), form (11) | 22 |
| style | bibliography (1), list (26) | 27 |
| table_id | table (62) | 62 |
| table_kind | table (62) | 62 |
| text | annex_heading (1), annex_note (7), bibliography_entry (3), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (1), form (26), form_field (201), form_number (13), form_placeholder (6), form_subfield (40), form_subtitle (14), form_title (21), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), list_item (98), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (812), place_and_date (20), proposal_basis (5), recipient (96), recipients (17), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62) | 1667 |
| title | annex (5), article (94), chapter (15), clause (267), form (27), numbered_item (26), numbered_section (5), point (257) | 696 |
| title_evidence | article (86), chapter (15), numbered_item (12) | 113 |
| title_source_offset | article (7), chapter (1) | 8 |
| title_source_ref | article (7), chapter (12), form (12) | 31 |
| title_source_spans | chapter (2) | 2 |
| type | annex (5), annex_heading (1), annex_note (7), annexes (2), article (94), bibliography (1), bibliography_entry (3), body (5), chapter (15), clause (267), closing (5), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (10), form (27), form_field (201), form_header (19), form_number (13), form_placeholder (6), form_signature (3), form_subfield (40), form_subtitle (14), form_title (21), header (5), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), legal_document (5), list (26), list_item (98), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (812), place_and_date (20), point (257), preamble (5), proposal_basis (5), recipient (96), recipients (17), signature (5), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62), title_block (5) | 2401 |
| unit | form_subfield (3) | 3 |
| value_text | form_field (201), form_subfield (40) | 241 |

Properties occurring once, manually reviewed:

- semantic: Known source signature_marker [daky] expresses signed status without inferring the signer.

## Retained form-label candidates

- 365/2026/NĐ-CP, source order 1729: NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT CỦA THƯƠNG NHÂN — short_label_outside_confirmed_input_sequence.
- 365/2026/NĐ-CP, source order 2396: NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT CỦA THƯƠNG NHÂN — short_label_outside_confirmed_input_sequence.
- 365/2026/NĐ-CP, source order 4688: NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT — short_label_outside_confirmed_input_sequence.
- 365/2026/NĐ-CP, source order 4719: TÊN THƯƠNG NHÂN — short_label_outside_confirmed_input_sequence.
- 365/2026/NĐ-CP, source order 5048: NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT — short_label_outside_confirmed_input_sequence.
- 365/2026/NĐ-CP, source order 5267: NGƯỜI ĐẠI DIỆN THEO — short_label_outside_confirmed_input_sequence.
- 365/2026/NĐ-CP, source order 5742: NGƯỜI ĐẠI DIỆN THEO — short_label_outside_confirmed_input_sequence.
- 365/2026/NĐ-CP, source order 5991: Số lượng nhập kho — short_label_outside_confirmed_input_sequence.
- 365/2026/NĐ-CP, source order 6001: Số lượng xuất kho — short_label_outside_confirmed_input_sequence.
- 365/2026/NĐ-CP, source order 6011: Số lượng tồn kho — short_label_outside_confirmed_input_sequence.
- 365/2026/NĐ-CP, source order 6413: NGƯỜI ĐẠI DIỆN THEO — short_label_outside_confirmed_input_sequence.
- 365/2026/NĐ-CP, source order 6669: NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT CỦA THƯƠNG NHÂN — short_label_outside_confirmed_input_sequence.
- 60/2026/TT-BCT, source order 1311: NGƯỜI RÀ SOÁT — short_label_outside_confirmed_input_sequence.
- 60/2026/TT-BCT, source order 1437: Thông tin kiểm tra: — introductory_prose_for_following_content.
- 60/2026/TT-BCT, source order 1616: NGƯỜI KIỂM TRA — short_label_outside_confirmed_input_sequence.
- 60/2026/TT-BCT, source order 2745: Đã nộp mẫu vật vào cơ quan lưu trữ gồm: — introductory_prose_for_following_content.
- 60/2026/TT-BCT, source order 2905: Tài liệu kèm theo: — introductory_prose_for_following_content.
- 60/2026/TT-BCT, source order 5120: Người theo dõi Chủ nhiệm đề án — short_label_outside_confirmed_input_sequence.
- 60/2026/TT-BCT, source order 5468: Người theo dõi Chủ nhiệm đề án — short_label_outside_confirmed_input_sequence.
- 60/2026/TT-BCT, source order 5741: cấp ngày tháng năm .Tại: — attached_source_field_continuation.
- 60/2026/TT-BCT, source order 5789: NGƯỜI YÊU CẦU — short_label_outside_confirmed_input_sequence.

## Form boundaries

- 365/2026/NĐ-CP, annex None: form 01 → ĐƠN ĐỀ NGHỊ → 14 children → next 02.
- 365/2026/NĐ-CP, annex None: form 02 → GIẤY CHỨNG NHẬN → 21 children → next 03.
- 365/2026/NĐ-CP, annex None: form 03 → ĐƠN ĐỀ NGHỊ → 17 children → next 04.
- 365/2026/NĐ-CP, annex None: form 04 → GIẤY CHỨNG NHẬN → 22 children → next 05.
- 365/2026/NĐ-CP, annex None: form 05 → GIẤY CHỨNG NHẬN → 22 children → next 06.
- 365/2026/NĐ-CP, annex None: form 06 → BÁO CÁO TÌNH HÌNH KÝ KẾT VÀ THỰC HIỆN HỢP ĐỒNG XUẤT KHẨU GẠO → 14 children → next 07.
- 365/2026/NĐ-CP, annex None: form 07 → BÁO CÁO LƯỢNG THÓC, GẠO THỰC TẾ TỒN KHO → 16 children → next 08.
- 365/2026/NĐ-CP, annex None: form 08 → BÁO CÁO → 15 children → next 09.
- 365/2026/NĐ-CP, annex None: form 09 → THÔNG BÁO → 14 children → next 10.
- 365/2026/NĐ-CP, annex None: form 10 → BÁO CÁO → 12 children → next 11.
- 365/2026/NĐ-CP, annex None: form 11 → VĂN BẢN ĐỀ NGHỊ → 12 children → next None.
- 60/2026/TT-BCT, annex I: form 01 → Danh mục thông tin, dữ liệu giao nộp → 12 children → next 02.
- 60/2026/TT-BCT, annex I: form 02 → Thông báo kết quả kiểm tra, đối chiếu
thông tin, dữ liệu giao nộp → 13 children → next 03.
- 60/2026/TT-BCT, annex I: form 03 → Thông báo kết quả kiểm tra mẫu vật địa chất, khoáng sản,
mẫu vật bảo tàng giao nộp → 13 children → next 04.
- 60/2026/TT-BCT, annex I: form 04 → Biên bản giao nhận thông tin, dữ liệu
địa chất, khoáng sản nộp lưu trữ → 20 children → next 05.
- 60/2026/TT-BCT, annex I: form 05 → Biên bản giao nhận mẫu vậtđịa chất, khoáng sản, mẫuvậtbảo tàng → 20 children → next None.
- 60/2026/TT-BCT, annex II: form 01 → Bìa 1 Thuyết minh tài liệu, báo cáo → 2 children → next 02.
- 60/2026/TT-BCT, annex II: form 02 → Bìa 2 Thuyết minh tài liệu, báo cáo → 11 children → next 03.
- 60/2026/TT-BCT, annex II: form 03 → Danh mục tài liệu tham khảo → 3 children → next 04.
- 60/2026/TT-BCT, annex II: form 04 → Danh mục các phụ lục kèm theo → 2 children → next 05.
- 60/2026/TT-BCT, annex II: form 05 → Danh mục bản vẽ kèm theo → 3 children → next 06.
- 60/2026/TT-BCT, annex II: form 06 → Danh mục tài liệu nguyên thủy → 3 children → next None.
- 60/2026/TT-BCT, annex III: form 01 → Nhật ký địa chất → 10 children → next 02.
- 60/2026/TT-BCT, annex III: form 02 → Sổ mô tả công trình khai đào (dọn vết lộ, hào, hố, lò, giếng) → 7 children → next 03.
- 60/2026/TT-BCT, annex III: form 03 → Thiết đồ theo dõi, mô tả công trình khoan → 5 children → next 04.
- 60/2026/TT-BCT, annex III: form 04 → Thiết đồ tổng hợp công trình khoan → 5 children → next None.
- 60/2026/TT-BCT, annex IV: form None → PHIẾU YÊU CẦU CUNG CẤP THÔNG TIN, DỮ LIỆU ĐỊA CHẤT, KHOÁNG SẢN → 16 children → next None.

Combined content.json size: 2,844,016 → 2,869,297 bytes. Physical geometry, effective text, actual empty cells and provenance remain intact. The JSON report contains cell/property counts and contributor estimates.

Tests cover flat dash/plus lists, nested parent/child markers, source-backed continuations, unrelated trailing prose, isolated signs, inline arithmetic, table/heading/form/annex boundaries, form-input ownership, links/annotations, nested cell lists, complete note consumption, non-mutating note lookahead, tight recipient dashes, corrupted serialized output and all five full captured fixtures. The audit independently reparses all 20 RAW tabs twice, compares artifact bytes, validates all 25 JSON files, checks manifest/source/output hashes and compares all acceptance invariants.

Remaining limits: isolated markers and uncertain continuation ownership are kept conservatively. Two previously recorded source ambiguities in other fixtures remain warnings. Broader multi-document validation is still required.

Extract V2.3.2 finalization passed for the current regression fixture.
Ready for broader multi-document validation.
