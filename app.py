"""PartWatch V0.2: provenance-aware lifecycle CSV checker."""
import pandas as pd
import streamlit as st
from lifecycle import load_records, match_parts, compare_snapshots, SNAPSHOT_COLUMNS

st.set_page_config(page_title="PartWatch | Lifecycle Checker", page_icon="🔎", layout="wide")
st.title("PartWatch")
st.caption("Industrial parts lifecycle intelligence · V0.2")
st.info("Demo data only. No manufacturer records or live lifecycle status are included. Unknown means not verified, NOT active.")
st.warning("Public prototype: do not upload confidential customer or inventory data. Files are processed on the hosting server.")
st.markdown("Lifecycle terminology reference: [Siemens official documentation](https://support.industry.siemens.com/cs/attachments/109983787/109983787_ProductLifeCycle_SINEC_NMS_DOC_V10_en.pdf). This is a general reference, not evidence for demo records.")

records = load_records()
sample = "brand,part_number\nDEMOCO,DEMO-PLC-100\nDEMOCO,DEMO-DRIVE-200\nOTHER,ABC123\n"
with st.expander("See sample CSV format", expanded=False):
    st.code(sample, language="csv")
    st.download_button("Download sample CSV", sample, "sample_parts.csv", "text/csv")

upload = st.file_uploader("Upload a CSV with brand and part_number columns", type=["csv"])
if upload is not None:
    try:
        incoming = pd.read_csv(upload, dtype=str, keep_default_na=False)
        result = match_parts(incoming, records)
        st.metric("Parts checked", len(result))
        st.metric("Verified matches", int((result["verification_status"] == "verified").sum()))
        st.metric("Unknown", int((result["plm_code"] == "UNKNOWN").sum()))
        choices = sorted(result["status"].unique().tolist())
        selected = st.multiselect("Filter by lifecycle status", choices, default=choices)
        filtered = result[result["status"].isin(selected)]
        st.dataframe(filtered, use_container_width=True, hide_index=True, column_config={"source_url": st.column_config.LinkColumn("Official source / evidence")})
        st.download_button("Download results CSV", filtered.to_csv(index=False).encode("utf-8-sig"), "partwatch_results.csv", "text/csv")
    except (ValueError, pd.errors.ParserError, UnicodeDecodeError, pd.errors.EmptyDataError) as exc:
        st.error(f"Could not process CSV: {exc}")

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

st.divider()
st.caption("Demo statuses are synthetic. A source URL alone is not verification; production records require permission to use data and documented review. No automatic crawling or monitoring is performed.")
