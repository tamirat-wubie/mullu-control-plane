# Mullu Holistic Loop Engineering Kernel v1

Purpose: define the shared governed loop contract used to describe existing Mullu loops without changing their runtime behavior.
Governance scope: loop manifests, loop state projections, step receipts, receipt lineage bindings, closure reports, registry exposure, status bindings, transition bindings, mode bindings, closure condition bindings, risk bindings, evidence bindings, evidence blockers, closure evidence packs, operator closure readiness views, proof obligation views, audit evolution views, recovery readiness views, rollback policy, learning bindings, and learning policy.
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
| `LoopReceiptLineageBinding` | Read-only map from each synthetic step receipt to its receipt hash, required evidence, observed evidence, blockers, source receipts, validators, and proof surfaces. |
| `LoopClosureReport` | Closure assessment with unresolved gaps, rollback availability, and learning candidates. |
| `LoopClosureEvidencePack` | Read-only aggregate of required evidence, observed evidence, authority, blockers, closure conditions, receipt lineage, rollback, validators, and proof surfaces needed to evaluate closure readiness. |
| `LoopOperatorClosureReadinessView` | Read-only operator projection of blockers, evidence gaps, authority gaps, rollback availability, and the next proof action. |
| `LoopProofObligationView` | Read-only proof obligation projection over evidence refs, authority refs, closure conditions, validators, proof surfaces, and blockers. |
| `LoopAuditEvolutionView` | Read-only audit evolution projection over receipt refs, receipt lineage refs, audit blockers, learning candidates, learning binding refs, and proof surfaces. |
| `LoopRecoveryReadinessView` | Read-only recovery projection over rollback policy, rollback catalog refs, blockers, receipt lineage refs, and proof surfaces. |
| `LoopStatusBinding` | Read-only map from projected status to blockers, verification refs, closure gates, validators, and proof surfaces. |
| `LoopTransitionBinding` | Read-only map from possible status and phase transitions to required evidence, authority, blockers, receipts, rollback refs, validators, and proof surfaces. |
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
| `audit_proof_verification_loop` | Describes audit, proof, trust-ledger anchor, and verification evidence without executing proof verification or anchor submission. | No |
| `authority_obligation_loop` | Describes authority obligation inventory, overdue debt resolution, and mesh validation evidence without satisfying obligations or mutating authority runtime behavior. | No |
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

## Transition Catalog

Each loop summary includes `transition_bindings`. A binding is a read-only
catalog entry for a possible status and phase transition:

| Field | Meaning |
| --- | --- |
| `transition_ref` | Stable transition label. |
| `from_status` | Source status boundary. |
| `to_status` | Target status boundary. |
| `from_step` | Source loop phase boundary. |
| `to_step` | Target loop phase boundary. |
| `required_authority_refs` | Authority labels required before the transition can be executed by a later workflow. |
| `required_evidence_refs` | Evidence labels required before the transition can be executed by a later workflow. |
| `blocker_refs` | Current blockers that prevent transition readiness. |
| `receipt_refs` | Receipts that would prove later transition execution. |
| `rollback_refs` | Rollback or recovery policy refs for failed transition execution. |
| `source_refs` | Existing files, schemas, or scripts that define the transition proof surface. |
| `validator_refs` | Existing tests or validators that check the referenced transition surface. |
| `proof_surface_refs` | Proof-matrix surface IDs related to transition readiness. |
| `read_only` | Always `true`; bindings do not update status or phase. |
| `executes_transition` | Always `false`; bindings do not execute transition behavior. |
| `terminal_closure` | Always `false`; bindings are not closure certificates. |

The catalog is exact by contract:

```text
set(transition_bindings[*].blocker_refs) == set(open_blockers)
transition_bindings[*].required_evidence_refs subset required_evidence
transition_bindings[*].required_authority_refs subset required_authority
rollback_policy in transition_bindings[*].rollback_refs
transition_bindings[*].read_only == true
transition_bindings[*].executes_transition == false
transition_bindings[*].terminal_closure == false
```

