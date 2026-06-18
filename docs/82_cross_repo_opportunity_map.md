# Cross-Repo Opportunity Map

Purpose: report which sibling and GitHub-hosted Mullusi repositories contain components or ideas that should be borrowed into Mullu Control Plane.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `docs/FOUNDATION_MODE.md`, `docs/00_platform_overview.md`, `docs/10_external_integration_plane.md`, `docs/20_code_automation_plane.md`, `docs/27_mfidel_semantic_layer.md`, `docs/56_general_agent_capability_roadmap.md`, `docs/61_temporal_scheduler_runbook.md`, `docs/80_read_only_worker_binding_contract.md`, `schemas/universal_action_orchestration.schema.json`, `schemas/worker_failure_receipt.schema.json`.
Invariants: recommendations do not import live authority; recommendations do not read secrets; recommendations do not call external connectors; recommendations do not activate runtime dispatch; recommendations do not claim production readiness; Mfidel atomicity is preserved.

## 1. Boundary

This report is an opportunity map, not an implementation grant.

It was compiled from:

| Source | Evidence surface inspected | Useful control-plane fit |
| --- | --- | --- |
| `external/nested-mind-platform` | local README and Rust workspace manifest | Runtime evidence contracts, SQLite ledgers, worker receipts, connector orchestration, readiness gates, waiver review, action-promotion gates |
| `maf/rust` | local Rust workspace manifest | Rust crate partitioning for kernel, capability, event, governance, orchestration, ops, learning, and truth-kernel surfaces |
| GitHub repository inventory | `gh repo list tamirat-wubie --limit 50` | Repository families for Mfidel substrate, SCCML, VIRECAI, search, browser inspection, symbolic kernels, and domain engines |
| `mullu-control-plane` current main | docs, schemas, scripts, examples, tests | Existing contracts for UAO, search, temporal scheduling, worker receipts, read-only worker binding, and personal-assistant projections |

Foundation Mode applies. Borrowing means translating proven ideas into local, reversible, schema-backed contracts before runtime execution. It does not mean copying live code or importing external authority.

## 2. Already Borrowed Into Main

The control plane already absorbed several high-fit ideas:

| Borrowed idea | Current control-plane surface | Status |
| --- | --- | --- |
| Search before retrieval | `SearchDecision` and `SearchReceipt` contracts | Implemented |
| Temporal scheduler evidence | temporal receipt family and scheduler runbook | Implemented |
| Worker failure as non-terminal evidence | `WorkerFailureReceipt` | Implemented |
| Read-only worker path | `ReadOnlyWorkerBinding` and runtime witness chain | Implemented |
| Scheduler-worker runtime receipt dry-run | `SchedulerWorkerRuntimeReceiptEmitterDryRun` | Implemented |
| Worker receipt ledger projection | `WorkerReceiptLedgerReadModel` | Implemented |
| Personal-assistant projections without effects | personal-assistant read-only, approval, research, GitHub/Codex, and math projections | Implemented |
| Mfidel substrate conformance witness | `MfidelSubstrateConformanceReceipt` | Implemented |
| Readiness gate and waiver review | `ReadinessWaiverReviewPacket` | Implemented |
| Browser inspection boundary | `BrowserObservationReceipt` | Implemented |
| Research source disagreement preservation | `ResearchSourceConflictMap` | Implemented |
| Capture policy and trusted reality evidence packet | `TrustedCaptureEvidencePacket` | Implemented |
| SCCML trace adapter boundary | `SccmlTraceAdapterWitness` | Implemented |
| Chaos rehearsal dry-run evidence | `ChaosRehearsalExecutionReport` | Implemented |
| Invariant fuzz execution evidence | `InvariantFuzzExecutionReport` | Implemented |
| MAF receipt parity boundary | `MafReceiptParityWitness` | Implemented |
| MAF ABI/CLI contract boundary | `MafAbiCliContractWitness` | Implemented |
| MAF subprocess effect boundary | `MafSubprocessEffectBoundaryWitness` | Implemented |
| MAF deterministic fixture parity boundary | `MafDeterministicFixtureParityWitness` | Implemented |
| MAF failure receipt path boundary | `MafFailureReceiptPathWitness` | Implemented |
| SWEWS world substrate replay evidence | `WorldSubstrateReplayWitness` | Implemented |

The next borrowed work should therefore avoid duplicating these surfaces and instead close adjacent gaps.

## 3. Ranked Borrow Candidates

