# Operating Substrate Integration Plan

> **In one box:** This page turns the operating-substrate foundation into a
> build plan for this repository. It shows what should change first, what must
> reuse existing Mullu Govern parts, and what remains blocked until evidence is
> collected. *(Doc type: Reference.)*

Purpose: map the operating-substrate foundation into the current Mullu Control Plane without creating a parallel architecture.
Governance scope: Capability ABI, self-model projection, world-state projection, Universal Action Orchestration, Symbolic Data Layer, Foundation Mode, and terminal closure.
Dependencies: `docs/62_governed_operational_intelligence.md`, `docs/39_governed_capability_fabric.md`, `docs/16_world_state_plane.md`, `docs/22_goal_reasoning.md`, `docs/FOUNDATION_MODE.md`, `gateway/world_state.py`, `gateway/capability_fabric.py`, `mcoi/mcoi_runtime/core/universal_action_kernel.py`, `mcoi/mcoi_runtime/core/capability_manifest_registry.py`, and `mcoi/mcoi_runtime/contracts/meta_reasoning.py`.
Invariants:
- The operating substrate is an integration layer inside Mullu Govern, not a new root system.
- No capability executes without admitted capability, policy, evidence, receipt, and recovery boundaries.
- World-state is projected from sourced claims and receipts; memory notes are not current truth.
- Self-model state is a read model over registered modules, capability health, evidence, and incidents.
- Foundation Mode blocks deployment, public readiness, legal, customer, paid infrastructure, and production-health claims unless named witnesses close.
- Mfidel atomicity remains unchanged; this plan does not decompose fidel shape or sound.

## Distinction

The pasted foundation describes a governed operating substrate. In this repo the
correct target is:

```text
Mullu Govern operating substrate
  = existing control-plane governance
  + capability ABI coverage
  + self-model read model
  + world-state projection
  + UAO admission and receipt closure
```

Do not add a separate `MulluOS` package, database root, action kernel, or policy
stack. That would split authority. The existing authority path remains:

```text
intent
  -> goal / plan
  -> world-state support
  -> simulation
  -> capability admission
  -> Universal Action Orchestration
  -> governed dispatch
  -> receipt / reconciliation
  -> terminal closure
  -> learning admission
```

## Existing Surface Map

| Foundation object | Existing repo surface | Integration judgment |
| --- | --- | --- |
| Capability ABI | `mcoi/mcoi_runtime/contracts/capability_manifest.py`, `mcoi/mcoi_runtime/core/capability_manifest_registry.py`, `gateway/capability_fabric.py` | Reuse and extend coverage. |
| Self-model | `mcoi/mcoi_runtime/contracts/meta_reasoning.py`, provider health, capability read models, incident records | Add a bounded projection, not a new authority. |
| World-state model | `gateway/world_state.py`, `mcoi/mcoi_runtime/core/world_state.py`, `schemas/world_state.schema.json` | Reuse; align naming and projection rules. |
| Goal hierarchy | `gateway/goal_compiler.py`, `mcoi/mcoi_runtime/contracts/goal.py`, `docs/22_goal_reasoning.md` | Reuse; bind goal state to UAO receipts. |
| Action admission kernel | `mcoi/mcoi_runtime/core/universal_action_kernel.py`, `docs/UNIVERSAL_ACTION_ORCHESTRATION.md` | Canonical action path. |
| Outcome learning | `mcoi/mcoi_runtime/core/outcome_learning_bridge.py`, closure learning modules | Keep candidate-only until validation. |
| Evaluation and adversarial lab | `gateway/evals.py`, `gateway/solver_forge_red_team_adapter.py`, `mcoi/mcoi_runtime/core/red_team_harness.py` | Reuse; add ABI and self-model cases. |
| Distributed coordination | temporal lease receipts, worker lease admission, coordination locks | Promote to durable stores before multi-worker production. |
| Data governance | `gateway/data_governance.py`, `mcoi/mcoi_runtime/core/data_governance.py` | Reuse; attach to modal observations and world-state candidates. |
| Human authority | `mcoi/mcoi_runtime/core/organization_kernel.py`, approval and authority docs | Reuse; expose self-model repair gates. |
| Incident response | `mcoi/mcoi_runtime/contracts/incident.py`, recovery modules | Reuse; bind capability degradation to self-model health. |
| Modal unification | multimodal operating layer docs and receipts | Reuse; require source-preserving observations. |

