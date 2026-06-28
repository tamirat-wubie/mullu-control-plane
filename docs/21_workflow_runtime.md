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
| `test_run` | `skill_execution` | `software_dev.change.run` |
| `diff_review` | `observation` | `software_change_diff` |
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
surface intentionally shows compact operator fields for task, status, reason,
next unlock, risk, action needed, rollback posture, mode posture, receipt
progress, sandbox-to-PR readiness, run status, current stage, and workflow-run
receipt link. The populated panel is `capability_health`, with `approvals`,
`proof_explorer`, and `workflow_monitor` also attached from existing read-only
approval history, receipt viewer, current task, plan review, and Developer
Workflow v1 run projections. Unrelated panels remain explicit missing read
models until their own governed projections are attached.
For API consumers that need only the monitor headline,
`workflow_monitor.metadata.workflow_monitor_summary` exposes monitor status,
current task id, current task count, plan review count, blocked and review
counts, workflow status, sandbox-to-PR readiness, blocker, next action, local
execution boundary, and no-effect flag. The status receipt mirrors this as
`workflow_monitor_summary` with a source reference to the workflow monitor
field.
The HTML dashboard renders the same data first as `Workflow Monitor Summary`,
so the operator can see the current task, blocker, next action, boundary, and
no-effect posture before reading the detailed workflow tables.
The status receipt also emits `control_tower_headline_summary`, a top-level
headline composed from `capability_health.metadata.control_system_summary` and
`workflow_monitor.metadata.friction_reduction_summary`. It reports task,
status, headline status, current milestone, current blocker, recommended mode,
safe local candidate count, dangerous blocker count, local continuation,
approval boundary, next action, next evidence id, and no-effect posture. The
dashboard renders it as `Control Tower Headline` before detailed panels.
The local lab readiness headline is `local_lab_readiness_summary`, composed
from `workflow_monitor.metadata.evidence_progress_summary` and
`workflow_monitor.metadata.local_rollback_flow_readiness_summary`. It reports
lab mode, local continuation, safe candidate count, pending evidence, next
evidence id, rollback receipt availability, rollback readiness, next action,
approval boundary, local-lab boundary, and no-effect posture. It is a readiness
projection only and does not execute local work.
The local resume plan is `local_resume_plan_summary`, composed from
`workflow_monitor.metadata.operator_decision_summary` and
`workflow_monitor.metadata.evidence_progress_summary`. It gives polling clients
one bounded next-step answer: whether local continuation is allowed,
recommended mode, current milestone, current blocker, next action, next
evidence id, safe candidate count, pending evidence, rollback readiness,
current approval requirement, approval boundary, local-lab boundary, and
no-effect posture. It is a resume hint only and does not grant write, PR,
connector, or real-world authority.
The workflow monitor also emits
`workflow_monitor.metadata.operator_action_card`, a reusable next-action card
with card id, title, status, reason, primary action, target href, focus item,
task id, risk, execution boundary, approval-required flag, and no-effect flag.
The status receipt mirrors this as `operator_action_card`, and the HTML
dashboard renders it as `Operator Action Card`.
For consumers that only need the deduplicated action/evidence payload, the
workflow monitor also emits `workflow_monitor.metadata.next_action_summary`.
It composes the action card, sandbox-to-PR focus, and sandbox-to-PR packet into
one object with status, blocker reason, primary action, action target, focus
id, focus source, required evidence ids, approval-required flag, risk,
local-lab boundary, and no-effect posture. The status receipt mirrors this as
`next_action_summary`.
The approval state is separately projected as
`workflow_monitor.metadata.approval_readiness_summary`. It reports whether
approval is required, the current operator approval status, whether approval is
missing, the current blocker, the before-PR-or-real-world-effect boundary, the
next approval action, PR-candidate status, and no-effect posture. This summary
is informational only: it does not grant approval, prepare a PR, or authorize
external execution. The status receipt mirrors it as
`approval_readiness_summary`, and the dashboard renders it as
`Approval Readiness Summary`.
The current decision is resolved into
`workflow_monitor.metadata.operator_decision_summary`. It composes the
next-action summary, approval readiness, milestone, and evidence progress into
one operator-facing answer: decision status, decision kind, current milestone,
current blocker, recommended action, action target, next evidence id, whether
operator review is required now, whether review is required before any external
effect, approval status, local continuation boundary, and no-effect posture.
This summary reduces dashboard scanning; it does not execute the action or
grant approval. The status receipt mirrors it as `operator_decision_summary`,
and the dashboard renders it as `Operator Decision Summary`.
The friction headline is
`workflow_monitor.metadata.friction_reduction_summary`. It composes operator
decision, evidence progress, and the current milestone into one answer:
whether local continuation is allowed, how many evidence items remain, the next
evidence id, the approval boundary, whether review is required now, and
no-effect posture. It exists to reduce operator scanning only; it does not
execute local work, grant approval, or permit PR or real-world effects. The
status receipt mirrors it as `friction_reduction_summary`, and the dashboard
renders it as `Friction Reduction Summary`.
The capability panel also projects
`capability_health.metadata.safe_automatic_action_candidates` from the safe
automatic zones. These candidates are reusable local-lab cards for docs, tests,
examples, local demos, README updates, schemas, and validators. They carry the
same no-effect and `local_lab_only` posture and are mirrored into the status
receipt as `safe_automatic_action_candidates`.
The safe queue headline is
`capability_health.metadata.safe_local_action_queue_summary`. It reports queue
status, candidate count, first candidate, first safe zone, first action,
recommended friction mode, approval requirement, local execution boundary, and
no-effect posture. This queue is a product surface for reducing dashboard
friction; it does not execute the candidate or create new write authority. The
status receipt mirrors it as `safe_local_action_queue_summary`, and the
dashboard renders it as `Safe Local Action Queue`.
The matching unsafe surface is
`capability_health.metadata.dangerous_zone_blockers`. It projects delete,
secret, email, money, deploy, merge, and production-data zones as explicit
blocked cards with required approval, rollback, and effect-receipt evidence.
The status receipt mirrors these as `dangerous_zone_blockers`, and the dashboard
shows them beside the safe candidates.
The dangerous blocker headline is
`capability_health.metadata.dangerous_action_blocker_summary`. It reports
blocker status, blocked-zone count, first blocker, first zone, first reason,
required evidence, approval requirement, rollback requirement, real-world
boundary, and no-effect posture. This is a visibility surface only: it does not
grant approval, execute rollback, or permit real-world effects. The status
receipt mirrors it as `dangerous_action_blocker_summary`, and the dashboard
renders it inside `Dangerous Zone Blockers`.
The Lab vs Real-world headline is
`capability_health.metadata.lab_real_world_summary`. It states whether lab mode
is allowed, how many local candidates can be prepared, fast-mode lab readiness,
real-world write status, dangerous blockers, approval-required count, both
execution boundaries, and no-effect posture. The status receipt mirrors it as
`lab_real_world_summary`.
The approval-boundary headline is
`capability_health.metadata.approval_boundary_summary`. It separates local
automatic candidates from capability unlocks, PR preparation, and dangerous
zones that still require approval. It records the approval boundary,
next approval capability, local execution boundary, and no-effect posture. The
status receipt mirrors it as `approval_boundary_summary`.
The rollback-control headline is
`capability_health.metadata.rollback_control_summary`. It states rollback
default coverage, rollback-required unlock count, capability count, sandbox-to-PR
policy readiness, the rollback policy, the receipt source, local execution
boundary, and no-effect posture. The status receipt mirrors it as
`rollback_control_summary`.
The master registry headline is
`capability_health.metadata.capability_registry_summary`. It gives API and HTML
consumers the registry answer in one object: capability count,
preflight-ready count, blocked count, approval-required count, pending unlocks,
the next blocked capability, the blocking reason, required evidence, local-lab
boundary, and no-effect posture. The status receipt mirrors it as
`capability_registry_summary`.
The friction-mode headline is
`capability_health.metadata.friction_mode_summary`. It condenses Strict,
Balanced, and Fast mode counts into one receipt-safe object with the default
mode, Foundation Mode recommendation, per-mode allowed/approval/blocked counts,
local-lab boundary, and no-effect posture. The status receipt mirrors it as
`friction_mode_summary`.
The same capability panel derives
`capability_health.metadata.safe_vs_dangerous_summary`, a compact headline with
safe candidate count, dangerous blocker count, first safe action, first blocked
zone, operator message, local-lab boundary, real-world boundary, and no-effect
flag. The status receipt mirrors it as `safe_vs_dangerous_summary`.
The unlock bridge is
`capability_health.metadata.unlock_readiness_summary`. It connects the next
unlock queue to the safe automatic candidates and dangerous blockers so the
operator can see the next capability, required evidence, pending unlock count,
safe candidate count, approval-bound blocker count, local-lab boundary, and
no-effect posture without scanning every capability row. The status receipt
mirrors it as `unlock_readiness_summary`.
The product-level control headline is
`capability_health.metadata.control_system_summary`. It composes the registry,
friction mode, lab boundary, safe/dangerous split, and unlock-readiness
projections into one operator surface: task, status, recommended mode,
capability count, pending unlocks, safe candidates, dangerous blockers, next
capability, required evidence, risk, action needed, local-lab boundary, and
no-effect posture. The status receipt mirrors it as `control_system_summary`
with a source reference to `capability_health.metadata.control_system_summary`.

