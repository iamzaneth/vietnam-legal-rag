# Extract schema 2.3.2

Extract is source-faithful semantic parsing. RAW HTML and its manifest remain the source of truth. EXTRACTED identifies source-backed structure without rewriting legal meaning, correcting spelling, inventing data, resolving cross-document references, summarizing, chunking or generating embeddings. Normalized will perform canonical field mapping and cross-tab merge; Chunks will create retrieval units and any deterministic structural IDs.

Formal contract: [Draft 2020-12 JSON Schema](../schemas/extracted.schema.json). The packaged schema references this same file. Acceptance specification: [Extract finalization](EXTRACTION_FINALIZATION_SPEC.md). Latest actual-output verification: [finalization audit](extract-v2.3.2-finalization-audit.md), [machine-readable audit](extract-v2.3.2-finalization-audit.json). Earlier audits: [form invariant hotfix](extract-v2.3.2-form-invariant-audit.md), [V2.3.2 cleanup](extract-v2.3.2-schema-audit.md), [V2.2](extract-v2.2-report.md), [V2.3](extract-v2.3-report.md).

## Artifacts and envelope

Each raw capture produces `content.json`, `properties.json`, `history.json`, `relations.json` and `manifest.json`; optional captured tabs can produce additional JSON. No HTML backup or debug TXT is written to extracted. The directory name and document_id come from the raw manifest.

All artifacts carry schema_version=2.3.2, parser_version=2.3.2, document_id, tab, source_url, source_ref and issues. File provenance uses `{layer: raw, path, sha256}`, where path is relative to the raw root. Source URL is the tab URL when available. Repeated extraction of identical source and metadata must produce identical bytes; extraction timestamps are not added.

## Common node contract

Semantic nodes retain `type`, `order`, a primary `source_ref`, and `children` (an empty array when there are no children). Other properties apply only when relevant: number, label, title, text, source_refs, source_offset and type-specific metadata. Physical cells use `content`, not a fabricated legal hierarchy.

| Property | Responsibility |
| --- | --- |
| order | Original source-order anchor; never renumbered during refinement. |
| source_ref | Main source element: dom_order, tag, line, column. File/path/checksum are inherited from the artifact envelope. |
| source_refs | Multiple distinct contributing elements, in source order, including primary first. Omitted for a singleton. |
| source_offset | Character offset within a source text unit that was split semantically. Zero is retained only for a real split. Not a byte offset. |
| number | Extracted source counter, including Roman numerals where present. |
| label | Source structural marker, such as Điều 5, 1., a), Mẫu số 04. or 2.1. |
| title | Associated heading. Not automatically the entire substantive sentence following a counter. |
| text | Source display/body text. For list/footnote markers, label owns the marker and text owns the body. |
| references | Source href, absolute URL, identifiers and anchor provenance, owned once by the node containing the actual text. |
| annotations | Source superscript/subscript positions; label_annotations/title_annotations keep their respective text offsets. |

**Absence convention:** stable semantic scalar fields use null when their value is absent; optional type-specific fields may be omitted. Empty strings must not represent semantic absence. Arrays stay []. Meaningful blank placeholders such as …… remain strings. Physical cell.text/effective_text can retain original empty strings as source measurements or the existing nested-content sentinel; these are not absent semantic scalars.

Sibling ordering is ascending `(order, source_offset default 0)`. Containers can share the first child's source_ref without duplicating its textual content. Coalesced titles retain title_source_ref and/or title_source_spans; displayed form title aliases also use title_source_ref and are projected only by the matching displayed child. title_ref is forbidden. Source spelling, numbers, punctuation, hyperlinks and meaningful Unicode are preserved.

## Node families

`content.json` has one `document: legal_document` tree. It never also stores a flat content array.

```text
legal_document
├── header
├── title_block
├── preamble
├── enacting_formula
├── body
├── closing
└── annexes
    └── annex[]
```

