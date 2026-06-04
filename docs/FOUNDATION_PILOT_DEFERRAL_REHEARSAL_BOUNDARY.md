<!--
Purpose: define the Foundation Mode pilot-deferral rehearsal boundary for local public-safe decision practice without pilot execution, participant invitation, access opening, waitlist/signup opening, customer access, personal-data collection, validation claims, support claims, legal claims, payment, publication, secrets, or deployment.
Governance scope: pilot-deferral rehearsal, local stop-rule drafting, participant-boundary blocking, access-channel blocking, waitlist/signup blocking, data-collection blocking, support-duty blocking, legal/business restraint, payment blocking, public-claim restraint, secret exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md, docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md, docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md, docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md, examples/foundation_pilot_deferral_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_pilot_deferral_rehearsal_boundary.py.
Invariants: no pilot deferral rehearsal execution, no pilot execution, no participant invitation, no access-channel opening, no waitlist opening, no pilot signup opening, no customer access, no personal-data collection, no market-validation claim, no support-readiness claim, no legal-clearance claim, no paid-pilot claim, no payment enablement, no money movement, no external-publication claim, no secret material, and no deployment claim.
-->

# Foundation Pilot Deferral Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** pilot-deferral rehearsal means practicing the local decision
> for why a pilot must stay deferred. It is not a pilot, invitation, access
> channel, waitlist, signup, customer access, data collection, market proof,
> support promise, legal clearance, paid step, publication, secret handling, or
> deployment.

