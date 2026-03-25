# 21 - Cross-Plane Workflow Runtime

## Purpose

The cross-plane workflow runtime composes skills across capability planes into
governed multi-step jobs. A workflow is a directed acyclic graph of stages where
each stage may invoke a skill, require operator approval, observe system state,
communicate with external systems, or wait for an asynchronous event. The
runtime enforces that every stage transition is explicit, verified, and subject
to the same autonomy and policy constraints that govern individual skill
execution.

## Owned Artifacts

| Artifact | Role |
|---|---|
| `WorkflowDescriptor` | Immutable definition of a workflow's stages, bindings, and transitions. |
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
| `approval_gate` | Pause until an operator approves continuation. |
| `observation` | Capture current system or environment state. |
| `communication` | Send or receive a message through the communication plane. |
| `wait_for_event` | Block until an external event arrives. |

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
2. No hidden transitions. Every control-flow edge must appear in the workflow descriptor's transition list.
3. No unverified completion. A workflow may only reach `completed` status after all stages have produced verified results.
4. No cycle in the stage graph. The validator rejects any descriptor whose stage predecessors form a cycle.
5. No dangling bindings. Every binding must reference stages that exist in the descriptor.