The transition catalog does not clear blockers, update loop status, advance
phase, execute validators, run rollback, or close loops. It only tells
operators which evidence, authority, receipt, rollback, validator, and proof
surfaces are required before a later loop-specific workflow may execute or
prove a transition.

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

## Receipt Lineage Catalog

Each loop summary includes `receipt_lineage_bindings`, one lineage entry for
each synthetic `step_receipts` item. The catalog links a receipt projection to
the evidence, blocker, validator, and proof surfaces that explain the receipt.
It does not emit a live receipt.

| Field | Meaning |
| --- | --- |
| `lineage_ref` | Stable lineage label for the synthetic receipt. |
| `step` | Canonical loop phase covered by the lineage entry. |
| `receipt_ref` | Receipt label used by transition and closure proof surfaces. |
| `receipt_hash` | Must match the corresponding step receipt `output_hash`. |
| `required_evidence_refs` | Required evidence labels that must exist before the receipt can prove readiness. |
| `observed_evidence_refs` | Evidence refs observed by the read model. |
| `blocker_refs` | Must match `open_blockers` exactly. |
| `source_receipt_refs` | Prior or related receipt labels; must include `receipt_ref`. |
| `source_refs` | Existing files, schemas, or scripts that define the receipt lineage surface. |
| `validator_refs` | Existing tests or validators that check the referenced receipt surface. |
| `proof_surface_refs` | Proof-matrix surface IDs related to receipt lineage. |
| `read_only` | Always `true`. |
| `emits_receipt` | Always `false`; this catalog does not write runtime receipts. |
| `terminal_closure` | Always `false`; lineage is not a closure certificate. |

The receipt lineage catalog is exact by contract:

```text
set(receipt_lineage_bindings[*].step) == set(step_receipts[*].step)
receipt_lineage_bindings[*].receipt_hash == matching_step_receipt.output_hash
set(receipt_lineage_bindings[*].blocker_refs) == set(open_blockers)
set(receipt_lineage_bindings[*].observed_evidence_refs) == set(evidence_refs)
receipt_lineage_bindings[*].emits_receipt == false
receipt_lineage_bindings[*].terminal_closure == false
```

## Closure Evidence Pack

Each loop summary includes `closure_evidence_pack`, one aggregate view of the
inputs needed to evaluate closure readiness. The pack is derived from existing
loop fields; it does not replace `closure_report`, does not emit receipts, and
does not certify terminal closure.

| Field | Meaning |
| --- | --- |
| `pack_ref` | Stable read-model label for the closure evidence pack. |
| `loop_id` | Loop identity covered by the pack. |
| `required_evidence_refs` | Must match `required_evidence`. |
| `observed_evidence_refs` | Must match `evidence_refs`. |
| `missing_evidence_refs` | Must match `missing_evidence`. |
| `required_authority_refs` | Must match `required_authority`. |
| `observed_authority_refs` | Must match `authority_refs`. |
| `missing_authority_refs` | Must match `missing_authority`. |
| `blocker_refs` | Must match `open_blockers`. |
| `closure_condition_refs` | Must match `closure_conditions`. |
| `receipt_lineage_refs` | Must match `receipt_lineage_bindings[*].lineage_ref`. |
| `closure_report_ref` | Stable pointer to the loop `closure_report`. |
| `rollback_ref` | Must match `rollback_policy`. |
| `validator_refs` | Validators that check the aggregate read-model contract. |
| `proof_surface_refs` | Proof-matrix surfaces related to the aggregate. |
| `evidence_complete` | Must match `closure_report.evidence_complete`. |
| `authority_complete` | `true` only when `missing_authority` is empty. |
| `closure_blocked` | `true` exactly when `open_blockers` is non-empty. |
| `rollback_available` | Must match `closure_report.rollback_available`. |
| `read_only` | Always `true`. |
| `emits_receipt` | Always `false`; this pack does not write runtime receipts. |
| `terminal_closure` | Always `false`; this pack is not a closure certificate. |

