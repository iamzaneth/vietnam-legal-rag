# Extract V2.3.1 freeze audit

Actual generated JSON was inspected after extraction. Independent checks reparse all 20 source tabs twice, compare artifact bytes, validate all 25 JSON files against Draft 2020-12, and compare V2.3.0 source hashes, legal/annex ancestry, URLs/identifiers and every physical table cell.

**Extract schema is ready to freeze.** This fixes the schema contract; source ambiguities remain explicit. Two existing warnings are retained in separate fixtures, with semantic_complete=false. The current Circular 60 fixture has no warnings/errors/fatals and semantic_complete=true.

Versions: schema **2.3.1**, parser **2.3.1**. No extraction pipeline redesign.

| Fixture | Articles | Clauses | Points | Annexes | Sections / items | Orphans | Ambiguous | W / E / F | Text / deterministic / schema / order | Semantic complete |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- |
| 16111 /QĐ-BCT | 3 | 2 | 0 | 0 | 0 / 0 | 0 | 0 | 1 / 0 / 0 | true / true / true / true | false |
| 365/2026/NĐ-CP | 28 | 80 | 110 | 1 | 0 / 0 | 0 | 0 | 0 / 0 / 0 | true / true / true / true | true |
| 59/2026/TT-BCT | 45 | 145 | 142 | 0 | 0 / 0 | 0 | 0 | 1 / 0 / 0 | true / true / true / true | false |
| 60/2026/TT-BCT | 15 | 36 | 5 | 4 | 5 / 26 | 0 | 0 | 0 / 0 / 0 | true / true / true / true | true |
| 34/2026/NQ-CP | 3 | 4 | 0 | 0 | 0 / 0 | 0 | 0 | 0 / 0 / 0 | true / true / true / true | true |

| Metric | V2.3.0 | V2.3.1 |
| --- | ---: | ---: |
| generic_form_label_paragraphs | 11 | 0 |
| generic_form_fields_including_values | 22 | 0 |
| duplicated_references | 13 | 0 |
| empty_string_semantic_fields | 106 | 0 |
| singleton_source_refs | 13 | 0 |
| unexplained_structured_paragraphs | 0 | 0 |
| unexplained_form_label_paragraphs | 11 | 0 |
| subfields | 30 | 39 |
| inconsistent_footnote_sequences | 0 | 0 |
| split_form_candidates | 0 | 0 |
| bibliography_fields_misclassified | 0 | 0 |
| structured_table_cell_lists | 4 | 4 |
| ignored_ui_artifacts | 4 | 4 |
| warnings | 2 | 2 |
| errors | 0 | 0 |

## Stable vocabularies

**Produced node types:** `annex`, `annex_heading`, `annex_note`, `annexes`, `article`, `bibliography`, `bibliography_entry`, `body`, `chapter`, `clause`, `closing`, `delegation_title`, `document_number`, `document_title`, `document_type_heading`, `enacting_formula`, `footnote`, `footnote_group`, `form`, `form_field`, `form_header`, `form_number`, `form_placeholder`, `form_signature`, `form_subfield`, `form_subtitle`, `form_title`, `header`, `heading`, `issuing_authority`, `issuing_authority_title`, `legal_basis`, `legal_document`, `list`, `list_item`, `national_heading`, `national_motto`, `note`, `numbered_item`, `numbered_section`, `paragraph`, `place_and_date`, `point`, `preamble`, `proposal_basis`, `recipient`, `recipients`, `signature`, `signature_marker`, `signature_status`, `signer_name`, `signer_title`, `table`, `title_block`.

**Allowed table kinds:** layout, data, matrix, form, key_value, annex_form, ambiguous. Produced: {'annex_form': 59, 'key_value': 2, 'matrix': 1}; 23 layout tables represented as semantic sections.

**Allowed field kinds:** composite, display, input, input_label, instruction, unknown. Produced: {'composite': 3, 'display': 2, 'input': 127, 'input_label': 27, 'instruction': 41}.

**Produced fallbacks:** {'paragraph': 829}. Paragraph remains valid for prose. Unknown/numbered_paragraph remain supported fallbacks in the formal schema.

Removed redundant fields: boundary_evidence (replaced by evidence); field_kind declaration (replaced by display); footnote ordinal when identical to marker; singleton source_refs; unsplit source_offset=0; default title_source_offset=0; duplicate structural references. Legacy document_number_candidates was already absent and is now rejected. Primary and mentioned number extraction is unchanged.

## Semantic changes

| Type | Before | After |
| --- | ---: | ---: |
| form_field | 173 | 200 |
| form_subfield | 30 | 39 |
| heading | 5 | 8 |
| paragraph | 865 | 829 |

