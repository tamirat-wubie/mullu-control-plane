# Personal Assistant MVP Roadmap

Purpose: stage the personal-assistant capability layer into reversible, evidence-backed PRs.
Governance scope: Foundation Mode delivery sequencing, no live connector overreach, approval-gated escalation, receipt continuity, and memory staging.
Dependencies: personal-assistant schemas, policies, validators, capability pack, UAO, WHQR, existing communication capability pack, TeamOps shared-inbox gates, and Nested Mind staging validators.
Invariants: each PR has one bounded authority increase; live execution and public/customer claims require later evidence.

## Build Order

| PR | Scope | Explicit non-goals |
| --- | --- | --- |
| 1 | Architecture, schemas, policies, examples, capability pack, validators, tests | No runtime execution |
| 2 | Skill registry loader and validator integration | No live connector calls |
| 3 | Request intake and WHQR missing-binding emission | No execution |
| 4 | Read-only inbox and calendar summaries | No send, delete, archive, create, move, cancel, invite |
| 5 | Draft-only assistant artifacts | No external communication |
| 6 | Approval queue read/preview projection | No approval auto-grant; no execution after approval |
| 7 | Memory observations | No raw chat-log storage; no live Nested Mind activation |
| 8 | TeamOps shared inbox planning and handoff | No mailbox mutation without approval evidence |
| 9 | GitHub and Codex review planning | No GitHub calls, repository reads, PR mutation, branch push, issue creation, review submission, merge, or deployment |
| 10 | Research source comparison and citation pack | No live web search, source contact, external submission, public posting, paid subscription, raw source body storage, or memory write |
| 11 | User-facing assistant console | No customer/SaaS readiness claim |

## PR 1 Acceptance Criteria

1. Documentation names the assistant as a governed user-intent interpreter.
2. Schemas validate request, skill, plan, approval, receipt, and memory-observation records.
3. Skill policy and approval matrix preserve P0-P5 boundaries.
4. Capability pack grants planning and governance authority only.
5. Examples cover inbox summary, calendar brief, registry, approval packet, and draft-only receipt.
6. Validators reject read-only mutation, draft-only send, missing P4/P5 approval, receipt under-reporting, raw private payloads, secret-like values, and under-specified memory observations.
7. Tests prove all required boundary cases.

## Future Authority Ladder

```text
schema witness
-> registry witness
-> intake witness
-> read-only connector witness
-> draft witness
-> approval witness
-> internal write witness
-> external communication witness
-> TeamOps shared-inbox witness
-> research citation witness
-> console witness
```

No stage may skip UAO admission, approval classification, receipt emission, and rollback or compensation planning where effect-bearing action exists.

## PR 6 Acceptance Criteria

1. Approval queue projections validate against `schemas/personal_assistant_approval_queue.schema.json`.
2. Queue records embed schema-valid approval packets and personal-assistant receipts.
3. Pending, approved, rejected, and revised decisions remain evidence records only.
4. Public routes expose read/preview projections without persistence claims or connector mutation.
5. `approval_is_execution`, `execution_allowed`, `external_send_allowed`, and `connector_mutation_allowed` remain false.
6. Raw private connector payloads, raw message bodies, credentials, tokens, and secret-like values are rejected.
7. Proof coverage classifies approval queue routes under the assistant planning surface.

## PR 6 Decision Evidence Acceptance Criteria

1. Approval decisions validate against `schemas/personal_assistant_approval_decision.schema.json`.
2. Approved, rejected, revised, and expired decisions embed schema-valid approval packets and receipts.
3. Approved and revised decisions remain `deferred` evidence records; they do not execute sends, invites, writes, connector mutation, or memory writes.
4. Rejected and expired decisions emit blocked receipts and record the non-actions taken.
5. `approval_decision_records_allowed` is true, while execution, external send, connector mutation, task/calendar writes, system-of-record writes, deployment mutation, customer-readiness claims, and live Nested Mind activation remain false.
6. Raw private connector payloads, raw message bodies, credentials, tokens, and secret-like values are rejected.
7. Proof coverage classifies approval decision evidence under the assistant planning surface.

## PR 4 Evidence Acceptance Criteria

1. Redacted inbox/calendar summaries validate against `schemas/personal_assistant_read_only_projection.schema.json`.
2. Projection envelopes embed schema-valid personal-assistant receipts.
3. `execution_allowed`, `live_connector_execution_allowed`, `mailbox_read_allowed`, `mailbox_mutation_allowed`, `calendar_write_allowed`, `external_send_allowed`, and `connector_mutation_allowed` remain false.
4. The source is explicitly `operator_supplied_redacted_projection`; the contract does not claim live provider reads.
5. Raw private connector payloads, raw message bodies, credentials, tokens, and secret-like values are rejected.
6. Assurance remains Foundation Mode only, with no live execution or customer-readiness claim.

## PR 5 Evidence Acceptance Criteria

1. Email, calendar, and task drafts validate against `schemas/personal_assistant_draft_projection.schema.json`.
2. Draft projection envelopes embed schema-valid personal-assistant receipts for each draft artifact.
3. `draft_preparation_allowed` is true, while `execution_allowed`, `live_connector_execution_allowed`, `external_send_allowed`, `calendar_write_allowed`, `task_write_allowed`, `memory_write_allowed`, `connector_mutation_allowed`, and `system_of_record_write_allowed` remain false.
4. Drafts require approval before any send, invite, connector mutation, task write, or system-of-record write.
5. Raw private connector payloads, raw message bodies, credentials, tokens, and secret-like values are rejected.
6. Assurance remains Foundation Mode only, with no live execution or customer-readiness claim.

## PR 7 Acceptance Criteria

