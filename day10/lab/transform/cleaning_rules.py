from __future__ import annotations

import csv
import hashlib
import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent

def load_data_contract() -> dict:
    contract_path = ROOT / "contracts" / "data_contract.yaml"
    if contract_path.exists():
        with contract_path.open("r", encoding="utf-8") as f:
            try:
                return yaml.safe_load(f) or {}
            except Exception:
                pass
    return {}

_CONTRACT = load_data_contract()

# Load ALLOWED_DOC_IDS and cutoff dates dynamically from data contract (Distinction Requirement)
_contract_doc_ids = _CONTRACT.get("allowed_doc_ids", [])
if _contract_doc_ids:
    ALLOWED_DOC_IDS = frozenset(_contract_doc_ids)
else:
    ALLOWED_DOC_IDS = frozenset(
        {
            "policy_refund_v4",
            "sla_p1_2026",
            "it_helpdesk_faq",
            "hr_leave_policy",
            "security_policy",
            "data_privacy_guideline",
            "access_control_sop",
        }
    )

_HR_LEAVE_MIN_DATE = _CONTRACT.get("policy_versioning", {}).get("hr_leave_min_effective_date", "2026-01-01")

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")

# Khai báo Regex cho Rule 1 (loại bỏ thẻ meta hệ thống hoặc ID trong ngoặc)
_SOURCE_TAG_PAT = re.compile(r"<[^>]+>|\[[^\]]+\]", re.IGNORECASE)



def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        return s, ""
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}", ""
    return "", "invalid_effective_date_format"


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    seq = 0

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_at = raw.get("exported_at", "")

        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        if doc_id == "hr_leave_policy" and eff_norm < _HR_LEAVE_MIN_DATE:
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        # 2. FIX DỮ LIỆU STALE (NỘI DUNG CŨ): 
        # Loại bỏ hẳn dòng chứa quy định phép năm cũ dù ngày export hợp lệ
        if doc_id == "hr_leave_policy" and ("10 ngày phép năm" in text or "10 ngày làm việc phép năm" in text):
            quarantine.append({**raw, "reason": "stale_hr_policy_content"})
            continue

        # 3. THÊM ≥3 RULE MỚI ĐỂ LÀM SẠCH TEXT
        fixed_text = text

        # Rule mới 1: Loại bỏ thẻ meta hệ thống 
        # metric_impact: Tránh cho mô hình RAG lấy các ID nội bộ không mang ý nghĩa nghiệp vụ làm nhiễu kết quả.
        fixed_text = _SOURCE_TAG_PAT.sub("", fixed_text)

        # Rule mới 2: Loại bỏ tiền tố gây nhiễu
        # metric_impact: Tối ưu vector ngữ nghĩa (embedding) bằng cách xóa bỏ từ khóa lỗi "!!!", "Nội dung không rõ ràng:" ở đầu chuỗi.
        fixed_text = fixed_text.replace("Nội dung không rõ ràng:", "").lstrip("! ").strip()

        # Rule mới 3: Sửa lỗi đánh máy lặp từ
        # metric_impact: Giảm chi phí token thừa và làm mượt ngữ nghĩa văn bản.
        if "làm việc làm việc" in fixed_text:
            fixed_text = fixed_text.replace("làm việc làm việc làm việc", "làm việc").replace("làm việc làm việc", "làm việc")

        # Rule mới 4: Bổ sung ngữ cảnh bị mất cho các ticket P1/P2/P3/P4
        # metric_impact: Bổ sung từ khóa "Ticket" vào trước "Escalation P1/P2" để mô hình embedding thu hẹp khoảng cách vector với các câu hỏi về ticket P1/P2, cải thiện độ chính xác retrieval.
        if fixed_text.startswith("Escalation P1:"):
            fixed_text = fixed_text.replace("Escalation P1:", "Ticket P1: Escalation:")
        elif fixed_text.startswith("Escalation P2:"):
            fixed_text = fixed_text.replace("Escalation P2:", "Ticket P2: Escalation:")

        if not fixed_text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        # Baseline: Fix stale refund
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            if "14 ngày làm việc" in fixed_text:
                fixed_text = fixed_text.replace(
                    "14 ngày làm việc",
                    "7 ngày làm việc",
                )
                fixed_text += " [cleaned: stale_refund_window]"

        key = _norm_text(fixed_text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)