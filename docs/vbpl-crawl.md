# Crawl và extract một văn bản từ vbpl.vn

Nguồn: <https://vbpl.vn>, bắt đầu từ <https://vbpl.vn/sitemap.xml>.

## Cài đặt và chạy

```bash
uv pip install --python .venv/bin/python -e '.[crawl]'
.venv/bin/vbpl-crawl-one
.venv/bin/vbpl-extract
```

Crawler mặc định dùng Google Chrome đã cài. Nếu dùng Chromium của Playwright:

```bash
.venv/bin/python -m playwright install chromium
.venv/bin/vbpl-crawl-one --channel chromium
```

Hoặc chạy trực tiếp từ mã nguồn, không cần cài lại entry point:

```bash
PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.ingestion.crawl_legal_documents
PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.ingestion.extract_legal_documents
```

## Bước crawl: raw

Module: `src/vietnam_legal_rag/ingestion/crawl_legal_documents.py`.
Mỗi lần chỉ crawl một văn bản, mặc định chọn văn bản đầu tiên trong sitemap.

Tùy chọn:

- `--url 'https://vbpl.vn/van-ban/chi-tiet/...'`: chọn URL cụ thể có trong sitemap.
  Chấp nhận URL có `?tabs=hop-nhat`; đối chiếu sitemap theo URL không có query/fragment.
- `--output data/raw/vbpl`: thư mục gốc raw của nguồn.
- `--channel chrome`: Chrome đã cài; dùng `chromium` cho Playwright Chromium.
- `--timeout 90`: thời gian chờ mỗi bước trong trình duyệt, tính bằng giây.
- `--headed`: hiển thị trình duyệt; cần môi trường có màn hình.

`--download-attachments` đã được bỏ: raw chỉ lưu HTML và manifest.
Crawler không mở tab Tải về và không lưu PDF/DOCX, TXT hoặc JSON dữ liệu tab vào raw.

Crawler đọc liên kết danh mục trong breadcrumb của trang văn bản:
`/van-ban/trung-uong` → `trung_uong`, `/van-ban/dia-phuong` → `dia_phuong`.
Không dùng menu chung, tên văn bản hay từ khóa trong toàn văn để phân loại.
Thiếu hoặc mâu thuẫn danh mục thì báo lỗi và giữ bản cũ.
Manifest ghi `document_scope` và `classification` để truy lại căn cứ phân loại.

```text
data/raw/vbpl/<trung_uong|dia_phuong>/<mã văn bản>/
├── content.html        # DOM toàn văn đã tải bằng trình duyệt
├── properties.html     # DOM tab Thuộc tính
├── relations.html      # DOM tab Lược đồ
├── history.html        # DOM tất cả trang của tab Lịch sử, nếu có
├── consolidated.html   # tab Các văn bản hợp nhất, nếu có
├── tab_<tên-tab>.html   # các tab bổ sung khác, nếu có
└── manifest.json       # nguồn, phân loại, thời điểm, tệp HTML và SHA-256
```

HTML mới giữ nguyên markup và thuộc tính của phần nội dung đã render;
bao bằng tài liệu HTML UTF-8. Không lưu HTML khung giao diện, screenshot,
sitemap XML hay nhật ký mạng. Các trang metadata được bao trong
`<section data-page="1">`, `data-page="2"`, ... để extract lại đúng phân trang.
Đây là DOM sau khi JavaScript chạy, không phải bytes phản hồi HTTP ban đầu.

Luồng crawl:

1. Đọc robots.txt và sitemap để chọn URL văn bản.
2. Mở trang bằng Playwright, chờ toàn văn và request dữ liệu ổn định.
3. Mở Nội dung trước, phân loại bằng breadcrumb và lưu HTML toàn văn.
4. Dò danh sách tab trong thanh tab của văn bản, mở tất cả tab còn lại ngoại trừ
   Tải về và Văn bản gốc; kiểm tra dữ liệu và đọc hết phân trang của từng tab.
5. Kiểm tra toàn văn không thay đổi, ghi manifest và SHA-256 của HTML.
6. Thay thế thư mục raw của văn bản sau khi toàn bộ lần crawl thành công.

## Bước extract: extracted

Module: `src/vietnam_legal_rag/ingestion/extract_legal_documents.py`.
Không cần Playwright hoặc mạng; chỉ đọc HTML và manifest đã lưu.