## First Build Unit

Build the first unit as one reversible proof thread:

```text
Capability ABI coverage
  -> self-model projection
  -> world-state projection binding
  -> UAO gate evidence
  -> operator read model
```

This sequence is narrower than the pasted foundation. It is the smallest unit
that prevents feature accumulation because each new capability becomes:

```text
declared
bounded
testable
auditable
governable
revocable
projectable
```

## Required Changes

| Order | Change | Files likely touched | Verification |
| --- | --- | --- | --- |
| 1 | Define self-model projection contract for module health, capability maturity, dependency refs, open incidents, and evidence refs. | `mcoi/mcoi_runtime/contracts/meta_reasoning.py`, `mcoi/tests/test_operating_substrate_self_model.py` | Contract tests and dashboard/read-model tests. |
| 2 | Add self-model projector that reads admitted capability manifests, subsystem health, world-state health, and runtime evidence without mutating policy. | `mcoi/mcoi_runtime/core/operating_substrate_self_model.py` | Unit tests for healthy, degraded, unknown, rejected. |
| 3 | Bind capability manifest registry coverage into the self-model read model. | `gateway/capability_fabric.py`, `mcoi/mcoi_runtime/core/capability_manifest_registry.py` | Capability manifest tests and fabric admission tests. |
| 4 | Bind world-state projection eligibility into action admission evidence. | `mcoi/mcoi_runtime/core/universal_action_kernel.py`, world-state tests | UAO tests covering open contradiction and stale claim. |
| 5 | Add operator read model for substrate status with no raw private reasoning, secrets, or provider-specific private values. | dashboard/operator modules and schemas | API/read-model tests. |

## Implementation Witness

Current local implementation closes the first read-model slice:

- `OperatingSubstrateSelfModelProjection` records capability maturity, admission, health, world-state status, evidence refs, incident refs, and Solver Outcome classification without mutation authority.
- `CapabilityManifestRegistry.read_model` exposes per-capability ABI coverage records for admitted, rejected, and evidence-bound manifests.
- `MaturityProjectingCapabilityAdmissionGate.read_model` classifies installed capability manifest coverage as complete, partial, missing, or unconfigured.
- `build_operating_substrate_self_model` projects admitted, rejected, missing, and gateway-classified capability manifest evidence into a read-only self-model.
- `OperatingSubstrateSummary` and `DashboardSnapshot.operating_substrate` expose a bounded operator view with no raw private reasoning and no mutation authorization.
- `DashboardEngine.build_operating_substrate_summary` and `DashboardBridge.full_snapshot` pass the projection into the existing dashboard path without creating a parallel action kernel.
- `UniversalActionRequest.operating_substrate_projection` lets strict UAO callers bind self-model evidence before governed dispatch.
- `WorldSupportCertificate.evidence_refs` and `OperatingSubstrateSupportCertificate.evidence_refs` feed the UAO `evidence_sufficient` guard, input refs, proof hash, and command replay proof detail.
- Missing required self-model evidence returns `AwaitingEvidence`; unhealthy or rejecting self-model evidence returns `GovernanceBlocked`; neither path dispatches.

## Non-Changes

The first proof thread must not:

- rename the product or replace Mullu Govern with a separate brand;
- create a new root action kernel outside UAO;
- claim production readiness or external availability;
- mutate DNS, legal records, customer state, payment state, or deployment state;
- promote lessons directly into global policy;
- add self-changing behavior without governed evolution and rollback evidence.

