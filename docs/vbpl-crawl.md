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
PYTHONPATH=src .venv/bin/python -m vietnam_legal_rag.ingestion.vbpl
```

Tùy chọn:

- `--url 'https://vbpl.vn/van-ban/chi-tiet/...'`: chọn URL cụ thể có trong sitemap.
- `--output data/raw/vbpl`: thư mục gốc lưu kết quả.
- `--timeout 90`: thời gian chờ mỗi bước trong trình duyệt, tính bằng giây.
- `--headed`: hiển thị trình duyệt; cần môi trường có màn hình.

Mặc định chọn văn bản đầu tiên trong sitemap. Mỗi lệnh chỉ crawl một văn bản.

## Dữ liệu đầu ra

```text
data/raw/vbpl/<mã văn bản>/
├── content.html        # toàn văn HTML sạch, mở trực tiếp offline
├── content.txt         # toàn văn UTF-8, đọc bằng trình soạn thảo
├── attachments/        # PDF, DOCX... nếu có
└── manifest.json       # nguồn, thời điểm, danh sách tệp và SHA-256
```

HTML đầu ra chỉ giữ nội dung và cấu trúc như đoạn văn, tiêu đề, bảng, danh sách,
chỉ số trên/dưới và liên kết tham chiếu. Liên kết tương đối được chuyển thành
URL đầy đủ của nguồn. CSS, thuộc tính style/class, JavaScript, giao diện điều hướng
và các thành phần tương tác được loại bỏ. HTML và TXT là bản nội dung đã trích
xuất; tệp đính kèm giữ nguyên bytes tải về.

Mỗi văn bản có một thư mục theo mã định danh trên website. Chạy lại cùng văn bản
sẽ cập nhật thư mục đó sau khi thu thập thành công. Nếu lỗi, dữ liệu tạm tự dọn
và bản thành công trước đó được giữ nguyên. Không tạo thư mục kết quả theo thời
gian cho mỗi lần chạy.

## Cách lấy nội dung động

1. Đọc `robots.txt` và sitemap đến khi tìm được URL văn bản.
2. Mở trang bằng Playwright/Chrome, chạy JavaScript để tải toàn văn.
3. Chờ phần nội dung, các request dữ liệu hoàn tất và nội dung ổn định.
4. Trích riêng phần toàn văn thành HTML sạch và TXT.
5. Mở tab **Tải về**, bấm từng nút và nhận tệp qua download event.
6. Kiểm tra tệp, SHA-256 và toàn văn không thay đổi trong lần lấy dữ liệu.
7. Lưu manifest và đưa kết quả hoàn chỉnh vào thư mục của văn bản.

Trình duyệt vẫn tải tài nguyên cần thiết để website hoạt động, nhưng crawler
chỉ ghi nội dung và tệp đính kèm ra đĩa. Không lưu HTML khung, snapshot giao diện,
CSS, screenshot, sitemap XML hoặc nhật ký mạng vào kết quả.

Website có thể trả 403 tùy user-agent. Crawler dùng user-agent Chrome thông
thường; khi gặp 403, timeout hoặc tệp tải lỗi, lệnh báo lỗi và trả exit code 1.
Nút tải tạo URL `blob:` bằng JavaScript nên việc tải sử dụng phiên trình duyệt.

## Phạm vi và kiểm thử

Hiện hỗ trợ trang `/van-ban/chi-tiet/` có tab Nội dung và Tải về. Văn bản thiếu
tab toàn văn, dưới 300 ký tự hoặc giao diện thay đổi sẽ báo lỗi để kiểm tra.
Toàn văn hiện trích dạng chữ và bảng; ảnh/canvas không được nhúng vào HTML sạch.
Các bản gốc vẫn được tải qua tệp đính kèm.

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v
```

Kiểm thử bao gồm sitemap, tệp tải lỗi, loại bỏ CSS/JavaScript nhưng giữ cấu trúc,
và việc cập nhật kết quả/dọn dữ liệu tạm khi có lỗi.


## Đối chiếu trực tiếp với nguồn

```bash
.venv/bin/python scripts/verify_vbpl.py
```

Lệnh mở lại từng văn bản, cuộn hết toàn văn và đối chiếu HTML đã lưu với DOM
nguồn: chữ (chuẩn hóa khoảng trắng), thứ tự đoạn, từng ô bảng và ô gộp,
danh sách, chỉ số trên/dưới và liên kết tham chiếu. TXT được so sánh với toàn
văn hiển thị sau cùng phép chuẩn hóa mà crawler sử dụng. Mọi tệp đính kèm
được tải lại vào thư mục tạm để so sánh tên, kích thước và SHA-256.

Kết quả nằm trong `evaluation/results/vbpl-verification.json`; từng manifest
cũng ghi lần xác minh thành công gần nhất. Việc đối chiếu chỉ xác nhận nội dung
nguồn tại thời điểm kiểm tra, không khẳng định HTML sạch giống từng byte với
HTML giao diện có CSS/JavaScript. Nếu nguồn thay đổi, lệnh báo sai khác.

`--repair-links` chỉ khôi phục liên kết tham chiếu đã bị bỏ ở phiên bản crawler
cũ khi toàn bộ chữ và cấu trúc bảng vẫn khớp nguồn. Các sai khác khác sẽ báo lỗi.