The tower composes a bounded sandbox-to-PR packet from two sources:

| Packet layer | Source |
| --- | --- |
| Capability policy | `capability_health.metadata.sandbox_to_pr_policy` |
| Sandbox receipts | `workflow_monitor.metadata.developer_workflow_run.receipt_checklist` |
| Sandbox receipt bundle | `examples/developer_workflow_sandbox_receipt_bundle.foundation.json` |
| Rollback status | `workflow_monitor.metadata.developer_workflow_run.sandbox_to_pr_readiness` |
| Approval status | `workflow_monitor.metadata.sandbox_to_pr_packet.approval` |
| PR candidate status | `workflow_monitor.metadata.sandbox_to_pr_packet.pr_candidate` |

The packet is projection-only. It reports the current blocker, next action, and
required evidence, while preserving `external_effects_allowed = false` and
`execution_boundary = local_lab_only`.
It also carries `receipt_bundle_ref`, which points to
`schemas/developer_workflow_sandbox_receipt_bundle.schema.json`,
`examples/developer_workflow_sandbox_receipt_bundle.foundation.json`, and
`scripts/validate_developer_workflow_sandbox_receipt_bundle.py`. It also names
`scripts/build_developer_workflow_sandbox_receipt_bundle.py`, the deterministic
local builder that converts explicit evidence refs, state hashes, command
records, diff hashes, and rollback commands into the bundle. The bundle is the
canonical local-lab evidence slot for sandbox patch, test gate, diff review, and
terminal receipts.

The sandbox-to-PR packet and the friction-control `sandbox_to_pr_now`
projection share one canonical `next_evidence` queue. The standalone validators
enforce this as a no-drift rule: evidence ids, labels, and receipt sources must
match across both fixtures before the workflow can claim PR-preparation
readiness. The packet validator also compares the same evidence signature and
completed-count state against the sandbox receipt bundle. Evidence status may
advance only through the workflow receipt source; the Foundation Mode
friction-control queue remains pending until sandbox patch, test gate, diff
review, and terminal receipts are attached.