Sections are optional and source-backed. Header contains issuing_authority, document_number, national_heading, national_motto and place_and_date. Title block groups document_type_heading/document_title/issuing_authority_title; a combined source paragraph can be split with offsets. Preamble groups legal_basis/proposal_basis. Literal and deterministic sentence-form enacting_formula establish the body boundary. Closing groups recipients/recipient and signature children delegation_title/signer_title/signature_status/signature_marker/signer_name. `[daky]` indicates signed, without inventing identity.

Legal body levels are part=10 → chapter=20 → section=30 → subsection=40 → article=50 → clause=60 → point=70. Missing levels are allowed. Paragraph/list/table are content, not legal levels. A stack plus second-pass sequence/point/style evidence controls attachment; source DOM nesting does not determine legal nesting. Uncertain numbering remains numbered_paragraph with candidate_role/evidence, or an explicitly unresolved source node. Synthetic clauses are never created to repair points.

Annex hierarchy is separate: annex → numbered_section → numbered_item. `2.1.3` has number_path=[2,1,3], level=3 and parent_number=2.1 only when that preceding prefix exists in the same annex. Annex numbers are not converted from Roman numerals into paths. annex_heading and annex_note retain headings and accompanying enactment notes. Annexes appearing after signatures belong under annexes, outside closing. Short source-backed item headings can use title with null text; full substantive sentences retain text.

## Forms and fields

Form boundaries require a source numbered Mẫu/Biểu/Phiếu caption, or a supported standalone displayed form heading when no numbered form is active. Internal BIÊN BẢN/THÔNG BÁO headings become form_title/form_subtitle, not new forms. Catalog form.title and displayed title/subtitle are retained separately.

```text
form
├── form_header
├── form_title / form_subtitle
├── form_field
│   └── form_subfield[]
├── form_placeholder
├── table
├── note / footnote_group
├── bibliography / list
└── form_signature
```

Form headers scope authority, national heading/motto, form_number and date independently of the main document header. field_name preserves the source name, such as Đơn vị chủ đầu tư; no canonical key mapping occurs. value_text is exclusively a clearly separable source value/placeholder, otherwise null. It never contains another input prompt or completion instruction; instruction fields always use null. A nested prompt can become a source-offset-backed form_subfield. A leading source blank followed by fixed prose/other prompts yields only that blank as value_text; the complete source display stays in text. text retains the source field display. placeholder_refs records explicit `(1)`/`(2)` markers without resolving their meaning.

| field_kind | Meaning |
| --- | --- |
| input | A value or fillable blank exists. |
| input_label | Source input label with implicit/empty value. |
| instruction | Instructions for completing/using the form. |
| composite | Source field with subfields, such as contiguous X/Y/H coordinates. |
| display | Fixed informational/declaration content. |
| unknown | Field evidence is insufficient for a more specific role. |

Every form_field and form_subfield explicitly carries field_name, field_kind, field_evidence and value_text. Source label/value classification is shared by both node families; unknown names/values stay null, and insufficient role evidence uses the existing unknown enum with source-backed classification evidence. The same enum applies wherever field_kind is emitted. Confirmed Form/annex_form context plus label evidence controls classification; a colon outside that scope is insufficient. An adjacent explicit form_placeholder can substantiate an otherwise unknown input prompt. A short noun-like label without a colon requires a continuous sequence bounded by compatible input fields/blanks. Optional source qualifiers remain in text; field_name can exclude the qualifier. An issued-document continuation may attach to the preceding number/code field, keeping the source fragment intact when date/place labels are not explicit. Emphasized uppercase internal formulas can remain heading nodes. Composite coordinates require continuous compatible source axes and blanks/values; no missing axis is invented and no cell boundary is crossed. Explicit units are retained. Alpha a/b/c/d sequences remain form_subfields of their compatible source field.

## Lists, notes and safe fallbacks

Local ordered/dash/plus sequences of at least two source-compatible markers become list/list_item, including inside table cells. Dash parents own following plus sublists. Lists are recognized before form inputs; genuine input prompts may remain source-backed form_field children of their list_item. Unmarked continuations require a heading-like item or colon lead-in, continuous source flow, no stronger semantic boundary and a compatible following marker. Trailing prose and isolated markers remain conservative paragraphs. A single dash parent plus a single explicit plus child can form a source-backed nested list; no parent is invented.