## Admission Rule

The integrated substrate should use this rule:

```text
effect_bearing(action) admitted iff:
  capability_manifest_admitted(action.capability)
  and self_model_allows(action.capability, action.environment)
  and world_state_supports(action.goal)
  and goal_authorizes(action)
  and policy_allows(action)
  and resource_budget_available(action)
  and evidence_current(action)
  and recovery_available(action)
  and receipt_emittable(action)
```

Unknown on any hard guard returns `AwaitingEvidence` or `GovernanceBlocked`.
Resource pressure never converts hard unknown into execution permission.

## Constructive Deltas

| Delta | Effect |
| --- | --- |
| Capability manifests become the first executable boundary. | Loose tools become governed capabilities. |
| Self-model becomes a read model over evidence. | Operators can see what is healthy, degraded, experimental, or revoked. |
| World-state remains claim-based and receipt-bound. | Current truth is not confused with notes or memory. |
| UAO remains the only effect-bearing path. | Execution authority stays centralized and auditable. |
| Outcome learning remains candidate-based. | Incidents improve tests without silently rewriting policy. |

## Fracture Deltas To Avoid

| Fracture | Block |
| --- | --- |
| Parallel operating substrate package | Split authority and duplicate policy. |
| Self-model as a mutating controller | Hidden self-change path. |
| Memory summaries as world-state facts | Stale truth and unsafe planning. |
| Durable worker execution before durable leases | Split-brain mutation risk. |
| Public readiness wording before witnesses | Foundation Mode violation. |

## Verification Lanes

Focused implementation should run:

```powershell
python -m pytest tests/test_operating_substrate_integration_plan.py -q
python -m pytest mcoi/tests/test_operating_substrate_self_model.py mcoi/tests/test_meta_reasoning.py -q
python -m pytest mcoi/tests/test_dashboard_contracts.py mcoi/tests/test_dashboard_engine.py mcoi/tests/test_dashboard_integration.py -q
python -m pytest mcoi/tests/test_world_state.py mcoi/tests/test_world_state_integration.py -q
python -m pytest mcoi/tests/test_capability_manifest_registry.py -q
python -m pytest mcoi/tests/test_universal_action_kernel.py -q
python scripts/run_workspace_governance_checks.py --json
```

If a focused test path is absent in a branch, replace it with the nearest
existing contract test and record `AwaitingEvidence` for the missing lane.

## Discipline Findings

| Discipline | Lens finding | Gap or pass | Fix |
| --- | --- | --- | --- |
| Strategy/Product | The foundation belongs under Foundation Mode and Mullu Govern, not a separate product claim. | Pass | Keep language bounded to repository-local architecture. |
| Design/Research | Operator readability is a risk because the substrate is deep. | Partial | Compact self-model/operator projection exists; broad UI work remains later. |
| Engineering | Core primitives already exist. | Pass | Integrate through existing contracts and kernels. |
| Quality/Security | ABI and self-model tests are needed before promotion. | Pass | Self-model, dashboard, UAO evidence-binding, manifest registry coverage, and gateway fabric coverage tests exist. |
| Operations | Durable coordination remains the production blocker. | Gap | Require lease and fencing evidence before multi-worker mutation. |
| Business/GTM | External readiness is not closed. | Gap | Preserve `AwaitingEvidence` until legal, customer, deployment, and production witnesses exist. |

## Go deeper / where to go next

| You now want to... | Go to |
| --- | --- |
| See the operating-intelligence roadmap | [Governed Operational Intelligence Extension](62_governed_operational_intelligence.md) |
| Review governed capability admission | [Governed Capability Fabric](39_governed_capability_fabric.md) |
| Review world-state boundaries | [World State Plane](16_world_state_plane.md) |
| Review goal reasoning | [Goal Reasoning](22_goal_reasoning.md) |
| Return to the documentation map | [Start Here](START_HERE.md) |

Back to [Start Here](START_HERE.md).
