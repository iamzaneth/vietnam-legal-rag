# Extract V2.3.2 — Finalization Specification

## 1. Purpose

This document is the authoritative engineering specification for finalizing the **EXTRACTED** layer of the Vietnam Legal RAG project using source data from `vbpl.vn`.

The goal is **not** to redesign the pipeline. The goal is to finish the current Extract V2.3.2 implementation, remove known semantic defects, strengthen validation against similar defects, preserve all already-correct behavior, and leave the extractor in a state that is safe to freeze for broader corpus testing.

Pipeline boundary:

```text
RAW
→ EXTRACTED
→ NORMALIZED
→ CHUNKS
→ EMBEDDINGS / VECTOR DB
```

This task concerns **RAW → EXTRACTED only**.

## 2. Core principles

1. **RAW is immutable.**
   - Never rewrite or “clean” raw HTML to make parsing easier.
   - Source fidelity must be preserved.

2. **Generated extracted JSON must never be repaired manually.**
   - Fix parser/source code.
   - Regenerate output.
   - Validate regenerated output.

3. **Extraction is conservative.**
   - Unknown but source-faithful is better than inferred but wrong.
   - Never invent missing values, dates, identifiers, links, headings, table semantics, legal hierarchy, or form values.

4. **No LLM rewriting/paraphrasing of legal text.**
   - Preserve source wording and order.

5. **No fixture-specific hardcoding in production parser logic.**
   Production code must not special-case:
   - document UUID,
   - document number,
   - title,
   - exact literal sentence,
   - exact DOM order from one fixture.

   Fixture-specific expected counts/text are allowed in tests only.

6. **Determinism is mandatory.**
   Same RAW input + same parser version/config must produce the same semantic output.

7. **Preserve provenance.**
   Semantic nodes must retain appropriate `source_ref`, `order`, offsets, references, and evidence fields where defined by schema.

8. **Do not merge tabs in Extract.**
   Keep:
   - `content.json`
   - `properties.json`
   - `history.json`
   - `relations.json`
   - `manifest.json`

   Canonical merging belongs to the Normalized layer.

## 3. Schema/version boundary

Current schema contract:

```text
schema_version = 2.3.2
```

Do **not** create a broad V2.3.3 schema redesign merely to fix parser behavior.

If the current V2.3.2 schema can represent the source correctly, treat the problem as a parser bug and fix the parser.

Only change schema shape/version if a genuinely new source structure cannot be represented faithfully with the current contract.

If the repository treats `parser_version` as implementation/release identity, update it according to the project's existing versioning convention. Do not change version numbers merely to hide regressions.

## 4. Current representative fixture

Primary regression fixture:

```text
document_id:
vbpl:a9bea550-bbe3-11f1-a338-51a5cc429fc7

document:
Thông tư 60/2026/TT-BCT
```

Preserve all currently-correct behavior while fixing the remaining defects.

Stable legal hierarchy:

```text
chapters = 4
articles = 15
clauses = 36
points = 5
```

Stable annex hierarchy:

```text
annexes = 4
numbered_sections = 5
numbered_items = 26
max_depth = 2
```

Current form baseline before final list fix:

```text
forms = 16
form_field = 81
form_subfield = 14
footnotes = 52
placeholder_references = 65
```

Important:
- `forms = 16` and `footnotes = 52` are strong regression invariants.
- Exact `form_field` count may legitimately change if a currently misclassified `+` list entry becomes a `list_item`.
- Do not preserve an incorrect node type merely to keep the old count.

Current table baseline:

```text
layout = 5
key_value = 1
annex_form = 33
ambiguous = 0
```

Current unresolved baseline:

```text
numbered_candidates = 0
orphan_nodes = 0
ambiguous_tables = 0
```

## 5. Known remaining defect: structured `-` / `+` lists

This is the main known semantic defect and must be fixed generically.

Known source pattern:

```text
- Tài liệu công trình khai đào.
+ Sổ mô tả công trình ...
+ Các thông tin thể hiện trên bản vẽ ...
+ Quy cách thiết đồ công trình.
...
+ Nội dung thiết đồ công trình.
...
+ Ảnh chụp công trình ...

- Tài liệu công trình khoan
Tài liệu công trình khoan gồm: ...
+ Thiết đồ theo dõi lỗ khoan ...
+ Ảnh mẫu lõi khoan ...
+ Sổ mô tả tài liệu địa chất thủy văn - địa chất công trình ...
+ Tài liệu kết quả đo địa vật lý ...
```

The current extractor incorrectly leaves many of these as sibling generic `paragraph` nodes.

The current structured audit also treats the `-` parent items as:

```text
reason = isolated_marker_without_adjacent_sequence
justified = true
```

even though `+` children exist in the same semantic region. This is a validation blind spot.

### Required semantic behavior

When source evidence clearly supports a list, produce a structural list using the existing schema conventions.

Conceptually:

```text
list
├── list_item "-" Tài liệu công trình khai đào.
│   └── list
│       ├── list_item "+" Sổ mô tả ...
│       ├── list_item "+" Các thông tin ...
│       ├── list_item "+" Quy cách ...
│       │   └── continuation paragraph(s), when source-backed
│       ├── list_item "+" Nội dung ...
│       │   └── continuation paragraph(s), when source-backed
│       └── list_item "+" Ảnh chụp ...
└── list_item "-" Tài liệu công trình khoan
    ├── continuation paragraph "Tài liệu công trình khoan gồm: ..."
    └── list
        ├── list_item "+" Thiết đồ ...
        ├── list_item "+" Ảnh mẫu lõi ...
        ├── list_item "+" Sổ mô tả ...
        └── list_item "+" Tài liệu kết quả đo địa vật lý ...
```

Do not invent a new schema if existing `list` / `list_item` / child semantics already support this.

### Marker handling

At minimum detect leading source markers:

```text
-
+
```

only when they are leading list markers, not when those characters appear inside ordinary prose.

Use sequence + semantic parent + source adjacency/context, not literal text.

A list candidate is strong when:
- two or more nearby sibling/source-flow paragraphs use recognized list markers; or
- a parent marker is followed by a sequence of child markers; or
- source markup/indentation/list semantics provide additional evidence.

Do not force an isolated single marker into a list when there is insufficient evidence.

For:

```text
- parent
+ child
+ child
```

represent `+` entries as subordinate to the preceding `-` item. Do not flatten the hierarchy.

### Continuation paragraphs

A non-marker paragraph between one list item and the next marker may be a continuation of the current list item **only when source-flow evidence supports it**.

Example:

```text
- Tài liệu công trình khoan
Tài liệu công trình khoan gồm: ...
+ ...
```

The unmarked explanatory paragraph should remain associated with the `-` item rather than become an unrelated sibling outside the list.

Similarly, explanatory paragraphs following a `+` heading-like item may remain children/continuations of that item until the next same/higher-level marker when source evidence supports that grouping.

Be conservative: adjacency alone is not sufficient in every document.

## 6. Known remaining defect: `+` list semantics inside forms

Current fixture contains:

```text
Tài liệu kèm theo:
+ Phiếu mẫu vật địa chất: (ghi rõ số lượng phiếu).
+ Các tư liệu khác: ảnh chụp mẫu (số lượng); phiếu kết quả phân tích (số lượng).
```

Current output is inconsistent:
- first `+` entry is classified as `form_field` / `instruction`;
- second `+` entry remains a generic `paragraph`.

Required behavior:

1. Detect the list structure first.
2. Represent both `+` entries consistently as list items when the source indicates a list/checklist.
3. If an item also contains form/instruction semantics and the existing schema supports nested semantic children, preserve those semantics beneath/within the list item.
4. If the schema does not support a safe nested form semantic, prefer a faithful `list_item` over inventing a form input.
5. Do not classify a list label as a user-entered `value_text`.
6. Do not preserve the old field count merely to avoid regression-count changes.