For operator attachment planning, the compact packet
`schemas/developer_workflow_sandbox_receipt_attachment_packet.schema.json`
projects the same four receipts into attachable rows with required input names,
observed bundle values, evidence refs, and the first pending attachment. Its
builder reads the sandbox-to-PR packet and sandbox receipt bundle only; it is
projection-only and preserves `external_effects_allowed = false`.

The builder is not execution authority. It does not write code, run tests,
collect diffs, open pull requests, call connectors, or mutate external state. It
only transforms already-collected local evidence into the canonical receipt
bundle and then validates the generated bundle:

```powershell
python scripts/build_developer_workflow_sandbox_receipt_attachment_packet.py --json
python scripts/validate_developer_workflow_sandbox_receipt_attachment_packet.py
python scripts/validate_developer_workflow_local_sandbox_proof_report.py
python scripts/collect_developer_workflow_sandbox_receipt_evidence.py --receipt-id sandbox_patch_receipt --before-file .change_assurance/before.txt --after-file .change_assurance/after.txt --diff-file .change_assurance/sandbox_patch.diff --command "apply_patch" --rollback-command "git apply -R .change_assurance/sandbox_patch.diff" --evidence-ref proof://developer-workflow-v1/sandbox-patch
python scripts/build_developer_workflow_sandbox_receipt_bundle.py --evidence examples/developer_workflow_sandbox_receipt_evidence.partial.json --output .change_assurance/developer_workflow_sandbox_receipt_bundle.generated.json
python scripts/validate_developer_workflow_sandbox_receipt_bundle.py --bundle .change_assurance/developer_workflow_sandbox_receipt_bundle.generated.json
```

The collector is also observational. It reads only named local artifact files,
stores `sha256:` hashes in evidence JSON, and never embeds raw artifact content.

The developer workflow and control tower can consume the collected bundle
through an explicit read-only opt-in:

```text
/operator/developer-workflow/read-model?include_local_sandbox_receipts=true
/operator/control-tower/read-model?include_local_sandbox_receipts=true
```

When the flag is absent, the projection keeps the default Foundation Mode
pending state. When the flag is present, the gateway reads only the fixed local
bundle path `.change_assurance/developer_workflow_sandbox_receipt_bundle.collected.json`,
validates the local-lab/no-effect boundary, and maps complete bundle receipts
into workflow receipt checklist progress.
The control tower dashboard displays `Local sandbox bundle` with the attached
bundle status and completed bundle receipt count, so operators can distinguish
default pending state from explicitly attached local evidence.
It also renders `Local Sandbox Bundle Receipts`, a receipt-level table derived
from the same validated bundle rows. The table shows each receipt label, status,
stage, required flag, and evidence refs without exposing raw file contents.
For API consumers that only need bundle progress,
`workflow_monitor.metadata.sandbox_receipt_bundle_summary` exposes bundle
status, completed count, required count, receipt row count, next receipt id,
next receipt status, local execution boundary, and no-effect flag. The status
receipt mirrors this as `sandbox_receipt_bundle_summary` with a source
reference to `workflow_monitor.metadata.sandbox_receipt_bundle_summary`.
It also renders `Sandbox Receipt Attachments`, a compact attachment table from
`workflow_monitor.metadata.sandbox_receipt_attachment_packet`. The table shows
the first pending attachment, per-receipt status, action hint, source, and
evidence refs while preserving the same projection-only local-lab boundary.
For API consumers,
`workflow_monitor.metadata.sandbox_receipt_attachment_readiness_summary`
exposes only the packet status, completed count, required count, next receipt
id, next label, next status, next action, local execution boundary, and
no-effect flag. The status receipt mirrors this as
`sandbox_receipt_attachment_readiness_summary` and derives it from the full
attachment packet when the compact read-model field is absent.
The workflow monitor also emits
`workflow_monitor.metadata.evidence_progress_summary`, which composes sandbox
receipt attachment progress, sandbox bundle progress, rollback receipt
availability, PR next-evidence count, the next evidence id, blocker, next
action, local-lab boundary, and no-effect posture. It is a progress projection
only and does not authorize evidence collection, rollback execution, PR
creation, or branch push. The status receipt mirrors it as
`evidence_progress_summary`.
The control tower also projects `sandbox_to_pr_focus`, a single operator-facing
next evidence item derived from that queue or from the approval/PR gate when
receipts are complete.
For API consumers that only need the gate state,
`workflow_monitor.metadata.sandbox_to_pr_summary` exposes status, blocker,
focus id, focus status, next action, next-evidence count, receipt progress,
approval status, PR-candidate status, local execution boundary, and no-effect
flag. The status receipt mirrors this as `sandbox_to_pr_summary` with a source
reference to `workflow_monitor.metadata.sandbox_to_pr_summary`.
The friction-control and sandbox-to-PR packet queue entries also carry bounded
action hints for the four local receipts. These hints describe which evidence
to attach; they are not executable commands and do not authorize external
effects.
`/operator/control-tower/status-receipt` exports the same focus as a compact
read-only receipt with the tower snapshot hash, blocker, next action, workflow
run state, local bundle receipt summary, sandbox receipt attachment summary,
local rollback summary, bounded focus action hint, and no-effect flags.

For a one-command local proof path, use:

```powershell
python scripts/run_developer_workflow_local_sandbox_proof.py --existing-evidence= --receipt-id sandbox_patch_receipt --before-file .change_assurance/before.txt --after-file .change_assurance/after.txt --diff-file .change_assurance/sandbox_patch.diff --command "apply_patch" --rollback-command "git apply -R .change_assurance/sandbox_patch.diff" --evidence-ref proof://developer-workflow-v1/sandbox-patch --json
```