```bash
# Trích xuất toàn bộ văn bản đã có ở raw.
.venv/bin/vbpl-extract --input data/raw/vbpl --output data/extracted/vbpl

# Trích xuất một văn bản; --output vẫn là thư mục gốc của nguồn.
.venv/bin/vbpl-extract \
  --input data/raw/vbpl/trung_uong/<mã-văn-bản> \
  --output data/extracted/vbpl
```

```text
data/extracted/vbpl/<mã văn bản>/
├── content.json
├── properties.json
├── relations.json
├── history.json
├── consolidated.json          # nếu raw có tab hợp nhất
├── tab_<tên-tab>.json          # nếu raw có tab bổ sung
└── manifest.json
```

Extractor chỉ ghi JSON, đầu vào hoàn toàn từ HTML raw. Chạy lại sẽ thay thế
thư mục extracted sau khi xử lý thành công và loại bỏ TXT/JSON cũ của lần trước.
Mỗi JSON có document_id giống manifest raw, schema_version, parser_version,
source_ref và issues. Không ghi thời điểm chạy extract để output deterministic.

`content.json` giữ duy nhất `content`, cây semantic theo thứ bậc Phần → Chương
→ Mục → Tiểu mục → Điều → Khoản → Điểm; không bắt buộc đủ cấp, không sort số.
Paragraph, list và table giữ thứ tự nguồn. Dòng Điều chứa body không tự thành
title. P rỗng không thành semantic element; đoạn unknown vẫn được bảo toàn.

Table phân biệt data/layout/ambiguous, giữ cell geometry/spans/sections và
header semantics có căn cứ. Layout table có issue info, không yêu cầu axis.
Bảng/list lồng nhau giữ cấu trúc, không flatten hoặc sao chép toàn bộ DOM.

Properties giữ ordered fields với label/value nguồn. History giữ trực tiếp
ngày/trạng thái/văn bản nguồn; bảng mơ hồ vẫn là table trong context. Relations
giữ label_raw, relation_type_raw, declared_count, real items; bỏ placeholder
`--`, giữ mọi số hiệu candidate và URL/identifier, không tự resolve.
Tab hợp nhất giữ document cards cùng ngày xác thực; mọi tab vẫn riêng JSON.

Xem [schema extracted 2.1.0](extracted-schema.md),
[JSON Schema](../schemas/extracted.schema.json) và
[kết quả so sánh mẫu](extract-comparison.md).

Validator kiểm tra identity/checksum/schema, bảo toàn text từ actual output,
source order/hierarchy/table/count/duplicates và parse lặp deterministic.
Manifest lưu version, checksum, status, issue_summary và issue references.
Info-only là success; warning là success_with_warnings; error/fatal là failed.
Raw thiếu/hash sai giữ extracted cũ và trả diagnostic manifest failed ra stderr.
Parser/validator lỗi vẫn giữ dữ liệu parse được và source pointer, không tự sửa
source. CLI tiếp tục các văn bản khác và trả exit code 1 nếu có lỗi.

HTML legacy vẫn được hỗ trợ. Href/data-row-key đã bị bỏ khỏi raw không thể
phục hồi tại extract; parser giữ number candidates và warning khi thiếu source
identifier. Không lấy dữ liệu extracted cũ để bù. Không canonicalize/merge tab,
chunk, embedding hoặc dùng LLM. Sau khi cập nhật raw cần chạy lại extract.

## Hai lớp tiếp theo

`data/normalized/` và `data/chunks/` hiện chỉ có `.gitkeep`.
Chuẩn hóa và chia đoạn sẽ được xây dựng sau.

## Phạm vi và kiểm thử

Crawler hỗ trợ trang `/van-ban/chi-tiet/` có tab Nội dung và toàn văn dài ít nhất
300 ký tự. Các tab metadata được dò từ trang. Ảnh, OCR, tệp đính kèm và tab Văn bản gốc chưa nằm trong pipeline.
Website có thể trả 403 hoặc timeout; crawler báo lỗi và trả exit code 1.

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v
```

Kiểm thử bao gồm phân loại, chọn tab động và hai tab bị loại, crawl chỉ lưu HTML,
phân trang, URL có tham số chọn tab, extract offline và thẻ văn bản hợp nhất,
truy nguồn bằng hash, định tuyến hai nhóm và giữ kết quả cũ khi lỗi.
