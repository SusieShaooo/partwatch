# Siemens Industry Mall — preliminary data-use rights review

Review date: 2026-10-18
Project: PartWatch V0.5
Status: OPEN / NOT APPROVED
Scope: Five manually reported Siemens lifecycle-status observations held in `pilot_observations.csv`.

## Evidence assessed
- Siemens general Terms of Use: https://www.siemens.com/en-us/terms-of-use/
  - Section A.4.4 limits sharing information with third parties.
  - Section A.5.1 addresses prior written permission for copying or exploitation of site content.
  - Section A.6.2 prohibits text/data mining and automated scraping/extraction.
  - Terms page states last updated 2025-10-27.
- Siemens Industry Mall product links in `pilot_observations.csv`.
- User-reported manual observations dated 2026-10-18. These are not independent live checks.

## Preliminary assessment
- Human observation does not by itself confer a license to redistribute the source information.
- The applicability of general terms versus any region-specific Industry Mall terms or separately negotiated agreements has not been conclusively established.
- Whether bare part numbers and short lifecycle labels can be reused independently of site-content restrictions needs focused legal/contractual review; no affirmative right is assumed.
- A public GitHub CSV is publicly accessible even when excluded from the Streamlit verified catalog. The existing observations should be treated as a potential disclosure exposure and reviewed before any expanded publication or commercial offering.

## Decision and safeguards
- Publication authorization: NOT APPROVED.
- Do not import Siemens observations into `lifecycle_records.csv` or mark them `Verified`.
- Do not automate extraction or scraping; do not copy screenshots, descriptions or other site content.
- Keep demo-only public product lookup unchanged.
- Avoid adding more manufacturer-derived records to public files pending clarification.
- Obtain explicit written permission or a suitable licensing agreement from Siemens covering: specific fields (MLFB/part number, PLM code, effective date), permitted territories, public display, customer-facing redistribution, storage, refresh cadence, API/batch access, attribution, and revocation.
- Check Industry Mall regional terms and applicable agreements; ask counsel if necessary.

## Approval gates
1. Confirm authoritative applicable terms for each source region.
2. Document written license or an alternative clear legal basis for the precise intended distribution.
3. Confirm permitted scope and restrictions.
4. Revalidate freshness and region-specific lifecycle meanings.
5. Record reviewer, date, decision, and evidence of authorization.
6. Only after all gates pass, consider promoting approved rows through the existing controlled review process.

This is an operational risk review, not a legal opinion.