Every change is accounted for: existing paragraph input labels/value lines become form_field; three source coordinate groups contribute nine subfields; three emphasized certificate formulas become existing heading nodes; two prompts followed by explicit blanks become input labels; three semantic field nodes are added over retained simple-cell physical text (including one two-line cell). Legal hierarchy, annex paths, forms, footnotes, bibliography, lists and placeholder references are unchanged.

## Retained paragraphs

- 60/2026/TT-BCT, source order 1437: `Thông tin kiểm tra:` — `introductory_prose_for_following_content`.
- 60/2026/TT-BCT, source order 2745: `Đã nộp mẫu vật vào cơ quan lưu trữ gồm:` — `introductory_prose_for_following_content`.
- 60/2026/TT-BCT, source order 2905: `Tài liệu kèm theo:` — `introductory_prose_for_following_content`.
- 60/2026/TT-BCT, source order 5741: `cấp ngày tháng năm .Tại:` — `source_continuation_without_input_label`.
- 60/2026/TT-BCT, source order 4133: `- Tài liệu công trình khai đào.` — `isolated_marker_without_adjacent_sequence`.
- 60/2026/TT-BCT, source order 4172: `- Tài liệu công trình khoan` — `isolated_marker_without_adjacent_sequence`.

Emphasized CHỨNG NHẬN formulas are heading nodes. Remaining introductory statements remain prose rather than invented input fields. The incomplete source fragment ending .Tại: is a continuation without a reliable field name. Two isolated dash headings are separated by substantive content and cannot be merged into one adjacent list.

## Property vocabulary

| Property | Types (count) | Total |
| --- | --- | ---: |
| annotations | form_field (1), form_number (1) | 2 |
| cells | table (62) | 62 |
| children | annex (5), annex_heading (1), annex_note (7), annexes (2), article (94), bibliography (1), bibliography_entry (3), body (5), chapter (15), clause (267), closing (5), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (10), form (27), form_field (200), form_header (19), form_number (13), form_placeholder (6), form_signature (3), form_subfield (39), form_subtitle (14), form_title (21), header (5), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), legal_document (5), list (19), list_item (66), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (829), place_and_date (20), point (257), preamble (5), proposal_basis (5), recipient (86), recipients (17), signature (5), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62), title_block (5) | 2367 |
| classification_evidence | table (62) | 62 |
| evidence | article (94), chapter (15), clause (267), form (27), point (257) | 660 |
| field_evidence | form_field (200), form_subfield (9) | 209 |
| field_kind | form_field (200), form_subfield (12) | 212 |
| field_name | form_field (200), form_subfield (24) | 224 |
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
| order | annex (5), annex_heading (1), annex_note (7), annexes (2), article (94), bibliography (1), bibliography_entry (3), body (5), chapter (15), clause (267), closing (5), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (10), form (27), form_field (200), form_header (19), form_number (13), form_placeholder (6), form_signature (3), form_subfield (39), form_subtitle (14), form_title (21), header (5), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), legal_document (5), list (19), list_item (66), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (829), place_and_date (20), point (257), preamble (5), proposal_basis (5), recipient (86), recipients (17), signature (5), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62), title_block (5) | 2367 |
| parent_number | numbered_item (26) | 26 |
| placeholder_refs | form_field (29), form_placeholder (3), form_subfield (2), paragraph (17), place_and_date (5) | 56 |
| promotion_evidence | clause (42) | 42 |
| references | annex_note (1), document_number (1), legal_basis (15), paragraph (10) | 27 |
| row_groups | table (62) | 62 |
| semantic | signature_marker (1) | 1 |
| semantics | table (62) | 62 |
| source_layouts | annexes (2), closing (5), header (5) | 12 |
| source_offset | delegation_title (2), document_title (1), document_type_heading (1), form_field (2), issuing_authority (1), national_heading (3), national_motto (3), paragraph (534), signer_name (1), signer_title (3) | 551 |
| source_ref | annex (5), annex_heading (1), annex_note (7), annexes (2), article (94), bibliography (1), bibliography_entry (3), body (5), chapter (15), clause (267), closing (5), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (10), form (27), form_field (200), form_header (19), form_number (13), form_placeholder (6), form_signature (3), form_subfield (39), form_subtitle (14), form_title (21), header (5), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), legal_document (5), list (19), list_item (66), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (829), place_and_date (20), point (257), preamble (5), proposal_basis (5), recipient (86), recipients (17), signature (5), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62), title_block (5) | 2367 |
| source_refs | chapter (11) | 11 |
| style | bibliography (1), list (19) | 20 |
| table_id | table (62) | 62 |
| table_kind | table (62) | 62 |
| text | annex_heading (1), annex_note (7), bibliography_entry (3), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (1), form (26), form_field (200), form_number (13), form_placeholder (6), form_subfield (39), form_subtitle (14), form_title (21), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), list_item (66), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (829), place_and_date (20), proposal_basis (5), recipient (86), recipients (17), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62) | 1640 |
| title | annex (5), article (94), chapter (15), clause (267), form (27), numbered_item (26), numbered_section (5), point (257) | 696 |
| title_evidence | article (86), chapter (15), numbered_item (12) | 113 |
| title_ref | form (12) | 12 |
| title_source_offset | article (7), chapter (1) | 8 |
| title_source_ref | article (7), chapter (12) | 19 |
| title_source_spans | chapter (2) | 2 |
| type | annex (5), annex_heading (1), annex_note (7), annexes (2), article (94), bibliography (1), bibliography_entry (3), body (5), chapter (15), clause (267), closing (5), delegation_title (7), document_number (5), document_title (5), document_type_heading (5), enacting_formula (5), footnote (54), footnote_group (10), form (27), form_field (200), form_header (19), form_number (13), form_placeholder (6), form_signature (3), form_subfield (39), form_subtitle (14), form_title (21), header (5), heading (8), issuing_authority (16), issuing_authority_title (1), legal_basis (23), legal_document (5), list (19), list_item (66), national_heading (17), national_motto (17), note (15), numbered_item (26), numbered_section (5), paragraph (829), place_and_date (20), point (257), preamble (5), proposal_basis (5), recipient (86), recipients (17), signature (5), signature_marker (1), signature_status (1), signer_name (5), signer_title (8), table (62), title_block (5) | 2367 |
| unit | form_subfield (3) | 3 |
| value_text | form_field (200), form_subfield (24) | 224 |

