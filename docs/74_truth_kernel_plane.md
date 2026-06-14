<!--
Purpose: define the canonical name, boundary, and admission contract for the Mullu truth-state kernel plane.
Governance scope: naming, MAF Core truth-state responsibility, exact versus bounded result authority, proof admission, journal binding, adapter admission, finite-domain proof threading, and Foundation Mode claim boundaries.
Dependencies: docs/00_platform_overview.md, docs/01_shared_invariants.md, docs/02_shared_contracts.md, docs/03_trace_and_replay.md, docs/04_policy_and_verification.md, docs/05_learning_admission.md, docs/15_deterministic_serialization_policy.md, docs/16_world_state_plane.md, docs/27_mfidel_semantic_layer.md, docs/UNIVERSAL_ACTION_ORCHESTRATION.md, schemas/truth_candidate.schema.json, schemas/kernel_proof.schema.json, schemas/truth_commit_candidate.schema.json, examples/truth_kernel/, mcoi/mcoi_runtime/truth_kernel_adapter.py, mcoi/mcoi_runtime/truth_kernel_finite_domain.py, maf/rust/crates/maf-truth-kernel/, tests/test_truth_kernel_plane_contracts.py, tests/test_truth_kernel_admission.py, tests/test_truth_kernel_finite_domain.py.
Invariants: Mullusi is the company name; Mullu is the suite/product family name; Mullu Truth Kernel is an internal MAF Core subsystem; approximate or bounded outputs cannot become truth; all truth-state mutation is proof-bound, governed, replayable, and non-public until witnessed; the Python adapter admits or rejects schema-bound commit candidates but does not mutate truth state; finite-domain proof threads emit replayable proof payloads but do not execute external actions.
-->

# Mullu Truth Kernel Plane

<!-- TYPE: Reference -->
<!-- AUDIENCE: architecture maintainers, kernel implementers, governance reviewers -->

> **In one box:** This page names the internal kernel that checks what can be
> treated as true inside the platform. Mullusi is the company, Mullu is the
> product family, and the kernel itself is called the Mullu Truth Kernel.
>
> This is a local architecture contract, not a launch claim and not a runtime
> readiness claim.

---

## Naming Decision

Canonical naming:

| Role | Canonical name | Short name | Rule |
| --- | --- | --- | --- |
| Company | Mullusi | n/a | Company name only; do not use as a subsystem name. |
| Product family | Mullu | n/a | Suite and family name. |
| Product | Mullu Govern | n/a | Public governed-execution product name. |
| Control surface | Mullu Control Plane | n/a | Operator/admin governance surface in this repository. |
| Shared substrate | MAF Core | MAF | Kernel-facing interfaces and shared runtime primitives. |
| Current runtime package | MCOI Runtime | MCOI | Existing governed runtime package. |
| Truth-state subsystem | Mullu Truth Kernel | MTK | Internal MAF Core subsystem for domains, constraints, kernel checks, and proofs. |
| Architecture plane | Truth Kernel Plane | TKP | Documentation and contract boundary for MTK. |
| Rust crate | `maf-truth-kernel` | n/a | Side-effect-free finite-domain kernel substrate under `maf/rust/crates/`. |
| Python adapter namespace | `mcoi_runtime.truth_kernel_adapter` | n/a | Adapter only; Python must not redefine the kernel contract or mutate truth state. |
| Python finite proof thread | `mcoi_runtime.truth_kernel_finite_domain` | n/a | Local finite-domain proof emitter; no external effects and no truth-state writes. |

Rejected or archival names:

| Name | Status | Reason |
| --- | --- | --- |
| Mullusi Symbolic Runtime | Retired draft name | Mullusi is the company, not the runtime subsystem. |
| MSR-HSK-F3 | Archival design-note label | Useful for provenance, not canonical repository naming. |
| Hardened Symbolic Kernel F3 | Archival kernel label | Too versioned and final-sounding for Foundation Mode. |

## Responsibility

