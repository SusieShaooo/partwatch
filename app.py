"""PartWatch V0.5: human-verified catalog and read-only pilot preparation."""
import pandas as pd
import streamlit as st
from lifecycle import load_records, match_parts, compare_snapshots, SNAPSHOT_COLUMNS
from review import review_queue, AUDIT_COLUMNS, validate_publication
from quality import triage, summarize_matches, build_report
from pilot import load_candidates, blank_feedback

st.set_page_config(page_title="PartWatch | Lifecycle Checker", page_icon="🔎", layout="wide")
st.title("PartWatch")
st.caption("Industrial parts lifecycle intelligence · V0.5")
st.info("Current catalog contains DEMO data only. No manufacturer records or live lifecycle status are included. Unknown means not verified, NOT active.")
st.warning("Public prototype: do not upload confidential customer or inventory data. Files are processed on the hosting server.")
st.markdown("Lifecycle terminology reference: [Siemens official documentation](https://support.industry.siemens.com/cs/attachments/109983787/109983787_ProductLifeCycle_SINEC_NMS_DOC_V10_en.pdf). This is a general reference, not evidence for demo records.")

records = load_records()
import pathlib
_audit = pd.read_csv(pathlib.Path(__file__).with_name("review_audit.csv"), dtype=str, keep_default_na=False)
validate_publication(records, _audit)
quality = triage(records)
sample = "brand,part_number\nDEMOCO,DEMO-PLC-100\nDEMOCO,DEMO-DRIVE-200\nOTHER,ABC123\n"
with st.expander("See sample CSV format", expanded=False):
    st.code(sample, language="csv")
    st.download_button("Download sample CSV", sample, "sample_parts.csv", "text/csv")

with st.expander("Quick lookup: one part number (no CSV required)", expanded=False):
    quick_brand = st.text_input("Manufacturer / brand", key="quick_brand")
    quick_part = st.text_input("Part number", key="quick_part")
    if isinstance(quick_brand, str) and isinstance(quick_part, str) and quick_brand.strip() and quick_part.strip():
        if len(quick_brand) > 100 or len(quick_part) > 150:
            st.error("Brand or part number is too long")
        else:
            quick = match_parts(pd.DataFrame([{"brand": quick_brand, "part_number": quick_part}]), records)
            st.dataframe(quick, use_container_width=True, hide_index=True,
                         column_config={"source_url": st.column_config.LinkColumn("Evidence URL")})
            st.caption("Static catalog only. Demo is synthetic; Unknown is not Active. Check source and last verification date.")

upload = st.file_uploader("Upload a CSV with brand and part_number columns", type=["csv"])
if upload is not None:
    try:
        incoming = pd.read_csv(upload, dtype=str, keep_default_na=False)
        result = match_parts(incoming, records)
        st.metric("Parts checked", len(result))
        st.metric("Verified matches", int((result["verification_status"] == "verified").sum()))
        st.metric("Unknown", int((result["plm_code"] == "UNKNOWN").sum()))
        counts = summarize_matches(result)
        st.caption(f"Distinct parts: {counts['distinct_parts']} · Duplicate rows: {counts['duplicate_rows']} · Demo matches: {counts['demo_rows']}")
        choices = sorted(result["status"].unique().tolist())
        selected = st.multiselect("Filter by lifecycle status", choices, default=choices)
        filtered = result[result["status"].isin(selected)]
        st.dataframe(filtered, use_container_width=True, hide_index=True, column_config={"source_url": st.column_config.LinkColumn("Official source / evidence")})
        st.download_button("Download results CSV", filtered.to_csv(index=False).encode("utf-8-sig"), "partwatch_results.csv", "text/csv")
        full_report = build_report(filtered.reset_index(drop=True))
        st.download_button("Download provenance and freshness report", full_report.to_csv(index=False).encode("utf-8-sig"), "partwatch_evidence_report.csv", "text/csv")
        unknown = result.loc[result["plm_code"] == "UNKNOWN", ["brand", "part_number"]]
        worksheet = review_queue(records, unknown)
        st.download_button("Download manual review worksheet CSV", worksheet.to_csv(index=False).encode("utf-8-sig"), "partwatch_review_worksheet.csv", "text/csv")
        st.caption("Review worksheet contains unmatched input and pending non-demo catalog records. It does NOT approve or publish data. Keep submitted parts non-confidential.")
    except (ValueError, pd.errors.ParserError, UnicodeDecodeError, pd.errors.EmptyDataError) as exc:
        st.error(f"Could not process CSV: {exc}")

