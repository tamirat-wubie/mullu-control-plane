# Governed Operational Intelligence Extension

Purpose: define the next Mullu platform layer that moves from governed task execution to governed operational intelligence.
Governance scope: world state, goal compilation, simulation, capability certification, worker mesh execution, memory admission, utility routing, collaboration cases, and external proof anchoring.
Dependencies: `docs/31_operational_graph.md`, `docs/33_governed_evolution.md`, `docs/37_terminal_closure_certificate.md`, `docs/38_closure_learning_admission.md`, `docs/39_governed_capability_fabric.md`, `docs/56_general_agent_capability_roadmap.md`, `KNOWN_LIMITATIONS_v0.1.md`, and `SECURITY_MODEL_v0.1.md`.
Invariants:
- No operational action may execute from a free-form request alone.
- No plan step may execute without checked preconditions, policy admission, required evidence, bounded side effects, and recovery coverage.
- No capability may be represented as production-ready without a maturity level and promotion evidence.
- No worker may act outside lease, budget, scope, timeout, sandbox, policy, receipt, verification, and recovery bounds.
- No closure-derived knowledge may enter planning without learning admission.
- No important effect-bearing action is complete without terminal closure and a signed evidence bundle when anchoring is required.

## Architecture

Mullu+ adds six planes above the existing governance guard chain:

```text
Mullu+
  -> Governance Plane
  -> World Plane
  -> Planning Plane
  -> Capability Plane
  -> Evidence Plane
  -> Intelligence Plane
  -> Product Plane
```

The extension does not weaken the current command spine. It adds typed world context, compiled plans, simulation, certified capabilities, bounded workers, and anchored proof before any operational action can claim completion.

## Formal Extension

Current symbolic structure:

```text
S := <I, Lambda, Sigma, Gamma, H>
```

Extended symbolic structure:

```text
S+ := <I, Lambda, Sigma, Gamma, H, T, Omega, Pi, Kappa, E, U>
```

| Symbol | Meaning |
| --- | --- |
| `T` | Temporal kernel |
| `Omega` | World-state graph |
| `Pi` | Goal and plan compiler |
| `Kappa` | Capability forge and registry |
| `E` | Eval and simulation environment |
| `U` | Utility, risk, and cost model |

Core execution rule:

```text
action_executable(a) <=>
  Lambda_authority(a)
  and Lambda_policy(a)
  and Lambda_budget(a)
  and Lambda_time(a, T)
  and Omega_supports(a)
  and Pi_plan_valid(a)
  and E_simulation_pass(a)
  and Kappa_capability_certified(a)
  and H_no_contradicting_closure(a)
```

## World Plane

The World Plane persists operational reality as a typed graph, not only as message memory.

Required objects:

| Object | Role |
| --- | --- |
| `WorldEntity` | Stable identity for a person, vendor, invoice, account, asset, document, device, case, or organization |
| `WorldRelation` | Typed edge between entities with source, validity, and evidence |
| `WorldEvent` | Timestamped observation or state transition |
| `WorldClaim` | Stated proposition with source, confidence, freshness, and risk class |
| `WorldState` | Materialized state projection over entities, relations, and events |
| `EvidenceRef` | Pointer to source document, receipt, approval, audit record, or external witness |
| `Contradiction` | Conflict between claims, states, or relations requiring resolution |
| `ValidityWindow` | `valid_from`, `valid_until`, and refresh requirement |

World graph invariants:

1. Every operational assertion must name its source and observation time.
2. State replacement is modeled as supersession, not silent overwrite.
3. Contradicting claims must create a contradiction node and block high-risk execution until resolved or accepted by policy.
4. Planning may consume only world facts marked `allowed_for_planning`.
5. Execution may consume only world facts marked `allowed_for_execution`.

## Planning Plane

The Planning Plane compiles user intent into governed executable structure.

Required objects:

