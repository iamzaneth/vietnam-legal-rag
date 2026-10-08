# Đối chiếu EXTRACT VBPL 1.0.0 → 2.0.0

Đã chạy lại toàn bộ 5 văn bản hiện có trong raw, tạo 25 JSON (gồm manifest).
Tổng dung lượng giảm từ **11,838,191 xuống 2,065,778 byte**
(**82.55%**). Có **3,213 semantic elements**.
Issues: **33 info, 199 warning, 0 error, 0 fatal**.
Cả 5 document có status `success_with_warnings`.

| Số hiệu nguồn | JSON trước (byte) | JSON sau (byte) | Giảm | Semantic elements | info / warning / error / fatal |
| --- | ---: | ---: | ---: | ---: | --- |
| 16111/QĐ-BCT | 942,736 | 56,288 | 94.03% | 92 | 4 / 5 / 0 / 0 |
| 365/2026/NĐ-CP | 4,248,114 | 881,366 | 79.25% | 1,390 | 14 / 85 / 0 / 0 |
| 59/2026/TT-BCT | 1,982,379 | 384,821 | 80.59% | 518 | 4 / 28 / 0 / 0 |
| 60/2026/TT-BCT | 3,657,241 | 677,187 | 81.48% | 1,107 | 7 / 75 / 0 / 0 |
| 34/2026/NQ-CP | 1,007,721 | 66,116 | 93.44% | 106 | 4 / 6 / 0 / 0 |

Dung lượng đo bằng tổng bytes UTF-8 của các JSON, bao gồm manifest, không dùng
kích thước block cấp phát của filesystem. Chi tiết từng tab, text hash và issue
counts nằm trong [report JSON](extract-comparison.json).

Semantic element gồm node pháp luật/paragraph/list/table, cell, field, history
event, relation group/item và nhãn cột lịch sử nguồn. Không tính text leaf, inline
DOM wrapper, bản sao toàn văn, source reference hoặc issue như semantic element.

## Bảo toàn dữ liệu

- 20/20 JSON tab giữ toàn bộ meaningful source text theo source order: source
  và actual output projection có cùng dãy Unicode characters sau bỏ formatting
  whitespace. Mỗi tab lưu source/extracted text SHA-256 giống nhau.
- 26 file trong raw (20 HTML, 5 manifest, 1 gitkeep) có cùng bytes/checksum với
  snapshot trước refactor. Không sửa hoặc crawl lại source để làm validator pass.
- Raw identity giữ nguyên trong tất cả JSON; mọi source/output checksum hợp lệ.
  Tất cả output được kiểm tra lại với JSON Schema 2020-12.
- P rỗng/spacing không thành semantic node. UI capture headings, placeholder
  `--` và separator bị loại đều có audit. Dòng `2` của quyết định 16111/QĐ-BCT
  còn nguyên, role unknown và warning; không đoán là page number hoặc Khoản.
- Điều 1 và Điều 2 của quyết định 16111/QĐ-BCT giữ full body với title null;
  Điều 3 nhận title ngắn “Tổ chức thực hiện”. Bảng đầu/cuối là layout.
- Bảng/list lồng, các paragraph riêng trong cell, spans/sections và cell order
  vẫn có cấu trúc. Quan hệ header/value chưa có căn cứ không được khẳng định.
- Parser chạy hai lần trên từng tab và toàn bộ corpus được chạy lại: JSON bytes
  giống nhau. Validator đối chiếu actual serialized records, không dùng DOM backup
  hoặc text projection được lưu trùng trong JSON.

Các warning còn lại phản ánh nguồn thiếu URL/identifier, bảng chưa xác định
được data/layout/header hoặc membership đoạn tiếp nối chưa chắc. Không có
header thì không tự dựng axis. Compound header giữ labels nhưng không đoán
row_axis/column_axis. Unknown text vẫn nằm trong cây semantic hoặc context.
Bảo toàn text không đồng nghĩa mọi semantic role đã được resolve.

## Mẫu tab Các văn bản hợp nhất

Capture đã có của quyết định 157/2007/QĐ-TTg (`13205`) được chạy offline riêng,
không thêm hoặc sửa raw trong corpus chính. Cả 5 tab (content, properties,
history, relations, consolidated) đều giữ text đầy đủ; Tải về/Văn bản gốc
không được extract.

6 JSON của mẫu này giảm từ **3,184,685 xuống 176,206 byte**
(**94.47%**), có **195 semantic elements**,
**1 info / 79 warning / 0 error / 0 fatal**.
Consolidated giữ document cards, số 08/VBHN-BTC và ngày xác thực 22/04/2022;
card chứa cả 05/2022/QĐ-TTg và 157/2007/QĐ-TTg giữ cả hai candidate.
Source không có URL/identifier chắc chắn cho các card này: URL/resolved ID
vẫn null và có warning, không tự chọn target từ các số hiệu.

## Kiểm thử và chạy lại

71 unit tests pass, gồm crawler/tab policy và extract/validator. Các ca kiểm tra
bao gồm optional/malformed HTML, hierarchy thiếu cấp, số không theo thứ tự,
body/title, Unicode/NBSP, các đoạn ngoài Điều, duplicate field labels, direct
history values, ambiguous history table, relation count/placeholder/multiple
candidates, layout/compound headers, rowspan/colspan/overlap/gap/large grid,
nested tables/lists, superscript/subscript offsets và byte determinism.

```bash
.venv/bin/vbpl-extract
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -t .
.venv/bin/python scripts/compare_vbpl_extract.py \
  --before /tmp/vbpl-extract-before-v2/extracted/vbpl \
  --after data/extracted/vbpl \
  --raw data/raw/vbpl \
  --output /tmp/extract-comparison-rerun.json
```

Snapshot trước refactor ở `/tmp/vbpl-extract-before-v2/extracted/`; bản scoped
cũ còn ở `/tmp/vbpl-extract-before-v2/scoped-output-original/`.
Snapshot này là bản sao phục vụ đối chiếu, không phải input của parser và không
được đưa vào extracted. Mọi lần extract vẫn chỉ đọc HTML + manifest trong raw.