Witness packet: [`../examples/foundation_pilot_deferral_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_pilot_deferral_rehearsal_witness.awaiting_evidence.json)

Rule: Pilot-deferral rehearsal is a local paper exercise, not a pilot,
participant invitation, access opening, waitlist/signup opening, customer
access, data collection, market validation, support readiness, legal
clearance, paid pilot, payment, publication, secret, or deployment
certificate.

No pilot deferral rehearsal execution, pilot execution, participant invitation,
access-channel opening, waitlist opening, pilot signup opening, customer
access, personal-data collection, market-validation claim, support-readiness
claim, legal-clearance claim, paid-pilot claim, payment enablement, money
movement, external publication, secret material, or deployment claim is
permitted by this boundary.

## What This Boundary Solves

The broader pilot-deferral boundary says a pilot stays delayed. This rehearsal
adds a smaller local practice surface: why the decision still stays deferred,
which stop rules protect it, and what evidence would be needed later before
one exact bounded action can even be considered.

This is useful because a solo operator can feel pressure to make a small pilot
sound harmless. The rehearsal keeps that pressure inside a local checklist:

1. State the pilot purpose question without choosing a pilot.
2. State participant, access, waitlist, signup, data, support, legal, payment,
   success, rollback, and public-claim stop rules.
3. Keep every rehearsal surface in `AwaitingEvidence`.
4. Keep every evidence reference as `manual_preparation_pending`.
5. Do not record names, emails, schedules, URLs, accounts, providers, customer
   details, private paths, credentials, secrets, payment values, or deployment
   targets.

## Current State

```text
pilot_deferral_rehearsal_boundary_state=AwaitingEvidence
deferral_rehearsal_executed=false
pilot_execution_allowed=false
participant_invitation_allowed=false
access_channel_opening_allowed=false
waitlist_opening_allowed=false
pilot_signup_open=false
customer_access_allowed=false
personal_data_collection_allowed=false
market_validation_claimed=false
support_readiness_claimed=false
legal_clearance_claimed=false
paid_pilot_allowed=false
payment_enabled=false
money_movement_allowed=false
external_publication_allowed=false
secret_material_allowed=false
deployment_allowed=false
```

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Pilot purpose deferral questions | Explain why a future pilot idea remains deferred. | Do not execute, schedule, or approve a pilot. |
| Participant boundary stop rule | Draft abstract participant-risk blockers. | Do not name, invite, contact, enroll, or assign people. |
| Access channel stop rule | Draft access-channel blockers. | Do not open links, accounts, forms, waitlists, signup paths, or invite routes. |
| Waitlist/signup stop rule | Draft why interest capture remains closed. | Do not open waitlists, signup forms, beta paths, or customer-access flows. |
| Data collection stop rule | Draft privacy and data-minimization blockers. | Do not collect or store personal data. |
| Support obligation stop rule | Draft support-duty blockers. | Do not promise response times, triage, incidents, or support coverage. |
| Legal/business stop rule | Draft qualified-review blockers. | Do not claim legal clearance, company authority, or terms readiness. |
| Paid pilot stop rule | Draft payment and money blockers. | Do not accept payment, enable payment, move money, or claim paid access. |
| Success metric stop rule | Draft local learning metric blockers. | Do not claim market validation, demand, or customer proof. |
| Rollback/recovery stop rule | Draft rollback and exit blockers. | Do not claim recovery, incident, or customer-exit readiness. |
| Public claim stop rule | Draft public-language blockers. | Do not publish externally or announce access, pilot, or deployment availability. |
| Reassessment handoff | Draft what later evidence would be needed. | Do not promote any surface out of `AwaitingEvidence`. |

## Operator Procedure

1. Treat the rehearsal as a paper checklist only.
2. Do not invite participants, open waitlists, open signup paths, open beta,
   create intake forms, collect personal data, start outreach, promise support,
   claim legal clearance, accept payment, publish externally, handle secrets,
   or deploy through this boundary.
3. Exclude private names, emails, schedules, account IDs, customer identities,
   provider values, private paths, payment values, credentials, secrets, and
   deployment targets.
4. Stop immediately if the rehearsal needs any outside person, public channel,
   external account, customer data, money movement, secret material, or runtime
   exposure.
5. Use the result only as a future review checklist for the main
   pilot-deferral boundary.

## Validation

Run:

```powershell
python scripts/validate_foundation_pilot_deferral_rehearsal_boundary.py
```

The validator checks that the pilot-deferral rehearsal witness:

1. keeps rehearsal execution, pilot execution, participant invitation,
   access-channel opening, waitlists, signup paths, customer access,
   personal-data collection, market validation, support readiness, legal
   clearance, paid pilot, payment, money movement, publication, secrets, and
   deployment blocked;
2. keeps every rehearsal surface in `AwaitingEvidence`;
3. keeps every evidence reference as `manual_preparation_pending`;
4. rejects URL, email, private path, participant, customer, account, provider,
   schedule, intake, billing, payment, secret, private-key, and
   deployment-shaped values; and
5. rejects promotion phrases that imply pilot, access, waitlist, signup,
   customer-access, validation, support, legal, payment, publication, or
   deployment promotion.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the broader pilot deferral boundary | [Foundation Pilot Deferral Boundary](FOUNDATION_PILOT_DEFERRAL_BOUNDARY.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare support safely | [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) |
| Prepare intake safely | [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md) |
| Prepare privacy/data safely | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |
| Keep deployment deferred safely | [Foundation Deployment Deferral Boundary](FOUNDATION_DEPLOYMENT_DEFERRAL_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: pilot deferral rehearsal execution blocked, pilot execution blocked, participant invitation blocked, access-channel opening blocked, waitlist opening blocked, pilot signup blocked, customer access blocked, personal-data collection blocked, market-validation claim blocked, support-readiness claim blocked, legal-clearance claim blocked, paid-pilot claim blocked, payment enablement blocked, money movement blocked, external publication blocked, secret material blocked, deployment blocked
  Open issues: pilot purpose deferral evidence, participant-boundary stop-rule evidence, access-channel stop-rule evidence, waitlist/signup stop-rule evidence, data-collection stop-rule evidence, support-obligation stop-rule evidence, legal/business stop-rule evidence, paid-pilot stop-rule evidence, success-metric stop-rule evidence, rollback/recovery stop-rule evidence, public-claim stop-rule evidence, and reassessment handoff remain AwaitingEvidence
  Next action: run the pilot-deferral rehearsal validator before relying on any pilot-deferral practice as evidence
