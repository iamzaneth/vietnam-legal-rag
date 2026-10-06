# Kiểm tra EXTRACT 2.3.2

Đọc lại toàn bộ JSON đã ghi, đối chiếu raw SHA-256, source text, source order, provenance, schema và parent. Parse lại từng tab hai lần rồi so bytes với artifact.

| Văn bản | Điều | Khoản | Điểm | Phụ lục | Section phụ lục | Item phụ lục | Depth | Orphan | Bảng ambiguous | Warning | Error/fatal | Text | Deterministic |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 16111 /QĐ-BCT | 3 | 2 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 1 | 0 | true | true |
| 365/2026/NĐ-CP | 28 | 80 | 110 | 1 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | true | true |
| 59/2026/TT-BCT | 45 | 145 | 142 | 0 | 0 | 0 | 5 | 0 | 0 | 1 | 0 | true | true |
| 60/2026/TT-BCT | 15 | 36 | 5 | 4 | 5 | 26 | 5 | 0 | 0 | 0 | 0 | true | true |
| 34/2026/NQ-CP | 3 | 4 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | true | true |

Counts/warnings trong bảng lấy từ content.json. JSON report còn giữ counts tất cả tab, evidence promotion, title refs và review từng table.

| Metric content | Trước | Sau |
| --- | ---: | ---: |
| forms | 27 | 27 |
| fields | 202 | 202 |
| subfields | 40 | 40 |
| placeholders | 6 | 6 |
| footnotes | 54 | 54 |
| placeholder_references | 65 | 65 |
| unresolved_numbered_form_items | 0 | 0 |
| split_form_candidates | 0 | 0 |
| inconsistent_footnote_sequences | 0 | 0 |
| bibliography_fields_misclassified | 0 | 0 |
| structured_table_cell_lists | 4 | 4 |
| generic_structured_paragraphs | 2 | 2 |
| form_nodes_missing_field_kind | 27 | 0 |
| form_nodes_missing_field_evidence | 30 | 0 |
| suspicious_value_text | 0 | 0 |
| semantic_empty_string_fields | 0 | 0 |
| physical_empty_cells | 420 | 420 |
| unexplained_form_label_paragraphs | 0 | 0 |
| unexplained_structured_paragraphs | 0 | 0 |
| ignored_ui_artifacts | 4 | 4 |
| orphan_nodes | 0 | 0 |
| numbered_paragraph_candidates | 0 | 0 |
| generic_decimal_paragraphs | 0 | 0 |
| ambiguous_tables | 0 | 0 |
| warnings | 2 | 2 |
| errors | 0 | 0 |

Cây debug được in ra console cho mọi document; không tạo TXT trong extracted. Mẫu nhỏ:

```text
legal_document
├── header
│   ├── paragraph
│   ├── issuing_authority
│   ├── document_number 16111 /QĐ-BCT
│   ├── national_heading
│   ├── national_motto
│   └── place_and_date
├── title_block
│   ├── document_type_heading
│   ├── document_title
│   └── issuing_authority_title
├── preamble
│   ├── legal_basis
│   ├── legal_basis
│   ├── legal_basis
│   └── proposal_basis
├── enacting_formula
├── body
│   ├── article 1
│   │   └── paragraph
│   ├── article 2
│   │   └── paragraph
│   └── article 3
│       ├── clause 1
│       │   └── paragraph
│       └── clause 2
│           └── paragraph
└── closing
    ├── recipients
    │   ├── recipient
    │   ├── recipient
    │   ├── recipient
    │   ├── recipient
    │   ├── recipient
    │   └── recipient
    └── signature
        ├── delegation_title
        ├── signer_title
        ├── signature_status
        └── signer_name
```

Các issue còn giữ:

- 16111 /QĐ-BCT: possible_page_number (warning), source order 13. Bare source number retained; page-transition evidence is insufficient to remove it
- 59/2026/TT-BCT: table_semantics_unresolved (warning), source order 440. Inspect source header declarations or table purpose; effective text and cell geometry are preserved

Bảng matrix giữ compound labels và orientation unknown vì nguồn không khai báo trục đủ rõ. Dòng số đơn lẻ của Quyết định được giữ vì thiếu evidence page transition. Không có orphan/candidate khoản hoặc decimal paragraph chưa xử lý trong các phụ lục của corpus.

20 tab bảo toàn text và deterministic. Properties/history/relations giữ source records, URL, identifier, ngày, số hiệu và provenance so với baseline. Table kind/grid/raw cell text/text_segments/effective_text và legal/annex counts giữ nguyên.

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit
PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.ingestion.extract_legal_documents --debug-tree
PYTHONPATH=src .venv/bin/python scripts/audit_vbpl_hierarchy.py --raw data/raw/vbpl --extracted data/extracted/vbpl --sample 0c389a00-78f6-11f1-a726-87c913cf8f30 --report docs/extract-hierarchy.json
```
