# Governed Planning Profile

Purpose: define a canonical, read-only interoperability profile across existing Mullu problem framing, planning, simulation, execution, effect-governance, closure, recovery, and learning surfaces.

Governance scope: OCE field completeness, RAG lineage bindings, CDCV causal traceability, CQTE bounded planning controls, UWMA evidence anchoring, SRCA replanning stability, PRS validation evidence, Foundation Mode authority denial, and Mfidel atomicity preservation.

Dependencies: `docs/75_problem_star_compilation_receipt.md`, `mcoi/mcoi_runtime/core/phi_gps.py`, `gateway/goal_compiler.py`, `gateway/causal_simulator.py`, `gateway/plan.py`, `gateway/plan_executor.py`, `gateway/plan_ledger.py`, `mcoi/mcoi_runtime/core/organization_kernel.py`, `mcoi/mcoi_runtime/core/whqr_mil_orchestrator.py`, `mcoi/mcoi_runtime/contracts/holistic_loop.py`, `docs/UNIVERSAL_ACTION_ORCHESTRATION.md`, and `docs/38_closure_learning_admission.md`.

Invariants: the profile is additive and reference-only; it does not register a planner, replace Phi-GPS, replace WHQR/MIL, replace OrgOS, replace Workflow, bypass UAO or Phi_gov, dispatch work, call connectors, write files or memory, migrate a system of record, enable runtime replanning, claim success, or grant terminal closure.

## Boundary

The Governed Planning Profile is a compatibility and audit contract. It records how existing planning-related artifacts fit together without collapsing their identities into a new runtime object.

```text
ProblemStar / Phi-GPS
        ↓ reference-only
Governed Planning Profile
        ↓ reference-only
Goal and plan compilation
        ↓ reference-only
Causal simulation and approval evidence
        ↓ reference-only
WHQR/MIL or OrgOS execution lineage
        ↓ governed separately
UAO and Phi_gov effect governance
        ↓ governed separately
Reconciliation, closure, and learning admission
```

The profile does not authorize any arrow in this diagram. Each source lineage keeps its own admission, authority, execution, verification, and closure rules.

## What This Profile Solves

Mullu already has multiple strong planning representations. The remaining architecture problem is interoperability and audit consistency, not the absence of planning machinery.

The profile provides:

1. Stable references to each existing lineage.
2. Explicit goal, constraint, evidence, assumption, unknown, contradiction, risk, budget, authority, approval, rollback, compensation, safe-stop, closure, and learning references.
3. A fail-closed authority envelope.
4. Replanning stability requirements such as local repair first, hysteresis, cooldown, and change budgets.
5. Count-based drift checks for profile completeness.
6. A future adapter target that does not require a second execution spine.

## Source Binding Rules

Every source binding must be:

- `reference_only`;
- read-only;
- non-executable;
- authority-neutral;
- backed by an existing repository path;
- uniquely identified.

The required initial bindings cover:

| Binding | Existing source | Role |
| --- | --- | --- |
| Problem compilation | `docs/75_problem_star_compilation_receipt.md` | Separates evidence, assumptions, unknowns, contradictions, goals, constraints, risks, actions, and proof obligations. |
| Phi-GPS solver | `mcoi/mcoi_runtime/core/phi_gps.py` | Frames, decomposes, evaluates, diagnoses, and verifies bounded problems. |
| Planning compiler | `gateway/goal_compiler.py` | Produces simulation-lineage goals, DAGs, conditions, evidence, rollback, approvals, and certificates. |
| Causal simulation | `gateway/causal_simulator.py` | Dry-runs plans and projects controls, failure modes, and compensation. |
| Capability plan | `gateway/plan.py` | Defines governed capability-plan and preview contracts. |
| Bounded plan execution | `gateway/plan_executor.py` | Defines dependency-ordered execution and checkpoint requirements. |
| Plan closure and recovery | `gateway/plan_ledger.py` | Records terminal certificates, evidence bundles, and recovery attempts. |
| Organization case governance | `mcoi/mcoi_runtime/core/organization_kernel.py` | Governs case plans, gates, evidence, action queues, reconciliation, and closure. |
| Live execution spine | `mcoi/mcoi_runtime/core/whqr_mil_orchestrator.py` | Preserves the WHQR-to-MIL governed acting path. |
| Holistic governed loops | `mcoi/mcoi_runtime/contracts/holistic_loop.py` | Defines typed observe, decide, act, verify, receipt, update, learn, audit, and close phases. |
| Effect governance | `docs/UNIVERSAL_ACTION_ORCHESTRATION.md` | Keeps every effect-bearing action behind UAO and Phi_gov. |
| Learning admission | `docs/38_closure_learning_admission.md` | Prevents unadmitted closure output from becoming planning knowledge. |

