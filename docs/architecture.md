# Kiến trúc ban đầu

## Pipeline xây dựng kho tri thức

1. `ingestion`: thu thập tài liệu, ghi URL nguồn, thời điểm lấy dữ liệu và mã kiểm tra nội dung.
   Với vbpl.vn, mặc định lưu toàn văn HTML/TXT, các tab Thuộc tính/Lược đồ/Lịch sử
   dạng HTML/TXT/JSON và manifest; tệp đính kèm chỉ tải
   khi bật `--download-attachments`. Dữ liệu được phân nhóm theo breadcrumb nguồn
   tại `data/raw/vbpl/trung_uong/<id>/` hoặc `data/raw/vbpl/dia_phuong/<id>/`.
2. `preprocessing`: đọc HTML/TXT; đọc thêm PDF/DOCX và xử lý OCR khi có tệp đính kèm,
   chuẩn hóa và nhận diện cấu trúc văn bản.
3. `preprocessing`: tạo đoạn trích theo điều/khoản/điểm khi có thể; giữ liên kết về tài liệu gốc.
4. `indexing`: tạo embedding và chỉ mục, ghi phiên bản mô hình cùng cấu hình xử lý.

Dữ liệu gốc ở `data/raw/` cần được giữ nguyên để có thể xử lý lại.
Tách văn bản trung gian khỏi dữ liệu chuẩn hóa để dễ tìm lỗi trong từng bước.
Chỉ mục cục bộ nằm ở `storage/indexes/`; khi dùng dịch vụ bên ngoài,
`indexing` và `retrieval` sẽ giao tiếp với dịch vụ đó.

## Luồng trả lời

1. `api` nhận câu hỏi và các điều kiện tra cứu, chẳng hạn thời điểm áp dụng.
2. `retrieval` tìm đoạn liên quan, lọc theo metadata phù hợp và xếp hạng lại khi cần.
3. `generation` ghép ngữ cảnh với prompt, tạo câu trả lời và gắn trích dẫn về nguồn.
4. `api` trả nội dung, trích dẫn và thông tin còn thiếu để giao diện hiển thị.

Khi nguồn chưa đủ hoặc thông tin hiệu lực chưa được xác minh, câu trả lời cần
nêu giới hạn đó. Không mặc định văn bản mới thu thập là văn bản đang có hiệu lực.

## Ranh giới mã nguồn

- `core`: cấu hình, logging và kiểu dữ liệu dùng chung; tránh gom logic nghiệp vụ vào đây.
- `scripts`: điểm chạy tác vụ; không sao chép logic của package.
- `frontend`: giao tiếp với backend qua API; không giữ khóa API của nhà cung cấp LLM.
- `prompts`: mẫu prompt được đánh phiên bản cùng mã nguồn.
- `configs`: tham số xử lý và truy xuất có thể kiểm tra lại khi đánh giá.

## Kiểm tra chất lượng

- `tests/unit`: kiểm tra chuẩn hóa, tách đoạn, lọc metadata và định dạng trích dẫn.
- `tests/integration`: kiểm tra lập chỉ mục, truy xuất và luồng API với dịch vụ phụ thuộc.
- `evaluation/datasets`: bộ câu hỏi và nguồn tham chiếu đã rà soát.
- `evaluation/results`: lưu kết quả kèm phiên bản dữ liệu, mã nguồn, prompt và mô hình.

Các thư mục hiện là vị trí dành sẵn. Chỉ bổ sung thư viện và dịch vụ khi triển khai
thành phần tương ứng.
