"""Functional smoke tests for PartWatch with a mocked Streamlit UI."""
import ast
import csv
import io
import runpy
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

ROOT = Path(__file__).resolve().parent


def run_app(csv_text=None):
    st = MagicMock()
    st.expander.return_value = nullcontext()
    st.file_uploader.return_value = io.StringIO(csv_text) if csv_text is not None else None
    with patch.dict('sys.modules', {'streamlit': st}):
        scope = runpy.run_path(str(ROOT / 'app.py'))
    return st, scope


class PartWatchTests(unittest.TestCase):
    def test_python_syntax(self):
        ast.parse((ROOT / 'app.py').read_text(encoding='utf-8'))

    def test_sample_csv(self):
        with (ROOT / 'sample_parts.csv').open(encoding='utf-8', newline='') as fh:
            rows = list(csv.DictReader(fh))
        self.assertTrue(rows)
        self.assertEqual({'brand', 'part_number'}, set(rows[0]))

    def test_app_boots_with_no_upload(self):
        st, _ = run_app()
        st.title.assert_called_once_with('PartWatch')
        st.error.assert_not_called()

    def test_match_normalizes_input_and_unknown_is_not_active(self):
        _, scope = run_app()
        sample = pd.DataFrame([
            {'brand': ' democo ', 'part_number': ' demo-plc-100 '},
            {'brand': 'OTHER', 'part_number': 'missing'},
        ])
        result = scope['match_parts'](sample)
        self.assertEqual(result['status'].tolist(), ['Discontinued', 'Unknown / Not verified'])
        self.assertEqual(result['part_number'].tolist(), ['DEMO-PLC-100', 'MISSING'])

    def test_upload_and_export_csv(self):
        st, _ = run_app('brand,part_number\nDEMOCO,DEMO-DRIVE-200\nOTHER,ABC123\n')
        st.dataframe.assert_called_once()
        displayed = st.dataframe.call_args.args[0]
        self.assertEqual(displayed['status'].tolist(), ['Phase-out', 'Unknown / Not verified'])
        export_calls = [c for c in st.download_button.call_args_list if c.args and c.args[0] == 'Download results CSV']
        self.assertEqual(len(export_calls), 1)
        self.assertIn('Unknown / Not verified', export_calls[0].args[1].decode('utf-8-sig'))
        st.error.assert_not_called()

    def test_bad_csv_shows_error(self):
        st, _ = run_app('sku\nA123\n')
        st.error.assert_called_once()
        self.assertIn('brand and part_number', st.error.call_args.args[0])

    def test_upload_limit(self):
        rows = 'brand,part_number\n' + 'DEMOCO,DEMO-PLC-100\n' * 1001
        st, _ = run_app(rows)
        st.error.assert_called_once()
        self.assertIn('1,000 rows', st.error.call_args.args[0])
        st.dataframe.assert_not_called()

    def test_demo_disclaimer(self):
        st, _ = run_app()
        self.assertIn('Demo data only', st.info.call_args.args[0])
        self.assertIn('Unknown means not verified', st.info.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