## 7. Structured paragraph audit must be strengthened

Current defect:

```text
generic_structured_paragraphs = 2
unexplained_structured_paragraphs = 0
```

while multiple `+`-prefixed structured paragraphs remain generic paragraphs.

Required changes:

1. Audit all recognized leading structured markers, including `+`.
2. Audit actual semantic output, not only the old marker detector.
3. Distinguish:
   - genuinely isolated/ambiguous marker paragraph;
   - marker paragraph that belongs to a clear sequence and should have been structured.
4. A clear sequence left as generic `paragraph` must increment an unresolved metric and/or make `semantic_complete = false` according to current validation design.
5. Do not game the metric by marking unresolved nodes `justified=true` without source evidence.

After the known defect is fixed, the representative fixture must not contain unexplained generic structured paragraphs for the `-` / `+` sequences above.

## 8. Legal document structure requirements

Maintain:

```text
legal_document
├── header
├── title_block
├── preamble
├── enacting_formula
├── body
├── closing
└── annexes
```

Legal hierarchy:

```text
Phần
→ Chương
→ Mục
→ Tiểu mục
→ Điều
→ Khoản
→ Điểm
→ content
```

Rules:
- all levels optional;
- preserve source order;
- use explicit labels when present;
- second-pass structural inference must remain conservative;
- no orphan clause/point when a valid parent can be determined;
- do not promote ordinary numbered content solely because it begins with digits;
- annex/form numbering must not leak into legal body hierarchy.

## 9. Annex requirements

Annex hierarchy is separate from legal hierarchy.

Examples:

```text
1
→ 1.1
→ 1.1.1
```

Forms/templates are separate from legal Điều/Khoản/Điểm structure.

Do not misinterpret numbering inside annex/forms as legal hierarchy unless the source context is actually the legal body.

Preserve annex titles, notes, form boundaries, numbering, and source order.

## 10. Form requirements

For every:

```text
type == form_field
or
type == form_subfield
```

the node must explicitly contain:

```text
field_name
field_kind
field_evidence
value_text
```

`value_text` may be `null` when no actual value/placeholder is present.

`field_kind` and `field_evidence` must not be omitted.

Follow the current field-kind vocabulary, including:

```text
input
input_label
instruction
composite
display
unknown
```

Do not use `unknown` merely as a default when deterministic evidence exists.

`value_text` must contain a source-provided value or source placeholder/input region. It must not contain another field label, synthetic text, or an empty string used instead of semantic null.

Composite coordinate fields such as X/Y/H must remain structured subfields with source-backed units.

Do not split one logical form into multiple forms because of decorative tables/headings/blank regions.

Preserve footnote sequence, reference markers, source order, and form-local association.

Do not merge bibliography/reference sections into form fields.

## 11. Table requirements

RAW HTML remains the fidelity source.

Extract logical grid while preserving physical source geometry.

Preserve at minimum:

```text
row
column
rowspan
colspan
text / effective_text
source_ref
```

and existing geometry metadata already used by the current schema.

Rules:
1. Reconstruct rowspan/colspan deterministically.
2. Do not invent values for uncovered logical slots.
3. Preserve nested tables.
4. Keep diagnostics for irregular grids.
5. Do not flatten meaningful tables into prose.
6. Do not invent row/column axis semantics when unavailable.
7. For layout/form/annex-form/key-value tables where axis roles are not applicable, do not emit meaningless:
   - `role = "unknown"`
   - `confidence = 0.0`
8. Header semantics only when deterministic source evidence supports them.
9. Better to mark ambiguity than create a false retrieval fact.

If retrieval-oriented table facts are produced, they must preserve:

```text
value + row context + column context + table context
```

## 12. Properties tab requirements

Extract source labels/values conservatively.