## Replanning Stability

This contract defines planning controls but does not activate runtime replanning.

The required repair order is:

```text
observe
→ retry safely
→ adjust parameters
→ reallocate resources
→ activate contingency
→ repair local branch
→ replan phase
→ replan mission
→ suspend or terminate
```

A future runtime adapter must provide separate enter and exit thresholds, a cooldown rule, and a bounded change budget. Goal rewrites, policy rewrites, and authority expansion remain subject to `Phi_gov`.

## Application Sequence

1. Validate the static profile and Foundation example.
2. Register the schema and validator in repository governance surfaces.
3. Add one adapter that projects an existing plan into the profile without changing the source object.
4. Run a shadow comparison between the source plan and the profile projection.
5. Record identity, evidence, authority, rollback, and closure mismatches.
6. Promote no runtime behavior until adapter parity, replay, recovery, and operator evidence exist.

## Reference Adapter And Shadow Admission

The first adapter slice is `gateway/governed_planning_profile_adapter.py`.
It consumes a compiled gateway plan and causal simulation receipt as structural
read-only inputs, then emits a `GovernedPlanningProfileAdmissionReport`.

The adapter does not import `gateway.goal_compiler`, `gateway.causal_simulator`,
`gateway.plan_executor`, any router, or any worker surface. That preserves the
existing rule that `gateway.goal_compiler` has only one non-test gateway
consumer: `gateway.causal_simulator`.

The report separates two classes of evidence:

1. `shadow_mismatches`: identity, topology, or simulation drift between the
   compiled plan and simulation receipt.
2. `promotion_blockers`: authority, evidence, closure, or Foundation Mode
   blockers that prevent runtime promotion even when shadow parity matches.

The report can say `shadow_parity_status = matched`, but it still cannot grant
execution, dispatch, runtime replanning, success, or terminal closure. Those
fields are hard false in the report schema.

## Shadow Dossier

The next no-effect slice is
`scripts/report_governed_planning_profile_shadow_dossier.py`. It runs the
read-only adapter across representative gateway planning classes:

1. uncompiled conversation;
2. read-only search;
3. compound search-to-notification;
4. high-risk payment;
5. search blocked by open world-state contradictions.

The dossier output is governed by
`schemas/governed_planning_profile_shadow_dossier.schema.json`. It records
scenario summaries, full admission reports, aggregate blocker counts, and
closure conditions. The dossier is a local proof surface only: it does not
register a planner, call a router, execute a plan, dispatch work, enable
runtime replanning, approve promotion, claim success, or provide terminal
closure.

The dossier is useful because it proves profile projection over multiple plan
shapes before operator shadow-pilot evidence exists. A verified dossier means
the local projection is structurally coherent; it does not mean runtime
promotion is authorized.

## Operator Shadow-Pilot Evidence

The next no-effect evidence slice is
`examples/governed_planning_profile_operator_shadow_pilot_evidence.awaiting_evidence.json`,
validated by
`scripts/validate_governed_planning_profile_operator_shadow_pilot_evidence.py`
and governed by
`schemas/governed_planning_profile_operator_shadow_pilot_evidence.schema.json`.

