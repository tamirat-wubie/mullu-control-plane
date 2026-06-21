# Mullu Personal Assistant Skill Architecture

Purpose: define the governed foundation architecture for personal-assistant request interpretation, skill routing, planning, approval, receipts, and memory observation.
Governance scope: OCE request completeness, RAG skill-to-capability linkage, CDCV plan-to-receipt causality, CQTE risk classification, UWMA evidence anchoring, SRCA bounded clarification loops, and PRS non-terminal foundation closure.
Dependencies: `docs/PERSONAL_ASSISTANT_RISK_BOUNDARY.md`, `docs/PERSONAL_ASSISTANT_MVP_ROADMAP.md`, `schemas/personal_assistant_*.schema.json`, `governance/personal_assistant_skill_policy.yaml`, `governance/personal_assistant_approval_matrix.yaml`, `capabilities/personal_assistant/capability_pack.json`, Universal Action Orchestration, WHQR clarification, existing communication capability packs, and Nested Mind staging evidence.
Invariants: the assistant plans, summarizes, drafts, clarifies, and records receipts by default; it does not send, delete, pay, publish, deploy, invite, message, mutate connector state, write systems of record, or activate live Nested Mind without explicit approval and evidence.

## Architecture

The personal assistant is a governed user-intent interpreter, not a loose chatbot.

```text
User request
-> Personal Assistant Intake
-> WHQR clarification or interpretation
-> Skill router
-> Risk and approval classifier
-> Plan builder
-> Capability adapter boundary
-> Dry run or preview
-> Approval gate when required
-> Execution only in later PRs
-> Evidence receipt
-> Governed memory observation
-> User-visible result
```

The formal record chain is:

```text
Human request
-> GovernedIntent
-> WHQRBinding
-> SkillPlan
-> ApprovalDecision
-> CapabilityDispatch
-> EvidenceReceipt
-> MemoryObservation
-> FollowUpState
```

This PR scope stops before `CapabilityDispatch` execution. It adds the static contracts, policies, fixtures, and validators needed for future execution lanes.

## Layer Boundary

| Layer | Purpose | Current authority |
| --- | --- | --- |
| Assistant boundary | Defines allowed and blocked assistant behavior | Static policy only |
| Interfaces | Binds web chat, console, and read-only intake surfaces to one core | Documentation only |
| Request intake | Converts user text into `personal_assistant.request` | Schema and examples only |
| WHQR bridge | Detects missing entity, evidence, action, and approval bindings | Architecture contract only |
| Skill registry | Registers governed skills with mode, risk, connectors, and blocked actions | Example registry and validator |
| Planner | Produces preview or draft plans with approval gates | Schema only |
| Approval | Classifies P0-P5 risk and explicit approval requirements | Matrix, validator, and stateless queue read/preview projection |
| Receipts | Records what was and was not done, with redaction policy | Schema, example, and validator |
| Memory observation | Prepares evidence-backed observation candidates, not raw chat logs | Schema, validator, runtime candidate ledger, and stateless public preview |

## Skill Groups

| Group | First allowed lane | Blocked until later evidence |
| --- | --- | --- |
| Inbox | summarize, find urgent, draft response | send, archive, delete, forward, batch label |
| Calendar | day brief, conflict detect, draft event | create, move, cancel, invite |
| Task | create proposal, prioritize, detect deadlines | write task without approval |
| Document | summarize, extract actions, draft, compare | sign, submit, publish, share externally, delete |
| Contact | lookup, disambiguate, context summary | message, invite, store contact, export list |
| TeamOps | shared-inbox plan, handoff, approval packet | live probe or mailbox mutation without approval evidence |
| Research | source compare, citation pack, watchlist plan | public posting, external submission, paid action |
| Math | calculate, compare scenarios, check units, explain assumptions | money movement, system-of-record write, connector mutation, public claim |
| GitHub and Codex | repo status, PR summary, release-readiness review | push, merge, open PR, deploy without approval |
| Planning | schedule, resource, budget, and priority solving | money movement or system mutation |
| Memory | observe, retrieve, compare, prepare child context | raw log storage or live Nested Mind activation |

