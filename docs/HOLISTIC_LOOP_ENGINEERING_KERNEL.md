# Mullu Holistic Loop Engineering Kernel v1

Purpose: define the shared governed loop contract used to describe existing Mullu loops without changing their runtime behavior.
Governance scope: loop manifests, loop state projections, step receipts, closure reports, registry exposure, status bindings, mode bindings, closure condition bindings, risk bindings, evidence bindings, evidence blockers, rollback policy, learning bindings, and learning policy.
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
| `LoopStatusBinding` | Read-only map from projected status to blockers, verification refs, closure gates, validators, and proof surfaces. |
| `LoopModeBinding` | Read-only map from projected mode to allowed modes, separation refs, real-execution guards, validators, and proof surfaces. |
| `LoopClosureConditionBinding` | Read-only map from each closure condition to required evidence refs, authority refs, validators, and proof surfaces. |
| `LoopAuthorityBinding` | Read-only map from each required authority label to source refs, validator refs, and proof surfaces. |
| `LoopRiskBinding` | Read-only map from the risk class to hazards, mitigations, monitors, source refs, validator refs, and proof surfaces. |
| `LoopRollbackBinding` | Read-only map from the rollback policy to recovery source refs, validator refs, and proof surfaces. |
| `LoopLearningBinding` | Read-only map from the learning policy to evidence inputs, admission refs, retention refs, validators, and proof surfaces. |
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

Missing required authority or evidence is a blocker:

```text
required_authority - authority_refs -> missing_authority
missing_authority -> open_blockers: missing_authority:<name>
required_evidence - evidence_refs -> missing_evidence
missing_evidence -> open_blockers: missing_evidence:<name>
open_blockers != empty -> status = blocked
```

This prevents fake closure. A loop may report runtime health or worker execution evidence, but the read model remains blocked until the manifest's authority requirements, evidence requirements, and closure conditions are satisfied.

## Status Catalog

Each loop summary includes `status_binding`. A binding is a read-only catalog
entry for the loop's projected status:

| Field | Meaning |
| --- | --- |
| `projected_status` | The current read-model status for this loop summary. |
| `status_reason` | Why the summary is blocked or verified while terminal closure remains separate. |
| `blocker_refs` | The unresolved blocker labels that explain a blocked status. |
| `verification_refs` | Required verification labels that must be observed before status can be verified. |
| `closure_gate_refs` | Closure condition labels that remain external gates for terminal closure. |
| `source_refs` | Existing files, schemas, or scripts that define the status proof surface. |
| `validator_refs` | Existing tests or validators that check the referenced status surface. |
| `proof_surface_refs` | Proof-matrix surface IDs related to the status projection. |
| `read_only` | Always `true`; bindings do not update status or execute loops. |
| `status_transition` | Always `false`; bindings do not authorize status transitions. |
| `terminal_closure` | Always `false`; bindings are not closure certificates. |

The catalog is exact by contract:

```text
status_binding.projected_status == status
set(status_binding.blocker_refs) == set(open_blockers)
status_binding.read_only == true
status_binding.status_transition == false
status_binding.terminal_closure == false
```

The status catalog does not clear blockers, mark a loop verified, transition
state, execute validators, or close loops. It only tells operators which
blockers, verification refs, closure gates, validators, and proof surfaces
explain the current projected status.

## Mode Catalog

Each loop summary includes `mode_binding`. A binding is a read-only catalog
entry for the loop's projected execution posture:

