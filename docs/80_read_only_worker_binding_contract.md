# ReadOnlyWorkerBinding Contract

Purpose: select the first Foundation Mode read-only worker path and bind its authority, lease preflight, rehearsal receipt, runtime receipt handoff, runtime receipt emitter dry-run, runtime runner binding witness, runtime receipt candidate, runtime receipt schema-binding witness, runtime receipt-store write-path witness, runtime runner registration witness, runtime dispatch endpoint registration witness, runtime receipt emitter registration witness, runtime receipt schema-binding activation witness, runtime receipt-store activation witness, runtime receipt-store operator approval witness, runtime receipt emission admission witness, runtime active lease admission witness, runtime dispatch admission witness, active runtime lease admission witness, UAO dispatch authorization witness, Phi_gov dispatch authorization witness, effect reconciliation witness, receipt append witness, terminal closure witness, runtime authority chain witness, runtime enablement witness, runtime enablement operator input request, runtime enablement evidence request status ledger, runtime enablement submitted evidence refs, runtime enablement review packet, operator runtime enablement approval ref, receipt-viewer projection, failure receipt, verification, rollback, and recovery obligations without registering a live worker.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `schemas/read_only_worker_binding.schema.json`, `schemas/read_only_worker_lease_preflight.schema.json`, `schemas/read_only_worker_rehearsal_receipt.schema.json`, `schemas/read_only_worker_runtime_receipt_handoff.schema.json`, `schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json`, `schemas/read_only_worker_runtime_runner_binding_witness.schema.json`, `schemas/read_only_worker_runtime_receipt_candidate.schema.json`, `schemas/read_only_worker_runtime_receipt_schema_binding_witness.schema.json`, `schemas/read_only_worker_runtime_receipt_store_write_path_witness.schema.json`, `schemas/read_only_worker_runtime_runner_registration_witness.schema.json`, `schemas/read_only_worker_runtime_dispatch_endpoint_registration_witness.schema.json`, `schemas/read_only_worker_runtime_receipt_emitter_registration_witness.schema.json`, `schemas/read_only_worker_runtime_receipt_schema_binding_activation_witness.schema.json`, `schemas/read_only_worker_runtime_receipt_store_activation_witness.schema.json`, `schemas/read_only_worker_runtime_receipt_store_operator_approval_witness.schema.json`, `schemas/read_only_worker_runtime_receipt_emission_admission_witness.schema.json`, `schemas/read_only_worker_runtime_active_lease_admission_witness.schema.json`, `schemas/read_only_worker_runtime_dispatch_admission_witness.schema.json`, `schemas/read_only_worker_active_runtime_lease_admission_witness.schema.json`, `schemas/read_only_worker_uao_dispatch_authorization_witness.schema.json`, `schemas/read_only_worker_phi_gov_dispatch_authorization_witness.schema.json`, `schemas/read_only_worker_effect_reconciliation_witness.schema.json`, `schemas/read_only_worker_receipt_append_witness.schema.json`, `schemas/read_only_worker_terminal_closure_witness.schema.json`, `schemas/read_only_worker_runtime_authority_chain_witness.schema.json`, `schemas/read_only_worker_runtime_enablement_witness.schema.json`, `schemas/read_only_worker_runtime_enablement_operator_input_request.schema.json`, `schemas/read_only_worker_runtime_enablement_evidence_request_status_ledger.schema.json`, `schemas/read_only_worker_runtime_enablement_submitted_evidence_refs.schema.json`, `schemas/read_only_worker_runtime_enablement_review_packet.schema.json`, `schemas/read_only_worker_operator_runtime_enablement_approval_ref.schema.json`, `scripts/validate_read_only_worker_binding.py`, `scripts/validate_read_only_worker_lease_preflight.py`, `scripts/validate_read_only_worker_rehearsal_receipt.py`, `scripts/validate_read_only_worker_runtime_receipt_handoff.py`, `scripts/validate_read_only_worker_runtime_receipt_emitter_dry_run.py`, `scripts/validate_read_only_worker_runtime_runner_binding_witness.py`, `scripts/validate_read_only_worker_runtime_receipt_candidate.py`, `scripts/validate_read_only_worker_runtime_receipt_schema_binding_witness.py`, `scripts/validate_read_only_worker_runtime_receipt_store_write_path_witness.py`, `scripts/validate_read_only_worker_runtime_runner_registration_witness.py`, `scripts/validate_read_only_worker_runtime_dispatch_endpoint_registration_witness.py`, `scripts/validate_read_only_worker_runtime_receipt_emitter_registration_witness.py`, `scripts/validate_read_only_worker_runtime_receipt_schema_binding_activation_witness.py`, `scripts/validate_read_only_worker_runtime_receipt_store_activation_witness.py`, `scripts/validate_read_only_worker_runtime_receipt_store_operator_approval_witness.py`, `scripts/validate_read_only_worker_runtime_receipt_emission_admission_witness.py`, `scripts/validate_read_only_worker_runtime_active_lease_admission_witness.py`, `scripts/validate_read_only_worker_runtime_dispatch_admission_witness.py`, `scripts/validate_read_only_worker_active_runtime_lease_admission_witness.py`, `scripts/validate_read_only_worker_uao_dispatch_authorization_witness.py`, `scripts/validate_read_only_worker_phi_gov_dispatch_authorization_witness.py`, `scripts/validate_read_only_worker_effect_reconciliation_witness.py`, `scripts/validate_read_only_worker_receipt_append_witness.py`, `scripts/validate_read_only_worker_terminal_closure_witness.py`, `scripts/validate_read_only_worker_runtime_authority_chain_witness.py`, `scripts/validate_read_only_worker_runtime_enablement_witness.py`, `scripts/emit_read_only_worker_runtime_enablement_operator_input_request.py`, `scripts/validate_read_only_worker_runtime_enablement_operator_input_request.py`, `scripts/validate_read_only_worker_runtime_enablement_evidence_request_status_ledger.py`, `scripts/validate_read_only_worker_runtime_enablement_submitted_evidence_refs.py`, `scripts/validate_read_only_worker_runtime_enablement_review_packet.py`, `scripts/validate_read_only_worker_operator_runtime_enablement_approval_ref.py`, `examples/read_only_worker_binding.foundation.json`, `examples/read_only_worker_lease_preflight.foundation.json`, `examples/read_only_worker_rehearsal_receipt.foundation.json`, `examples/read_only_worker_runtime_receipt_handoff.foundation.json`, `examples/read_only_worker_runtime_receipt_emitter_dry_run.foundation.json`, `examples/read_only_worker_runtime_runner_binding_witness.foundation.json`, `examples/read_only_worker_runtime_receipt_candidate.foundation.json`, `examples/read_only_worker_runtime_receipt_schema_binding_witness.foundation.json`, `examples/read_only_worker_runtime_receipt_store_write_path_witness.foundation.json`, `examples/read_only_worker_runtime_runner_registration_witness.foundation.json`, `examples/read_only_worker_runtime_dispatch_endpoint_registration_witness.foundation.json`, `examples/read_only_worker_runtime_receipt_emitter_registration_witness.foundation.json`, `examples/read_only_worker_runtime_receipt_schema_binding_activation_witness.foundation.json`, `examples/read_only_worker_runtime_receipt_store_activation_witness.foundation.json`, `examples/read_only_worker_runtime_receipt_store_operator_approval_witness.foundation.json`, `examples/read_only_worker_runtime_receipt_emission_admission_witness.foundation.json`, `examples/read_only_worker_runtime_active_lease_admission_witness.foundation.json`, `examples/read_only_worker_runtime_dispatch_admission_witness.foundation.json`, `examples/read_only_worker_active_runtime_lease_admission_witness.foundation.json`, `examples/read_only_worker_uao_dispatch_authorization_witness.foundation.json`, `examples/read_only_worker_phi_gov_dispatch_authorization_witness.foundation.json`, `examples/read_only_worker_effect_reconciliation_witness.foundation.json`, `examples/read_only_worker_receipt_append_witness.foundation.json`, `examples/read_only_worker_terminal_closure_witness.foundation.json`, `examples/read_only_worker_runtime_authority_chain_witness.foundation.json`, `examples/read_only_worker_runtime_enablement_witness.foundation.json`, `examples/read_only_worker_runtime_enablement_evidence_request_status_ledger.foundation.json`, `examples/read_only_worker_runtime_enablement_submitted_evidence_refs.foundation.json`, `examples/read_only_worker_runtime_enablement_review_packet.foundation.json`, `examples/read_only_worker_operator_runtime_enablement_approval_ref.foundation.json`, `schemas/worker_mesh.schema.json`, `schemas/worker_failure_receipt.schema.json`, `schemas/temporal_lease_window_receipt.schema.json`.
Invariants: selected worker path is `read_only_repo_inspection`; runtime dispatch is denied; temporal lease preflight is required before any later dispatch admission; local rehearsal evidence is dry-run only; runtime receipt handoff is contract-only; runtime receipt emitter dry-run is simulated only; runtime runner binding witness is witness-only; runtime receipt candidate is candidate-only; runtime receipt schema-binding witness is witness-only; runtime receipt-store write-path witness is witness-only; runtime runner registration witness is witness-only; runtime dispatch endpoint registration witness is witness-only; runtime receipt emitter registration witness is witness-only; runtime receipt schema-binding activation witness is witness-only; runtime receipt-store activation witness is witness-only; runtime receipt-store operator approval witness is witness-only; runtime receipt emission admission witness is witness-only; runtime active lease admission witness is witness-only; runtime dispatch admission witness is witness-only; active runtime lease admission witness is witness-only; UAO dispatch authorization witness is witness-only; Phi_gov dispatch authorization witness is witness-only; effect reconciliation witness is witness-only; receipt append witness is witness-only; terminal closure witness is witness-only; runtime authority chain witness is witness-only; runtime enablement witness is witness-only; runtime enablement operator input request is non-executing; runtime enablement evidence request status ledger is status-only; runtime enablement submitted evidence refs are review-pending and non-authoritative; runtime enablement review packet is non-accepting and non-authoritative; operator runtime enablement approval ref is review-only and non-authoritative; console receipt projection is read-only; external network, secrets, filesystem writes, connector authority, terminal closure, success claims, and raw output retention are denied; WorkerFailureReceipt remains mandatory for failed dispatch evidence; Mfidel atomicity is preserved.

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
schemas/read_only_worker_runtime_receipt_handoff.schema.json
schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json
schemas/read_only_worker_runtime_runner_binding_witness.schema.json
schemas/read_only_worker_runtime_receipt_candidate.schema.json
schemas/read_only_worker_runtime_receipt_schema_binding_witness.schema.json
schemas/read_only_worker_runtime_receipt_store_write_path_witness.schema.json
schemas/read_only_worker_runtime_runner_registration_witness.schema.json
schemas/read_only_worker_runtime_dispatch_endpoint_registration_witness.schema.json
schemas/read_only_worker_runtime_receipt_emitter_registration_witness.schema.json
schemas/read_only_worker_runtime_receipt_schema_binding_activation_witness.schema.json
schemas/read_only_worker_runtime_receipt_store_activation_witness.schema.json
schemas/read_only_worker_runtime_receipt_store_operator_approval_witness.schema.json
schemas/read_only_worker_runtime_receipt_emission_admission_witness.schema.json
schemas/read_only_worker_runtime_dispatch_admission_witness.schema.json
schemas/read_only_worker_active_runtime_lease_admission_witness.schema.json
schemas/read_only_worker_uao_dispatch_authorization_witness.schema.json
schemas/read_only_worker_phi_gov_dispatch_authorization_witness.schema.json
```

`ReadOnlyWorkerLeasePreflight` binds the selected path to the existing temporal lease window contract. It keeps `dispatch_admitted = false` in Foundation Mode, requires `lease_active` temporal evidence for any future admission, requires a fencing token and positive sequence, and preserves `WorkerFailureReceipt` as the mandatory failure path.

Worker dispatch remains blocked until a later runtime proof thread binds an actual runner, verification envelope, and receipt emission. If dispatch fails later, `WorkerFailureReceipt` records failed steps, partial or unknown effects, rollback refs, recovery refs, and no-success guards.

`ReadOnlyWorkerRehearsalReceipt` closes the local rehearsal-only evidence gap. It records dry-run inspected refs and path-hash evidence under local repository prefixes while keeping `dispatch_admitted = false`, `terminal_closure = false`, `success_claim_allowed = false`, and all external or mutation effects denied.

The personal-assistant console read model binds the rehearsal receipt into its receipt panel through `receipts.viewer_binding`. This is a read-only projection only: it exposes the receipt id, schema ref, source fixture ref, worker path, dry-run mode, digest ref, and denial flags, while keeping runtime dispatch, filesystem writes, external effects, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeReceiptHandoff` binds the next runtime boundary without granting runtime authority. It requires the binding, lease preflight, rehearsal receipt, and console projection as source evidence, names future runtime-emitter gates, and keeps runner registration, dispatch endpoint registration, receipt-emitter registration, runtime dispatch, filesystem writes, connector calls, terminal closure, and success claims false. Future admission remains blocked until runtime-runner evidence, receipt-emitter dry-run evidence, active temporal lease evidence, UAO admission, `Phi_gov` authorization, and WorkerFailureReceipt obligations are present.

