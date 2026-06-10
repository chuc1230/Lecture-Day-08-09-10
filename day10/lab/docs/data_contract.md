# Data contract — Lab Day 10

Tài liệu đặc tả hợp đồng dữ liệu dùng để đồng bộ thông tin cấu trúc, chất lượng và nguồn gốc dữ liệu.

---

## 1. Nguồn dữ liệu (Source Map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| `policy_refund_v4` | Batch CSV Export | Chứa thông tin stale (14 ngày làm việc cũ). | Expectation halt: `refund_no_stale_14d_window` báo lỗi. |
| `sla_p1_2026` | API Pull/Batch | Mất ngữ cảnh "Ticket" gây giảm chất lượng retrieval. | `hits_forbidden` khi đánh giá retrieval hoặc `core_docs_present` fail. |
| `it_helpdesk_faq` | Database Sync | Lỗi định dạng ngày tháng hiệu lực (`effective_date`). | `effective_date_iso_yyyy_mm_dd` báo lỗi format không phải ISO. |
| `hr_leave_policy` | HR System Export | Xung đột phiên bản cũ (HR 2025 có 10 ngày phép) vs mới (12 ngày phép). | Expectation halt: `hr_leave_no_stale_10d_annual` phát hiện dòng 10 ngày phép. |
| `access_control_sop` | Document Parser | Bị loại bỏ nhầm do thiếu allowlist trong pipeline. | Cách ly nhầm vào quarantine (`unknown_doc_id`). |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| `chunk_id` | string | Có | Khóa định danh duy nhất ổn định sinh ra bằng SHA-256 hash từ `doc_id` + nội dung chunk. |
| `doc_id` | string | Có | ID logic của tài liệu (phải thuộc allowlist trong contract). |
| `chunk_text` | string | Có | Nội dung văn bản sạch (độ dài tối thiểu 8 ký tự, đã lọc bỏ meta tag, lặp từ, và lỗi chính tả). |
| `effective_date` | date | Có | Ngày hiệu lực của tài liệu định dạng ISO YYYY-MM-DD. |
| `exported_at` | datetime | Có | Thời gian xuất bản dữ liệu từ hệ thống nguồn. |

---

## 3. Quy tắc quarantine vs drop

- **Quarantine (Cách ly):** 
  Các dòng dữ liệu không đạt tiêu chuẩn validation (như sai format ngày, doc_id lạ không có trong allowlist, hoặc chứa nội dung chính sách cũ) sẽ bị đẩy vào file cách ly trong `artifacts/quarantine/quarantine_<run_id>.csv` thay vì bị xóa âm thầm. 
  *Biện pháp xử lý:* Đội ngũ Data Ops sẽ kiểm tra nguyên nhân cách ly, sửa đổi file cấu hình `data_contract.yaml` hoặc mã nguồn làm sạch, và chạy lại pipeline dữ liệu để merge lại.
- **Drop (Bỏ qua hoàn toàn):**
  Chỉ áp dụng với các dòng dữ liệu trống rỗng hoàn toàn sau khi làm sạch (`missing_chunk_text` hoặc `missing_effective_date` không có giá trị thay thế) hoặc các dòng trùng lặp nội dung văn bản (`duplicate_chunk_text`).

---

## 4. Phiên bản & Canonical (Source of Truth)

- **Policy Refund:** File canonical duy nhất là `policy_refund_v4.txt` trong thư mục `data/docs/`. Các quy định hoàn tiền cũ 14 ngày sẽ tự động được chuẩn hóa về 7 ngày.
- **HR Leave Policy:** Tệp tin canonical duy nhất là `hr_leave_policy.txt` trong thư mục `data/docs/`. Bản HR 2026 (ngày hiệu lực `>= 2026-01-01`) là nguồn chính thức quy định 12 ngày phép năm. Mọi dữ liệu phép năm cũ (10 ngày) từ năm 2025 đều bị loại bỏ hoặc cách ly.