This packet binds the deterministic shadow dossier id and hash to five
operator-observation placeholders, one for each covered plan class. Each
placeholder remains `AwaitingEvidence`; parity is not confirmed, runtime
promotion is not ready, and every promotion gate still blocks runtime
promotion. The packet is therefore an intake contract for future operator
observations, not the observations themselves.

The packet also records remaining promotion gates for operator shadow-pilot
observation, runtime promotion approval, replay/recovery witness, and terminal
closure certificate. All execution, dispatch, runtime replanning, success, and
terminal closure authority stays hard false.

## Operator Shadow-Pilot Observation Receipt

The collected local observation slice is
`examples/governed_planning_profile_operator_shadow_pilot_observation_receipt.local.json`,
validated by
`scripts/validate_governed_planning_profile_operator_shadow_pilot_observation_receipt.py`
and governed by
`schemas/governed_planning_profile_operator_shadow_pilot_observation_receipt.schema.json`.

This receipt closes only the local operator shadow-pilot observation gap for
the five deterministic no-effect scenarios. It binds the prior AwaitingEvidence
request id and hash to receipt refs for each plan class, confirms that the
observed read-only projection matches the shadow dossier, and records zero
shadow mismatches.

The receipt does not authorize runtime promotion. The runtime promotion
approval, replay/recovery witness, and terminal closure certificate gates
remain `AwaitingEvidence` and continue to block promotion. Execution, dispatch,
runtime replanning, success, and terminal closure authority remain hard false.

## Runtime Promotion Approval Packet

The local runtime-promotion approval slice is
`examples/governed_planning_profile_runtime_promotion_approval_packet.local.json`,
validated by
`scripts/validate_governed_planning_profile_runtime_promotion_approval_packet.py`
and governed by
`schemas/governed_planning_profile_runtime_promotion_approval_packet.schema.json`.

This packet binds the collected local observation receipt and records that the
runtime-promotion approval criteria have passed for the no-effect shadow-pilot
surface. The approval is conditional and local-only: it confirms observation
coverage, parity, projection match, zero shadow mismatches, preserved authority
denials, and Foundation Mode no-effect boundaries.

The packet closes only the runtime-promotion approval evidence gap. It does
not authorize runtime promotion because replay/recovery witness and terminal
closure certificate evidence remain `AwaitingEvidence`. Execution, dispatch,
runtime replanning, success, and terminal closure authority remain hard false.

## Replay/Recovery Witness

The local replay/recovery slice is
`examples/governed_planning_profile_replay_recovery_witness.local.json`,
validated by
`scripts/validate_governed_planning_profile_replay_recovery_witness.py`
and governed by
`schemas/governed_planning_profile_replay_recovery_witness.schema.json`.

This witness binds the runtime-promotion approval packet to one no-effect
replay/recovery probe for each covered plan class. Each probe is digest-bound,
records zero replay mismatches, documents rollback and incident-handoff paths,
and preserves the Foundation Mode no-effect boundary.

The witness closes only the replay/recovery evidence gap. It does not execute
replay or rollback, does not authorize runtime promotion, and leaves terminal
closure certificate evidence as `AwaitingEvidence`. Execution, dispatch,
runtime replanning, success, and terminal closure authority remain hard false.

## Terminal Closure Certificate

The local terminal-closure slice is
`examples/governed_planning_profile_terminal_closure_certificate.local.json`,
validated by
`scripts/validate_governed_planning_profile_terminal_closure_certificate.py`
and governed by
`schemas/governed_planning_profile_terminal_closure_certificate.schema.json`.

This certificate binds the replay/recovery witness and records that every
promotion-evidence gate in the local no-effect ladder is now satisfied:
operator shadow-pilot observation, runtime-promotion approval,
replay/recovery witness, and terminal closure certificate. Each covered plan
class receives a `ClosedNoEffect` terminal record that preserves zero replay
mismatches, rollback documentation, and incident-handoff documentation.

