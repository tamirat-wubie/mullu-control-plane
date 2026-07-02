# Operator Workflow Dashboard

Purpose: define the projection-only operator workflow dashboard that unifies
local Developer Workflow status, local receipt summary, safe-local action,
rollback, and approval-boundary fields.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `gateway/operator_workflow_dashboard.py`,
`schemas/operator_workflow_dashboard_read_model.schema.json`, and the existing
local Developer Workflow receipt, status, and safe-local action projections.
Invariants: the dashboard is read-only, projection-only, and grants no external
execution, PR creation, branch push, merge, deployment, connector, email,
money, or production-write authority.

## Architecture

The dashboard is a single operator read model:

```text
local workflow receipt projection
  -> workflow status projection
  -> safe local action projection
  -> local workflow closure packet projection
  -> safe local action rehearsal receipt projection
  -> causal repair receipt projection
  -> readiness lane projection
  -> capability promotion ladder filters
  -> operator workflow dashboard row
```

It does not create a new workflow runtime. It composes already-governed
projection artifacts into one bounded dashboard row.

## Dashboard Fields

Each row exposes:

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
Promotion filter
Readiness lane
```

The default generated row represents `Mullu Developer Workflow v1`.

The readiness lane is a compact no-effect routing summary. It reports:

```text
lane status
proof state
operator outcome
primary blocker
current gate id
next action
required evidence refs
linked receipt refs
```

It is not execution authority. The schema requires
`readiness_is_not_execution_authority=true`,
`execution_authority_granted=false`, `live_execution_enabled=false`, and
`external_effects_allowed=false`.

## Next-Action Packet

The dashboard readiness lane can be projected into a compact next-action
handoff packet:

```text
operator workflow dashboard
  -> readiness lane
  -> operator workflow next-action packet
```

The packet carries the current lane status, proof state, operator outcome,
primary blocker, current gate, required evidence refs, linked receipt flags,
approval display state, and blocked effects. It is still projection-only and
does not perform approval, create files, push branches, create PRs, merge,
deploy, call connectors, or grant live execution.

## Promotion Filters

The dashboard also exposes read-only promotion filters for the canonical
capability ladder:

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

These filters help the operator view capabilities by current promotion level.
They do not authorize execution, PR creation, branch push, merge, connector
use, or live writes. The dashboard schema requires
`filter_is_not_execution_authority=true` and `live_execution_enabled=false`.

## Execution Boundary

The dashboard remains in `local_lab` mode.

Blocked effects:

```text
create_pr
push_branch
merge
deploy
connector_call
send_email
move_money
write_production_data
```

Approval state is displayed as evidence. Approval is not performed by this
dashboard.

Rollback is displayed as a required or not-required status. Rollback is not
executed by this dashboard.

## Commands

Generate the dashboard artifact:

```powershell
python gateway/operator_workflow_dashboard.py --json
```

Generate the next-action handoff packet from a dashboard artifact:

```powershell
python scripts/build_operator_workflow_next_action_packet.py --dashboard .change_assurance/operator_workflow_dashboard.read_model.generated.json --json
```

Default output:

```text
.change_assurance/operator_workflow_dashboard.read_model.generated.json
.change_assurance/operator_workflow_next_action_packet.generated.json
```

Run focused validation:

```powershell
python -m pytest tests/test_build_operator_workflow_next_action_packet.py -q
python -m pytest tests/test_operator_workflow_dashboard.py -q
python scripts/validate_protocol_manifest.py
python scripts/validate_schemas.py
```

## Status

Outcome: `AwaitingEvidence` until the current gate's missing evidence is
provided by local workflow receipts.

The dashboard can report `preflight_ready`, but it still does not grant live
execution authority.
