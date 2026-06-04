<!--
Purpose: define the Foundation Mode funding and team boundary before any fundraising, investor outreach, grant application, pitch publication, hiring, contractor engagement, advisor commitment, compensation commitment, equity promise, payroll setup, budget commitment, company-formation claim, legal-clearance claim, external publication, or deployment claim.
Governance scope: funding posture, team posture, local planning questions, investor-outreach blocking, grant-application blocking, pitch-publication blocking, hiring blocking, contractor/advisor blocking, compensation/equity blocking, payroll blocking, budget blocking, legal/company blocking, money-movement blocking, external-publication restraint, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md, docs/FOUNDATION_COST_BUDGET_BOUNDARY.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, docs/FOUNDATION_FUNDING_TEAM_OBLIGATION_REHEARSAL_BOUNDARY.md, examples/foundation_funding_team_witness.awaiting_evidence.json, scripts/validate_foundation_funding_team_boundary.py.
Invariants: no fundraising, no investor outreach, no grant application, no pitch publication, no hiring, no contractor engagement, no advisor commitment, no compensation commitment, no equity promise, no payroll setup, no budget commitment, no company-formation claim, no legal-clearance claim, no money movement, no external publication, and no deployment claim.
-->

# Foundation Funding Team Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** funding and team preparation means drafting the local questions
> needed before asking anyone for money, work, advice, equity, payroll, grants,
> or public recruiting. It does not contact investors, apply for grants, publish
> a pitch, hire people, engage contractors, promise equity, set compensation,
> set up payroll, commit budget, form a company, claim legal clearance, publish
> externally, move money, or deploy anything.

Witness packet: [`../examples/foundation_funding_team_witness.awaiting_evidence.json`](../examples/foundation_funding_team_witness.awaiting_evidence.json)

Rule: Funding/team preparation is a local planning boundary, not fundraising, hiring, or team formation.

No fundraising, investor outreach, grant application, pitch publication, hiring,
contractor engagement, advisor commitment, compensation commitment, equity
promise, payroll setup, budget commitment, company-formation claim,
legal-clearance claim, money movement, external publication, or deployment claim
is permitted by this boundary.

## What This Boundary Solves

Funding and team work can create obligations before the project has stable local
proof, legal/business review, budget authority, ownership clarity, or support
capacity. Even a casual pitch, job post, advisor note, or contractor message can
create expectation pressure and confused claims.

This boundary keeps preparation small:

1. Draft funding-readiness and investor-boundary questions locally.
2. Draft grant, pitch, hiring, contractor, advisor, compensation, equity, and
   payroll questions locally.
3. Keep every outside person, money, employment, legal, and publication action
   closed until a later witness promotes one exact step.

## Current State

```text
funding_team_boundary_state=AwaitingEvidence
fundraising_allowed=false
investor_outreach_allowed=false
grant_application_allowed=false
pitch_deck_publication_allowed=false
hiring_allowed=false
contractor_engagement_allowed=false
advisor_commitment_allowed=false
compensation_commitment_allowed=false
equity_promise_allowed=false
payroll_setup_allowed=false
budget_commitment_allowed=false
company_formation_claimed=false
legal_clearance_claimed=false
money_movement_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Public-Safe Preparation Surfaces

| Surface | Public-safe record here | Do not claim here |
| --- | --- | --- |
| Funding readiness questions | Local readiness questions only. | Fundraising readiness or funding secured. |
| Investor boundary questions | Draft investor-contact boundaries only. | Investor outreach, interest, or meetings. |
| Grant program questions | Local grant-fit questions only. | Grant submission or award likelihood. |
| Pitch deck questions | Draft pitch-content questions only. | Published pitch, sent deck, or fundraising launch. |
| Hiring role questions | Local role-gap questions only. | Open job, candidate pipeline, or hiring readiness. |
| Contractor engagement questions | Draft contractor-scope questions only. | Contractor engagement, SOW, or vendor commitment. |
| Advisor/mentor questions | Local advisor-boundary questions only. | Advisor commitment, mentor assignment, or board formation. |
| Compensation/equity questions | Local compensation and ownership questions only. | Salary, equity, option, or ownership promise. |
| Payroll/budget questions | Draft payroll and budget questions only. | Payroll setup, budget approval, or spend authority. |
| Public recruiting questions | Local wording questions only. | Job post, public recruiting, or external publication. |

## Operator Procedure

1. Keep every funding/team artifact local and non-binding.
2. Do not contact investors, submit grants, send pitch decks, publish recruiting
   language, hire people, engage contractors, commit advisors, promise equity,
   promise compensation, set up payroll, or commit budgets.
3. Do not use local funding/team planning to claim company readiness, legal
   clearance, operational capacity, or team coverage.
4. Treat every funding/team surface as `AwaitingEvidence` until legal/business,
   budget, ownership, support, recovery, runtime, and deployment evidence close.

## Validation

Run:

```powershell
python scripts/validate_foundation_funding_team_boundary.py
```

The validator checks that the witness packet:

1. keeps every funding/team surface in `AwaitingEvidence`;
2. keeps fundraising, investor outreach, grants, pitch publication, hiring,
   contractor engagement, advisor commitment, compensation, equity, payroll,
   budget, money movement, external publication, and deployment blocked;
3. rejects URL, email, private path, amount, investor, grant, job, payroll,
   equity, compensation, or secret shaped values; and
4. rejects funding/team promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare operator readiness safely | [Foundation Operator Readiness Boundary](FOUNDATION_OPERATOR_READINESS_BOUNDARY.md) |
| Prepare cost/budget safely | [Foundation Cost Budget Boundary](FOUNDATION_COST_BUDGET_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |
| Rehearse funding/team obligations without obligations | [Foundation Funding Team Obligation Rehearsal Boundary](FOUNDATION_FUNDING_TEAM_OBLIGATION_REHEARSAL_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: fundraising blocked, investor outreach blocked, grants blocked, pitch publication blocked, hiring blocked, contractor engagement blocked, advisor commitment blocked, compensation commitment blocked, equity promise blocked, payroll setup blocked, budget commitment blocked, company-formation claim blocked, legal-clearance claim blocked, money movement blocked, external publication blocked, deployment blocked
  Open issues: funding readiness evidence, investor boundary evidence, grant program evidence, pitch deck evidence, hiring role evidence, contractor engagement evidence, advisor/mentor evidence, compensation/equity evidence, payroll/budget evidence, public recruiting evidence, legal/business review, and funding/team witness remain AwaitingEvidence
  Next action: run the funding/team boundary validator, then keep funding and team actions closed until evidence promotes one bounded step
