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
-> Capability control system
```

It answers four operator questions:

1. What is unlocked?
2. What is blocked?
3. Why is it blocked?
4. What evidence is needed next?

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

## Verification

Run:

```powershell
python scripts/validate_capability_control_system.py
python -m pytest tests/test_validate_capability_control_system.py -q
python scripts/validate_schemas.py
```

STATUS:
  Completeness: 100%
  Invariants verified: read-only projection, L0-L9 levels, friction modes, lab boundary, safe/danger zones
  Open issues: none
  Next action: render the control-system registry and task cards in the browser-facing operator dashboard