| Rank | Source family | Borrow candidate | Why it matches Mullu Control Plane | Foundation Mode implementation |
| --- | --- | --- | --- | --- |
| 1 | `external/nested-mind-platform` v25 | Connector orchestration and action-promotion gate | The control plane has connector descriptors and UAO, but still needs a promotion gate that proves a connector action moved from plan-only to admissible authority without bypassing receipts. | Add `ConnectorActionPromotionGate` schema, example, validator, proof-matrix row, and docs. Keep `promotion_allowed=false` until all live evidence exists. |
| 2 | `external/nested-mind-platform` v17-v20 | Readiness gate, waiver proposal, waiver certificate, waiver application | Release, deployment, and runtime promotion already use readiness claims; waiver handling needs a typed review queue instead of scattered accepted-risk notes. | Add a `ReadinessWaiverReviewPacket` contract with operator approvals, expiry, compensating controls, and no deployment authority. |
| 3 | `external/nested-mind-platform` v18-v19 | Chaos rehearsal and invariant fuzz execution reports | Control-plane validators prove static contracts well, but runtime resilience claims need rehearsal evidence before production exposure. | Implemented as dry-run `ChaosRehearsalExecutionReport` and `InvariantFuzzExecutionReport`; future live use remains blocked pending staging boundary, rollback, incident, and operator approval witnesses. |
| 4 | `external/nested-mind-platform` v14-v16 | SQLite-backed job receipt and distributed lease execution ledger | Scheduler-worker proof threads now exist, but there is no operator read model summarizing lease, worker, failure, and runtime receipt chain status. | Add `WorkerReceiptLedgerReadModel` that projects existing receipts without executing jobs or reading a live database. |
| 5 | `maf/rust` | MAF receipt parity boundary | The Rust workspace is organized into kernel, capability, event, governance, orchestration, ops, learning, and truth-kernel crates, but Python control-plane claims need explicit staged witnesses before runtime binding. | Implemented as `MafReceiptParityWitness`, `MafAbiCliContractWitness`, `MafSubprocessEffectBoundaryWitness`, `MafDeterministicFixtureParityWitness`, and `MafFailureReceiptPathWitness`; executable runtime binding remains a separate implementation thread. |
| 6 | `external/swews-core` | Future world substrate runtime adapter | `WorldSubstrateReplayWitness` covers digest-only replay admission, but live world runtime binding remains unavailable. | Defer adapter code until replay witnesses, SQLite boundaries, service-call receipts, rollback plans, and branch quarantine evidence are all verified. |
| 7 | `msic-sdk`, `tatoken-kernel`, `tarc-core` | Mfidel substrate conformance witness | Mfidel atomicity is a hard invariant, but SDK/kernel drift can still occur across TypeScript, Python, and Rust implementations. | Add `MfidelSubstrateConformanceReceipt` with substrate digest, row/column bounds, no-normalization proof refs, and cross-runtime fixture refs. |
| 8 | `Virecai` | Capture policy and trusted reality evidence packet | Control-plane capture policy exists, but future browser, screen, video, and sensor receipts need a standard evidence envelope before any live capture. | Extend capture-policy work with a `TrustedCaptureEvidencePacket` dry-run contract. Keep media capture, file writes, and connector calls denied. |
| 9 | `mullu-inspect`, `mullu-browser` | Browser observation receipt | Browser inspection is valuable for operator evidence, but it must be separated from navigation control and external effect authority. | Add a `BrowserObservationReceipt` contract for URL hash, DOM digest, screenshot digest ref, consent scope, and no-click/no-submit/no-secret flags. |
| 10 | `mullu-search` | Research source conflict map | Search decisions and receipts exist, but the control plane should preserve disagreements across sources as first-class operator evidence. | Add `ResearchSourceConflictMap` as a read-only receipt that binds citation refs, freshness, contradiction class, and follow-up sensing needs. |

## 4. Do Not Borrow Yet

| Source idea | Reason to defer | Required witness before reconsideration |
| --- | --- | --- |
| Live connector workers from `external/nested-mind-platform` v23-v25 | They cross secret, external endpoint, token, and notification boundaries. | Secret access receipt, connector worker execution receipt, UAO admission, `Phi_gov` authorization, and rollback evidence. |
| Direct production Kubernetes chaos execution | It is world-changing and can damage runtime state. | Staging-only dry-run proof, cluster boundary witness, rollback plan, and operator approval chain. |
| Direct browser/app control from `mullu-inspect` or `mullu-browser` | Inspection can become mutation through click, form submit, cookie, or session effects. | Browser observation receipt, consent boundary, no-secret policy, and click/submit approval gate. |
| Direct Rust runtime binding from `maf/rust` | The current repository states receipt-shape parity, ABI/CLI contract evidence, subprocess boundary evidence, static deterministic fixture parity, and static failure receipt path evidence, but not executable Python runtime binding. | UAO admission, implementation design, rollback evidence, runtime execution receipts, and terminal closure evidence. |
| Direct search ingestion from `mullu-search` | Search may collect stale, private, copyrighted, or instruction-bearing content. | Search decision, source-scope policy, citation receipt, conflict map, and raw-body retention denial. |

## 5. Recommended Implementation Sequence

1. `ConnectorActionPromotionGate`
   - Highest leverage because it closes the gap between connector descriptors, UAO, and future live action execution.
   - Must remain plan-only in Foundation Mode.

2. MAF runtime binding implementation witness
   - Follows `MafFailureReceiptPathWitness` and proves executable binding behavior only after UAO admission, rollback evidence, runtime execution receipts, and explicit operator authority.
   - Must remain `AwaitingEvidence` until implementation evidence exists without overclaiming static witnesses as execution authority.

## 6. Project Discipline Mesh Findings

| Discipline | Lens finding | Gap or pass | Fix |
| --- | --- | --- | --- |
| Strategy/Product | Borrowed components should enhance operator proof, connector promotion, worker receipt visibility, and substrate conformance before public exposure. | Pass | Prioritize the top five sequence items. |
| Design/Research | Operator-facing evidence needs read models and conflict maps, not more hidden backend state. | Gap | Add receipt-ledger and source-conflict projections before live execution UX. |
| Engineering | Current contracts are strong for dry-run proof; connector promotion and runtime ledgers remain fragmented. | Gap | Add schema-backed promotion gate and ledger read model. |
| Quality/Security | Live connector and browser ideas cross authority, secret, external endpoint, and session boundaries. | Gap | Keep all borrowed ideas dry-run until UAO, `Phi_gov`, and rollback receipts exist. |
| Operations | Readiness and waiver evidence exists conceptually but should be routable through typed packets. | Gap | Add waiver review and readiness execution contracts before production promotion. |
| Business/GTM | Public capability claims would be premature without production witnesses. | Pass | Keep report Foundation Mode-local and avoid customer-readiness language. |

## 7. Outcome

`SolvedVerified` for repository-local opportunity identification.

Runtime implementation remains `AwaitingEvidence` for any live connector, browser, worker, deployment, or external endpoint action.
