# EXTRACT V2.3 — form semantics và kiểm tra JSON thực tế

Parser **2.3.0**, schema **2.3.0**. Tiếp tục từ V2.2 bằng scoped form refinement;
giữ nguyên physical extraction, provenance, legal/annex hierarchy, clause promotion,
effective-cell pipeline và properties/history/relations. Không dùng LLM, không
special-case số hiệu hoặc nội dung fixture, không tạo field/parent thiếu nguồn.

Đã chạy extraction bốn vòng vào staging để inspect/repair, sau đó sinh lại tất cả
**20 JSON tab + 5 manifests**. Audit đọc artifact đã ghi, validate schema, raw
SHA-256, text projection, source order, legal parents, form semantics và provenance;
parse từng tab độc lập hai lần rồi so bytes với chính artifact. Cây debug và form
boundaries được in console/log; không lưu TXT trong extracted.

Evidence máy đọc: [extract-hierarchy.json](extract-hierarchy.json). Counts pháp lý,
tree mẫu và các issue: [extract-hierarchy.md](extract-hierarchy.md). JSON report
giữ mọi form boundary, footnote group, table review và structured paragraph còn lại.

## V2.2 → V2.3, cùng nguồn

Baseline là bản sao output V2.2 trước khi sửa. Metrics tính trên content.json;
structured marker gồm digit, decimal, alphabetic, dash và standalone ↩ ở paragraph.
UI metric tính ignored_elements có reason navigation_artifact, gồm cả backlinks
trước đây nằm trong list_item nên không nằm trong paragraph metric.

| Metric | V2.2 | V2.3 |
| --- | ---: | ---: |
| Generic structured paragraphs | 61 | 2 |
| Structured paragraphs chưa có lý do hợp lệ | 51 | 0 |
| Inconsistent footnote sequences | 9 | 0 |
| Form subfields | 0 | 30 |
| Possible split form | 5 | 0 |
| Bibliography entries sai thành form_field | 3 | 0 |
| Structured table-cell lists | 0 | 4 |
| Ignored UI artifacts | 0 | 4 |
| Footnotes | 25 | 54 |
| Form placeholders | 0 | 6 |
| Placeholder references | 0 | 65 |
| Unresolved numbered form items | 24 | 0 |
| Forms | 28 | 27 |
| Fields | 68 | 173 |
| Warnings | 2 | 2 |
| Errors/fatal | 0 | 0 |
| Orphan nodes | 0 | 0 |
| Clause candidates còn chờ promotion | 0 | 0 |
| Generic decimal paragraphs | 0 | 0 |
| Ambiguous tables | 0 | 0 |
| meaningful_text_preserved, mọi tab | true | true |
| Deterministic, mọi tab | true | true |

Form count giảm ròng một: Nghị định có 11 source captions thật thay vì 10 forms
V2.2; Thông tư 60 có 16 forms thay vì 18 do hai heading BIÊN BẢN được giữ trong
Mẫu 04/05. Không dùng mục tiêu count để tạo cấu trúc.

## Từng fixture thực tế

| Văn bản | Điều | Khoản | Điểm | Annex | Annex section/item | Form | Field/subfield | Footnote | Cell list | Orphan | Ambiguous | Warning/error | Text | Deterministic |
| --- | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| 16111 /QĐ-BCT | 3 | 2 | 0 | 0 | 0/0 | 0 | 0/0 | 0 | 0 | 0 | 0 | 1/0 | true | true |
| 365/2026/NĐ-CP | 28 | 80 | 110 | 1 | 0/0 | 11 | 117/26 | 2 | 3 | 0 | 0 | 0/0 | true | true |
| 59/2026/TT-BCT | 45 | 145 | 142 | 0 | 0/0 | 0 | 0/0 | 0 | 0 | 0 | 0 | 1/0 | true | true |
| 60/2026/TT-BCT | 15 | 36 | 5 | 4 | 5/26 | 16 | 56/4 | 52 | 1 | 0 | 0 | 0/0 | true | true |
| 34/2026/NQ-CP | 3 | 4 | 0 | 0 | 0/0 | 0 | 0/0 | 0 | 0 | 0 | 0 | 0/0 | true | true |

