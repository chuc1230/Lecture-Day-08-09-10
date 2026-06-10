# Báo Cáo Dự Án Cá Nhân — Lab Day 10: Data Pipeline & Data Observability

**Học viên thực hiện:** Đặng Minh Chức - 2A202600611
**Lớp:** C401  
**Ngày nộp:** 2026-06-10  

---

## 1. Luồng xử lý các tài liệu gốc (Raw TXT Processing Flow)

Hệ thống RAG sử dụng 5 tài liệu nghiệp vụ gốc (canonical sources) được lưu trữ dưới dạng văn bản thô `.txt` trong thư mục `data/docs/`:
1.  `policy_refund_v4.txt`: Chính sách hoàn tiền hiện hành (quy định 7 ngày làm việc).
2.  `sla_p1_2026.txt`: SLA và quy trình xử lý sự cố khẩn cấp P1/P2.
3.  `it_helpdesk_faq.txt`: FAQ giải đáp thắc mắc về tài khoản, VPN, email.
4.  `hr_leave_policy.txt`: Chính sách nghỉ phép năm 2026 (quy định 12 ngày phép năm).
5.  `access_control_sop.txt`: Quy trình phân quyền và phê duyệt truy cập hệ thống.

### Luồng chuyển đổi và xử lý dữ liệu:
- **Phân mảnh (Chunking):** Các tài liệu gốc được chia nhỏ thành các phân đoạn nội dung (chunks).
- **Xuất bản thô (Dirty Export):** Các chunks này được hệ thống nguồn xuất bản ra tệp CSV thô `policy_export_dirty.csv` cùng các metadata đi kèm (`doc_id`, `effective_date`, `exported_at`).
- **Phát sinh lỗi (Anomalies):** Do xuất bản tự động từ nhiều hệ thống không đồng bộ, tệp CSV thô chứa nhiều lỗi nghiêm trọng:
    *   *Lỗi định dạng:* Ngày tháng hiệu lực không đồng nhất (thiếu ngày hoặc sai chuẩn ISO như `DD/MM/YYYY`).
    *   *Chính sách cũ (Stale content):* Chứa nội dung hoàn tiền 14 ngày làm việc cũ hoặc chính sách phép năm 10 ngày cũ của năm 2025.
    *   *Nhiễu văn bản (Noise):* Dính các tiền tố lỗi (`!!!`, `Nội dung không rõ ràng:`), thẻ meta hệ thống và lỗi lặp từ chính tả (`làm việc làm việc`).
    *   *Thiếu ngữ cảnh (Context Loss):* Các dòng về xử lý sự cố P1/P2 bị mất chữ "Ticket", chỉ ghi "Escalation P1/P2" dẫn đến việc tìm kiếm ngữ nghĩa (semantic search) bị sai lệch.

---

## 2. Cách thức hoạt động của Pipeline

Pipeline dữ liệu được thực thi thông qua tệp `etl_pipeline.py` đi qua 4 giai đoạn khép kín:

```
[Ingest] ──> [Clean / Transform] ──> [Validate / Quality] ──> [Embed / Load]
```

### Giai đoạn 1: Ingest (Nạp dữ liệu)
Pipeline đọc dữ liệu từ tệp CSV thô đầu vào. Tại đây, một mã định danh phiên chạy duy nhất (`run_id`) được khởi tạo dưới dạng UTC timestamp (ví dụ: `2026-06-10T09-33Z`), và số lượng dòng thô đầu vào được ghi nhận (`raw_records`).

### Giai đoạn 2: Clean / Transform (Làm sạch & Chuẩn hóa)
Chạy qua hàm `clean_rows` trong `cleaning_rules.py` để lọc và chuẩn hóa từng dòng dữ liệu:
1.  **Kiểm tra Allowlist:** Chỉ cho phép các `doc_id` được đăng ký trong hợp đồng dữ liệu `data_contract.yaml`. Các dòng lạ sẽ bị cách ly (`unknown_doc_id`).
2.  **Chuẩn hóa ngày hiệu lực:** Chuyển đổi ngày hiệu lực sang định dạng ISO `YYYY-MM-DD`. Nếu trống hoặc lỗi định dạng, đẩy vào cách ly (`missing_effective_date` hoặc `invalid_effective_date_format`).
3.  **Lọc phiên bản cũ:** Lọc bỏ các dòng chính sách nhân sự có ngày hiệu lực trước mốc tối thiểu được khai báo trong hợp đồng dữ liệu (`_HR_LEAVE_MIN_DATE`) hoặc chứa nội dung 10 ngày phép cũ (`stale_hr_policy_content`).
4.  **Làm sạch văn bản (Text Cleaning):** Lọc bỏ các thẻ hệ thống (khớp regex `_SOURCE_TAG_PAT`), xóa tiền tố gây nhiễu, sửa lỗi chính tả lặp từ, và **làm giàu ngữ cảnh** bằng cách đổi các cụm `"Escalation P1:"` thành `"Ticket P1: Escalation:"` để cải thiện độ khớp RAG.
5.  **Cập nhật quy định hiện hành:** Sửa đổi quy định 14 ngày hoàn tiền cũ thành 7 ngày làm việc chuẩn của phiên bản v4.
6.  **Loại bỏ trùng lặp:** Lọc bỏ các dòng trùng lặp nội dung văn bản (`duplicate_chunk_text`) sau khi đã làm sạch và sinh mã định danh hash SHA-256 duy nhất (`chunk_id`) cho từng chunk sạch.

