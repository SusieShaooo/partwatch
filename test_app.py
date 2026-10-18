"""PartWatch V0.2 unit tests and Streamlit smoke tests."""
import ast
import csv
import io
import runpy
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
from lifecycle import load_records, match_parts, compare_snapshots, SNAPSHOT_COLUMNS
from review import REVIEW_FIELDS, AUDIT_COLUMNS, review_queue, approve_review, validate_publication
from quality import triage, summarize_matches, build_report

ROOT = Path(__file__).resolve().parent

def run_app(csv_text=None, *, quick_brand=None, quick_part=None):
    st = MagicMock()
    st.expander.return_value = nullcontext()
    st.slider.return_value = 180
    if quick_brand is not None and quick_part is not None:
        st.text_input.side_effect = [quick_brand, quick_part]
    st.file_uploader.side_effect = [io.StringIO(csv_text) if csv_text is not None else None, None]
    st.multiselect.side_effect = lambda label, choices, default: default
    with patch.dict("sys.modules", {"streamlit": st}):
        runpy.run_path(str(ROOT / "app.py"))
    return st

class PartWatchTests(unittest.TestCase):
    def setUp(self):
        self.records = load_records()

    def test_syntax(self):
        for filename in ("app.py", "lifecycle.py", "review.py", "review_cli.py", "quality.py"):
            ast.parse((ROOT / filename).read_text(encoding="utf-8"))

    def test_sample_csv(self):
        with (ROOT / "sample_parts.csv").open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertTrue(rows)
        self.assertEqual(set(rows[0]), {"brand", "part_number"})

    def test_demo_records_are_not_verified(self):
        self.assertTrue((self.records["verification_status"] == "demo").all())
        self.assertTrue((self.records["plm_code"] == "DEMO").all())
        self.assertTrue((self.records["source_url"] == "").all())

    def test_normalized_match_and_unknown(self):
        result = match_parts(pd.DataFrame([
            {"brand": " democo ", "part_number": " demo-plc-100 "},
            {"brand": "OTHER", "part_number": "NOT-FOUND"},
        ]), self.records)
        self.assertEqual(result["status"].tolist(), ["Discontinued (demo)", "Unknown / Not verified"])
        self.assertEqual(result["plm_code"].tolist(), ["DEMO", "UNKNOWN"])
        self.assertEqual(result["verified_at"].tolist(), ["", ""])

    def test_duplicate_input_rows_preserved(self):
        incoming = pd.DataFrame([{"brand": "DEMOCO", "part_number": "DEMO-PLC-100"}] * 2)
        self.assertEqual(len(match_parts(incoming, self.records)), 2)

    def test_bad_input_columns(self):
        with self.assertRaisesRegex(ValueError, "brand and part_number"):
            match_parts(pd.DataFrame({"sku": ["A"]}), self.records)

    def test_upload_limit(self):
        incoming = pd.DataFrame([{"brand": "X", "part_number": "A"}] * 1001)
        with self.assertRaisesRegex(ValueError, "1,000"):
            match_parts(incoming, self.records)

    def test_duplicate_record_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            pd.concat([self.records, self.records.iloc[[0]]]).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_records(path)

    def test_unverified_status_cannot_claim_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            modified = self.records.copy()
            modified.loc[0, "verification_status"] = "verified"
            modified.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "Verified records"):
                load_records(path)

    def test_http_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            modified = self.records.copy()
            modified.loc[0, "source_url"] = "http://example.com"
            modified.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                load_records(path)

    def test_snapshot_same_records_unchanged(self):
        before = self.records[SNAPSHOT_COLUMNS].copy()
        comparison = compare_snapshots(before, before)
        self.assertTrue((comparison["change"] == "Unchanged").all())

    def test_snapshot_demo_change_never_called_verified(self):
        before = self.records[SNAPSHOT_COLUMNS].copy()
        after = before.copy()
        after.loc[0, "status"] = "Changed demo lifecycle"
        result = compare_snapshots(before, after)
        self.assertEqual(result.loc[result["part_number"] == "DEMO-PLC-100", "change"].iloc[0], "Status differs (demo / unverified)")

    def test_snapshot_missing_row_not_discontinued(self):
        before = self.records[SNAPSHOT_COLUMNS].copy()
        after = before.iloc[1:].copy()
        result = compare_snapshots(before, after)
        label = result.loc[result["part_number"] == "DEMO-PLC-100", "change"].iloc[0]
        self.assertIn("not evidence of discontinuation", label)

    def test_snapshot_duplicate_and_bad_schema_rejected(self):
        before = self.records[SNAPSHOT_COLUMNS].copy()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            compare_snapshots(pd.concat([before, before.iloc[[0]]]), before)
        with self.assertRaisesRegex(ValueError, "missing columns"):
            compare_snapshots(pd.DataFrame({"sku": ["x"]}), before)

    def test_snapshot_verified_change_requires_two_verified_records(self):
        before = self.records[SNAPSHOT_COLUMNS].copy()
        after = before.copy()
        before.loc[0, ["plm_code", "verification_status"]] = ["PM300", "verified"]
        after.loc[0, ["plm_code", "verification_status"]] = ["PM400", "verified"]
        result = compare_snapshots(before, after)
        self.assertEqual(result.loc[result["part_number"] == "DEMO-PLC-100", "change"].iloc[0], "Verified-record status differs (review evidence)")

    def test_snapshot_ui_download_and_empty_compare_upload(self):
        st = run_app()
        labels = [call.args[0] for call in st.download_button.call_args_list]
        self.assertIn("Download current catalog snapshot", labels)
        self.assertEqual(st.file_uploader.call_count, 2)

    def valid_proposal(self):
        return pd.DataFrame([{"brand": "SIEMENS", "part_number": "6TEST-001",
            "plm_code": "PM400", "status": "Phase-out reported",
            "effective_date": "", "source_url": "https://example.com/product/6TEST-001",
            "verified_at": "2026-01-01",
            "evidence_note": "Manually compare official details and exact part number.",
            "rights_basis": "official_link_and_factual_summary"}])

    def test_review_queue_deduplicates_and_excludes_demo(self):
        incoming = pd.DataFrame([{"brand": " siemens ", "part_number": " abc "},
                                 {"brand": "SIEMENS", "part_number": "ABC"}])
        queue = review_queue(self.records, incoming)
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue.iloc[0]["part_number"], "ABC")
        self.assertEqual(list(queue.columns), REVIEW_FIELDS)

    def test_approval_requires_confirmation(self):
        with self.assertRaisesRegex(ValueError, "confirmations"):
            approve_review(self.records, pd.DataFrame(columns=AUDIT_COLUMNS),
                self.valid_proposal(), "reviewer-01", source_reviewed=True)

    def test_approved_record_has_matching_audit(self):
        catalog, log = approve_review(self.records, pd.DataFrame(columns=AUDIT_COLUMNS),
            self.valid_proposal(), "reviewer-01", source_reviewed=True, rights_checked=True)
        self.assertEqual(len(catalog), len(self.records) + 1)
        self.assertEqual(log.iloc[0]["reviewer_id"], "reviewer-01")
        self.assertTrue(validate_publication(catalog, log))
        with self.assertRaisesRegex(ValueError, "matching review audit"):
            validate_publication(catalog, pd.DataFrame(columns=AUDIT_COLUMNS))

    def test_demo_promotion_blocked(self):
        proposal = self.valid_proposal()
        proposal.loc[0, ["brand", "part_number"]] = ["DEMOCO", "DEMO-PLC-100"]
        with self.assertRaisesRegex(ValueError, "Demo"):
            approve_review(self.records, pd.DataFrame(columns=AUDIT_COLUMNS),
                proposal, "reviewer-01", source_reviewed=True, rights_checked=True)

    def test_evidence_and_rights_must_be_present(self):
        for field, value, error in [("evidence_note", "short", "evidence note"),
                                     ("rights_basis", "unknown", "rights basis"),
                                     ("source_url", "http://example.com", "HTTPS")]:
            proposal = self.valid_proposal()
            proposal.loc[0, field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, error):
                approve_review(self.records, pd.DataFrame(columns=AUDIT_COLUMNS),
                    proposal, "reviewer-01", source_reviewed=True, rights_checked=True)

    def test_public_catalog_matches_audit(self):
        audit = pd.read_csv(ROOT / "review_audit.csv", dtype=str, keep_default_na=False)
        self.assertTrue(validate_publication(self.records, audit))

    def test_readonly_review_worksheets(self):
        st = run_app("brand,part_number\nOTHER,ABC123\n")
        labels = [call.args[0] for call in st.download_button.call_args_list]
        self.assertIn("Download manual review worksheet CSV", labels)
        self.assertIn("Download pending review worksheet", labels)

    def test_freshness_demo_never_marked_verified(self):
        priorities = triage(self.records, as_of="2026-10-18")
        self.assertEqual(priorities["review_priority"].tolist(), ["Demo only"] * 3)

    def test_review_due_buckets(self):
        rows = self.records.iloc[[0]].copy()
        rows.loc[rows.index[0], ["verification_status", "plm_code", "verified_at", "source_url"]] = [
            "verified", "PM400", "2026-01-01", "https://example.com/evidence"]
        self.assertEqual(triage(rows, as_of="2026-10-18").iloc[0]["review_priority"], "Review overdue")
        self.assertEqual(triage(rows, as_of="2026-02-01").iloc[0]["review_priority"], "Fresh verified")
        self.assertEqual(triage(rows, as_of="2026-06-01", review_interval_days=180).iloc[0]["review_priority"], "Review approaching")

    def test_freshness_future_date_not_trusted(self):
        rows = self.records.iloc[[0]].copy()
        rows.loc[rows.index[0], ["verification_status", "plm_code", "verified_at", "source_url"]] = [
            "verified", "PM300", "2026-12-01", "https://example.com"]
        self.assertEqual(triage(rows, as_of="2026-10-18").iloc[0]["review_priority"], "Needs evidence")

    def test_batch_coverage_duplicate_counts(self):
        incoming = pd.DataFrame([{"brand":"DEMOCO","part_number":"DEMO-PLC-100"},
                                 {"brand":" democo ","part_number":"demo-plc-100"},
                                 {"brand":"OTHER","part_number":"UNKNOWN"}])
        counts = summarize_matches(match_parts(incoming, self.records))
        self.assertEqual((counts["rows"], counts["distinct_parts"], counts["duplicate_rows"],
                          counts["unknown_rows"], counts["demo_rows"]), (3, 2, 1, 1, 2))

    def test_report_provenance_and_ui_download(self):
        result = match_parts(pd.DataFrame([{"brand": "OTHER", "part_number": "ABC"}]), self.records)
        report = build_report(result, as_of="2026-10-18")
        self.assertEqual(report.iloc[0]["review_priority"], "Needs evidence")
        self.assertIn("not a live", report.iloc[0]["data_notice"])
        st = run_app("brand,part_number\nOTHER,ABC123\n")
        labels = [x.args[0] for x in st.download_button.call_args_list]
        self.assertIn("Download provenance and freshness report", labels)
        self.assertIn("Download review priority queue", labels)

    def test_quick_lookup_known_demo_and_unknown(self):
        st = run_app(quick_brand=" democo ", quick_part="demo-plc-100")
        matched = [call.args[0] for call in st.dataframe.call_args_list
                   if "status" in call.args[0].columns]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].iloc[0]["status"], "Discontinued (demo)")
        other = run_app(quick_brand="OTHER", quick_part="NOT-FOUND")
        matched_unknown = [call.args[0] for call in other.dataframe.call_args_list
                           if "status" in call.args[0].columns]
        self.assertEqual(matched_unknown[0].iloc[0]["status"], "Unknown / Not verified")

    def test_quick_lookup_limits_size(self):
        st = run_app(quick_brand="X" * 101, quick_part="ABC")
        self.assertTrue(any("too long" in call.args[0] for call in st.error.call_args_list))

    def test_app_no_upload(self):
        st = run_app()
        st.title.assert_called_once_with("PartWatch")
        st.error.assert_not_called()

    def test_app_upload_filter_and_export(self):
        st = run_app("brand,part_number\nDEMOCO,DEMO-DRIVE-200\nOTHER,ABC123\n")
        st.multiselect.assert_called_once()
        self.assertGreaterEqual(st.dataframe.call_count, 1)
        exports = [c for c in st.download_button.call_args_list if c.args and c.args[0] == "Download results CSV"]
        self.assertEqual(len(exports), 1)
        csv_data = exports[0].args[1].decode("utf-8-sig")
        self.assertIn("verification_status", csv_data)
        self.assertIn("Unknown / Not verified", csv_data)
        st.error.assert_not_called()

    def test_app_invalid_csv(self):
        st = run_app("sku\nABC\n")
        st.error.assert_called_once()
        self.assertIn("brand and part_number", st.error.call_args.args[0])

if __name__ == "__main__":
    unittest.main()
