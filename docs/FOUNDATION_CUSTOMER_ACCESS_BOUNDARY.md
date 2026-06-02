<!--
Purpose: define the Foundation Mode customer-access boundary before any invitation, account creation, onboarding readiness, support commitment, terms/privacy readiness, personal-data collection, paid access, pilot access, beta access, waitlist opening, external publication, or deployment claim.
Governance scope: customer-access posture, local access-policy questions, invitation blocking, account-creation blocking, onboarding-readiness blocking, support-duty blocking, terms/privacy blocking, data-handling blocking, paid-access blocking, pilot/beta/waitlist blocking, external-publication restraint, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md, docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md, docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, examples/foundation_customer_access_witness.awaiting_evidence.json, scripts/validate_foundation_customer_access_boundary.py.
Invariants: no customer access opening, no customer invitation, no account creation, no access channel opening, no onboarding readiness claim, no support commitment, no terms/privacy readiness claim, no personal-data collection, no paid access, no pilot access, no beta access, no waitlist opening, no external publication, and no deployment claim.
-->

# Foundation Customer Access Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** customer-access preparation means drafting the local questions
> that would be needed before anyone outside the operator can use the system. It
> does not invite customers, open accounts, publish access channels, onboard
> users, collect personal data, accept payment, open beta/pilot/waitlist access,
> publish externally, or deploy anything.

Witness packet: [`../examples/foundation_customer_access_witness.awaiting_evidence.json`](../examples/foundation_customer_access_witness.awaiting_evidence.json)

Rule: Customer-access preparation is a local planning boundary, not an access approval.

No customer access opening, customer invitation, account creation, access-channel
opening, onboarding-readiness claim, support commitment, terms/privacy readiness
claim, personal-data collection, paid access, pilot access, beta access, waitlist
opening, external publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

Customer access is the point where private project work becomes an obligation to
other people. It creates support, safety, privacy, legal, recovery, billing, and
trust duties before the project has proven those duties can be handled.

This boundary keeps the work small:

1. Draft access-policy questions locally.
2. Draft invitation, account, and onboarding questions locally.
3. Draft support, terms/privacy, data, rollback, and payment-exposure questions locally.
4. Keep every access channel closed until later evidence promotes one exact step.

## Current State

```text
customer_access_boundary_state=AwaitingEvidence
customer_access_allowed=false
customer_invitation_allowed=false
account_creation_allowed=false
access_channel_open_allowed=false
onboarding_ready_claimed=false
support_commitment_allowed=false
terms_privacy_ready_claimed=false
personal_data_collection_allowed=false
paid_access_allowed=false
pilot_access_allowed=false
beta_access_allowed=false
waitlist_open=false
external_publication_allowed=false
deployment_allowed=false
```

## Public-Safe Preparation Surfaces

| Surface | Public-safe record here | Do not claim here |
| --- | --- | --- |
| Access policy questions | Local entry/exit criteria only. | Access approval or customer eligibility. |
| Eligibility boundary questions | Draft boundary questions only. | Accepted customers or qualification results. |
| Account creation questions | Local account-shape questions only. | Account creation, tenant setup, or login readiness. |
| Invitation flow questions | Draft invitation controls only. | Sent invitations, invite links, or open access channels. |
| Support duty questions | Local support-duty questions only. | SLA, support readiness, or incident coverage. |
| Terms/privacy questions | Draft review questions only. | Legal clearance, terms readiness, or privacy readiness. |
| Data handling questions | Local data-handling questions only. | Personal-data collection, storage, or processor activation. |
| Rollback/exit questions | Draft recovery and exit questions only. | Customer rollback readiness or recovery guarantee. |
| Payment exposure questions | Local paid-access questions only. | Payment acceptance, paid pilot, or money movement. |
| Public-claim questions | Local wording review only. | Public launch, customer readiness, or deployment readiness. |

## Operator Procedure

1. Keep every customer-access artifact local and non-operational.
2. Do not invite customers, create accounts, open access channels, send invite
   links, open beta, open a pilot, open a waitlist, or publish signup language.
3. Do not collect personal data, payment details, support requests, or customer
   commitments in Foundation Mode.
4. Do not claim customer readiness until support, privacy/data, legal/business,
   security, recovery, runtime, payment, and deployment evidence are all
   promoted by later witnesses.
5. Treat every customer-access surface as `AwaitingEvidence` until a later
   signed witness promotes exactly one bounded external action.

## Validation

Run:

```powershell
python scripts/validate_foundation_customer_access_boundary.py
```

The validator checks that the witness packet:

1. keeps every customer-access surface in `AwaitingEvidence`;
2. keeps invitation, account creation, access channels, onboarding readiness,
   support commitment, terms/privacy readiness, personal-data collection, paid
   access, pilot/beta/waitlist access, external publication, and deployment
   blocked;
3. rejects URL, email, private path, account, invite, tenant, customer, or secret
   shaped values; and
4. rejects customer-access promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare intake/onboarding safely | [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md) |
| Prepare support readiness safely | [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) |
| Prepare privacy/data safely | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: customer access blocked, customer invitation blocked, account creation blocked, access channel blocked, onboarding readiness blocked, support commitment blocked, terms/privacy readiness blocked, personal-data collection blocked, paid access blocked, pilot access blocked, beta access blocked, waitlist blocked, external publication blocked, deployment blocked
  Open issues: access policy evidence, eligibility boundary evidence, account creation evidence, invitation flow evidence, support duty evidence, terms/privacy review evidence, data handling evidence, rollback/exit evidence, payment exposure evidence, public-claim evidence, and customer-access witness remain AwaitingEvidence
  Next action: run the customer-access boundary validator, then keep customer-access surfaces closed until evidence promotes one bounded step
