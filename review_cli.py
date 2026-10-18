"""Local-only review approval; does not expose writes on Streamlit public site."""
import argparse
from pathlib import Path
import pandas as pd
from lifecycle import load_records
from review import AUDIT_COLUMNS, approve_review

def main():
    parser = argparse.ArgumentParser(description="Approve ONE manually checked lifecycle proposal locally")
    parser.add_argument("--proposal", required=True, help="One-row CSV containing review fields")
    parser.add_argument("--reviewer-id", required=True, help="Public pseudonym, never personal contact details")
    parser.add_argument("--confirm-source-reviewed", action="store_true")
    parser.add_argument("--confirm-rights-checked", action="store_true")
    parser.add_argument("--catalog", default="lifecycle_records.csv")
    parser.add_argument("--audit", default="review_audit.csv")
    args = parser.parse_args()
    if not (args.confirm_source_reviewed and args.confirm_rights_checked):
        parser.error("Both explicit human confirmation flags are required")
    catalog = Path(args.catalog)
    audit_path = Path(args.audit)
    if catalog.resolve() == audit_path.resolve():
        parser.error("Catalog and audit must be different files")
    records = load_records(catalog)
    log = pd.read_csv(audit_path, dtype=str, keep_default_na=False)
    proposal = pd.read_csv(args.proposal, dtype=str, keep_default_na=False)
    updated, updated_log = approve_review(
        records, log, proposal, args.reviewer_id,
        source_reviewed=True, rights_checked=True)
    # Validate data before modifying files; require the operator to review both diffs before commit.
    updated.to_csv(catalog, index=False)
    updated_log[AUDIT_COLUMNS].to_csv(audit_path, index=False)
    print("Review applied locally. Inspect both CSV diffs before Git commit; no automatic publishing.")

if __name__ == "__main__":
    main()
