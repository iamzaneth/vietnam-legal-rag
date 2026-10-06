# EXTRACT V2.2 — kết quả kiểm tra artifact

Parser **2.2.0**, schema **2.2.0**. Đã chạy lại tất cả 5 raw captures, đọc lại 20
JSON tab và 5 manifests, in cây debug cho từng văn bản, rồi đối chiếu raw, schema,
source order, provenance, text SHA-256 và JSON bytes của hai lần parse độc lập.
Không có TXT trong extracted. Kết quả máy đọc: [extract-hierarchy.json](extract-hierarchy.json).
Cây mẫu và số liệu: [extract-hierarchy.md](extract-hierarchy.md).

## Fixtures thực tế

Các counts và issues dưới đây lấy từ `content.json` đã ghi, không lấy từ test expectations.

| Văn bản | Điều | Khoản | Điểm | Annex | Numbered section | Numbered item | Max depth | Orphan | Ambiguous table | Info | Warning | Error/fatal | Text preserved | Deterministic |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 16111 /QĐ-BCT | 3 | 2 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 2 | 1 | 0 | true | true |
| 365/2026/NĐ-CP | 28 | 80 | 110 | 1 | 0 | 0 | 5 | 0 | 0 | 38 | 0 | 0 | true | true |
| 59/2026/TT-BCT | 45 | 145 | 142 | 0 | 0 | 0 | 5 | 0 | 0 | 2 | 1 | 0 | true | true |
| 60/2026/TT-BCT | 15 | 36 | 5 | 4 | 5 | 26 | 5 | 0 | 0 | 39 | 0 | 0 | true | true |
| 34/2026/NQ-CP | 3 | 4 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 2 | 0 | 0 | true | true |

Depth tính cạnh từ document qua sections và legal/annex numbered nodes; content,
table, list và form wrappers không cộng thêm level. Annex number_path depth của
Thông tư 60 là **2**. Cả 20 tab: **93 info, 2 warning, 0 error, 0 fatal**.
`schema_valid`, `order_valid`, `parent_child_valid` đều true. Quyết định 16111 và
Thông tư 59 có status `valid_with_warnings`, semantic_complete false; ba văn bản
còn lại có status `valid`, semantic_complete true.

## Trước → sau, cùng các captures

Baseline là output V2.1 lưu trước khi sửa. Metrics chỉ tính content.json.

| Metric | V2.1 | V2.2 |
| --- | ---: | ---: |
| Orphan nodes | 18 | 0 |
| Numbered paragraph có candidate_role clause | 42 | 0 |
| Generic decimal paragraph | 26 | 0 |
| Ambiguous table | 62 | 0 |
| Warning | 189 | 2 |

| Văn bản | Orphan | Candidate khoản | Decimal paragraph | Ambiguous table | Warning |
| --- | --- | --- | --- | --- | --- |
| 16111 /QĐ-BCT | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 1 → 1 |
| 365/2026/NĐ-CP | 18 → 0 | 5 → 0 | 0 → 0 | 27 → 0 | 78 → 0 |
| 59/2026/TT-BCT | 0 → 0 | 34 → 0 | 0 → 0 | 1 → 0 | 37 → 1 |
| 60/2026/TT-BCT | 0 → 0 | 3 → 0 | 26 → 0 | 34 → 0 | 73 → 0 |
| 34/2026/NQ-CP | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 |

## Evidence từ JSON đã sinh

- Nghị định 365: source orders **738** và **847** được promotion từ numbered
  paragraph thành Khoản 1 trong Điều 23/24. Các điểm a/b/c và điểm tiếp theo được
  gắn vào các khoản nguồn này; không tạo parent giả. Tổng 18 orphan points đã sửa.
- Thông tư 60: annex I/II/III/IV là children của `annexes`, tách khỏi closing.
  Annex II có sections 1/2/3 với 16 items; annex III có sections 1/2 với 10 items.
  `2.1`, `2.2`, `2.3` là numbered_item dưới section 2, với number_path và prefix parent.
  Không còn generic decimal paragraph hoặc legal clause/point trong annex.