Physical cell properties (separate physical contract): `association_status` (30), `cell_id` (1123), `cell_type` (1123), `colspan` (1123), `column` (1123), `column_axis` (1), `confidence` (1123), `content` (85), `effective_text` (1123), `evidence` (705), `labels` (1), `order` (1123), `orientation` (1), `original_colspan` (1123), `original_rowspan` (1123), `role` (1123), `row` (1123), `row_axis` (1), `row_group_id` (1123), `rowspan` (1123), `section` (1123), `source_ref` (1123), `text` (1123), `text_segments` (1123).

Rare properties reviewed: title_source_spans/title_source_ref/title_ref preserve distinct merged-title/alias provenance; promotion_evidence preserves legal inference; annotations preserve inline notation; source_layouts audits semanticized tables; list numbering preserves source list attributes; semantic describes known signature markers. No typo spelling or arbitrary field_kind found.

## Size and physical data

Combined content.json bytes: **2,908,607 → 2,931,475**. New field metadata explains the net size increase; duplication cleanup is not a compression target. Per-fixture contributor estimates are in the JSON report.

Physical cell.text, effective_text and text_segments are source measurements: an original empty cell or nested-content sentinel can retain empty strings. Semantic scalar absence uses null; optional properties can be omitted; blank placeholders remain source strings. Cell semantics never changes rectangles or effective text. One ragged annex-form grid retains the source colspan=17 row under a 21-column header; uncovered slots carry no invented value or asserted axis association, so its diagnostic is informational.

## Validation and reproduction

159 unit tests pass (25 new V2.3.1 tests; existing metadata/null and cell-field expectations updated). Tests cover form scoping, field names/values, composite coordinates, raw cell preservation, reference ownership, provenance/offset cleanup, idempotence, enum failures, legacy rejection, and metadata conservation. Actual output validation is independent of tests.

Files changed: schema_cleanup.py; extract_legal_documents.py; extract_quality.py; extract_validation.py; structured_html.py; form_refinement.py; form_validation.py; table_semantics.py; schemas/extracted.schema.json; audit_vbpl_hierarchy.py; audit_extract_schema.py; test_schema_cleanup.py; test_form_refinement.py; test_extract_legal_documents.py; README.md; extracted-schema.md; generated Extract JSON and audit reports. The packaged schema symlink continues to reference the same formal schema.

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit
PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.ingestion.extract_legal_documents --debug-tree
PYTHONPATH=src .venv/bin/python scripts/audit_extract_schema.py --raw data/raw/vbpl --extracted data/extracted/vbpl --before /path/to/v2.3.0/extracted --report docs/extract-v2.3.1-schema-audit.json
```
