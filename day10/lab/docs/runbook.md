# Runbook — Lab Day 10 (Incident Triage & Mitigation)

Tài liệu hướng dẫn vận hành và khắc phục sự cố dữ liệu cho hệ thống RAG Customer Support & IT Helpdesk.

---

## Symptom (Triệu chứng)
- Người dùng nhận được thông tin cũ hoặc không chính xác từ Agent (Ví dụ: chính sách hoàn tiền báo là "14 ngày làm việc" thay vì "7 ngày làm việc" của v4, hoặc số ngày phép năm của nhân viên dưới 3 năm kinh nghiệm báo là "10 ngày" thay vì "12 ngày").
- Agent không thể trả lời được các câu hỏi liên quan đến tài liệu mới cập nhật (Ví dụ: Quy trình cấp quyền Level 4 Admin Access trong `access_control_sop`).

---

## Detection (Phát hiện)
- **Freshness SLA Alert:** Hệ thống kiểm tra Freshness phát hiện tuổi dữ liệu vượt quá 24 giờ (`freshness_check=FAIL` hoặc `reason=freshness_sla_exceeded`).
- **Expectation Suite Halt:** Pipeline bị dừng đột ngột (HALT) ở bước validate khi chạy `etl_pipeline.py` do các quy tắc kiểm tra chất lượng bị vi phạm (Ví dụ: `refund_no_stale_14d_window` hoặc `hr_leave_no_stale_10d_annual` báo FAIL).
- **Retrieval Evaluation:** Đánh giá định kỳ bằng `eval_retrieval.py` phát hiện `hits_forbidden=yes` hoặc `contains_expected=no`.

---

## Diagnosis (Chẩn đoán)

| Bước | Việc làm | Kết quả mong đợi / Cách phân tích |
|------|----------|----------------------------------|
| 1 | Kiểm tra file manifest gần nhất trong `artifacts/manifests/manifest_<run_id>.json` | Xác định `run_timestamp`, `latest_exported_at` để đánh giá độ trễ dữ liệu và kiểm tra xem có cờ `--no-refund-fix` hay `--skip-validate` nào được bật hay không. |
| 2 | Mở file cách ly trong `artifacts/quarantine/quarantine_<run_id>.csv` | Phân tích cột `reason` để tìm nguyên nhân dữ liệu bị đẩy vào quarantine (Ví dụ: `unknown_doc_id` do chưa đăng ký nguồn, `stale_hr_policy_content` do xung đột nội dung cũ, hoặc `invalid_effective_date_format`). |
| 3 | Chạy thử truy vấn thủ công và xem file eval | Chạy `python eval_retrieval.py --out artifacts/eval/temp_eval.csv` để xem tài liệu nào đang xếp hạng Top-1 (`top1_doc_id`) và xem nội dung preview có bị nhiễu bởi các thẻ meta hệ thống hay lặp từ hay không. |

---

## Mitigation (Khắc phục tạm thời)
1. **Sửa quy tắc lọc & chạy lại pipeline:**
   Cập nhật các quy tắc trong `transform/cleaning_rules.py` (allowlist, loại bỏ stale content) và chạy:
   ```bash
   .venv\Scripts\python.exe etl_pipeline.py run
   ```
2. **Loại bỏ "mồi cũ" (Pruning):**
   Đảm bảo bước publish vector store thực hiện prune (xóa) tất cả các vector ID cũ không còn xuất hiện trong tệp dữ liệu đã làm sạch của run hiện tại để tránh nhiễu kết quả của Agent.
3. **Rollback dữ liệu:**
   Nếu dữ liệu mới bị hỏng nghiêm trọng và không thể sửa ngay, tiến hành rollback vector database về snapshot sạch gần nhất và phát cảnh báo bảo trì dữ liệu trên UI.

---

## Prevention (Phòng ngừa dài hạn)
1. **Ràng buộc dữ liệu qua Data Contract:**
   Đồng bộ hóa toàn bộ danh sách tài liệu hợp lệ (`allowed_doc_ids`) và các cấu hình versioning (như ngày hiệu lực tối thiểu `hr_leave_min_effective_date`) vào `contracts/data_contract.yaml`. Không hard-code trong mã nguồn.
2. **Mở rộng các bộ giám sát (Expectation Suite):**
   Duy trì các quy tắc kiểm tra nghiêm ngặt như kiểm tra sự hiện diện của toàn bộ tài liệu cốt lõi (`core_docs_present`) và loại bỏ trùng lặp văn bản để chặn đứng dữ liệu bẩn trước khi embed.
3. **Cấu hình tự động kiểm tra Freshness hàng ngày:**
   Chạy tác vụ kiểm tra độ tươi của dữ liệu định kỳ và gửi cảnh báo trực tiếp về kênh `#data-ops-alerts` khi có sự cố.
