# 35 - Compensation Assurance

## Purpose

Compensation assurance governs recovery actions after an original effect
reconciliation is unresolved. It prevents a system from claiming recovery merely
because a rollback or refund tool was invoked.

The layer answers: what original effect failed, what compensation is approved,
what recovery capability ran, what actual compensation effects were observed,
what evidence proves those effects, and whether the compensation itself
reconciled?

## Owned Artifacts

| Artifact | Role |
|---|---|
| `CompensationPlan` | Approved recovery plan bound to the original command and reconciliation |
| `CompensationAttempt` | Execution witness for one compensation dispatch |
| `CompensationOutcome` | Terminal verification and reconciliation result |
| `CompensationAssuranceGate` | Runtime bridge for planning, injected dispatch, observation, reconciliation, and graph anchoring |

## Admission Rule

A compensation plan may be created only when:

1. The original effect reconciliation is unresolved: `partial_match`,
   `mismatch`, or `unknown`.
2. The original reconciliation references the same command and effect plan as
   the original `EffectPlan`.
3. A case exists for the unresolved effect.
4. A compensation or rollback capability is declared.
5. Approval evidence is present.
6. Expected effects, forbidden effects, and required evidence are explicit.

Matched original reconciliation cannot create compensation.

## Runtime Rule

Compensation dispatch is injected into `CompensationAssuranceGate`. The gate does
not call providers directly. After dispatch, the returned `ExecutionResult` is
observed through effect assurance:

```text
CompensationPlan
  -> injected dispatch
  -> ExecutionResult.actual_effects
  -> observed effects
  -> verification
  -> compensation reconciliation
  -> CompensationOutcome
```

The compensation is successful only when the compensation reconciliation is
`MATCH`. Any partial, mismatched, or unknown compensation result remains
`requires_review` and keeps the case attached.

## Graph Projection

When an operational graph is attached, compensation assurance anchors:

| Node | Type |
|---|---|
| `command:{command_id}` | job |
| `compensation_plan:{compensation_plan_id}` | runbook |
| `compensation_attempt:{attempt_id}` | provider_action |
| `compensation_outcome:{outcome_id}` | verification |
| `approval:{approval_id}` | approval |
| `evidence:{evidence_ref}` | document |

Edges bind approval, plan, attempt, outcome, and evidence so recovery is
auditable as a causal chain.

## Hard Invariants

1. No compensation after matched original reconciliation.
2. No compensation without case and approval.
3. No compensation without expected effects and forbidden effects.
4. No successful compensation without observed actual effects.
5. No successful compensation without compensation reconciliation `MATCH`.
6. No compensation graph anchor without evidence references.
7. Provider invocation alone is never recovery proof.

## Relationship To Accepted Risk

Accepted risk and compensation are separate closure paths:

```text
unresolved original reconciliation
  -> compensation
     -> MATCH: compensated recovery is proven
     -> not MATCH: review remains open

unresolved original reconciliation
  -> accepted risk
     -> bounded owner-approved residual risk remains open until expiry/closure
```

Compensation changes reality to counter an unwanted effect. Accepted risk records
bounded tolerance of a known unresolved gap. Neither path may claim ordinary
success.
