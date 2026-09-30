# Crawl nội dung một văn bản từ vbpl.vn

Nguồn: <https://vbpl.vn>, bắt đầu từ <https://vbpl.vn/sitemap.xml>.

## Cài đặt và chạy

```bash
uv pip install --python .venv/bin/python -e '.[crawl]'
.venv/bin/vbpl-crawl-one
```

Mặc định dùng Google Chrome đã cài. Nếu dùng Chromium của Playwright:

```bash
.venv/bin/python -m playwright install chromium
.venv/bin/vbpl-crawl-one --channel chromium
```

Hoặc chạy trực tiếp từ mã nguồn:

```bash
PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.ingestion.crawl_legal_documents
```

Tùy chọn:

- `--url 'https://vbpl.vn/van-ban/chi-tiet/...'`: chọn URL cụ thể có trong sitemap.
- `--download-attachments`: tải thêm PDF/DOCX và các tệp đính kèm; mặc định bỏ qua.
- `--output data/raw/vbpl`: thư mục gốc lưu kết quả.
- `--timeout 90`: thời gian chờ mỗi bước trong trình duyệt, tính bằng giây.
- `--headed`: hiển thị trình duyệt; cần môi trường có màn hình.

Mặc định chọn văn bản đầu tiên trong sitemap. Mỗi lệnh chỉ crawl một văn bản.

## Phân loại trung ương và địa phương

Module crawler: `src/vietnam_legal_rag/ingestion/crawl_legal_documents.py`.
Lệnh `vbpl-crawl-one` vẫn được giữ để tương thích.

Crawler đọc liên kết danh mục trong breadcrumb của trang văn bản:
`/van-ban/trung-uong` → `trung_uong`, `/van-ban/dia-phuong` → `dia_phuong`.
Không dùng menu chung, tên văn bản hay từ khóa trong toàn văn để phân loại.
Thiếu hoặc mâu thuẫn danh mục thì báo lỗi, không xuất kết quả và giữ bản cũ.
Manifest ghi `document_scope` và `classification` để truy lại căn cứ phân loại.

```text
data/raw/vbpl/
├── trung_uong/
│   └── <mã văn bản>/
└── dia_phuong/
    └── <mã văn bản>/
```

`--output` là thư mục gốc của nguồn; crawler tự thêm nhóm và mã văn bản.

## Dữ liệu đầu ra

```text
data/raw/vbpl/<trung_uong|dia_phuong>/<mã văn bản>/
├── content.html        # toàn văn HTML sạch, mở trực tiếp offline
├── content.txt         # toàn văn UTF-8, đọc bằng trình soạn thảo
├── properties.html / .txt / .json  # Thuộc tính
├── relations.html / .txt / .json   # Lược đồ
├── history.html / .txt / .json     # Lịch sử (gộp tất cả trang nếu phân trang)
├── attachments/        # chỉ tạo khi bật --download-attachments và có tệp
└── manifest.json       # nguồn, thời điểm, danh sách tệp và SHA-256
```

HTML đầu ra chỉ giữ nội dung và cấu trúc như đoạn văn, tiêu đề, bảng, danh sách,
chỉ số trên/dưới và liên kết tham chiếu. Liên kết tương đối được chuyển thành
URL đầy đủ của nguồn. CSS, thuộc tính style/class, JavaScript, giao diện điều hướng
và các thành phần tương tác được loại bỏ. HTML và TXT là bản nội dung đã trích
xuất. Mặc định lưu toàn văn, ba tab Thuộc tính/Lược đồ/Lịch sử và manifest; không mở tab Tải về.
Khi bật `--download-attachments`, tệp đính kèm giữ nguyên bytes tải về.
Manifest ghi `attachment_policy: "skip"`, `attachments: []`,
`expected_attachments: null` và `all_listed_attachments_downloaded: null`
khi bỏ qua; `null` nghĩa là không kiểm tra, không có nghĩa nguồn không có tệp.
Khi bật tải, policy là `"download"` và số tệp được kiểm tra như trước.

