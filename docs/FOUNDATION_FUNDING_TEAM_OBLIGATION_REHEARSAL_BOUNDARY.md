<!--
Purpose: define the Foundation Mode funding/team obligation rehearsal boundary for local public-safe obligation mapping without fundraising, outreach, grants, pitch publication, hiring, contractors, advisors, compensation, equity, payroll, budget commitment, spending, company/legal claims, customer access, money movement, external publication, secrets, or deployment.
Governance scope: funding/team obligation rehearsal, local question drafting, contact-list exclusion, obligation blocking, money-movement blocking, legal/company blocking, customer-access blocking, external-publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_FUNDING_TEAM_BOUNDARY.md, docs/FOUNDATION_COST_BUDGET_BOUNDARY.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, examples/foundation_funding_team_obligation_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_funding_team_obligation_rehearsal_boundary.py.
Invariants: no funding readiness claim, no team readiness claim, no fundraising, no investor outreach, no grant application, no pitch publication, no hiring, no contractor engagement, no advisor commitment, no compensation commitment, no equity promise, no payroll setup, no budget commitment, no spending, no company-formation claim, no legal-clearance claim, no customer access, no contact-list storage, no money movement, no external publication, no secret material, and no deployment claim.
-->

# Foundation Funding Team Obligation Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** funding/team obligation rehearsal means mapping what duties
> would appear later if you contacted investors, applied for grants, published a
> pitch, hired people, used contractors, committed advisors, promised payment or
> equity, set budgets, or recruited publicly. It does not do any of those
> things.

Witness packet: [`../examples/foundation_funding_team_obligation_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_funding_team_obligation_rehearsal_witness.awaiting_evidence.json)

Rule: Funding/team obligation rehearsal is a local paper exercise, not funding,
team formation, outreach, recruiting, payment, or approval.

No funding readiness, team readiness, fundraising, investor outreach, grant
application, pitch publication, hiring, contractor engagement, advisor
commitment, compensation commitment, equity promise, payroll setup, budget
commitment, spending, company-formation claim, legal-clearance claim, customer
access, contact-list storage, money movement, external publication, secret
material, or deployment claim is permitted by this boundary.

## What This Boundary Solves

The funding/team boundary keeps real obligations closed. A solo operator still
needs a safe way to understand the obligation surface before any outreach,
application, recruiting, compensation, equity, payroll, budget, or payment work
exists.

This is preparation only:

1. Draft local obligation questions for each future funding/team action.
2. Keep every surface in `AwaitingEvidence`.
3. Keep evidence references as `manual_preparation_pending`.
4. Do not store investor names, contact lists, emails, URLs, application IDs,
   candidate IDs, contractor IDs, advisor names, payroll IDs, payment IDs,
   budget amounts, private paths, secrets, or private key material.
5. Do not claim funding readiness, team readiness, legal clearance, company
   readiness, customer access, paid launch readiness, or deployment readiness.

## Current State

```text
funding_team_obligation_rehearsal_boundary_state=AwaitingEvidence
obligation_rehearsal_executed=false
funding_readiness_claimed=false
team_readiness_claimed=false
fundraising_allowed=false
investor_outreach_allowed=false
grant_application_allowed=false
pitch_publication_allowed=false
hiring_allowed=false
contractor_engagement_allowed=false
advisor_commitment_allowed=false
compensation_commitment_allowed=false
equity_promise_allowed=false
payroll_setup_allowed=false
budget_commitment_allowed=false
spending_allowed=false
company_formation_claimed=false
legal_clearance_claimed=false
customer_access_allowed=false
contact_list_storage_allowed=false
money_movement_allowed=false
external_publication_allowed=false
secret_material_allowed=false
deployment_allowed=false
```

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Solo capacity obligation questions | Draft what funding/team work would demand from one operator. | Do not claim team coverage or support capacity. |
| Funding readiness obligation questions | Draft readiness and evidence questions. | Do not claim funding readiness or funding secured. |
| Investor outreach obligation questions | Draft what investor contact would require later. | Do not contact investors or store contact lists. |
| Grant obligation questions | Draft application-duty questions. | Do not submit grants or record application IDs. |
| Pitch publication obligation questions | Draft public-claim and evidence questions. | Do not publish, send, or host a pitch. |
| Hiring obligation questions | Draft role, support, and supervision questions. | Do not open jobs, collect candidates, or claim hiring readiness. |
| Contractor obligation questions | Draft scope, access, and payment questions. | Do not engage contractors or create statements of work. |
| Advisor obligation questions | Draft advisor-boundary questions. | Do not commit advisors, mentors, boards, or access. |
| Compensation/equity obligation questions | Draft promise and ownership questions. | Do not promise salary, equity, options, percentages, or ownership. |
| Payroll/budget obligation questions | Draft payroll, invoice, and budget questions. | Do not set up payroll, approve budgets, spend, or move money. |
| Public recruiting stop rule | Draft language that must stay blocked. | Do not publish job posts, recruiting copy, or external calls. |
| Legal/company handoff | Draft later evidence needs. | Do not claim company formation, legal clearance, or qualified review. |

## Operator Procedure

1. Keep all entries fictional, local, and public-safe.
2. Draft obligation questions only; do not execute or promote actions.
3. Exclude contact details, account details, application details, payment
   details, budget amounts, candidate details, private paths, secrets, and
   private key material.
4. Stop if work requires outside people, payment, legal judgment, company
   formation, funding, grants, recruiting, compensation, equity, customer
   access, public publication, or deployment.
5. Use the result only as a future evidence checklist.

## Validation

Run:

```powershell
python scripts/validate_foundation_funding_team_obligation_rehearsal_boundary.py
```

The validator checks that the funding/team obligation rehearsal witness:

1. keeps funding readiness, team readiness, fundraising, investor outreach,
   grants, pitch publication, hiring, contractors, advisors, compensation,
   equity, payroll, budget, spending, company/legal claims, customer access,
   contact-list storage, money movement, publication, secrets, and deployment
   blocked;
2. keeps every rehearsal surface in `AwaitingEvidence`;
3. keeps every evidence reference as `manual_preparation_pending`;
4. rejects URL, email, private path, currency amount, investor, contact, grant,
   pitch, job, candidate, contractor, advisor, payroll, equity, compensation,
   payment, account, secret, private-key, and deployment-shaped values; and
5. rejects promotion phrases that imply funding/team readiness or activation.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the broader funding/team boundary | [Foundation Funding Team Boundary](FOUNDATION_FUNDING_TEAM_BOUNDARY.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare cost/budget safely | [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: funding readiness blocked, team readiness blocked, fundraising blocked, investor outreach blocked, grants blocked, pitch publication blocked, hiring blocked, contractor engagement blocked, advisor commitment blocked, compensation commitment blocked, equity promise blocked, payroll setup blocked, budget commitment blocked, spending blocked, company-formation claim blocked, legal-clearance claim blocked, customer access blocked, contact-list storage blocked, money movement blocked, external publication blocked, secret material blocked, deployment blocked
  Open issues: solo capacity obligation evidence, funding readiness obligation evidence, investor outreach obligation evidence, grant obligation evidence, pitch publication obligation evidence, hiring obligation evidence, contractor obligation evidence, advisor obligation evidence, compensation/equity obligation evidence, payroll/budget obligation evidence, public recruiting stop-rule evidence, and legal/company handoff remain AwaitingEvidence
  Next action: run the funding/team obligation rehearsal validator before relying on obligation mapping as evidence
