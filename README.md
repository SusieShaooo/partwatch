# PartWatch V0.4

Public prototype for industrial spare-part lifecycle lookups. Hosted demo: https://spareparts-lifecycle-demo.streamlit.app/

**Important: All bundled product statuses are synthetic.** No live manufacturer lifecycle records, scheduled checks, alerts, or scraping are included. Unknown is not Active. This prototype is not ready for confidential customer inventory.

## Features
- One-part quick lookup without CSV, with strict input length limits
- CSV upload (`brand,part_number`), up to 1,000 rows
- Case/whitespace-insensitive matching; duplicates preserved
- Lifecycle status filtering and export with source/effective/verification dates
- Evidence URL column rendered as links when a legitimate, reviewed record is added
- Explicit distinction between demo, verified, and unverified statuses
- Download catalog snapshot; upload a previous catalog snapshot to inspect changes and export the comparison
- Download read-only manual review worksheets for unmatched parts
- Offline operator-gated review and audit log; no public write endpoint
- Human-review freshness dashboard (30-365 day adjustable interval) and CSV priority export
- Upload coverage counters: matched demo, verified, unknown, distinct parts, duplicates
- Per-part provenance and freshness report with explicit static-data disclaimer

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

## V0.4 data-quality dashboard and CSV reports

The evidence-quality panel classifies catalog records as `Demo only`, `Needs evidence`,
`Fresh verified`, `Review approaching`, or `Review overdue`. The default review interval is
180 days, with a 30-day warning window; these are operational reminders, **not** product
lifecycle claims. The reviewer must recheck the official evidence to establish a new verification
date; merely opening the dashboard never renews that date.

The batch lookup includes counts for distinct parts, repeated rows, unverified/unknown,
and demo matches, plus a provenance/freshness CSV report with a prominent non-live notice.
Only filtered rows appear in the report export. No customer data is stored to disk by the
application code; temporary Streamlit server processing still occurs, so use **non-confidential**
test files only. The public UI continues to be read-only.

## Manual snapshot comparison

Download the current catalog snapshot from the Streamlit page, then upload an older snapshot with the same columns: `brand,part_number,plm_code,status,verified_at,verification_status`. The tool compares by normalized brand + part number and labels rows as added, removed, unchanged or different. **Removed from snapshot does not mean discontinued.** Demo/unverified changes are never labeled manufacturer-confirmed. Even a difference between two verified records is a candidate for human evidence review, not an automated official alert. No file storage, scheduling, or background crawling is performed.

## V0.3 human verification workflow

**Public interface is read-only.** Users can download a review worksheet containing unknown uploaded models; no upload, login, or action on the public app can label a record verified. Do not submit sensitive inventory or reviewer personal information to the public repository.

Only repository maintainers who have actually reviewed a manufacturer's official product page may use the **local CLI**. Do not automate access to manufacturer sites, copy copyrighted page text, or imply a page's public availability grants redistribution rights.

1. Download a worksheet in the public UI or create a one-row CSV with columns:
   `brand,part_number,plm_code,status,effective_date,source_url,verified_at,evidence_note,rights_basis`
2. Confirm the exact manufacturer and part identifier, geographic/product variant, PLM status, any effective date, the source's context, and usage rights. Write a *paraphrased* evidence note of at least 20 characters. Use actual review date in YYYY-MM-DD.
3. Choose `rights_basis` of `official_link_and_factual_summary` only when linking and stating independently confirmed facts is appropriate; use `explicit_permission` only with confirmed permission. These are human declarations, **not** automated legal determinations.
4. Run **locally** from the repo root:

```bash
python review_cli.py --proposal reviewed_one_row.csv --reviewer-id reviewer-01 \
  --confirm-source-reviewed --confirm-rights-checked
python -m unittest discover -v
```

5. Inspect changes to **both** `lifecycle_records.csv` and `review_audit.csv`. Commit both through normal GitHub review. Only after merging can a verified record appear on the public site. Use a non-identifying reviewer pseudonym: the audit CSV is public.
6. GitHub CI verifies that every published `verified` record has a corresponding audit event. Review and evidence quality are still human responsibilities; URLs and checkboxes alone cannot establish authenticity.

New records are **not** added by downloading a worksheet; that worksheet is only a draft for the operator's one-row proposal. Demo records cannot be approved. No production data is bundled in this repo. The review CLI operates on local CSVs only, not on Streamlit server state. It does not query websites or send emails.

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
