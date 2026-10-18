# PartWatch V0.2

Public prototype for industrial spare-part lifecycle lookups. Hosted demo: https://spareparts-lifecycle-demo.streamlit.app/

**Important: All bundled product statuses are synthetic.** No live manufacturer lifecycle records, scheduled checks, alerts, or scraping are included. Unknown is not Active. This prototype is not ready for confidential customer inventory.

## Features
- CSV upload (`brand,part_number`), up to 1,000 rows
- Case/whitespace-insensitive matching; duplicates preserved
- Lifecycle status filtering and export with source/effective/verification dates
- Evidence URL column rendered as links when a legitimate, reviewed record is added
- Explicit distinction between demo, verified, and unverified statuses

## Data schema
`lifecycle_records.csv` fields:

| Field | Description |
|---|---|
| brand | Manufacturer |
| part_number | Exact SKU |
| plm_code | PM300 / PM400 / PM410 / PM490 / PM500 / UNKNOWN / DEMO |
| status | Human-readable status |
| effective_date | ISO date YYYY-MM-DD, if known |
| source_url | HTTPS official source or licensed evidence URL |
| verified_at | ISO date of actual human review, **not** date of data import |
| verification_status | demo / verified / unverified |

A record marked `verified` must have a source URL, review date, and non-demo, non-unknown PLM code. The app does **not** independently confirm that a link supports the claimed status: maintainers must verify it before committing any real record. Do not copy or redistribute manufacturer data unless usage rights permit it. The Siemens lifecycle document is linked only as general terminology reference, not as evidence for bundled demo records.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

## Tests

```bash
python -m unittest discover -v
```

GitHub Actions runs the same tests on pushes.

## Deploy
Streamlit Community Cloud: repository `SusieShaooo/partwatch`, branch `main`, entrypoint `app.py`. A push to main normally triggers a redeploy. Check the Streamlit dashboard and application logs if it fails.

## Safety and limits
- Do not upload sensitive inventories: this is a public unauthenticated demo.
- No background monitoring, email alerts, manufacturer integrations, or legal data license included.
- A URL alone does not mean a lifecycle status is verified.
- Unknown statuses must never be interpreted as Active.
- Production requires approved data rights, privacy/security review, source audit, freshness rules, and change history.
