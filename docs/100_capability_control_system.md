# Capability Control System

Purpose: define the master operator read model that organizes capability
registry state, unlock levels, friction modes, safe zones, and dashboard tasks.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `capabilities/*/capability_pack.json`,
`docs/74_capability_passports.md`, `docs/76_capability_passport_dashboard.md`,
`mcoi/mcoi_runtime/app/capability_control_system.py`, and
`schemas/capability_control_system.schema.json`.
Invariants: the control system is read-only, does not grant execution
authority, and keeps real-world effects approval-bound.

## Architecture

The control system is the reusable surface above individual gates:

```text
Capability packs
-> Capability passports
-> Capability passport dashboard
-> Capability debt report
-> Capability closure runner
-> Capability control system
```

It answers five operator questions:

1. What is unlocked?
2. What is blocked?
3. Why is it blocked?
4. What evidence is needed next?
5. Which one closure lane should be handled first?

## Unlock Levels

The canonical L0-L9 ladder remains defined in
`mcoi/mcoi_runtime/core/capability_unlock_ladder.py`.

| Level | Meaning |
| --- | --- |
| L0 | Read-only inspection and summary. |
| L1 | Local demo or dry-run. |
| L2 | Prepare diffs, schemas, tests, docs, and packets. |
| L3 | Write files inside a controlled workspace or branch. |
| L4 | Run bounded tests and capture receipts. |
| L5 | Prepare PR evidence; opening a PR remains approval-bound. |
| L6 | Record human approval or rejection. |
| L7 | Live connector read probe. |
| L8 | Approved live connector write. |
| L9 | Customer-ready product operation with production witnesses. |

## Friction Modes

| Mode | Boundary | Behavior |
| --- | --- | --- |
| Strict | real world | Approval before sensitive or external effects. |
| Balanced | lab | Approval before risky or external actions. |
| Fast | lab | Auto-admit reversible local-lab work with receipts. |

Fast Mode is intentionally bounded. It can reduce local development friction
for docs, tests, examples, README updates, schemas, validators, and local demo
files. It cannot send email, move money, deploy, merge to main, touch secrets,
delete files, or write production data.

## Dashboard Task Shape

Operator task cards use this compact shape:

```text
Task: Build demo
Status: blocked
Reason: required evidence or hard governance condition is missing
Next unlock: bind rollback or recovery evidence
Risk: medium
Action needed: approve bounded lab action or keep prepare-only
```

This is a product surface, not an execution surface. Execution authority still
belongs to capability packs, UAO admission, approval policy, evidence
verification, receipts, rollback policy, and terminal closure.

## Workflow Dashboard Surface

`docs/104_operator_workflow_dashboard.md` defines the unified local workflow
dashboard row. It composes the local Developer Workflow receipt projection,
workflow status projection, and safe-local action projection into:

```text
Task
Status
Current gate
Missing evidence
Next action
Risk
Receipts
Rollback
Approval needed
```

The implementation is `gateway/operator_workflow_dashboard.py`.

## Safe Local Action Rehearsal

`docs/105_safe_local_action_rehearsal.md` defines
`govern.safe_local_action.rehearsal`. It rehearses file write, PR creation,
merge request, rollback, and connector action scenarios without performing any
of them.

The rehearsal receipt explicitly preserves this rule:

```text
simulation is not execution proof
post-execution evidence remains required
```

## Causal Repair Service

`docs/106_causal_repair_service.md` defines
`govern.causal_repair.service`. It classifies failed patch plan, failed test,
stale evidence, missing approval, impossible rollback, CI failure, and unsafe
browser evidence cases into cause class, effect class, reversibility class,
repair strategy, missing proof refs, and next repair proof action.

The service receipt explicitly preserves this rule:

```text
repair classification is not repair execution proof
rollback and compensation remain blocked until evidence and authority exist
```

## Capability Promotion Ladder

`docs/74_capability_passports.md` now exposes the L0-L9 promotion ladder on
every capability passport. The passport keeps `current_unlock_level` for C0-C7
evidence maturity and adds `current_promotion_level` for the product-facing
authority boundary:

```text
L0 read-only
L1 draft-only
L2 proposal-only
L3 sandbox-write
L4 test-run
L5 PR-preview
L6 PR-create with approval
L7 merge-request with approval
L8 live connector read
L9 live connector write
```

## Verification

Run:

```powershell
python scripts/validate_capability_control_system.py
python scripts/validate_capability_closure_runner.py --strict
python gateway/operator_workflow_dashboard.py --json
python scripts/run_safe_local_action_rehearsal.py --json
python scripts/validate_safe_local_action_rehearsal.py --json
python scripts/run_causal_repair_service.py --json
python scripts/validate_causal_repair_service_receipt.py --json
python scripts/validate_capability_passports.py --json
python -m pytest tests/test_validate_capability_passports.py -q
python -m pytest tests/test_operator_workflow_dashboard.py -q
python -m pytest tests/test_safe_local_action_rehearsal.py -q
python -m pytest tests/test_causal_repair_service.py -q
python -m pytest tests/test_validate_capability_control_system.py -q
python scripts/validate_schemas.py
```

STATUS:
  Completeness: 100%
  Invariants verified: read-only projection, L0-L9 levels, friction modes, lab boundary, safe/danger zones, closure runner no-authority boundary, workflow dashboard no-effect boundary, safe local action rehearsal no-effect boundary, causal repair service no-execution boundary, passport-visible promotion ladder
  Open issues: none
  Next action: produce fresh Linux/rootless-Docker browser sandbox evidence or bind promotion ladder into operator dashboard filters
