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
│   ├── raw/                   # HTML nguồn và manifest.json
│   ├── extracted/             # JSON có cấu trúc trích xuất từ HTML trong raw
│   ├── normalized/            # Dữ liệu chuẩn hóa; sẽ triển khai sau
│   ├── chunks/                # Đoạn trích phục vụ RAG; sẽ triển khai sau
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
Nguồn tài liệu → crawl → data/raw (HTML + manifest)
              → extract → data/extracted (JSON có cấu trúc)
              → normalize → data/normalized       # triển khai sau
              → chunk → data/chunks               # triển khai sau
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
Lệnh cài đặt trên cài package cục bộ và jsonschema cho validator. Việc đọc `.env` sẽ được bổ sung
khi triển khai cấu hình ứng dụng.

## Nguồn dữ liệu đầu tiên: vbpl.vn

Crawler đọc [sitemap](https://vbpl.vn/sitemap.xml), chọn đúng một văn bản,
chạy JavaScript bằng Chrome, dò tất cả tab thực tế và lưu HTML nguồn cùng
`manifest.json` vào lớp `raw`, chỉ bỏ qua Tải về và Văn bản gốc.
Bước extract đọc lại HTML trên đĩa
để tạo JSON có cấu trúc tại lớp `extracted`, không cần trình duyệt hoặc mạng.

```bash
uv pip install --python .venv/bin/python -e '.[crawl]'
.venv/bin/vbpl-crawl-one
.venv/bin/vbpl-extract
```

Module crawler: `src/vietnam_legal_rag/ingestion/crawl_legal_documents.py`.
Module extractor: `src/vietnam_legal_rag/ingestion/extract_legal_documents.py`.
Raw giữ `vbpl/<trung_uong|dia_phuong>/<mã văn bản>/`;
extracted giữ `vbpl/<mã văn bản>/`.
Crawler phân loại theo breadcrumb của nguồn; hỗ trợ cả tab Các văn bản hợp nhất. `raw` chỉ chứa HTML và manifest,
không tải tệp đính kèm. HTML mới giữ markup và thuộc tính DOM để trích xuất lại.
Đọc cấu trúc toàn văn tại `data/extracted/vbpl/<mã văn bản>/content.json`.
Schema 2.3.2 giữ duy nhất `document: legal_document` trong content.json,
với header/title/preamble/body/closing/annexes và hierarchy Phần → Điều → Khoản → Điểm.
Second pass dùng sequence/points/style để promotion Khoản, tách hierarchy đánh số
thập phân của phụ lục. Form refinement dùng ranh giới Mẫu số, field/subfield,
footnote sequences, bibliography và lists trong ô bảng; validator audit những
paragraph còn marker. `--debug-tree` in cây ra console.
Layout tables thành section semantic; data tables giữ cell geometry tại đúng
legal parent. History/relations tách primary number và mentions; validator kiểm
tra hierarchy, text fidelity, provenance và determinism.
Xem [schema extracted](docs/extracted-schema.md) và [kết quả hierarchy mẫu](docs/extract-hierarchy.md).
Contract V2.3.2 và đối chiếu actual JSON: [báo cáo freeze](docs/extract-v2.3.2-form-invariant-audit.md).
Kết quả kiểm tra V2.3 và delta từ V2.2: [báo cáo form semantics](docs/extract-v2.3-report.md).
Chạy lại sẽ cập nhật thư mục văn bản sau khi bước tương ứng thành công.
`normalized` và `chunks` hiện chỉ là thư mục dành sẵn.
Xem [hướng dẫn crawler](docs/vbpl-crawl.md) để cài Chromium, chọn URL và kiểm thử.

## Quy ước làm việc

- Đặt logic chính trong `src/vietnam_legal_rag/`; script và notebook gọi lại logic này.
- Lưu prompt ở `prompts/`, cấu hình không nhạy cảm ở `configs/`, khóa API trong `.env`.
- Không đưa dữ liệu lớn, chỉ mục, cache, kết quả chạy hoặc khóa API vào Git.
- Chỉ commit dữ liệu mẫu và bộ đánh giá nhỏ sau khi kiểm tra quyền sử dụng và thông tin nhạy cảm.
- Giữ thông tin nguồn và phiên bản xuyên suốt quá trình xử lý để truy ngược mỗi trích dẫn.
- Xem [kiến trúc](docs/architecture.md) và [quy ước dữ liệu](docs/data-conventions.md)
  trước khi triển khai pipeline.