| Fixture | Structured paragraphs | Inconsistent notes | Subfields | Split forms | Sai bibliography | Cell lists | Ignored UI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 16111 /QĐ-BCT | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 |
| 365/2026/NĐ-CP | 49 → 0 | 0 → 0 | 0 → 26 | 3 → 0 | 0 → 0 | 0 → 3 | 0 → 2 |
| 59/2026/TT-BCT | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 1 |
| 60/2026/TT-BCT | 12 → 2 | 9 → 0 | 0 → 4 | 2 → 0 | 3 → 0 | 0 → 1 | 0 → 1 |
| 34/2026/NQ-CP | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 |

Max legal/annex hierarchy depth vẫn **3/5/5/5/3**, lần lượt theo bảng trên.
Annex number-path max depth của Thông tư 60 vẫn **2**. Mọi fixture có
schema_valid/order_valid/parent_child_valid true và form_validation.semantic_complete
true. Hai fixture có warning cũ giữ hierarchy status valid_with_warnings, không
được báo semantic_complete true cho toàn document. Cả 20 tab: **93 info, 2 warning,
0 error, 0 fatal**.

## Acceptance evidence đọc từ content.json

- **Footnote sequence:** Thông tư 60, Annex I Mẫu 01 giữ một footnote_group với
  marker 1/2/3/4/5; “2 Địa danh.” thành marker `2`, text `Địa danh.`, label `2`.
  Tất cả 9 chuỗi mixed roles trước đây đã repair; 52 footnotes của Thông tư được
  kiểm tra trong chính JSON. Note groups không mượn markers từ form kế tiếp.
- **Subfield:** Annex III Mẫu 01 “Nhật ký địa chất”, form_field 2 giữ a/b/c/d
  ở source orders 4383/4392/4401/4406. Field 3 kế tiếp không nằm trong subfield d.
  Nghị định có thêm 26 subfields; các table giữa a/b giữ đúng vị trí và geometry.
- **Boundary/title:** Annex I Mẫu 04 tại order 1669 giữ BIÊN BẢN (1742) và displayed
  subtitle trong cùng form; Mẫu 05 (2628) tương tự. Nghị định nhận đủ các caption
  Unicode tổ hợp `Mẫu số`, forms 01…11; displayed headings thành form_title,
  không tạo sibling form mới. Mọi boundary/next number/child count nằm trong report JSON.
- **Bibliography:** Annex II Mẫu 03 tại order 3458 có bibliography với ba
  bibliography_entry; không có form_field ở ba entries này. Generic factual
  numbered list dùng list/list_item, không tự thành input field.
- **Cell lists:** Thông tư, table cell chứa Dọn vết lộ/Hào/Giếng/Lò có ordered list
  1…4. Ba dash lists của Nghị định được group trong cell. Cell raw text, ordered
  text_segments, effective_text và grid rectangles giống V2.2 byte-for-value;
  table_kind vẫn được xác định trước bước local cell refinement.
- **Navigation:** ↩ ở em source orders 6697/6704 của Nghị định, 1879 của Thông tư 59
  và 5829 của Thông tư 60 nằm trong ignored_elements với reason navigation_artifact.
  Không còn ↩ trong semantic text/list_item. Hai footnote descriptions của Nghị
  định được giữ. Plain symbols trong legal prose không bị blacklist.
- **Heading/body:** Annex II numbered_item 1.1 “Văn bản pháp lý” và các short
  sibling headings có title, text rỗng và dependent paragraphs. Full sentence
  numbered items 2.1/2.2/2.3 vẫn giữ semantic text, không tự thành title.
- **V2.2 regression:** Counts Điều/Khoản/Điểm, annex number paths, promotion evidence,
  title_block, enactment section, annexes ngoài closing giữ nguyên. Tất cả **62**
  non-layout tables giữ kind/grid/source cells/raw text/segments/effective text:
  **59 annex_form**, **2 key_value**, **1 matrix**. Annex forms không được ép axes.
  Properties/history/relations của 5 captures giống V2.2 ở mọi field, kể cả primary/
  mentioned document numbers, bỏ qua duy nhất parser_version/schema_version.

