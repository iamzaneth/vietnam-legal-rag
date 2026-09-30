# Quy ước dữ liệu pháp luật

Đây là đề xuất ban đầu để triển khai schema; chưa phải schema đã được thực thi.

## Tài liệu

Mỗi tài liệu nên giữ các trường sau khi nguồn có cung cấp:

- `document_id`: định danh nội bộ ổn định của văn bản.
- `version_id`: định danh phiên bản nội dung cụ thể.
- `title`, `document_number`, `document_type`, `issuing_authority`: thông tin nhận diện.
- `issued_date`, `effective_from`, `effective_to`: ngày ban hành và khoảng hiệu lực đã xác minh.
- `legal_status`: trạng thái hiệu lực; dùng `unknown` khi chưa xác minh được.
- `source_url`, `retrieved_at`, `content_hash`: nguồn, thời điểm thu thập và mã kiểm tra nội dung.
- `raw_path`: đường dẫn tương đối đến tài liệu gốc trong kho dữ liệu.
- `relations`: quan hệ sửa đổi, bổ sung, thay thế hoặc bãi bỏ, kèm nguồn xác minh.

Lưu ngày theo `YYYY-MM-DD`, thời điểm theo ISO 8601 có múi giờ.
Dùng `null` cho ngày chưa biết; không suy diễn ngày hiệu lực từ ngày ban hành.
Thông tin hiệu lực có thể khác nhau giữa các phần của một văn bản, vì vậy cần
cho phép bổ sung metadata ở cấp điều/khoản khi triển khai schema.

## Đoạn trích

- `chunk_id`: định danh ổn định trong một phiên bản và cấu hình chia đoạn.
- `document_id`, `version_id`: liên kết về tài liệu cụ thể.
- `text`: nội dung đoạn trích.
- `chapter`, `section`, `article`, `clause`, `point`: vị trí trong cấu trúc văn bản, nếu có.
- `page_number` hoặc vị trí trong nội dung gốc: phục vụ đối chiếu trích dẫn.
- `source_url`: liên kết đến nguồn.
- `pipeline_version`: phiên bản xử lý tạo ra đoạn trích.

Không gộp đoạn từ các văn bản hoặc phiên bản khác nhau thành cùng một đoạn.
Giữ nguyên dấu tiếng Việt trong nội dung; dùng tên tệp đơn giản, nhất quán.

## Lưu trữ và Git

Dữ liệu trong `raw/`, `interim/`, `processed/`, chỉ mục, cache và kết quả đánh giá
được bỏ qua bởi Git. Các tệp `.gitkeep` chỉ giúp giữ cây thư mục khi commit.
Dữ liệu gốc cần có phương án sao lưu riêng khi bắt đầu thu thập.

`data/samples/`, `tests/fixtures/` và `evaluation/datasets/` có thể chứa dữ liệu nhỏ
để chia sẻ trong repo; kiểm tra quyền sử dụng và loại bỏ thông tin nhạy cảm trước khi commit.
