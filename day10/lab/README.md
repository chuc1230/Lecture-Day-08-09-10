# Lab Day 10 — Data Pipeline & Data Observability

## THÔNG TIN CÁ NHÂN & THỰC HIỆN
- **Học viên thực hiện:** Đặng Minh Chức-2A202600611
- **Lớp:** C401
- **Ngày nộp:** 2026-06-10

---

## HƯỚNG DẪN CHẠY CHƯƠNG TRÌNH (EXECUTION GUIDE)

### Bước 1: Thiết lập môi trường và kích hoạt Virtual Environment (venv)
1. Mở cửa sổ Terminal (PowerShell hoặc Command Prompt) tại thư mục dự án `lab`.
2. Tạo môi trường ảo (nếu chưa có):
   ```bash
   python -m venv .venv
   ```
3. Kích hoạt môi trường ảo:
   * **Windows (PowerShell):**
     ```powershell
     .venv\Scripts\Activate.ps1
     ```
   * **Windows (Cmd):**
     ```cmd
     .venv\Scripts\activate.bat
     ```
   * **Linux / macOS:**
     ```bash
     source .venv/bin/activate
     ```
4. Cài đặt các thư viện phụ thuộc:
   ```bash
   pip install -r requirements.txt
   ```
5. Chuẩn bị file cấu hình môi trường:
   ```bash
   cp .env.example .env
   ```

### Bước 2: Chạy Pipeline dữ liệu chuẩn (Ingest -> Clean -> Validate -> Embed)
Thực thi pipeline để tự động nạp dữ liệu thô, làm sạch theo các quy tắc, kiểm định expectations và re-embed vào ChromaDB:
```bash
python etl_pipeline.py run
```
*Lưu ý:* Lệnh này phải hoàn thành với thông báo thành công `PIPELINE_OK`.

### Bước 3: Chạy đánh giá chất lượng truy vấn tự kiểm (Evaluation)
Đánh giá chất lượng retrieval trên 21 câu hỏi mẫu để sinh file so sánh:
```bash
python eval_retrieval.py --out artifacts/eval/eval_after_fix.csv
```

### Bước 4: Chạy kiểm tra chấm điểm chính thức (10 câu hỏi đánh giá)
Sinh ra kết quả đánh giá 10 câu hỏi nghiệp vụ chính thức dưới dạng JSONL:
```bash
python grading_run.py --out artifacts/eval/grading_run.jsonl
```

### Bước 5: Chạy công cụ tự kiểm tra của giảng viên (Sanity Check)
Kiểm tra định dạng và trạng thái đạt/không đạt của file grading kết quả:
```bash
python instructor_quick_check.py --grading artifacts/eval/grading_run.jsonl
```

### Bước phụ: Chạy thử nghiệm dữ liệu lỗi (Inject Corruption)
Để thử nghiệm tiêm dữ liệu lỗi hoàn tiền 14 ngày làm việc và bỏ qua kiểm định (phục vụ đối chứng):
```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
python eval_retrieval.py --out artifacts/eval/after_inject_bad.csv
```
*(Sau khi chạy thử nghiệm lỗi, vui lòng chạy lại lệnh ở Bước 2 để trả cơ sở dữ liệu vector store về trạng thái dữ liệu sạch).*

---

## TỔNG QUAN KIẾN THỨC & VẤN ĐỀ GIẢI QUYẾT TRONG BÀI LAB