### Giai đoạn 3: Validate / Quality (Kiểm định chất lượng)
Hàm `run_expectations` trong `expectations.py` thực thi 8 quy tắc kiểm định chất lượng (E1 đến E8). Nếu bất kỳ quy tắc nghiêm ngặt nào (`halt` severity) bị thất bại:
- Pipeline sẽ **dừng lại ngay lập tức** (HALT) và không nạp dữ liệu vào cơ sở dữ liệu vector nhằm bảo vệ an toàn dữ liệu.
- Cờ ghi đè `--skip-validate` chỉ được sử dụng cho mục đích thử nghiệm dữ liệu lỗi.

### Giai đoạn 4: Embed / Load (Nạp cơ sở dữ liệu)
Khi vượt qua bước validation thành công:
1.  Dữ liệu sạch được lưu trữ vào tệp CSV sạch trong thư mục `artifacts/cleaned/`.
2.  Pipeline sử dụng mô hình `all-MiniLM-L6-v2` để chuyển đổi văn bản sạch thành vector embedding.
3.  Thực hiện **Snapshot Sync:** Upsert các vector mới vào ChromaDB theo `chunk_id` và **xóa bỏ (prune)** các vector ID cũ không còn xuất hiện trong phiên chạy sạch hiện hành để đảm bảo đồng bộ hóa tuyệt đối.

---

## 3. Bảng chất lượng dữ liệu & So sánh Before/After

### 3a. Bảng metric_impact (Số liệu chất lượng thực tế)

| Quy tắc / Expectation mới | Trước (Số liệu) | Sau / Khi Inject (Số liệu) | Bằng chứng kiểm thử |
|---------------------------|-----------------|---------------------------|---------------------|
| **Rule 1 & 2:** Lọc meta tag & tiền tố | Giữ nguyên `"!!!"` hoặc `"Nội dung không rõ ràng:"`. | Loại bỏ hoàn toàn ở các dòng 35, 56, 87... | `cleaning_rules.py` |
| **Rule 3:** Sửa lỗi lặp từ | Chứa `"làm việc làm việc"` | Thay thế thành `"làm việc"` duy nhất (dòng 18, 109, 205). | `cleaning_rules.py` |
| **Rule 4:** Làm giàu ngữ cảnh | Chứa `"Escalation P1:"` | Đổi thành `"Ticket P1: Escalation:"` | `cleaning_rules.py` |
| **Expectation E7:** Core docs present | Không kiểm tra sự hiện diện của tài liệu. | Kiểm tra đủ 5 tệp chính. Dừng chạy nếu thiếu file nào. | `expectations.py` |
| **Expectation E8:** No duplicate text | Không kiểm tra trùng lặp chunk. | Đưa ra cảnh báo (Warn) nếu phát hiện trùng lặp. | `expectations.py` |

### 3b. So sánh hiệu quả truy vấn (Before/After Retrieval)

Sự khác biệt rõ ràng giữa phiên bản lỗi (Injected Bad) và phiên bản sạch (Cleaned Run):
-   **Phiên bản dữ liệu lỗi (Injected Bad - `after_inject_bad.csv`):**
    Truy vấn chính sách hoàn tiền (`q_refund_window`) dính lỗi nặng do trích xuất thông tin cũ:
    *   *Top-1 Preview:* `"Yêu cầu hoàn tiền được chấp nhận trong vòng 14 ngày làm việc kể từ xác nhận đơn."`
    *   *hits_forbidden:* `yes`
-   **Phiên bản dữ liệu sạch (Cleaned Run - `eval_after_fix.csv`):**
    Hệ thống tự động trả về chính sách chuẩn 7 ngày hiện hành:
    *   *Top-1 Preview:* `"Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng."`
    *   *hits_forbidden:* `no`

---

## 4. Hướng dẫn chạy chương trình (Execution Guide)

Đảm bảo môi trường đã được cài đặt đầy đủ thư viện thông qua `pip install -r requirements.txt`.

### Bước 1: Chạy pipeline làm sạch và nạp dữ liệu sạch vào ChromaDB
Chạy lệnh chuẩn để thực hiện toàn bộ quy trình: nạp, làm sạch, kiểm định và nhúng dữ liệu. Lệnh này phải kết thúc với trạng thái thành công (`PIPELINE_OK`).
```bash
.venv\Scripts\python.exe etl_pipeline.py run
```

### Bước 2: Chạy đánh giá chất lượng truy vấn tự kiểm (21 câu hỏi)
Lệnh này kiểm tra bộ câu hỏi tự luyện và lưu kết quả đối chứng trước/sau ra file CSV.
```bash
.venv\Scripts\python.exe eval_retrieval.py --out artifacts/eval/eval_after_fix.csv
```

### Bước 3: Chạy chấm điểm chính thức (10 câu hỏi đánh giá)
Sinh ra file JSONL kết quả kiểm tra chất lượng tìm kiếm cho 10 câu hỏi nghiệp vụ.
```bash
.venv\Scripts\python.exe grading_run.py --out artifacts/eval/grading_run.jsonl
```

### Bước 4: Chạy kiểm tra nhanh định dạng và kết quả của giảng viên
Dùng để tự động kiểm tra định dạng và trạng thái đạt/không đạt của file chấm điểm chính thức:
```bash
.venv\Scripts\python.exe instructor_quick_check.py --grading artifacts/eval/grading_run.jsonl
```

### Bước phụ (Chạy thử nghiệm dữ liệu lỗi):
Để chạy thử nghiệm chế độ tiêm nhiễm dữ liệu lỗi (Sprint 3) nhằm thu thập bằng chứng lỗi:
```bash
.venv\Scripts\python.exe etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
.venv\Scripts\python.exe eval_retrieval.py --out artifacts/eval/after_inject_bad.csv
```
*(Lưu ý: Luôn chạy lại Bước 1 sau khi chạy thử nghiệm dữ liệu lỗi để khôi phục cơ sở dữ liệu về trạng thái sạch).*