The runner collects local artifact hashes, builds
`.change_assurance/developer_workflow_sandbox_receipt_bundle.collected.json`,
refreshes
`.change_assurance/developer_workflow_sandbox_receipt_attachment_packet.generated.json`,
then refreshes the downstream PR-preparation, local-candidate,
PR-tool-admission, external-approval-witness, command-preview, metadata, and
readiness-bundle packets. It writes a concise Developer Workflow operator
receipt plus
`.change_assurance/developer_workflow_local_sandbox_proof_report.generated.json`,
and
`.change_assurance/developer_workflow_local_rollback_summary_packet.generated.json`,
and
`.change_assurance/developer_workflow_local_rollback_approval_packet.generated.json`,
validates the generated chain, and prints the opt-in workflow and control tower
URLs. It does not execute the supplied command string; the command is receipt
evidence for the already performed local action. External PR execution remains
blocked unless the downstream approval witness and readiness bundle explicitly
close.
When `include_local_sandbox_receipts=true` is used, the control tower reads that
proof report as `workflow_monitor.metadata.local_sandbox_proof_report` and
renders `Local Sandbox Proof Report` with the generated artifact paths. The
report is validated with
`scripts/validate_developer_workflow_local_sandbox_proof_report.py` and rejected
if it claims command execution or external effects.
For API consumers,
`workflow_monitor.metadata.local_sandbox_proof_readiness_summary` exposes only
the proof status, ok flag, bundle status, attachment packet status, next
attachment id, PR readiness status, completed count, required count, execution
performed flag, and no-effect flag. The status receipt mirrors this as
`local_sandbox_proof_readiness_summary` and derives it from the full proof
report when the compact read-model field is absent.
The control tower also reads
`workflow_monitor.metadata.local_rollback_summary_packet` when the generated
rollback summary exists. The `Local Rollback Summary` dashboard section shows
per-artifact `Remove-Item -LiteralPath ... -Force` command previews with
`required_confirmation = true`, while `rollback_execution_performed` and
`external_effects_allowed` remain false.
The control tower reads
`workflow_monitor.metadata.local_rollback_approval_packet` when present. The
`Local Rollback Approval` dashboard section shows selected artifacts,
operator approval status, and whether deletion execution is allowed. The
default Foundation packet is `pending`, selects no artifacts, and keeps
`delete_execution_allowed = false`.
The control tower also derives
`workflow_monitor.metadata.local_rollback_flow_command` from the approval
packet. The `Local Rollback Flow Command` dashboard section shows the exact
dry-run command for the selected artifacts and a separate command that appends
`--execute`; the dry-run command is the default operator hint and never carries
external effects.
The same section acts as a bounded action card: it names the next operator
action, selected artifact ids, rollback summary path, approval packet path, and
the dry-run or execution receipt path that will be refreshed by the rollback
flow runner.
Each path is linked through a whitelisted read-only viewer:

```text
/operator/control-tower/local-rollback-receipt?receipt_id=summary
/operator/control-tower/local-rollback-receipt?receipt_id=approval
/operator/control-tower/local-rollback-receipt?receipt_id=execution
```

