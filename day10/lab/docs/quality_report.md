# Quality Report — Lab Day 10 (Cá nhân)

Tài liệu báo cáo chất lượng dữ liệu và so sánh kết quả retrieval trước/sau khi chạy pipeline làm sạch.

**run_id:** `2026-06-10T09-40Z`  
**Ngày:** 2026-06-10  

---

## 1. Tóm tắt số liệu chất lượng

Dưới đây là so sánh số liệu giữa phiên chạy dữ liệu lỗi bị tiêm nhiễm (Injected Bad Run) và phiên chạy dữ liệu sạch chuẩn (Cleaned Run):

| Chỉ số | Trước (Injected Bad Run) | Sau (Cleaned Run) | Ghi chú |
|--------|--------------------------|-------------------|---------|
| **run_id** | `inject-bad` | `2026-06-10T09-40Z` | Phiên bản chuẩn so với phiên bản test lỗi |
| **raw_records** | 247 | 247 | Tổng số dòng thô nạp vào giống nhau |
| **cleaned_records** | 37 | 37 | Số lượng dòng sạch được nạp vào Chroma |
| **quarantine_records**| 210 | 210 | Số lượng dòng bẩn bị đẩy vào Quarantine |
| **Expectation halt?** | **YES** (Bị bỏ qua do `--skip-validate` để demo) | **NO** (Tất cả expectations đều PASS) | Expectation `refund_no_stale_14d_window` bị vi phạm ở bản test lỗi. |

---

## 2. Before / After Retrieval Evidence

Kết quả so sánh giữa hai phiên chạy được lấy trực tiếp từ `after_inject_bad.csv` và `eval_after_fix.csv` trong thư mục `artifacts/eval/`:

### Câu hỏi then chốt: Chính sách hoàn tiền (`q_refund_window`)
- **Trước (Injected Bad Run):**
  - **top1_doc_id:** `policy_refund_v4`
  - **top1_preview:** `"Yêu cầu hoàn tiền được chấp nhận trong vòng 14 ngày làm việc kể từ xác nhận đơn."`
  - **contains_expected:** `yes`
  - **hits_forbidden:** `yes` (Bị dính lỗi nghiêm trọng do trích xuất thông tin cũ 14 ngày).
- **Sau (Cleaned Run):**
  - **top1_doc_id:** `policy_refund_v4`
  - **top1_preview:** `"Yêu cầu được gửi trong vòng 7 ngày làm việc kể từ thời điểm xác nhận đơn hàng."`
  - **contains_expected:** `yes`
  - **hits_forbidden:** `no` (Hoàn toàn chính xác, dọn sạch thông tin 14 ngày cũ và thay bằng 7 ngày hiện hành).

### Câu hỏi Merit: Versioning HR (`q_hr_annual_leave_under3`)
- **Trước (Injected Bad Run) và Sau (Cleaned Run):**
  - Cả hai phiên chạy đều trả về kết quả chính xác: `"Nhân viên dưới 3 năm kinh nghiệm được 12 ngày phép năm theo chính sách 2026."`
  - **contains_expected:** `yes`
  - **hits_forbidden:** `no`
  - **top1_doc_expected:** `yes`
  - *Giải thích:* Do logic dọn dẹp stale effective date và stale content của chính sách nhân sự luôn hoạt động độc lập với cờ `--no-refund-fix`.

---

## 3. Freshness & Monitor

- **Kết quả freshness_check:** `FAIL`
- **Chi tiết:**
  - `latest_exported_at`: `2026-04-10T00:00:00`
  - `age_hours`: `1473.69` giờ
  - `sla_hours`: `24.0` giờ
  - `reason`: `freshness_sla_exceeded`
- **Giải thích SLA:** 
  Do dữ liệu CSV mẫu (`policy_export_dirty.csv`) có timestamp xuất bản cũ (`2026-04-10`), kết quả cảnh báo trễ SLA là hoàn toàn chính xác. Trong vận hành thực tế, một cảnh báo Alert sẽ được gửi trực tiếp về kênh `#data-ops-alerts` để đội ngũ vận hành kích hoạt quy trình kéo dữ liệu mới từ các DB/API nguồn.

---

## 4. Corruption Inject (Sprint 3)

Để kiểm chứng tính bền vững của chất lượng dữ liệu và bộ giám sát, chúng tôi đã thực hiện tiêm dữ liệu bẩn bằng cách chạy:
```bash
.venv\Scripts\python.exe etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
```
- **Cách phá hỏng:** Tắt quy tắc tự động sửa thời hạn hoàn tiền từ 14 ngày về 7 ngày (`--no-refund-fix`).
- **Cách phát hiện:** Bộ giám sát (Expectation suite) phát hiện vi phạm và báo lỗi ngay lập tức:
  `expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=1`
  Đồng thời, khi chạy đánh giá retrieval, kết quả trả về bị dính từ khóa cấm (`hits_forbidden=yes`), làm chứng cứ rõ ràng để phát hiện lỗi dữ liệu.

---

## 5. Hạn chế & việc chưa làm
- Việc kiểm tra Freshness hiện tại chỉ dựa vào manifest tĩnh thay vì truy vấn động vào watermark của vector DB.
- Bộ từ khóa trong file kiểm thử tự động `test_questions.json` còn đơn giản, chưa tích hợp LLM-judge làm bộ đánh giá ngữ nghĩa thông minh hơn.
