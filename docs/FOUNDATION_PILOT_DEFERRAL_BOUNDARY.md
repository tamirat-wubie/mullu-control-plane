<!--
Purpose: define the Foundation Mode pilot-deferral boundary before any pilot execution, participant invitation, access channel, waitlist, beta opening, customer access, personal-data collection, market-validation claim, support-readiness claim, legal-clearance claim, paid-pilot claim, external publication, or deployment claim.
Governance scope: pilot deferral, local pilot prerequisite questions, participant-boundary blocking, access-channel blocking, intake blocking, support-duty blocking, privacy caution, legal/business restraint, public-claim restraint, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md, docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md, docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md, docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md, examples/foundation_pilot_deferral_witness.awaiting_evidence.json, scripts/validate_foundation_pilot_deferral_boundary.py.
Invariants: no pilot execution, no participant invitation, no access channel opening, no waitlist opening, no beta opening, no customer access, no personal-data collection, no market-validation claim, no support-readiness claim, no legal-clearance claim, no paid-pilot claim, no external-publication claim, and no deployment claim.
-->

# Foundation Pilot Deferral Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** pilot deferral means future pilot thinking can be written as
> local prerequisite questions only. It does not invite participants, open an
> access channel, open a waitlist, open beta, collect personal data, claim
> market validation, promise support, claim legal clearance, accept payment,
> publish externally, or deploy.

Witness packet: [`../examples/foundation_pilot_deferral_witness.awaiting_evidence.json`](../examples/foundation_pilot_deferral_witness.awaiting_evidence.json)

Rule: Pilot deferral is a local planning boundary, not a pilot-execution, participant-invitation, access-opening, market-validation, support-readiness, legal-clearance, paid-pilot, publication, or deployment certificate.

No pilot execution, participant invitation, access channel opening, waitlist
opening, beta opening, customer access, personal-data collection,
market-validation claim, support-readiness claim, legal-clearance claim,
paid-pilot claim, external publication, or deployment claim is permitted by
this boundary.

## What This Boundary Solves

A pilot sounds small, but it creates real obligations: participant trust,
support expectations, privacy duties, terms, rollback paths, feedback handling,
public claims, and sometimes money. Foundation Mode is not ready for that
surface. This boundary keeps pilot thinking as a private local evidence problem
until later witness evidence promotes one exact bounded pilot action.

This boundary keeps the work small:

1. Draft pilot purpose questions without choosing participants.
2. Draft participant-boundary questions without inviting anyone.
3. Draft access-channel questions without opening a channel.
4. Draft privacy, support, rollback, success-metric, legal, and public-claim
   questions without treating them as readiness evidence.
5. Keep every pilot surface in `AwaitingEvidence`.

## Current State

```text
pilot_deferral_boundary_state=AwaitingEvidence
pilot_execution_allowed=false
participant_invitation_allowed=false
access_channel_allowed=false
waitlist_allowed=false
beta_allowed=false
customer_access_allowed=false
personal_data_collection_allowed=false
market_validation_claimed=false
support_ready_claimed=false
legal_clearance_claimed=false
paid_pilot_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Deferral Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Pilot purpose questions | State why a future pilot might exist. | Do not execute or schedule a pilot. |
| Participant boundary questions | Define participant constraints abstractly. | Do not name, invite, contact, or enroll people. |
| Access channel questions | List access-channel prerequisites. | Do not open forms, waitlists, beta, accounts, or invite links. |
| Consent and privacy questions | Draft consent and data-minimization questions. | Do not collect personal data or publish privacy claims. |
| Support coverage questions | Draft support-duty questions. | Do not promise response times or claim support readiness. |
| Rollback and exit questions | Draft stop, rollback, and exit questions. | Do not claim incident coverage or recovery readiness. |
| Success metric questions | Draft possible local learning metrics. | Do not claim market validation or product-market proof. |
| Legal and terms questions | Draft qualified-review questions. | Do not claim legal clearance, terms readiness, or company authority. |
| Public claim questions | Draft claim blockers. | Do not publish externally or announce pilot readiness. |

## Operator Procedure

1. Treat any pilot as `DelayedByDesign` until product scope, support, intake,
   privacy, legal, security, deployment, rollback, and source-control evidence
   exists.
2. Do not invite participants, open waitlists, open beta, create intake forms,
   collect personal data, start outreach, promise support, accept payment, or
   publish pilot language through this boundary.
3. Do not record private names, emails, schedules, account IDs, customer
   identities, provider values, private paths, credentials, or secrets.
4. Keep every pilot surface in `AwaitingEvidence` until a later governed
   witness promotes one exact bounded action.
5. If a future pilot question appears, route it first through this deferral
   boundary, then through product-scope, support, intake, privacy, legal,
   deployment-deferral, and source-control boundaries.

## Validation

Run:

```powershell
python scripts/validate_foundation_pilot_deferral_boundary.py
```

The validator checks that the pilot-deferral witness:

1. keeps every pilot surface in `AwaitingEvidence`;
2. blocks pilot execution, participant invitation, access-channel opening,
   waitlists, beta, customer access, personal-data collection, market
   validation, support readiness, legal clearance, paid pilot, external
   publication, and deployment;
3. rejects URL, email, private path, person/customer/provider, schedule,
   account, billing, credential, secret, or intake-shaped values; and
4. rejects pilot-readiness, access-opening, market-validation, support-ready,
   legal-clearance, paid-pilot, publication, and deployment phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare product scope safely | [Foundation Product Scope Boundary](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md) |
| Prepare support safely | [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) |
| Prepare intake safely | [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md) |
| Prepare privacy/data safely | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |
| Keep deployment deferred safely | [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: pilot execution blocked, participant invitation blocked, access channel blocked, waitlist blocked, beta blocked, customer access blocked, personal-data collection blocked, market-validation claim blocked, support-readiness claim blocked, legal-clearance claim blocked, paid-pilot claim blocked, external-publication claim blocked, deployment blocked
  Open issues: pilot purpose evidence, participant-boundary evidence, access-channel evidence, consent/privacy evidence, support coverage evidence, rollback/exit evidence, success-metric evidence, legal/terms evidence, public-claim evidence, and pilot witness remain AwaitingEvidence
  Next action: run the pilot-deferral boundary validator before any future pilot-readiness or participant-access claim