The pack is exact by contract:

```text
set(closure_evidence_pack.required_evidence_refs) == set(required_evidence)
set(closure_evidence_pack.observed_evidence_refs) == set(evidence_refs)
set(closure_evidence_pack.missing_evidence_refs) == set(missing_evidence)
set(closure_evidence_pack.required_authority_refs) == set(required_authority)
set(closure_evidence_pack.observed_authority_refs) == set(authority_refs)
set(closure_evidence_pack.missing_authority_refs) == set(missing_authority)
set(closure_evidence_pack.blocker_refs) == set(open_blockers)
set(closure_evidence_pack.receipt_lineage_refs) == set(receipt_lineage_bindings[*].lineage_ref)
closure_evidence_pack.emits_receipt == false
closure_evidence_pack.terminal_closure == false
```

## Operator Closure Readiness View

Each loop summary includes `operator_closure_readiness_view`, a bounded
operator-facing projection over the closure evidence pack and closure report.
The view answers what blocks review next; it does not add evidence, emit a
receipt, expose a mutation route, run rollback, or certify closure.

| Field | Meaning |
| --- | --- |
| `view_ref` | Stable read-model label for the operator readiness view. |
| `loop_id` | Loop identity covered by the view. |
| `projected_status` | Must match the loop summary `status`. |
| `readiness_state` | `blocked_by_unresolved_gaps` when blockers exist, otherwise `ready_for_terminal_closure_review`. |
| `blocker_refs` | Must match `open_blockers`. |
| `evidence_gap_refs` | Must match `missing_evidence`. |
| `authority_gap_refs` | Must match `missing_authority`. |
| `closure_condition_refs` | Must match `closure_conditions`. |
| `rollback_ref` | Must match `rollback_policy`. |
| `rollback_available` | Must match `closure_report.rollback_available`. |
| `next_proof_action` | `resolve_blockers_before_terminal_closure_review` while blocked, otherwise `run_loop_specific_terminal_closure_workflow`. |
| `next_proof_refs` | Includes `closure_evidence_pack` and `closure_report`; blocked loops also name their blockers. |
| `read_only` | Always `true`. |
| `mutation_route` | Always `false`; this view cannot change loop state. |
| `terminal_closure` | Always `false`; this view is not a closure certificate. |

The view is exact by contract:

```text
operator_closure_readiness_view.projected_status == status
set(operator_closure_readiness_view.blocker_refs) == set(open_blockers)
set(operator_closure_readiness_view.evidence_gap_refs) == set(missing_evidence)
set(operator_closure_readiness_view.authority_gap_refs) == set(missing_authority)
set(operator_closure_readiness_view.closure_condition_refs) == set(closure_conditions)
operator_closure_readiness_view.rollback_ref == rollback_policy
operator_closure_readiness_view.rollback_available == closure_report.rollback_available
operator_closure_readiness_view.read_only == true
operator_closure_readiness_view.mutation_route == false
operator_closure_readiness_view.terminal_closure == false
```

## Proof Obligation View

Each loop summary includes `proof_obligation_view`, a bounded projection of the
proof inputs that must be present before terminal closure review. The view is
derived from the closure evidence pack and current loop summary fields. It does
not execute validators, add evidence, update state, or certify terminal
closure.

