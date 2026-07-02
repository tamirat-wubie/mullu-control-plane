# Safe Local Action Rehearsal

Purpose: define the proof-only rehearsal lane for local developer actions before
any real workspace mutation or external effect is allowed.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `mcoi/govern/safe_local_action_rehearsal/runner.py`,
`schemas/safe_local_action_rehearsal_receipt.schema.json`, and
`gateway/operator_workflow_dashboard.py`.
Invariants: rehearsal is not execution proof; post-execution evidence remains
required; live execution remains disabled.

## Capability

```text
govern.safe_local_action.rehearsal
```

## Rehearsed Scenarios

```text
simulate file write
simulate PR creation
simulate merge request
simulate rollback
simulate connector action
```

Each scenario is proof-only:

```text
proof_only: true
mutation_performed: false
external_effects_allowed: false
proof_limit: simulation_is_not_execution_proof
```

## Blocked Effects

```text
file_write
branch_push
pull_request_create
merge
rollback_execute
deploy
connector_call
external_write
live_execution
```

## Commands

Generate a rehearsal receipt:

```powershell
python scripts/run_safe_local_action_rehearsal.py --json
```

Validate the receipt:

```powershell
python scripts/validate_safe_local_action_rehearsal.py --json
```

Default receipt:

```text
.change_assurance/safe_local_action_rehearsal_receipt.json
```

## Boundary

This rehearsal can reduce uncertainty before approval, but it cannot close a
live action. Live closure still requires explicit approval plus observed
post-execution evidence and rollback or compensation evidence.