Explicit references headings use bibliography/bibliography_entry rather than form_field. After Ghi chú/Chú thích/Notes, sequence-aware footnote_group/footnote classification covers consecutive markers consistently, regardless of typography. note can contain alphabetic/dash/plus explanations. HTML-generated ordinal markers are metadata rather than invented visible source text. An explicit recipient heading scopes recipient markers, including tight dashes introduced by inline markup; tight source display stays intact to preserve cell effective_text.

Genuine prose remains paragraph. heading, unknown, numbered_paragraph and layout_block are safe representations when more specific evidence is absent. Structured-paragraph and form-label audits must explain any retained marker/label candidate. The serialized structured audit includes plus markers and bounded continuation/nested-marker context; an unresolved sequence makes semantic_complete false and emits a warning. Navigation artifacts are ignored only with source link/navigation or terminal footnote-backlink context; ignored_elements retains reason, text, order and provenance. Plain symbols and form blanks are not globally blacklisted.

## Tables

Pipeline: physical cells → rowspan/colspan expansion → cell content → ordered text_segments/effective_text → kind classification → headers → compound candidates → axis inference → association validation.

Allowed table_kind: layout, data, matrix, form, key_value, annex_form, ambiguous. Layout tables become semantic document sections and can retain source_layouts for audit. Layout/form/annex_form/key_value kinds have no forced factual row/column axes and omit inapplicable role/confidence cell metadata. Data/matrix kinds retain meaningful cell classification. Matrix compound headers can preserve labels while orientation remains unknown.

Physical table representation retains deterministic table_id/cell_id, grid_shape, row_groups, row, column, rowspan/colspan, original span values, source_ref, raw text, text_segments and effective_text. There is no duplicate expanded grid. Nested paragraphs/lists/form fields/composites live in cell.content. Adding semantic cell content does not change geometry or effective_text. When meaningful cell.content represents a simple raw cell's display, text projection uses that semantic owner once while raw cell.text remains available.

Header_refs are asserted only with adequate geometry/source declarations; otherwise header_candidates and unknown association status remain explicit. Never infer axis direction from two phrases alone. Overlap is error; lost cell content is error; lost meaningful source text is fatal. Source grid gaps are not filled. An explainable ragged form grid with preserved cells and no asserted axis association can be informational; uncertain factual associations require warning.

## Properties, history and relations

Properties fields remain ordered `{label, value, order, source_ref, evidence}` records. Source labels are not canonicalized. Literal -- is preserved; genuine source duplicate labels are not merged, and parser-created duplicate fields are invalid. A structured value is represented by value_content, with scalar value null when it has no independent semantic text.

History events remain separate source rows; same date with different status does not merge. Source dates/status/document text, source_cells and provenance remain intact. Primary/mentioned document numbers are retained.

Relation items preserve text, url, primary_document_number_candidate, mentioned_document_numbers, resolved_document_id, resolution_status, order and source_ref. Primary number extraction includes `Luật <name> số <number>`, without consuming a later mentioned document. Candidate-only resolution is normal; no cross-document resolution is forced. Empty groups remain declared_count=0/items=[] with no fake -- item. Legacy document_number_candidates is forbidden; text can be null only when meaningful structured content owns the display.

## Evidence, quality and manifest

| Evidence property | Decision described |
| --- | --- |
| evidence | Assignment of structural type; replaces form boundary_evidence. |
| heading_evidence | Why source was treated as heading. |
| title_evidence | How the associated title was determined. |
| field_evidence | Why source was treated as form field/subfield. |
| classification_evidence | Table/form purpose classification. |
| promotion_evidence | Second-pass legal promotion with its evidence model. |

Keep separate decisions separate; do not duplicate one decision across evidence fields. Full source-derived arrays are not copied onto structural parents when their actual textual owner already carries them.

For compatibility issues still contains info/warning/error/fatal records. Info denotes extraction diagnostics, not unhealthy content. Manifest stores no duplicate full issue objects: tabs keep issue_refs and summaries. issue_summary and diagnostic_info_count/warning_count/error_count/fatal_count distinguish expected observations from actual problems. Status is success, success_with_warnings or failed.

