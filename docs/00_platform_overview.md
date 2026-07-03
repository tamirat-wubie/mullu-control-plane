# Platform Overview

> **In one box:** This is the map. It says which parts of the code count as the
> [control plane](GLOSSARY.md#control-plane) (the decide / check / record layer)
> and which names mean what (Mullu Govern vs Mullu vs Mullu Platform vs Mullu Control Plane).
> Read it when you're unsure *where a responsibility lives*. Brand new? Read the
> jargon-free [Plain-English Overview](explain/PLAIN_ENGLISH.md) first.
> *(Doc type: Reference.)*

Purpose: define the repository boundary for Mullu Govern and the Mullu Control Plane.
Governance scope: Milestone 0 shared foundation and Foundation Mode claim boundary.
Dependencies: `docs/FOUNDATION_MODE.md`, `docs/PRODUCT_BOUNDARY.md`, `docs/01_shared_invariants.md`, `docs/02_shared_contracts.md`, `docs/74_truth_kernel_plane.md`, `docs/75_problem_star_compilation_receipt.md`, `docs/76_clarification_request_contract.md`, `docs/77_search_decision_contract.md`, `docs/78_search_receipt_contract.md`, `docs/79_worker_failure_receipt_contract.md`, `docs/80_read_only_worker_binding_contract.md`, `docs/82_cross_repo_opportunity_map.md`, `docs/83_connector_action_promotion_gate_contract.md`, `docs/84_worker_receipt_ledger_read_model_contract.md`, `docs/85_mfidel_substrate_conformance_receipt_contract.md`, `docs/86_readiness_waiver_review_packet_contract.md`, `docs/87_browser_observation_receipt_contract.md`, `docs/88_research_source_conflict_map_contract.md`, `docs/89_trusted_capture_evidence_packet_contract.md`, `docs/90_sccml_trace_adapter_witness_contract.md`, `docs/91_resilience_rehearsal_reports_contract.md`, `docs/91_chaos_rehearsal_execution_report_contract.md`, `docs/92_invariant_fuzz_execution_report_contract.md`, `docs/92_world_substrate_replay_witness_contract.md`, `schemas/read_only_worker_rehearsal_receipt.schema.json`, `schemas/read_only_worker_runtime_receipt_handoff.schema.json`, `schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json`, `schemas/read_only_worker_runtime_runner_binding_witness.schema.json`, `schemas/connector_action_promotion_gate.schema.json`, `schemas/worker_receipt_ledger_read_model.schema.json`, `schemas/mfidel_substrate_conformance_receipt.schema.json`, `schemas/readiness_waiver_review_packet.schema.json`, `schemas/browser_observation_receipt.schema.json`, `schemas/research_source_conflict_map.schema.json`, `schemas/trusted_capture_evidence_packet.schema.json`, `schemas/sccml_trace_adapter_witness.schema.json`, `schemas/chaos_rehearsal_execution_report.schema.json`, `schemas/invariant_fuzz_execution_report.schema.json`, `schemas/world_substrate_replay_witness.schema.json`, `schemas/read_only_worker_runtime_receipt_store_activation_witness.schema.json`, `schemas/read_only_worker_runtime_receipt_emission_admission_witness.schema.json`, `schemas/read_only_worker_runtime_active_lease_admission_witness.schema.json`, `schemas/read_only_worker_runtime_dispatch_admission_witness.schema.json`, `schemas/read_only_worker_active_runtime_lease_admission_witness.schema.json`, `schemas/read_only_worker_uao_dispatch_authorization_witness.schema.json`, `schemas/read_only_worker_phi_gov_dispatch_authorization_witness.schema.json`, `schemas/read_only_worker_effect_reconciliation_witness.schema.json`, `schemas/read_only_worker_receipt_append_witness.schema.json`, `schemas/read_only_worker_terminal_closure_witness.schema.json`, `schemas/read_only_worker_runtime_enablement_witness.schema.json`, `schemas/read_only_worker_runtime_status_read_model.schema.json`.
Invariants: shared meaning is defined once; Foundation Mode remains the current operating posture until promoted by witness; MAF Core and MCOI Runtime remain split; Mullu Govern remains the public product name; Mullu remains the suite/family name; Mullusi remains the company name; Mullu Platform remains a developer and architecture term; Mullu Control Plane remains the admin/governance/deployment surface; Mullu Truth Kernel remains an internal MAF Core subsystem, not a company, product, or runtime replacement.

## Product Identity

Mullu Govern is the public governed-execution product by Mullusi. Mullu is the
suite/family name. Mullu Platform is reserved for developer, SDK, API,
deployment, and architecture contexts. This repository defines the Mullu Control
Plane surface for admin, governance, approval, trace, budget, lineage, and
deployment operation.

Subsystem naming follows the same boundary. Mullusi is the company, not a
component prefix. The truth-state kernel subsystem is named
[Mullu Truth Kernel](74_truth_kernel_plane.md), with `MTK` as the internal
short name and Truth Kernel Plane as its architecture boundary.

## Current Operating Posture

The current repository posture is [Foundation Mode](FOUNDATION_MODE.md):
private, local-first architecture hardening before deployment, customer access,
company formation, paid infrastructure, or patent filing. Platform capability
may be broad, but current proof work should remain narrow, local, reversible,
and receipt-backed until a later status witness promotes the project.

## Structure

- `Shared Contracts` define invariants, contract meaning, trace semantics, policy semantics, verification semantics, and learning admission semantics.
- `MAF Core` owns the general substrate, kernel-facing interfaces, and shared runtime primitives.
- `Mullu Truth Kernel` is an internal MAF Core subsystem for domains, constraints, closure, propagation, kernel checks, projections, forced values, and proof-bound truth-state commits.
- `ProblemStar Compilation Receipt` is a read-only governance receipt proving raw input was separated into canonical Phi-GPS fields and proof surfaces before solver routing.
- `ClarificationRequest Contract` is a read-only interpretation blocker that asks one focused question and preserves `no_execution` until missing action slots are answered.
- `SearchDecision Contract` is a read-only pre-retrieval search gate that records search need, freshness, source scope, budget, and retrieval safety before evidence collection.
- `SearchReceipt Contract` is a read-only post-decision search receipt that records evidence metadata, freshness results, citations, conflicts, retrieval errors, and retrieval safety outcomes.
- `Observation Evidence Acquisition Architecture` is the cross-platform intake contract defined in docs/94_observation_evidence_acquisition_architecture.md for converting repository, CI, inbox/calendar, provider, worker, deployment, approval, browser/search, and operator evidence into bounded planning input without execution authority or truth commits.
- `ResearchSourceConflictMap Contract` preserves citation-backed source disagreements, contradiction classes, freshness impact, and follow-up sensing needs without live search, source contact, connector calls, raw source-body retention, answer synthesis, memory writes, publication, terminal closure, or success claims.
- `TrustedCaptureEvidencePacket Contract` binds source-surface hashes, capture-policy refs, evidence-classification refs, browser-observation refs, digest-only capture artifacts, privacy guards, and authority denials without live capture, media recording, camera or microphone capture, sensor reads, file writes, connector calls, raw payload retention, publication, terminal closure, or success claims.
- `SccmlTraceAdapterWitness Contract` binds SCCML instruction-trace digest refs, state-hash refs, proof refs, unsupported-operation gap refs, KernelProof refs, TraceEntry refs, UAO refs, LifeMeaningJudgment refs, integrity guards, and authority denials without live kernel execution, subprocess execution, replay, state mutation, proof acceptance, connector calls, raw trace or state retention, terminal closure, or success claims.
- `ResilienceRehearsalReports Contract` records dry-run chaos rehearsal and deterministic invariant fuzz evidence with rollback and incident handoff obligations while keeping runtime execution, random live fuzzing, external effects, filesystem mutation, deployment mutation, production-readiness claims, success claims, and terminal closure denied.
- `ChaosRehearsalExecutionReport Contract` binds scenario refs, invariant refs, injection-point refs, expected containment refs, expected signal refs, required evidence refs, rollback guard refs, result-bank digest refs, UAO refs, LifeMeaningJudgment refs, safety guards, and authority denials without live chaos execution, staging or production targeting, runtime disruption, event-chain mutation, connector calls, raw runtime log retention, rollback execution, terminal closure, or success claims.
- `InvariantFuzzExecutionReport Contract` binds deterministic seed refs, case-bank digest refs, mutation-class refs, oracle refs, expected accept and reject counts, projection leak checks, result-bank digest refs, UAO refs, LifeMeaningJudgment refs, safety guards, and authority denials without live runtime execution, staging or production targeting, canonical state mutation, event-chain mutation, runtime lawbook migration, connector calls, raw case payload retention, rollback execution, terminal closure, or success claims.
- `MafReceiptParityWitness Contract` binds Python receipt schema digests to Rust MAF crate manifest and entry digests while keeping PyO3 binding, subprocess execution, CLI execution, Rust execution, connectors, writes, runtime dispatch, terminal closure, and success claims denied until ABI, subprocess, fixture-parity, and failure-path witnesses exist.
- `MafAbiCliContractWitness Contract` records the MAF CLI/ABI boundary as scaffold-only static evidence while keeping command behavior, CLI execution, subprocess execution, PyO3 binding, Rust execution, runtime dispatch, terminal closure, and success claims denied.
- `MafSubprocessEffectBoundaryWitness Contract` records process-spawn, filesystem-write, network-call, secret-read, dispatch, and state-mutation controls as static subprocess boundary evidence while keeping subprocess execution, command behavior, runtime binding, terminal closure, and success claims denied.
- `MafFailureReceiptPathWitness Contract` records static failure receipt materialization paths for MAF CLI descriptors while keeping runtime binding, command behavior, CLI execution, subprocess execution, raw failure payload retention, writes, terminal closure, and success claims denied.
- `MafRuntimeBindingAdmissionWitness Contract` records the governed admission gate for future MAF runtime binding while keeping implementation start, executable binding, PyO3, subprocess execution, backend default flips, terminal closure, and success claims denied.
- `WorldSubstrateReplayWitness Contract` binds world snapshot digest refs, replay trace digest refs, sparse-cache truth refs, legal geometry refs, field derivation refs, invariant registry refs, branch quarantine refs, replay probe refs, planner/executor parity refs, UAO refs, LifeMeaningJudgment refs, SimulationReceipt refs, EffectAssurance refs, and SDLC recovery refs without live world service calls, SQLite reads or writes, world mutation, replay execution, planner/executor execution, external endpoint calls, raw world or replay payload retention, terminal closure, or success claims.
- `WorkerFailureReceipt Contract` is a non-terminal post-dispatch worker receipt that records failed steps, partial effects, unknown effects, rollback obligations, recovery obligations, and no-success guards.
- `ReadOnlyWorkerBinding Contract` selects local repo inspection as the first worker path and binds worker mesh plus failure receipts while denying runtime dispatch, network, secrets, writes, connector authority, terminal closure, and raw output retention.
- `ReadOnlyWorkerRehearsalReceipt Contract` records local dry-run evidence for the selected read-only worker path while still denying runtime dispatch, external effects, filesystem writes, connector calls, raw output retention, success claims, and terminal closure; the personal-assistant console receipt panel now carries a read-only projection of that rehearsal evidence.
- `AgenticServiceHarnessAgentRunReceiptEmitterDryRun Contract` records a generic dry-run `AgentRun` receipt envelope from the harness read-model fixture while keeping runtime receipt emission, receipt-store append, adapter execution, runtime state writes, external effects, secret material, success claims, and terminal closure denied.
- `AgenticServiceHarnessWorkspaceSandboxPreflight Contract` binds the branch-write-awaiting-approval sandbox to command allowlist, path allowlist, timeout, network, cleanup, approval, and no-effect controls while keeping branch creation, file writes, command execution, cleanup execution, adapter execution, receipt-store append, external effects, success claims, and terminal closure denied.
- `ReadOnlyWorkerRuntimeReceiptHandoff Contract` binds the next runtime receipt-emitter proof boundary while keeping runner registration, dispatch endpoint registration, receipt-emitter registration, filesystem writes, connector calls, success claims, and terminal closure denied.
- `ReadOnlyWorkerRuntimeReceiptEmitterDryRun Contract` records dry-run emitter-envelope evidence while still denying runner registration, dispatch endpoint registration, runtime emitter registration, runtime receipt schema binding, filesystem writes, connector calls, runtime receipt emission, success claims, and terminal closure.
- `ReadOnlyWorkerRuntimeRunnerBindingWitness Contract` records witness-only evidence for future runtime runner registration and runtime receipt schema binding while keeping registration, binding, dispatch, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerRuntimeReceiptCandidate Contract` defines the future runtime receipt envelope for the selected read-only worker path while keeping schema binding, dispatch, receipt emission, worker invocation, writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerRuntimeReceiptSchemaBindingWitness Contract` records witness-only evidence for future runtime receipt schema binding while keeping binding, registry writes, dispatch, receipt emission, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerRuntimeReceiptStoreWritePathWitness Contract` records witness-only evidence for future runtime receipt-store writes while keeping writer registration, write-path registration, receipt append, dispatch, receipt emission, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerRuntimeRunnerRegistrationWitness Contract` records witness-only evidence for future live runtime runner registration while keeping runner registration, runner registry writes, dispatch endpoint registration, dispatch, receipt emission, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerRuntimeDispatchEndpointRegistrationWitness Contract` records witness-only evidence for future live dispatch endpoint registration while keeping endpoint registration, endpoint registry writes, route binding, dispatch, worker invocation, receipt emission, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerRuntimeReceiptEmitterRegistrationWitness Contract` records witness-only evidence for future live runtime receipt emitter registration while keeping emitter registration, emitter registry writes, dispatch, worker invocation, receipt emission, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerRuntimeReceiptSchemaBindingActivationWitness Contract` records witness-only evidence for future live runtime receipt schema-binding activation while keeping schema-binding activation, schema registry writes, emitter registration, dispatch, worker invocation, receipt emission, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerRuntimeReceiptStoreActivationWitness Contract` records witness-only evidence for future live runtime receipt-store activation while keeping receipt-store activation, receipt append, dispatch, worker invocation, receipt emission, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerRuntimeReceiptStoreOperatorApprovalWitness Contract` records the missing operator approval boundary for future live runtime receipt-store activation and receipt emission admission while keeping approval collection, approval grant, receipt-store activation, emission admission, receipt append, dispatch, worker invocation, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerRuntimeReceiptEmissionAdmissionWitness Contract` records witness-only evidence for future runtime receipt emission admission while keeping emission admission, receipt emission, receipt append, dispatch, worker invocation, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerRuntimeDispatchAdmissionWitness Contract` records witness-only evidence for future live runtime dispatch admission while keeping dispatch admission, runtime dispatch, worker invocation, receipt emission, receipt append, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerActiveRuntimeLeaseAdmissionWitness Contract` records witness-only evidence for future active TemporalLeaseWindowReceipt admission while keeping active lease observation, dispatch admission, runtime dispatch, worker invocation, receipt emission, receipt append, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerUaoDispatchAuthorizationWitness Contract` records witness-only evidence for future Universal Action Orchestration dispatch authorization while keeping UAO authorization, `Phi_gov` authorization, dispatch admission, runtime dispatch, worker invocation, receipt emission, receipt append, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerPhiGovDispatchAuthorizationWitness Contract` records witness-only evidence for future `Phi_gov` dispatch authorization while keeping UAO authorization, `Phi_gov` authorization, dispatch admission, runtime dispatch, worker invocation, receipt emission, receipt append, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerRuntimeActiveLeaseAdmissionWitness Contract` records witness-only evidence for future active runtime lease admission while keeping lease claims, distributed lease execution, dispatch admission, runtime dispatch, worker invocation, receipt emission, receipt append, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerEffectReconciliationWitness Contract` records witness-only evidence for future effect reconciliation after `Phi_gov` authorization while keeping reconciliation collection, dispatch admission, runtime dispatch, worker invocation, receipt emission, receipt append, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerReceiptAppendWitness Contract` records witness-only evidence for future receipt append after effect reconciliation, runtime receipt emission admission, and receipt-store activation while keeping append collection, dispatch admission, runtime dispatch, worker invocation, receipt emission, receipt append, filesystem writes, connector calls, success claims, and terminal closure unperformed.
- `ReadOnlyWorkerTerminalClosureWitness Contract` records witness-only evidence for future terminal closure after receipt append while keeping terminal closure, dispatch admission, runtime dispatch, worker invocation, receipt emission, receipt append, filesystem writes, connector calls, and success claims unperformed.
- `ReadOnlyWorkerRuntimeEnablementWitness Contract` records witness-only evidence for future runtime enablement after terminal closure while keeping runtime enablement, dispatch admission, runtime dispatch, worker invocation, receipt emission, receipt append, filesystem writes, connector calls, and success claims unperformed.
- `ReadOnlyWorkerRuntimeEnablementOperatorInputRequest Contract` records the missing evidence names operators must bind before runtime enablement can be reconsidered while keeping runtime enablement, runtime dispatch, worker invocation, receipt emission, receipt append, terminal closure, secret serialization, connector calls, and success claims unperformed.
- `ReadOnlyWorkerRuntimeEnablementEvidenceRequestStatusLedger Contract` records unresolved status for each requested runtime enablement evidence input while keeping evidence submission, acceptance, rejection, authorization, runtime enablement, dispatch, worker invocation, receipt emission, receipt append, terminal closure, connector calls, secret serialization, and success claims unperformed.
- `ReadOnlyWorkerRuntimeEnablementSubmittedEvidenceRefs Contract` records repo-local runtime enablement witness refs submitted for review while keeping evidence acceptance, rejection, authorization, runtime enablement, dispatch, worker invocation, receipt emission, receipt append, terminal closure, connector calls, secret serialization, and success claims unperformed.
- `ReadOnlyWorkerRuntimeEnablementReviewPacket Contract` reviews submitted repo-local runtime enablement refs while keeping evidence acceptance, rejection, authorization, runtime enablement, dispatch, worker invocation, receipt emission, receipt append, terminal closure, connector calls, secret serialization, and success claims unperformed.
- `ReadOnlyWorkerRuntimeEnablementEvidenceAcceptanceGate Contract` accepts the twelve reviewed runtime enablement evidence refs while keeping authority grants, runtime admission, runtime enablement, dispatch, worker invocation, receipt emission, receipt append, terminal closure, connector calls, secret serialization, and success claims unperformed.
- `ReadOnlyWorkerRuntimeEnablementAdmissionGate Contract` consumes accepted runtime enablement evidence and keeps runtime admission blocked under Foundation Mode until a future governed runtime promotion decision exists.
- `ReadOnlyWorkerRuntimeEnablementPromotionDecision Contract` records the governed Foundation Mode decision that denies runtime promotion while keeping runtime admission, runtime enablement, dispatch, worker invocation, receipt emission, receipt append, terminal closure, connector calls, secret serialization, filesystem writes, and success claims unperformed.
- `ReadOnlyWorkerRuntimeFoundationClosureSummary Contract` summarizes the complete read-only worker runtime chain as closed for Foundation Mode and blocked for live runtime authority.
- `ReadOnlyWorkerRuntimeDisablementRollbackPlan Contract` records review-only rollback evidence for future runtime enablement while keeping authority, runtime enablement, dispatch, worker invocation, receipt emission, receipt append, terminal closure, connector calls, secret serialization, filesystem writes, and success claims unperformed.
- `ReadOnlyWorkerTrustedRuntimeClockReceipt Contract` records review-only trusted runtime clock evidence for future runtime enablement while keeping authority, runtime enablement, dispatch, worker invocation, receipt emission, receipt append, terminal closure, connector calls, secret serialization, filesystem writes, and success claims unperformed.
- `ReadOnlyWorkerOperatorRuntimeEnablementApprovalRef Contract` records review-only operator approval reference evidence for future runtime enablement while keeping evidence acceptance, authority grants, runtime enablement, dispatch, worker invocation, receipt emission, receipt append, terminal closure, connector calls, secret serialization, filesystem writes, and success claims unperformed.
- `ConnectorActionPromotionGate Contract` classifies whether a connector action may move beyond plan-only status while keeping live connector calls, external writes, secret access, runtime dispatch, deployment mutation, success claims, and terminal closure denied until UAO, Phi_gov, approval, secret-access, connector-worker, and rollback evidence exists.
- `WorkerReceiptLedgerReadModel Contract` projects worker, scheduler, distributed lease, runtime handoff, runtime emitter, runner witness, schema-binding, and failure receipt status without ledger append, dispatch, backend calls, filesystem writes, connector calls, secret access, success claims, or terminal closure.
- `MfidelSubstrateConformanceReceipt Contract` records local Python Mfidel substrate digests, grid bounds, exact-preservation witnesses, no-normalization proof refs, and TypeScript/Rust SDK/kernel evidence gaps without Unicode normalization, fidel decomposition, live runtime calls, cross-runtime closure, or terminal closure.
- `ReadinessWaiverReviewPacket Contract` records waiver review scope, approval state, expiry, compensating controls, required evidence, and blocked reasons without granting readiness claims, deployment authority, runtime promotion, publication, terminal closure, or success claims.
- `BrowserObservationReceipt Contract` records hash-only URL evidence, DOM and screenshot digest refs, consent scope, capture policy refs, evidence classification refs, privacy guards, and authority denials without browser navigation, click, form-submit, cookie/session, secret, connector, publication, terminal closure, or success claims.
- `Cross-Repo Opportunity Map` records which sibling and GitHub-hosted Mullusi repositories should influence future local contracts, while blocking live connector, browser, worker, deployment, secret, and public-readiness authority in Foundation Mode.
- `MCOI Runtime` owns computer-operation-specific observation and execution runtime surfaces.
- `Mullu Govern` remains product-facing and explains governed execution to users and buyers.
- `Mullu Control Plane` remains operator-facing and consumes traces, approvals, and status from the shared foundation.

The control-plane architecture treats every executable action as a governed
structure, not as a bare function call. The minimum action object is:

```text
Action := intent + actor + tenant + capability + policy + budget + time + evidence + receipt + closure
```

This makes Mullu Control Plane a higher-order structure over executable symbols:
features become capabilities, capabilities pass through policy and authority,
effects emit evidence and receipts, and closure produces the proof surface that
operators and downstream systems can inspect.

## Current repository boundary

- Shared definitions live in `docs/` and `schemas/`.
- Rust scaffold lives under `maf/rust/`.
- MAF runtime binding remains unclaimed; receipt parity, ABI/CLI contract, subprocess effect boundary, deterministic fixture parity, failure receipt path, and runtime-binding admission are Foundation Mode witnesses, while executable runtime binding implementation remains `AwaitingEvidence`.
- Python scaffold lives under `mcoi/`.
- Cross-runtime compatibility work lives under `integration/`.

## Repository Topology Decision

The current topology is one repository:

```text
repository: mullu-control-plane
product: Mullu Govern
company: Mullusi
```

This repository may contain governance engine, policy engine, witness engine,
receipt engine, deployment engine, agent runtime, skills, gateway, SDK, APIs,
documentation, tests, and operations while the project remains in Foundation
Mode. That is an intentional monorepo posture, not a final service boundary.

Do not split this repository while the active blocker is deployment evidence.
Repository splitting is deferred until public runtime evidence and usage create
real coordination pressure.

Split triggers:

1. Issue `#330` is closed by signed deployment witness evidence.
2. Deployment witness publication passes.
3. Public runtime health is verified by witness, conformance, proof, and audit
   endpoints.
4. First external users have arrived and the operator has evidence that repo
   size, review ownership, or deployable-service boundaries are causing real
   friction.
5. At least one scale trigger exists: 50+ active users, multiple teams, or
   multiple independently deployable services.

Possible future repositories, only after those triggers:

```text
mullu-govern-web
mullu-govern-api
mullu-control-plane-core
mullu-control-plane-sdk
mullusi-docs
```

Until then, Render or any other host may point at the current
`mullu-control-plane` runtime as the current platform runtime. That deployment
target does not by itself prove the final product architecture, public runtime
health, or repository-split readiness.

## Status (2026-04-26)

Milestone 0 is complete. The platform now implements the governed
runtime end-to-end. See `docs/CORE_STRUCTURE.md` for the verified
state of the foundational layer (MAF/MCOI split, contracts, schemas,
layering) and the load-bearing-claims spec set:

- `docs/CORE_STRUCTURE.md` â€” Foundation (this layer)
- `docs/LEDGER_SPEC.md` â€” Hash-chain audit trail + external verifier
- `docs/MAF_RECEIPT_COVERAGE.md` â€” Transition-receipt coverage
- `docs/GOVERNANCE_GUARD_CHAIN.md` â€” Eight-guard chain semantics

Each spec includes a compliance posture table that distinguishes
verified from aspirational. The platform's architectural claims are
load-bearing top-to-bottom.
