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

## Validation

```text
python scripts/validate_governed_planning_profile.py
python scripts/validate_governed_planning_profile.py --json
python -m pytest tests/test_validate_governed_planning_profile.py -q
python -m pytest tests/test_gateway/test_governed_planning_profile_adapter.py -q
```

STATUS:
  Completeness: static contract, Foundation fixture, and first read-only adapter defined
  Authority: no execution, dispatch, connector, write, migration, replanning, success, or closure authority
  Open issues: operator shadow-pilot evidence, runtime promotion approval, replay, recovery, and closure evidence remain AwaitingEvidence
  Next action: run shadow admission reports across more plan classes before any runtime promotion