| Object | Role |
| --- | --- |
| `Goal` | User or system objective with success criteria and risk class |
| `SubGoal` | Bounded part of a goal with owner and closure condition |
| `PlanDAG` | Directed acyclic plan over typed steps and dependencies |
| `PlanStep` | One executable or reviewable unit bound to a capability |
| `Precondition` | Required fact, authority, time, budget, or evidence before execution |
| `Postcondition` | Verifiable condition after execution |
| `RequiredEvidence` | Evidence that must exist before or after a step |
| `RollbackStep` | Compensation or recovery action for bounded side effects |
| `ApprovalRequirement` | Authority requirement with role, separation of duty, and expiry |
| `TerminalCondition` | Closure condition for goal, subgoal, or plan |

Plan execution invariant:

```text
plan_step_executable(step) <=>
  preconditions_pass(step)
  and policy_allows(step)
  and required_evidence_exists(step)
  and side_effects_bounded(step)
  and recovery_exists_when_required(step)
```

The compiler must produce a plan certificate before the executor dispatches effect-bearing work.

## Simulation Plane

The Causal Simulator dry-runs risky actions before approval or execution.

Required output:

| Field | Role |
| --- | --- |
| `simulation_id` | Stable simulation identity |
| `action` | Candidate action or plan step |
| `risk` | Computed risk class |
| `would_execute` | Boolean dry-run result |
| `reason` | Primary causal explanation |
| `required_controls` | Controls needed before execution |
| `failure_modes` | Provider, policy, world-state, temporal, and recovery risks |
| `compensation_path` | Required rollback or review path |

Simulation rule:

```text
high_risk_action:
  plan -> simulate -> verify -> approve -> execute -> reconcile -> close
```

No high-risk action may use:

```text
plan -> execute
```

## Capability Plane

The Capability Plane governs creation, certification, and dispatch of executable powers.

### Capability Forge

The forge accepts API docs, schemas, runbooks, workflow descriptions, and examples. It emits candidate packages only.

Candidate package outputs:

| Artifact | Required content |
| --- | --- |
| `schema` | Input, output, error, and receipt contracts |
| `adapter` | Bounded provider adapter or worker client |
| `policy_rules` | Authority, approval, tenant, content, budget, and side-effect gates |
| `evals` | Injection, tenant boundary, approval, secret, budget, and failure tests |
| `mock_provider` | Deterministic non-production provider |
| `sandbox_tests` | Sandboxed replay evidence |
| `receipt_contract` | Command-bound proof returned by the worker |
| `rollback_path` | Compensation, downgrade, or review path |
| `documentation` | Operator contract and promotion evidence |

Forge invariant: the forge may generate candidates, but it may not self-deploy critical capabilities.

### Capability Maturity Levels

| Level | Meaning |
| --- | --- |
| `C0` | Described only |
| `C1` | Unit tested |
| `C2` | Mock tested |
| `C3` | Sandbox tested |
| `C4` | Live read-only receipt exists |
| `C5` | Live write receipt exists |
| `C6` | Production-certified |
| `C7` | Autonomy-certified |

Every capability registry entry must expose current level, evidence refs, missing promotion evidence, and allowed execution environments.

### Networked Worker Mesh

The worker mesh distributes execution while central governance remains authoritative.

Worker contract:

| Field | Role |
| --- | --- |
| `worker_id` | Stable worker identity |
| `capability` | Bound capability id |
| `tenant_id` | Tenant boundary |
| `lease_id` | Time-bounded authority grant |
| `allowed_operations` | Explicitly permitted operations |
| `forbidden_operations` | Explicitly denied operations |
| `budget` | Cost and call limit |
| `scope` | Resource and data boundary |
| `timeout` | Execution deadline |
| `sandbox` | Isolation profile |
| `receipt_schema_ref` | Required proof contract |
| `verification_ref` | Required verification contract |
| `recovery_ref` | Rollback, compensation, or review path |
| `expires_at` | Lease expiry |

Worker invariant: a worker receipt is necessary but never sufficient for terminal closure; closure still requires verification and reconciliation.

### User-Owned Agent Identity

Persistent agents are accountable identities, not anonymous processes.

Agent identity contract:

| Field | Role |
| --- | --- |
| `agent_id` | Stable agent identity |
| `owner_id` | Human or organization owner |
| `tenant_id` | Tenant boundary |
| `role` | Operational role |
| `allowed_capabilities` | Explicitly permitted capability set |
| `forbidden_capabilities` | Explicitly denied capability set |
| `budget` | Cost and action limits |
| `memory_scope` | Planning and execution memory admission |
| `approval_scope` | Approval request and grant limits |
| `delegation_scope` | Lease-bound worker delegation limits |
| `evidence_history` | Proof refs for identity outcomes |
| `reputation_score` | Evidence-derived reliability score |

Agent identity invariant: an agent cannot mutate policy, approve its own request, cross tenant scope, use unadmitted memory, delegate without a lease-bound scope, or update reputation without evidence.

## Evidence Plane

The Evidence Plane binds commands to receipts, audit, terminal certificates, learning decisions, and external anchors.

### Trust Ledger

Every important action should be represented by a signed evidence bundle:

| Field | Role |
| --- | --- |
| `bundle_id` | Evidence bundle identity |
| `tenant_id` | Tenant identity |
| `command_id` | Command identity |
| `terminal_certificate_id` | Terminal closure anchor |
| `deployment_id` | Runtime deployment identity |
| `commit_sha` | Code version |
| `hash_chain_root` | Audit chain root |
| `signature` | Signature over bundle contents |

Trust ledger invariant: audit/proof records may exist before closure, but external anchoring must bind the final terminal certificate.

### Memory Lattice

Memory is separated by use and risk:

| Memory class | Planning use |
| --- | --- |
| `raw_event_memory` | Not directly allowed |
| `episodic_closure_memory` | Allowed only through learning admission |
| `semantic_fact_memory` | Allowed if fresh, sourced, and admitted |
| `procedural_runbook_memory` | Allowed if certified and scoped |
| `policy_memory` | Allowed only from policy authority |
| `preference_memory` | Allowed only inside owner and tenant scope |
| `risk_memory` | Required for risk scoring |
| `contradiction_memory` | Blocks or escalates conflicted actions |
| `supersession_memory` | Resolves stale state without deleting history |

Required memory fields:

```text
source
observed_at
valid_from
valid_until
trust_class
supersedes
contradicts
requires_refresh
allowed_for_planning
allowed_for_execution
```

## Intelligence Plane

The Intelligence Plane improves the system without bypassing governed evolution.

| Engine | Role | Hard boundary |
| --- | --- | --- |
| `PolicyProver` | Searches for counterexamples to policy invariants | Cannot weaken policy to prove success |
| `WorkflowMiningEngine` | Detects repeated human workflows and drafts governed templates | Cannot activate workflow without operator review |
| `EconomicIntelligenceEngine` | Optimizes safe cost, risk, quality, latency, and review burden | Cannot choose cheaper route that violates controls |
| `AutonomousTestGenerationEngine` | Converts failures into permanent replay and governance tests | Cannot suppress failing traces |
| `AutonomousCapabilityUpgradeLoop` | Diagnoses, proposes, tests, and packages upgrades | Cannot deploy high-risk changes without certified approval |
| `ClaimVerificationEngine` | Separates observed facts, user claims, source claims, inferences, stale results, and contradictions | Cannot promote unverified claims into execution facts |

Utility formula:

```text
ExpectedUtility(action)
  = expected_value
  - model_cost
  - tool_cost
  - latency_cost
  - risk_cost
  - human_review_cost
  - failure_compensation_cost
```

The utility engine chooses among admitted actions only. It does not override policy, authority, or proof requirements.

## Collaboration Plane

Operations require governed negotiation, not unstructured chat.

Required objects:

| Object | Role |
| --- | --- |
| `Case` | Durable collaboration container |
| `Proposal` | Suggested action with evidence and controls |
| `Counterproposal` | Alternate path with changed constraints |
| `ApprovalRequest` | Formal authority request |
| `Obligation` | Assigned responsibility with due time |
| `Escalation` | Routing when obligations stall or risk changes |
| `Decision` | Accepted, rejected, deferred, or modified outcome |
| `Deadline` | Temporal bound |
| `Closure` | Case terminal state |

Collaboration invariant: a conversation may create proposals and cases, but only governed approvals and terminal closure can authorize and certify effects.

