# Capability Closure Runner

Purpose: define the repository-local process that turns the ranked capability
debt report into one selected closure lane, missing refs, next approval action,
and closure receipt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `mcoi/capability_closure/runner.py`,
`scripts/run_capability_debt_closure.py`,
`scripts/validate_capability_closure_runner.py`,
`examples/capability_debt_report.foundation.json`, and the four closure
schemas.
Invariants: closure runner artifacts are planning records only; they do not
grant live execution, connector mutation, repository mutation, PR creation,
merge authority, production readiness, or terminal closure.

## Architecture

The closure runner is the first systematic step after the capability debt
report:

```text
Capability debt report
-> deterministic lane selection
-> missing evidence refs
-> next approval action
-> closure receipt
-> stop before live execution
```

Default selection prefers the first approval-bound low-rehearsal lane already
identified in the debt report doctrine:

```text
email.send.with_approval
```

If that lane is unavailable, the runner falls back to highest severity, then
category, capability id, and debt id. This keeps selection deterministic.

## Outputs

The generated files are:

| Output | Meaning |
| --- | --- |
| `capability_closure_plan.json` | Selected capability, selected debt item, current gate, blocked effects, and next proof step. |
| `missing_evidence_refs.json` | Approval, evidence, rollback, replay, promotion, and live-action refs grouped by category. |
| `next_approval_action.json` | Approval gate ids, required receipts, required inputs, and proof validator command. |
| `closure_receipt.json` | Causal trace proving the runner stopped at `AwaitingEvidence` without live effects. |

Checked foundation examples use `.foundation.json` suffixes under `examples/`.

## Boundary

These fields must remain fixed:

```text
plan_is_not_execution_authority = true
refs_are_not_execution_authority = true
approval_action_is_not_execution_authority = true
closure_receipt_is_not_execution_authority = true
live_execution_enabled = false
closure_claim = not_closed
status = AwaitingEvidence
proof_state = Unknown
```

The closure receipt effect boundary must keep these false:

```text
capability_live_execution_performed
connector_mutation_performed
external_write_performed
target_repository_mutation_authorized
target_repository_file_write_performed
branch_push_performed
pull_request_created
merge_performed
production_claim_made
```

## Validation

Run:

```powershell
python scripts/run_capability_debt_closure.py --output-dir .change_assurance --json
python scripts/validate_capability_closure_runner.py --generated-names --plan .change_assurance/capability_closure_plan.json --missing-refs .change_assurance/missing_evidence_refs.json --next-approval .change_assurance/next_approval_action.json --receipt .change_assurance/closure_receipt.json --strict
python scripts/validate_capability_closure_runner.py --strict
python -m pytest tests/test_capability_closure_runner.py tests/test_validate_capability_closure_runner.py -q
```

## Change Deltas

Constructive deltas:

1. Adds one deterministic debt closure runner.
2. Adds four artifact contracts for closure planning.
3. Adds no-authority receipt checks before any live execution claim.
4. Adds focused tests for lane selection, fallback ranking, CLI output, and validator rejection paths.

Fracture deltas: none. The runner is additive and does not change capability
admission, live execution, connector writes, repository writes, PR creation, or
merge behavior.

## Status

Outcome: AwaitingEvidence until the selected approval and evidence refs exist.

Next action: use the closure artifacts to drive one approval-evidence proof
step, then proceed to the local developer workflow v1 proposal path.

STATUS:
  Completeness: 100%
  Invariants verified: read-only closure planning, explicit missing refs, approval-bound next action, no live execution
  Open issues: selected lane remains AwaitingEvidence by design
  Next action: validate generated closure artifacts and use them as the next proof step input
