# Kiến trúc ban đầu

## Pipeline xây dựng kho tri thức

1. `ingestion` / crawl: dò tab trên từng văn bản, thu thập HTML của mọi tab
   ngoại trừ Tải về và Văn bản gốc; ghi URL, thời điểm, phân loại, danh sách tab
   và SHA-256 vào `manifest.json`.
   `data/raw/` chỉ lưu HTML và manifest. Với vbpl.vn, văn bản được phân nhóm theo
   breadcrumb tại `data/raw/vbpl/<trung_uong|dia_phuong>/<id>/`.
2. `ingestion` / extract: đọc HTML đã lưu, tạo JSON cấu trúc toàn văn và JSON
   riêng cho từng tab tại `data/extracted/vbpl/<id>/`. Manifest extracted ghi
   định danh raw, SHA-256 của HTML nguồn và các tệp JSON đầu ra. Parser giữ
   paragraph/list/table, cây pháp luật theo thứ tự nguồn và issues của dữ liệu
   chưa rõ. Không merge tab hoặc tạo document canonical ở bước này.
   Bước này chạy offline, có thể chạy lại mà không crawl lại.
3. `preprocessing` / normalize: chuẩn hóa và nhận diện cấu trúc văn bản,
   đầu ra tại `data/normalized/`; sẽ xây dựng sau.
4. `preprocessing` / chunk: tạo đoạn trích theo điều/khoản/điểm và giữ liên kết
   về văn bản, đầu ra tại `data/chunks/`; sẽ xây dựng sau.
5. `indexing`: tạo embedding và chỉ mục, ghi phiên bản mô hình cùng cấu hình xử lý.

Bốn lớp dữ liệu là `raw → extracted → normalized → chunks`.
HTML trong raw cần được giữ nguyên sau khi crawl để có thể trích xuất lại.
Mỗi bước crawl/extract ghi vào thư mục tạm và chỉ thay kết quả của văn bản đó
khi hoàn tất; lỗi integrity giữ bản thành công trước. Validator ghi status
`failed` và issues nếu có lỗi cấu trúc/text, vẫn lưu dữ liệu parse được và
source reference để audit. Issue info đơn thuần không làm document failed. Crawl và extract là hai lệnh
độc lập: sau khi cập nhật raw, chạy extract để cập nhật dữ liệu tương ứng.
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
- `src/vietnam_legal_rag/ingestion`: crawl/extract orchestration; subpackages `html`, `semantics`, `refinement`, `validation` giữ các trách nhiệm độc lập.
- `src/vietnam_legal_rag/cli`: argparse và điều phối lệnh `vlr`; không giữ quy tắc parser/audit.
- `src/vietnam_legal_rag/evaluation`: cấu hình run, sampling, audit độc lập và báo cáo; không phụ thuộc script.
- `scripts`: thin compatibility wrappers; logic chính nằm trong package. `pyproject.toml` khai báo console entrypoints.
- `frontend`: giao tiếp với backend qua API; không giữ khóa API của nhà cung cấp LLM.
- `prompts`: mẫu prompt được đánh phiên bản cùng mã nguồn.
- `configs`: tham số xử lý và truy xuất có thể kiểm tra lại khi đánh giá.

## Kiểm tra chất lượng

- `tests/unit`: kiểm tra ingestion, evaluation và CLI theo bố cục package.
- `tests/regression`: kiểm tra mẫu nguồn, corpus batch-50 và golden RAW.
- `tests/support.py`: fixture giả lập và đường dẫn gốc dùng chung.
- `tests/integration`: kiểm tra lập chỉ mục, truy xuất và luồng API với dịch vụ phụ thuộc.
- `evaluation/datasets`: bộ câu hỏi và nguồn tham chiếu đã rà soát.
- `evaluation/results`: lưu kết quả kèm phiên bản dữ liệu, mã nguồn, prompt và mô hình.

Các thư mục của những giai đoạn chưa triển khai vẫn là vị trí dành sẵn. Chỉ bổ sung thư viện và dịch vụ khi triển khai
thành phần tương ứng.

Chi tiết module và các đường dẫn đã chuyển: [Python layout](python-layout.md).
