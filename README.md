# Chatbot RAG pháp luật Việt Nam

Khung dự án chatbot tra cứu văn bản pháp luật Việt Nam, sử dụng RAG
(Retrieval-Augmented Generation): tìm nội dung liên quan trước khi tạo câu trả lời có trích dẫn.

## Cấu trúc thư mục

```text
vietnam-legal-rag/
├── src/vietnam_legal_rag/       # Mã nguồn Python
│   ├── api/                    # API hội thoại, tra cứu và kiểm tra trạng thái
│   ├── core/                   # Cấu hình ứng dụng, logging và kiểu dữ liệu dùng chung
│   ├── ingestion/              # Thu thập, đọc tài liệu và lưu thông tin nguồn
│   ├── preprocessing/          # Chuẩn hóa, tách điều/khoản/điểm và chia đoạn
│   ├── indexing/               # Tạo embedding và cập nhật chỉ mục tìm kiếm
│   ├── retrieval/              # Tìm kiếm, lọc metadata và xếp hạng lại kết quả
│   └── generation/             # Ghép ngữ cảnh, gọi LLM và định dạng trích dẫn
├── frontend/                  # Giao diện chatbot; chọn framework sau
├── configs/                   # Cấu hình pipeline, mô hình và tìm kiếm; không chứa bí mật
├── prompts/                   # Mẫu prompt có quản lý phiên bản
├── data/
│   ├── raw/                   # Tài liệu gốc; giữ nguyên nội dung tải về
│   ├── interim/               # Văn bản đã trích xuất, dữ liệu đang chuẩn hóa
│   ├── processed/             # Văn bản và đoạn trích đã chuẩn hóa, kèm metadata
│   └── samples/               # Mẫu nhỏ được phép chia sẻ và đưa vào Git
├── storage/
│   ├── indexes/               # Chỉ mục tìm kiếm lưu cục bộ
│   └── cache/                 # Bộ nhớ đệm có thể tạo lại
├── evaluation/
│   ├── datasets/              # Bộ câu hỏi, đáp án tham chiếu và trích dẫn kỳ vọng
│   └── results/               # Kết quả đánh giá từng lần chạy
├── tests/
│   ├── unit/                  # Kiểm thử từng thành phần
│   ├── integration/           # Kiểm thử phối hợp các thành phần và dịch vụ
│   └── fixtures/              # Dữ liệu giả lập, nhỏ và cố định cho kiểm thử
├── scripts/                   # Điểm chạy các tác vụ thu thập, lập chỉ mục, đánh giá
├── notebooks/                 # Thử nghiệm và khám phá dữ liệu
├── docs/
│   ├── architecture.md        # Luồng xử lý và trách nhiệm các thành phần
│   └── data-conventions.md    # Quy ước dữ liệu pháp luật và thông tin nguồn
├── .env.example               # Mẫu biến môi trường
├── .gitignore
└── pyproject.toml             # Khai báo package Python
```

## Luồng xử lý dự kiến

```text
Nguồn tài liệu → ingestion → data/raw
              → preprocessing → data/interim → data/processed
              → indexing → chỉ mục tìm kiếm

Câu hỏi → API → retrieval → generation → câu trả lời kèm trích dẫn
```

`evaluation/` dùng để đánh giá chất lượng truy xuất, câu trả lời và trích dẫn.
`tests/` dùng để kiểm tra tính đúng đắn của mã nguồn.

## Môi trường phát triển

Khung ban đầu dùng Python 3.11 trở lên. Chưa chọn framework API, nhà cung cấp
LLM, mô hình embedding, cơ sở dữ liệu vector hoặc framework giao diện.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

Dự án đã có crawler thử một văn bản từ vbpl.vn; chưa có chatbot hoặc pipeline RAG.
Lệnh cài đặt trên chỉ cài package Python cục bộ. Việc đọc `.env` sẽ được bổ sung
khi triển khai cấu hình ứng dụng.

## Nguồn dữ liệu đầu tiên: vbpl.vn

Crawler đọc [sitemap](https://vbpl.vn/sitemap.xml), chọn đúng một văn bản,
chạy JavaScript bằng Chrome, trích toàn văn thành HTML/TXT sạch và tải tệp đính kèm.

```bash
uv pip install --python .venv/bin/python -e '.[crawl]'
.venv/bin/vbpl-crawl-one
```

Kết quả nằm trong `data/raw/vbpl/<mã văn bản>/`. Mở `content.html` để đọc
toàn văn offline hoặc `content.txt` để xem văn bản thuần. HTML đã bỏ CSS và
JavaScript. `manifest.json` ghi nguồn và danh sách tệp; chạy lại cùng văn bản
sẽ cập nhật thư mục hiện có sau khi tải thành công.
Xem [hướng dẫn crawler](docs/vbpl-crawl.md) để cài Chromium, chọn URL và kiểm thử.

## Quy ước làm việc

- Đặt logic chính trong `src/vietnam_legal_rag/`; script và notebook gọi lại logic này.
- Lưu prompt ở `prompts/`, cấu hình không nhạy cảm ở `configs/`, khóa API trong `.env`.
- Không đưa dữ liệu lớn, chỉ mục, cache, kết quả chạy hoặc khóa API vào Git.
- Chỉ commit dữ liệu mẫu và bộ đánh giá nhỏ sau khi kiểm tra quyền sử dụng và thông tin nhạy cảm.
- Giữ thông tin nguồn và phiên bản xuyên suốt quá trình xử lý để truy ngược mỗi trích dẫn.
- Xem [kiến trúc](docs/architecture.md) và [quy ước dữ liệu](docs/data-conventions.md)
  trước khi triển khai pipeline.
