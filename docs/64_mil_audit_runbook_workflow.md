# MIL Audit Runbook Workflow

Purpose: Operator workflow for turning a verified MIL audit record into a replay-backed procedural runbook.
Governance scope: MIL audit records, persisted trace spines, persisted replay records, learning admission, and durable runbook storage.
Dependencies: `MILAuditStore`, `TraceStore`, `ReplayStore`, `RunbookStore`, `RunbookLibrary`, `PersistedReplayValidator`.
Invariants:
- MIL audit records must be anchored in the MIL audit hash chain.
- Trace spine persistence must happen before replay persistence.
- Runbook admission must validate the persisted replay with a matching state hash and environment digest.
- Durable runbook storage is optional but required for cross-session operator inspection.
- Stored runbooks must preserve execution, verification, replay, trace, and learning admission provenance.

## Architecture

```text
MIL audit record
  -> hash-chain validation
  -> reconstructed trace spine
  -> TraceStore persistence
  -> ReplayStore persistence
  -> persisted replay validation
  -> LearningAdmissionDecision(status=admit)
  -> RunbookLibrary admission
  -> optional RunbookStore persistence
```

The MIL audit path upgrades a completed governed execution from episodic proof into procedural memory. The admitted runbook is not inferred from raw conversation or loose planning. It is derived from a hash-anchored MIL record and a replayable trace bundle.

## CLI Workflow

Validate the machine-readable operator checklist before executing the workflow:

```powershell
python scripts\validate_mil_audit_runbook_operator_checklist.py --checklist examples\mil_audit_runbook_operator_checklist.json --json
```

Set explicit store paths. Do not rely on implicit process state.

```powershell
$MIL_AUDIT_STORE = ".mullu\mil-audit"
$TRACE_STORE = ".mullu\mil-traces"
$REPLAY_STORE = ".mullu\mil-replays"
$RUNBOOK_STORE = ".mullu\mil-runbooks"
$RECORD_ID = "mil-audit-record-example"
```

Inspect the audit record:

```powershell
mcoi mil-audit get --store $MIL_AUDIT_STORE --json $RECORD_ID
```

Build an observation-only replay projection:

```powershell
mcoi mil-audit replay --store $MIL_AUDIT_STORE --json $RECORD_ID
```

Persist the trace spine, persist the replay record, admit the runbook, and store the runbook entry:

```powershell
mcoi mil-audit admit-runbook `
  --store $MIL_AUDIT_STORE `
  --trace-store $TRACE_STORE `
  --replay-store $REPLAY_STORE `
  --runbook-store $RUNBOOK_STORE `
  --runbook-id runbook-mil-example-001 `
  --name "MIL Governed Example Runbook" `
  --description "Replay-backed runbook admitted from a verified MIL audit record." `
  --json `
  $RECORD_ID
```

Fetch one persisted MIL-derived runbook:

```powershell
mcoi mil-audit runbook-get `
  --runbook-store $RUNBOOK_STORE `
  --json `
  runbook-mil-example-001
```

List persisted MIL-derived runbooks:

```powershell
mcoi mil-audit runbook-list `
  --runbook-store $RUNBOOK_STORE `
  --json
```

## HTTP Workflow

Admit and optionally persist a runbook:

```http
POST /api/v1/mil-audit/admit-runbook
Content-Type: application/json

{
  "record_id": "mil-audit-record-example",
  "mil_audit_store_path": ".mullu/mil-audit",
  "trace_store_path": ".mullu/mil-traces",
  "replay_store_path": ".mullu/mil-replays",
  "runbook_store_path": ".mullu/mil-runbooks",
  "runbook_id": "runbook-mil-example-001",
  "name": "MIL Governed Example Runbook",
  "description": "Replay-backed runbook admitted from a verified MIL audit record."
}
```

List persisted runbooks:

```http
GET /api/v1/mil-audit/runbooks?runbook_store_path=.mullu/mil-runbooks
```

Fetch one persisted runbook:

```http
GET /api/v1/mil-audit/runbooks/runbook-mil-example-001?runbook_store_path=.mullu/mil-runbooks
```

## Admission Gates

| Gate | Required witness | Failure mode |
|---|---|---|
| MIL audit anchor | MIL audit hash-chain entry | record is rejected as unanchored |
| Trace persistence | six-entry reconstructed trace spine | replay validation cannot proceed |
| Replay persistence | `ReplayStore` record | runbook admission rejects replay |
| Replay validation | `ReplayVerdict.MATCH` | runbook admission returns rejected |
| Learning admission | `LearningAdmissionDecision(status=admit)` | procedural memory entry is rejected |
| Durable storage | `RunbookStore` entry | cross-session inspection is unavailable |

## Operator Checks

The machine-readable checklist is `examples/mil_audit_runbook_operator_checklist.json`.
It binds each command to required evidence and is validated by
`scripts/validate_mil_audit_runbook_operator_checklist.py`.

After admission, verify the response contains:

```text
operation: admit-runbook
runbook_status: admitted
runbook_persisted: true
provenance.execution_id
provenance.verification_id
provenance.replay_id
provenance.trace_id
provenance.learning_admission_id
```

Then verify the stored runbook can be read back:

```powershell
mcoi mil-audit runbook-get --runbook-store $RUNBOOK_STORE --json runbook-mil-example-001
```

The returned `provenance.verification_id` must equal the source MIL audit `record_id`.

## Failure Handling

| Symptom | Likely cause | Operator action |
|---|---|---|
| `MIL audit store unavailable` | audit store path does not exist | provide the explicit local audit store path |
| `MIL audit runbook admission rejected` | unanchored record, replay mismatch, collision, or invalid request | inspect the MIL audit record and replay bundle |
| `MIL audit runbook unavailable` | requested runbook id is absent from `RunbookStore` | list runbooks, then retry with a stored id |
| `runbook_persisted: false` | no `RunbookStore` path was provided | rerun admission with `--runbook-store` or `runbook_store_path` |

## Status Block

```text
STATUS:
  Completeness: 100%
  Invariants verified: [MIL audit anchor, trace-before-replay persistence, replay validation, learning admission, durable runbook readback]
  Open issues: none
  Next action: execute the CLI or HTTP workflow with a real MIL audit record
```