Mỗi văn bản có một thư mục theo mã định danh trên website. Chạy lại cùng văn bản
sẽ thay thế thư mục đó sau khi thu thập thành công. Chạy lại ở chế độ mặc định
cũng loại bỏ tệp đính kèm của lần tải trước. Nếu lỗi, dữ liệu tạm tự dọn
và bản thành công trước đó được giữ nguyên. Không tạo thư mục kết quả theo thời
gian cho mỗi lần chạy.

## Cách lấy nội dung động

1. Đọc `robots.txt` và sitemap đến khi tìm được URL văn bản.
2. Mở trang bằng Playwright/Chrome, chạy JavaScript để tải toàn văn.
3. Chờ phần nội dung, các request dữ liệu hoàn tất và nội dung ổn định.
4. Trích riêng phần toàn văn thành HTML sạch và TXT.
5. Mở lần lượt Thuộc tính, Lược đồ, Lịch sử; chờ ổn định, lưu HTML/TXT/JSON.
   Kiểm tra số mục quan hệ theo tiêu đề từng nhóm, đọc tiếp nếu tab có phân trang.
6. Chỉ khi bật `--download-attachments`: mở tab **Tải về**, tải và kiểm tra từng tệp.
7. Ghi SHA-256 cho tệp đã lưu và kiểm tra toàn văn không thay đổi trong lần lấy dữ liệu.
8. Lưu manifest và đưa kết quả hoàn chỉnh vào thư mục của văn bản.

Trình duyệt vẫn tải tài nguyên cần thiết để website hoạt động, nhưng crawler
chỉ ghi toàn văn, metadata và tệp đính kèm nếu được bật ra đĩa. Không lưu HTML khung, snapshot giao diện,
CSS, screenshot, sitemap XML hoặc nhật ký mạng vào kết quả.

Website có thể trả 403 tùy user-agent. Crawler dùng user-agent Chrome thông
thường; khi gặp 403, timeout hoặc tệp tải lỗi, lệnh báo lỗi và trả exit code 1.
Nút tải tạo URL `blob:` bằng JavaScript nên việc tải sử dụng phiên trình duyệt.

## Phạm vi và kiểm thử

Hiện hỗ trợ trang `/van-ban/chi-tiet/` có tab Nội dung và Tải về. Văn bản thiếu
tab toàn văn, dưới 300 ký tự hoặc giao diện thay đổi sẽ báo lỗi để kiểm tra.
Toàn văn hiện trích dạng chữ và bảng; ảnh/canvas không được nhúng vào HTML sạch.
Muốn lưu bản gốc và phụ lục chỉ có trong tệp đính kèm, cần bật `--download-attachments`.

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v
```

Kiểm thử bao gồm sitemap, tệp tải lỗi, loại bỏ CSS/JavaScript nhưng giữ cấu trúc,
và việc cập nhật kết quả/dọn dữ liệu tạm khi có lỗi.

## Dữ liệu các tab bổ sung

Mỗi JSON ghi URL nguồn, tên tab, thời điểm lấy và danh sách `pages`:
- `fields`: nhãn và giá trị Thuộc tính theo nguồn, không suy diễn ngày hoặc hiệu lực.
- `groups`: nhóm quan hệ Lược đồ, từng mục có tên, nội dung và URL nếu có.
- `columns`, `rows`: tiêu đề cột và dòng Lịch sử; giữ `source_key` khi nguồn cung cấp.
- `links`: liên kết trong DOM; URL là `null` nếu nguồn dùng sự kiện JavaScript thay cho `href`.
- `empty`: nguồn hiển thị trạng thái không có dữ liệu; khác với tab chưa tải xong.

Các trường không áp dụng cho một tab là danh sách rỗng. HTML giữ nội dung và cấu trúc,
không tái tạo bố cục đồ họa hoặc hành vi JavaScript của trang nguồn.
Manifest ghi trạng thái từng tab trong `tabs`, SHA-256 của mọi tệp trong `files`.
Thiếu tab, lỗi tải, số quan hệ không khớp hoặc phân trang không tiến triển đều báo lỗi;
kết quả cũ chỉ bị thay thế khi toàn bộ lần crawl thành công.
Tab Văn bản gốc không nằm trong phạm vi này; tải tệp gốc vẫn cần `--download-attachments`.
