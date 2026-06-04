<!--
Purpose: define the Foundation Mode solo daily loop boundary for cautious one-person progression without private schedule recording, productivity claims, external action, or deployment claims.
Governance scope: solo-operator daily triage, one-task selection, prerequisite alignment, local evidence capture, validation checkpoints, stop conditions, handoff notes, carryover notes, private-value exclusion, and external-action blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md, docs/FOUNDATION_NEXT_ACTION_BOUNDARY.md, examples/foundation_solo_daily_loop_witness.awaiting_evidence.json, scripts/validate_foundation_solo_daily_loop_boundary.py.
Invariants: no daily productivity readiness claim, no schedule-readiness claim, no private calendar recording, no private health tracking, no task-completion guarantee, no team-coverage claim, no support-coverage claim, no roadmap commitment, no deadline promise, no external action, no spending, no legal/business action, no secret use, no credential use, no source-control publication, and no deployment claim.
-->

# Foundation Solo Daily Loop Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** solo daily loop preparation means each working session can
> choose one local-safe task, check constraints, capture evidence, validate, and
> leave a handoff note. It does not prove productivity, verify a schedule,
> record a private calendar, track health, guarantee completion, create team or
> support coverage, commit to a roadmap, promise deadlines, spend money, take
> legal/business action, use secrets or credentials, publish source control, or
> deploy anything.

Witness packet: [`../examples/foundation_solo_daily_loop_witness.awaiting_evidence.json`](../examples/foundation_solo_daily_loop_witness.awaiting_evidence.json)

Rule: Solo daily loop preparation is a public-safe local planning boundary, not
permission to record private schedule details or claim operational readiness.

No daily productivity readiness, schedule-readiness claim, private calendar
recording, private health tracking, task-completion guarantee, team coverage,
support coverage, roadmap commitment, deadline promise, external action,
spending, legal/business action, secret use, credential use, source-control
publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

Foundation Mode needs a repeatable shape for one person who is preparing
carefully. Without a daily loop, `continue` work can drift into too many tasks,
private planning details, or premature readiness claims.

This boundary keeps each session small:

1. Select one local-safe task from the prerequisite ledger.
2. Check whether that task depends on money, legal review, customers, secrets,
   credentials, external accounts, publication, source-control publication, or
   deployment.
3. If it does, keep the blocked part in `AwaitingEvidence` and choose a smaller
   local preparation step.
4. Capture only public-safe evidence references.
5. Run the focused validator and, when needed, the governance preflight receipt.
6. Stop with a short handoff and a bounded carryover note.

This is preparation only. It does not create a schedule, deadline, support
promise, team process, deployment path, or business/legal authority.

## Current State

```text
solo_daily_loop_boundary_state=AwaitingEvidence
daily_productivity_readiness_claimed=false
schedule_readiness_claimed=false
private_calendar_recording_allowed=false
private_health_tracking_allowed=false
task_completion_guaranteed=false
team_coverage_claimed=false
support_coverage_claimed=false
roadmap_commitment_claimed=false
deadline_promise_claimed=false
external_action_allowed=false
spending_allowed=false
legal_business_action_allowed=false
secret_use_allowed=false
credential_use_allowed=false
source_control_publication_allowed=false
deployment_allowed=false
```

## Solo Daily Loop Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Session intake | Name the current local goal and current repository posture. | Do not record private schedule or private health details. |
| One-task selection | Pick one local-safe prerequisite or one narrow repair. | Do not expand into broad roadmap work. |
| Prerequisite alignment | Map the task to the Foundation prerequisite ledger. | Do not bypass unknown hard constraints. |
| Risk and stop check | Identify stop conditions before editing. | Do not continue across validation failure, private data, money, legal, customer, or deployment boundaries. |
| Local evidence capture | Name the public-safe files, validators, and receipts that can prove the step. | Do not record secrets, credentials, customer data, account values, or private paths. |
| Validation checkpoint | Run focused validation before making a broader claim. | Do not claim readiness from intent or partial evidence. |
| Handoff note | Summarize changed surfaces and remaining `AwaitingEvidence`. | Do not claim customer support, team coverage, or deployment readiness. |
| Carryover note | Leave one next local-safe candidate. | Do not promise dates, deadlines, or roadmap commitments. |

## Operator Procedure

1. Start each working session from [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md).
2. Pick one local-safe prerequisite, not a bundle.
3. Check stop conditions before any file edit.
4. Keep all evidence public-safe and repository-local.
5. Run focused validators and targeted tests.
6. Run the workspace governance preflight receipt when governed surfaces change.
7. Stop with a handoff that separates what passed from what remains
   `AwaitingEvidence`.

## Validation

Run:

```powershell
python scripts/validate_foundation_solo_daily_loop_boundary.py
```

The validator checks that the solo daily loop witness:

1. keeps productivity readiness, schedule readiness, private calendar
   recording, private health tracking, task-completion guarantees, team
   coverage, support coverage, roadmap commitments, deadline promises,
   external action, spending, legal/business action, secret use, credential use,
   source-control publication, and deployment blocked;
2. keeps every loop surface in `AwaitingEvidence`;
3. rejects URL, email, private path, private schedule, private health, customer,
   provider, account, secret, credential, deployment, spending, legal,
   source-control publication, roadmap, or deadline shaped values; and
4. rejects promotion phrases that imply productivity, schedule, support, team,
   completion, publication, or deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| Pick a prerequisite row | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare operator readiness safely | [Foundation Operator Readiness Boundary](FOUNDATION_OPERATOR_READINESS_BOUNDARY.md) |
| Choose one next local action | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |
| Record test evidence without readiness claims | [Foundation Test Evidence Boundary](FOUNDATION_TEST_EVIDENCE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: productivity readiness blocked, schedule readiness blocked, private calendar recording blocked, private health tracking blocked, task-completion guarantee blocked, team coverage blocked, support coverage blocked, roadmap commitment blocked, deadline promise blocked, external action blocked, spending blocked, legal/business action blocked, secret use blocked, credential use blocked, source-control publication blocked, deployment blocked
  Open issues: session-intake evidence, one-task-selection evidence, prerequisite-alignment evidence, risk-stop evidence, local-evidence evidence, validation-checkpoint evidence, handoff-note evidence, and carryover-note evidence remain AwaitingEvidence
  Next action: run the solo daily loop validator before relying on daily-loop planning as evidence