- Combined `THÔNG TƯ Quy định...` ở source order **53** đã tách document type/title.
  Sentence enactment là section riêng trong mọi capture. Split chapter titles giữ
  source_refs/title_source_spans; Điều 19 của Nghị định có title từ heading markup
  kết hợp child legal structure. Các fixture split Article/Chapter riêng được
  serialize rồi validate trong tests.
- Thông tư 59: `table_440` giữ grid **7 × 6** và toàn bộ source cell rectangles.
  Corner `cell_446` vẫn giữ original text rỗng và nested paragraphs; effective_text
  chứa đầy đủ bảy fragments. Hai compound labels được nối đúng; orientation
  unknown, row_axis/column_axis null vì thiếu evidence khai báo trục.
- Cả **62** non-layout tables giữ nguyên geometry/source cells so với baseline:
  **59 annex_form**, **2 key_value**, **1 matrix**. Annex forms không có data axes
  suy đoán. **23** layout tables giữ source_layout provenance trong semantic sections.
- Properties/history/relations của mọi capture giữ source records, ngày, URL,
  identifiers, số hiệu, source order và provenance; mọi source text SHA-256 bằng
  baseline. Luật có tên nhận primary number trước các số hiệu được nhắc sau đó.
  Legacy document_number_candidates đã bỏ khỏi schema và outputs.

Hai warning còn giữ: source order **13** của Quyết định là dòng `2`, thiếu page
transition evidence để loại bỏ; matrix của Thông tư 59 thiếu evidence về hướng trục.
Không còn orphan cần giải thích. Không thay text để làm hierarchy đẹp hơn.

## Tests và files của lần refactor này

**108 tests qua**, gồm **19 tests mới** tại
[test_semantic_refinement.py](../tests/unit/test_semantic_refinement.py).
Các tests phủ annex scope/prefix/sequence, deep/zero-padded counters, clause
promotion và list boundaries, missing parent, split/long titles, cả 10 document
type prefixes, sentence enactment, effective text/nested tables, matrix axes,
annex forms, dash lists, footnotes, page artifacts, signature marker và named Laws.
Các tests V2.1 được chuyển sang metrics/schema V2.2 và severity fatal cho lost text.

Files parser/validator đã sửa hoặc thêm:

- `src/vietnam_legal_rag/ingestion/semantic_refinement.py` — thêm second pass.
- `src/vietnam_legal_rag/ingestion/table_semantics.py` — thêm effective text/table kinds.
- `src/vietnam_legal_rag/ingestion/structured_html.py`
- `src/vietnam_legal_rag/ingestion/legal_hierarchy.py`
- `src/vietnam_legal_rag/ingestion/html_tables.py`
- `src/vietnam_legal_rag/ingestion/hierarchy_validation.py`
- `src/vietnam_legal_rag/ingestion/extract_validation.py`
- `src/vietnam_legal_rag/ingestion/extract_quality.py`
- `src/vietnam_legal_rag/ingestion/vbpl_tabs.py`
- `src/vietnam_legal_rag/ingestion/extract_legal_documents.py`

Schema/audit/tests/docs:

- `schemas/extracted.schema.json` và schema package symlink hiện có.
- `scripts/audit_vbpl_hierarchy.py`
- `tests/unit/test_semantic_refinement.py`
- `tests/unit/test_legal_hierarchy.py`
- `tests/unit/test_structured_html.py`
- `tests/unit/test_extract_legal_documents.py`
- `README.md`, `docs/extracted-schema.md`, `docs/extract-hierarchy.json`,
  `docs/extract-hierarchy.md`, `docs/extract-v2.2-report.md`.
- Sinh lại **20 JSON tab + 5 manifests** trong `data/extracted/vbpl/`.

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit
PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.ingestion.extract_legal_documents --debug-tree
PYTHONPATH=src .venv/bin/python scripts/audit_vbpl_hierarchy.py \
  --raw data/raw/vbpl --extracted data/extracted/vbpl \
  --sample 0c389a00-78f6-11f1-a726-87c913cf8f30 \
  --report docs/extract-hierarchy.json
```

Audit nhận thêm `--before <snapshot V2.1>` để kiểm tra source-record/grid regression
và tính delta. Các delta trong báo cáo hiện tại đã được kiểm tra với snapshot này.