SHA-256 của raw files không đổi. Meaningful-text SHA-256 của ba content tabs có
backlinks thay đổi đúng bốn source characters được audit; checksum source/output
sau exclusions vẫn bằng nhau. Audit đối chiếu projection cũ với raw cũ, kiểm tra
từng leaf bị loại và đối chiếu projection mới với raw trừ đúng các ignored leaves.
Không nới conservation thành so tập từ hoặc bỏ qua sai khác không giải thích được.

## Hai structured paragraphs được giữ

Thông tư 60, Annex III → section 1 → numbered_item 1.6:

| Source order | Text | Lý do |
| --- | --- | --- |
| 4133 | - Tài liệu công trình khai đào. | Dash label theo sau bởi các đoạn marker “+” và prose; không có adjacent dash sequence. |
| 4172 | - Tài liệu công trình khoan | Dash label theo sau bởi prose và các đoạn marker “+”; tách khỏi dòng 4133 bởi nhiều source blocks. |

Giữ paragraph source-faithful vì rule nhóm dash yêu cầu sequence liền kề, không
merge qua thuyết minh hoặc một marker khác. `structured_paragraph_audit` ghi
scope/reason/neighbors/source_ref cho cả hai; không còn marker paragraph chưa được
giải thích. Generic prose vẫn được giữ trong legal body, annex và forms.

Warning cũ còn giữ: Quyết định có số đơn lẻ `2` ở order 13, thiếu page-transition
evidence; matrix của Thông tư 59 thiếu evidence hướng trục. Không có warning mới
về form/footnote/bibliography, không còn orphan cần giải thích.

## Files và tests

**134 unit tests pass**, gồm **26 tests mới** tại
[test_form_refinement.py](../tests/unit/test_form_refinement.py). Phủ note sequence
mixed typography, note scopes, alpha/dash notes, marker/body và superscript provenance,
subfields/dot/Vietnamese markers, table-separated subfields, discontinuous markers,
catalog/display boundaries, Unicode tổ hợp, prose citations, headers/date placeholders,
blank authority và subject cùng header layout table không đóng title region quá sớm,
bibliography/factual lists, cell lists/grid/effective text, nonsequential candidates,
annex heading/body, navigation positives/negatives, placeholder refs và independent
validators phát hiện partial footnotes/split forms/bibliography misclassification.
108 tests V2.2 vẫn pass, không đổi expectations của chúng.

Files thêm/sửa của V2.3:

- `src/vietnam_legal_rag/ingestion/form_refinement.py` — pass mới trong pipeline hiện có.
- `src/vietnam_legal_rag/ingestion/form_validation.py` — form checks và paragraph audit.
- `src/vietnam_legal_rag/ingestion/semantic_refinement.py` — form boundary/candidate handling và gọi pass mới.
- `src/vietnam_legal_rag/ingestion/structured_html.py` — navigation audit, empty wrappers, parser/schema version.
- `src/vietnam_legal_rag/ingestion/extract_quality.py` — projection source title alias đúng một lần.
- `src/vietnam_legal_rag/ingestion/table_semantics.py` — giữ effective text khi có title alias.
- `src/vietnam_legal_rag/ingestion/extract_validation.py` — tích hợp independent form validator.
- `schemas/extracted.schema.json` — node types/refs/metrics/audit V2.3; package schema symlink hiện có.
- `tests/unit/test_form_refinement.py`, `scripts/audit_vbpl_hierarchy.py`.
- `README.md`, `docs/extracted-schema.md`, `docs/extract-hierarchy.json`,
  `docs/extract-hierarchy.md`, `docs/extract-v2.3-report.md`.
- Sinh lại 25 JSON artifacts trong `data/extracted/vbpl/`.

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit
PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.ingestion.extract_legal_documents --debug-tree
PYTHONPATH=src .venv/bin/python scripts/audit_vbpl_hierarchy.py \
  --raw data/raw/vbpl --extracted data/extracted/vbpl \
  --sample 0c389a00-78f6-11f1-a726-87c913cf8f30 \
  --before <snapshot-V2.2>/extracted --report docs/extract-hierarchy.json
```

Audit cũng chạy được không có --before để kiểm tra lại toàn bộ actual artifacts;
before/after của báo cáo này đã được chạy với snapshot V2.2 trong cùng workspace session.
