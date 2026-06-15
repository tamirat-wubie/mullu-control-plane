# WorkerFailureReceipt Contract

Purpose: define the post-dispatch worker failure receipt contract for failed steps, partial effects, unknown effects, rollback obligations, recovery obligations, and non-terminal closure guards.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `schemas/worker_failure_receipt.schema.json`, `scripts/validate_worker_failure_receipt.py`, `examples/worker_failure_receipt.foundation.json`.
Invariants: worker failure cannot claim success; terminal closure remains false; partial or unknown effects require recovery evidence or an explicit blocker; rollback-required states require rollback refs; raw worker output and raw secrets are not stored; Mfidel atomicity is preserved.

## 1. Boundary

`WorkerFailureReceipt` is a non-terminal receipt emitted after a worker dispatch fails, times out, partially completes, or triggers a safety floor.

It may record:

```text
worker dispatch reference
tenant, actor, worker, lease, and command refs
failure state
failure class
effect status
completed and failed step refs
partial effect refs
rollback action refs
recovery action refs
blocked reason refs
governance guards
receipt envelope
```

It must not:

```text
claim worker success
claim terminal closure
renew execution authority
hide failed steps
store raw worker output
store raw secrets
erase partial or unknown effects
```

## 2. State Model

| Receipt State | Meaning | Required Behavior |
| --- | --- | --- |
| `FAILED_BEFORE_EXECUTION` | Dispatch was rejected or failed before effects. | `effect_status = no_effect_confirmed`; rollback is not required. |
| `PARTIAL_EXECUTION_RECORDED` | At least one step completed before failure. | Partial effects are recorded and recovery is required. |
| `TIMEOUT_WITH_UNKNOWN_EFFECT` | Worker timed out before effect verification. | Recovery is required and unknown effect handling is explicit. |
| `ROLLBACK_REQUIRED` | A failure left effects that require rollback. | Rollback refs and recovery requirement are mandatory. |
| `RECOVERY_REQUIRED` | The failure cannot close without a recovery path. | Recovery refs or blocked reason refs are mandatory. |
| `SAFE_HALT_RECORDED` | Safety floor halted execution. | Solver outcome is `SafeHalt`; closure remains non-terminal. |

## 3. No-Success Rule

```text
terminal_closure = false
success_claim_allowed = false
execution_authority_renewal_allowed = false
```

A worker failure receipt is evidence for repair, rollback, retry, or incident handoff. It is not a terminal certificate and cannot authorize a user-facing success claim.

## 4. Partial-Effect Rule

```text
partial_effect_recorded or effect_unknown
  requires recovery_required = true
  and recovery_action_refs or blocked_reason_refs is non-empty
```

If the system cannot prove that no effect occurred, the receipt preserves uncertainty and points to recovery or escalation evidence.

## 5. Rollback Rule

```text
rollback_required = true
  requires rollback_action_refs is non-empty
```

The receipt may declare rollback pending, but it cannot imply rollback has completed. A separate recovery, rollback, incident, or terminal-closure artifact must close the chain.

## 6. Foundation Example

`examples/worker_failure_receipt.foundation.json` records a read-only worker timeout in Foundation Mode with one completed step, one failed step, one partial local effect, one rollback action, one recovery action, and one blocker.

The example proves:

```text
receipt_state = PARTIAL_EXECUTION_RECORDED
effect_status = partial_effect_recorded
rollback_required = true
recovery_required = true
terminal_closure = false
success_claim_allowed = false
raw_secret_material_included = false
```

## 7. Validation

Run:

```powershell
python scripts/validate_worker_failure_receipt.py
python -m pytest tests/test_validate_worker_failure_receipt.py -q
python scripts/validate_schemas.py
python scripts/validate_protocol_manifest.py
```

STATUS:
  Completeness: 100%
  Invariants verified: no success claim, no terminal closure, failed-step evidence, partial-effect recovery, rollback refs, raw secret rejection, raw output rejection, Mfidel atomicity
  Open issues: no live worker runtime is registered by this contract
  Next action: bind WorkerFailureReceipt emission to the first read-only worker path
