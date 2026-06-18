# Connector Action Promotion Gate Contract

Purpose: define the non-executing gate that decides whether a connector action may move beyond plan-only status.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `schemas/connector_action_promotion_gate.schema.json`, `examples/connector_action_promotion_gate.foundation.json`, `scripts/validate_connector_action_promotion_gate.py`, `tests/test_validate_connector_action_promotion_gate.py`, `schemas/connector_descriptor.schema.json`, `schemas/connector_result.schema.json`, `schemas/universal_action_orchestration.schema.json`, `schemas/connector_self_healing_receipt.schema.json`, `schemas/worker_failure_receipt.schema.json`, `docs/10_external_integration_plane.md`.
Invariants: connector promotion is not execution; live connector calls remain denied in Foundation Mode; secret access remains denied; runtime dispatch remains denied; deployment mutation remains denied; terminal closure remains denied; Mfidel atomicity is preserved.

## 1. Boundary

`ConnectorActionPromotionGate` is a gate receipt, not a connector invocation.

It binds:

```text
ConnectorDescriptor
ConnectorResult
Universal Action Orchestration ref
Phi_gov authorization status
operator approval status
secret-access receipt status
connector-worker execution receipt status
rollback and recovery evidence status
```

The Foundation example intentionally returns:

```text
decision = PROMOTION_BLOCKED_AWAITING_LIVE_EVIDENCE
promotion_allowed = false
live_connector_call_allowed = false
secret_access_allowed = false
runtime_dispatch_allowed = false
terminal_closure_allowed = false
```

## 2. Required Evidence

A connector action cannot be promoted until all required evidence refs are present:

```text
evidence://connector-action/uao-admission
evidence://connector-action/phi-gov-authorization
evidence://connector-action/operator-approval
evidence://connector-action/credential-scope-live-bound
evidence://connector-action/secret-access-receipt
evidence://connector-action/connector-worker-execution-receipt
evidence://connector-action/rollback-recovery-receipt
```

Missing evidence is recorded as blocked reason refs. Missing evidence never silently degrades into live execution.

## 3. Source Binding

The gate validates the checked-in connector compatibility fixtures:

```text
integration/contracts_compat/fixtures/connector_descriptor.json
integration/contracts_compat/fixtures/connector_result.json
```

The validator verifies that connector id, effect class, trust class, credential scope, enabled state, and result connector id remain aligned. A mismatch blocks the gate.

## 4. Authority Denials

Foundation Mode denies:

```text
promotion_allowed
live_connector_call_allowed
external_write_allowed
secret_access_allowed
runtime_dispatch_allowed
deployment_mutation_allowed
terminal_closure_allowed
success_claim_allowed
raw_secret_material_included
```

Future live promotion requires a separate proof thread. This contract only defines the admission gate and rejection evidence.

## 5. Validation

Run:

```powershell
python scripts/validate_connector_action_promotion_gate.py
python -m pytest tests/test_validate_connector_action_promotion_gate.py -q
python scripts/validate_protocol_manifest.py
python scripts/proof_coverage_matrix.py --check
python scripts/validate_sdlc_artifact.py
```

## 6. Outcome

`SolvedVerified` for the schema, example, validator, proof coverage, and SDLC evidence.

Live connector execution remains `AwaitingEvidence`.
