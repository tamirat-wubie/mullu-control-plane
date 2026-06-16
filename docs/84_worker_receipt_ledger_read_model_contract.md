# Worker Receipt Ledger Read Model Contract

Purpose: define the read-only operator projection over worker receipt chains.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `schemas/worker_receipt_ledger_read_model.schema.json`, `examples/worker_receipt_ledger_read_model.foundation.json`, `scripts/validate_worker_receipt_ledger_read_model.py`, `tests/test_validate_worker_receipt_ledger_read_model.py`, `schemas/worker_failure_receipt.schema.json`, `schemas/read_only_worker_runtime_receipt_candidate.schema.json`, `schemas/connector_action_promotion_gate.schema.json`, `docs/79_worker_failure_receipt_contract.md`, `docs/80_read_only_worker_binding_contract.md`, `docs/83_connector_action_promotion_gate_contract.md`.
Invariants: the read model does not read a live receipt store; it does not dispatch workers; it does not emit runtime receipts; it does not call connectors; it does not write files; it does not expose raw payloads or secrets; it does not permit terminal closure or success claims; Mfidel atomicity is preserved.

## 1. Boundary

`WorkerReceiptLedgerReadModel` is an operator projection, not a receipt store and not a worker runtime.

It aggregates bounded references across:

```text
Temporal scheduler receipts
Distributed lease claim and execution receipts
Scheduler worker runtime receipt handoffs
Scheduler worker runtime receipt emitter dry-runs
Read-only worker binding and runtime receipt candidates
Worker failure receipts
Connector action promotion gates
```

The Foundation example intentionally uses `FOUNDATION_FIXTURE_PROJECTION` and keeps `source_receipt_store_live_read_performed=false`.

## 2. Authority Denials

Foundation Mode denies:

```text
live_receipt_store_read_allowed
worker_dispatch_allowed
runtime_receipt_emission_allowed
connector_call_allowed
external_write_allowed
secret_access_allowed
filesystem_write_allowed
deployment_mutation_allowed
terminal_closure_allowed
success_claim_allowed
raw_payload_included
raw_secret_material_included
```

The read model can show blocked and recovery-required chains, but those states never become closure authority.

## 3. Summary Integrity

The validator recomputes:

```text
chain_count
blocked_chain_count
recovery_required_count
terminal_closure_allowed_count
success_claim_allowed_count
blocked_reason_ref_count
recovery_obligation_ref_count
receipt_ref_count
evidence_ref_count
```

Any mismatch between the projected chains and summary fields is rejected.

## 4. Validation

Run:

```powershell
python scripts/validate_worker_receipt_ledger_read_model.py
python -m pytest tests/test_validate_worker_receipt_ledger_read_model.py -q
python scripts/validate_protocol_manifest.py
python scripts/proof_coverage_matrix.py --check
python scripts/validate_sdlc_artifact.py
python scripts/validate_sdlc_security_review.py --review examples/sdlc/security_review_worker_receipt_ledger_read_model_20260616.json --strict
```

## 5. Outcome

`SolvedVerified` for the schema, Foundation example, validator, proof coverage, and SDLC evidence.

Live receipt-store reads, worker dispatch, runtime receipt emission, connector calls, and terminal closure remain `AwaitingEvidence`.