The [Truth Kernel Plane](GLOSSARY.md#truth-kernel--truth-kernel-plane) owns the
local answer to this question:

```text
Given declared domains, admitted constraints, and a candidate state,
is the state valid, invalid, contradictory, unknown, or budget-limited?
```

It is responsible for:

| Area | Responsibility |
| --- | --- |
| Identity | Stable IDs, signatures, canonical ordering, and deterministic hashes. |
| Domains | Versioned variable domains and membership checks. |
| Constraints | Immutable constraint records with explicit status and scope. |
| Closure | Deterministic derived consequences from admitted constraints. |
| Propagation | Sound pruning of impossible values before search. |
| Kernel check | Validity judgment for complete candidate states. |
| Projection | Possible-value queries with exact, bounded, approximate, or unknown status. |
| Forced values | Values proven true in every valid state. |
| Proofs | Replayable proof objects for validity, invalidity, projection, forced value, contradiction, and commit. |
| Journal binding | Truth-state commits linked to trace and replay surfaces. |

It is not responsible for:

| Area | Owner |
| --- | --- |
| Policy allow/deny decisions | [Policy and Verification](04_policy_and_verification.md) |
| Effect-bearing action orchestration | [Universal Action Orchestration](UNIVERSAL_ACTION_ORCHESTRATION.md) |
| External tool or connector execution | Capability and adapter planes |
| Learning admission | [Learning Admission](05_learning_admission.md) |
| World observation capture | Perception or world-state producers |
| Public deployment evidence | Deployment witness and production-readiness docs |

## Relationship To Existing Repository

MTK complements the current platform. It does not replace MCOI, UAO, policy,
receipts, or replay.

| Existing surface | Existing role | MTK relationship |
| --- | --- | --- |
| [Shared Invariants](01_shared_invariants.md) | System-wide rules that cannot be broken. | MTK must satisfy them and may add local truth-state invariants. |
| [Shared Contracts](02_shared_contracts.md) | Cross-runtime data contracts. | MTK may add future contracts, but cannot redefine existing ones. |
| [Trace and Replay](03_trace_and_replay.md) | Causal record and deterministic replay. | MTK commits must emit trace entries and replayable proof references. |
| [Policy and Verification](04_policy_and_verification.md) | Action gate and closure. | MTK can inform policy, but cannot approve execution by itself. |
| [Learning Admission](05_learning_admission.md) | Gate for new knowledge entering planning. | Learned constraints require admission before they influence MTK. |
| [World State Plane](16_world_state_plane.md) | Evidence-derived world model. | MTK validates candidate world-state claims when exact truth-state checks are available. |
| [Mfidel Semantic Layer](27_mfidel_semantic_layer.md) | Atomic Mfidel symbol handling. | MTK must preserve fidel atomicity when domains or constraints include Mfidel symbols. |
| [Universal Action Orchestration](UNIVERSAL_ACTION_ORCHESTRATION.md) | Effect-bearing action envelope. | MTK proof may be cited as evidence inside UAO, but cannot bypass UAO. |

## Layer Scope

MTK starts with L0-L2 only.

| Layer | Included now | Deferred |
| --- | --- | --- |
| L0 identity | IDs, signatures, canonical ordering, deterministic serialization. | Distributed identity federation. |
| L1 truth core | domains, constraints, closure, propagation, kernel checks, projections, forced values, proofs. | Kernel geometry, compression, planner, simulation, perception. |
| L2 protection | sandboxed proposal evaluation, proof witness refs, atomic truth commit, journal replay. | Autonomous repair authority, learned hard-rule promotion, public runtime claims. |

Deferred MSR-HSK-F3 draft modules remain conceptually useful but are not
admitted as active repository scope until a later contract names their tests,
owners, and rollback paths.

## Truth Admission Contract

Truth-state mutation follows this path:

```text
TruthCandidate
  -> sandbox evaluation
  -> deterministic closure and propagation
  -> kernel check or query proof
  -> ProofState
  -> governance reference
  -> atomic truth commit candidate
  -> trace entry
  -> journal replay check
```

Admission rules:

| Result kind | Can answer query? | Can support planning? | Can mutate truth? | Required handling |
| --- | --- | --- | --- | --- |
| `ExactResult` | Yes | Yes | Yes, only with proof and governance ref | Store proof and trace. |
| `ContradictionResult` | Yes | Blocks dependent planning | No | Emit contradiction proof and repair candidate if available. |
| `BoundedResult` | Yes, with bounds | Only as bounded advisory input | No | Carry budget and incompleteness reason. |
| `ApproximateResult` | Yes, advisory only | Only where policy permits advisory ranking | No | Mark as non-truth evidence. |
| `UnknownResult` | Yes, as unknown | No for hard constraints | No | Block hard action and plan sensing. |
| `BudgetExceededResult` | Yes, as budget-limited | No for hard constraints | No | Record budget and required next evidence. |

Hard invariant:

```text
result.kind in {BoundedResult, ApproximateResult, UnknownResult, BudgetExceededResult}
  -> cannot_promote_truth
```

Forced values require exact uniqueness proof:

```text
ForcedValue(v) = a
  -> ExactProjection(v) = {a}
  or uniqueness_proof(v, a) = Pass
```

Confidence can rank evidence, but confidence is not proof:

```text
confidence_score != proof
confidence_score cannot upgrade ApproximateResult into ExactResult
```

## Schema Contracts

The first MTK contract artifacts are documentation and validation shapes only.
They do not execute a kernel, dispatch actions, write memory, or commit truth.

| Schema | Purpose | Example |
| --- | --- | --- |
| `schemas/truth_candidate.schema.json` | Describes a proposed truth-state delta and its proof obligations. | `examples/truth_kernel/truth_candidate.exact_constraint_addition.json` |
| `schemas/kernel_proof.schema.json` | Describes replayable proof for a truth-kernel result. | `examples/truth_kernel/kernel_proof.exact_projection.json` |
| `schemas/truth_commit_candidate.schema.json` | Describes a proof-bound, governance-bound truth commit candidate. | `examples/truth_kernel/truth_commit_candidate.exact_constraint_addition.json` |

Contract tests live in `tests/test_truth_kernel_plane_contracts.py`.

## Runtime Adapter

The first executable MTK surface is the schema-bound Python adapter
`mcoi_runtime.truth_kernel_adapter`. It is intentionally narrow:

| Adapter responsibility | Rule |
| --- | --- |
| Cross-reference binding | Candidate, proof, and commit candidate IDs, tenant IDs, proof refs, and kernel signatures must match. |
| Exactness gate | `proof_state = Pass` and `result_kind = ExactResult` are required for truth mutation. |
| Replay gate | Proof replay must be deterministic and the commit journal must require replay. |
| Replay hash gate | Commit journal replay hash must equal the proof replay expected hash. |
| Governance gate | Governance, trace, rollback, and admission reason references must be present. |
| Sandbox gate | Mutation candidates must require sandbox isolation and the proof must carry `witness:sandbox-isolated`. |
| Mfidel gate | Any Mfidel-bearing delta must preserve atomicity. |
| State boundary | The adapter returns an admission decision only; it does not write truth state. |

Runtime admission tests live in `tests/test_truth_kernel_admission.py`.

## Finite-Domain Proof Thread

`mcoi_runtime.truth_kernel_finite_domain` is the first local proof thread. It
is deliberately smaller than the future Rust kernel:

| Proof-thread responsibility | Rule |
| --- | --- |
| Domain membership | Every projected value must come from a declared finite domain. |
| Constraint evaluation | Allowed and forbidden assignments are checked as total finite relations. |
| Propagation | Exact propagation emits projected values, pruned values, and forced values from the finite valid-state closure. |
| Closure idempotence | Re-running the same finite closure with the same budget yields the same closure hash. |
| Closure proof payload | Exact closure can emit a schema-compatible `ValidityProof` with enumeration, constraint, closure, and forced-value derivation steps. |
| Exact projection | Exact proof is emitted only when all candidate states fit within budget. |
| Contradiction proof | Empty valid-state sets emit `ContradictionResult`, not truth mutation authority. |
| Budget proof | Budget exhaustion emits `BudgetExceededResult` with `BudgetUnknown`; it cannot become truth. |
| Replay binding | Proof payloads carry deterministic replay hashes and validate against `schemas/kernel_proof.schema.json`. |
| Sandbox witness | Generated proof payloads include `witness:sandbox-isolated` before adapter admission can grant mutation authority. |
| Mfidel boundary | Mfidel-bearing domains must preserve atomic symbol identity. |

Finite-domain proof tests live in `tests/test_truth_kernel_finite_domain.py`.

Generated proof payloads are wired into commit-candidate fixtures through
`build_truth_commit_candidate_from_proof(...)` and then checked by
`admit_truth_commit_candidate(...)`. The builder is deterministic and
non-mutating; the adapter remains the authority gate. Budget-limited and
contradicted proofs can still produce recordable commit-candidate-shaped
objects, but the adapter rejects them before mutation authority.

Finite closure and propagation are read models. They can identify forced values
and pruned values, but a forced value still needs an exact projection proof and
adapter admission before it can support a truth mutation.

Multi-step closure proof payloads are now emitted as `ValidityProof` objects.
They are replayable evidence for the finite closure, not a state write. A
budget-limited closure proof remains recordable, but the adapter rejects it
before mutation authority because `BudgetUnknown` cannot satisfy the exact
truth-admission gate.

## Rust Kernel Substrate

`maf/rust/crates/maf-truth-kernel` is the first Rust-side MTK substrate. It
matches the Python finite-domain boundary but remains narrower than a full
production kernel:

| Rust substrate responsibility | Rule |
| --- | --- |
| Workspace placement | The crate is a `maf/rust` workspace member and is covered by the existing Rust CI `cargo test` job. |
| State boundary | The crate is pure and does not mutate truth state, journals, memory, files, or external systems. |
| Exact projection | Exact projection emits `Pass` plus `ExactResult` only when all finite states fit within budget. |
| Budget gate | Budget exhaustion emits `BudgetUnknown` plus `BudgetExceededResult`, never mutation authority. |
| Contradiction gate | Empty valid-state sets emit `ContradictionResult` with a no-valid-state witness. |
| Sandbox witness | Projection proofs always preserve `witness:sandbox-isolated`. |
| Replay binding | Proof summaries carry deterministic replay hashes and proof hashes. |
| Mfidel boundary | Mfidel-bearing domains fail closed unless atomicity is declared preserved. |
| Fixture parity | Rust and Python finite projection summaries share `examples/truth_kernel/truth_kernel_finite_projection_summary.json`. |

Rust unit tests live inside `maf/rust/crates/maf-truth-kernel/src/lib.rs`.
Run them with:

```powershell
cargo test -p maf-truth-kernel
```

## Current Proof Boundary Checklist

This checklist defines what can be claimed today. It is the review boundary for
MTK changes until a later commit-journal writer and production kernel runtime
are admitted.

| Boundary | Current status | Required witness |
| --- | --- | --- |
| Naming | Closed | This document keeps Mullusi as company, Mullu as product family, and Mullu Truth Kernel as internal subsystem. |
| Schema contracts | Closed | `truth_candidate`, `kernel_proof`, and `truth_commit_candidate` schemas validate with examples. |
| Python admission adapter | Closed for admission decisions | Adapter accepts or rejects schema-bound commit candidates and never mutates truth state. |
| Python finite proof thread | Closed for local finite domains | Exact, contradiction, budget, closure, propagation, replay, sandbox, and Mfidel tests pass. |
| Rust finite substrate | Closed for pure finite-domain projection | `maf-truth-kernel` emits deterministic exact, contradiction, budget, replay, sandbox, and Mfidel outcomes. |
| Rust schema proof emitter | Closed for schema-shaped projection proofs | Rust-emitted `KernelProof` fixture validates against `schemas/kernel_proof.schema.json` and is admitted by the Python adapter. |
| Cross-language parity | Closed for projection summary parity | Rust and Python share `examples/truth_kernel/truth_kernel_finite_projection_summary.json`. |
| Truth-state mutation | Deferred | No commit journal writer is admitted. Adapter admission is not a state write. |
| Public runtime readiness | Deferred | Foundation Mode keeps public claims at `AwaitingEvidence` until live witnesses exist. |

Do not claim more than this checklist. A change that adds mutation authority,
production runtime authority, external effects, learned hard-rule promotion, or
public readiness must introduce its own SDLC requirement, rollback path,
security review, and governance receipt.

## Commit Boundary

MTK truth commits are local state changes, so they are effect-bearing inside the
repository even when they do not touch the outside world.

Every truth commit candidate must carry:

| Field | Meaning |
| --- | --- |
| `candidate_id` | Stable identifier for the proposed truth-state delta. |
| `parent_kernel_signature` | Kernel signature before the proposal. |
| `delta_kind` | Domain addition, constraint addition, constraint quarantine, status change, or proof attachment. |
| `proof_ref` | Replayable proof reference. |
| `witness_refs` | Supporting examples, counterexamples, or replay traces. |
| `policy_ref` | Governance or policy decision reference. |
| `rollback_ref` | Replay or prior-signature path. |
| `new_kernel_signature` | Deterministic signature after accepted commit. |

Commit cannot proceed when any required field is missing.

## Mfidel Boundary

If MTK domains or constraints include Amharic, Ge'ez, or Mfidel symbols, the
kernel must treat each fidel as atomic.

Rules:

1. No Unicode decomposition, recomposition, or normalization for fidel symbols.
2. No root-letter model.
3. No split of fidel into consonant and vowel structure for text processing.
4. Sound overlays may be represented only as sound-layer relations, never as
   structural decomposition.
5. Kernel signatures over fidel domains must preserve the original atomic
   symbol identity.

## Implementation Sequence

Use this order:

1. Keep this document as the canonical naming and boundary contract.
2. Keep schemas for `TruthCandidate`, `KernelProof`, and
   `TruthCommitCandidate` aligned with examples and tests.
3. Keep the schema-bound Python adapter pure and non-mutating.
4. Keep the local finite-domain proof thread side-effect-free and schema-bound.
5. Keep Rust and Python proof behavior aligned through deterministic projection, closure,
   budget, contradiction, sandbox-witness, replay-hash, and Mfidel tests.
6. Add broader runtime unit tests for deterministic hashing, domain membership, closure
   idempotence, propagation monotonicity, kernel determinism, exact projection,
   forced-value uniqueness, contradiction proof, sandbox isolation, and replay.
7. Extend Python adapters only after the Rust or contract source of truth exists.

## Non-Goals

MTK does not:

1. Launch a new product.
2. Replace Mullu Govern, Mullu Control Plane, MAF Core, or MCOI Runtime.
3. Prove public runtime readiness.
4. Execute external actions.
5. Admit learned knowledge without the learning admission gate.
6. Promote approximate or bounded outputs into truth.
7. Weaken Mfidel atomicity.

## Required Validators

For schema and adapter steps:

```powershell
python scripts/validate_agents_governance.py
python scripts/validate_workspace_governance_witness.py
python -m pytest tests/test_truth_kernel_plane_contracts.py -q
python -m pytest tests/test_truth_kernel_admission.py -q
python -m pytest tests/test_truth_kernel_finite_domain.py -q
cd maf/rust
cargo test -p maf-truth-kernel
```

Before broader implementation steps:

```powershell
python scripts/validate_sdlc_artifact.py
python scripts/validate_sdlc_state_machine.py
python scripts/validate_universal_action_orchestration.py
python scripts/detect_uao_runtime_bypass.py
python scripts/run_workspace_governance_checks.py
```

Implementation tests must be added with the first code-bearing MTK change.

---

## Go deeper / where to go next

| You now want to... | Go to |
| --- | --- |
| Understand the platform boundary | [Platform Overview](00_platform_overview.md) |
| Check the rules that cannot break | [Shared Invariants](01_shared_invariants.md) |
| Understand trace and replay | [Trace and Replay](03_trace_and_replay.md) |
| Understand learning admission | [Learning Admission](05_learning_admission.md) |
| Understand world-state evidence | [World State Plane](16_world_state_plane.md) |
| Look up a confusing word | [Glossary](GLOSSARY.md) |
| See the whole documentation map | [Start Here](START_HERE.md) |

<- Back to [Start Here](START_HERE.md)

STATUS:
  Completeness: 100%
  Invariants verified: Mullusi company boundary, Mullu product-family boundary, MTK internal-subsystem boundary, exact-result truth admission only, approximate-output non-promotion, Foundation Mode non-public claim, schema-bound non-mutating adapter boundary, finite-domain proof thread non-effect boundary, Rust finite-domain substrate non-effect boundary, Rust schema proof emitter boundary, sandbox-isolation witness gate, replay-hash equality gate
  Open issues: full production kernel persistence, commit journal writer, byte-identical full proof-payload parity, and public runtime readiness remain deferred
  Next action: add a commit-journal writer only after a separate SDLC requirement, rollback plan, security review, and governance receipt exist