| Field | Meaning |
| --- | --- |
| `projected_mode` | The current read-model mode for this loop summary. |
| `allowed_modes` | Manifest modes that the loop is allowed to describe. |
| `purpose` | Why these mode boundaries exist for the loop. |
| `separation_refs` | Named dry-run, shadow, simulation, replay, or real-mode separation rules. |
| `real_execution_guard_refs` | Authority, witness, or policy labels required before real execution can be claimed. |
| `source_refs` | Existing files, schemas, or scripts that define mode separation. |
| `validator_refs` | Existing tests or validators that check the referenced mode boundary. |
| `proof_surface_refs` | Proof-matrix surface IDs related to mode separation. |
| `read_only` | Always `true`; bindings do not switch modes or execute loops. |
| `mode_transition` | Always `false`; bindings do not authorize mode transitions. |
| `terminal_closure` | Always `false`; bindings are not closure certificates. |

The catalog is exact by contract:

```text
mode_binding.projected_mode == mode
mode in mode_binding.allowed_modes
mode_binding.read_only == true
mode_binding.mode_transition == false
mode_binding.terminal_closure == false
```

The mode catalog does not promote dry-run to real execution, authorize mode
switching, mutate loop state, or close loops. It only tells operators which mode
separation rules, real-execution guards, validators, and proof surfaces matter
for later loop-specific execution admission.

## Closure Condition Catalog

Each loop summary includes `closure_condition_bindings`. A binding is a
read-only catalog entry for one declared `closure_conditions` label:

| Field | Meaning |
| --- | --- |
| `closure_ref` | The closure condition label the binding explains. |
| `purpose` | Why this condition is required before closure can be considered. |
| `required_evidence_refs` | Required evidence labels that support the closure condition. |
| `required_authority_refs` | Required authority labels that support the closure condition. |
| `source_refs` | Existing files, schemas, or scripts that define the closure proof surface. |
| `validator_refs` | Existing tests or validators that check the referenced closure surface. |
| `proof_surface_refs` | Proof-matrix surface IDs related to the closure condition. |
| `read_only` | Always `true`; bindings do not evaluate or close the loop. |
| `terminal_closure` | Always `false`; bindings are not closure certificates. |

The catalog is exact by contract:

```text
set(closure_condition_bindings[*].closure_ref) == set(closure_conditions)
closure_condition_bindings[*].required_evidence_refs subset required_evidence
closure_condition_bindings[*].required_authority_refs subset required_authority
closure_condition_bindings[*].read_only == true
closure_condition_bindings[*].terminal_closure == false
```

The closure condition catalog does not mark conditions satisfied, clear
blockers, execute validators, or close loops. It only tells operators which
evidence, authority, validator, and proof surfaces are required before a later
loop-specific closure workflow can claim a condition is satisfied.

## Authority Catalog

Each loop summary includes `authority_bindings`. A binding is a read-only
catalog entry for one `required_authority` label:

| Field | Meaning |
| --- | --- |
| `authority_ref` | The required authority label the binding explains. |
| `purpose` | Why the authority is required for loop closure or execution admission. |
| `source_refs` | Existing files, schemas, or scripts that define the authority surface. |
| `validator_refs` | Existing tests or validators that check the referenced authority surface. |
| `proof_surface_refs` | Proof-matrix surface IDs related to the authority. |
| `read_only` | Always `true`; bindings do not grant approval or execute authority checks. |
| `terminal_closure` | Always `false`; bindings are not closure certificates. |

The catalog is exact by contract:

```text
set(authority_bindings[*].authority_ref) == set(required_authority)
```

Missing, duplicate, or extra authority bindings are validation failures. The
catalog does not grant authority. It only tells operators where authority proof
must come from when a later loop-specific workflow runs.

## Risk Catalog

Each loop summary includes `risk_binding`. A binding is a read-only catalog
entry for the loop's `risk_class`:

| Field | Meaning |
| --- | --- |
| `risk_ref` | The risk class label the binding explains. |
| `purpose` | Why this loop risk class exists. |
| `hazard_refs` | Named hazards that can prevent safe closure or execution admission. |
| `mitigation_refs` | Named mitigation requirements or blocker policies. |
| `monitor_refs` | Existing monitor, report, or receipt surfaces that expose the risk. |
| `source_refs` | Existing files, schemas, or scripts that define the risk surface. |
| `validator_refs` | Existing tests or validators that check the referenced risk surface. |
| `proof_surface_refs` | Proof-matrix surface IDs related to the risk. |
| `read_only` | Always `true`; bindings do not execute risk scoring or admission. |
| `terminal_closure` | Always `false`; bindings are not closure certificates. |