Preserve raw source sentinel values such as:

```text
"--"
```

in Extract. Canonical conversion to null belongs to Normalized.

Preserve:

```text
label
value
order
source_ref
evidence
```

Do not canonicalize labels into Normalized-style keys in Extract unless already required by schema.

## 13. History tab requirements

Preserve events in source order.

Retain:

```text
date
status
source_document
source_ref
source_cells
```

For source-document numbers:
- distinguish primary referenced number from additional mentioned numbers;
- never invent URL or resolved document ID;
- retain `null` when unavailable.

## 14. Relations tab requirements

Preserve every source relation group, including zero-count groups.

For each group preserve:

```text
label_raw
relation_type_raw
declared_count
items
order
source_ref
```

Rules:
1. `declared_count` must match extracted meaningful item count when the source count is reliable.
2. Source placeholder `--` is not a relation item.
3. Keep `--` only as ignored/source evidence where applicable.
4. Do not invent links.
5. If source has no usable href, `url = null` is correct.
6. Distinguish:
   - `primary_document_number_candidate`
   - `mentioned_document_numbers`
7. Do not reintroduce legacy `document_number_candidates` if current schema replaced it.
8. `resolved_document_id` stays null unless deterministic resolution exists.
9. `resolution_status = candidate_only` is appropriate when only a textual candidate exists.
10. Do not canonicalize `relation_type_raw` in Extract.

## 15. References and document-number extraction

Reference extraction must be deterministic and context-aware.

Example:

```text
Nghị quyết số 15/2026/NQ-CP
... Nghị định số 46/2026/NĐ-CP ...
... Nghị quyết số 66.13/2026/NQ-CP ...
```

Conceptual result:

```text
primary_document_number_candidate = 15/2026/NQ-CP
mentioned_document_numbers = [
  46/2026/NĐ-CP,
  66.13/2026/NQ-CP
]
```

Do not greedily treat all document numbers in one sentence as equivalent primaries.

Support legitimate Vietnamese legal-number patterns, including decimal-like resolution numbers, without confusing dates/ratios/table values for document numbers.

## 16. Text fidelity and ignored elements

Continue to satisfy:

```text
meaningful_text_preserved = true
source_text_sha256 == extracted_text_sha256
```

for the representative fixture under the project's existing fidelity definition.

Navigation/UI artifacts may be ignored only with explicit reason and provenance.

Do not silently drop source text that carries legal/form meaning.

## 17. Diagnostics and severity

Severity vocabulary:

```text
info
warning
error
fatal
```

Overall status:

```text
success
success_with_warnings
failed
```

Informational diagnostics are allowed.

For the representative fixture final acceptance requires:

```text
warning = 0
error = 0
fatal = 0
```

Do not hide a real structural defect by downgrading it merely to make acceptance pass.

## 18. Validation invariants

Final representative fixture must satisfy:

```text
meaningful_text_preserved = true
schema_valid = true
deterministic = true
semantic_complete = true
order_valid = true
parent_child_valid = true
hierarchy status = valid

warning = 0
error = 0
fatal = 0
```

Form-related final requirements:

```text
form_nodes_missing_field_kind = 0
form_nodes_missing_field_evidence = 0
suspicious_value_text = 0
semantic_empty_string_fields = 0
unexplained_form_label_paragraphs = 0
unexplained_structured_paragraphs = 0
```

The structured-list audit must additionally prove there is no clear `-` / `+` sequence left as generic sibling paragraphs.

## 19. Required tests

Add/adjust tests that protect the general rule.

### A. Simple flat dash list

```text
- A
- B
- C
```

Expected: one list with three list items.

### B. Nested dash/plus list

```text
- Parent A
+ Child A1
+ Child A2
- Parent B
+ Child B1
```

Expected: two parent items; plus items nested beneath the correct parent.

### C. Parent with continuation

```text
- Parent
Explanatory continuation paragraph
+ Child
```