| Field | Meaning |
| --- | --- |
| `obligation_ref` | Stable read-model label for the proof obligation view. |
| `loop_id` | Loop identity covered by the view. |
| `obligation_state` | `blocked_by_missing_proof` when blockers exist, otherwise `proof_obligations_satisfied_terminal_review_required`. |
| `required_evidence_refs` | Must match `required_evidence`. |
| `satisfied_evidence_refs` | Must match `evidence_refs`. |
| `missing_evidence_refs` | Must match `missing_evidence`. |
| `required_authority_refs` | Must match `required_authority`. |
| `satisfied_authority_refs` | Must match `authority_refs`. |
| `missing_authority_refs` | Must match `missing_authority`. |
| `closure_condition_refs` | Must match `closure_conditions`. |
| `validator_refs` | Must match `closure_evidence_pack.validator_refs`. |
| `proof_surface_refs` | Must match `closure_evidence_pack.proof_surface_refs`. |
| `blocker_refs` | Must match `open_blockers`. |
| `read_only` | Always `true`. |
| `executes_validator` | Always `false`; this view is not a validator runner. |
| `terminal_closure` | Always `false`; this view is not a closure certificate. |

The view is exact by contract:

```text
set(proof_obligation_view.required_evidence_refs) == set(required_evidence)
set(proof_obligation_view.satisfied_evidence_refs) == set(evidence_refs)
set(proof_obligation_view.missing_evidence_refs) == set(missing_evidence)
set(proof_obligation_view.required_authority_refs) == set(required_authority)
set(proof_obligation_view.satisfied_authority_refs) == set(authority_refs)
set(proof_obligation_view.missing_authority_refs) == set(missing_authority)
set(proof_obligation_view.closure_condition_refs) == set(closure_conditions)
set(proof_obligation_view.validator_refs) == set(closure_evidence_pack.validator_refs)
set(proof_obligation_view.proof_surface_refs) == set(closure_evidence_pack.proof_surface_refs)
set(proof_obligation_view.blocker_refs) == set(open_blockers)
proof_obligation_view.read_only == true
proof_obligation_view.executes_validator == false
proof_obligation_view.terminal_closure == false
```

## Audit Evolution View

Each loop summary includes `audit_evolution_view`, a bounded projection that
connects audit blockers, synthetic receipt outputs, receipt lineage, closure
learning candidates, and learning binding refs. The view is derived from the
loop summary; it does not emit a receipt, admit learning, update memory, mutate
tests, or certify terminal closure.

| Field | Meaning |
| --- | --- |
| `view_ref` | Stable read-model label for the audit evolution view. |
| `loop_id` | Loop identity covered by the view. |
| `audit_state` | `audit_blocked_by_unresolved_gaps` when blockers exist, otherwise `audit_ready_for_terminal_review`. |
| `receipt_refs` | Must match `step_receipts[*].output_hash`. |
| `receipt_lineage_refs` | Must match `receipt_lineage_bindings[*].lineage_ref`. |
| `audit_blocker_refs` | Must match `open_blockers`. |
| `learning_policy_ref` | Must match `learning_policy`. |
| `learning_candidate_refs` | Must match `closure_report.learning_candidates`. |
| `learning_evidence_input_refs` | Must match `learning_binding.evidence_input_refs`. |
| `learning_admission_refs` | Must match `learning_binding.admission_refs`. |
| `learning_retention_refs` | Must match `learning_binding.retention_refs`. |
| `proof_surface_refs` | Must match the union of closure evidence pack and learning binding proof surfaces. |
| `read_only` | Always `true`. |
| `emits_receipt` | Always `false`; this view does not write runtime receipts. |
| `admits_learning` | Always `false`; this view does not authorize learning. |
| `terminal_closure` | Always `false`; this view is not a closure certificate. |

The view is exact by contract:

```text
set(audit_evolution_view.receipt_refs) == set(step_receipts[*].output_hash)
set(audit_evolution_view.receipt_lineage_refs) == set(receipt_lineage_bindings[*].lineage_ref)
set(audit_evolution_view.audit_blocker_refs) == set(open_blockers)
audit_evolution_view.learning_policy_ref == learning_policy
set(audit_evolution_view.learning_candidate_refs) == set(closure_report.learning_candidates)
set(audit_evolution_view.learning_evidence_input_refs) == set(learning_binding.evidence_input_refs)
set(audit_evolution_view.learning_admission_refs) == set(learning_binding.admission_refs)
set(audit_evolution_view.learning_retention_refs) == set(learning_binding.retention_refs)
set(audit_evolution_view.proof_surface_refs) == set(closure_evidence_pack.proof_surface_refs) union set(learning_binding.proof_surface_refs)
audit_evolution_view.read_only == true
audit_evolution_view.emits_receipt == false
audit_evolution_view.admits_learning == false
audit_evolution_view.terminal_closure == false
```