The catalog is exact by contract:

```text
risk_binding.risk_ref == risk_class
risk_binding.read_only == true
risk_binding.terminal_closure == false
```

The risk catalog does not score risk, admit execution, mutate policy, or close
loops. It only tells operators which hazards, mitigations, monitors, and proof
surfaces matter for the loop's declared risk class.

## Rollback Catalog

Each loop summary includes `rollback_binding`. A binding is a read-only catalog
entry for the loop's `rollback_policy`:

| Field | Meaning |
| --- | --- |
| `rollback_ref` | The rollback policy label the binding explains. |
| `purpose` | Why the rollback path exists and what recovery boundary it describes. |
| `source_refs` | Existing files, schemas, or scripts that define the recovery path. |
| `validator_refs` | Existing tests or validators that check the referenced recovery surface. |
| `proof_surface_refs` | Proof-matrix surface IDs related to rollback or recovery. |
| `read_only` | Always `true`; bindings do not execute rollback. |
| `terminal_closure` | Always `false`; bindings are not closure certificates. |

The catalog is exact by contract:

```text
rollback_binding.rollback_ref == rollback_policy
rollback_binding.read_only == true
rollback_binding.terminal_closure == false
```

The rollback catalog does not restore snapshots, invalidate claims, or open
recovery handoffs. It only tells operators where recovery proof must come from.

## Learning Catalog

Each loop summary includes `learning_binding`. A binding is a read-only catalog
entry for the loop's `learning_policy`:

| Field | Meaning |
| --- | --- |
| `learning_ref` | The learning policy label the binding explains. |
| `purpose` | Why this learning path exists. |
| `evidence_input_refs` | Required evidence labels that may feed later learning. |
| `admission_refs` | Named admission rules that prevent uncontrolled learning. |
| `retention_refs` | Records or ledgers where validated learning evidence is retained. |
| `source_refs` | Existing files, schemas, or scripts that define the learning surface. |
| `validator_refs` | Existing tests or validators that check the referenced learning surface. |
| `proof_surface_refs` | Proof-matrix surface IDs related to learning. |
| `read_only` | Always `true`; bindings do not write memory or update policy. |
| `terminal_closure` | Always `false`; bindings are not closure certificates. |

The catalog is exact by contract:

```text
learning_binding.learning_ref == learning_policy
learning_binding.read_only == true
learning_binding.terminal_closure == false
```

The learning catalog does not admit learning, write memory, mutate tests, or
update SDLC gates. It only tells operators which evidence inputs, admission
rules, retention surfaces, and proof surfaces matter for later loop-specific
learning workflows.

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

## Step Receipt Trail

Each loop summary includes `step_receipts`, a bounded read-only projection over
the manifest's canonical loop phases. These receipts are not runtime execution
receipts. They give operators and validators a common shape for asking whether
each phase is blocked or verified:

| Field | Meaning |
| --- | --- |
| `loop_id` | The registered loop the receipt describes. |
| `step` | One canonical phase: observe, decide, act, verify, record_receipt, update_state, learn, or audit. |
| `input_hash` | Deterministic read-model input boundary hash. |
| `output_hash` | Deterministic read-model output boundary hash. |
| `decision` | Projection decision for the phase. |
| `evidence_refs` | Evidence refs observed by the read model. |
| `status` | `blocked` while unresolved gaps exist; otherwise `verified`. |
| `errors` | Must match `open_blockers` exactly. |
| `metadata.read_only` | Always `true`. |
| `metadata.synthetic_projection` | Always `true`; this is not a live runtime receipt. |
| `metadata.terminal_closure` | Always `false`. |
| `metadata.behavior_rewrite` | Always `false`. |