The JSON form is available at
`/operator/control-tower/local-rollback-receipt/read-model`. The route accepts
only those receipt ids, resolves them to fixed `.change_assurance` files, runs
the existing receipt validators, and returns a projection-only payload with
`external_effects_allowed = false`.
The action card also reports compact receipt availability for `summary`,
`approval`, and `execution`, so missing local evidence is visible before the
operator opens a link.
It also exposes a compact `readiness_verdict`: `awaiting_selection`,
`awaiting_summary_receipt`, `awaiting_approval_receipt`, or
`ready_for_dry_run`. The verdict is derived from selected artifact ids and
receipt availability only; it does not grant execution authority.
For API consumers that do not need the full command card,
`workflow_monitor.metadata.local_rollback_flow_readiness_summary` exposes only
the verdict, command status, selected artifact count, receipt availability
count, next action, and no-effect flags.
`workflow_monitor.metadata.local_rollback_receipts_summary` exposes the compact
state of the rollback summary, approval packet, and execution receipt together:
attachment count, generated and selected artifact counts, approval status,
execution mode, execution status, delete authority, rollback execution flag,
and no-effect flag.
The status receipt mirrors this as `local_rollback_receipts_summary` with a
source reference to `workflow_monitor.metadata.local_rollback_receipts_summary`.
The status receipt mirrors this as
`local_rollback_flow_readiness_summary`; if an older snapshot lacks the compact
field, the receipt derives it from `local_rollback_flow_command` and its receipt
availability block.
The broader Developer Workflow v1 state has the same compact surface at
`workflow_monitor.metadata.developer_workflow_readiness_summary`, covering the
workflow status, current task, sandbox-to-PR blocker, receipt progress,
approval and PR-candidate status, rollback receipt status, execution boundary,
next action, and no-effect flag.
The status receipt mirrors this as
`developer_workflow_readiness_summary` and records its source as
`workflow_monitor.metadata.developer_workflow_readiness_summary`; if an older
snapshot lacks the read-model field, the receipt derives the same bounded values
from the existing workflow run and sandbox-to-PR packet.
The operator-facing milestone surface is
`workflow_monitor.metadata.developer_workflow_milestone_summary`. It projects
the same local Developer Workflow v1 state into one current milestone:
`collect_sandbox_receipts`, `request_operator_approval`,
`prepare_pr_candidate`, `closed`, or `review`. The field also carries blocker,
next action, receipt progress, approval status, PR-candidate status, local lab
boundary, and no-effect posture. The status receipt mirrors it as
`developer_workflow_milestone_summary` with a source reference to
`workflow_monitor.metadata.developer_workflow_milestone_summary`.
The completion rollup is `developer_workflow_completion_summary`, composed from
`workflow_monitor.metadata.developer_workflow_milestone_summary` and
`workflow_monitor.metadata.evidence_progress_summary`. It reports workflow
status, completion status, milestone, blocker, completed and required evidence
counts, progress percent, pending evidence, next closure condition, terminal
closure readiness, PR creation authority, local-lab boundary, and no-effect
posture. It is a progress projection only; it does not close the workflow,
approve PR preparation, create a pull request, or perform external effects.
The terminal closure field is `operator_terminal_closure_summary`, composed
from `workflow_monitor.metadata.developer_workflow_milestone_summary` and
`workflow_monitor.metadata.evidence_progress_summary`. It reports terminal
status, closure readiness, workflow status, completion status, current blocker,
pending evidence, review readiness, approval status, rollback readiness,
PR-creation denial, branch-push denial, next closure condition, local-lab
boundary, and no-effect posture. It is a terminal closure projection only and
does not close, approve, create a PR, push a branch, or perform external
effects.
The resume checkpoint field is `operator_resume_checkpoint_summary`, composed
from `workflow_monitor.metadata.friction_reduction_summary` and
`workflow_monitor.metadata.operator_decision_summary`. It reports checkpoint
status, local resume allowance, terminal status, recommended mode, current
milestone, blocker, next action, next evidence id, pending evidence, rollback
readiness, current approval requirement, local-lab boundary, and no-effect
posture. It is a resume projection only and does not execute local changes or
cross any external boundary.
The sandbox milestone field is `operator_sandbox_milestone_summary`, composed
from `workflow_monitor.metadata.developer_workflow_milestone_summary` and
`workflow_monitor.metadata.evidence_progress_summary`. It reports the current
sandbox milestone, next evidence id, next local action, evidence counts,
required receipt classes, write-authority denial, PR-creation denial, local-lab
boundary, and no-effect posture. It is a milestone projection only and does not
grant file-write authority, create a pull request, or perform external effects.
The sandbox receipt checklist field is
`operator_sandbox_receipt_checklist_summary`, composed from
`workflow_monitor.metadata.evidence_progress_summary` and
`workflow_monitor.metadata.sandbox_receipt_attachment_readiness_summary`. It
reports checklist status, next receipt id, next receipt action, completed,
required, and pending receipt counts, canonical receipt sequence, terminal
review allowance, write-authority denial, and no-effect posture. It is a
checklist projection only and does not attach receipts, write files, or perform
external effects.
The sandbox patch receipt field is `operator_sandbox_patch_receipt_summary`,
composed from
`workflow_monitor.metadata.sandbox_receipt_attachment_readiness_summary` and
`workflow_monitor.metadata.evidence_progress_summary`. It reports the
`sandbox_patch_receipt` status, required evidence parts, next attachment action,
rollback and dry-run requirements, write-authority denial, attachment denial,
local-lab boundary, and no-effect posture. It is a first-receipt detail
projection only and does not collect evidence, attach a receipt, or perform
file writes.
The sandbox patch command field is `operator_sandbox_patch_command_summary`,
anchored to the documented `sandbox_patch_receipt` collection command. It
reports the preview command, expected input files, expected output receipt
bundle, execution denial, attachment denial, write-authority denial, and
no-effect posture. It is a command preview only and does not run the collection
script or attach evidence.
The sandbox patch bundle preview field is
`operator_sandbox_patch_bundle_preview_summary`, anchored to the documented
`sandbox_patch_receipt` bundle validation path. It reports the expected bundle
path, included receipt ids, validation command, bundle-generation denial,
validation denial, attachment denial, write-authority denial, and no-effect
posture. It is a bundle preview only and does not generate or validate the
bundle.
The sandbox patch validation readiness field is
`operator_sandbox_patch_validation_readiness_summary`, anchored to the
documented `sandbox_patch_receipt` validation path. It reports validation
status, bundle path, validator command, prerequisites, missing prerequisite
count, validation denial, terminal-review denial, and no-effect posture. It is a
validation readiness projection only and does not run validators or advance
terminal review.
The sandbox patch terminal review field is
`operator_sandbox_patch_terminal_review_summary`, anchored to the documented
`sandbox_patch_receipt` terminal review path. It reports review status, review
target, prerequisites, missing prerequisite count, review command, review
denial, approval-request denial, PR-creation denial, and no-effect posture. It
is a terminal review readiness projection only and does not request approval,
prepare a pull request, or advance terminal closure.
The sandbox patch approval readiness field is
`operator_sandbox_patch_approval_readiness_summary`, anchored to the documented
`sandbox_patch_receipt` approval readiness path. It reports approval status,
approval target, prerequisites, missing prerequisite count, approval-request
denial, PR-preparation denial, PR-creation denial, and no-effect posture. It is
an approval readiness projection only and does not request approval, prepare a
pull request, create a pull request, or perform external effects.
The sandbox patch PR preparation readiness field is
`operator_sandbox_patch_pr_preparation_readiness_summary`, anchored to the
documented `sandbox_patch_receipt` PR preparation readiness path. It reports
preparation status, preparation target, prerequisites, missing prerequisite
count, preparation denial, branch-push denial, PR-creation denial, and no-effect
posture. It is a PR preparation readiness projection only and does not prepare a
pull request, push a branch, create a pull request, or perform external effects.
The sandbox patch PR creation readiness field is
`operator_sandbox_patch_pr_creation_readiness_summary`, anchored to the
documented `sandbox_patch_receipt` PR creation readiness path. It reports
creation status, creation target, prerequisites, missing prerequisite count,
creation denial, branch-push denial, PR-creation denial, connector-call denial,
and no-effect posture. It is a PR creation readiness projection only and does
not push a branch, call a connector, create a pull request, or perform external
effects.
The sandbox patch PR CI readiness field is
`operator_sandbox_patch_pr_ci_readiness_summary`, anchored to the documented
`sandbox_patch_receipt` PR CI readiness path. It reports CI status, CI target,
prerequisites, missing prerequisite count, CI-observation denial, GitHub polling
denial, check-update denial, ready-for-review denial, and no-effect posture. It
is a PR CI readiness projection only and does not poll GitHub, update checks,
mark a pull request ready for review, or perform external effects.
The operator handoff field is `operator_handoff_summary`, composed from
`workflow_monitor.metadata.developer_workflow_milestone_summary` and
`workflow_monitor.metadata.operator_decision_summary`. It gives a future
operator or resumed run the portable state: task, handoff status, current
milestone, blocker, next action, next evidence id, pending evidence count,
approval boundary, recommended mode, local resume allowance, forbidden effects,
local-lab boundary, and no-effect posture. It is a handoff projection only and
does not grant authority for branch push, pull request creation, merge,
deployment, connector writes, or real-world effects.
The review-readiness field is `operator_review_readiness_summary`, composed
from `workflow_monitor.metadata.evidence_progress_summary` and
`workflow_monitor.metadata.approval_readiness_summary`. It reports whether the
current local workflow is ready for operator review, the blocking reason,
evidence progress, next evidence id, next review action, approval boundary,
PR-creation authority, local-lab boundary, and no-effect posture. It is a
review packaging projection only and cannot approve, create, push, merge, or
call external connectors.
The review packet field is `operator_review_packet_summary`, composed from
`workflow_monitor.metadata.approval_readiness_summary` and
`workflow_monitor.metadata.evidence_progress_summary`. It reports review packet
status, review readiness, review blocker, evidence counts, next evidence id,
next packet action, approval boundary, current approval requirement,
PR-creation denial, local-lab boundary, and no-effect posture. It is a review
packet projection only and does not approve, prepare, create, or push a PR.
The active blocker field is `operator_blocker_summary`, composed from
`workflow_monitor.metadata.developer_workflow_milestone_summary` and
`workflow_monitor.metadata.evidence_progress_summary`. It classifies the
current blocker, records the clearing action, next evidence id, pending evidence
count, approval posture, local resume allowance, local-lab boundary, and
no-effect posture. It is a diagnosis projection only; clearing the blocker
still requires the named evidence or approval witness.
The packet inventory field is `operator_packet_summary`, composed from
`workflow_monitor.metadata.sandbox_receipt_bundle_summary` and
`workflow_monitor.metadata.local_rollback_receipts_summary`. It reports the
status of the local sandbox receipts, attachment packet, proof report, rollback
receipts, PR readiness packet, packet counts, next packet, next packet action,
local-lab boundary, and no-effect posture. It is an inventory projection only
and does not create or attach packets by itself.
The authority field is `operator_authority_summary`, composed from
`workflow_monitor.metadata.approval_readiness_summary` and
`capability_health.metadata.lab_real_world_summary`. It reports current
authority as local-lab only, whether local preparation and review are allowed,
whether approval is required now, the approval boundary, and explicit denials
for PR creation, branch push, connector writes, and real-world effects. It is
an authority projection only and does not grant new execution capability.
The risk field is `operator_risk_summary`, composed from
`capability_health.metadata.dangerous_action_blocker_summary` and
`workflow_monitor.metadata.evidence_progress_summary`. It reports local risk
status, risk level, risk driver, risk scope, safe candidate count, dangerous
blockers, pending evidence, approval boundary, rollback readiness, local-lab
boundary, and no-effect posture. It is a risk projection only and does not
relax any approval or external-effect boundary.
The approval packet field is `operator_approval_packet_summary`, composed from
`workflow_monitor.metadata.approval_readiness_summary` and
`workflow_monitor.metadata.evidence_progress_summary`. It reports whether the
packet is still awaiting evidence, the approval requirement and status, the
current blocker, evidence counts, next evidence id, next approval action,
approval target, PR-preparation readiness, local-lab boundary, and no-effect
posture. It is a packet projection only and does not approve, prepare, or
create a PR by itself.
The evidence gap field is `operator_evidence_gap_summary`, composed from
`workflow_monitor.metadata.evidence_progress_summary` and
`workflow_monitor.metadata.friction_reduction_summary`. It reports the current
gap status, local receipt gap class, evidence counts, next evidence id, next
gap action, approval-blocked posture, local continuation allowance, local-lab
boundary, and no-effect posture. It is a gap projection only and does not
waive required evidence.
The rollback gap field is `operator_rollback_gap_summary`, composed from
`workflow_monitor.metadata.local_rollback_flow_readiness_summary` and
`workflow_monitor.metadata.local_rollback_receipts_summary`. It reports
rollback gap status, readiness verdict, command status, selected artifact
count, rollback receipt counts, next rollback action, dry-run requirement,
execute-flag requirement, rollback readiness, approval status, local-lab
boundary, and no-effect posture. It is a rollback projection only and does not
execute rollback or approve deletion.
The PR gap field is `operator_pr_gap_summary`, composed from
`workflow_monitor.metadata.pr_readiness_summary` and
`workflow_monitor.metadata.pr_readiness_bundle`. It reports PR gap status, the
first blocker, external PR execution readiness, next evidence count, receipt
progress, preview-only posture, PR creation denial, branch push denial, local
execution boundary, and no-effect posture. It is a PR projection only and does
not prepare, create, or push a PR.
The HTML dashboard and status receipt also expose
`operator_dashboard_summary`, a composed surface over
`capability_health.metadata.control_system_summary` and
`workflow_monitor.metadata.developer_workflow_milestone_summary`. It carries the
current task, status, milestone, blocker, next action, recommended mode,
receipt progress, pending unlock count, safe/dangerous counts, next unlock,
risk, action needed, local-lab boundary, and no-effect posture. This is a
dashboard bridge only; it does not create workflow authority.
To reduce repeated invocations, the same runner also accepts a receipt manifest:

```powershell
python scripts/run_developer_workflow_local_sandbox_proof.py --existing-evidence= --receipt-manifest .change_assurance/developer_workflow_receipts.manifest.json --json
```

The manifest root is an object with `workflow_run_id` and a non-empty
`receipts` list. Each receipt entry must provide `receipt_id`, `before_file`,
`after_file`, `diff_file`, `command`, `rollback_command`, and `evidence_refs`.
Relative artifact paths resolve from the manifest file location. Manifest mode
still reads only named local files, records hashes rather than raw file content,
and keeps external PR execution closed.

The next approval surface is
`schemas/pr_preparation_approval_packet.schema.json`. The builder reads a
sandbox receipt bundle and emits a projection-only approval packet:

```powershell
python scripts/build_pr_preparation_approval_packet.py --bundle .change_assurance/developer_workflow_sandbox_receipt_bundle.collected.json --output .change_assurance/pr_preparation_approval_packet.generated.json --json
python scripts/validate_pr_preparation_approval_packet.py --packet .change_assurance/pr_preparation_approval_packet.generated.json
```

If the bundle is incomplete, the packet remains `awaiting_receipts`. If all four
sandbox receipts are complete, it moves to `awaiting_operator_approval` and the
only authorized post-approval effect is
`prepare_local_pr_candidate_packet`. External PR creation, branch push, merge,
deployment, and connector calls remain forbidden.
When the operator has approved local PR candidate preparation, the same builder
can record that bounded local approval:

```powershell
python scripts/build_pr_preparation_approval_packet.py --bundle .change_assurance/developer_workflow_sandbox_receipt_bundle.collected.json --output .change_assurance/pr_preparation_approval_packet.generated.json --approval-status approved --json
```

The one-command runner exposes the same local approval slot:

```powershell
python scripts/run_developer_workflow_local_sandbox_proof.py --existing-evidence= --receipt-manifest .change_assurance/developer_workflow_receipts.manifest.json --pr-preparation-approval-status approved --json
```

Approval can be recorded only after the sandbox receipt bundle is complete. It
advances the local candidate and PR-tool admission packets, but it still does
not authorize branch push, external pull request creation, merge, deployment,
or connector calls.

After approval is recorded, the local candidate packet can be generated:

```powershell
python scripts/build_local_pr_candidate_packet.py --approval-packet .change_assurance/pr_preparation_approval_packet.generated.json --output .change_assurance/local_pr_candidate_packet.generated.json --json
python scripts/validate_local_pr_candidate_packet.py --packet .change_assurance/local_pr_candidate_packet.generated.json
```

The candidate packet is still local-lab only. It can be `ready_for_pr_tool`, but
`pr_creation_allowed`, `branch_push_allowed`, and `external_effects_allowed`
remain false. A separate live PR tool admission step must own any actual branch
push or external PR creation.

The local PR tool admission packet is the next bounded step:

```powershell
python scripts/build_pr_tool_admission_packet.py --candidate-packet .change_assurance/local_pr_candidate_packet.generated.json --output .change_assurance/pr_tool_admission_packet.generated.json --json
python scripts/validate_pr_tool_admission_packet.py --packet .change_assurance/pr_tool_admission_packet.generated.json
```

This packet admits only local PR-tool preparation when the local candidate is
ready. It may render a PR body, assemble PR metadata, and prepare a command
preview, but it still keeps `pr_creation_allowed`, `branch_push_allowed`, and
`external_effects_allowed` false. External PR execution requires a separate
approval witness and remains outside this local admission packet.

The external PR execution approval witness is the authority evidence for that
separate boundary:

```powershell
python scripts/build_external_pr_execution_approval_witness.py --admission-packet .change_assurance/pr_tool_admission_packet.generated.json --output .change_assurance/external_pr_execution_approval_witness.generated.json --approval-status pending --json
python scripts/validate_external_pr_execution_approval_witness.py --witness .change_assurance/external_pr_execution_approval_witness.generated.json
```

Only when local PR-tool admission is true and `--approval-status approved` is
recorded may the witness set branch push and external PR creation authority to
true. The witness is still evidence only: it does not push, open, merge, deploy,
or call a connector.
The one-command runner can carry this final approval into a command-preview
handoff:

```powershell
python scripts/run_developer_workflow_local_sandbox_proof.py --existing-evidence= --receipt-manifest .change_assurance/developer_workflow_receipts.manifest.json --pr-preparation-approval-status approved --external-pr-approval-status approved --json
```

That path can report `ready_for_external_pr_execution = true` and
`command_preview_rendered = true`, but the generated command preview and PR
readiness bundle still record `execution_performed = false`.

After the witness grants authority, the command preview packet can render exact
external PR commands without executing them:

```powershell
python scripts/build_pr_command_preview_packet.py --approval-witness .change_assurance/external_pr_execution_approval_witness.generated.json --output .change_assurance/pr_command_preview_packet.generated.json --json
python scripts/validate_pr_command_preview_packet.py --packet .change_assurance/pr_command_preview_packet.generated.json
```

The packet is always `preview_only` and always keeps
`execution_performed = false`. If the witness is pending or incomplete, the
packet remains `blocked` and `command_preview` is empty.

The PR metadata packet prepares governed title/body content for the same local
candidate:

```powershell
python scripts/build_pr_metadata_packet.py --candidate-packet .change_assurance/local_pr_candidate_packet.generated.json --command-preview-packet .change_assurance/pr_command_preview_packet.generated.json --output .change_assurance/pr_metadata_packet.generated.json --json
python scripts/validate_pr_metadata_packet.py --packet .change_assurance/pr_metadata_packet.generated.json
```

