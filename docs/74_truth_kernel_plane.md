<!--
Purpose: define the canonical name, boundary, and admission contract for the Mullu truth-state kernel plane.
Governance scope: naming, MAF Core truth-state responsibility, exact versus bounded result authority, proof admission, journal binding, and Foundation Mode claim boundaries.
Dependencies: docs/00_platform_overview.md, docs/01_shared_invariants.md, docs/02_shared_contracts.md, docs/03_trace_and_replay.md, docs/04_policy_and_verification.md, docs/05_learning_admission.md, docs/15_deterministic_serialization_policy.md, docs/16_world_state_plane.md, docs/27_mfidel_semantic_layer.md, docs/UNIVERSAL_ACTION_ORCHESTRATION.md, schemas/truth_candidate.schema.json, schemas/kernel_proof.schema.json, schemas/truth_commit_candidate.schema.json, examples/truth_kernel/, tests/test_truth_kernel_plane_contracts.py.
Invariants: Mullusi is the company name; Mullu is the suite/product family name; Mullu Truth Kernel is an internal MAF Core subsystem; approximate or bounded outputs cannot become truth; all truth-state mutation is proof-bound, governed, replayable, and non-public until witnessed; MTK schema contracts remain non-executing until runtime code is separately admitted.
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
| Future Rust crate | `maf-truth-kernel` | n/a | Implementation target only after contract and tests exist. |
| Future Python namespace | `mcoi_runtime.truth_kernel_adapter` | n/a | Adapter only; Python must not redefine the kernel contract. |

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
3. Add a local finite-domain proof thread with no external effects.
4. Add runtime unit tests for deterministic hashing, domain membership, closure
   idempotence, propagation monotonicity, kernel determinism, exact projection,
   forced-value uniqueness, contradiction proof, sandbox isolation, and replay.
5. Add a Rust `maf-truth-kernel` crate only after the schema and tests are
   accepted.
6. Add Python adapters only after the Rust or contract source of truth exists.

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

For this documentation-only step:

```powershell
python scripts/validate_agents_governance.py
python scripts/validate_workspace_governance_witness.py
python -m pytest tests/test_truth_kernel_plane_contracts.py -q
```

Before any implementation step:

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
  Invariants verified: Mullusi company boundary, Mullu product-family boundary, MTK internal-subsystem boundary, exact-result truth admission only, approximate-output non-promotion, Foundation Mode non-public claim, non-executing schema contract boundary
  Open issues: runtime implementation is deferred
  Next action: add a local finite-domain proof thread only after schema contract validation remains green
