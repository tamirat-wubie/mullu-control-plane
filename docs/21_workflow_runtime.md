# 21 - Cross-Plane Workflow Runtime

> **In one box:** How several [skills](GLOSSARY.md#skill--skill-boundary) are
> chained into one larger workflow that still passes every gate at every step.
> New here? → [Plain-English Overview](explain/PLAIN_ENGLISH.md); unknown word?
> → [Glossary](GLOSSARY.md). *(Doc type: Reference.)*

## Purpose

The cross-plane workflow runtime composes skills across capability planes into
governed multi-step jobs. A workflow is a directed acyclic graph of stages where
each stage may invoke a skill, require operator approval, observe system state,
communicate with external systems, or wait for an asynchronous event. The
runtime enforces that every stage transition is explicit, verified, and subject
to the same autonomy and policy constraints that govern individual skill
execution.

For trusted local requests, the default workflow shape is autonomous execution:
skill stages run in topological order without operator interruption when the
capability gate admits the action, the effects are local or reversible, and each
stage emits bounded verification evidence. Approval stages are boundary stages,
not routine stage separators.

## Owned Artifacts

| Artifact | Role |
|---|---|
| `WorkflowDescriptor` | Immutable definition of a workflow's stages and bindings. |
| `WorkflowStage` | One unit of work within a workflow (skill execution, approval gate, etc.). |
| `WorkflowBinding` | Data-flow edge connecting one stage's output to another's input. |
| `WorkflowExecutionRecord` | Full trace of a workflow run including per-stage results. |
| `WorkflowTransition` | Typed edge describing how control flows between stages. |
| `WorkflowVerificationRecord` | Post-execution verification of a completed workflow. |

## Lifecycle

A workflow execution progresses through the following states:

```
draft --> validated --> running --> completed
                           |------> failed
                           |------> suspended
```

- **draft**: Descriptor created but not yet validated.
- **validated**: All stages, bindings, and transitions are structurally sound (no cycles, all references resolve).
- **running**: Execution has started; stages are being processed in topological order.
- **completed**: All stages finished successfully and verification passed.
- **failed**: A stage failed and the workflow stopped (governed early-stop).
- **suspended**: Execution paused by operator intervention or approval timeout.

## Stage Types

| Type | Description |
|---|---|
| `skill_execution` | Invoke a registered skill via the skill system. |
| `approval_gate` | Pause until an operator approves continuation for a modeled hard boundary. |
| `observation` | Capture current system or environment state. |
| `communication` | Send or receive a message through the communication plane. |
| `wait_for_event` | Block until an external event arrives. |

## Local Developer Workflow v1

`mullu.local_developer_workflow.v1` is the reusable foundation-stage software
delivery chain. It composes existing skills and capability gates; it does not
create new execution authority.

Canonical implementation:

```text
mcoi/mcoi_runtime/core/capability_unlock_ladder.py
```

Reusable closure helpers:

```text
mullu_local_developer_workflow_v1_descriptor()
validate_local_developer_workflow_descriptor()
build_local_developer_workflow_read_model()
```

Operator read endpoint:

```text
GET /api/v1/workflow/local-developer/read-model
```

The endpoint is read-only. It returns the descriptor, validation state,
selectability, stage rows, binding count, approval boundary, and authority
flags. It does not start workflow execution, open a pull request, push a branch,
or grant live connector authority.

Stage order:

```text
plan_local_change
  -> run_local_change_chain
  -> verify_local_receipt
  -> operator_review_gate
  -> prepare_pr_evidence
```

Governed binding:

| Stage | Type | Skill or gate | Closure evidence |
| --- | --- | --- | --- |
| `plan_local_change` | `skill_execution` | `agentic_control.coding_governor.v1` | `code_change_plan_ref` |
| `run_local_change_chain` | `skill_execution` | `software_dev.change_closure.v1` | `change_receipt_id` |
| `verify_local_receipt` | `skill_execution` | `agentic_control.quality_governor.v1` | `quality_verification_plan_ref` |
| `operator_review_gate` | `approval_gate` | operator review boundary | `approval_decision_ref` |
| `prepare_pr_evidence` | `skill_execution` | `agentic_control.release_governor.v1` | PR evidence and handoff packet |

This is the first reusable chain for the unlock ladder:

```text
task -> local plan -> bounded change -> dry-run checks -> receipt
  -> operator approval -> PR evidence
```

The workflow intentionally prepares PR evidence only after the operator review
gate. It must not push, open a pull request, deploy, or mutate external state
without a later approval-bound live action.

## Transition Rules

1. Each stage must reach a terminal status (completed, failed, or skipped) before any successor stage may begin.
2. Predecessor completion is verified against the stage graph before dispatch.
3. Conditional transitions evaluate their condition string against stage output; if the condition is not met the transition is not taken.
4. On-failure transitions activate only when the source stage fails; they do not override the governed early-stop unless explicitly modeled.
5. A stage may have multiple predecessors; all must complete before the stage is eligible.

## Failure Modes

| Mode | Trigger | Effect |
|---|---|---|
| `stage_failed` | A stage executor returns a non-success status. | Workflow transitions to `failed`; partial results preserved. |
| `approval_timeout` | An approval gate exceeds its timeout. | Workflow transitions to `suspended`. |
| `verification_mismatch` | Post-execution verification detects inconsistency. | Mismatch reasons recorded in `WorkflowVerificationRecord`. |
| `workflow_suspended` | Operator requests suspension or an unrecoverable wait. | Workflow transitions to `suspended`; partial results preserved. |

## Prohibitions

1. No stage may bypass autonomy or policy evaluation. Every skill-execution stage is subject to the same autonomy mode and policy checks as a standalone skill invocation.
2. No hidden control flow. Every control-flow dependency must appear in the descriptor's predecessor graph or an explicit `WorkflowTransition` artifact.
3. No unverified completion. A workflow may only reach `completed` status after all stages have produced verified results.
4. No cycle in the stage graph. The validator rejects any descriptor whose stage predecessors form a cycle.
5. No dangling bindings. Every binding must reference stages that exist in the descriptor.

## Agentic-Control Governor Chain

Governor cohesion is represented as the read-only workflow descriptor
`agentic_control.governor_chain.cohesion.v1`. It composes existing governors; it
does not register a new governor skill and does not grant capability authority.

The canonical order is:

```text
policy_governor
  -> decision_governor
  -> design_governor
  -> coding_governor
  -> quality_governor
  -> release_governor
  -> runtime_governor
```

Each stage is a `skill_execution` stage bound to an existing
`agentic_control.*_governor.v1` descriptor. Every skill in the chain must remain
`external_read`, keep mandatory verification, and carry
`grants_new_capability_authority = false`.

The handoff key is explicit:

```text
governance_packet_ref -> upstream_governance_packet_ref
```

`mcoi_runtime.core.governor_chain.validate_governor_chain_descriptor` fails
closed when a governor is missing, blocked, writable, reordered, or detached from
the expected predecessor/binding topology.

## Mullu Developer Workflow v1

`mullu_developer_workflow.v1` is the first complete local lab workflow over the
software-development capability pack. It turns a user request into a bounded
change candidate without touching production, customers, money, email, or live
connector writes.

```text
user request
  -> repository map
  -> context bundle
  -> gate plan
  -> sandbox change
  -> diff and receipt review
  -> operator approval
  -> PR candidate preparation
```

The workflow composes existing capabilities only:

| Stage | Type | Capability |
| --- | --- | --- |
| `request_intake` | `observation` | `operator.user_request` |
| `repo_map` | `skill_execution` | `software_dev.repo_map.read` |
| `context_bundle` | `skill_execution` | `software_dev.context_bundle.build` |
| `gate_plan` | `skill_execution` | `software_dev.gate_plan.select` |
| `sandbox_change` | `skill_execution` | `software_dev.change.run` |
| `receipt_review` | `observation` | `software_change_receipt` |
| `operator_approval` | `approval_gate` | `developer_reviewer` |
| `pr_candidate` | `skill_execution` | `software_dev.pr_candidate.prepare` |

Terminal closure is:

```text
diff_receipt_reviewed_then_pr_candidate_prepared
```

The operator console projects this workflow from the capability registry through
`friction_control.developer_workflow_v1`. The projection is read-only. It reports
`preflight_ready` only when all required capabilities are registered and the
effect-bearing stages are lab-mode admissible through sandbox, receipt, rollback,
and no-network constraints.

The operator control tower exposes the same workflow summary through
`/operator/control-tower/read-model` and `/operator/control-tower`. The dashboard
surface intentionally shows the compact operator fields: task, status, reason,
next unlock, risk, and action needed. The populated panel is
`capability_health`, with `approvals`, `proof_explorer`, and `workflow_monitor`
also attached from existing read-only approval history, receipt viewer, current
task, and plan review projections. Unrelated panels remain explicit missing read
models until their own governed projections are attached.

Real-world effects remain outside this workflow. Opening an external pull
request, pushing a branch, merging, deployment, customer communication, or
production data mutation must enter a stronger workflow with approval, witness,
monitoring, and rollback evidence.