## Recovery Readiness View

Each loop summary includes `recovery_readiness_view`, a bounded projection that
connects the rollback policy, closure evidence pack, closure report, receipt
lineage, current blockers, and rollback catalog refs. The view is derived from
existing read-model fields; it does not execute rollback, open incidents, mutate
state, or certify terminal closure.

| Field | Meaning |
| --- | --- |
| `view_ref` | Stable read-model label for the recovery readiness view. |
| `loop_id` | Loop identity covered by the view. |
| `recovery_state` | `recovery_blocked_by_unresolved_gaps` when blockers exist, otherwise `recovery_ready_for_terminal_review`. |
| `rollback_ref` | Must match `rollback_policy`. |
| `rollback_available` | Must match `closure_report.rollback_available`. |
| `closure_report_ref` | Stable pointer to `closure_report`. |
| `closure_evidence_pack_ref` | Must match `closure_evidence_pack.pack_ref`. |
| `blocker_refs` | Must match `open_blockers`. |
| `receipt_lineage_refs` | Must match `closure_evidence_pack.receipt_lineage_refs`. |
| `recovery_source_refs` | Must match `rollback_binding.source_refs`. |
| `recovery_validator_refs` | Must match `rollback_binding.validator_refs`. |
| `recovery_proof_surface_refs` | Must match the union of closure evidence pack and rollback binding proof surfaces. |
| `next_recovery_action` | Names the next non-mutating recovery proof action. |
| `read_only` | Always `true`. |
| `executes_rollback` | Always `false`; this view does not restore or revert state. |
| `opens_incident` | Always `false`; this view does not create incident handoffs. |
| `terminal_closure` | Always `false`; this view is not a closure certificate. |

The view is exact by contract:

```text
recovery_readiness_view.rollback_ref == rollback_policy
recovery_readiness_view.rollback_available == closure_report.rollback_available
recovery_readiness_view.closure_report_ref == "closure_report"
recovery_readiness_view.closure_evidence_pack_ref == closure_evidence_pack.pack_ref
set(recovery_readiness_view.blocker_refs) == set(open_blockers)
set(recovery_readiness_view.receipt_lineage_refs) == set(closure_evidence_pack.receipt_lineage_refs)
set(recovery_readiness_view.recovery_source_refs) == set(rollback_binding.source_refs)
set(recovery_readiness_view.recovery_validator_refs) == set(rollback_binding.validator_refs)
set(recovery_readiness_view.recovery_proof_surface_refs) == set(closure_evidence_pack.proof_surface_refs) union set(rollback_binding.proof_surface_refs)
recovery_readiness_view.read_only == true
recovery_readiness_view.executes_rollback == false
recovery_readiness_view.opens_incident == false
recovery_readiness_view.terminal_closure == false
```

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

## Kernel v1 Stability Boundary

The `holistic_loop_kernel.v1` contract is frozen as a v1 additive-only
read-model contract. Existing v1 fields, field meanings, read-only flags,
non-terminal closure flags, blocker semantics, and registered loop identifiers
are part of the stable contract surface.

No v1 field may be removed, renamed, repurposed, or made effect-bearing inside
the v1 contract. A breaking shape change requires a v2 contract boundary with a
new schema identifier, new fixture, updated validators, and explicit migration
notes. A v1 extension may add a new read-only field or view only when existing
v1 consumers can ignore it without losing the current contract.

The stability boundary is enforced by:

1. A golden snapshot fixture for the current default read model.
2. Schema validation of the current report and normalized HTTP payload.
3. Report-to-HTTP parity validation.
4. A proof matrix witness guard requiring zero unanchored holistic loop labels.
5. Documentation checks for the v1 additive-only policy and extension rules.
6. Extension admission validation for default loop registrations.