`ReadOnlyWorkerRuntimeReceiptEmitterDryRun` records the receipt-emitter dry-run evidence named by the handoff. It proves the future emitter envelope, required source refs, runtime gates, runtime witnesses, failure-receipt obligation, output-digest-only policy, and terminal-closure block while keeping runner registration, dispatch endpoint registration, runtime emitter registration, runtime receipt schema binding, runtime dispatch, runtime receipt emission, worker mesh dispatch receipts, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeRunnerBindingWitness` records the next witness-only evidence boundary named by the dry-run. It proves future runner registration obligations and future runtime receipt schema-binding obligations while keeping runtime runner registration, dispatch endpoint registration, runtime emitter registration, runtime receipt schema binding, runtime dispatch, filesystem writes, connector calls, terminal closure, and success claims unperformed.

`ReadOnlyWorkerRuntimeReceiptCandidate` defines the future runtime receipt envelope named by the runner-binding witness. It requires source witness refs, UAO, `Phi_gov`, causal trace, active temporal lease, runner registration witness, schema-binding witness, failure receipt, effect reconciliation, and receipt-store refs while keeping schema binding, runtime dispatch, worker invocation, runtime receipt emission, worker mesh dispatch receipt emission, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeReceiptSchemaBindingWitness` records the schema-binding evidence boundary named by the runtime receipt candidate. It validates the candidate schema and example, binds source candidate evidence, lists future schema-binding inputs, and keeps runtime receipt schema binding, schema registry writes, runtime dispatch, runtime receipt emission, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeReceiptStoreWritePathWitness` records the receipt-store write-path evidence boundary named by the schema-binding witness. It binds source schema-binding and candidate evidence, lists future append-only and idempotent store inputs, and keeps receipt-store writer registration, write-path registration, receipt append, runtime dispatch, runtime receipt emission, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeRunnerRegistrationWitness` records the future live runner registration evidence boundary without performing registration. It binds the runner-binding and receipt-store write-path witnesses, lists operator approval, runner identity digest, capability scope, temporal lease, UAO, `Phi_gov`, receipt-store, WorkerFailureReceipt, and effect-reconciliation inputs, and keeps runner registration, runner registry writes, dispatch endpoint registration, runtime dispatch, runtime receipt emission, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeDispatchEndpointRegistrationWitness` records the future live dispatch endpoint registration evidence boundary without performing registration. It binds the runner-registration witness, lists operator approval, live runner registration, endpoint identity digest, route boundary, temporal lease, UAO, `Phi_gov`, receipt-store, WorkerFailureReceipt, and effect-reconciliation inputs, and keeps endpoint registration, endpoint registry writes, route binding, runtime dispatch, worker invocation, runtime receipt emission, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeReceiptEmitterRegistrationWitness` records the future live runtime receipt emitter registration evidence boundary without performing registration. It binds the dispatch endpoint registration witness, lists operator approval, emitter identity digest, emitter registration boundary, temporal lease, UAO, `Phi_gov`, receipt-store, WorkerFailureReceipt, and effect-reconciliation inputs, and keeps emitter registration, emitter registry writes, runtime receipt emission, runtime dispatch, worker invocation, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeReceiptSchemaBindingActivationWitness` records the future live runtime receipt schema-binding activation evidence boundary without activating schema binding. It binds the receipt emitter registration witness and schema-binding witness, lists operator approval, emitter identity digest, schema identity digest, schema activation boundary, schema registry boundary, temporal lease, UAO, `Phi_gov`, receipt-store, WorkerFailureReceipt, and effect-reconciliation inputs, and keeps schema-binding activation, schema registry writes, runtime receipt emission, runtime dispatch, worker invocation, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeReceiptStoreActivationWitness` records the future live runtime receipt-store activation evidence boundary without activating a receipt store. It binds the schema-binding activation witness and receipt-store write-path witness, lists operator approval, store identity digest, store activation boundary, append-only receipt-store evidence, temporal lease, UAO, `Phi_gov`, WorkerFailureReceipt, and effect-reconciliation inputs, and keeps receipt-store activation, receipt append, runtime receipt emission, runtime dispatch, worker invocation, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeReceiptStoreOperatorApprovalWitness` records the missing operator approval evidence boundary for future runtime receipt-store activation and runtime receipt emission admission. It binds the activation and emission-admission witnesses, marks approval as `AwaitingEvidence`, and keeps operator approval collection, operator approval grant, receipt-store activation, emission admission, receipt append, runtime dispatch, worker invocation, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeReceiptEmissionAdmissionWitness` records the future runtime receipt emission admission evidence boundary without admitting emission. It binds the receipt-store activation witness, schema-binding activation witness, receipt-emitter registration witness, and receipt-store write-path witness, lists operator approval, emitter identity digest, schema identity digest, receipt-store activation evidence, active temporal lease, UAO, `Phi_gov`, WorkerFailureReceipt, and effect-reconciliation inputs, and keeps emission admission, runtime receipt emission, receipt append, runtime dispatch, worker invocation, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeActiveLeaseAdmissionWitness` records the future active runtime lease admission evidence boundary without claiming or executing a lease. It binds the read-only worker binding and lease preflight, lists operator approval, active temporal lease, tenant/actor boundary, resource scope, distributed lease claim receipt, distributed lease execution receipt, UAO, `Phi_gov`, WorkerFailureReceipt, and effect-reconciliation inputs, and keeps active lease admission, lease claim, distributed lease execution, dispatch admission, runtime dispatch, worker invocation, runtime receipt emission, receipt append, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeDispatchAdmissionWitness` records the future live runtime dispatch admission evidence boundary without admitting dispatch. It binds the receipt-emission admission witness plus upstream receipt-store activation, schema-binding activation, runner registration, dispatch-endpoint registration, receipt-emitter registration, receipt candidate, runner-binding, emitter dry-run, handoff, binding, lease-preflight, active lease admission witness, rehearsal, active temporal lease, UAO, `Phi_gov`, WorkerFailureReceipt, and effect-reconciliation inputs, and keeps dispatch admission, runtime dispatch, worker invocation, runtime receipt emission, receipt append, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerActiveRuntimeLeaseAdmissionWitness` records the future active TemporalLeaseWindowReceipt admission evidence boundary without observing a live lease or admitting dispatch. It binds the runtime dispatch admission witness and lease preflight, lists live lease-active status, active lease state, trusted runtime clock, fencing token, positive sequence, UAO, `Phi_gov`, WorkerFailureReceipt, and effect-reconciliation inputs, and keeps active lease observation, active lease admission, runtime dispatch admission, runtime dispatch, worker invocation, runtime receipt emission, receipt append, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerUaoDispatchAuthorizationWitness` records the future Universal Action Orchestration dispatch authorization evidence boundary without authorizing UAO or `Phi_gov`. It binds the runtime dispatch admission witness and active runtime lease admission witness, lists UAO request, effect-bearing classification, no-bypass proof, policy allow decision, tenant/actor/worker scope, active lease admission, runtime dispatch admission boundary, trusted runtime clock, `Phi_gov`, WorkerFailureReceipt, and effect-reconciliation inputs, and keeps UAO authorization, `Phi_gov` authorization, dispatch admission, runtime dispatch, worker invocation, runtime receipt emission, receipt append, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerPhiGovDispatchAuthorizationWitness` records the future `Phi_gov` dispatch authorization evidence boundary without authorizing UAO, authorizing `Phi_gov`, or admitting dispatch. It binds the UAO dispatch authorization witness and active runtime lease admission witness, lists model freeze, episode snapshot, governance authority, UAO dispatch authorization evidence, no-bypass proof, constraint satisfaction, LifeMeaningJudgment, active lease admission, trusted runtime clock, WorkerFailureReceipt, and effect-reconciliation inputs, and keeps UAO authorization, `Phi_gov` authorization, dispatch admission, runtime dispatch, worker invocation, runtime receipt emission, receipt append, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerEffectReconciliationWitness` records the future effect reconciliation evidence boundary without collecting reconciliation evidence or admitting dispatch. It binds the Phi_gov dispatch authorization witness plus upstream UAO and active lease witnesses, requires expected and observed effect evidence, worker receipt evidence, WorkerFailureReceipt obligation on error, and no unexpected filesystem, network, or connector effects, and keeps UAO authorization, `Phi_gov` authorization, effect reconciliation, dispatch admission, runtime dispatch, worker invocation, runtime receipt emission, receipt append, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerReceiptAppendWitness` records the future receipt append evidence boundary without appending a receipt or admitting dispatch. It binds the effect reconciliation witness, runtime receipt emission admission witness, and receipt-store activation witness, requires append-only proof, idempotency proof, receipt digest, trusted runtime clock, and WorkerFailureReceipt obligation on error, and keeps receipt append, dispatch admission, runtime dispatch, worker invocation, runtime receipt emission, filesystem writes, connector calls, terminal closure, and success claims false.

`ReadOnlyWorkerTerminalClosureWitness` records the future terminal closure evidence boundary without closing terminal evidence or admitting dispatch. It binds the receipt append witness and effect reconciliation witness, requires final judgment, no unexpected effects, evidence bundle, replay verification, terminal closure certificate, receipt digest, trusted runtime clock, and WorkerFailureReceipt obligation on error, and keeps terminal closure, dispatch admission, runtime dispatch, worker invocation, runtime receipt emission, receipt append, filesystem writes, connector calls, and success claims false.

`ReadOnlyWorkerRuntimeEnablementWitness` records the future runtime enablement evidence boundary without enabling runtime dispatch or invoking a worker. It binds the terminal closure witness, requires runtime runner registration, dispatch endpoint registration, receipt emitter registration, receipt-store activation, operator runtime enablement approval, active runtime lease evidence, UAO and Phi_gov dispatch authorization evidence, runtime dispatch admission evidence, rollback evidence, trusted runtime clock evidence, and WorkerFailureReceipt obligation on error, and keeps runtime enablement, dispatch admission, runtime dispatch, worker invocation, runtime receipt emission, receipt append, filesystem writes, connector calls, network access, secret access, terminal closure, and success claims false.

`ReadOnlyWorkerRuntimeEnablementOperatorInputRequest` converts the blocked runtime enablement witness into an explicit missing-evidence request for operator review. It lists the terminal closure certificate, runner registration, dispatch endpoint registration, receipt emitter registration, receipt-store activation, runtime enablement approval, active runtime lease observation, UAO dispatch authorization, `Phi_gov` dispatch authorization, runtime dispatch admission, disablement rollback plan, and trusted runtime clock inputs while keeping runtime enablement, dispatch admission, runtime dispatch, worker invocation, runtime receipt emission, receipt append, terminal closure, filesystem writes, connector calls, network access, secret access, and success claims false.

`ReadOnlyWorkerOperatorRuntimeEnablementApprovalRef` records the operator approval reference required by the runtime enablement input request without accepting evidence or granting runtime authority. It binds the local control-studio approval ref for review only and keeps runtime enablement, dispatch, worker invocation, receipt emission, receipt append, terminal closure, filesystem writes, connector calls, network access, secret access, and success claims false.

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
python scripts/validate_read_only_worker_runtime_receipt_handoff.py
python scripts/validate_read_only_worker_runtime_receipt_emitter_dry_run.py
python scripts/validate_read_only_worker_runtime_runner_binding_witness.py
python scripts/validate_read_only_worker_runtime_receipt_candidate.py
python scripts/validate_read_only_worker_runtime_receipt_schema_binding_witness.py
python scripts/validate_read_only_worker_runtime_receipt_store_write_path_witness.py
python scripts/validate_read_only_worker_runtime_runner_registration_witness.py
python scripts/validate_read_only_worker_runtime_dispatch_endpoint_registration_witness.py
python scripts/validate_read_only_worker_runtime_receipt_emitter_registration_witness.py
python scripts/validate_read_only_worker_runtime_receipt_schema_binding_activation_witness.py
python scripts/validate_read_only_worker_runtime_receipt_store_activation_witness.py
python scripts/validate_read_only_worker_runtime_receipt_store_operator_approval_witness.py
python scripts/validate_read_only_worker_runtime_receipt_emission_admission_witness.py
python scripts/validate_read_only_worker_runtime_active_lease_admission_witness.py
python scripts/validate_read_only_worker_runtime_dispatch_admission_witness.py
python scripts/validate_read_only_worker_active_runtime_lease_admission_witness.py
python scripts/validate_read_only_worker_uao_dispatch_authorization_witness.py
python scripts/validate_read_only_worker_phi_gov_dispatch_authorization_witness.py
python scripts/validate_read_only_worker_runtime_authority_chain_witness.py
python scripts/validate_read_only_worker_runtime_enablement_witness.py
python scripts/emit_read_only_worker_runtime_enablement_operator_input_request.py
python scripts/validate_read_only_worker_runtime_enablement_operator_input_request.py --require-blocked
python scripts/validate_read_only_worker_runtime_enablement_evidence_request_status_ledger.py
python scripts/validate_read_only_worker_runtime_enablement_submitted_evidence_refs.py
python scripts/validate_read_only_worker_runtime_enablement_review_packet.py
python scripts/validate_read_only_worker_operator_runtime_enablement_approval_ref.py
python scripts/validate_read_only_worker_runtime_disablement_rollback_plan.py
python scripts/validate_read_only_worker_trusted_runtime_clock_receipt.py
python scripts/validate_personal_assistant_console_read_model.py
python -m pytest tests/test_validate_read_only_worker_binding.py -q
python -m pytest tests/test_validate_read_only_worker_lease_preflight.py -q
python -m pytest tests/test_validate_read_only_worker_rehearsal_receipt.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_receipt_handoff.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_receipt_emitter_dry_run.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_runner_binding_witness.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_receipt_candidate.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_receipt_schema_binding_witness.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_receipt_store_write_path_witness.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_runner_registration_witness.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_dispatch_endpoint_registration_witness.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_receipt_emitter_registration_witness.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_receipt_schema_binding_activation_witness.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_receipt_store_activation_witness.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_receipt_emission_admission_witness.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_active_lease_admission_witness.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_dispatch_admission_witness.py -q
python -m pytest tests/test_validate_read_only_worker_active_runtime_lease_admission_witness.py -q
python -m pytest tests/test_validate_read_only_worker_uao_dispatch_authorization_witness.py -q
python -m pytest tests/test_validate_read_only_worker_phi_gov_dispatch_authorization_witness.py -q
python -m pytest tests/test_validate_read_only_worker_effect_reconciliation_witness.py -q
python -m pytest tests/test_validate_read_only_worker_receipt_append_witness.py -q
python -m pytest tests/test_validate_read_only_worker_terminal_closure_witness.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_authority_chain_witness.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_enablement_witness.py -q
python -m pytest tests/test_emit_read_only_worker_runtime_enablement_operator_input_request.py tests/test_validate_read_only_worker_runtime_enablement_operator_input_request.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_enablement_evidence_request_status_ledger.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_enablement_submitted_evidence_refs.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_enablement_review_packet.py -q
python -m pytest tests/test_validate_read_only_worker_runtime_disablement_rollback_plan.py tests/test_validate_read_only_worker_trusted_runtime_clock_receipt.py -q
python -m pytest tests/test_validate_personal_assistant_console_read_model.py tests/test_personal_assistant_console.py -q
python scripts/validate_schemas.py
python scripts/validate_protocol_manifest.py
```