The receipt trail is exact by contract:

```text
all(step_receipts[*].loop_id == loop_id)
set(step_receipts[*].errors) == set(open_blockers)
step_receipts[*].metadata.read_only == true
step_receipts[*].metadata.terminal_closure == false
```

The `act` receipt explicitly describes existing behavior without executing it.
The read model can therefore expose loop phases without changing deployment,
runtime conformance, cognitive, proof, or code-change behavior.

## Closure Readiness

Each loop summary also includes a derived `closure_report`. This report is a
read-only closure-readiness assessment, not a closure certificate:

| Field | Meaning |
| --- | --- |
| `closed` | Always `false` in the read model. |
| `closure_reason` | Explains whether the summary is blocked by gaps or verified but still awaiting terminal closure. |
| `evidence_complete` | `true` only when no required evidence is missing. |
| `unresolved_gaps` | Must match `open_blockers` exactly. |
| `rollback_available` | `true` when the manifest has a rollback policy. |
| `learning_candidates` | Learning policy candidates emitted when blockers remain. |
| `metadata.read_only` | Always `true`. |
| `metadata.terminal_closure` | Always `false`. |

The closure report prevents an evidence-complete read model from being confused
with loop closure:

```text
evidence_complete == true
open_blockers == []
status == verified
closed == false
terminal_closure_required == true
```

Terminal closure remains a loop-specific proof workflow outside this read-model
surface.

## Boundary

This kernel is intentionally non-invasive:

1. It does not call deployment witness collection.
2. It does not call runtime conformance collection.
3. It does not construct or run the cognitive loop.
4. It does not dispatch governed code-change workers.
5. It does not create a public mutation route.
6. It does not grant authority or execute authority checks referenced by the catalog.
7. It does not score risk or execute risk admission referenced by the catalog.
8. It does not execute rollback or recovery actions referenced by the catalog.
9. It does not admit learning, write memory, mutate tests, or update gates referenced by the catalog.
10. It does not update loop status or execute status validators referenced by the catalog.
11. It does not execute evidence validators referenced by the catalog.
12. It does not emit live runtime execution receipts.
13. It does not mark any loop closed.
14. It only exposes typed read-model contracts that other surfaces can adopt later.

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
| `loops[].status_binding` | Read-only status catalog entry matching the projected loop status and blockers. |
| `loops[].mode_binding` | Read-only mode catalog entry matching the projected loop mode and allowed modes. |
| `loops[].closure_condition_bindings` | Read-only closure condition catalog entries covering every declared closure condition. |
| `loops[].authority_bindings` | Read-only authority catalog entries covering every required authority label. |
| `loops[].risk_binding` | Read-only risk catalog entry matching the loop risk class. |
| `loops[].rollback_binding` | Read-only recovery catalog entry matching the loop rollback policy. |
| `loops[].learning_binding` | Read-only learning catalog entry matching the loop learning policy. |
| `loops[].evidence_bindings` | Read-only evidence catalog entries covering every required evidence label. |
| `loops[].step_receipts` | Read-only synthetic receipt trail for the canonical loop phases. |
| `loops[].closure_report` | Read-only non-terminal closure-readiness report for each loop summary. |
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
8. Authority bindings cover every required authority label and cannot claim terminal closure.
9. Risk bindings cover each risk class and cannot score risk, admit execution, or claim closure.
10. Rollback bindings cover each recovery policy and cannot execute rollback or claim closure.
11. Learning bindings cover each learning policy and cannot admit learning, write memory, mutate tests, or claim closure.
12. Evidence bindings cover every required evidence label and cannot claim terminal closure.
13. Step receipt trails are read-only synthetic projections and must match blockers.
14. Closure reports cannot claim terminal closure and must match blockers.
