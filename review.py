"""Manual, operator-controlled review workflow. No web requests or automatic approvals."""
from datetime import date, datetime, timezone
from urllib.parse import urlparse
import pandas as pd

from lifecycle import COLUMNS, VALID_CODES, clean, load_records

REVIEW_FIELDS = ["brand", "part_number", "plm_code", "status", "effective_date",
                 "source_url", "verified_at", "evidence_note", "rights_basis"]
AUDIT_COLUMNS = ["recorded_at_utc", "reviewer_id", "brand", "part_number",
                 "previous_plm_code", "new_plm_code", "previous_status", "new_status",
                 "source_url", "verified_at", "evidence_note", "rights_basis"]
RIGHTS_BASIS = {"official_link_and_factual_summary", "explicit_permission"}

def review_queue(records, unmatched=None):
    """Draft worksheet for actual non-demo records; never promotes a demo."""
    base = records.loc[records["verification_status"] != "demo", ["brand", "part_number"]].copy()
    if unmatched is not None:
        incoming = unmatched[["brand", "part_number"]].copy()
        incoming["brand"] = incoming["brand"].map(clean)
        incoming["part_number"] = incoming["part_number"].map(clean)
        base = pd.concat([base, incoming], ignore_index=True)
    base = base.loc[(base["brand"] != "") & (base["part_number"] != "")]
    base = base.drop_duplicates(["brand", "part_number"]).reset_index(drop=True)
    for column in REVIEW_FIELDS:
        if column not in base:
            base[column] = ""
    return base[REVIEW_FIELDS]

def validate_proposal(proposal, records):
    """Check structure only; a human must actually inspect rights and source evidence."""
    if len(proposal) != 1 or not set(REVIEW_FIELDS).issubset(proposal.columns):
        raise ValueError("Review proposal must contain exactly one row with all required columns")
    row = {col: str(proposal.iloc[0][col]).strip() for col in REVIEW_FIELDS}
    row["brand"], row["part_number"] = clean(row["brand"]), clean(row["part_number"])
    row["plm_code"] = clean(row["plm_code"])
    if not row["brand"] or not row["part_number"]:
        raise ValueError("Brand and part number are required")
    if row["brand"] == "DEMOCO" or row["plm_code"] not in VALID_CODES - {"DEMO", "UNKNOWN"}:
        raise ValueError("Demo records and demo/unknown PLM codes cannot be approved")
    existing = records.loc[(records["brand"] == row["brand"]) &
                           (records["part_number"] == row["part_number"])]
    if not existing.empty and existing.iloc[0]["verification_status"] == "demo":
        raise ValueError("Demo records cannot be promoted")
    url = urlparse(row["source_url"])
    if (url.scheme != "https" or not url.hostname or url.username or url.password or
            not url.hostname.lower().endswith((".com", ".de", ".net", ".org", ".gov", ".edu"))):
        raise ValueError("An HTTPS source URL with a recognizable domain is required")
    try:
        checked = date.fromisoformat(row["verified_at"])
    except ValueError as exc:
        raise ValueError("verified_at must be a real ISO date") from exc
    if checked > date.today():
        raise ValueError("Verification date cannot be in the future")
    if row["effective_date"]:
        try:
            date.fromisoformat(row["effective_date"])
        except ValueError as exc:
            raise ValueError("effective_date must be a real ISO date") from exc
    if len(row["evidence_note"]) < 20:
        raise ValueError("A meaningful evidence note (20+ characters) is required")
    if row["rights_basis"] not in RIGHTS_BASIS:
        raise ValueError("A documented data usage rights basis is required")
    if not row["status"]:
        raise ValueError("Human-readable status is required")
    return row

def approve_review(records, audit, proposal, reviewer_id, *, source_reviewed=False, rights_checked=False):
    """Operator confirmation is required. Return updated frames; caller saves locally."""
    if not (source_reviewed and rights_checked):
        raise ValueError("Explicit source and usage-rights confirmations are required")
    reviewer_id = str(reviewer_id).strip()
    if not (3 <= len(reviewer_id) <= 60) or any(c in reviewer_id for c in "\r\n,"):
        raise ValueError("Use a 3-60 character non-sensitive reviewer ID")
    if not set(AUDIT_COLUMNS).issubset(audit.columns):
        raise ValueError("Audit log is missing required columns")
    row = validate_proposal(proposal, records)
    same = (records["brand"] == row["brand"]) & (records["part_number"] == row["part_number"])
    prior = records.loc[same]
    old_code = prior.iloc[0]["plm_code"] if len(prior) else ""
    old_status = prior.iloc[0]["status"] if len(prior) else ""
    updated = records.loc[~same, COLUMNS].copy()
    new_record = {col: row[col] for col in COLUMNS if col in row}
    new_record["verification_status"] = "verified"
    updated = pd.concat([updated, pd.DataFrame([new_record], columns=COLUMNS)], ignore_index=True)
    event = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reviewer_id": reviewer_id,
        "brand": row["brand"], "part_number": row["part_number"],
        "previous_plm_code": old_code, "new_plm_code": row["plm_code"],
        "previous_status": old_status, "new_status": row["status"],
        "source_url": row["source_url"], "verified_at": row["verified_at"],
        "evidence_note": row["evidence_note"], "rights_basis": row["rights_basis"],
    }
    updated_audit = pd.concat([audit[AUDIT_COLUMNS], pd.DataFrame([event])], ignore_index=True)
    return updated, updated_audit

def validate_publication(records, audit):
    """Reject published verified records without a corresponding matching audit event."""
    if not set(AUDIT_COLUMNS).issubset(audit.columns):
        raise ValueError("Missing review audit columns")
    for row in records.itertuples(index=False):
        if row.verification_status != "verified":
            continue
        events = audit.loc[
            (audit["brand"] == row.brand) &
            (audit["part_number"] == row.part_number) &
            (audit["new_plm_code"] == row.plm_code) &
            (audit["new_status"] == row.status) &
            (audit["source_url"] == row.source_url) &
            (audit["verified_at"] == row.verified_at)
        ]
        if events.empty:
            raise ValueError("Verified record missing a matching review audit event: " + row.part_number)
        if not events["rights_basis"].isin(RIGHTS_BASIS).any():
            raise ValueError("Verified record missing acceptable rights basis: " + row.part_number)
    return True
