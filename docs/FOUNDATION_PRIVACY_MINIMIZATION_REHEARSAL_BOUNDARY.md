<!--
Purpose: define the Foundation Mode privacy minimization rehearsal boundary for public-safe data-category drafting without collecting, storing, tracking, processing, publishing, or deploying.
Governance scope: privacy minimization rehearsal planning, local data-category questions, prohibited-field questions, consent exclusion, retention/deletion draft exclusion, analytics exclusion, processor exclusion, legal-clearance blocking, customer-access blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md, docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md, docs/FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md, examples/foundation_privacy_minimization_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_privacy_minimization_rehearsal_boundary.py.
Invariants: no minimization approval, no personal-data collection, no personal-data storage, no consent capture, no retention/deletion approval, no privacy notice publication, no analytics tracking, no processor activation, no legal clearance claim, no customer access, and no deployment claim.
-->

# Foundation Privacy Minimization Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** privacy minimization rehearsal means drafting which future
> data fields should be avoided, reduced, or delayed using fictional local
> categories. It does not collect or store personal data, capture consent,
> approve retention or deletion rules, publish a privacy notice, enable
> analytics, activate processors, claim legal clearance, open customer access,
> or deploy anything.

Witness packet: [`../examples/foundation_privacy_minimization_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_privacy_minimization_rehearsal_witness.awaiting_evidence.json)

Rule: Privacy minimization rehearsal is a local paper exercise, not permission
to handle personal data or claim privacy readiness.

No minimization approval, personal-data collection, personal-data storage,
consent capture, retention/deletion approval, privacy notice publication,
analytics tracking, processor activation, legal-clearance claim, customer
access, or deployment claim is permitted by this boundary.

## What This Boundary Solves

The privacy/data boundary keeps personal-data handling closed. A solo operator
still needs a safe way to think through what should not be collected later.

This is preparation only:

1. Draft fictional data-category questions locally.
2. Draft prohibited-field and minimization questions locally.
3. Draft consent, retention, deletion, processor, analytics, and subject-request
   stop rules locally.
4. Keep every privacy/data surface in `AwaitingEvidence`.
5. Do not claim privacy readiness, legal clearance, customer access, or
   deployment readiness from this rehearsal.

## Current State

```text
privacy_minimization_rehearsal_boundary_state=AwaitingEvidence
minimization_rehearsal_executed=false
minimization_policy_approved=false
personal_data_collection_allowed=false
personal_data_storage_allowed=false
consent_capture_allowed=false
retention_deletion_policy_approved=false
privacy_notice_publication_allowed=false
analytics_tracking_allowed=false
processor_activation_allowed=false
legal_clearance_claimed=false
customer_access_allowed=false
deployment_allowed=false
```

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Fictional data categories | Draft generic category questions. | Do not record names, emails, contacts, account IDs, or customer records. |
| Prohibited field list | Draft fields to avoid later. | Do not create real intake fields or collection forms. |
| Minimization rule questions | Draft keep/drop/delay questions. | Do not approve a minimization policy. |
| Consent stop rule | Draft when consent would be needed. | Do not capture consent or claim legal approval. |
| Retention/deletion stop rule | Draft lifecycle questions. | Do not approve retention schedules or deletion workflows. |
| Tracking stop rule | Draft tracking-risk questions. | Do not enable cookies, analytics tags, pixels, or telemetry tracking. |
| Processor stop rule | Draft processor review questions. | Do not activate vendors, accounts, contracts, processors, or CRM tools. |
| Subject request stop rule | Draft future request-handling questions. | Do not promise support workflows or response times. |
| Handoff note | Draft later evidence requirements. | Do not claim privacy readiness, customer access, or deployment. |

## Operator Procedure

1. Keep all examples fictional, local, and public-safe.
2. Do not record real people data, contact details, account values, customer
   records, private paths, vendor account IDs, tracking IDs, or secrets.
3. Do not create forms, consent flows, analytics tags, cookies, processors,
   CRM imports, privacy notices, retention systems, deletion systems, or subject
   request workflows.
4. Stop if work requires legal/privacy conclusions, personal-data handling,
   third-party processors, customer access, support commitments, payment, public
   publication, or deployment.
5. Use the result only as a draft for future privacy/data design.

## Validation

Run:

```powershell
python scripts/validate_foundation_privacy_minimization_rehearsal_boundary.py
```

The validator checks that the privacy minimization rehearsal witness:

1. keeps minimization approval, personal-data collection/storage, consent
   capture, retention/deletion approval, privacy notice publication, analytics
   tracking, processor activation, legal clearance, customer access, and
   deployment blocked;
2. keeps every rehearsal surface in `AwaitingEvidence`;
3. rejects URL, email, private path, personal-data, account, tracking,
   processor, consent, retention, deletion, subject-request, customer-access,
   and deployment-shaped values; and
4. rejects promotion phrases that imply privacy readiness, minimization
   approval, consent readiness, retention/deletion readiness, processor
   readiness, tracking readiness, customer access, or deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Prepare the broader privacy/data boundary | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare intake/onboarding safely | [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md) |
| Prepare customer access without opening access | [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: minimization approval blocked, personal-data collection blocked, personal-data storage blocked, consent capture blocked, retention/deletion approval blocked, privacy notice publication blocked, analytics tracking blocked, processor activation blocked, legal clearance not claimed, customer access blocked, deployment blocked
  Open issues: data-category evidence, prohibited-field evidence, minimization-rule evidence, consent-stop evidence, retention/deletion-stop evidence, tracking-stop evidence, processor-stop evidence, subject-request-stop evidence, and handoff evidence remain AwaitingEvidence
  Next action: run the privacy minimization rehearsal validator before relying on minimization planning as evidence
