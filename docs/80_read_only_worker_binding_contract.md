# ReadOnlyWorkerBinding Contract

Purpose: select the first Foundation Mode read-only worker path and bind its authority, receipt, verification, rollback, and recovery obligations without registering a live worker.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `schemas/read_only_worker_binding.schema.json`, `scripts/validate_read_only_worker_binding.py`, `examples/read_only_worker_binding.foundation.json`, `schemas/worker_mesh.schema.json`, `schemas/worker_failure_receipt.schema.json`.
Invariants: selected worker path is `read_only_repo_inspection`; runtime dispatch is denied; external network, secrets, filesystem writes, connector authority, terminal closure, and raw output retention are denied; WorkerFailureReceipt remains mandatory for failed dispatch evidence; Mfidel atomicity is preserved.

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
```

This lets the platform pick a first worker path without accidentally creating execution authority.

## 3. Receipt Binding

The selected path must carry both dispatch and failure receipt contracts:

```text
schemas/worker_mesh.schema.json
schemas/worker_failure_receipt.schema.json
```

Worker dispatch remains blocked until a later runtime proof thread binds an actual runner, lease preflight, and verification envelope. If dispatch fails later, `WorkerFailureReceipt` records failed steps, partial or unknown effects, rollback refs, recovery refs, and no-success guards.

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
python -m pytest tests/test_validate_read_only_worker_binding.py -q
python scripts/validate_schemas.py
python scripts/validate_protocol_manifest.py
```

STATUS:
  Completeness: 100%
  Invariants verified: first worker path selected, runtime dispatch denied, network denied, secret access denied, filesystem writes denied, connector authority denied, terminal closure denied, raw output retention denied, worker failure receipt binding
  Open issues: live worker runner, lease preflight, dispatch endpoint, and receipt emission remain unregistered
  Next action: add a local rehearsal-only worker lease preflight for `read_only_repo_inspection`