## Product Plane

Domain operating packs package the governed substrate into buyer-visible outcomes.

| Pack | Required focus |
| --- | --- |
| `FinanceOpsPack` | Invoice approval, payment guard, budget enforcement, duplicate detection |
| `CustomerSupportPack` | Triage, escalation, refund approval, SLA tracking |
| `CompliancePack` | Evidence bundles, audit exports, policy exceptions |
| `ResearchPack` | Source tracking, literature review, experiment log, claim graph |
| `HealthcareAdminPack` | Appointment support, intake summaries, escalation, privacy gates |
| `EducationPack` | Tutoring, lesson planning, assessment feedback, learning memory |
| `ManufacturingOpsPack` | SOP assistant, incident reports, maintenance workflows |

Pack invariant: a pack packages schemas, policies, workflows, connectors, evals, risk rules, approval roles, evidence exports, and dashboard views; it does not create authority outside the capability registry.

## Multimodal Operating Layer

Governed perception and action may cover:

```text
text
PDF
spreadsheet
image
voice
screen
browser
email
calendar
forms
video frames
```

Each modality must define parse scope, side-effect scope, evidence receipt, source preservation, and external-send policy.

Example rule:

```text
Document Worker:
  can parse PDF
  can extract invoice fields
  cannot send document externally unless approved
  must produce extraction receipt
  must preserve source reference
```

## Physical Boundary

Physical, IoT, and robotics actions are later-stage capabilities. They require a separate physical-action boundary:

```text
physical actuator
hardware identity
safety envelope
manual override
emergency stop
simulation pass
operator approval
environment sensor confirmation
```

Rule:

```text
physical-world side effects require stricter governance than digital side effects
```

Do not admit physical control until digital governance has production witness evidence.

## First Five Build Order

| Order | Addition | Reason | First artifact |
| --- | --- | --- | --- |
| 1 | World-State Graph | Gives durable operational reality | `world_state.schema.json` and append-only store |
| 2 | Goal Compiler | Converts vague requests into governed plans | `goal.schema.json`, plan compiler, plan certificate |
| 3 | Causal Simulator | Blocks risky direct execution | simulation receipt schema and high-risk gate |
| 4 | Capability Forge | Creates certified candidate capabilities | candidate package schema and forge validator |
| 5 | Networked Worker Mesh | Enables distributed execution under central governance | worker lease schema and signed receipt verifier |

These five are the minimum path from governed task runtime to governed operational intelligence platform.

## Promotion Gates

| Gate | Required evidence |
| --- | --- |
| `design_admitted` | Architecture spec, object contracts, invariants |
| `schema_admitted` | JSON schemas, examples, validators |
| `mock_certified` | Unit tests, mock provider tests, failure fixtures |
| `sandbox_certified` | Sandbox replay, receipt verification, rollback case |
| `live_read_certified` | Live read-only receipt, dependency probe, deployment witness |
| `live_write_certified` | Live write receipt, signed worker response, compensation proof |
| `production_certified` | ChangeCommand, ChangeCertificate, canary result, terminal closure |
| `autonomy_certified` | Bounded autonomous loop, external anchor, red-team counterexample pass |

## Non-Goals

- This extension does not grant free-form agent autonomy.
- This extension does not let generated capabilities self-deploy critical powers.
- This extension does not replace terminal closure with worker receipts.
- This extension does not allow memory to enter planning without admission.
- This extension does not treat cost optimization as a governance override.

## Proof-of-Resolution Stamp

```text
PRS-62:
  distinction: operational intelligence is separated from task execution
  constraint: every new power remains under guard chain, proof, and closure
  ontology: required objects are named and bounded
  topology: planes and dependencies are explicit
  form: maturity levels, promotion gates, and execution rules are decidable
  organization: first-five build order defines sequencing
  module: each plane owns one bounded responsibility
  execution: action_executable rule defines admission
  architecture: central governance remains authoritative over workers
  performance: utility engine optimizes only admitted actions
  feedback: prover, simulator, tests, mining, and upgrade loop close learning paths
  evolution: high-risk changes remain under ChangeCommand and ChangeCertificate
```
