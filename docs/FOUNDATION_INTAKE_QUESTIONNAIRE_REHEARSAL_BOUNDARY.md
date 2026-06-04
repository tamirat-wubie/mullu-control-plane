<!--
Purpose: define the Foundation Mode intake questionnaire rehearsal boundary for public-safe field drafting without publishing forms, collecting submissions, opening waitlists, or onboarding customers.
Governance scope: intake questionnaire rehearsal planning, fictional local field categories, consent/privacy stop rules, collection exclusion, CRM exclusion, outreach exclusion, customer-access blocking, payment blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md, examples/foundation_intake_questionnaire_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_intake_questionnaire_rehearsal_boundary.py.
Invariants: no questionnaire execution claim, no active intake form, no form publication, no waitlist opening, no pilot signup, no personal-data collection, no CRM import, no outreach campaign, no customer onboarding, no customer access, no payment collection, no legal/privacy readiness claim, and no deployment claim.
-->

# Foundation Intake Questionnaire Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** intake questionnaire rehearsal preparation means drafting the
> shape of future intake questions with fictional local examples. It does not
> publish a form, collect submissions, open a waitlist, accept pilot signups,
> collect personal data, import contacts, start outreach, onboard customers,
> open customer access, collect payment, claim legal or privacy readiness, or
> deploy anything.

Witness packet: [`../examples/foundation_intake_questionnaire_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_intake_questionnaire_rehearsal_witness.awaiting_evidence.json)

Rule: Intake questionnaire rehearsal is a local paper exercise, not an intake
channel or onboarding-readiness proof.

No questionnaire execution, active intake form, form publication, waitlist
opening, pilot signup, personal-data collection, CRM import, outreach campaign,
customer onboarding, customer access, payment collection, legal/privacy
readiness claim, or deployment claim is permitted by this boundary.

## What This Boundary Solves

The broad intake/onboarding boundary says the intake channel stays closed. A
solo operator still needs a safe way to prepare the future question shape before
any collection surface exists.

This is preparation only:

1. Draft generic field categories locally.
2. Draft eligibility prompts without accepting real users.
3. Draft consent, privacy, retention, and decline questions without legal or
   privacy readiness claims.
4. Keep every collection, outreach, CRM, customer-access, payment, and
   deployment surface closed.
5. Treat the rehearsal as `AwaitingEvidence` until a later governed witness
   promotes exactly one bounded action.

## Current State

```text
intake_questionnaire_rehearsal_boundary_state=AwaitingEvidence
questionnaire_rehearsal_executed=false
active_intake_form_exists=false
form_publication_allowed=false
waitlist_open=false
pilot_signup_open=false
personal_data_collection_allowed=false
crm_import_allowed=false
outreach_campaign_allowed=false
customer_onboarding_allowed=false
customer_access_allowed=false
payment_collection_allowed=false
legal_privacy_readiness_claimed=false
deployment_allowed=false
```

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Fictional field categories | Draft generic field categories. | Do not publish a form, survey, waitlist, or signup link. |
| Eligibility prompt shape | Draft local eligibility prompts. | Do not qualify, accept, reject, or onboard real users. |
| Consent boundary questions | Draft questions for later qualified review. | Do not claim consent, terms, privacy, or legal readiness. |
| Privacy minimization questions | Draft what data should not be collected. | Do not collect, store, process, or import personal data. |
| Retention/deletion questions | Draft retention and deletion questions. | Do not create retention systems or deletion promises. |
| Disqualification reply shape | Draft fictional reply shapes. | Do not send replies or start outreach. |
| Operator review gate | Draft the later go/no-go review questions. | Do not approve intake, onboarding, customer access, payment, or deployment. |
| Handoff note | Draft what future evidence would require. | Do not claim intake readiness or onboarding readiness. |

## Operator Procedure

1. Keep questionnaire examples fictional, local, and public-safe.
2. Do not record real names, emails, organization names, account values, private
   paths, contact lists, payment details, or personal data.
3. Do not publish form links, waitlists, surveys, signup pages, intake email
   flows, or customer-access routes.
4. Stop if work requires legal/privacy conclusions, consent capture, CRM import,
   outreach, onboarding, payment collection, customer support, customer access,
   or deployment.
5. Use the result only as a draft for future intake design.

## Validation

Run:

```powershell
python scripts/validate_foundation_intake_questionnaire_rehearsal_boundary.py
```

The validator checks that the intake questionnaire rehearsal witness:

1. keeps questionnaire execution, form publication, waitlist opening, pilot
   signup, personal-data collection, CRM import, outreach, onboarding,
   customer access, payment collection, legal/privacy readiness claims, and
   deployment blocked;
2. keeps every rehearsal surface in `AwaitingEvidence`;
3. rejects URL, email, private path, form-link, CRM, contact, payment, legal,
   consent, customer, onboarding, and deployment-shaped values; and
4. rejects promotion phrases that imply intake, form, waitlist, signup,
   collection, onboarding, customer-access, payment, legal/privacy, or
   deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Prepare the broader intake boundary | [Foundation Intake Onboarding Boundary](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare privacy/data without handling people data | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |
| Prepare customer access without opening access | [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: questionnaire execution blocked, active form blocked, form publication blocked, waitlist closed, pilot signup closed, personal-data collection blocked, CRM import blocked, outreach blocked, customer onboarding blocked, customer access blocked, payment collection blocked, legal/privacy readiness claim blocked, deployment blocked
  Open issues: field-category evidence, eligibility-prompt evidence, consent-boundary evidence, privacy-minimization evidence, retention/deletion evidence, reply-shape evidence, operator-review evidence, and handoff evidence remain AwaitingEvidence
  Next action: run the intake questionnaire rehearsal validator before relying on questionnaire planning as evidence