The certificate closes only the local evidence ladder. It does not authorize
runtime promotion or activate any runtime path. Runtime promotion remains a
separate authority-changing action that must be explicitly submitted and
governed before activation. Execution, dispatch, runtime replanning, success,
and terminal closure authority remain hard false.

## Runtime Authorization Request

The local runtime-authorization request slice is
`examples/governed_planning_profile_runtime_authorization_request.local.json`,
validated by
`scripts/validate_governed_planning_profile_runtime_authorization_request.py`
and governed by
`schemas/governed_planning_profile_runtime_authorization_request.schema.json`.

This request binds the terminal closure certificate and records that the
operator authorization question has been submitted as a no-effect governance
artifact. It preserves the completed evidence ladder while making the next
authority dependency explicit: a separate signed runtime-authorization response
witness is still required.

The request does not authorize runtime promotion. It records
`operator_response_required = true`, `operator_response_collected = false`, and
`runtime_authorization_gate_satisfied = false`. Execution, dispatch, runtime
replanning, success, and terminal closure authority remain hard false.

## Runtime Authorization Generic Continuation Rejection

The local generic-continuation rejection slice is
`examples/governed_planning_profile_runtime_authorization_generic_continuation_rejection.local.json`,
validated by
`scripts/validate_governed_planning_profile_runtime_authorization_generic_continuation_rejection.py`
and governed by
`schemas/governed_planning_profile_runtime_authorization_generic_continuation_rejection.schema.json`.

This witness binds the runtime authorization request and records that generic
`continue` input is not a signed runtime authorization approval. It records
`solver_outcome = GovernanceBlocked`,
`runtime_authorization_response_status = RejectedNoEffect`, and
`generic_continuation_rejected = true`.

The witness does not authorize runtime promotion. It keeps
`operator_approval_collected = false`, `signed_approval_present = false`, and
`runtime_authorization_gate_satisfied = false`. Execution, dispatch, runtime
replanning, success, runtime activation, and terminal closure authority remain
hard false. A future explicit signed runtime authorization approval witness
remains the next required gate before activation.

## Runtime Authorization Approval Witness Template

The local approval-witness-template slice is
`examples/governed_planning_profile_runtime_authorization_approval_witness_template.local.json`,
validated by
`scripts/validate_governed_planning_profile_runtime_authorization_approval_witness_template.py`
and governed by
`schemas/governed_planning_profile_runtime_authorization_approval_witness_template.schema.json`.

This template binds the runtime authorization request and the generic
continuation rejection witness, then defines the required fields for a future
explicit signed runtime authorization approval witness. It is not itself an
approval witness. It keeps `template_accepted_as_approval = false`,
`approval_witness_collected = false`, `operator_response_recorded = false`,
`operator_approval_collected = false`, `signed_approval_present = false`, and
`runtime_authorization_gate_satisfied = false`.

The template preserves the remaining gates explicitly: an explicit signed
runtime authorization approval witness must be collected first, and runtime
activation still requires a separate governed activation gate. Runtime
promotion, execution, dispatch, runtime replanning, success claims, runtime
activation, and terminal closure authority remain hard false.

## Runtime Authorization Signed Approval Intake

The local signed-approval-intake slice is
`examples/governed_planning_profile_runtime_authorization_signed_approval_intake.local.json`,
validated by
`scripts/validate_governed_planning_profile_runtime_authorization_signed_approval_intake.py`
and governed by
`schemas/governed_planning_profile_runtime_authorization_signed_approval_intake.schema.json`.

This intake contract binds the approval witness template and records the exact
future signed approval values that must be supplied: operator identity,
explicit decision value, source request hash acknowledgement, generic
continuation rejection hash acknowledgement, authority-scope acknowledgement,
activation separation acknowledgement, rollback and hysteresis acknowledgement,
signed timestamp, and signature reference. It is not a signed approval witness
and does not verify a signature.