1. Memory observation records validate against `schemas/personal_assistant_memory_observation.schema.json`.
2. Candidate ledger projections validate against `schemas/personal_assistant_memory_read_model.schema.json`.
3. Memory review evidence validates against `schemas/personal_assistant_memory_review.schema.json`.
4. The runtime prepares observation candidates with source, confidence, scope, mutability, evidence refs, receipt refs, sensitivity, retention policy, and Nested Mind staging status.
5. Review decisions cover `kept_for_operator_review`, `rejected`, `revision_requested`, `deferred`, and `expired` without admitting candidates into live memory.
6. Public routes expose empty read-model, stateless candidate preview, and stateless review preview projections only.
7. `live_memory_write_allowed`, `memory_admission_allowed`, `nested_mind_live_activation_allowed`, `raw_private_payload_storage_allowed`, `secret_value_storage_allowed`, and `candidate_only` remain false/false/false/false/false/true as applicable.
8. Raw chat logs, raw connector payloads, credentials, tokens, private keys, and secret-like values are rejected.
9. Receipts record memory candidate creation or review plus actions not taken: live memory write, memory admission, Nested Mind activation, raw chat-log storage, raw connector payload storage, and system-of-record mutation.
10. Proof coverage classifies memory observation and review routes under the assistant planning surface.

## PR 8 Acceptance Criteria

1. TeamOps shared-inbox projections validate against `schemas/personal_assistant_teamops_projection.schema.json`.
2. Projection envelopes embed schema-valid TeamOps operator handoff packets and personal-assistant receipts.
3. Public routes expose stateless TeamOps shared-inbox plan previews only.
4. `execution_allowed`, `live_connector_execution_allowed`, `live_probe_execution_allowed`, `mailbox_read_allowed`, `mailbox_mutation_allowed`, `draft_creation_allowed`, `external_send_allowed`, `connector_mutation_allowed`, `system_of_record_write_allowed`, `deployment_mutation_allowed`, and `nested_mind_live_activation_allowed` remain false.
5. Ready live-probe evidence is treated as handoff readiness only; no live probe, Gmail call, shared-inbox read, draft, send, archive, delete, label, or provider mutation is performed.
6. Raw private connector payloads, raw message bodies, credentials, tokens, private keys, and secret-like values are rejected.
7. Receipts record handoff planning and live-probe gate classification plus actions not taken: Gmail not called, shared inbox not read, email not drafted, email not sent, mailbox not mutated, provider configuration not mutated, secret values not serialized, and live probe not executed.
8. Proof coverage classifies TeamOps shared-inbox plan previews under the assistant planning surface.

## PR 9 Acceptance Criteria

1. GitHub and Codex review projections validate against `schemas/personal_assistant_github_codex_projection.schema.json`.
2. Projection envelopes embed schema-valid personal-assistant receipts.
3. Public routes expose stateless GitHub/Codex review previews only.
4. `execution_allowed`, `live_connector_execution_allowed`, `github_call_allowed`, `repository_read_allowed`, `repository_mutation_allowed`, `pull_request_mutation_allowed`, `branch_push_allowed`, `issue_creation_allowed`, `review_submission_allowed`, `deployment_mutation_allowed`, `system_of_record_write_allowed`, and `nested_mind_live_activation_allowed` remain false.
5. Ready evidence is treated as review readiness only; no GitHub call, repository read, pull-request open, merge, branch push, issue creation, review submission, or deployment is performed.
6. Raw diffs, raw connector payloads, raw repository contents, credentials, tokens, private keys, and secret-like values are rejected.
7. Receipts record review planning and Codex instruction drafting plus actions not taken: GitHub not called, pull request not opened, pull request not merged, branch not pushed, issue not created, review not submitted, deployment not started, repository not mutated, secret values not serialized, and raw diff not serialized.
8. Proof coverage classifies GitHub/Codex review previews under the assistant planning surface.

## PR 10 Acceptance Criteria

1. Research source-compare projections validate against `schemas/personal_assistant_research_projection.schema.json`.
2. Projection envelopes embed schema-valid personal-assistant receipts.
3. Public routes expose stateless research source-compare previews only.
4. `execution_allowed`, `live_connector_execution_allowed`, `web_search_allowed`, `web_search_performed`, `source_contact_allowed`, `external_submission_allowed`, `public_post_allowed`, `paid_subscription_allowed`, `system_of_record_write_allowed`, `memory_write_allowed`, and `nested_mind_live_activation_allowed` remain false.
5. Ready evidence is treated as citation-backed comparison readiness only; no web search, source contact, external submission, public post, paid subscription, memory write, or system-of-record write is performed.
6. Raw source bodies, raw connector payloads, credentials, tokens, private keys, and secret-like values are rejected.
7. Receipts record source comparison and citation-pack projection plus actions not taken: web search not performed, source not contacted, external submission not performed, public post not created, paid subscription not started, raw source body not serialized, secret values not serialized, memory not written, and Nested Mind not activated.
8. Proof coverage classifies research source-compare previews under the assistant planning surface.

## Handoff Risks

| Boundary | Risk | Control |
| --- | --- | --- |
| Product to engineering | Assistant becomes broad instead of governed | Keep PR scope one lane at a time |
| Design to engineering | Chat surface hides approval gates | Approval packet and receipt viewer are required UI surfaces later |
| Engineering to operations | Live connector read/write overclaim | Treat live provider calls as `AwaitingEvidence` until witness exists |
| Engineering to memory | Raw conversation storage | Store only typed memory observations with receipt refs |
| Engineering to public surface | Customer readiness overclaim | Keep Foundation Mode language until named witnesses exist |

## Verification Ladder

PR 1 should run static validators and tests only. Later PRs add runtime validators after each lane has capability evidence.
