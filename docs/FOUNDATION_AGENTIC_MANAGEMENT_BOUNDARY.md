<!--
Purpose: define the Foundation Mode agentic-management boundary before any autonomous management, task execution, delegation, scheduling, resource-allocation, approval-bypass, customer, money-movement, publication, or deployment claim.
Governance scope: goal-intake questions, plan-decomposition questions, delegation questions, schedule/queue questions, resource/budget questions, priority/tradeoff questions, escalation/approval questions, progress/receipt questions, rollback/recovery questions, performance-review questions, customer blocking, money-movement blocking, publication blocking, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_CAPABILITY_ROADMAP_BOUNDARY.md, docs/FOUNDATION_OPERATIONS_RUNBOOK_BOUNDARY.md, examples/foundation_agentic_management_witness.awaiting_evidence.json, scripts/validate_foundation_agentic_management_boundary.py.
Invariants: no autonomous management authority, no task execution authority, no delegation activation, no scheduling commitment, no resource allocation approval, no budget commitment, no final priority claim, no approval bypass, no live monitoring claim, no operator replacement claim, no customer commitment, no money movement, no external publication, and no deployment claim.
-->

# Foundation Agentic Management Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** agentic-management preparation means drafting local control
> questions for goals, plans, delegation, queues, resources, approvals,
> receipts, rollback, and review. It does not mean the system can manage work
> autonomously, execute tasks, schedule commitments, allocate resources, bypass
> approvals, replace an operator, commit to customers, move money, publish, or
> deploy.

Witness packet: [`../examples/foundation_agentic_management_witness.awaiting_evidence.json`](../examples/foundation_agentic_management_witness.awaiting_evidence.json)

Rule: Agentic-management preparation is a local planning boundary, not an autonomous-management, task-execution, delegation, scheduling, resource-allocation, approval-bypass, customer, money-movement, publication, or deployment certificate.

No autonomous management authority, task execution authority, delegation
activation, scheduling commitment, resource allocation approval, budget
commitment, final priority claim, approval bypass, live monitoring claim,
operator replacement claim, customer commitment, money movement, external
publication, or deployment readiness is permitted by this boundary.

## What This Boundary Solves

Foundation Mode needs management controls for autonomous work without creating
false authority. This boundary covers management, planning, delegation,
scheduling, budget, escalation, progress, rollback, and performance questions
while keeping all effect-bearing authority blocked.

This boundary separates local management design from execution authority:

1. Goals can be decomposed into local questions without authorizing task execution.
2. Delegation and queue surfaces can be drafted without assigning workers or schedules.
3. Resource and budget questions can be prepared without approving allocation or spend.
4. Escalation and approval paths can be named without bypassing operator review.
5. Progress, rollback, and performance review questions can be drafted without claiming live monitoring or operational readiness.

## Current State

```text
agentic_management_boundary_state=AwaitingEvidence
agentic_management_claimed=false
autonomous_management_authority_claimed=false
task_execution_authority_allowed=false
delegation_activation_allowed=false
scheduling_commitment_allowed=false
resource_allocation_approved=false
budget_commitment_allowed=false
priority_final_claimed=false
approval_bypass_allowed=false
live_monitoring_claimed=false
operator_replacement_claimed=false
customer_commitment_allowed=false
money_movement_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Preparation Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Goal-intake questions | Draft how goals enter a governed work queue. | Do not claim autonomous management authority. |
| Plan-decomposition questions | Draft how work could be split into bounded steps. | Do not authorize task execution. |
| Delegation questions | Draft worker, skill, and capability routing questions. | Do not activate delegation or child work. |
| Schedule/queue questions | Draft queue order, wait states, and stop rules. | Do not promise schedules, deadlines, or delivery dates. |
| Resource/budget questions | Draft resource needs and budget guard questions. | Do not allocate resources or commit budgets. |
| Priority/tradeoff questions | Draft tradeoff and tension criteria. | Do not claim final priority order. |
| Escalation/approval questions | Draft approval gates and escalation paths. | Do not bypass operator or governance approval. |
| Progress/receipt questions | Draft receipt and progress-report fields. | Do not claim live monitoring or external reporting. |
| Rollback/recovery questions | Draft rollback and compensation questions. | Do not claim recovery readiness. |
| Performance-review questions | Draft review and improvement questions. | Do not claim operator replacement, customer commitment, publication, money movement, or deployment. |

## Operator Procedure

1. Keep agentic-management preparation as local questions and evidence gates.
2. Do not assign real workers, schedules, budgets, customers, provider accounts,
   credentials, endpoints, or private paths in the witness.
3. Treat task execution, delegation, scheduling, allocation, approval bypass,
   customer commitment, money movement, publication, and deployment as blocked.
4. Route any future promotion through a named evidence witness and `Phi_gov`
   review before running effect-bearing work.
5. Re-run the validator after any management-control wording change.

## Validation

```powershell
python scripts/validate_foundation_agentic_management_boundary.py
```

STATUS:
  Completeness: 100%
  Invariants verified: autonomous management authority blocked, task execution authority blocked, delegation activation blocked, scheduling commitment blocked, resource allocation approval blocked, budget commitment blocked, final priority claim blocked, approval bypass blocked, live monitoring claim blocked, operator replacement claim blocked, customer commitment blocked, money movement blocked, external publication blocked, deployment blocked
  Open issues: goal-intake evidence, plan-decomposition evidence, delegation evidence, schedule/queue evidence, resource/budget evidence, priority/tradeoff evidence, escalation/approval evidence, progress/receipt evidence, rollback/recovery evidence, and performance-review evidence remain AwaitingEvidence
  Next action: run the agentic-management validator before any future management authority, task execution, delegation, scheduling, allocation, approval-bypass, customer, money, publication, or deployment claim