Expected: continuation remains associated with Parent when source-flow evidence is sufficient.

### D. Isolated marker

```text
- One isolated source paragraph
```

with no supporting sequence/context.

Expected: do not force structure solely from marker; preserve conservatively and audit honestly.

### E. Plus list inside form context

```text
Tài liệu kèm theo:
+ Item 1
+ Item 2
```

Expected: consistent treatment; one item must not become form_field while its sibling remains paragraph without source evidence.

### F. Plus/minus inside ordinary prose

Mathematical signs, hyphenated prose, ranges, or inline symbols must not become list items unless the symbol is a valid leading list marker with structural evidence.

### G. Existing full regression fixture

Re-run full representative document and verify stable legal/annex/form/table invariants.

## 20. Required self-review procedure

Do not stop after the first code edit.

Perform:

```text
inspect current code/schema/tests
→ inspect RAW source around failing structures
→ fix parser generically
→ add/update tests
→ run targeted tests
→ rerun extractor from RAW
→ inspect actual regenerated JSON
→ recursively audit semantic tree
→ run full relevant tests
→ compare regression invariants
→ repeat if any acceptance criterion fails
```

Do not merely report that the code “should” work.

The regenerated JSON is the evidence.

## 21. Required recursive audit before completion

Before declaring success, recursively inspect regenerated `content.json` and verify:

1. No `form_field` / `form_subfield` missing:
   - `field_name`
   - `field_kind`
   - `field_evidence`
   - `value_text`
2. No deprecated `title_ref` remains if convention is `title_source_ref`.
3. No meaningless:
   - `role: "unknown"`
   - `confidence: 0.0`
   on tables where semantics are not applicable.
4. No semantic empty string where null/absence is required.
5. No suspicious label text stored as `value_text`.
6. No clear structured marker sequence (`-`, `+`) remains as generic sibling paragraphs.
7. No newly introduced orphan hierarchy nodes.
8. No unresolved numbered candidates for the representative fixture.
9. Source order remains valid.
10. All five Extract outputs share correct identity/schema version.

## 22. Regression expectations for the current fixture

After list fix, preserve:

```text
chapters = 4
articles = 15
clauses = 36
points = 5

annexes = 4
numbered_sections = 5
numbered_items = 26

forms = 16
footnotes = 52

orphan_nodes = 0
ambiguous_tables = 0
numbered_candidates = 0

warning = 0
error = 0
fatal = 0
```

Do **not** blindly require old:

```text
fields = 81
```

if correcting form-local `+` list legitimately changes that count.

Report final count and why it changed.

## 23. Scope control

Do not:
- start Normalized implementation;
- start chunking;
- start embeddings;
- redesign crawler;
- change RAW storage naming;
- merge tabs;
- add LLM-based semantic rewriting;
- add broad speculative abstractions unrelated to demonstrated extraction needs.

Keep work focused on finishing Extract V2.3.2 correctly.

## 24. Completion criteria

Task is complete only when:

1. Known `-` / `+` structured-list defects are fixed generically.
2. Form-local `+` list inconsistency is fixed.
3. Structured-paragraph audit can catch these defects if they regress.
4. Representative fixture is regenerated from RAW.
5. Source text fidelity remains intact.
6. Legal hierarchy remains stable.
7. Annex hierarchy remains stable.
8. Forms/footnotes remain semantically correct.
9. Tables do not regress.
10. Properties/history/relations do not regress.
11. All relevant tests pass.
12. Recursive final audit finds no remaining known structural inconsistency.
13. No acceptance criterion was weakened merely to obtain green output.

Only then report:

```text
Extract V2.3.2 finalization passed for the current regression fixture.
Ready for broader multi-document validation.
```

If any requirement cannot be satisfied without a real schema change, do **not**
silently redesign the schema. Explain the exact schema limitation and the smallest
proposed change, with evidence from RAW and generated output.
