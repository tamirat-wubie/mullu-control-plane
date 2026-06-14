# ReadOnlyWorkerBinding Contract

Purpose: select the first Foundation Mode read-only worker path and bind its authority, lease preflight, rehearsal receipt, receipt-viewer projection, failure receipt, verification, rollback, and recovery obligations without registering a live worker.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `schemas/read_only_worker_binding.schema.json`, `schemas/read_only_worker_lease_preflight.schema.json`, `schemas/read_only_worker_rehearsal_receipt.schema.json`, `scripts/validate_read_only_worker_binding.py`, `scripts/validate_read_only_worker_lease_preflight.py`, `scripts/validate_read_only_worker_rehearsal_receipt.py`, `examples/read_only_worker_binding.foundation.json`, `examples/read_only_worker_lease_preflight.foundation.json`, `examples/read_only_worker_rehearsal_receipt.foundation.json`, `schemas/worker_mesh.schema.json`, `schemas/worker_failure_receipt.schema.json`, `schemas/temporal_lease_window_receipt.schema.json`.
Invariants: selected worker path is `read_only_repo_inspection`; runtime dispatch is denied; temporal lease preflight is required before any later dispatch admission; local rehearsal evidence is dry-run only; console receipt projection is read-only; external network, secrets, filesystem writes, connector authority, terminal closure, success claims, and raw output retention are denied; WorkerFailureReceipt remains mandatory for failed dispatch evidence; Mfidel atomicity is preserved.

## 1. Boundary

`ReadOnlyWorkerBinding` is a Foundation Mode contract, not a runtime registration.

It selects:

```text
selected_worker_path = read_only_repo_inspection
worker_id = worker_local_read_only_repo_inspection
operation_family = local_repo_inspection
```

It binds:

```text
Worker Mesh dispatch receipt schema
WorkerFailureReceipt failure schema
TemporalLeaseWindowReceipt pre-dispatch schema
local repo input refs
forbidden network, secret, cross-tenant, raw-output, external-request, and filesystem-write refs
verification refs
rollback refs
recovery refs
```

## 2. Authority Denials

The binding is intentionally non-runtime:

```text
runtime_dispatch_allowed = false
external_network_allowed = false
secret_access_allowed = false
filesystem_write_allowed = false
connector_authority_allowed = false
terminal_closure_allowed = false
raw_output_retention_allowed = false
lease_preflight_required = true
```

This lets the platform pick a first worker path without accidentally creating execution authority.

## 3. Receipt Binding

The selected path must carry both dispatch and failure receipt contracts:

```text
schemas/worker_mesh.schema.json
schemas/worker_failure_receipt.schema.json
schemas/temporal_lease_window_receipt.schema.json
schemas/read_only_worker_rehearsal_receipt.schema.json
```

`ReadOnlyWorkerLeasePreflight` binds the selected path to the existing temporal lease window contract. It keeps `dispatch_admitted = false` in Foundation Mode, requires `lease_active` temporal evidence for any future admission, requires a fencing token and positive sequence, and preserves `WorkerFailureReceipt` as the mandatory failure path.

Worker dispatch remains blocked until a later runtime proof thread binds an actual runner, verification envelope, and receipt emission. If dispatch fails later, `WorkerFailureReceipt` records failed steps, partial or unknown effects, rollback refs, recovery refs, and no-success guards.

`ReadOnlyWorkerRehearsalReceipt` closes the local rehearsal-only evidence gap. It records dry-run inspected refs and path-hash evidence under local repository prefixes while keeping `dispatch_admitted = false`, `terminal_closure = false`, `success_claim_allowed = false`, and all external or mutation effects denied.

The personal-assistant console read model binds the rehearsal receipt into its receipt panel through `receipts.viewer_binding`. This is a read-only projection only: it exposes the receipt id, schema ref, source fixture ref, worker path, dry-run mode, digest ref, and denial flags, while keeping runtime dispatch, filesystem writes, external effects, connector calls, terminal closure, and success claims false.

## 4. First-Worker Rationale

`read_only_repo_inspection` is selected before search or document workers because it:

```text
uses local repository evidence
does not need external network access
does not need connector credentials
does not need raw secret access
can prove receipt flow before customer or production exposure
```

Search and document workers remain future candidates after this local path proves the receipt spine.

## 5. Validation

Run:

```powershell
python scripts/validate_read_only_worker_binding.py
python scripts/validate_read_only_worker_lease_preflight.py
python scripts/validate_read_only_worker_rehearsal_receipt.py
python scripts/validate_personal_assistant_console_read_model.py
python -m pytest tests/test_validate_read_only_worker_binding.py -q
python -m pytest tests/test_validate_read_only_worker_lease_preflight.py -q
python -m pytest tests/test_validate_read_only_worker_rehearsal_receipt.py -q
python -m pytest tests/test_validate_personal_assistant_console_read_model.py tests/test_personal_assistant_console.py -q
python scripts/validate_schemas.py
python scripts/validate_protocol_manifest.py
```

STATUS:
  Completeness: 100%
  Invariants verified: first worker path selected, runtime dispatch denied, lease preflight required, local rehearsal receipt bound, read-only receipt viewer projection bound, network denied, secret access denied, filesystem writes denied, connector authority denied, terminal closure denied, success claims denied, raw output retention denied, temporal lease window receipt binding, worker failure receipt binding
  Open issues: live worker runner, dispatch endpoint, and runtime receipt emission remain unregistered
  Next action: design runtime receipt emission handoff before enabling any worker runtime
