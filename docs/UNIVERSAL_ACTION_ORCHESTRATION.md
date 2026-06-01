# Universal Action Orchestration

Purpose: define the governed v1 action-shape contract for effect-bearing control-plane actions.
Governance scope: OCE action envelope completeness, RAG trace-to-receipt linkage, CDCV no-execution-by-claim causality, CQTE decidable admission shape, UWMA fixture witness anchoring, and PRS terminal closure state.
Dependencies: `schemas/universal_action_orchestration.schema.json`, `scripts/validate_universal_action_orchestration.py`, and examples in `examples/`.
Invariants: UAO v1 validates existence and shape only; it does not execute actions, dispatch workers, call external systems, send messages, move money, mutate schedules, or write memory.

## Architecture

UAO v1 hardens a core idea into repository law:

```text
passive doc -> schema contract -> example fixtures -> validator -> workspace preflight required gate
```

The v1 record is a non-executing Universal Action Envelope plus admission, trace, receipt, and closure references:

```text
UniversalActionOrchestration :=
  <action_envelope, decision, trace_ref, admission_receipt_ref,
   execution_receipt_ref, closure_state>
```

| Contract field | Purpose |
| --- | --- |
| `action_envelope` | Source, actor, tenant, intent, target, risk, requested time, approval, evidence, and capability references. |
| `decision` | Admission decision: `allow`, `block`, `defer`, `escalate`, or `simulate`. |
| `trace_ref` | Causal decision trace reference bound to the trace stage output. |
| `admission_receipt_ref` | Receipt reference proving admission was recorded. |
| `execution_receipt_ref` | Receipt reference proving execution only when execution is admitted; otherwise null. |
| `closure_state` | Terminal closure state mirrored from `closure.status`. |

## Algorithm

The validator applies these rules deterministically:

1. Every UAO example must have an `action_envelope`.
2. Every envelope must include `source`, `actor`, `tenant`, `intent`, `target`, `risk`, and `requested_at`.
3. Every decision must be one of `allow`, `block`, `defer`, `escalate`, or `simulate`.
4. Every effect-bearing action must include `trace_ref`, `admission_receipt_ref`, and `closure_state`.
5. Every admitted `allow` action must include an emitted `execution_receipt_ref`.
6. Every blocked, deferred, or escalated action must include a reason code.
7. No example may claim execution unless an execution receipt exists.
8. No raw private reasoning field may exist anywhere in the record.
9. No high-risk `allow` action may pass without approval, evidence, and capability references.
10. Every example must include `closure_state`.

The core invariant is:

```text
effect_bearing(action) -> trace_ref and admission_receipt_ref and closure_state
```

Invalid UAO is a preflight-blocking condition:

```text
not UAO_valid(action) -> preflight_fail
```

## Fixtures

The default validator set covers allowed, blocked, deferred, and simulated outcomes:

- `examples/universal_action_orchestration.allowed_status_publish.json`
- `examples/universal_action_orchestration.blocked_invoice_payment.json`
- `examples/uao/blocked_missing_approval.json`
- `examples/uao/deferred_stale_evidence.json`
- `examples/uao/simulated_low_risk_readonly.json`

## Verification

Run:

```powershell
python scripts/validate_universal_action_orchestration.py
python scripts/validate_universal_action_orchestration.py --json --receipt-path .tmp/uao-validation-receipt.json
python -m unittest discover -s tests -p "test_validate_universal_action_orchestration.py"
python scripts/run_workspace_governance_checks.py
```

The workspace preflight includes the validator, so UAO drift blocks repository closure.
The optional JSON receipt is read-only and records validity, check names, workspace-relative example path labels, error counts, and bounded errors for autonomous preflight consumers.