## Request Contract

Every request must become a structured object with:

```text
request_id
request_type = personal_assistant.request
user_goal
requested_capabilities
risk_level
requires_approval
execution_mode
missing_bindings
connector_refs
governance_refs
blocked_actions
```

Unclear requests must not be silently interpreted. WHQR clarification records missing:

1. Entity binding, such as "which Daniel".
2. Evidence binding, such as "which document".
3. Action boundary, such as "draft only or send".
4. Approval scope, such as "one message or all messages".

## Skill Contract

Every skill record must include:

```text
skill_id
mode
risk_level
requires_approval
connectors
allowed_actions
blocked_actions
effect_boundary
capability_refs
receipt_required
nested_mind_live_activation_allowed = false
public_readiness_claim_allowed = false
```

Read-only and draft-only skills cannot declare mutation authority. P4 and P5 skills cannot be admitted without explicit approval.

## Approval Queue Contract

Approval queue records are evidence objects, not execution grants. A queue
record may bind:

```text
approval_id
request_id
plan_id
proposed_actions
forbidden_without_approval
decision_record
receipt_ref
evidence_refs
```

An approval decision can be `approved`, `rejected`, `revised`, or `expired`,
but the decision itself does not call a connector or perform the proposed
action. Public queue projections must keep:

```text
approval_is_execution = false
execution_allowed = false
external_send_allowed = false
connector_mutation_allowed = false
system_of_record_write_allowed = false
```

Future execution after approval still requires a separate UAO dispatch,
connector authority proof, effect receipt, and rollback or compensation plan.

Memory observation review records are also evidence objects, not memory-write
grants. A review decision can be `kept_for_operator_review`, `rejected`,
`revision_requested`, `deferred`, or `expired`. Kept, revision, and deferred
reviews emit deferred receipts; rejected and expired reviews emit blocked
receipts. All review receipts keep:

```text
live_memory_write_allowed = false
memory_admission_allowed = false
nested_mind_live_activation_allowed = false
raw_private_payload_storage_allowed = false
secret_value_storage_allowed = false
system_of_record_write_allowed = false
```

## Receipt Contract

Every assistant action, including blocked and draft-only actions, emits a receipt with:

```text
actions_taken
actions_not_taken
decision
approval_required
redactions
private_payload_policy
evidence_refs
timestamp
```

Receipts must never serialize raw connector payloads, raw private message bodies, token values, credentials, or private keys. Receipts may carry hashes, refs, redacted summaries, and bounded action names.

Math receipts add a stricter planning-only proof boundary:

```text
connectors_used = []
connector_payload_projection = no_connector_payload
approval_required = false
actions_not_taken include payment, subscription, system-of-record write, connector mutation, external submission, public post, and publication denial witnesses
```

Planning receipts add a schedule-preview proof boundary:

```text
connectors_used = []
connector_payload_projection = no_connector_payload
approval_required = false
actions_not_taken include calendar event creation, task write, invite, message, system-of-record write, connector mutation, external submission, public post, money movement, deployment, memory write, and Nested Mind activation denial witnesses
```

## Memory Contract

Memory observations are governed claims, not chat logs. Each observation must carry:

```text
memory_type
claim
source
confidence
scope
mutable
receipt_id
evidence_refs
retention_policy
```

The current memory lane is candidate-only. It may prepare a claim-level
observation, attach source evidence, emit a receipt, and expose a read model for
operator review. It must keep:

```text
live_memory_write_allowed = false
nested_mind_live_activation_allowed = false
raw_private_payload_storage_allowed = false
secret_value_storage_allowed = false
candidate_only = true
```

Nested Mind remains `staging_only` until staging evidence and a memory topology
activation decision exist. Requests to activate Nested Mind live memory are
blocked or classified as `AwaitingEvidence`, not represented as complete.

## TeamOps Shared-Inbox Contract

TeamOps shared-inbox plans are operator handoff projections, not mailbox
operations. A TeamOps plan may classify handoff readiness, summarize live-probe
gates, and emit a receipt. It must keep:

```text
execution_allowed = false
live_connector_execution_allowed = false
live_probe_execution_allowed = false
mailbox_read_allowed = false
mailbox_mutation_allowed = false
draft_creation_allowed = false
external_send_allowed = false
connector_mutation_allowed = false
system_of_record_write_allowed = false
```

The public preview route is
`/api/v1/personal-assistant/teamops/shared-inbox/plan/preview`. It accepts
connector proof references and bounded environment-shape evidence only. It does
not call Gmail, read shared inboxes, create drafts, send messages, mutate
provider configuration, serialize secrets, activate Nested Mind, or claim
customer readiness.

## GitHub and Codex Review Contract

GitHub and Codex review plans are operator-supplied evidence projections, not
GitHub adapter operations. A review plan may summarize a pull-request evidence
packet, classify blocking questions, and draft the next Codex instruction. It
must keep:

```text
execution_allowed = false
live_connector_execution_allowed = false
github_call_allowed = false
repository_read_allowed = false
repository_mutation_allowed = false
pull_request_mutation_allowed = false
branch_push_allowed = false
issue_creation_allowed = false
review_submission_allowed = false
deployment_mutation_allowed = false
system_of_record_write_allowed = false
```

The public preview route is
`/api/v1/personal-assistant/github-codex/review/preview`. It accepts connector
proof references and bounded operator-supplied PR evidence only. It does not
call GitHub, read repositories, open or merge pull requests, push branches,
create issues, submit reviews, deploy services, serialize raw diffs or secrets,
activate Nested Mind, or claim customer readiness.

## Research Source-Compare Contract

Research source-compare plans are operator-supplied public-source evidence
projections, not live retrieval operations. A research plan may compare bounded
source summaries, bind citation refs, classify freshness/conflict notes, and
emit a receipt. It must keep:

```text
execution_allowed = false
live_connector_execution_allowed = false
web_search_allowed = false
web_search_performed = false
source_contact_allowed = false
external_submission_allowed = false
public_post_allowed = false
paid_subscription_allowed = false
system_of_record_write_allowed = false
memory_write_allowed = false
```

The public preview route is
`/api/v1/personal-assistant/research/source-compare/preview`. It accepts bounded
operator-supplied source metadata and citation refs only. It does not browse the
web, contact sources, submit externally, post publicly, start subscriptions,
write memory, serialize raw source bodies or secrets, activate Nested Mind, or
claim customer readiness.

## Math Reasoning Contract

Math reasoning plans are operator-supplied numeric-value projections, not
financial execution, payment, subscription, record-writing, or deployment
operations. A math plan may compare bounded scenario values, compute scenario
totals, check units, list assumptions and constraints, and emit a receipt. It
must keep:

```text
execution_allowed = false
live_connector_execution_allowed = false
money_movement_allowed = false
paid_subscription_allowed = false
system_of_record_write_allowed = false
connector_mutation_allowed = false
external_submission_allowed = false
public_post_allowed = false
deployment_allowed = false
memory_write_allowed = false
```

The public preview route is
`/api/v1/personal-assistant/math/reasoning/preview`. It accepts bounded
operator-supplied numeric values only. It does not move money, change paid
subscriptions, write systems of record, mutate connectors, submit externally,
post publicly, deploy services, write memory, serialize raw private payloads or
secrets, activate Nested Mind, or claim customer readiness.

## Schedule Planning Contract

Schedule planning plans are operator-supplied time-window and work-item
projections, not calendar, task-system, messaging, record-writing, payment, or
deployment operations. A planning preview may assign bounded work items into
bounded time windows, compute capacity remaining, list assumptions and
constraints, and emit a receipt. It must keep:

```text
execution_allowed = false
live_connector_execution_allowed = false
calendar_write_allowed = false
task_write_allowed = false
invite_allowed = false
message_person_allowed = false
system_of_record_write_allowed = false
connector_mutation_allowed = false
external_submission_allowed = false
public_post_allowed = false
money_movement_allowed = false
deployment_allowed = false
memory_write_allowed = false
```

