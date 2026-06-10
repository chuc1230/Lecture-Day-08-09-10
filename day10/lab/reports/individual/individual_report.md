# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Đặng Minh Chức - 2A202600611
**Lớp:** C401   
**Ngày nộp:** 2026-06-10  
**Độ dài:** ~500 từ

---

## 1. Tôi phụ trách phần nào?

**File / module:**

- `contracts/data_contract.yaml`: Cấu hình metadata, danh sách `allowed_doc_ids`, `canonical_sources`, và ngày hiệu lực tối thiểu cho chính sách HR.
- `transform/cleaning_rules.py`: Triển khai tải hợp đồng dữ liệu động, sửa lỗi cú pháp regex `_SOURCE_TAG_PAT`, và phát triển 4 quy tắc làm sạch dữ liệu (loại bỏ thẻ meta, lọc tiền tố nhiễu, sửa lỗi chính tả lặp từ và làm giàu ngữ cảnh ticket).
- `quality/expectations.py`: Bổ sung 2 expectations E7 (`core_docs_present` - halt) và E8 (`no_duplicate_chunk_text` - warn).
- `docs/runbook.md` và `docs/pipeline_architecture.md`: Viết tài liệu hướng dẫn vận hành và thiết kế sơ đồ kiến trúc.

---

## 2. Một quyết định kỹ thuật

Quyết định kỹ thuật quan trọng nhất của tôi là **tách biệt cấu hình khỏi mã nguồn (Configuration Decoupling)** bằng cách tải động danh sách document cho phép (`ALLOWED_DOC_IDS`) và ngày hiệu lực tối thiểu (`_HR_LEAVE_MIN_DATE`) từ `contracts/data_contract.yaml`. 

Thay vì hard-code các giá trị này trong logic của `transform/cleaning_rules.py`, tôi đã sử dụng thư viện `PyYAML` để nạp tệp cấu hình khi khởi động pipeline. Điều này mang lại hai lợi ích lớn:
1. **Dễ bảo trì:** Khi công ty bổ sung tài liệu mới (như `access_control_sop`), tôi chỉ cần cập nhật tệp YAML cấu hình mà không cần can thiệp vào mã nguồn Python.
2. **Đồng bộ hóa:** Hợp đồng dữ liệu đóng vai trò là "Single Source of Truth", đảm bảo tính thống nhất tuyệt đối giữa schema đã định nghĩa và logic thực tế chạy trong pipeline.

---

## 3. Một lỗi hoặc anomaly đã xử lý

**Triệu chứng:** Khi chạy thử nghiệm đánh giá retrieval trên bộ câu hỏi, câu hỏi `gq_d10_06` về thời gian tự động escalate của ticket P1 bị lỗi `contains_expected: false` do không tìm thấy từ khóa "10 phút" trong Top-5 chunk trả về từ ChromaDB.
**Phát hiện:** Tôi kiểm tra và phát hiện dòng dữ liệu thô chứa thông tin này (`Row 228`) bị đánh giá khoảng cách vector kém (Rank 9) do chunk text chỉ ghi `"Escalation P1: tự động escalate lên Senior Engineer..."` mà thiếu mất từ khóa cốt lõi là `"Ticket"` khiến mô hình embedding `all-MiniLM-L6-v2` không nhận diện được sự liên quan.
**Khắc phục:** Tôi đã thêm Quy tắc 4 (Rule 4) trong `cleaning_rules.py` để tự động làm giàu ngữ cảnh: phát hiện các dòng bắt đầu bằng `"Escalation P1:"` và đổi thành `"Ticket P1: Escalation:"`. Nhờ vậy, câu hỏi `gq_d10_06` đã được xếp hạng lên Rank 1 với khoảng cách cực thấp, vượt qua bộ chấm điểm thành công.

---

## 4. Bằng chứng trước / sau

Dưới đây là bằng chứng trích xuất từ các file đánh giá tương ứng với `run_id: 2026-06-10T09-40Z` và `inject-bad`:

- **Trước khi fix (Injected Bad - `after_inject_bad.csv`):**
  `q_refund_window, ... , policy_refund_v4, Yêu cầu hoàn tiền được chấp nhận trong vòng 14 ngày làm việc kể từ xác nhận đơn. , yes, yes, yes` (Dính từ khóa cấm 14 ngày làm việc).
- **Sau khi fix (Cleaned Run - `eval_after_fix.csv`):**
  `q_refund_window, ... , policy_refund_v4, Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng. , yes, no, yes` (Đã được làm sạch hoàn toàn về 7 ngày).

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ tích hợp thư viện **Great Expectations** thực tế vào pipeline thay thế bộ test custom hiện tại, đồng thời thiết lập cảnh báo tự động gửi tin nhắn trực tiếp qua Slack API khi bước freshness hoặc validation trả về trạng thái FAIL.
