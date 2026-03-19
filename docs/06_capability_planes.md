# Capability Planes

Scope: all Mullu Platform modules. Each plane is a bounded domain of responsibility.

A plane owns its artifacts, defines its inputs and outputs, and declares what it MUST NOT do. No plane may bypass another plane's contract boundaries.

## 1. Governance Plane

Purpose: enforce platform-wide policy, invariant compliance, and access control.

Inputs: policy definitions, invariant declarations, access control lists, escalation requests.
Outputs: `PolicyDecision`, governance audit entries, escalation records.

Prohibited behaviors:
- MUST NOT execute actions directly.
- MUST NOT modify world state.
- MUST NOT admit knowledge (that is Learning Admission's role).

Dependencies: none. Governance is a root plane.

## 2. Perception Plane

Purpose: convert raw sensory input into structured observations.

Inputs: raw screen frames, DOM snapshots, API responses, file contents, sensor data.
Outputs: structured observations with source attribution and confidence scores.

Prohibited behaviors:
- MUST NOT interpret intent from observations.
- MUST NOT trigger actions based on perceived content.
- MUST NOT persist observations directly to long-term memory.

Dependencies: none for intake. World State Plane for delivery.

## 3. World State Plane

Purpose: maintain the canonical representation of the current environment.

Inputs: structured observations from Perception, execution results from Execution, verification outcomes.
Outputs: state snapshots, state diffs, state hashes for trace reproducibility.

Prohibited behaviors:
- MUST NOT generate observations (that is Perception's role).
- MUST NOT plan or decide (that is Planning's role).
- MUST NOT hold stale state without expiry markers.

Dependencies: Perception Plane, Verification Plane.

## 4. Capability Plane

Purpose: declare and resolve what subjects can do in the current context.

Inputs: `CapabilityDescriptor` registrations, subject identifiers, scope constraints.
Outputs: capability registry snapshots, capability resolution results.

Prohibited behaviors:
- MUST NOT grant capabilities not declared in the registry.
- MUST NOT execute capabilities (that is Execution's role).
- MUST NOT infer capabilities from observed behavior.

Dependencies: Governance Plane for access constraints.

## 5. Planning Plane

Purpose: produce deterministic plans from state, registry, and goal inputs.

Inputs: world state snapshot, capability registry snapshot, goal specification, admitted knowledge.
Outputs: `plan_id`-bearing plan artifacts with ordered action sequences.

Prohibited behaviors:
- MUST NOT use unadmitted knowledge.
- MUST NOT execute any step of the plan.
- MUST NOT produce plans that bypass the policy gate.
- MUST NOT produce nondeterministic output for identical inputs (Invariant 1).

Dependencies: World State Plane, Capability Plane, Memory Plane (admitted knowledge only).

## 6. Execution Plane

Purpose: carry out approved plan steps and record observed effects.

Inputs: policy-approved action steps, execution context, capability bindings.
Outputs: `ExecutionResult` with actual effects, execution traces.

Prohibited behaviors:
- MUST NOT begin without a `PolicyDecision` of `allow` (Invariant 6).
- MUST NOT fabricate actual effects; MUST observe them.
- MUST NOT skip verification handoff.
- MUST NOT re-run uncontrolled external effects during replay (Invariant 4).

Dependencies: Governance Plane (policy gate), Capability Plane (bindings), Planning Plane (action steps).

## 7. Verification Plane

Purpose: close every action with a terminal verification outcome.

Inputs: `ExecutionResult`, expected effects from plan, observation evidence.
Outputs: `VerificationResult` with status `pass`, `fail`, or `inconclusive`.

Prohibited behaviors:
- MUST NOT verify without referencing the execution it closes.
- MUST NOT allow an action to complete without exactly one closure (Invariant 7).
- MUST NOT modify execution results.

Dependencies: Execution Plane, Perception Plane (for evidence gathering).

## 8. Memory Plane

Purpose: store, index, retrieve, and promote knowledge across memory tiers.

Inputs: verified execution outcomes, admitted learning artifacts, explicit storage requests.
Outputs: knowledge retrieval results, memory tier metadata, promotion/demotion records.

Prohibited behaviors:
- MUST NOT store unadmitted knowledge for planning use.
- MUST NOT mutate kernel invariants through learning paths (Invariant 8).
- MUST NOT serve expired or revoked knowledge without marking it as such.

Dependencies: Verification Plane (only verified outcomes enter), Governance Plane (retention policies).

## 9. Communication Plane

Purpose: manage structured message exchange between agents, users, and external parties.

Inputs: message payloads, routing metadata, channel declarations.
Outputs: delivered message receipts, delivery failure records.

Prohibited behaviors:
- MUST NOT send messages that bypass policy review when policy applies.
- MUST NOT fabricate message attribution.
- MUST NOT route messages to undeclared channels.

Dependencies: Governance Plane (policy on outbound communication), Coordination Plane (multi-agent routing).

## 10. External Integration Plane

Purpose: manage connections to systems outside the platform boundary.

Inputs: connector configurations, credential scopes, integration requests.
Outputs: integration responses with source attribution, connector health records.

Prohibited behaviors:
- MUST NOT use credentials outside their declared scope.
- MUST NOT cache external responses as trusted world state without re-observation.
- MUST NOT expose internal identifiers to external systems.

Dependencies: Governance Plane (credential policy), Capability Plane (integration capabilities).

## 11. Temporal Plane

Purpose: manage time-dependent scheduling, deadlines, and temporal ordering.

Inputs: schedule definitions, deadline constraints, temporal ordering requirements.
Outputs: scheduling decisions, deadline breach alerts, temporal ordering proofs.

Prohibited behaviors:
- MUST NOT execute actions (that is Execution's role).
- MUST NOT fabricate timestamps.
- MUST NOT silently drop expired deadlines.

Dependencies: Governance Plane (scheduling policy), Execution Plane (for deadline-bound actions).

## 12. Coordination Plane

Purpose: orchestrate multi-agent and multi-step workflows.

Inputs: workflow definitions, agent availability, dependency graphs.
Outputs: coordination directives, workflow state transitions, conflict resolution records.

Prohibited behaviors:
- MUST NOT override individual agent policy decisions.
- MUST NOT assign work to agents lacking required capabilities.
- MUST NOT hide coordination failures from the trace.

Dependencies: Capability Plane (agent capabilities), Governance Plane (coordination policy), Planning Plane (workflow plans).

## 13. Meta-Reasoning Plane

Purpose: evaluate and adjust the platform's own reasoning processes.

Inputs: trace histories, verification outcomes, planning performance metrics.
Outputs: reasoning adjustment proposals, strategy selection records.

Prohibited behaviors:
- MUST NOT mutate kernel invariants (Invariant 8).
- MUST NOT bypass the learning admission gate to inject knowledge.
- MUST NOT execute adjustments without policy approval.
- MUST NOT reason about its own meta-reasoning recursively without a bounded depth limit.

Dependencies: Memory Plane (historical traces), Governance Plane (approval for adjustments), Verification Plane (outcome data).

## Cross-plane rules

1. No plane may invoke another plane's internal artifacts directly. All cross-plane communication uses declared interfaces.
2. Every cross-plane data transfer MUST carry source plane attribution.
3. A plane failure MUST NOT silently propagate. The consuming plane MUST handle or escalate.
4. Plane boundaries are enforcement points for Shared Invariants 1-8.
