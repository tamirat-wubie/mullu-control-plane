<!--
Purpose: define the Foundation Mode intake and onboarding boundary before any waitlist, pilot signup, customer onboarding, PII collection, outreach, paid access, or deployment claim.
Governance scope: intake posture, onboarding posture, consent/privacy preparation, no active form, no waitlist, no pilot signup, no PII collection, no CRM import, no customer access, and no deployment claim.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_intake_onboarding_witness.awaiting_evidence.json, scripts/validate_foundation_intake_onboarding_boundary.py.
Invariants: no active intake form, no waitlist opening, no pilot signup, no customer onboarding, no PII collection, no CRM import, no outreach campaign, no paid access, no customer access, no deployment claim.
-->

# Foundation Intake Onboarding Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** intake and onboarding preparation means drafting the questions,
> consent rules, and onboarding steps that would be needed later. It does not
> publish a form, open a waitlist, accept pilot signups, collect personal data,
> import contacts, start outreach, onboard customers, or deploy anything.

Witness packet: [`../examples/foundation_intake_onboarding_witness.awaiting_evidence.json`](../examples/foundation_intake_onboarding_witness.awaiting_evidence.json)

Rule: Intake preparation is a local planning boundary, not an active intake channel.

No active intake form, waitlist opening, pilot signup, customer onboarding, PII
collection, CRM import, outreach campaign, paid access, customer access, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

Intake is easy to confuse with readiness. A form, waitlist, or signup page can
create privacy duties, support duties, expectation pressure, and customer
evidence claims before the project is ready.

This boundary keeps intake preparation small:

1. Draft future eligibility questions locally.
2. Draft consent and privacy questions locally.
3. Draft onboarding steps locally.
4. Keep all collection, outreach, and customer access closed.

## Current State

```text
intake_onboarding_boundary_state=AwaitingEvidence
intake_open=false
waitlist_open=false
pilot_signup_open=false
customer_onboarding_allowed=false
pii_collection_allowed=false
crm_import_allowed=false
outreach_campaign_allowed=false
paid_access_allowed=false
customer_access_allowed=false
deployment_allowed=false
```

## Public-Safe Preparation Surfaces

| Surface | Public-safe record here | Do not claim here |
| --- | --- | --- |
| Future interest form shape | Local field categories only. | Live form URL, submissions, or collection. |
| Eligibility questions | Draft questions only. | Accepted users or pilot qualification. |
| Consent language | Draft legal/business questions only. | Privacy compliance or legal clearance. |
| Onboarding steps | Local checklist only. | Customer onboarding readiness. |
| Data retention questions | Draft retention questions only. | Approved privacy policy or retention system. |
| Decline/reply template | Draft response wording only. | Active support or outreach campaign. |

## Operator Procedure

1. Keep every intake artifact local and non-collecting.
2. Do not publish forms, waitlists, signup links, surveys, or intake email flows.
3. Do not collect personal data, contact lists, customer details, or payment
   details in Foundation Mode.
4. Do not start outreach or onboarding until legal/business, support, privacy,
   recovery, and deployment evidence close.
5. Treat every intake surface as `AwaitingEvidence` until a later signed witness
   promotes it.

## Validation

Run:

```powershell
python scripts/validate_foundation_intake_onboarding_boundary.py
```

The validator checks that the witness packet:

1. keeps every intake/onboarding surface in `AwaitingEvidence`;
2. keeps forms, waitlists, pilot signup, PII collection, CRM import, outreach,
   paid access, customer access, and deployment blocked;
3. rejects URL, email, private path, CRM, account, secret, or form-link shaped
   values; and
4. rejects intake/onboarding promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare support readiness safely | [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: intake closed, waitlist closed, pilot signup closed, PII collection blocked, CRM import blocked, outreach blocked, customer onboarding blocked, paid access blocked, deployment blocked
  Open issues: privacy review, terms, consent language, support capacity, data retention, onboarding operations, and deployment evidence remain AwaitingEvidence
  Next action: run the intake/onboarding boundary validator, then keep intake surfaces closed until evidence promotes them