### 1. Luồng xử lý dữ liệu từ các tài liệu gốc (Raw TXT) sang Vector Store
- **Nguồn gốc (data/docs/):** Hệ thống quản trị lưu trữ 5 tài liệu nghiệp vụ chuẩn (`policy_refund_v4.txt`, `sla_p1_2026.txt`, `it_helpdesk_faq.txt`, `hr_leave_policy.txt`, `access_control_sop.txt`).
- **Phân mảnh thô (CSV Export):** Khi các hệ thống xuất bản dữ liệu thô ra tệp CSV `data/raw/policy_export_dirty.csv`, dữ liệu bị bẩn (chính sách hoàn tiền 14 ngày cũ, ngày phép 10 ngày cũ của năm 2025, lỗi định dạng ngày tháng, dính meta tag hệ thống, lặp từ chính tả và mất từ khóa ngữ cảnh quan trọng như "Ticket").
- **Chuẩn hóa & Đồng bộ:** Pipeline đóng vai trò cầu nối, tự động sửa đổi chính sách hoàn tiền 14 ngày thành 7 ngày, lọc bỏ phép năm cũ dưới 2026, loại bỏ thẻ rác, và khôi phục từ khóa ngữ cảnh `"Ticket P1/P2: "` để đảm bảo dữ liệu khi được nhúng (embedded) vào ChromaDB luôn sạch và có độ liên quan ngữ nghĩa cực cao.

### 2. Cách thức hoạt động của Pipeline
- **Ingest:** Đọc CSV dữ liệu thô, khởi tạo `run_id` duy nhất và ghi nhận số lượng dòng đầu vào.
- **Clean (Transform):** Áp dụng các quy tắc làm sạch dữ liệu. Để đạt yêu cầu **Distinction**, danh sách `allowed_doc_ids` và ngày phép năm tối thiểu `_HR_LEAVE_MIN_DATE` được tải động từ file cấu hình `data_contract.yaml` thay vì hard-code trong code.
- **Validate (Quality Gate):** Thực thi 8 quy tắc kiểm định (E1 đến E8). Nếu phát hiện lỗi nghiêm trọng (Halt severity) như ngày hiệu lực sai định dạng hoặc thiếu tài liệu cốt lõi, pipeline lập tức dừng lại, ngăn ngừa dữ liệu lỗi rò rỉ vào hệ thống phục vụ Agent.
- **Embed (Load):** Chuyển đổi văn bản sạch thành vector embeddings qua mô hình `all-MiniLM-L6-v2`, thực hiện **Snapshot Sync** (upsert vector mới theo `chunk_id` và tự động prune/xóa các vector ID cũ không còn nằm trong tập dữ liệu sạch hiện tại để tránh "mồi cũ" gây nhiễu).

---

## Bối cảnh

Vector store và agent Day 09 chỉ ổn nếu **pipeline ingest → clean → validate → publish** ổn. Lab này mô phỏng:

- Export "raw" từ **5 hệ thống nguồn** (CSV mẫu) có **duplicate**, **dòng thiếu ngày**, **doc_id lạ**, **ngày hiệu lực không ISO**, **xung đột version HR (10 vs 12 ngày phép)**, **chunk policy sai cửa sổ hoàn tiền (14 vs 7 ngày)**, và **nguồn dữ liệu chưa được đăng ký trong pipeline**.
- Pipeline baseline được cung cấp nhưng **chưa hoàn chỉnh** — học viên phải phân tích dữ liệu raw, phát hiện lỗ hổng trong code, sửa và mở rộng pipeline để embed **toàn bộ** dữ liệu cần thiết vào vector database.
- Nhóm phải có **log số record**, **quarantine**, **expectation halt có kiểm soát**, **run_id** trên manifest, và **bằng chứng before/after** trên retrieval test.

---

## Mục tiêu học tập

| Mục tiêu | Sprint |
|----------|--------|
| Phân tích raw data + phát hiện pipeline gaps + sửa pipeline | Sprint 1 |
| Cleaning rules + cleaned CSV + quarantine + embed | Sprint 1–2 |
| Expectation suite (≥2 mới) + chạy pipeline thành công | Sprint 2 |
| Inject corruption + so sánh eval + quality report | Sprint 3 |
| Freshness check + runbook + hoàn thiện docs & báo cáo | Sprint 4 |

---

## Nhiệm vụ chính — Pipeline cần sửa gì?

> **Pipeline baseline chưa hoàn chỉnh.** Dữ liệu raw chứa export từ **5 hệ thống nguồn**, nhưng pipeline hiện tại chỉ nhận diện và xử lý **một phần**. Học viên cần tự phân tích và sửa pipeline để embed đủ dữ liệu, đảm bảo trả lời đúng **tất cả 10 câu hỏi đánh giá** trong `data/grading_questions.json`.

