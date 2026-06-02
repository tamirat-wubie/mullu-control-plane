<!--
Purpose: define the Foundation Mode operator-readiness boundary for a solo operator before any team, hiring, support, authority, or deployment claim.
Governance scope: solo-operator planning, local capacity questions, skill-gap questions, learning-plan questions, decision-authority questions, escalation-boundary questions, fatigue stop rules, review cadence, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_operator_readiness_witness.awaiting_evidence.json, scripts/validate_foundation_operator_readiness_boundary.py.
Invariants: no solo-operator capacity verification claim, no schedule-readiness claim, no skill-readiness claim, no team-readiness claim, no hiring-readiness claim, no delegation-readiness claim, no incident-coverage readiness claim, no support-coverage readiness claim, no legal-authority readiness claim, no financial-authority readiness claim, no private schedule or health recording, and no deployment claim.
-->

# Foundation Operator Readiness Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** operator-readiness preparation means writing down the solo
> operator questions that keep work small, reversible, and paced. It does not
> prove capacity, verify a schedule, claim skill readiness, create a team,
> authorize hiring, delegate work, promise coverage, claim legal or financial
> authority, record private personal details, or deploy anything.

Witness packet: [`../examples/foundation_operator_readiness_witness.awaiting_evidence.json`](../examples/foundation_operator_readiness_witness.awaiting_evidence.json)

Rule: Operator-readiness preparation is a local planning boundary, not
permission to claim operational readiness.

No solo-operator capacity verification, schedule-readiness claim,
skill-readiness claim, team-readiness claim, hiring-readiness claim,
delegation-readiness claim, incident-coverage readiness claim, support-coverage
readiness claim, legal-authority readiness claim, financial-authority readiness
claim, private schedule recording, private health recording, or deployment
claim is permitted by this boundary.

## What This Boundary Solves

Foundation Mode is intentionally solo and cautious. That is useful only if the
project keeps the operator surface honest: one person, local proof first,
bounded tasks, no fake support coverage, no hidden delegation, and no pressure
to act like a team or company before evidence exists.

This is preparation only:

1. The repository can name solo-operator planning surfaces.
2. The witness can prove every surface is still `AwaitingEvidence`.
3. Validators can reject premature team, hiring, support, authority, or
   deployment claims.
4. No private schedule, private health detail, legal authority, financial
   authority, team operation, external delegation, support coverage, or
   deployment is created by this document or validator.

## Current State

```text
operator_readiness_boundary_state=AwaitingEvidence
operator_capacity_verified=false
schedule_readiness_claimed=false
skill_readiness_claimed=false
team_readiness_claimed=false
hiring_ready_claimed=false
delegation_ready_claimed=false
incident_coverage_ready_claimed=false
support_coverage_ready_claimed=false
legal_authority_ready_claimed=false
financial_authority_ready_claimed=false
private_schedule_recording_allowed=false
private_health_recording_allowed=false
deployment_allowed=false
```

## Operator-Readiness Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Solo capacity questions | Define how to keep work small and reversible. | Do not claim capacity is verified. |
| Time-budget questions | Draft pacing and stop-condition questions. | Do not record private schedule details or claim schedule readiness. |
| Skill-gap questions | Name learning areas as public-safe categories. | Do not claim skill readiness. |
| Learning-plan questions | Draft the next learning loop. | Do not claim training completion. |
| Decision-authority questions | Define when to pause, ask, or document. | Do not claim legal or financial authority readiness. |
| Escalation-boundary questions | Draft when outside review may be needed. | Do not delegate, hire, or imply team coverage. |
| Fatigue stop rules | Draft local stop rules for risky actions. | Do not record private health details. |
| Review cadence questions | Draft when to re-check the prerequisite ledger. | Do not claim incident or support coverage. |

## Operator Procedure

1. Keep operator planning public-safe and category-level.
2. Do not record private schedule, private health, account, money, or legal
   authority details in Git.
3. Treat every operator-readiness surface as `AwaitingEvidence`.
4. Convert broad work into one small local proof item before any outside action.
5. Do not present the project as team-ready, support-ready, incident-ready,
   legally authorized, financially authorized, or deployment-ready from this
   boundary.

## Validation

Run:

```powershell
python scripts/validate_foundation_operator_readiness_boundary.py
```

The validator checks that the operator-readiness witness:

1. keeps capacity verification, schedule readiness, skill readiness, team
   readiness, hiring readiness, delegation readiness, incident coverage,
   support coverage, legal-authority readiness, financial-authority readiness,
   private schedule recording, private health recording, and deployment
   disabled;
2. keeps every surface in `AwaitingEvidence`;
3. rejects URL, email, private path, private schedule, private health, team,
   hiring, delegation, support coverage, legal authority, or financial authority
   shaped values; and
4. rejects readiness-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare source-control safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| Prepare support readiness safely | [Foundation Support Readiness Boundary](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: capacity verification blocked, schedule-readiness claim blocked, skill-readiness claim blocked, team-readiness claim blocked, hiring-readiness claim blocked, delegation-readiness claim blocked, incident coverage blocked, support coverage blocked, legal-authority readiness blocked, financial-authority readiness blocked, private schedule recording blocked, private health recording blocked, deployment blocked
  Open issues: solo capacity evidence, pacing evidence, skill-gap evidence, learning-loop evidence, decision-authority evidence, escalation evidence, stop-rule evidence, and review-cadence evidence remain AwaitingEvidence
  Next action: run the operator-readiness boundary validator before any future operational-readiness claim
