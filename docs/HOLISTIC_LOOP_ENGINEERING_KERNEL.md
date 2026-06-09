# Mullu Holistic Loop Engineering Kernel v1

Purpose: define the shared governed loop contract used to describe existing Mullu loops without changing their runtime behavior.
Governance scope: loop manifests, loop state projections, step receipts, closure reports, registry exposure, evidence bindings, evidence blockers, rollback policy, and learning policy.
Dependencies: `mcoi_runtime.contracts.holistic_loop`, `mcoi_runtime.core.holistic_loop_registry`, existing deployment witness, runtime conformance, cognitive outcome, and governed code-change surfaces.
Invariants: this is a read-model-first contract layer; it adds no public mutation route; it does not rewrite deployment, cognitive, proof verification, or code-change behavior.

## Architecture

Mullu now exposes a common loop contract for governed processes:

```text
observe
-> decide
-> act
-> verify
-> record_receipt
-> update_state
-> learn
-> audit
-> repeat or close
```

The kernel models the common contract through:

| Record | Role |
| --- | --- |
| `LoopManifest` | Static purpose, owner, authority, evidence, closure, rollback, and learning contract. |
| `LoopState` | Current read-only status, phase, mode, receipt, blockers, and evidence refs. |
| `LoopStepReceipt` | Step-level input hash, output hash, decision, evidence, status, errors, and timestamp. |
| `LoopClosureReport` | Closure assessment with unresolved gaps, rollback availability, and learning candidates. |
| `LoopEvidenceBinding` | Read-only map from each required evidence label to source refs, validator refs, and proof surfaces. |
| `LoopRegistry` | Immutable registry binding manifests to read-only states. |
| `LoopReadModel` | Bounded loop summary projection for dashboards, docs, and validators. |

## Registered Loops

| Loop ID | Purpose | Runtime behavior changed |
| --- | --- | --- |
| `deployment_witness_loop` | Describes endpoint publication, runtime witness, conformance, audit, proof, and authority evidence for deployment closure. | No |
| `runtime_conformance_loop` | Describes signed runtime conformance collection and certificate validation. | No |
| `cognitive_outcome_loop` | Describes observe, decide, act, verify, learn, and audit evidence for cognitive outcome recording. | No |
| `governed_code_change_loop` | Describes lease-bound code-worker execution, SDLC receipt requirements, rollback handoff, and terminal closure blockers. | No |

## Evidence Rule

Missing required evidence is a blocker:

```text
required_evidence - evidence_refs -> missing_evidence
missing_evidence -> open_blockers: missing_evidence:<name>
open_blockers != empty -> status = blocked
```

This prevents fake closure. A loop may report runtime health or worker execution evidence, but the read model remains blocked until the manifest's evidence requirements and closure conditions are satisfied.

## Evidence Catalog

Each loop summary includes `evidence_bindings`. A binding is a read-only catalog
entry for one `required_evidence` label:

| Field | Meaning |
| --- | --- |
| `evidence_ref` | The required evidence label the binding explains. |
| `purpose` | Why the evidence is required for loop closure. |
| `source_refs` | Existing files, schemas, or scripts that define or collect the evidence. |
| `validator_refs` | Existing tests or validators that check the referenced evidence surface. |
| `proof_surface_refs` | Proof-matrix surface IDs related to the evidence. |
| `read_only` | Always `true`; bindings do not execute collection or validation. |
| `terminal_closure` | Always `false`; bindings are not closure certificates. |

The catalog is exact by contract:

```text
set(evidence_bindings[*].evidence_ref) == set(required_evidence)
```

Missing, duplicate, or extra bindings are validation failures. The catalog does
not replace live evidence. It only tells operators where proof must come from
when a later loop-specific adapter or closure workflow runs.

## Boundary

This kernel is intentionally non-invasive:

1. It does not call deployment witness collection.
2. It does not call runtime conformance collection.
3. It does not construct or run the cognitive loop.
4. It does not dispatch governed code-change workers.
5. It does not create a public mutation route.
6. It does not execute evidence validators referenced by the catalog.
7. It only exposes typed read-model contracts that other surfaces can adopt later.

## Read-Only Exposure

The default MCOI HTTP router now mounts one read-only loop endpoint:

```text
GET /api/v1/loops/read-model
```

The endpoint returns the same bounded loop summary surface as the local report
script:

| Field | Meaning |
| --- | --- |
| `read_model_id` | Stable identifier: `holistic_loop_read_model`. |
| `read_model_version` | Contract version: `holistic_loop_kernel.v1`. |
| `status` | `blocked` while any returned loop has blockers; otherwise `verified`. |
| `loops` | Bounded registered loop summaries. |
| `loops[].evidence_bindings` | Read-only evidence catalog entries covering every required evidence label. |
| `blocked_count` | Count of returned summaries carrying blockers. |
| `verified_count` | Count of returned summaries marked verified. |
| `read_only` | Always `true`. |
| `report_is_not_terminal_closure` | Always `true`; this route is not a closure certificate. |
| `terminal_closure_required` | Always `true`; live closure still requires loop-specific proof. |

The route has no POST, PUT, PATCH, or DELETE companion. It is a projection over
the registry contract, not an execution surface.

## Verification

Focused tests:

```powershell
python -m pytest mcoi/tests/test_holistic_loop_kernel.py mcoi/tests/test_holistic_loop_router.py tests/test_report_holistic_loop_read_model.py tests/test_validate_holistic_loop_read_model.py tests/test_validate_holistic_loop_http_surface.py tests/test_proof_coverage_matrix.py
```

Read-only report:

```powershell
python scripts/report_holistic_loop_read_model.py --json
```

Read-model contract validation:

```powershell
python scripts/validate_holistic_loop_read_model.py
```

HTTP read-model surface validation:

```powershell
python scripts/validate_holistic_loop_http_surface.py
```

The tests verify:

1. The first four loops are registered.
2. Each loop exposes purpose, authority, evidence requirements, and closure conditions.
3. Missing evidence becomes blockers.
4. Complete evidence can verify the read model without executing runtime behavior.
5. Explicit blockers override complete evidence.
6. Step receipts and closure reports are typed and immutable.
7. The HTTP read-model route is mounted read-only and has no mutation companion.
8. Evidence bindings cover every required evidence label and cannot claim terminal closure.
