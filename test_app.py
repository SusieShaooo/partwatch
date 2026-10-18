import ast
import csv
import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class ProjectTests(unittest.TestCase):
    def test_python_syntax(self):
        ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))

    def test_sample_csv(self):
        rows = list(csv.DictReader(io.StringIO((ROOT / "sample_parts.csv").read_text(encoding="utf-8"))))
        self.assertTrue(rows)
        self.assertEqual(set(rows[0]), {"brand", "part_number"})

    def test_demo_disclaimer(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn("Demo data only", source)
        self.assertIn("Unknown / Not verified", source)

if __name__ == "__main__":
    unittest.main()