### Extension Admission Guard

New default loop registrations must pass extension admission before they are
treated as part of the v1 registry. Admission is read-only and does not execute
the candidate loop. It checks:

1. Each loop manifest declares authority, evidence, closure, rollback, learning,
   canonical steps, allowed modes, and existing source surfaces.
2. `metadata.behavior_rewrite` remains `false`.
3. Missing authority and missing evidence are projected as explicit blockers.
4. Summary and closure-report records do not claim terminal closure.
5. The holistic loop proof surface carries an anchored admission witness.

Run:

```powershell
python scripts/validate_holistic_loop_extension_admission.py
```

Admission passing means a loop is structurally eligible for the read model. It
does not mean the loop is verified, closed, authorized for real execution, or
allowed to mutate runtime behavior.

### Candidate Map

The candidate map lists existing loop-like surfaces that may be considered for
future admission and reports whether a candidate has already been admitted into
the default registry. It does not register candidates and does not execute their
behavior.

Run:

```powershell
python scripts/report_holistic_loop_candidate_map.py
```

The current candidate map includes:

| Candidate ID | Boundary |
| --- | --- |
| `audit_proof_verification_loop` | Audit, proof, and trust-ledger anchor verification surfaces; admitted into the default read model as a read-only blocked loop. |
| `authority_obligation_loop` | Authority debt detection, satisfaction, and closure evidence surfaces; admitted into the default read model as a read-only blocked loop. |
| `universal_action_orchestration_loop` | Effect-bearing action admission, receipt, replay, and no-bypass surfaces. |
| `workflow_execution_loop` | Workflow descriptor, run, orchestration, and replay surfaces. |

Registered candidates are projected as:

```text
registered == true
admission_status == registered
admission_blockers == []
next_action == already_registered
read_only == true
mutation_route == false
terminal_closure == false
```

Unregistered candidates are projected as:

```text
registered == false
admission_status == blocked
admission_blockers include not_registered
admission_blockers include requires_operator_registration_decision
read_only == true
mutation_route == false
terminal_closure == false
behavior_rewrite == false
```

This preserves the extension boundary: candidate discovery is not registration,
verification, closure, or runtime migration.

### UAO Admission Dossier

The Universal Action Orchestration admission dossier is the first candidate
specific readiness projection. It proves whether the UAO loop candidate is
ready for an operator registration decision without registering the loop.

Run:

```powershell
python scripts/report_holistic_loop_uao_admission_dossier.py
```

The dossier reports:

```text
candidate_id == universal_action_orchestration_loop
admission_status == ready_for_operator_decision
requires_operator_registration_decision in admission_blockers
registered == false
read_only == true
mutation_route == false
runtime_behavior_change == false
terminal_closure == false
registration_effect.registers_loop == false
```

The dossier includes a proposed `LoopManifest`, existing source refs, evidence
gap report, authority gap report, closure-condition gap report, rollback
readiness, and learning policy readiness. It does not grant authority, emit a
receipt, mutate the registry, execute UAO behavior, or close admission.

### Workflow Admission Dossier

The Workflow Execution admission dossier applies the same candidate-specific
readiness boundary to workflow descriptor, run, orchestration, replay, wait
state, and workflow-store surfaces.

Run:

```powershell
python scripts/report_holistic_loop_workflow_admission_dossier.py
```

The dossier reports:

```text
candidate_id == workflow_execution_loop
admission_status == ready_for_operator_decision
requires_operator_registration_decision in admission_blockers
registered == false
read_only == true
mutation_route == false
runtime_behavior_change == false
terminal_closure == false
registration_effect.registers_loop == false
```

The dossier includes a proposed `LoopManifest`, existing workflow source refs,
evidence gap report, authority gap report, closure-condition gap report,
rollback readiness, and learning policy readiness. It does not grant authority,
emit a receipt, mutate the registry, execute workflow behavior, or close
admission.