STATUS:
  Completeness: 100%
  Invariants verified: first worker path selected, runtime dispatch denied, lease preflight required, local rehearsal receipt bound, runtime receipt handoff bound, runtime receipt emitter dry-run bound, runtime runner binding witness bound, runtime receipt candidate bound, runtime receipt schema-binding witness bound, runtime receipt-store write-path witness bound, runtime runner registration witness bound, runtime dispatch endpoint registration witness bound, runtime receipt emitter registration witness bound, runtime receipt schema-binding activation witness bound, runtime receipt-store activation witness bound, runtime receipt-store operator approval witness bound, runtime receipt emission admission witness bound, runtime active lease admission witness bound, runtime dispatch admission witness bound, active runtime lease admission witness bound, UAO dispatch authorization witness bound, Phi_gov dispatch authorization witness bound, effect reconciliation witness bound, receipt append witness bound, terminal closure witness bound, runtime authority chain witness bound, runtime enablement witness bound, runtime enablement operator input request bound, runtime enablement evidence request status ledger bound, runtime enablement submitted evidence refs bound, runtime enablement review packet bound, operator runtime enablement approval ref bound, read-only receipt viewer projection bound, network denied, secret access denied, filesystem writes denied, connector authority denied, runtime enablement denied, terminal closure denied, success claims denied, raw output retention denied, temporal lease window receipt binding, worker failure receipt binding
  Open issues: live worker runner, dispatch endpoint, runtime receipt emitter, runtime receipt schema-binding activation, runtime receipt-store activation, runtime receipt-store operator approval collection, runtime receipt emission admission, runtime dispatch admission, active runtime lease observation, UAO dispatch authorization execution, `Phi_gov` dispatch authorization execution, evidence acceptance, runtime admission, effect reconciliation execution, receipt append execution, terminal closure execution, runtime enablement execution, and worker runtime activation remain unperformed
  Next action: add separate evidence acceptance and runtime admission gates before enabling any worker runtime
