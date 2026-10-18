"""Evidence freshness and triage indicators. No external requests or claims of live checks."""
from datetime import date
import pandas as pd
from lifecycle import COLUMNS, clean

TRIAGE_COLUMNS = ["brand", "part_number", "plm_code", "verification_status", "verified_at",
                  "review_age_days", "review_priority", "review_reason", "source_url"]
PRIORITIES = ["Review overdue", "Review approaching", "Needs evidence", "Demo only", "Fresh verified"]

def triage(records, *, as_of=None, review_interval_days=180, warning_days=30):
    """Assign a workflow priority, never infer actual manufacturer lifecycle state."""
    if not set(COLUMNS).issubset(records.columns):
        raise ValueError("Catalog missing lifecycle columns")
    if review_interval_days < 1 or warning_days < 0 or warning_days >= review_interval_days:
        raise ValueError("Invalid review frequency")
    as_of = as_of or date.today()
    if isinstance(as_of, str):
        as_of = date.fromisoformat(as_of)
    rows = []
    for rec in records[COLUMNS].itertuples(index=False):
        row = rec._asdict()
        state = row["verification_status"]
        age = ""
        if state == "demo":
            priority, reason = "Demo only", "Synthetic example; not verified"
        elif state != "verified":
            priority, reason = "Needs evidence", "No completed human verification"
        elif not row["source_url"] or not row["verified_at"]:
            priority, reason = "Needs evidence", "Verified flag is missing evidence or date"
        else:
            checked = date.fromisoformat(row["verified_at"])
            age = (as_of - checked).days
            if age < 0:
                priority, reason = "Needs evidence", "Verification date is in the future"
            elif age >= review_interval_days:
                priority, reason = "Review overdue", "Review interval exceeded; status not rechecked"
            elif age >= review_interval_days - warning_days:
                priority, reason = "Review approaching", "Manual review due soon"
            else:
                priority, reason = "Fresh verified", "Reviewed recently; not live monitored"
        rows.append({"brand": row["brand"], "part_number": row["part_number"],
                     "plm_code": row["plm_code"], "verification_status": state,
                     "verified_at": row["verified_at"], "review_age_days": age,
                     "review_priority": priority, "review_reason": reason,
                     "source_url": row["source_url"]})
    return pd.DataFrame(rows, columns=TRIAGE_COLUMNS)

def summarize_matches(result):
    """Count distinct and repeated customer identifiers without implying verification."""
    if not {"brand", "part_number", "plm_code", "verification_status"}.issubset(result.columns):
        raise ValueError("Result missing matching fields")
    normalized = result[["brand", "part_number"]].copy()
    normalized["brand"] = normalized["brand"].map(clean)
    normalized["part_number"] = normalized["part_number"].map(clean)
    return {
        "rows": len(result),
        "distinct_parts": len(normalized.drop_duplicates()),
        "duplicate_rows": len(result) - len(normalized.drop_duplicates()),
        "verified_rows": int((result["verification_status"] == "verified").sum()),
        "unknown_rows": int((result["plm_code"] == "UNKNOWN").sum()),
        "demo_rows": int((result["verification_status"] == "demo").sum()),
    }

def build_report(result, *, as_of=None):
    """Return CSV-ready fact-based report with per-row provenance/freshness warnings."""
    quality = triage(result, as_of=as_of)
    report = result.copy()
    report["review_priority"] = quality["review_priority"].to_numpy()
    report["review_reason"] = quality["review_reason"].to_numpy()
    report["review_age_days"] = quality["review_age_days"].to_numpy()
    report["data_notice"] = "Static catalog lookup; not a live manufacturer check"
    return report