The intake keeps `intake_accepted_as_approval = false`,
`signed_approval_witness_collected = false`, `operator_response_recorded =
false`, `operator_approval_collected = false`, `signed_approval_present =
false`, `decision_value_accepted = false`, `signature_verified = false`, and
`runtime_authorization_gate_satisfied = false`. Generic continuation remains
non-authorizing. Runtime activation still requires a separate governed
activation gate after a real signed approval witness is collected and verified.

## Validation

```text
python scripts/validate_governed_planning_profile.py
python scripts/validate_governed_planning_profile.py --json
python scripts/report_governed_planning_profile_shadow_dossier.py
python scripts/report_governed_planning_profile_shadow_dossier.py --json
python scripts/validate_governed_planning_profile_operator_shadow_pilot_evidence.py
python scripts/validate_governed_planning_profile_operator_shadow_pilot_evidence.py --json
python scripts/validate_governed_planning_profile_operator_shadow_pilot_observation_receipt.py
python scripts/validate_governed_planning_profile_operator_shadow_pilot_observation_receipt.py --json
python scripts/validate_governed_planning_profile_runtime_promotion_approval_packet.py
python scripts/validate_governed_planning_profile_runtime_promotion_approval_packet.py --json
python scripts/validate_governed_planning_profile_replay_recovery_witness.py
python scripts/validate_governed_planning_profile_replay_recovery_witness.py --json
python scripts/validate_governed_planning_profile_terminal_closure_certificate.py
python scripts/validate_governed_planning_profile_terminal_closure_certificate.py --json
python scripts/validate_governed_planning_profile_runtime_authorization_request.py
python scripts/validate_governed_planning_profile_runtime_authorization_request.py --json
python scripts/validate_governed_planning_profile_runtime_authorization_generic_continuation_rejection.py
python scripts/validate_governed_planning_profile_runtime_authorization_generic_continuation_rejection.py --json
python scripts/validate_governed_planning_profile_runtime_authorization_approval_witness_template.py
python scripts/validate_governed_planning_profile_runtime_authorization_approval_witness_template.py --json
python scripts/validate_governed_planning_profile_runtime_authorization_signed_approval_intake.py
python scripts/validate_governed_planning_profile_runtime_authorization_signed_approval_intake.py --json
python -m pytest tests/test_validate_governed_planning_profile.py -q
python -m pytest tests/test_gateway/test_governed_planning_profile_adapter.py -q
python -m pytest tests/test_report_governed_planning_profile_shadow_dossier.py -q
python -m pytest tests/test_validate_governed_planning_profile_operator_shadow_pilot_evidence.py -q
python -m pytest tests/test_validate_governed_planning_profile_operator_shadow_pilot_observation_receipt.py -q
python -m pytest tests/test_validate_governed_planning_profile_runtime_promotion_approval_packet.py -q
python -m pytest tests/test_validate_governed_planning_profile_replay_recovery_witness.py -q
python -m pytest tests/test_validate_governed_planning_profile_terminal_closure_certificate.py -q
python -m pytest tests/test_validate_governed_planning_profile_runtime_authorization_request.py -q
python -m pytest tests/test_validate_governed_planning_profile_runtime_authorization_generic_continuation_rejection.py -q
python -m pytest tests/test_validate_governed_planning_profile_runtime_authorization_approval_witness_template.py -q
python -m pytest tests/test_validate_governed_planning_profile_runtime_authorization_signed_approval_intake.py -q
```

STATUS:
  Completeness: static contract, Foundation fixture, first read-only adapter, multi-class shadow dossier, operator evidence intake contract, local operator observation receipt, runtime-promotion approval packet, replay/recovery witness, terminal closure certificate, runtime authorization request, generic continuation rejection witness, runtime authorization approval witness template, and signed approval intake contract defined
  Authority: no execution, dispatch, connector, write, migration, replanning, success, replay, rollback, runtime promotion, or closure authority
  Open issues: explicit signed runtime authorization approval witness remains absent; separate runtime activation gate remains absent
  Next action: collect explicit signed runtime authorization approval witness values before activation