The public preview route is
`/api/v1/personal-assistant/planning/schedule/preview`. It accepts bounded
operator-supplied time windows and work items only. It does not create, move,
or cancel calendar events, write tasks, invite or message people, mutate
connectors, write systems of record, submit externally, post publicly, move
money, deploy services, write memory, serialize raw private payloads or
secrets, activate Nested Mind, or claim customer readiness.

## Operator Console Lane-Status Contract

The operator console is a read-only foundation status surface. It may aggregate
assistant lane evidence into one read model for operator review, but it does
not execute skills, call connectors, write memory, grant approval, or promote
customer readiness. The console exposes:

```text
lane_id
stage
state
route_refs
schema_refs
validator_refs
execution_allowed = false
live_connector_execution_allowed = false
connector_mutation_allowed = false
external_effect_allowed = false
customer_readiness_claim_allowed = false
nested_mind_live_activation_allowed = false
receipt_required = true
```

The public console routes are:

```text
/api/v1/console/personal-assistant
/api/v1/console/personal-assistant/view
```

They render the lane inventory, approval queue, receipt viewer, memory
candidates, TeamOps plans, and skill status as escaped read-model data only.
The console validator rejects lane-count drift, missing schema or validator
evidence, runtime lane routes without route refs, raw private payload fields,
secret-like values, and any lane status that claims execution, connector,
external-effect, customer-readiness, or live Nested Mind authority.

## Skill Readiness Catalog Contract

The skill readiness catalog is a no-effect evidence artifact that binds every
registered skill to a known foundation readiness lane, authority coverage
record, approval posture, and capability reference. It is designed for operator
review and future console composition; it is not a skill executor, approval
grant, connector proof, customer-readiness claim, or production-readiness claim.

The catalog exposes:

```text
skill_id
group
mode
risk_level
readiness_lane_id
readiness_lane_state
approval_policy_ref
requires_approval
p4_p5_approval_guarded
foundation_only
execution_enabled = false
authority_covered
receipt_required
uao_required
capability_refs
readiness_bound
```

The catalog validator rejects missing lane bindings, unsolved lane state,
authority coverage drift, executable skill drift, P4/P5 approval drift, effect
boundary overclaim, secret-shaped values, and customer or production readiness
claims.

## Dry-Run Packet Contract

The dry-run packet is a no-effect replay artifact that binds one representative
inbox, task, calendar-conflict, draft-response, approval, no-send, and memory
candidate request across intake, WHQR binding, skill routing, read-only preview,
calendar-conflict reasoning, task-intake projection, draft preview, explicit P4
approval gating, blocked external-send wait state, memory observation review,
receipt replay, and terminal foundation closure. It is a workflow proof, not an
executor.

It must keep:

```text
execution_authority_granted = false
live_connector_execution_allowed = false
connector_mutation_allowed = false
external_effect_allowed = false
external_send_allowed = false
mailbox_mutation_allowed = false
calendar_write_allowed = false
task_write_allowed = false
system_of_record_write_allowed = false
memory_write_allowed = false
memory_admission_allowed = false
deployment_mutation_allowed = false
customer_ready_claim_allowed = false
live_nested_mind_activation_allowed = false
```

The packet records source artifacts as refs, SHA-256 digests, schema refs, and
serialized lengths only. It validates acyclic stage topology, no dangling
predecessors, no dangling source or stage bindings, approval gates before P4/P5
paths, source artifact schema refs against their checked-in source payloads,
source artifact digests against current checked-in refs using the newline-stable
text-source digest, stage-level `execution_allowed = false`, and absence of
secret-shaped values. The dry-run packet binds runtime-boundary evidence
directly and does not bind the aggregate foundation closure packet, so the
aggregate closure can consume dry-run evidence without forming a causal proof
cycle.

The skill registry may declare future approval-gated effect models, but the
dry-run packet must not execute them or convert them into runtime authority.

## Foundation Closure Packet Contract

The foundation closure packet is the aggregate no-effect evidence packet. It
binds the foundation evidence receipt, readiness index, coherence ledger,
authority coverage receipt, capsule alignment receipt, policy matrix receipt,
runtime boundary receipt, skill readiness catalog, and dry-run packet. It
requires all nine sources to be bound, schema-versioned, `SolvedVerified`,
closed by their declared closure field, no-effect, non-authoritative, and free
of secret-shaped values.