### Authority Admission Dossier

The Authority Obligation admission dossier reports the admitted
candidate-specific registry state for authority debt detection, obligation
satisfaction, escalation, closure receipt, and responsibility mesh surfaces.

Run:

```powershell
python scripts/report_holistic_loop_authority_admission_dossier.py
```

The dossier reports:

```text
candidate_id == authority_obligation_loop
admission_status == registered
admission_blockers == []
next_action == already_registered
registered == true
read_only == true
mutation_route == false
runtime_behavior_change == false
terminal_closure == false
registration_effect.registers_loop == false
```

The dossier includes a proposed `LoopManifest`, existing authority source refs,
evidence gap report, authority gap report, closure-condition gap report,
rollback readiness, and learning policy readiness. It does not grant authority,
satisfy obligations, emit a receipt, mutate the registry, execute authority
behavior, or claim terminal closure.

### Audit Proof Admission Dossier

The Audit Proof Verification admission dossier now reports the registered
admission state for audit verification, proof verification, trust-ledger anchor
verification, export packaging, remote submission preflight, and gateway
verification surfaces. It remains read-only and does not perform the registry
admission itself.

Run:

```powershell
python scripts/report_holistic_loop_audit_proof_admission_dossier.py
```

The dossier reports:

```text
candidate_id == audit_proof_verification_loop
admission_status == registered
admission_blockers == []
next_action == already_registered
registered == true
read_only == true
mutation_route == false
runtime_behavior_change == false
terminal_closure == false
registration_effect.registers_loop == false
```

The dossier includes a proposed `LoopManifest`, existing audit/proof source
refs, evidence gap report, authority gap report, closure-condition gap report,
rollback readiness, and learning policy readiness. It does not verify proofs,
submit anchors, emit receipts, mutate the registry, execute audit/proof
behavior, or claim terminal closure.

### Extension Checklist

Before adding a future v1.x loop view or field:

1. Keep the addition read-only and non-terminal.
2. Do not execute loop behavior, validators, rollback, learning, receipt
   emission, status transition, or incident opening.
3. Preserve every existing v1 field name and meaning.
4. Add schema fields as additive optional-or-required v1.x fields only when all
   report, HTTP, fixture, and validators are updated together.
5. Add focused tests for positive projection, mismatch rejection, and
   effect-claim rejection.
