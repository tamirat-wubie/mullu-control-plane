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
python scripts/validate_personal_assistant_read_only_projection.py
python scripts/validate_personal_assistant_draft_projection.py
python scripts/validate_personal_assistant_approval_decision.py
python scripts/validate_personal_assistant_console_read_model.py
python scripts/validate_personal_assistant_receipt.py
python scripts/validate_personal_assistant_receipt.py --receipt examples/personal_assistant_receipt_math_reasoning.json
python -m pytest tests/test_personal_assistant_skill_registry.py tests/test_personal_assistant_runtime_skill_registry.py tests/test_personal_assistant_approval.py tests/test_personal_assistant_approval_queue.py tests/test_validate_personal_assistant_approval_decision.py tests/test_personal_assistant_receipts.py tests/test_personal_assistant_memory.py tests/test_personal_assistant_memory_runtime.py tests/test_validate_personal_assistant_memory_review.py tests/test_gateway/test_personal_assistant_public_routes.py -q
python scripts/validate_schemas.py
python scripts/validate_protocol_manifest.py
python scripts/validate_public_repository_surface.py
python scripts/validate_release_status.py
git diff --check
```

Full workspace governance preflight remains required before terminal closure claims.
