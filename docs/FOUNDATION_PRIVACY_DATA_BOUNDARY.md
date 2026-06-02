<!--
Purpose: define the Foundation Mode privacy and data-retention boundary before any personal-data collection, storage, consent capture, tracking, processor use, privacy-policy publication, customer access, or deployment claim.
Governance scope: privacy posture, data-retention posture, consent-preparation posture, no personal-data collection, no data storage, no tracking, no processor activation, no customer access, and no deployment claim.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_privacy_data_witness.awaiting_evidence.json, scripts/validate_foundation_privacy_data_boundary.py.
Invariants: no personal-data collection, no personal-data storage, no approved retention policy claim, no deletion policy claim, no consent capture, no analytics tracking, no third-party processor activation, no privacy-policy publication, no legal clearance, no customer access, no deployment claim.
-->

# Foundation Privacy Data Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** privacy and data-retention preparation means drafting the
> questions and controls that would be needed before handling people data. It
> does not collect data, store data, publish a privacy policy, capture consent,
> enable analytics, activate processors, open customer access, or deploy
> anything.

Witness packet: [`../examples/foundation_privacy_data_witness.awaiting_evidence.json`](../examples/foundation_privacy_data_witness.awaiting_evidence.json)

Rule: Privacy/data preparation is a local planning boundary, not permission to handle personal data.

No personal-data collection, personal-data storage, retention-policy approval,
deletion-policy approval, consent capture, analytics tracking, third-party
processor activation, privacy-policy publication, legal-clearance, customer
access, or deployment claim is permitted by this boundary.

## What This Boundary Solves

Intake and onboarding drafts can create privacy pressure even when no customer
access exists. Foundation Mode needs a separate privacy/data boundary so future
data handling is prepared without silently becoming active collection.

This boundary keeps the work small:

1. Draft data classification questions locally.
2. Draft consent, retention, deletion, processor, and tracking questions
   locally.
3. Keep real personal data, contact details, analytics, processors, and storage
   out of the repository.
4. Keep privacy and legal readiness in `AwaitingEvidence`.

## Current State

```text
privacy_data_boundary_state=AwaitingEvidence
personal_data_collection_allowed=false
personal_data_storage_allowed=false
retention_policy_approved=false
deletion_policy_approved=false
privacy_notice_published=false
consent_capture_allowed=false
analytics_tracking_allowed=false
third_party_processor_allowed=false
legal_clearance_claimed=false
customer_access_allowed=false
deployment_allowed=false
```

## Public-Safe Preparation Surfaces

| Surface | Public-safe record here | Do not store or claim here |
| --- | --- | --- |
| Data classification draft | Category questions only. | Real people data or customer records. |
| Consent questions | Draft review questions only. | Active consent capture or legal approval. |
| Retention/deletion questions | Draft lifecycle questions only. | Approved retention schedule or deletion workflow. |
| Privacy notice questions | Draft notice questions only. | Published privacy notice or legal clearance. |
| Processor inventory draft | Processor categories only. | Vendor account IDs, contracts, or live processors. |
| Analytics questions | Tracking-risk questions only. | Analytics tags, cookies, or tracking activation. |
| Subject request questions | Draft request-handling questions only. | Active request workflow or support promise. |
| Data minimization checklist | Local checklist only. | Customer-data processing readiness. |

## Operator Procedure

1. Keep privacy/data materials as local drafts.
2. Do not collect or store personal data in Foundation Mode.
3. Do not publish privacy notices, consent flows, tracking, processors, or data
   retention commitments without qualified review and later signed witness
   evidence.
4. Do not connect analytics, CRM, forms, or processors while intake remains
   closed.
5. Treat every privacy/data surface as `AwaitingEvidence` until a later signed
   witness promotes it.

## Validation

Run:

```powershell
python scripts/validate_foundation_privacy_data_boundary.py
```

The validator checks that the witness packet:

1. keeps every privacy/data surface in `AwaitingEvidence`;
2. blocks personal-data collection, storage, consent capture, tracking,
   processor activation, policy publication, customer access, and deployment;
3. rejects personal-data-shaped, account-shaped, URL, email, private-path, or
   secret values; and
4. rejects privacy/data readiness-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare intake/onboarding safely | [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: personal-data collection blocked, personal-data storage blocked, consent capture blocked, analytics tracking blocked, processor activation blocked, privacy publication blocked, legal clearance not claimed, customer access blocked, deployment blocked
  Open issues: privacy review, retention review, deletion review, consent review, processor review, analytics review, legal/business review, and deployment evidence remain AwaitingEvidence
  Next action: run the privacy/data boundary validator, then keep all personal-data handling closed until evidence promotes it