Manifest quality has meaningful_text_preserved, deterministic, schema_valid and semantic_complete. The latter stays false when an actual source structural ambiguity remains, even if the schema and text are valid. hierarchy_validation separates schema/order/parent validity, completeness, status and legal/annex/table/unresolved counts; status is valid, valid_with_warnings or invalid. form_validation covers fields, subfields, placeholders, notes, split-form candidates, bibliography, structured lists, unexplained labels/markers and suspicious_value_text. form_nodes_missing_field_kind and form_nodes_missing_field_evidence must be zero; missing required field properties make semantic_complete false and fail schema validation. The recursive invariant audit covers exactly fields + subfields nodes, including those inside table cells. semantic_empty_string_fields scans semantic nodes only; physical_empty_cells counts cells whose raw text and effective text are both empty. Real empty physical cells remain source empty strings.

meaningful_text_preserved compares source_text_sha256 and extracted_text_sha256 from the **actual serialized semantic projection**, after audited ignored elements. Determinism is verified by repeated parsing. Every semantic node must have traceable primary provenance; there are no random node UUIDs. Debug trees and vocabularies are console/log output, not TXT artifacts in extracted.

## Validation

The formal JSON Schema validates content, properties, history, relations and manifests, with node-type conditionals, required legal numbers, source provenance, scalar absence, field_kind/table_kind enums and explicit rejection of obsolete fields. Safe source-faithful fallback types remain representable.

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -t .
PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.ingestion.extract_legal_documents --debug-tree
PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.cli audit schema --raw data/raw/vbpl --extracted data/extracted/vbpl --before /path/to/pre-hotfix/v2.3.2/extracted --report docs/extract-v2.3.2-form-invariant-audit.json
```

The freeze audit includes every available representative capture: simple Decision, Decree with annexes, technical Circular with a matrix, Circular with forms/decimal annex numbering, and Resolution. Passing tests alone is insufficient; generated JSON, fallback paragraphs, form boundaries, node/property vocabularies and metadata/table regressions are inspected independently.

## Broader source validation within V2.3.2

The [50-document batch report](../reports/extract-validation-50/report.md) records five interleaved Central/Local waves, generic parser repairs, source evidence, regression membership and final diagnostics. The schema and parser version remain 2.3.2: all observed structures fit the existing contract.

Explicit English legal labels and legacy spaced hyphen/slash counters use the same legal hierarchy as their Vietnamese counterparts. Quoted replacement provisions, contract articles and Roman/alphabetic local outlines keep their own counter scope. An attached legal act can retain intermediate signing and letterhead blocks in the canonical body without duplicating root document sections. Annex counters and nested lists stay within their source annex/form scope.

Source CSS emphasis, provision-heading classes and bold/shaded table header bands can support classification. Formula and symbol-definition tables retain their physical cells and spans using the existing key_value representation when the source supports that purpose; factual axes are never invented. Missing relation identifiers, headerless table axes, formula media, isolated possible page numbers, duplicated source legal numbers and incomplete quotations keep their diagnostics. For an incomplete quotation, an explicit next sequential amendment can bound local counters without inserting a closing mark.

The final batch has schema_valid, deterministic and meaningful_text_preserved at 50/50. semantic_complete remains 41/50 because nine reviewed documents retain source warnings; the report does not override that flag. The original golden fixture retains all expected invariants and zero warnings/errors/fatals.

Reproduce validation from the retained local RAW captures:

```bash
.venv/bin/python -m vietnam_legal_rag.cli validate --help
.venv/bin/python -m vietnam_legal_rag.cli validate audit --regenerate
.venv/bin/python -m unittest discover -s tests -t . -q
.venv/bin/python -m vietnam_legal_rag.cli validate report --output-dir reports/extract-validation-50/runtime/rebuilt
```

The batch audit exits nonzero when source warnings remain; review the diagnostics rather than treating command success as semantic acceptance. Capture regressions reference immutable local RAW by identity and hash, while portable pattern tests run without those captures. The crawler's existing HTML-only policy excludes Tải về and Văn bản gốc; attachment validation is outside this recorded batch.