### Quy trình gợi ý

**Bước 1 — Chạy pipeline lần đầu và quan sát:**

```bash
python etl_pipeline.py run
```

Pipeline sẽ **HALT** do expectation phát hiện dữ liệu chưa sạch. Đọc kỹ log để hiểu lý do.

**Bước 2 — Phân tích dữ liệu raw:**

- Có bao nhiêu `doc_id` **unique** trong `data/raw/policy_export_dirty.csv`? có 20 
- `ALLOWED_DOC_IDS` trong `transform/cleaning_rules.py` chứa những doc_id nào? "policy_refund_v4", "sla_p1_2026", "it_helpdesk_faq", "hr_leave_policy",
- Có nguồn dữ liệu hợp lệ nào trong CSV bị pipeline **bỏ qua** (quarantine nhầm) không? có
 - security_policy (Tài liệu thật về bảo mật hệ thống quản trị, hiện đang bị gạt nhầm vào quarantine)   
 - data_privacy_guideline (Tài liệu thật về mã hóa dữ liệu người dùng, hiện đang bị gạt nhầm vào quarantine)   
 - access_control_sop (Tài liệu thật về quy trình phân quyền quản trị năm 2026, hiện đang bị gạt nhầm vào quarantine)   
**Bước 3 — Đối chiếu với câu hỏi đánh giá:**

- Mở `data/grading_questions.json`, kiểm tra trường `expect_top1_doc_id` — cần những nguồn nào?
 - "policy_refund_v4", "sla_p1_2026", "it_helpdesk_faq", "hr_leave_policy", "access_control_sop"
- So sánh với những gì pipeline hiện tại cho phép — thiếu nguồn nào? "access_control_sop"

**Bước 4 — Sửa pipeline:**

Cần sửa `transform/cleaning_rules.py` (và có thể cả `quality/expectations.py`):
1. Cập nhật allowlist nếu phát hiện nguồn hợp lệ bị thiếu.
2. Thêm cleaning rules để loại bỏ dữ liệu stale (ví dụ: nội dung chính sách cũ vẫn xuất hiện dù ngày export mới).
3. Thêm ≥ **3 rule mới** và ≥ **2 expectation mới** (xem yêu cầu Sprint 2).
4. Đảm bảo `python etl_pipeline.py run` **exit 0** — tất cả expectations phải pass.

**Bước 5 — Kiểm tra kết quả:**

```bash
# Test retrieval tự kiểm (21 câu)
python eval_retrieval.py --out artifacts/eval/eval_after_fix.csv

# Grading chính thức (10 câu)
python grading_run.py --out artifacts/eval/grading_run.jsonl
```

Kiểm tra: `contains_expected` phải `true` và `hits_forbidden` phải `false` cho tất cả câu hỏi.

---

## Cấu trúc thư mục

```
lab/
├── etl_pipeline.py           # Sprint 1–2: run ingest→clean→validate→embed
├── eval_retrieval.py         # Sprint 3–4: before/after retrieval (CSV)
├── grading_run.py            # Grading chính thức — 10 câu đánh giá
├── instructor_quick_check.py # GV: sanity artifact grading/manifest (tuỳ chọn)
│
├── transform/
│   └── cleaning_rules.py     # ⚠️ Baseline chưa đủ — sinh viên phải sửa + mở rộng
├── quality/
│   └── expectations.py       # Baseline expectations — sinh viên thêm ≥2 mới
├── monitoring/
│   └── freshness_check.py    # Đọc manifest + SLA đơn giản
│
├── contracts/
│   └── data_contract.yaml    # Contract dữ liệu — điền owner/SLA
│
├── data/
│   ├── docs/                 # 5 tài liệu gốc (policy, SLA, FAQ, HR, access control)
│   ├── raw/
│   │   └── policy_export_dirty.csv   # Export bẩn từ 5 hệ thống nguồn
│   ├── test_questions.json           # 21 câu tự kiểm (retrieval + keyword)
│   └── grading_questions.json        # 10 câu đánh giá chính thức
│
├── artifacts/
│   ├── logs/
│   ├── manifests/
│   ├── quarantine/
│   ├── cleaned/
│   └── eval/
│
├── docs/
│   ├── pipeline_architecture.md
│   ├── data_contract.md
│   ├── runbook.md
│   └── quality_report_template.md
│
├── reports/
│   ├── group_report.md
│   └── individual/
│       └── template.md
│
├── requirements.txt
└── .env.example
```