6. Add or update the proof matrix witness label and exact test anchor.
7. Regenerate the golden snapshot and proof matrix fixtures in the same change.
8. Run the holistic loop kernel freeze validator before claiming closure.

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
11. It does not execute status or phase transitions referenced by the catalog.
12. It does not execute evidence validators referenced by the catalog.
13. It does not emit live runtime execution receipts.
14. It does not emit receipt lineage records into runtime stores.
15. It does not emit closure evidence packs into runtime stores.
16. It does not emit audit evolution views into runtime stores, admit learning, or update memory.
17. It does not execute rollback, open incidents, or emit recovery readiness views into runtime stores.
18. It does not mark any loop closed.
19. It only exposes typed read-model contracts that other surfaces can adopt later.

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
| `loops[].transition_bindings` | Read-only transition catalog entries describing allowed status and phase transition gates. |
| `loops[].mode_binding` | Read-only mode catalog entry matching the projected loop mode and allowed modes. |
| `loops[].closure_condition_bindings` | Read-only closure condition catalog entries covering every declared closure condition. |
| `loops[].authority_bindings` | Read-only authority catalog entries covering every required authority label. |
| `loops[].risk_binding` | Read-only risk catalog entry matching the loop risk class. |
| `loops[].rollback_binding` | Read-only recovery catalog entry matching the loop rollback policy. |
| `loops[].learning_binding` | Read-only learning catalog entry matching the loop learning policy. |
| `loops[].evidence_bindings` | Read-only evidence catalog entries covering every required evidence label. |
| `loops[].step_receipts` | Read-only synthetic receipt trail for the canonical loop phases. |
| `loops[].receipt_lineage_bindings` | Read-only lineage catalog entries linking synthetic receipts to evidence, blockers, validators, and proof surfaces. |
| `loops[].closure_report` | Read-only non-terminal closure-readiness report for each loop summary. |
| `loops[].closure_evidence_pack` | Read-only aggregate of evidence, authority, blockers, closure conditions, lineage refs, rollback, validators, and proof surfaces. |
| `loops[].operator_closure_readiness_view` | Read-only operator view of current blockers and next proof action. |
| `loops[].proof_obligation_view` | Read-only proof obligation view over required evidence, authority, closure conditions, validators, proof surfaces, and blockers. |
| `loops[].audit_evolution_view` | Read-only audit evolution view over receipt refs, lineage refs, blockers, learning candidates, learning binding refs, and proof surfaces. |
| `loops[].recovery_readiness_view` | Read-only recovery readiness view over rollback policy, closure evidence pack, receipt lineage refs, blockers, rollback catalog refs, and proof surfaces. |
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
python -m pytest mcoi/tests/test_holistic_loop_kernel.py mcoi/tests/test_holistic_loop_router.py tests/test_report_holistic_loop_read_model.py tests/test_report_holistic_loop_candidate_map.py tests/test_report_holistic_loop_uao_admission_dossier.py tests/test_report_holistic_loop_workflow_admission_dossier.py tests/test_report_holistic_loop_authority_admission_dossier.py tests/test_report_holistic_loop_audit_proof_admission_dossier.py tests/test_validate_holistic_loop_read_model.py tests/test_validate_holistic_loop_http_surface.py tests/test_validate_holistic_loop_kernel_freeze.py tests/test_validate_holistic_loop_extension_admission.py tests/test_proof_coverage_matrix.py -q
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

Kernel v1 freeze validation:

```powershell
python scripts/validate_holistic_loop_kernel_freeze.py
```

Extension admission validation:

```powershell
python scripts/validate_holistic_loop_extension_admission.py
```

Candidate map validation:

```powershell
python scripts/report_holistic_loop_candidate_map.py
```

UAO admission dossier validation:

```powershell
python scripts/report_holistic_loop_uao_admission_dossier.py
```

Workflow admission dossier validation:

```powershell
python scripts/report_holistic_loop_workflow_admission_dossier.py
```

Authority admission dossier validation:

```powershell
python scripts/report_holistic_loop_authority_admission_dossier.py
```

Audit proof admission dossier validation:

```powershell
python scripts/report_holistic_loop_audit_proof_admission_dossier.py
```

The tests verify:

1. The six default loops are registered.
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
14. Receipt lineage bindings cover step receipts exactly and cannot emit receipts.
15. Closure evidence packs aggregate closure inputs exactly and cannot emit receipts.
16. Closure reports cannot claim terminal closure and must match blockers.
17. Recovery readiness views connect rollback policy, blockers, receipt lineage, closure evidence, and rollback catalog refs without executing rollback, opening incidents, or claiming closure.
18. The v1 golden snapshot matches the current default report.
19. The normalized HTTP payload matches the local report contract.
20. The holistic proof matrix surface has zero unanchored witness labels.
21. Extension admission keeps default loop registrations read-only, blocker-aware, non-terminal, and proof-anchored.
22. The candidate map lists loop-like surfaces, distinguishes admitted candidates from still-blocked candidates, and does not register, verify, close, or mutate them.
23. The UAO admission dossier proves readiness for an operator registration decision without registering, mutating, or closing the loop.
24. The workflow admission dossier proves readiness for an operator registration decision without registering, mutating, or closing the loop.
25. The authority admission dossier reports default registry admission without mutating, satisfying obligations, or closing the loop.
26. The audit/proof admission dossier reports default registry admission without mutating the registry, verifying proofs, submitting anchors, or closing the loop.
