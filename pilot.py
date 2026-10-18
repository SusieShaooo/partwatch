"""Privacy-conscious pilot evaluation. No customer accounts, storage, or network actions."""
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd
from lifecycle import clean

CANDIDATE_COLS = ["brand","part_number","observed_plm_code","observed_status",
                  "source_url","source_region","evidence_seen_in_search",
                  "manual_review_state","usage_rights_review","notes"]
FEEDBACK_COLS = ["participant_code","business_type","parts_checked","tasks_completed",
                 "useful_result","time_saved_estimate_minutes","biggest_problem",
                 "would_use_again","willingness_to_pay_usd_month","permission_to_share_anonymized"]
BUSINESS_TYPES = {"distributor","maintenance_team","repair_shop","other"}
YES_NO_UNSURE = {"yes","no","unsure"}
PRICE_OPTIONS = {"0","29","49","99","unsure"}

def load_candidates(path=None):
    path = Path(path) if path else Path(__file__).with_name("pilot_candidates.csv")
    records = pd.read_csv(path,dtype=str,keep_default_na=False)
    if not set(CANDIDATE_COLS).issubset(records.columns):
        raise ValueError("Missing candidate fields")
    records = records[CANDIDATE_COLS].copy()
    records["brand"] = records["brand"].map(clean)
    records["part_number"] = records["part_number"].map(clean)
    if records.duplicated(["brand","part_number"]).any():
        raise ValueError("Duplicate pilot candidates")
    if not records["manual_review_state"].eq("Pending human recheck").all():
        raise ValueError("Pilot candidate state must remain pending")
    if not records["usage_rights_review"].eq("Not reviewed").all():
        raise ValueError("Pilot candidate rights must remain unreviewed")
    for url in records["source_url"]:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "mall.industry.siemens.com":
            raise ValueError("Pilot leads must use Siemens official HTTPS pages")
    return records

def blank_feedback():
    return pd.DataFrame(columns=FEEDBACK_COLS)

def validate_feedback(df):
    if not set(FEEDBACK_COLS).issubset(df.columns):
        raise ValueError("Feedback missing required columns")
    if len(df)>50:
        raise ValueError("Only 50 anonymized interviews per sheet")
    data = df[FEEDBACK_COLS].copy().fillna("")
    for row in data.itertuples(index=False):
        if not row.participant_code or len(row.participant_code)>24 or not all(x.isalnum() or x in "-_" for x in row.participant_code):
            raise ValueError("Use a short anonymous participant code (letters, digits, dash, underscore)")
        if row.business_type not in BUSINESS_TYPES:
            raise ValueError("Invalid business type")
        if row.useful_result not in YES_NO_UNSURE or row.would_use_again not in YES_NO_UNSURE:
            raise ValueError("Invalid yes/no/unsure response")
        if row.willingness_to_pay_usd_month not in PRICE_OPTIONS:
            raise ValueError("Invalid price choice")
        if row.permission_to_share_anonymized not in ("yes","no"):
            raise ValueError("Explicit sharing permission required")
        for field in (row.parts_checked,row.tasks_completed,row.time_saved_estimate_minutes):
            if not field.isdigit() or int(field)>10000:
                raise ValueError("Expected nonnegative integer counts")
        if len(row.biggest_problem)>200:
            raise ValueError("Limit notes to 200 characters; no personal data")
    if data["participant_code"].duplicated().any():
        raise ValueError("Duplicate participant codes")
    return data

def feedback_summary(data):
    valid=validate_feedback(data)
    # Only count aggregate signals; never expose a participant roster publicly.
    n=len(valid)
    paying=int(valid["willingness_to_pay_usd_month"].isin(["29","49","99"]).sum())
    return {"interviews":n,"useful_yes":int(valid["useful_result"].eq("yes").sum()),
            "repeat_yes":int(valid["would_use_again"].eq("yes").sum()),
            "paid_intent":paying,"eligible_to_share":int(valid["permission_to_share_anonymized"].eq("yes").sum())}
