# TSDR Evidence Template

Purpose: provide the official USPTO evidence capture format for close-variant `MULU` records.
Governance scope: trademark serial verification, source provenance, conflict rating, legal-review handoff, and launch-blocking evidence.
Dependencies: `docs/TRADEMARK_SEARCH_RUNBOOK.md`, `docs/NAME_CLEARANCE_PRELIMINARY.md`, `docs/mullu-name-clearance-draft.json`.
Invariants: third-party mirrors do not close the USPTO search gate; only official TSDR evidence and qualified legal review can close close-variant risk.

## Capture Rules

For each serial, capture the official USPTO TSDR status page or API-style status
page and attach the exported page, screenshot, or signed PDF to the clearance
packet.

USPTO-documented status URL pattern:

```text
https://tsdrapi.uspto.gov/ts/cd/casestatus/sn<SERIAL_NUMBER>/content.html
```

Do not change `public_paid_launch_allowed` to `true` from this template alone.
This file defines the record shape; it is not a legal conclusion.

## Required Serial Checks

| Serial | Mark | Why it is tracked | TSDR URL |
| --- | --- | --- | --- |
| `99518598` | `MULU` | Close-variant software/service-adjacent public record | `https://tsdrapi.uspto.gov/ts/cd/casestatus/sn99518598/content.html` |
| `99264214` | `MULU` | Close-variant business/technical-service public record | `https://tsdrapi.uspto.gov/ts/cd/casestatus/sn99264214/content.html` |
| `85772539` | `MULU` | Older close-variant record that may affect history/confusion review | `https://tsdrapi.uspto.gov/ts/cd/casestatus/sn85772539/content.html` |
| `85494313` | `MULU` | Older close-variant record that may affect history/confusion review | `https://tsdrapi.uspto.gov/ts/cd/casestatus/sn85494313/content.html` |
| `85222451` | `MULU` | Older close-variant record that may affect history/confusion review | `https://tsdrapi.uspto.gov/ts/cd/casestatus/sn85222451/content.html` |

## Evidence Table

Copy this table into the final clearance packet and fill one row per official
TSDR capture.

| Field | Required value |
| --- | --- |
| Serial number | USPTO serial number |
| Mark literal | Mark text exactly as shown in TSDR |
| Owner/applicant | Current owner/applicant exactly as shown in TSDR |
| Status | Current TSDR status |
| Status date | Current TSDR status date |
| Filing date | Filing date |
| Registration number | Registration number or `none` |
| Classes | Nice classes and U.S. classes shown in TSDR |
| Goods/services | Goods/services summary, with full export attached |
| First-use dates | First use anywhere and in commerce, if shown |
| Prosecution events | Material events affecting live/dead/pending state |
| Evidence capture URL | TSDR status URL used |
| Evidence artifact | Screenshot/export/PDF path or storage reference |
| Captured by | Reviewer name or system identity |
| Captured at | Date, time, and timezone |
| Conflict rating | none, low, medium, high, or blocking |
| Legal reviewer | Reviewer name, firm, or authority |
| Legal conclusion | proceed, proceed_with_risk_controls, hold, or rename |
| Launch effect | no_effect, keep_blocked, or clears_named_gate |

## Per-Serial Worksheet

### Serial `99518598`

```text
mark_literal:
owner_applicant:
status:
status_date:
filing_date:
registration_number:
classes:
goods_services_summary:
first_use_dates:
prosecution_events:
evidence_capture_url: https://tsdrapi.uspto.gov/ts/cd/casestatus/sn99518598/content.html
evidence_artifact:
captured_by:
captured_at:
conflict_rating:
legal_reviewer:
legal_conclusion:
launch_effect:
```

### Serial `99264214`

```text
mark_literal:
owner_applicant:
status:
status_date:
filing_date:
registration_number:
classes:
goods_services_summary:
first_use_dates:
prosecution_events:
evidence_capture_url: https://tsdrapi.uspto.gov/ts/cd/casestatus/sn99264214/content.html
evidence_artifact:
captured_by:
captured_at:
conflict_rating:
legal_reviewer:
legal_conclusion:
launch_effect:
```

### Serial `85772539`

```text
mark_literal:
owner_applicant:
status:
status_date:
filing_date:
registration_number:
classes:
goods_services_summary:
first_use_dates:
prosecution_events:
evidence_capture_url: https://tsdrapi.uspto.gov/ts/cd/casestatus/sn85772539/content.html
evidence_artifact:
captured_by:
captured_at:
conflict_rating:
legal_reviewer:
legal_conclusion:
launch_effect:
```

### Serial `85494313`

```text
mark_literal:
owner_applicant:
status:
status_date:
filing_date:
registration_number:
classes:
goods_services_summary:
first_use_dates:
prosecution_events:
evidence_capture_url: https://tsdrapi.uspto.gov/ts/cd/casestatus/sn85494313/content.html
evidence_artifact:
captured_by:
captured_at:
conflict_rating:
legal_reviewer:
legal_conclusion:
launch_effect:
```

### Serial `85222451`

```text
mark_literal:
owner_applicant:
status:
status_date:
filing_date:
registration_number:
classes:
goods_services_summary:
first_use_dates:
prosecution_events:
evidence_capture_url: https://tsdrapi.uspto.gov/ts/cd/casestatus/sn85222451/content.html
evidence_artifact:
captured_by:
captured_at:
conflict_rating:
legal_reviewer:
legal_conclusion:
launch_effect:
```

## Closure Rule

The `close_variant_review` gate may close only when:

1. All required serials have official TSDR evidence attached.
2. Each serial has a conflict rating.
3. A qualified legal reviewer records a conclusion.
4. The clearance packet records whether the result is `proceed`,
   `proceed_with_risk_controls`, `hold`, or `rename`.
5. The readiness witness is updated in the same change that closes the gate.
