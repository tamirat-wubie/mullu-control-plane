# Governed Capability Fabric

> **In one box:** The shared "plug" that turns any domain's work into a governed
> [capability](GLOSSARY.md#capability--capability-plane) the platform can run
> safely — the connector between domain packs and the governed core. New here?
> → [Plain-English Overview](explain/PLAIN_ENGLISH.md). *(Doc type: Reference.)*

Purpose: define the shared contract surface that turns domain work into governed capability execution.
Governance scope: capability registry entries, domain capsules, capsule compiler inputs, authority, evidence, recovery, and obligation routing.
Dependencies: `docs/06_capability_planes.md`, `docs/31_operational_graph.md`, `docs/37_terminal_closure_certificate.md`, `schemas/capability_registry_entry.schema.json`, and `schemas/domain_capsule.schema.json`.
Invariants:
- No command can execute without a typed capability registry entry.
- No capability registry entry is complete without authority, isolation, evidence, recovery, cost, and obligation models.
- Registry read models expose derived C-level maturity without mutating source registry entries.
- No domain capsule is deployable without owner team, policies, evidence rules, recovery rules, test fixtures, read models, and operator views.
- Terminal closure remains the only success authority for effect-bearing actions.

## Architecture

The platform becomes general purpose by admitting every domain action through the same governed lifecycle:

```text
Command -> Typed Intent -> Capability -> Authority -> Effect -> Evidence -> Closure -> Obligation
```

A capability registry entry defines one executable action. A domain capsule packages the operating model for one domain. The capsule compiler turns certified capsule inputs into registry entries, policies, fixtures, read models, and operator views.

## Universal Event Spine v2

The fabric is not channel-centered. Slack, GitHub, Gmail, dashboards, documents,
alerts, and API webhooks are surfaces over one event path:

```text
Any human/system event
-> universal governed event
-> symbolic event compilation
-> identity and authority resolution
-> scoped context resolution
-> risk-tier policy decision
-> capability passport and registry routing
-> causal episode plan
-> Universal Action Orchestration when effect-bearing
-> verification and causal receipt
-> memory gate
```

Canonical contract implementation:

```text
mcoi/mcoi_runtime/contracts/universal_capability_fabric.py
```

Schema-backed fixtures:

| Contract | Schema | Fixture |
| --- | --- | --- |
| Universal governed event | `schemas/universal_governed_event.schema.json` | `integration/governed_capability_fabric/fixtures/universal_governed_event.json` |
| Causal capability receipt | `schemas/causal_capability_receipt.schema.json` | `integration/governed_capability_fabric/fixtures/causal_capability_receipt.json` |
| Memory gate decision | `schemas/memory_gate_decision.schema.json` | `integration/governed_capability_fabric/fixtures/memory_gate_decision.json` |

`UniversalGovernedEvent` binds event identity, actor, workspace, surface,
channel, intent, target object, requested action, context references, risk
class, authority reference, timestamp, trace reference, and deterministic
idempotency key. Surface adapters may normalize to this contract, but they do
not reason, authorize, or execute.

`FabricContextEvidence` keeps retrieved context bounded by source, permission
scope, sensitivity, observation time, confidence, and freshness. External
content can inform the event compiler, but it never becomes authority.

## Risk-Tier Policy

The v2 risk classes preserve speed for low-risk work while failing closed for
sensitive or external-obligation work:

| Risk class | Meaning | Default decision |
| --- | --- | --- |
| `class_0_observe` | Public or non-sensitive read-only observation | `allow_read_only` |
| `class_1_prepare` | Draft, plan, simulate, recommend | `allow_draft_only` |
| `class_2_reversible` | Reversible internal action with receipt | `allow` |
| `class_3_sensitive` | Sensitive action or private data boundary | `require_approval` |
| `class_4_external_obligation` | Merge, deploy, publish, send, bill, sign, or similar external obligation | `require_approval` |
| `class_5_blocked` | Unauthorized, unsafe, secret-exposing, destructive, or policy-violating action | `block` |

The default function `default_policy_decision_for_risk` is a guardrail, not a
complete policy engine. Stronger policy may always block or escalate. Weaker
policy may not directly allow `class_4_external_obligation`, and `class_5_blocked`
must remain blocked.

## Universal Capability Passport Standard

`UniversalCapabilityPassport` is the plug-compatible declaration format for a
capability's domain, inputs, outputs, required evidence, allowed tools, blocked
actions, risk class, verification rules, receipt fields, and memory policy.

Important boundary:

```text
capability passport != execution authority
```

The passport must set `passport_is_not_execution_authority = true`. Execution
authority still comes from an admitted `CapabilityRegistryEntry`, capsule
admission, policy decision, UAO when effect-bearing, verification, and terminal
closure.

## Causal Episode and Receipt

Every universal event episode follows this causal order:

```text
cause
-> interpretation
-> constraint
-> evidence
-> options
-> decision
-> action
-> consequence
-> receipt
-> memory_gate
```

`CausalEpisodePlan` rejects plans that reorder these stages. `CausalCapabilityReceipt`
records actor, surface, intent, target object, risk, evidence, policy decision,
actions taken, actions blocked, assumptions, verification result, final judgment,
memory update, timestamp, and partial failure reasons. A non-blocked receipt
cannot claim completion without evidence.

## Memory Gate

Memory is scoped and governed, not automatic:

```text
No memory without scope.
No scope without permission.
No durable memory without validation.
```

`MemoryGateDecision` can store, block, defer, or mark memory as not required.
Durable memory requires validated evidence and an audit reference. Sensitive,
private, unverified, or temporary material must use `blocked`, `defer`, or
ephemeral handling instead of silent persistence.

## First Workroom Path

The first product path is the GitHub Operations Workroom:

```text
GitHub event or dashboard request
-> UniversalGovernedEvent
-> PR/CI symbolic compilation
-> risk-tier decision
-> GitHub read-only capability passport
-> causal episode plan
-> PR or CI evidence inspection
-> causal receipt
-> memory gate
```

This keeps GitHub useful as the first surface while preserving the broader
fabric invariant: new surfaces attach through adapters, not custom runtimes.

Canonical local projection:

```text
gateway/github_operations_workroom.py
```

The projection currently admits bounded GitHub Operations Workroom paths for
PR safety, Actions failure diagnosis, repository status summary, patch-plan
drafting, and issue drafting. The
preview path creates a `UniversalGovernedEvent`, symbolic compilation,
authority resolution, risk policy result, capability passport, causal episode
plan, receipt, and memory gate. Live paths are constrained to GET-only GitHub
reads, bounded evidence summaries, hashed payloads, and causal receipts. No
path can post comments, create issues, merge, rerun workflows, dispatch
workflows, mutate repositories, deploy, or claim release readiness without a
separate write capability and explicit approval.

Operator preview routes:

```text
GET  /operator/github-operations/pr-safety
GET  /operator/github-operations/pr-safety/read-model
POST /operator/github-operations/pr-safety/read-admission/preview
POST /operator/github-operations/pr-safety/read-evidence
GET  /operator/github-operations/pr-safety/read-evidence/receipts/{receipt_filename}
POST /operator/github-operations/pr-safety/preview
GET  /operator/github-operations/actions-failure/read-model
GET  /operator/github-operations/actions-failure
POST /operator/github-operations/actions-failure/read-admission/preview
POST /operator/github-operations/actions-failure/read-evidence
GET  /operator/github-operations/repo-status/read-model
GET  /operator/github-operations/repo-status
POST /operator/github-operations/repo-status/read-admission/preview
POST /operator/github-operations/repo-status/read-evidence
GET  /operator/github-operations/patch-plan/read-model
GET  /operator/github-operations/patch-plan
POST /operator/github-operations/patch-plan/draft
GET  /operator/github-operations/issue-draft/read-model
GET  /operator/github-operations/issue-draft
POST /operator/github-operations/issue-draft/draft
GET  /operator/github-operations/release-readiness/read-model
GET  /operator/github-operations/release-readiness
POST /operator/github-operations/release-readiness/assess
```

The GET read model powers the browser-facing Workroom panel. Missing evidence
returns `AwaitingEvidence` with required evidence listed; supplied evidence refs
produce the same governed projection and receipt as the POST preview. The PR
safety, Actions failure, repository status, patch-plan, issue-draft, and
release-readiness surfaces
preserve a closed effect boundary by default: no GitHub call, no repository
read, no issue creation, no release creation, no tag creation, no PR mutation,
no branch push, no workflow trigger, no review submission, and no deployment
change. Live read routes open GitHub read authority only for the admitted
GET-only connector call.

The read-admission preview binds planned live evidence collection to the
existing certified `connector.github.read` capability. It admits only
`pull_request`, `diff`, `checks`, and `changed_files` evidence kinds, requires
`oauth:github.read`, allows only `connector_worker.github_read` against
`api.github.com`, and records that no connector call has been performed. It
cannot grant comment, merge, branch-delete, deployment, or repository-write
authority.

The read-evidence route is the first bounded live execution path. It accepts an
operator-provided token for the single request, performs only the admitted
GET-only reads, returns bounded summaries and hashes, emits a read receipt,
feeds the receipt into the PR safety projection, and evaluates a non-mutating
PR safety judgment. The response never returns the token. Its effect boundary
sets GitHub call and repository read to true while keeping repository mutation,
PR mutation, branch push, review submission, deployment mutation, and
system-of-record writes false.

The route also persists a workspace-local receipt bundle under
`MULLU_GITHUB_WORKROOM_RECEIPT_DIR`, defaulting to
`.tmp/github-operations-workroom/receipts`. The bundle filename is derived from
the read receipt identity, the write is confined to the configured receipt
root, and the payload contains only admission metadata, bounded fetch result,
read receipt, PR safety projection, PR safety judgment, hashes, and storage
witness fields. It records `token_persisted=false`,
`write_authority_granted=false`, and `merge_authority_granted=false`.

The receipt read-back route accepts only a stored GitHub read-evidence bundle
filename. It rejects path-like names, confines reads to the configured receipt
root, validates that the stored bundle is JSON, and refuses bundles containing
credential markers. This gives the Workroom a durable evidence read model
without turning receipt storage into a generic file reader.

The browser Workroom panel includes a `Read Evidence` control that posts to the
same route. The token field is a password input, the token is sent in the POST
body only, and the page clears the input after constructing the request. The UI
renders the returned receipt and judgment as bounded operator evidence; it does
not store credentials, expose raw GitHub tools, or add write controls.

`GitHubReadOnlyEvidenceFetcher` is the execution-side companion for this
admission. It only issues `GET` requests to `https://api.github.com`, returns
bounded evidence hashes and summaries, does not return the access token, and
cannot construct a result with write authority. A fetch result is evidence
collection, not merge safety judgment and not production closure.

Completed fetches emit a `CausalCapabilityReceipt` through
`build_github_read_only_evidence_fetch_receipt`. The receipt records
`ALLOW_READ_ONLY`, the collected evidence refs, payload hashes by reference,
blocked write actions, and any partial evidence gaps. The PR safety Workroom can
then use `build_pr_safety_projection_from_github_fetch_receipt` to bind that
receipt into a `Class 1 — Prepare` projection. This keeps the causal chain:

```text
read admission -> GET-only fetch -> read evidence receipt -> PR safety projection
```

The final projection still cannot merge, deploy, push, delete a branch, or post
a review. Read evidence earns inspection context, not execution authority.

## GitHub Actions Failure Diagnosis

The Actions failure path is the second narrow Workroom capability. It reuses the
same governed connector admission, evidence hashing, causal receipt, and
read-only effect boundary, but targets workflow-run failure diagnosis instead of
pull-request merge safety.

Allowed evidence:

```text
workflow_run
jobs
failed_job_logs
```

The live execution route performs only GET requests against `api.github.com` and
does not return or persist the access token. Failed job logs are reduced to
hash-bound digests and bounded failure-signal excerpts; raw full logs are not
persisted.

Blocked actions:

```text
rerun_workflow_without_explicit_approval
cancel_workflow_without_explicit_approval
dispatch_workflow_without_explicit_approval
post_github_comment_without_write_admission
mutate_repository_without_write_admission
```

The result is a read-only diagnosis receipt containing failure summary,
suspected failed jobs, payload hashes, bounded log signals, recommended next
action, and blocked actions. No endpoint in this path can rerun, cancel,
dispatch, comment, push, merge, or deploy.

## GitHub Repository Status Summary

The repository status path is the third narrow Workroom capability. It is a
`Class 0 - Observe` path for bounded repository overview, not release approval
and not repository mutation.

Allowed evidence:

```text
repository
recent_commits
open_pull_requests
open_issues
workflow_runs
```

The live execution route performs only GET requests against `api.github.com`,
hashes each payload, and returns bounded summaries for repository metadata,
recent commits, open pull requests, open issues, and recent workflow runs. The
access token is accepted only for the request, is not returned, and the browser
panel clears the password field after constructing the request.

Blocked actions:

```text
create_issue_without_explicit_approval
post_github_comment_without_write_admission
mutate_repository_without_write_admission
trigger_workflow_without_explicit_approval
claim_release_ready_without_required_evidence
```

The result is a read-only repository status receipt containing evidence refs,
payload hashes, partial failure reasons when GitHub evidence is incomplete,
open PR and issue counts, recent commit count, workflow status counts, and a
non-mutating final judgment. It can inform inspection, triage, or next planning
work, but it cannot create issues, post comments, trigger workflows, push,
merge, deploy, or certify release readiness.

## GitHub Patch Plan Draft

The patch-plan path is the fourth narrow Workroom capability. It is a
`Class 1 - Prepare` path that consumes bounded evidence summaries and receipt
refs from prior diagnosis, repository status, or PR safety work. It does not
read GitHub, accept an access token, edit files, create branches, create pull
requests, create issues, post comments, or claim that a fix is complete.

Required evidence:

```text
diagnosis_or_problem_summary
affected_file_or_component_refs
verification_expectations
```

Blocked actions:

```text
edit_repository_without_patch_approval
create_branch_without_explicit_approval
create_pull_request_without_explicit_approval
post_github_comment_without_write_admission
create_issue_without_explicit_approval
claim_fix_complete_without_verification
```

The result is a draft-only causal receipt containing the objective, evidence
refs, target summary, proposed steps, verification commands, risks, assumptions,
and blocked actions. Missing objective, evidence refs, evidence summaries, or
verification expectations returns `AwaitingEvidence` and defers memory update.
Drafting earns a plan, not write authority.

## GitHub Issue Draft

The issue-draft path is the fifth narrow Workroom capability. It is a
`Class 1 - Prepare` path that converts bounded diagnosis, status, PR safety, or
patch-plan evidence refs into local issue title/body/label suggestions. It does
not read GitHub, accept an access token, create issues, apply labels, assign
users, post comments, mutate repository state, or claim that an issue exists on
GitHub.

Required evidence:

```text
problem_summary
evidence_refs
acceptance_criteria
```

Blocked actions:

```text
create_github_issue_without_explicit_approval
apply_github_labels_without_write_admission
assign_github_issue_without_write_admission
post_github_comment_without_write_admission
mutate_repository_without_write_admission
claim_issue_created_without_live_receipt
```

The result is a draft-only causal receipt containing the issue title, issue
body, suggested labels, evidence refs, acceptance criteria, and blocked actions.
Missing problem summary, evidence refs, or acceptance criteria returns
`AwaitingEvidence` and defers memory update. Drafting earns an issue proposal,
not GitHub write authority.

## GitHub Release Readiness

The release-readiness path is the sixth narrow Workroom capability. It is a
`Class 1 - Prepare` path that converts bounded repository, CI, change, risk,
rollback, and blocker evidence refs into a local release-readiness judgment:
`ready`, `blocked`, or `awaiting_evidence`. It does not read GitHub, accept an
access token, create tags, create GitHub releases, deploy, publish packages,
trigger workflows, merge, mutate repository state, or claim external release
completion.

Required evidence:

```text
release_objective
candidate_ref
ci_status_ref
change_summary_ref
risk_or_rollback_ref
```

Blocked actions:

```text
create_git_tag_without_release_approval
create_github_release_without_release_approval
deploy_release_without_deployment_witness
publish_package_without_external_obligation_approval
trigger_workflow_without_explicit_approval
merge_or_mutate_repository_without_write_admission
claim_release_ready_without_required_evidence
```

The result is a prepare-only causal receipt containing the release objective,
candidate ref, evidence refs, blockers, required next evidence, release notes
outline, rollback summary, and blocked actions. Missing release objective,
candidate ref, CI status refs, change summary refs, or risk/rollback refs
returns `AwaitingEvidence` and defers memory update. Declared blockers return
`blocked`. A `ready` judgment earns only a local recommendation; release
execution still requires explicit human approval and fresh release/deployment
witness evidence.

## GitHub PR Merge Approval Request

The PR merge-approval-request path is the seventh narrow Workroom capability.
It is a `Class 1 - Prepare` path that converts bounded PR safety, CI, review,
rollback, and explicit approver evidence refs into a local approval request
packet. It does not read GitHub, accept an access token, merge, push, delete a
branch, deploy, post a comment, mutate repository state, or treat generic
continuation as merge approval.

Required evidence:

```text
pull_request_number
pr_safety_receipt_ref
ci_status_ref
review_approval_ref
rollback_ref
explicit_approver_ref
```

Blocked actions:

```text
merge_pull_request_without_explicit_human_approval
merge_pull_request_without_fresh_ci_evidence
merge_pull_request_without_pr_safety_receipt
merge_pull_request_without_review_approval_evidence
merge_pull_request_without_rollback_or_revert_plan
delete_branch_without_post_merge_cleanup_approval
deploy_after_merge_without_deployment_witness
mutate_repository_from_approval_request_packet
```

The result is a prepare-only causal receipt containing the approval question,
evidence refs, required next evidence, blockers, allowed response kinds, default
rejection response, and blocked actions. Missing PR safety, CI, review,
rollback, approver, or objective evidence returns `AwaitingEvidence` and defers
memory update. Declared blockers return `blocked`. A `ready_for_approval`
packet earns only an approval question; merge execution still requires explicit
human approval and a separate fresh merge-execution receipt.

`evaluate_github_pr_safety_judgment` converts the read-only fetch result and
fetch receipt into one bounded status:

| Status | Meaning |
| --- | --- |
| `ready_for_review` | Required read-only evidence is present and no blocking PR/check condition is observed. This permits review continuation only, not merge. |
| `blocked` | Evidence shows a blocking condition such as draft PR, failing checks, closed/merged PR, or GitHub non-mergeable state. |
| `needs_evidence` | Required evidence is missing, partial, stale, or internally unknown. |

The judgment always keeps `merge_authority_granted=false` and
`write_authority_granted=false`.

## Capability Registry Entry

Each registry entry carries the minimum information needed to execute an action without weakening closure law.

| Field | Governance role |
| --- | --- |
| `capability_id` | Stable action identity |
| `domain` | Domain ownership boundary |
| `input_schema_ref` | Typed intent contract |
| `output_schema_ref` | Typed result contract |
| `effect_model` | Expected and forbidden effects |
| `evidence_model` | Proof receipts required for closure |
| `authority_policy` | Roles, approval chain, and separation of duty |
| `isolation_profile` | Execution plane, network boundary, and secret scope |
| `recovery_plan` | Rollback, compensation, and review behavior |
| `cost_model` | Budget class and maximum estimated cost |
| `obligation_model` | Owner, due time, and escalation path |
| `certification_status` | Lifecycle gate for admission |

## GCI Execution Contract

Runtime tool execution is now gated by a fixed GCI `CapabilityContract` before any executor, worker, or adapter can run. The contract is the runtime-local admission unit that binds capability identity to governance depth, effect class, source trust, and five cost/risk axes.

| Field | Governance role |
| --- | --- |
| `capability` | Stable action identity used by the execution gate |
| `layer` | Runtime layer that owns the action boundary |
| `cap_level` | Capability autonomy or mutation level requested |
| `gov_tier` | Governance depth available for this request |
| `axis_T` | Temporal validity and freshness constraint |
| `axis_E` | Economic or budget constraint |
| `axis_C` | Cognitive/operator-review load constraint |
| `axis_R` | Risk tier carried into admission |
| `axis_V` | Effect class: `value_producing` or `effectful` |
| `precond` | Preconditions that must hold before execution |
| `fail_mode` | Explicit blocked or degraded behavior |
| `reversible` | Whether the action can be reversed without compensation |
| `intent_source` | Source-trust binding for authorization |

The central admission rule is:

```text
enable(capability @ Cn)
<=> gov_tier >= Gn
AND axis_T, axis_E, axis_C, axis_R, axis_V are populated
AND effectful requests are sourced from user_direct authorization
```

If the rule is not satisfied, `Phi_gov` blocks execution and the tool gateway records the denied path in the causal ledger. A command found in monitored content, a document, an email, or an external signal can inform planning, but it cannot become direct authorization for an effectful action.

Value-producing capabilities may create information only. Effectful capabilities mutate external or durable state and require the stronger gate.

| Capability | Effect class |
| --- | --- |
| summarize document | `value_producing` |
| draft email | `value_producing` |
| send email | `effectful` |
| deploy service | `effectful` |
| modify issue | `effectful` |
| delete file | `effectful` |

Reused plans, memory, repository state, deployment state, finance context, calendar facts, infrastructure facts, and security assumptions must pass `OP_reground` before they guide effectful execution. Digital state claims that affect closure must pass L2 reality verification because digital state and reality state can diverge.

`GovernedToolRegistry.capability_contract_coverage()` exposes the runtime read model for this gate. Operators can inspect registered tool count, enabled tool count, explicit versus synthesized contract count, blocked contract count, per-tool admission status, and rejected reasons without invoking any tool. A complete report means every registered tool has a populated `CapabilityContract` that satisfies the CxG grid; a blocked report identifies the exact `Phi_gov` reason before execution is possible.

`GovernedToolRegistry.decision_read_model()` exposes the bounded live operator view of recent tool decisions. It shows allowed count, blocked count, decision stage, source trust, effect class, capability level, governance tier, and reasons such as `effectful_action_requires_user_direct_intent_source`. This is visibility only; durable rejected-path receipts remain the audit authority for long-term evidence.

## Maturity Projection

Registry entries do not self-promote. Gateway-built fabric read models derive a `capability_maturity_assessment` from each installed entry and attach the C0-C7 summary to both the internal capability projection and the governed operator record. Certification can lift a capability to mock-evaluated maturity, but production readiness still requires explicit sandbox, live receipt, worker deployment, recovery, and autonomy evidence through `extensions.capability_maturity_evidence`.

Read models also expose a derived `maturity_label` for operator scanning. The label is not admission authority: `Specified` covers C0-C2, `Implemented` covers C3-C5, and `Verified` covers C6-C7. Runtime admission, production readiness, and autonomy readiness continue to use the C-level evidence gates and cannot be promoted by changing the label.

Checked-in default packs include two concrete C6 witnesses. `connector.github.read` is read-only and carries sandbox, live-read, worker deployment, and recovery evidence references; because it is not world-mutating, the live-write gate is not required. `financial.send_payment` is effect-bearing and reaches C6 only because it also carries live-write evidence. Both examples remain below C7 until bounded autonomy controls are supplied.

Certification pipelines can avoid hand-authored maturity flags by emitting `extensions.capability_certification_evidence` with concrete certification, sandbox, live-read, optional live-write, worker, recovery, and autonomy-control references. The maturity synthesizer converts that bundle into the canonical `capability_maturity_evidence` extension shape, validates the capability identity, and can run in strict mode when a caller requires production readiness before writing the generated extension.

## Capability Unlock Ladder

The C0-C7 maturity model remains the evidence-derived readiness contract. The
Level 0-9 unlock ladder is a reusable operator profile over that maturity model:
it says which gates must be present before a class of work may run. It does not
promote a capability and it does not create execution authority.

Canonical implementation:

```text
mcoi/mcoi_runtime/core/capability_unlock_ladder.py
```

Reusable gate templates:

| Gate template | Purpose |
| --- | --- |
| `evidence_intake_gate` | Collects bounded evidence before action selection. |
| `approval_gate` | Records explicit operator decision before a hard boundary. |
| `verifier_gate` | Checks observed state against the expected proof surface. |
| `workspace_write_gate` | Confines file writes to the controlled workspace or branch. |
| `connector_lease_gate` | Confines credentialed connector access to a scoped lease. |
| `execution_receipt_gate` | Requires command-bound execution receipts. |
| `rollback_gate` | Requires rollback, compensation, or recovery evidence. |
| `operator_review_gate` | Preserves human review before escalation or PR evidence. |

Unlock levels:

| Level | Name | Required boundary |
| ---: | --- | --- |
| 0 | Read-only | Evidence intake only; no durable or external effects. |
| 1 | Local demo | Local dry run plus verifier and receipt. |
| 2 | File preparation | Diffs, docs, schemas, tests, and review packets only. |
| 3 | File writing | Workspace write, receipt, rollback, and operator review. |
| 4 | Test execution | Bounded tests with verifier, receipt, and rollback. |
| 5 | PR creation | PR evidence preparation; opening requires approval. |
| 6 | Human approval | Approval or rejection is recorded as the effect. |
| 7 | Live connector probe | Scoped read-only credentialed connector lease and live witness. |
| 8 | Approved live action | Approved live write with receipt and recovery. |
| 9 | Customer-ready product | Customer exposure requires production witnesses, support, monitoring, and rollback. |

The focused contract test is:

```powershell
python -m pytest mcoi/tests/test_capability_unlock_ladder.py -q
```

### Admission Projection

`CommandCapabilityAdmissionGate` resolves `metadata.unlock_ladder` during typed
intent admission. Accepted decisions now carry the ladder id, level, gate
template ids, and approval, receipt, rollback, and live-witness booleans. This
turns the ladder from documentation metadata into a reusable runtime policy
surface without granting new authority.

Malformed ladder metadata fails closed with a stable reason and structured
rejection codes:

```text
reason: capability unlock profile invalid
rejection_codes: (<profile_error_code>, ...)
```

The admission resolver preserves older capability entries that do not declare a
ladder profile, but any entry that declares one must match the canonical ladder
exactly. This keeps future capability packs from silently substituting weaker
gates for effect-bearing actions.

## Friction Control Projection

The operator console now derives a `capability_friction_control` read model from
governed capability records. This projection does not grant execution authority.
It converts many fine-grained gates into four operator-facing questions:

| Question | Read-model source |
| --- | --- |
| What is unlocked? | `unlock_level`, `friction_status`, and mode admission fields. |
| What is blocked? | `blocked_actions` projected from forbidden effects, approval, and production evidence. |
| Why is it blocked? | `required_before_unlock` and `next_unlock`. |
| What boundary applies? | `operating_boundary`, `lab_mode_allowed`, and `real_world_mode_allowed`. |

Canonical unlock levels are:

```text
L0 read-only
L1 plan-only
L2 prepare-only
L3 write-to-sandbox
L4 run tests
L5 create PR
L6 merge with approval
L7 live connector read
L8 live connector write
L9 production/customer mode
```

Friction modes are read-model policy summaries:

| Mode | Meaning |
| --- | --- |
| `strict` | Approval before effect-bearing action and production evidence before real-world writes. |
| `balanced` | Read and prepare are automatic; risky local changes require approval. |
| `fast` | Local lab actions are automatic only when sandbox, receipt, rollback, and no-network constraints hold. |

The lab boundary is the default for Foundation Mode. Lab mode may write local
sandbox files, run tests, create demos, and prepare review packets. Real-world
mode remains blocked until the relevant capability carries production witness
evidence and any approval policy is satisfied.

Safe automatic zones:

```text
write_docs
write_tests
write_examples
write_local_demo_files
update_readme
generate_schemas
generate_validators
```

Dangerous zones:

```text
delete_files
touch_secrets
send_email
move_money
deploy
merge_to_main
write_production_data
```

Rollback is part of the friction contract: every world-mutating local capability
must expose receipt and rollback or compensation requirements before it can be
treated as fast-mode lab-ready.

Canonical artifacts:

| Artifact | Role |
| --- | --- |
| `schemas/capability_friction_control.schema.json` | Strict operator read-model contract. |
| `schemas/sandbox_to_pr_preparation_packet.schema.json` | Strict packet contract for local sandbox-to-PR readiness. |
| `schemas/developer_workflow_sandbox_receipt_attachment_packet.schema.json` | Strict operator attachment packet for the four sandbox receipt rows. |
| `schemas/developer_workflow_local_sandbox_proof_report.schema.json` | Strict no-execution report contract for the one-command local proof runner output. |
| `schemas/developer_workflow_local_rollback_summary_packet.schema.json` | Strict projection-only rollback summary contract for generated local proof artifacts. |
| `schemas/developer_workflow_local_rollback_approval_packet.schema.json` | Strict local-lab approval contract for selected generated artifact rollback deletion authority. |
| `schemas/developer_workflow_local_rollback_execution_receipt.schema.json` | Strict local-lab rollback execution receipt contract for approved generated artifact deletion. |
| `schemas/developer_workflow_sandbox_receipt_bundle.schema.json` | Strict local-lab receipt bundle contract for sandbox patch, test, diff, and terminal evidence. |
| `schemas/pr_preparation_approval_packet.schema.json` | Strict approval packet contract for local PR candidate preparation after sandbox receipts complete. |
| `schemas/local_pr_candidate_packet.schema.json` | Strict local PR candidate packet contract that remains local-only and does not open an external PR. |
| `schemas/pr_tool_admission_packet.schema.json` | Strict local PR-tool admission packet contract that permits local PR body/metadata preparation only. |
| `schemas/external_pr_execution_approval_witness.schema.json` | Strict approval witness contract for branch push and external PR creation authority. |
| `schemas/pr_command_preview_packet.schema.json` | Strict non-executing PR command preview packet contract. |
| `schemas/pr_metadata_packet.schema.json` | Strict PR title/body/label metadata packet contract. |
| `schemas/pr_readiness_bundle.schema.json` | Strict end-to-end PR readiness bundle contract. |
| `schemas/developer_workflow_operator_receipt.schema.json` | Strict concise operator receipt contract for the full Developer Workflow v1 path. |
| `schemas/operator_control_tower_status_receipt.schema.json` | Strict receipt contract for the dashboard focus export. |
| `examples/capability_friction_control.foundation.json` | Foundation Mode software-development projection. |
| `examples/sandbox_to_pr_preparation_packet.foundation.json` | Foundation Mode sandbox-to-PR packet fixture. |
| `examples/developer_workflow_sandbox_receipt_attachment_packet.foundation.json` | Foundation Mode sandbox receipt attachment packet fixture. |
| `examples/developer_workflow_local_sandbox_proof_report.foundation.json` | Foundation Mode local sandbox proof runner report fixture. |
| `examples/developer_workflow_local_rollback_summary_packet.foundation.json` | Foundation Mode rollback summary fixture for generated local proof artifacts. |
| `examples/developer_workflow_local_rollback_approval_packet.foundation.json` | Foundation Mode pending rollback approval fixture with no deletion authority. |
| `examples/developer_workflow_local_rollback_execution_receipt.foundation.json` | Foundation Mode rollback execution receipt fixture blocked by missing approval. |
| `examples/developer_workflow_sandbox_receipt_bundle.foundation.json` | Foundation Mode sandbox receipt bundle fixture. |
| `examples/developer_workflow_sandbox_receipt_evidence.partial.json` | Example local evidence input for the sandbox receipt bundle builder. |
| `examples/pr_preparation_approval_packet.foundation.json` | Foundation Mode PR-preparation approval packet fixture. |
| `examples/local_pr_candidate_packet.foundation.json` | Foundation Mode local PR candidate packet fixture. |
| `examples/pr_tool_admission_packet.foundation.json` | Foundation Mode PR-tool admission packet fixture. |
| `examples/external_pr_execution_approval_witness.foundation.json` | Foundation Mode external PR execution approval witness fixture. |
| `examples/pr_command_preview_packet.foundation.json` | Foundation Mode non-executing PR command preview fixture. |
| `examples/pr_metadata_packet.foundation.json` | Foundation Mode PR title/body/label metadata fixture. |
| `examples/pr_readiness_bundle.foundation.json` | Foundation Mode end-to-end PR readiness bundle fixture. |
| `scripts/validate_capability_friction_control.py` | Runtime and schema validator. |
| `scripts/validate_sandbox_to_pr_preparation_packet.py` | Schema and semantic validator for the sandbox-to-PR packet. |
| `scripts/build_developer_workflow_sandbox_receipt_attachment_packet.py` | Deterministic projection builder from sandbox-to-PR packet and sandbox receipt bundle to attachable receipt rows. |
| `scripts/validate_developer_workflow_sandbox_receipt_attachment_packet.py` | Schema and semantic validator for the sandbox receipt attachment packet. |
| `scripts/validate_developer_workflow_local_sandbox_proof_report.py` | Schema and semantic validator for the local sandbox proof runner report. |
| `scripts/build_developer_workflow_local_rollback_summary_packet.py` | Deterministic projection builder from local proof report generated artifacts to rollback command previews. |
| `scripts/validate_developer_workflow_local_rollback_summary_packet.py` | Schema and semantic validator for the rollback summary packet. |
| `scripts/build_developer_workflow_local_rollback_approval_packet.py` | Deterministic approval packet builder from rollback summary rows to selected local deletion authority. |
| `scripts/validate_developer_workflow_local_rollback_approval_packet.py` | Schema and semantic validator for the rollback approval packet. |
| `scripts/execute_developer_workflow_local_rollback.py` | Local rollback runner that deletes approved generated artifact files only with `--execute` after workspace-boundary checks. |
| `scripts/run_developer_workflow_local_rollback_flow.py` | One-command local rollback orchestration path that records approval, emits a dry-run receipt, and optionally executes rollback. |
| `scripts/validate_developer_workflow_local_rollback_execution_receipt.py` | Schema and semantic validator for the rollback execution receipt. |
| `scripts/collect_developer_workflow_sandbox_receipt_evidence.py` | Local artifact hash collector for one sandbox receipt evidence record. |
| `scripts/build_developer_workflow_sandbox_receipt_bundle.py` | Deterministic local builder from explicit evidence input to sandbox receipt bundle. |
| `scripts/run_developer_workflow_local_sandbox_proof.py` | One-command local proof runner that collects evidence, builds the sandbox bundle, refreshes the attachment packet, downstream PR-readiness packets, rollback summary packet, rollback approval packet, validates them, and prints opt-in dashboard URLs. |
| `scripts/validate_developer_workflow_sandbox_receipt_bundle.py` | Schema and semantic validator for the sandbox receipt bundle. |
| `scripts/build_pr_preparation_approval_packet.py` | Deterministic approval packet builder from sandbox receipt bundle to local PR candidate preparation request. |
| `scripts/validate_pr_preparation_approval_packet.py` | Schema and semantic validator for the PR-preparation approval packet. |
| `scripts/build_local_pr_candidate_packet.py` | Deterministic local PR candidate packet builder from approved preparation packet. |
| `scripts/validate_local_pr_candidate_packet.py` | Schema and semantic validator for the local PR candidate packet. |
| `scripts/build_pr_tool_admission_packet.py` | Deterministic local PR-tool admission packet builder from a local PR candidate packet. |
| `scripts/validate_pr_tool_admission_packet.py` | Schema and semantic validator for the PR-tool admission packet. |
| `scripts/build_external_pr_execution_approval_witness.py` | Deterministic approval witness builder for external PR execution authority. |
| `scripts/validate_external_pr_execution_approval_witness.py` | Schema and semantic validator for the external PR execution approval witness. |
| `scripts/build_pr_command_preview_packet.py` | Deterministic non-executing command preview builder from an external PR approval witness. |
| `scripts/validate_pr_command_preview_packet.py` | Schema and semantic validator for the PR command preview packet. |
| `scripts/build_pr_metadata_packet.py` | Deterministic PR metadata builder from the local candidate and optional command preview. |
| `scripts/validate_pr_metadata_packet.py` | Schema and semantic validator for the PR metadata packet. |
| `scripts/build_pr_readiness_bundle.py` | Deterministic end-to-end readiness bundle builder linking all PR artifacts. |
| `scripts/validate_pr_readiness_bundle.py` | Schema and semantic validator for the PR readiness bundle. |
| `scripts/build_developer_workflow_operator_receipt.py` | Deterministic concise operator receipt builder over the generated Developer Workflow packet chain. |
| `tests/test_validate_capability_friction_control.py` | Contract and rejection coverage. |
| `tests/test_validate_sandbox_to_pr_preparation_packet.py` | Packet validator and rejection coverage. |
| `tests/test_build_developer_workflow_sandbox_receipt_attachment_packet.py` | Attachment packet builder coverage for pending, complete, and CLI write paths. |
| `tests/test_validate_developer_workflow_sandbox_receipt_attachment_packet.py` | Attachment packet validator coverage for authority, action, and bundle-status drift. |
| `tests/test_validate_developer_workflow_local_sandbox_proof_report.py` | Local proof report validator coverage for no-effect, status, URL, and artifact drift. |
| `tests/test_build_developer_workflow_local_rollback_summary_packet.py` | Rollback summary builder coverage for generated artifact projection and empty reports. |
| `tests/test_validate_developer_workflow_local_rollback_summary_packet.py` | Rollback summary validator coverage for authority, artifact, command, and confirmation drift. |
| `tests/test_build_developer_workflow_local_rollback_approval_packet.py` | Rollback approval builder coverage for pending and approved selected artifact states. |
| `tests/test_validate_developer_workflow_local_rollback_approval_packet.py` | Rollback approval validator coverage for evidence, artifact, command, status, and execution overclaim drift. |
| `tests/test_execute_developer_workflow_local_rollback.py` | Rollback execution runner coverage for dry-run, deletion, boundary blocking, and CLI receipt output. |
| `tests/test_run_developer_workflow_local_rollback_flow.py` | Rollback flow coverage for approval selection, mandatory dry-run, optional execution, and CLI output. |
| `tests/test_validate_developer_workflow_local_rollback_execution_receipt.py` | Rollback execution receipt validator coverage for overclaim, count drift, boundary evidence, and CLI output. |
| `tests/test_collect_developer_workflow_sandbox_receipt_evidence.py` | Collector coverage for hashing, merge behavior, and rejection paths. |
| `tests/test_build_developer_workflow_sandbox_receipt_bundle.py` | Builder coverage for partial, complete, and rejected evidence. |
| `tests/test_run_developer_workflow_local_sandbox_proof.py` | Local proof runner coverage for sandbox bundle generation, PR-readiness projection, opt-in URLs, and rejection paths. |
| `tests/test_validate_developer_workflow_sandbox_receipt_bundle.py` | Bundle validator and rejection coverage. |
| `tests/test_build_pr_preparation_approval_packet.py` | PR-preparation approval packet builder coverage for incomplete, complete, and overclaim paths. |
| `tests/test_validate_pr_preparation_approval_packet.py` | Fixture validator coverage for local-only approval and external PR rejection. |
| `tests/test_build_local_pr_candidate_packet.py` | Local PR candidate packet builder coverage for receipt, approval, ready, and overclaim paths. |
| `tests/test_validate_local_pr_candidate_packet.py` | Fixture validator coverage for local candidate authority boundaries. |
| `tests/test_build_pr_tool_admission_packet.py` | PR-tool admission packet builder coverage for blocked, admitted, and overclaim paths. |
| `tests/test_validate_pr_tool_admission_packet.py` | Fixture validator coverage for local PR-tool admission authority boundaries. |
| `tests/test_build_external_pr_execution_approval_witness.py` | External PR approval witness builder coverage for pending, approved, and overclaim paths. |
| `tests/test_validate_external_pr_execution_approval_witness.py` | Fixture validator coverage for pending external PR execution approval. |
| `tests/test_build_pr_command_preview_packet.py` | PR command preview builder coverage for blocked, approved, and executed-claim paths. |
| `tests/test_validate_pr_command_preview_packet.py` | Fixture validator coverage for non-executing preview boundaries. |
| `tests/test_build_pr_metadata_packet.py` | PR metadata builder coverage for blocked, ready, and authority-overclaim paths. |
| `tests/test_validate_pr_metadata_packet.py` | Fixture validator coverage for PR metadata non-execution boundaries. |
| `tests/test_build_pr_readiness_bundle.py` | PR readiness bundle builder coverage for blocked, ready, and overclaim paths. |
| `tests/test_validate_pr_readiness_bundle.py` | Fixture validator coverage for end-to-end readiness bundle boundaries. |
| `tests/test_build_developer_workflow_operator_receipt.py` | Operator receipt builder coverage for blocked, ready-preview, and execution-overclaim paths. |
| `/operator/capabilities/friction-control/read-model` | Read-only gateway route for the live operator projection. |
| `/operator/developer-workflow/read-model` | Read-only `workflow_run` projection for Developer Workflow v1 stage state. |
| `/operator/developer-workflow` | Browser drilldown for the Developer Workflow v1 run receipt. |
| `/operator/control-tower/read-model` | Read-only operator control tower snapshot with capability friction, approval, receipt, workflow panels, and sandbox-to-PR packet attached. |
| `/operator/control-tower` | Browser dashboard showing Developer Workflow v1 task, status, reason, next unlock, risk, action needed, rollback posture, rollback summary previews, receipt checklist, sandbox-to-PR packet, current stage, panel health, and drilldown links. |

The Developer Workflow v1 route conforms to
`schemas/workflow_run.schema.json`. Its receipt is projection-only and keeps
`execution_allowed`, `write_allowed`, and `real_world_effects_allowed` false
until an actual governed execution path supplies approval, sandbox-write,
diff, test, rollback, and PR-candidate evidence.

The friction-control read model also exposes `sandbox_to_pr_now`, a compact
operator answer for "what blocks PR now" without requiring the full control
tower. In Foundation Mode the field is policy-level only: it can report that
capability policy and workflow topology are ready, while the live sandbox
receipts still need to be attached through the control tower packet.
The capability console renders the same field with a compact next-evidence
table for the required sandbox patch, test gate, diff review, and terminal
receipts. Each row includes a bounded `action` hint that describes the receipt
to attach without granting command execution authority.
The control tower sandbox-to-PR packet exposes the same `next_evidence` shape so
the console and tower cannot diverge on which receipt bundle is missing.
The drift guard is bidirectional: `validate_capability_friction_control.py`
loads the packet fixture, and `validate_sandbox_to_pr_preparation_packet.py`
loads the friction-control fixture. Both validators compare evidence ids,
labels, action hints, and receipt sources, so either fixture changing alone
fails closed.
The packet also references the sandbox receipt bundle contract and validator.
`validate_sandbox_to_pr_preparation_packet.py` compares packet receipt count,
ready state, and evidence signature against
`examples/developer_workflow_sandbox_receipt_bundle.foundation.json`, so the PR
packet cannot drift away from the concrete local-lab receipt slots.
The packet reference also names
`scripts/build_developer_workflow_sandbox_receipt_bundle.py`, which converts
operator-supplied or runtime-supplied local evidence into the bundle without
running effects. Missing receipt evidence remains pending; concrete receipt
evidence can advance one receipt at a time.
The receipt attachment packet sits between the operator action hints and the
full sandbox receipt bundle. It projects each canonical sandbox receipt row with
the required input field names, observed bundle values, evidence refs, and first
pending attachment while preserving `external_effects_allowed = false`. Its
builder is a read-only projection over the sandbox-to-PR packet and receipt
bundle; it does not collect files, run tests, write code, or approve PR work.
`scripts/collect_developer_workflow_sandbox_receipt_evidence.py` is the
observational bridge before the builder: it reads named local artifact files,
records only `sha256:` hashes and evidence refs, and merges one canonical
receipt id into the builder input JSON. The local proof runner can also consume
one receipt manifest with all four canonical receipt entries, then rebuild the
same sandbox bundle and downstream PR-readiness chain in one command.
The developer workflow and control tower can consume the collected bundle only
through the explicit read-only query flag
`include_local_sandbox_receipts=true`. Without that flag, Foundation Mode keeps
the default pending projection; with it, the gateway reads the fixed local
`.change_assurance/developer_workflow_sandbox_receipt_bundle.collected.json`
bundle and maps complete bundle receipts into the workflow checklist.
The dashboard renders this as `Local sandbox bundle`, showing the bundle status
and completed bundle receipt count without changing approval, PR, or external
write authority.
The dashboard also renders `Local Sandbox Bundle Receipts`, a bounded
receipt-level projection with label, status, stage, required flag, and evidence
refs. The same bounded summary is exported in
`/operator/control-tower/status-receipt` under `sandbox_receipt_bundle`.
The dashboard now also renders `Sandbox Receipt Attachments`, a compact table
from `workflow_monitor.metadata.sandbox_receipt_attachment_packet`. It shows the
operator-facing attachment status, next attachment, action hint, source, and
evidence refs for each canonical sandbox receipt. The same projection is
included in `/operator/control-tower/status-receipt` under
`sandbox_receipt_attachments`, with no execution or external effect authority.
The one-command local proof runner also writes
`.change_assurance/developer_workflow_local_sandbox_proof_report.generated.json`.
When local sandbox receipts are explicitly included, the control tower exposes a
bounded `local_sandbox_proof_report` summary and renders `Local Sandbox Proof
Report` with the generated artifact paths. The loader rejects any report that
claims command execution or external effects.
After the bundle closes, `build_pr_preparation_approval_packet.py` emits the
operator approval request for local PR candidate packet preparation. The packet
does not open a pull request; it keeps `pr_creation_allowed = false`, forbids
branch push, merge, deployment, and connector calls, and defaults the decision
to `defer`. When invoked with `--approval-status approved` after receipts are
complete, the packet records only the local approval to prepare a PR candidate;
external effects remain closed.
After approval is recorded, `build_local_pr_candidate_packet.py` can emit the
local PR candidate packet. That packet can become `ready_for_pr_tool`, but it
still keeps external effects, branch push, and PR creation disabled.
`build_pr_tool_admission_packet.py` then consumes that candidate and admits
only local PR-tool preparation when the candidate is ready. The admitted local
actions are PR body rendering, PR metadata assembly, and command preview
preparation. Opening an external pull request, pushing a branch, merging,
deploying, and connector calls remain forbidden in the admission packet.
`build_external_pr_execution_approval_witness.py` is the final authority witness
before external PR effects. It can mark branch push and external pull request
creation as allowed only when local PR-tool admission is true and the operator
approval status is `approved`. The witness records authority evidence only; it
does not push a branch, open a pull request, merge, deploy, or call a connector.
`build_pr_command_preview_packet.py` consumes that witness and renders exact
`git push` and `gh pr create` command text only after authority is present. The
packet is always `preview_only`, always records `execution_performed = false`,
and emits no command text while blocked.
The local proof runner exposes the same final handoff with
`--external-pr-approval-status approved`; it may render command previews, but it
does not execute them.
`build_pr_metadata_packet.py` prepares the governed PR title, body sections,
labels, source branch, target branch, rollback notes, and command-preview
binding. It remains preview-only and grants no branch push or pull request
creation authority.
`build_pr_readiness_bundle.py` links the sandbox receipt bundle, approval
packet, local candidate, PR-tool admission packet, external approval witness,
command preview, metadata, and rollback into one operator-facing packet. In
Foundation Mode it remains blocked until sandbox receipts and downstream
approval artifacts close.
`build_developer_workflow_operator_receipt.py` compresses the same generated
packet chain into one concise operator receipt with sandbox progress, approval
state, local candidate state, external handoff state, rollback, source refs, and
`execution_performed = false`.
The operator control tower also projects this as
`workflow_monitor.metadata.pr_readiness_bundle` and
`workflow_monitor.metadata.developer_workflow_operator_receipt`, renders `PR
Readiness Bundle` and `Developer Workflow Operator Receipt` dashboard sections,
and exports the same compact no-execution status in
`/operator/control-tower/status-receipt`.
The operator control tower derives `sandbox_to_pr_focus` from the same packet,
showing the first pending sandbox receipt before receipts are complete, then the
approval or PR candidate gate after the receipt bundle closes.
The route `/operator/control-tower/status-receipt` exports that focus as a
hash-bearing, projection-only status receipt, including the bounded focus
`action` hint. It is audit evidence for what the dashboard showed; it does not
approve writes, prepare a PR, or mutate external state. The receipt conforms to
`schemas/operator_control_tower_status_receipt.schema.json`.
The friction-control read model advertises the status receipt validator and
test lane as required closure validators so the dashboard receipt check is not
only a route-level test.

Validation:

```powershell
python scripts/validate_capability_friction_control.py
python scripts/validate_sandbox_to_pr_preparation_packet.py
python scripts/build_developer_workflow_sandbox_receipt_attachment_packet.py --json
python scripts/validate_developer_workflow_sandbox_receipt_attachment_packet.py
python scripts/validate_developer_workflow_local_sandbox_proof_report.py
python scripts/collect_developer_workflow_sandbox_receipt_evidence.py --receipt-id sandbox_patch_receipt --before-file .change_assurance/before.txt --after-file .change_assurance/after.txt --diff-file .change_assurance/sandbox_patch.diff --command "apply_patch" --rollback-command "git apply -R .change_assurance/sandbox_patch.diff" --evidence-ref proof://developer-workflow-v1/sandbox-patch
python scripts/build_developer_workflow_sandbox_receipt_bundle.py --evidence examples/developer_workflow_sandbox_receipt_evidence.partial.json --output .change_assurance/developer_workflow_sandbox_receipt_bundle.generated.json
python scripts/run_developer_workflow_local_sandbox_proof.py --existing-evidence= --receipt-id sandbox_patch_receipt --before-file .change_assurance/before.txt --after-file .change_assurance/after.txt --diff-file .change_assurance/sandbox_patch.diff --command "apply_patch" --rollback-command "git apply -R .change_assurance/sandbox_patch.diff" --evidence-ref proof://developer-workflow-v1/sandbox-patch --json
python scripts/run_developer_workflow_local_sandbox_proof.py --existing-evidence= --receipt-manifest .change_assurance/developer_workflow_receipts.manifest.json --json
python scripts/run_developer_workflow_local_sandbox_proof.py --existing-evidence= --receipt-manifest .change_assurance/developer_workflow_receipts.manifest.json --pr-preparation-approval-status approved --json
python scripts/run_developer_workflow_local_sandbox_proof.py --existing-evidence= --receipt-manifest .change_assurance/developer_workflow_receipts.manifest.json --pr-preparation-approval-status approved --external-pr-approval-status approved --json
python scripts/validate_developer_workflow_sandbox_receipt_bundle.py
python scripts/build_pr_preparation_approval_packet.py --bundle examples/developer_workflow_sandbox_receipt_bundle.foundation.json --output .change_assurance/pr_preparation_approval_packet.generated.json --approval-status pending
python scripts/validate_pr_preparation_approval_packet.py
python scripts/build_local_pr_candidate_packet.py --approval-packet examples/pr_preparation_approval_packet.foundation.json --output .change_assurance/local_pr_candidate_packet.generated.json
python scripts/validate_local_pr_candidate_packet.py
python scripts/build_pr_tool_admission_packet.py --candidate-packet examples/local_pr_candidate_packet.foundation.json --output .change_assurance/pr_tool_admission_packet.generated.json
python scripts/validate_pr_tool_admission_packet.py
python scripts/build_external_pr_execution_approval_witness.py --admission-packet examples/pr_tool_admission_packet.foundation.json --output .change_assurance/external_pr_execution_approval_witness.generated.json
python scripts/validate_external_pr_execution_approval_witness.py
python scripts/build_pr_command_preview_packet.py --approval-witness examples/external_pr_execution_approval_witness.foundation.json --output .change_assurance/pr_command_preview_packet.generated.json
python scripts/validate_pr_command_preview_packet.py
python scripts/build_pr_metadata_packet.py --candidate-packet examples/local_pr_candidate_packet.foundation.json --command-preview-packet examples/pr_command_preview_packet.foundation.json --output .change_assurance/pr_metadata_packet.generated.json
python scripts/validate_pr_metadata_packet.py
python scripts/build_pr_readiness_bundle.py --output .change_assurance/pr_readiness_bundle.generated.json
python scripts/validate_pr_readiness_bundle.py
python scripts/build_developer_workflow_operator_receipt.py --output .change_assurance/developer_workflow_operator_receipt.generated.json
python scripts/validate_operator_control_tower_status_receipt.py
python -m pytest tests/test_validate_capability_friction_control.py -q
python -m pytest tests/test_validate_sandbox_to_pr_preparation_packet.py -q
python -m pytest tests/test_build_developer_workflow_sandbox_receipt_attachment_packet.py tests/test_validate_developer_workflow_sandbox_receipt_attachment_packet.py -q
python -m pytest tests/test_validate_developer_workflow_local_sandbox_proof_report.py -q
python -m pytest tests/test_collect_developer_workflow_sandbox_receipt_evidence.py -q
python -m pytest tests/test_build_developer_workflow_sandbox_receipt_bundle.py -q
python -m pytest tests/test_run_developer_workflow_local_sandbox_proof.py -q
python -m pytest tests/test_validate_developer_workflow_sandbox_receipt_bundle.py -q
python -m pytest tests/test_build_pr_preparation_approval_packet.py -q
python -m pytest tests/test_validate_pr_preparation_approval_packet.py -q
python -m pytest tests/test_build_local_pr_candidate_packet.py -q
python -m pytest tests/test_validate_local_pr_candidate_packet.py -q
python -m pytest tests/test_build_pr_tool_admission_packet.py -q
python -m pytest tests/test_validate_pr_tool_admission_packet.py -q
python -m pytest tests/test_build_external_pr_execution_approval_witness.py -q
python -m pytest tests/test_validate_external_pr_execution_approval_witness.py -q
python -m pytest tests/test_build_pr_command_preview_packet.py -q
python -m pytest tests/test_validate_pr_command_preview_packet.py -q
python -m pytest tests/test_build_pr_metadata_packet.py -q
python -m pytest tests/test_validate_pr_metadata_packet.py -q
python -m pytest tests/test_build_pr_readiness_bundle.py -q
python -m pytest tests/test_validate_pr_readiness_bundle.py -q
python -m pytest tests/test_build_developer_workflow_operator_receipt.py -q
python -m pytest tests/test_validate_operator_control_tower_status_receipt.py -q
python scripts/validate_schemas.py
```

## Capability Forge

The capability forge emits candidate packages and certification handoffs, never registry mutations. A candidate handoff binds the package id, package hash, sandbox receipt, live receipt, worker deployment, recovery evidence, and optional autonomy-control reference into a `CapabilityCertificationEvidenceBundle` that the maturity synthesizer can consume. Effect-bearing handoffs fail closed until live-write and recovery evidence references are present.

The forge-side registry handoff installer accepts only a stamped handoff for an already certified registry entry. It writes the bundle as `extensions.capability_certification_evidence`, refuses direct `capability_maturity_evidence` overrides, and validates production readiness through the maturity synthesizer without installing executable capability records or bypassing capsule admission.

For capsule compilation, the batch installer requires exact coverage between registry entries and handoffs, preserves entry order, and returns a hash-stamped batch witness. The capsule compiler then serializes those evidence-bearing entries, and `GovernedCapabilityRegistry.install` still performs the only executable registry admission.

## Capsule Admission Shortcut

Operators do not need to hand-correlate forge handoffs, compiler artifacts, and registry installation records. `install_certified_capsule_with_handoff_evidence` composes the existing gates in one deterministic sequence:

```text
registry entries + certification handoffs
  -> exact handoff evidence batch
  -> domain capsule compilation
  -> GovernedCapabilityRegistry.install
  -> capsule admission receipt
```

The receipt records the batch hash, handoff hashes, compilation id, installation id, capability ids, artifact ids, certification-evidence manifest id, warnings, errors, and post-install registry counts. It is an audit witness only; `GovernedCapabilityRegistry.install` remains the admission authority. If strict admission rejects a compiled capsule, the function still returns a rejected receipt without mutating registry state.

The gateway exposes this shortcut through the authority-operator boundary:

| Route | Method | Role |
| --- | --- | --- |
| `/capability-fabric/capsule-admissions` | `POST` | Accepts one capsule, registry entry set, handoff set, and `require_production_ready` flag; returns the receipt, evidence batch, compilation result, and installation record. |
| `/capability-fabric/capsule-admission-receipts` | `GET` | Returns recent admission receipts with optional `status`, `limit`, and `offset` bounds. |

The POST surface fails closed when capability fabric admission is disabled, rejects malformed payloads before registry mutation, and stores only the hash-stamped receipt in the bounded in-process operator receipt window.

## Domain Capsule

A domain capsule is a packaged operating model, not a free-form plugin.

| Capsule part | Required relation |
| --- | --- |
| `ontology_refs` | Defines domain symbols and resource identities |
| `capability_refs` | Binds the capsule to executable registry actions |
| `policy_refs` | Binds action admission to policy law |
| `evidence_rules` | Defines proof required before terminal closure |
| `approval_rules` | Defines authority and escalation paths |
| `recovery_rules` | Defines rollback, compensation, and review obligations |
| `test_fixture_refs` | Defines certification fixtures |
| `read_model_refs` | Defines certified state projections |
| `operator_view_refs` | Defines console surfaces over certified state |
| `owner_team` | Owns unresolved risk and post-closure obligations |

## Capsule Compiler

The capsule compiler has one responsibility: convert a domain capsule into deployable governed artifacts without changing global command law.

```text
capsule source
  -> schema validation
  -> ontology reference validation
  -> capability reference validation
  -> policy/evidence/recovery compilation
  -> registry entry emission
  -> certification evidence manifest emission
  -> fixture and read-model registration
  -> certification report
```

Compiler output must include registry manifests, certification evidence manifests, policy packs, evidence packs, approval packs, recovery packs, obligation templates, fixture references, read-model descriptors, operator-view descriptors, and a certification report. The certification evidence manifest is an operator audit artifact over `extensions.capability_certification_evidence`; it is not admission authority. Marketplace installation is blocked until the certification report marks the capsule `certified`.

## Closure Rule

The fabric does not authorize text-only success claims. Effect-bearing capabilities must return command-bound evidence, then effect assurance reconciles observed state, and only terminal closure can certify completion.

## Command Admission Rule

Typed command intents resolve by exact `intent_name -> capability_id` lookup against the installed governed capability registry. A command that does not resolve to an installed capability receives an explicit rejected admission decision before dispatch. Accepted decisions carry the capability domain, owner team, and evidence obligations forward into execution planning.
