# Quy ước dữ liệu pháp luật

Schema extracted đã được triển khai: xem [extracted 2.1.0](extracted-schema.md).
Các trường tài liệu canonical và đoạn trích bên dưới vẫn là đề xuất cho các bước sau.

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

## Phân nhóm dữ liệu crawl vbpl.vn

Crawler hiện ghi `document_scope` là `trung_uong` hoặc `dia_phuong` trong manifest.
Trường `classification` lưu phương thức `source_breadcrumb` và các URL breadcrumb.
Raw dùng `vbpl/<document_scope>/<id>/`; extracted dùng `vbpl/<id>/`:

- `raw`: chỉ HTML nguồn và `manifest.json`; trường `files` và `tabs.*.files`
  chỉ tham chiếu HTML trong thư mục văn bản. `tabs` ghi các tab thực tế đã lấy;
  `excluded_tabs` ghi các tab Tải về/Văn bản gốc đã bỏ qua.
- `extracted`: chỉ JSON được trích xuất từ HTML raw, cùng `manifest.json`
  ghi `document_id` nguyên giá trị từ raw, schema/parser version, source refs,
  source/file hashes và issues. Không ghi timestamp chạy extract để đảm bảo deterministic.
- `normalized`: dành cho dữ liệu chuẩn hóa, chưa triển khai.
- `chunks`: dành cho đoạn trích, chưa triển khai.

Đường dẫn trong các bản ghi tệp là tương đối với thư mục văn bản của lớp đó.
Trong extracted, source_ref cấp file dùng đường dẫn tương đối với root raw
và SHA-256. Source_ref cấp record kế thừa file đó, thêm vị trí nguồn để audit.
Không có đường dẫn tuyệt đối hoặc timestamp của lần extract.
Nhóm chưa xác định sẽ báo lỗi. `data/samples/` là nơi để mẫu chia sẻ,
không phải một lớp của pipeline.

## Lưu trữ và Git

Dữ liệu trong `raw/`, `extracted/`, `normalized/`, `chunks/`, chỉ mục, cache và kết quả đánh giá
được bỏ qua bởi Git. Các tệp `.gitkeep` chỉ giúp giữ cây thư mục khi commit.
Dữ liệu gốc cần có phương án sao lưu riêng khi bắt đầu thu thập.

`data/samples/`, `tests/fixtures/` và `evaluation/datasets/` có thể chứa dữ liệu nhỏ
để chia sẻ trong repo; kiểm tra quyền sử dụng và loại bỏ thông tin nhạy cảm trước khi commit.