with st.expander("Evidence quality and review freshness (static catalog)", expanded=False):
    st.caption("Review age is a reminder based on the last manual check, not evidence that a manufacturer's status changed.")
    days = st.slider("Manual review interval (days)", min_value=30, max_value=365, value=180, step=30)
    from quality import triage as reassess
    reviewed = reassess(records, review_interval_days=days, warning_days=min(30, days - 1))
    st.metric("Verified catalog records", int((records["verification_status"] == "verified").sum()))
    st.metric("Overdue for manual review", int((reviewed["review_priority"] == "Review overdue").sum()))
    st.dataframe(reviewed, use_container_width=True, hide_index=True,
                 column_config={"source_url": st.column_config.LinkColumn("Evidence link")})
    st.download_button("Download review priority queue", reviewed.to_csv(index=False).encode("utf-8-sig"), "partwatch_review_priorities.csv", "text/csv")

with st.expander("Compare two lifecycle snapshots (manual, not live monitoring)", expanded=False):
    st.caption("This is a file-to-file comparison. Removed records do not prove discontinuation. Demo and unverified differences are not confirmed manufacturer changes.")
    current_snapshot = records[SNAPSHOT_COLUMNS]
    st.download_button("Download current catalog snapshot", current_snapshot.to_csv(index=False).encode("utf-8-sig"), "partwatch_catalog_snapshot.csv", "text/csv")
    previous_upload = st.file_uploader("Upload a previous catalog snapshot CSV", type=["csv"], key="previous_snapshot")
    if previous_upload is not None:
        try:
            previous = pd.read_csv(previous_upload, dtype=str, keep_default_na=False)
            changes = compare_snapshots(previous, current_snapshot)
            st.metric("Differences to review", int((changes["change"] != "Unchanged").sum()))
            st.dataframe(changes, use_container_width=True, hide_index=True)
            st.download_button("Download snapshot comparison CSV", changes.to_csv(index=False).encode("utf-8-sig"), "partwatch_snapshot_comparison.csv", "text/csv")
        except (ValueError, pd.errors.ParserError, UnicodeDecodeError, pd.errors.EmptyDataError) as exc:
            st.error(f"Could not compare snapshots: {exc}")

with st.expander("Review workflow and evidence checklist (read-only)", expanded=False):
    pending = review_queue(records)
    st.metric("Non-demo records to review", len(pending))
    st.download_button("Download pending review worksheet", pending.to_csv(index=False).encode("utf-8-sig"), "partwatch_pending_review.csv", "text/csv")
    st.markdown("""
    **Human review process (repo maintainers only):**
    1. Check the exact manufacturer part number and applicable region against an official page.
    2. Confirm lifecycle code, effective date (if available), and the date actually reviewed.
    3. Write an evidence note and determine whether linking and summarizing the facts is permitted.
    4. Use the local `review_cli.py` with both confirmations, then inspect and commit the catalog **and** audit log changes through an approved repository review.
    This public site cannot change verified records, and a link alone is not proof.
    """)

with st.expander("V0.5: Real-part evidence leads (NOT verified)", expanded=False):
    st.warning("These Siemens references are research leads from historical indexed pages, not live checks, authorized catalog records, or usable customer lifecycle answers. Human re-verification and rights review are required.")
    candidates = load_candidates()
    st.metric("Evidence leads awaiting review", len(candidates))
    st.dataframe(candidates, use_container_width=True, hide_index=True,
                 column_config={"source_url": st.column_config.LinkColumn("Manufacturer page to review")})
    st.download_button("Download evidence leads for manual verification",
                       candidates.to_csv(index=False).encode("utf-8-sig"), "partwatch_pilot_leads.csv", "text/csv")
    st.caption("Candidate observations are not added to the customer-search database. They may be outdated or region-specific.")

with st.expander("V0.5: Customer discovery pilot (privacy-first)", expanded=False):
    st.markdown("""
    Use a five-interview trial with industrial spare-part distributors. Ask if the tool
    helps, whether they would use it again, and which **hypothetical** monthly price
    they might consider. Price interest is not a purchase commitment.
    Do not enter emails, real names, confidential SKU lists, or customer information
    on this public demo. Collect optional, anonymous feedback offline with consent.
    The website does not accept or store survey submissions.
    """)
    template=blank_feedback()
    st.download_button("Download anonymous customer interview template",
                       template.to_csv(index=False).encode("utf-8-sig"),
                       "partwatch_customer_interviews_template.csv", "text/csv")
    st.caption("Offline analysis: python pilot_cli.py --feedback anonymized_interviews.csv")

st.divider()
st.caption("Demo statuses are synthetic. A source URL alone is not verification; production records require permission to use data and documented review. No automatic crawling or monitoring is performed.")
