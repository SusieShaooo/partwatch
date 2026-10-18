"""PartWatch lifecycle record validation and CSV matching. No scraping."""
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd

COLUMNS = ["brand", "part_number", "plm_code", "status", "effective_date", "source_url", "verified_at", "verification_status"]
VALID_CODES = {"PM300", "PM400", "PM410", "PM490", "PM500", "UNKNOWN", "DEMO"}
VALID_VERIFICATION = {"demo", "verified", "unverified"}
OUTPUT_COLUMNS = ["brand", "part_number", "plm_code", "status", "effective_date", "source_url", "verified_at", "verification_status"]

def clean(value):
    return str(value).strip().upper() if pd.notna(value) else ""

def load_records(path=None):
    path = Path(path) if path is not None else Path(__file__).with_name("lifecycle_records.csv")
    records = pd.read_csv(path, dtype=str, keep_default_na=False)
    if not set(COLUMNS).issubset(records.columns):
        raise ValueError("Lifecycle records missing required columns")
    records = records[COLUMNS].copy()
    records["brand"] = records["brand"].map(clean)
    records["part_number"] = records["part_number"].map(clean)
    records["plm_code"] = records["plm_code"].map(clean)
    records["verification_status"] = records["verification_status"].str.strip().str.lower()
    if records.duplicated(["brand", "part_number"]).any():
        raise ValueError("Duplicate brand + part_number in lifecycle records")
    if not records["plm_code"].isin(VALID_CODES).all():
        raise ValueError("Invalid PLM code")
    if not records["verification_status"].isin(VALID_VERIFICATION).all():
        raise ValueError("Invalid verification status")
    for date_col in ("verified_at", "effective_date"):
        valid = records[date_col].eq("") | pd.to_datetime(records[date_col], errors="coerce", format="%Y-%m-%d").notna()
        if not valid.all():
            raise ValueError("Invalid ISO date in " + date_col)
    for r in records.itertuples(index=False):
        if r.source_url:
            url = urlparse(r.source_url)
            if url.scheme != "https" or not url.netloc or url.username or url.password:
                raise ValueError("Only HTTPS evidence URLs are accepted")
        if r.verification_status == "verified" and (not r.source_url or not r.verified_at or r.plm_code in ("DEMO", "UNKNOWN")):
            raise ValueError("Verified records require source, date, and real PLM code")
        if r.verification_status == "demo" and r.plm_code != "DEMO":
            raise ValueError("Demo records must use DEMO code")
    return records

def match_parts(incoming, records):
    if not {"brand", "part_number"}.issubset(incoming.columns):
        raise ValueError("CSV must contain brand and part_number columns.")
    if len(incoming) > 1000:
        raise ValueError("Maximum 1,000 rows per upload.")
    parts = incoming[["brand", "part_number"]].copy()
    parts["brand"] = parts["brand"].map(clean)
    parts["part_number"] = parts["part_number"].map(clean)
    result = parts.merge(records, on=["brand", "part_number"], how="left", validate="many_to_one")
    defaults = {"plm_code": "UNKNOWN", "status": "Unknown / Not verified", "effective_date": "", "source_url": "", "verified_at": "", "verification_status": "unverified"}
    for col, default in defaults.items():
        result[col] = result[col].fillna(default)
    return result[OUTPUT_COLUMNS]