---

## Setup

```bash
cd lab
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

**Lần đầu** SentenceTransformers có thể tải model `all-MiniLM-L6-v2` (~90MB) — cần mạng.

---

## Chạy pipeline

### Luồng chuẩn (sau khi đã sửa pipeline)

```bash
# Chạy toàn bộ: ingest → clean → validate → embed
python etl_pipeline.py run

# Kiểm tra freshness
python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_<run-id>.json
```

### Eval retrieval (sau khi đã embed)

```bash
python eval_retrieval.py --out artifacts/eval/after_fix_eval.csv
cat artifacts/eval/after_fix_eval.csv
```

> **Ghi chú eval:** `hits_forbidden` quét **toàn bộ top-k** chunk ghép lại (không chỉ top-1), để phát hiện "câu trả lời nhìn đúng nhưng context vẫn còn chunk stale".  
> **Index snapshot:** sau mỗi lần `run`, embed **upsert** theo `chunk_id` và **xoá id không còn trong cleaned** để tránh vector cũ làm fail grading.

### Sprint 3 — Inject corruption (embed dữ liệu "xấu", bỏ qua halt)

```bash
python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate
python eval_retrieval.py --out artifacts/eval/after_inject_bad.csv
# So sánh với file eval sau khi chạy lại pipeline chuẩn
```

### Grading chính thức (10 câu)

```bash
python grading_run.py --out artifacts/eval/grading_run.jsonl
```

**Giảng viên — kiểm tra nhanh artifact (tuỳ chọn):**

```bash
python instructor_quick_check.py --grading artifacts/eval/grading_run.jsonl
python instructor_quick_check.py --manifest artifacts/manifests/manifest_<run-id>.json
```

---

## 4 Sprints (chi tiết)

### Sprint 1 (60') — Phân tích & Ingest

- Đọc `data/raw/policy_export_dirty.csv` — liệt kê các `doc_id` unique, đếm số record mỗi loại.
- **Chạy pipeline lần đầu** → quan sát HALT → đọc log xác định nguyên nhân.
- **So sánh** `doc_id` trong CSV vs `ALLOWED_DOC_IDS` trong `cleaning_rules.py` → phát hiện nguồn bị thiếu.
- **Đối chiếu** `expect_top1_doc_id` trong `grading_questions.json` → xác nhận cần sửa gì.
- Bắt đầu sửa `cleaning_rules.py`: cập nhật allowlist, thêm rules cho dữ liệu stale.
- Điền **source map** ngắn trong `docs/data_contract.md` (ít nhất 2 nguồn / failure mode / metric).

**DoD:** Log có `raw_records`, `cleaned_records`, `quarantine_records`, `run_id`. Hiểu tại sao pipeline halt.

---

### Sprint 2 (60') — Clean + validate + embed

- Hoàn thiện sửa pipeline: pipeline phải **exit 0** với expectation không halt.
- Thêm ≥ **3 rule mới** và ≥ **2 expectation mới** (đếm trên file nhận được).
- **Chống trivial:** mỗi rule/expectation mới phải có **tác động đo được** — ghi trong `reports/group_report.md` bảng *metric_impact* (ví dụ: `quarantine_records` tăng khi inject, `expectation X fail` trước khi fix). Rule chỉ "strip space" mà không đổi số liệu → **trừ điểm**.
- Đảm bảo embed **idempotent** (upsert `chunk_id` + prune id thừa — baseline đã làm).

**DoD:** `python etl_pipeline.py run` exit 0. `python grading_run.py` → kiểm tra nhanh kết quả.

---

### Sprint 3 (60') — Inject corruption & before/after

- Cố ý làm hỏng dữ liệu (`--no-refund-fix --skip-validate`) → lưu eval "xấu".
- Chạy lại pipeline chuẩn → lưu eval "tốt".
- Lưu **2 file eval** so sánh + ảnh chụp / đoạn log chứng minh.
- Hoàn thành quality report theo `docs/quality_report_template.md`.

**DoD:** Có số liệu chứng minh retrieval **tệ hơn** trước fix và **tốt hơn** sau fix.

---

### Sprint 4 (60') — Monitoring + docs + báo cáo

- Điền `docs/pipeline_architecture.md`, `docs/data_contract.md`, `docs/runbook.md`.
- `python etl_pipeline.py freshness --manifest …` — giải thích PASS/WARN/FAIL trong runbook.
- Chạy `python grading_run.py` lần cuối → verify 10 câu đều pass.
- Hoàn thành `reports/group_report.md` + mỗi người `reports/individual/[ten].md`.

**DoD:** Grading JSONL hợp lệ. README nhóm có "một lệnh chạy cả pipeline". Peer review 3 câu hỏi ghi trong group report.

---

## Deliverables (nộp bài)

| Item | Ghi chú |
|------|---------|
| `etl_pipeline.py` + `transform/` + `quality/` + `monitoring/` | Có thể mở rộng file, không xóa entrypoint bắt buộc |
| `contracts/data_contract.yaml` | Điền owner, SLA, nguồn |
| `artifacts/logs/`, `manifests/`, `quarantine/`, `eval/` | Ít nhất 1 run "tốt" + evidence inject |
| `docs/*.md` (3 file + quality report) | Theo template |
| `reports/group_report.md` | |
| `reports/individual/*.md` | Mỗi thành viên |
| `artifacts/eval/grading_run.jsonl` | 10 câu: `gq_d10_01` … `gq_d10_10` |

---

## Dữ liệu trong raw CSV

Raw CSV (`data/raw/policy_export_dirty.csv`) chứa export từ nhiều hệ thống. Dưới đây là tham khảo (không phải đáp án — học viên tự phân tích):

| Nguồn dữ liệu | Tài liệu tham khảo | Ghi chú |
|----------------|---------------------|---------|
| `policy_refund_v4` | `data/docs/policy_refund_v4.txt` | Có chunk stale "14 ngày" cần fix |
| `sla_p1_2026` | `data/docs/sla_p1_2026.txt` | SLA và quy trình xử lý sự cố |
| `it_helpdesk_faq` | `data/docs/it_helpdesk_faq.txt` | FAQ IT nội bộ |
| `hr_leave_policy` | `data/docs/hr_leave_policy.txt` | Có xung đột version 2025 vs 2026 |
| `access_control_sop` | `data/docs/access_control_sop.txt` | Quy trình cấp quyền truy cập |
| `invalid_doc_*`, `legacy_*` | (không có tài liệu) | Export lỗi / hệ thống cũ |

> **Lưu ý:** Không phải tất cả nguồn dữ liệu đều được pipeline baseline xử lý. Học viên cần tự phát hiện và sửa.

---

## Phân vai (gợi ý — đồng bộ slide Hands-on 10)

| Vai | Trách nhiệm | Sprint chính |
|-----|-------------|----------------|
| **Ingestion Owner** | raw paths, logging, manifest, phân tích doc_id | 1 |
| **Cleaning / Quality Owner** | `cleaning_rules.py`, `expectations.py`, quarantine | 1–3 |
| **Embed Owner** | Chroma collection, idempotency, eval, grading verify | 2–3 |
| **Monitoring / Docs Owner** | freshness, runbook, 3 docs, group report | 4 |

---

## Debug order (nhắc từ slide Day 10)

```
Freshness / version → Volume & errors → Schema & contract → Lineage / run_id → mới đến model/prompt
```

---

## Tài nguyên tham khảo

- Slide: [`../lecture-10.html`](../lecture-10.html)
- Lab Day 09 (orchestration): [`../../day09/lab/README.md`](../../day09/lab/README.md)
- Great Expectations (tuỳ chọn nâng cao): https://docs.greatexpectations.io/
- ChromaDB: https://docs.trychroma.com/