It records PR title, body sections, labels, source branch, target branch,
rollback notes, and the command-preview packet hash. It remains preview-only and
keeps external effects, branch push, and PR creation disabled.

The PR readiness bundle is the single operator-facing packet for this chain:

```powershell
python scripts/build_pr_readiness_bundle.py --output .change_assurance/pr_readiness_bundle.generated.json --json
python scripts/validate_pr_readiness_bundle.py --bundle .change_assurance/pr_readiness_bundle.generated.json
```

It links sandbox receipts, approval, local candidate, PR-tool admission,
external approval witness, command preview, metadata, and rollback. In
Foundation Mode the fixture remains `awaiting_sandbox_receipts` and blocks
external PR execution.
The one-command local proof runner also writes
`.change_assurance/pr_readiness_bundle.generated.json` by default, so operators
can refresh the whole local chain before inspecting the control tower.
It also writes
`.change_assurance/developer_workflow_operator_receipt.generated.json`, a
compact receipt with sandbox progress, local approval state, candidate state,
external handoff state, rollback, source refs, and `execution_performed = false`.
It also writes
`.change_assurance/developer_workflow_local_rollback_summary_packet.generated.json`,
a projection-only rollback map over generated local artifacts; it does not
delete files or perform rollback.
It also writes
`.change_assurance/developer_workflow_local_rollback_approval_packet.generated.json`,
a local-lab approval packet. That packet may authorize later deletion of
selected generated artifacts only when approval evidence is present; it still
does not execute rollback.
To turn that approval into a local execution receipt, use:

```powershell
python scripts/execute_developer_workflow_local_rollback.py --approval-packet .change_assurance/developer_workflow_local_rollback_approval_packet.generated.json --rollback-summary .change_assurance/developer_workflow_local_rollback_summary_packet.generated.json --json
```

For a one-command operator path that records approval and always emits a dry-run
receipt before optional execution, use:

```powershell
python scripts/run_developer_workflow_local_rollback_flow.py --rollback-summary .change_assurance/developer_workflow_local_rollback_summary_packet.generated.json --artifact-id operator_receipt --approved-by operator --approval-evidence-ref approval://local/rollback/operator-receipt --json
```

Add `--execute` only after inspecting the dry-run receipt. Use `--approve-all`
only when every generated artifact in the rollback summary should be selected.

Without `--execute`, the runner performs a dry-run and emits
`.change_assurance/developer_workflow_local_rollback_execution_receipt.generated.json`
without deleting files. With `--execute`, it deletes only approved selected
artifact files that resolve inside `--workspace-root`, blocks directory
deletion, records pre/post existence per artifact, and validates the execution
receipt before reporting closure.
When `include_local_sandbox_receipts=true` is used, the control tower also
reads `workflow_monitor.metadata.local_rollback_execution_receipt`. The
`Local Rollback Execution Receipt` dashboard section shows execution status,
mode, per-artifact action status, workspace-boundary result, and pre/post file
existence.
The same dashboard request renders `Local Rollback Flow Command`, sourced from
`workflow_monitor.metadata.local_rollback_flow_command`, so the operator can
copy the bounded dry-run rollback flow for the currently selected artifacts
before deciding whether to append `--execute`. The card also shows the
receipt path that the dry-run refreshes, which keeps rollback inspection tied to
the local evidence chain instead of a loose command snippet.
Those receipt links use the local rollback receipt viewer route and never accept
an arbitrary filesystem path from the browser.
The card shows `available` or `unavailable` for each whitelisted receipt and a
count such as `3/3`, which is derived from already loaded and validated local
rollback packets.
The readiness verdict appears beside the command card and remains distinct from
the destructive execution boundary; `--execute` is still required separately.
The control tower read model exposes the same status at
`workflow_monitor.metadata.pr_readiness_bundle`; the HTML dashboard renders it
as `PR Readiness Bundle`, and the status receipt exports the compact
`pr_readiness` object.
For API consumers that do not need the artifact matrix,
`workflow_monitor.metadata.pr_readiness_summary` exposes only readiness status,
external PR readiness, first blocker, next-evidence count, receipt progress,
preview-only status, execution status, and no-effect/no-PR-write flags.
The status receipt mirrors this as `pr_readiness_summary` with a source
reference to `workflow_monitor.metadata.pr_readiness_summary`, so polling
clients can read PR readiness without traversing the full readiness bundle.
It also projects `workflow_monitor.metadata.developer_workflow_operator_receipt`
as the concise no-execution operator receipt. The dashboard renders this as
`Developer Workflow Operator Receipt`, while
`/operator/control-tower/status-receipt` embeds the same projection under
`developer_workflow_operator_receipt` with `execution_performed = false`.
For API consumers that only need receipt readiness,
`workflow_monitor.metadata.developer_workflow_operator_receipt_summary` exposes
solver outcome, readiness status, external PR readiness, command preview state,
next-evidence count, execution status, and no-effect flag.
The operator control tower status receipt mirrors this compact summary as
`developer_workflow_operator_receipt_summary` with a source reference to the
workflow monitor field, so status consumers can avoid traversing the full
operator receipt payload.

The stage-level receipt is exposed through
`/operator/developer-workflow/read-model` and rendered at
`/operator/developer-workflow`. The JSON route conforms to
`schemas/workflow_run.schema.json` and carries
`metadata.projection_only = true`, `metadata.execution_allowed = false`, and
`metadata.real_world_effects_allowed = false`. It is a workflow-run witness for
the local lab control surface, not authority to write files, push branches,
open external pull requests, or call connectors.

Real-world effects remain outside this workflow. Opening an external pull
request, pushing a branch, merging, deployment, customer communication, or
production data mutation must enter a stronger workflow with approval, witness,
monitoring, and rollback evidence.
