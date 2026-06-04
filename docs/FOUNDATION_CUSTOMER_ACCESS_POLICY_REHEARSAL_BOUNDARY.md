<!--
Purpose: define the Foundation Mode customer-access policy rehearsal boundary for public-safe access-rule drafting without inviting customers, creating accounts, opening channels, or deploying.
Governance scope: customer-access policy rehearsal planning, local eligibility and denial criteria, invitation exclusion, account and tenant exclusion, login route exclusion, support-duty blocking, terms/privacy blocking, personal-data exclusion, paid-access blocking, pilot/beta/waitlist blocking, external-publication restraint, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md, docs/FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md, docs/FOUNDATION_SUPPORT_READINESS_BOUNDARY.md, docs/FOUNDATION_PRIVACY_DATA_BOUNDARY.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, examples/foundation_customer_access_policy_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_customer_access_policy_rehearsal_boundary.py.
Invariants: no access-policy approval, no customer access opening, no customer invitation, no account creation, no tenant provisioning, no login route publication, no support commitment, no terms/privacy readiness claim, no personal-data collection, no paid access, no pilot/beta/waitlist access, no external publication, and no deployment claim.
-->

# Foundation Customer Access Policy Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** customer-access policy rehearsal means drafting local entry,
> denial, pause, rollback, and handoff rules for future access decisions. It
> does not approve access, invite customers, create accounts, provision tenants,
> publish login routes, make support commitments, claim terms/privacy readiness,
> collect personal data, accept paid access, open pilot/beta/waitlist access,
> publish externally, or deploy anything.

Witness packet: [`../examples/foundation_customer_access_policy_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_customer_access_policy_rehearsal_witness.awaiting_evidence.json)

Rule: Customer access policy rehearsal is a local paper exercise, not an access
approval, customer invitation, or readiness proof.

No access-policy approval, customer access opening, customer invitation,
account creation, tenant provisioning, login route publication, support
commitment, terms/privacy readiness claim, personal-data collection, paid
access, pilot/beta/waitlist access, external publication, or deployment claim
is permitted by this boundary.

## What This Boundary Solves

The broad customer-access boundary keeps access closed. A solo operator still
needs a safe way to think through future access decisions before anyone outside
the operator can use the system.

This is preparation only:

1. Draft entry and denial criteria locally.
2. Draft pause and exit rules locally.
3. Draft account, tenant, login-route, support, terms/privacy, data, payment,
   and deployment stop rules locally.
4. Keep every access mechanism closed.
5. Treat the rehearsal as `AwaitingEvidence` until a later governed witness
   promotes exactly one bounded action.

## Current State

```text
customer_access_policy_rehearsal_boundary_state=AwaitingEvidence
access_policy_rehearsal_executed=false
access_policy_approved=false
customer_access_allowed=false
customer_invitation_allowed=false
account_creation_allowed=false
tenant_provisioning_allowed=false
login_route_publication_allowed=false
support_commitment_allowed=false
terms_privacy_ready_claimed=false
personal_data_collection_allowed=false
paid_access_allowed=false
pilot_beta_waitlist_access_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Entry criteria questions | Draft generic local criteria. | Do not approve, qualify, or admit customers. |
| Denial criteria questions | Draft why access should remain closed. | Do not reject real people or send replies. |
| Pause/stop rules | Draft when access work must stop. | Do not override privacy, legal, support, payment, runtime, or deployment gates. |
| Account/tenant boundary | Draft account and tenant questions. | Do not create accounts, tenants, logins, identities, or access links. |
| Invitation boundary | Draft invitation control questions. | Do not invite customers or generate invite links. |
| Support-duty boundary | Draft future support-duty questions. | Do not promise response times, SLA, or incident coverage. |
| Terms/privacy boundary | Draft qualified-review questions. | Do not claim terms readiness, privacy readiness, or legal clearance. |
| Data/payment boundary | Draft exposure questions. | Do not collect personal data, payment details, subscriptions, or invoices. |
| Publication/deployment boundary | Draft public-claim and deployment stop questions. | Do not publish access routes, public offers, or deployment claims. |
| Handoff note | Draft later evidence requirements. | Do not claim customer-access readiness. |

## Operator Procedure

1. Keep customer-access policy examples fictional, local, and public-safe.
2. Do not record names, emails, organization names, account IDs, tenant IDs,
   invite links, login URLs, private paths, payment details, customer data, or
   personal data.
3. Do not create accounts, tenants, identities, invitations, access links,
   waitlists, beta/pilot channels, payment flows, support channels, or login
   routes.
4. Stop if work requires support commitments, legal/privacy conclusions,
   personal-data handling, payment collection, runtime exposure, publication,
   or deployment.
5. Use the result only as a draft for future customer-access design.

## Validation

Run:

```powershell
python scripts/validate_foundation_customer_access_policy_rehearsal_boundary.py
```

The validator checks that the customer-access policy rehearsal witness:

1. keeps access-policy approval, customer access, invitations, account
   creation, tenant provisioning, login route publication, support commitment,
   terms/privacy readiness, personal-data collection, paid access,
   pilot/beta/waitlist access, external publication, and deployment blocked;
2. keeps every rehearsal surface in `AwaitingEvidence`;
3. rejects URL, email, private path, account, tenant, invite, login, customer,
   personal-data, support, terms/privacy, payment, publication, and
   deployment-shaped values; and
4. rejects promotion phrases that imply access policy approval, customer
   access, invitation, account, tenant, login, support, terms/privacy, paid
   access, pilot/beta/waitlist, publication, or deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Prepare the broader customer-access boundary | [Foundation Customer Access Boundary](FOUNDATION_CUSTOMER_ACCESS_BOUNDARY.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare support readiness safely | [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) |
| Prepare privacy/data safely | [Foundation Privacy Data Boundary](FOUNDATION_PRIVACY_DATA_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: access-policy approval blocked, customer access blocked, invitation blocked, account creation blocked, tenant provisioning blocked, login route publication blocked, support commitment blocked, terms/privacy readiness blocked, personal-data collection blocked, paid access blocked, pilot/beta/waitlist access blocked, external publication blocked, deployment blocked
  Open issues: entry-criteria evidence, denial-criteria evidence, pause-rule evidence, account/tenant evidence, invitation-boundary evidence, support-duty evidence, terms/privacy evidence, data/payment evidence, publication/deployment evidence, and handoff evidence remain AwaitingEvidence
  Next action: run the customer-access policy rehearsal validator before relying on access-policy planning as evidence
