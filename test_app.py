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

ROOT = Path(__file__).resolve().parent

def run_app(csv_text=None):
    st = MagicMock()
    st.expander.return_value = nullcontext()
    st.file_uploader.side_effect = [io.StringIO(csv_text) if csv_text is not None else None, None]
    st.multiselect.side_effect = lambda label, choices, default: default
    with patch.dict("sys.modules", {"streamlit": st}):
        runpy.run_path(str(ROOT / "app.py"))
    return st

class PartWatchTests(unittest.TestCase):
    def setUp(self):
        self.records = load_records()

    def test_syntax(self):
        for filename in ("app.py", "lifecycle.py"):
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

    def test_app_no_upload(self):
        st = run_app()
        st.title.assert_called_once_with("PartWatch")
        st.error.assert_not_called()

    def test_app_upload_filter_and_export(self):
        st = run_app("brand,part_number\nDEMOCO,DEMO-DRIVE-200\nOTHER,ABC123\n")
        st.multiselect.assert_called_once()
        st.dataframe.assert_called_once()
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