The closure packet remains non-terminal. It does not grant execution authority,
live connector execution, connector mutation, external effects, system-of-record
writes, memory writes, deployment mutation, customer readiness, production
readiness, live Nested Mind activation, or terminal closure.

The closure validator also compares every recorded source receipt digest to the
current checked-in source ref using a newline-stable text-source digest and
validates each source receipt against its recorded schema ref. Digest mismatch,
schema mismatch, missing source or schema refs, or refs that escape the
repository fail validation even when the packet schema is otherwise well formed.

## Integration Position

This layer composes existing certified capabilities. It does not reimplement live Gmail, calendar, GitHub, filesystem, deployment, payment, or Nested Mind execution. Future PRs can bind each skill lane to existing capability packs through UAO after approval and receipt evidence is present.

## Verification

Required local gates for this foundation layer:

```powershell
python scripts/validate_personal_assistant_skill_registry.py
python scripts/validate_personal_assistant_approval_matrix.py
python scripts/validate_personal_assistant_approval_queue.py
python scripts/validate_personal_assistant_memory_observation.py
python scripts/validate_personal_assistant_memory_review.py
python scripts/validate_personal_assistant_teamops_projection.py
python scripts/validate_personal_assistant_github_codex_projection.py
python scripts/validate_personal_assistant_research_projection.py
python scripts/validate_personal_assistant_math_projection.py
python scripts/validate_personal_assistant_planning_projection.py
python scripts/collect_personal_assistant_skill_readiness_catalog.py
python scripts/validate_personal_assistant_skill_readiness_catalog.py --require-closed
python scripts/collect_personal_assistant_dry_run_packet.py --output .change_assurance/personal_assistant_dry_run_packet.json
python scripts/validate_personal_assistant_dry_run_packet.py --packet .change_assurance/personal_assistant_dry_run_packet.json --require-closed
python scripts/collect_personal_assistant_foundation_closure_packet.py --output .change_assurance/personal_assistant_foundation_closure_packet.json
python scripts/validate_personal_assistant_foundation_closure_packet.py --packet .change_assurance/personal_assistant_foundation_closure_packet.json --require-closed
python scripts/validate_personal_assistant_read_only_projection.py
python scripts/validate_personal_assistant_draft_projection.py
python scripts/validate_personal_assistant_approval_decision.py
python scripts/validate_personal_assistant_console_read_model.py
python scripts/validate_personal_assistant_receipt.py
python scripts/validate_personal_assistant_receipt.py --receipt examples/personal_assistant_receipt_math_reasoning.json
python -m pytest tests/test_personal_assistant_skill_registry.py tests/test_personal_assistant_runtime_skill_registry.py tests/test_personal_assistant_approval.py tests/test_personal_assistant_approval_queue.py tests/test_validate_personal_assistant_approval_decision.py tests/test_personal_assistant_receipts.py tests/test_personal_assistant_memory.py tests/test_personal_assistant_memory_runtime.py tests/test_validate_personal_assistant_memory_review.py tests/test_validate_personal_assistant_teamops_projection.py tests/test_validate_personal_assistant_github_codex_projection.py tests/test_validate_personal_assistant_research_projection.py tests/test_validate_personal_assistant_math_projection.py tests/test_validate_personal_assistant_planning_projection.py tests/test_collect_personal_assistant_skill_readiness_catalog.py tests/test_validate_personal_assistant_skill_readiness_catalog.py tests/test_collect_personal_assistant_dry_run_packet.py tests/test_validate_personal_assistant_dry_run_packet.py tests/test_personal_assistant_teamops.py tests/test_gateway/test_personal_assistant_public_routes.py -q
python scripts/validate_schemas.py
python scripts/validate_protocol_manifest.py
python scripts/validate_public_repository_surface.py
python scripts/validate_release_status.py
git diff --check
```

Full workspace governance preflight remains required before terminal closure claims.
