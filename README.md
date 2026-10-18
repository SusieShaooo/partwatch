# PartWatch V0.1

A lightweight Streamlit prototype for industrial spare-part lifecycle checks.

**Demo only:** All lifecycle statuses in this repository are synthetic. Unknown does not mean active. No live manufacturer records are included.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy

1. Open https://share.streamlit.io and sign in with GitHub.
2. Choose **New app**, repository `SusieShaooo/partwatch`, branch `main`, main file `app.py`.
3. Deploy using the Community Cloud free tier (subject to limits).

## CSV format

```csv
brand,part_number
DEMOCO,DEMO-PLC-100
DEMOCO,DEMO-DRIVE-200
OTHER,ABC123
```

Do not upload confidential inventory information to a public demo. The app processes uploads on its hosting server. Before production use, verify data licenses, add access controls and privacy protections, and validate statuses against manufacturer sources.

## Tests

```bash
python -m unittest discover -v
```
