<!--
Purpose: define the read-only persistence and read-model binding plan that follows the Agentic Service Harness readiness map.
Governance scope: planning-only binding for tenant, project, repository, agent run, approval, sandbox, receipt, evidence, and loop status surfaces.
Dependencies: MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md, MULLUSI_AGENTIC_SERVICE_HARNESS_LIVE_TASK_RUN_PRODUCER_EVIDENCE.md, schemas/agentic_service_harness.schema.json, schemas/agentic_service_harness_live_producer_admission_gate.schema.json, schemas/agentic_service_harness_live_producer_witness_requirements.schema.json, schemas/agentic_service_harness_live_producer_operator_approval_request.schema.json, schemas/agentic_service_harness_live_producer_operator_response_witness.schema.json, schemas/agentic_service_harness_live_producer_operator_decision_evidence.schema.json, schemas/agentic_service_harness_live_producer_operator_decision_record.schema.json, gateway/agentic_service_harness_live_task_run_producer.py, gateway/agentic_service_harness_live_producer_admission.py, gateway/agentic_service_harness_live_producer_witness_requirements.py, gateway/agentic_service_harness_live_producer_operator_approval.py, gateway/agentic_service_harness_live_producer_operator_response.py, gateway/agentic_service_harness_live_producer_operator_decision.py, gateway/agentic_service_harness_live_producer_operator_decision_record.py, scripts/validate_agentic_service_harness_live_task_run_producer_rehearsal.py, scripts/validate_agentic_service_harness_live_producer_admission_gate.py, scripts/validate_agentic_service_harness_live_producer_witness_requirements.py, scripts/validate_agentic_service_harness_live_producer_operator_approval_request.py, scripts/validate_agentic_service_harness_live_producer_operator_response_witness.py, scripts/validate_agentic_service_harness_live_producer_operator_decision_evidence.py, scripts/validate_agentic_service_harness_live_producer_operator_decision_record.py, docs/maps/MULLUSI_ASK_TO_RECEIPT_FLOW_MAP.md, docs/maps/MULLUSI_EVIDENCE_RECEIPT_MAP.md, docs/FOUNDATION_MODE.md.
Invariants: planning_only=true; ui_created=false; mutation_endpoints_admitted=false; external_adapter_integrated=false; default_high_risk_authority=false.
-->

# Mullusi Agentic Service Harness Read Model Binding Plan

## Objective

Bind the merged Agentic Service Harness contract to a read-only persistence and read-model plan before any dashboard, mutation endpoint, external adapter, or live automation work begins.

Solver outcome: `SolvedVerified` for the planning boundary, read-model schema, fixture projection, integrity validator, local persistence rehearsal, read-only route design proof, static read-only status route, runtime source binding, runtime-local read-model producer, live task/run producer evidence contract, local evidence fixture, local producer rehearsal, read-only rehearsal status projection, blocked live producer admission gate, live producer witness requirements packet, operator approval request packet, operator response witness packet, operator decision evidence boundary, operator decision record intake boundary, operator decision value absence witness, operator decision pending status, operator decision value intake preflight, generic continuation rejection witness, operator decision value request packet, operator decision value template packet, operator decision value collection gate, operator decision value record path, explicit operator approval value record, effect receipt preflight, external adapter evidence preflight, and secret handoff preflight. Live task/run producer implementation, actual effect receipt observation, actual external adapter evidence, actual secret handoff, and rollback proof remain `AwaitingEvidence`.

## Scope

This artifact is a planning-only bridge between the contract schema and the future product surface. It defines how the first harness phase should persist and project the following symbols without granting write authority:

| Symbol | Binding decision | Read-model purpose |
| --- | --- | --- |
| `User` | Persist as identity projection only; no secret fields. | Show actor, memberships, and default harness role. |
| `Organization` | Persist as tenant boundary projection. | Scope users, projects, approvals, and receipt visibility. |
| `Project` | Persist as the harness work container. | Group repositories, agent tasks, runs, receipts, and loop status. |
| `RepositoryConnection` | Persist as redacted provider binding. | Show provider, repository slug, default branch, permission scope, and credential binding ref only. |
| `AgentTask` | Persist as immutable task request record. | Preserve objective, requested mode, risk, evidence refs, and required approvals. |
| `AgentAdapter` | Persist as contract-only adapter descriptor. | Show allowed modes, authority class, sandbox requirement, and receipt schema ref. |
| `WorkspaceSandbox` | Persist as sandbox policy projection. | Show command allowlist, path allowlist, timeout, network policy, redaction, and cleanup receipt ref. |
| `AgentRun` | Persist as run lifecycle projection. | Show status, adapter, sandbox, approval gates, receipt, evidence bundle, and result summary refs. |
| `ApprovalGate` | Persist as approval requirement projection. | Show required role, risk, action class, pending/denied/blocked state, and evidence refs. |
| `AgentRunReceipt` | Persist as non-terminal receipt projection. | Show request ref, selected agent ref, mode, files changed, commands, tests, policy result, risk, evidence refs, and next action. |
| `EvidenceBundle` | Persist as redacted reference bundle. | Show command log refs, test log refs, diff refs, policy refs, and redaction policy. |
| `ResultSummary` | Persist as user-visible read model. | Show outcome, status text, changed-file count, test status, blockers, and next action. |
| `PermissionModel` | Persist as tenant/project policy snapshot. | Show roles, action classes, blocked high-risk actions, and false high-risk authority flags. |
| `Receipt` | Bind to the existing receipt taxonomy. | Connect task, policy, budget, approval, worker, closure, denial, and final-user receipts. |
| `LoopStatus` | Reuse existing loop read model. | Show loop status without creating a terminal closure claim. |

## Source Contracts

| Source | Role |
| --- | --- |
| `schemas/agentic_service_harness.schema.json` | Canonical first contract for harness objects and scenario examples. |
| `MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md` | Source readiness classification and smallest-next-PR decisions. |
| `docs/maps/MULLUSI_ASK_TO_RECEIPT_FLOW_MAP.md` | Existing ask-to-receipt state and receipt chain. |
| `docs/maps/MULLUSI_EVIDENCE_RECEIPT_MAP.md` | Existing evidence and receipt taxonomy. |
| `docs/FOUNDATION_MODE.md` | Foundation Mode authority boundary. |
| `MULLUSI_AGENTIC_SERVICE_HARNESS_LIVE_TASK_RUN_PRODUCER_EVIDENCE.md` | Evidence boundary for future live task/run producer admission. |
| `schemas/agentic_service_harness_live_task_run_producer_evidence.schema.json` | Schema for the local live-producer evidence fixture. |
| `examples/agentic_service_harness_live_task_run_producer_evidence.local.json` | Local fixture proving the evidence surfaces without live execution. |
| `schemas/agentic_service_harness_live_producer_admission_gate.schema.json` | Schema for the blocked live producer admission gate. |
| `examples/agentic_service_harness_live_producer_admission_gate.local.json` | Local fixture proving live producer admission remains blocked. |
| `schemas/agentic_service_harness_live_producer_witness_requirements.schema.json` | Schema for required live producer witnesses that remain `AwaitingEvidence`. |
| `examples/agentic_service_harness_live_producer_witness_requirements.local.json` | Local fixture proving required witnesses grant no authority. |
| `schemas/agentic_service_harness_live_producer_operator_approval_request.schema.json` | Schema for the operator approval request that remains uncollected and non-authorizing. |
| `examples/agentic_service_harness_live_producer_operator_approval_request.local.json` | Local fixture proving the operator request grants no live authority. |
| `schemas/agentic_service_harness_live_producer_operator_response_witness.schema.json` | Schema for the operator response witness that records missing explicit response evidence. |
| `examples/agentic_service_harness_live_producer_operator_response_witness.local.json` | Local fixture proving missing operator response evidence grants no live authority. |
| `schemas/agentic_service_harness_live_producer_operator_decision_evidence.schema.json` | Schema for the decision evidence boundary that rejects generic continuation as approval. |
| `examples/agentic_service_harness_live_producer_operator_decision_evidence.local.json` | Local fixture proving generic continuation grants no live authority. |
| `schemas/agentic_service_harness_live_producer_operator_decision_record.schema.json` | Schema for the pending operator decision record intake envelope. |
| `examples/agentic_service_harness_live_producer_operator_decision_record.local.json` | Local fixture proving generic continuation records no decision. |
| `schemas/agentic_service_harness_live_producer_operator_decision_value_absence.schema.json` | Schema for the witness that no explicit decision value has been provided. |
| `examples/agentic_service_harness_live_producer_operator_decision_value_absence.local.json` | Local fixture proving generic continuation is not an approval or rejection value. |
| `schemas/agentic_service_harness_live_producer_operator_decision_pending_status.schema.json` | Schema for the blocked pending-status projection. |
| `examples/agentic_service_harness_live_producer_operator_decision_pending_status.local.json` | Local fixture proving the decision gate remains blocked. |
| `schemas/agentic_service_harness_live_producer_operator_decision_value_intake_preflight.schema.json` | Schema for the future explicit decision value intake preflight. |
| `examples/agentic_service_harness_live_producer_operator_decision_value_intake_preflight.local.json` | Local fixture proving no value is collected by the preflight. |
| `schemas/agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection.schema.json` | Schema for the generic continuation rejection witness. |
| `examples/agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection.local.json` | Local fixture proving generic continuation is rejected as a non-decision input. |
| `schemas/agentic_service_harness_live_producer_operator_decision_value_request.schema.json` | Schema for the explicit operator decision value request packet. |
| `examples/agentic_service_harness_live_producer_operator_decision_value_request.local.json` | Local fixture asking for explicit approval or rejection without collecting a value. |
| `schemas/agentic_service_harness_live_producer_operator_decision_value_template.schema.json` | Schema for template-only explicit approval/rejection value shapes. |
| `examples/agentic_service_harness_live_producer_operator_decision_value_template.local.json` | Local fixture proving templates are not accepted as values and grant no authority. |
| `schemas/agentic_service_harness_live_producer_operator_decision_value_collection_gate.schema.json` | Schema for the blocked collection gate after template publication. |
| `examples/agentic_service_harness_live_producer_operator_decision_value_collection_gate.local.json` | Local fixture proving no collection route is admitted before an actual value exists. |
| `schemas/agentic_service_harness_live_producer_operator_decision_value_record_path.schema.json` | Schema for the future value-record path that remains blocked before actual operator value presence. |
| `examples/agentic_service_harness_live_producer_operator_decision_value_record_path.local.json` | Local fixture proving no operator decision value record is created before an actual value exists. |
| `schemas/agentic_service_harness_live_producer_operator_decision_value_record.schema.json` | Schema for the explicit operator decision value record. |
| `examples/agentic_service_harness_live_producer_operator_decision_value_record.local.json` | Local fixture recording the explicit operator approval value while granting no live authority. |
| `schemas/agentic_service_harness_live_producer_effect_receipt_preflight.schema.json` | Schema for the blocked effect receipt preflight after explicit operator approval. |
| `examples/agentic_service_harness_live_producer_effect_receipt_preflight.local.json` | Local fixture proving the effect receipt remains `AwaitingEvidence` until an admitted live side effect exists. |
| `schemas/agentic_service_harness_live_producer_external_adapter_evidence_preflight.schema.json` | Schema for the blocked external adapter evidence preflight. |
| `examples/agentic_service_harness_live_producer_external_adapter_evidence_preflight.local.json` | Local fixture proving adapter evidence remains `AwaitingEvidence` until redacted provider, adapter, scope, egress, redaction, and effect-receipt linkage evidence exists. |
| `schemas/agentic_service_harness_live_producer_secret_handoff_preflight.schema.json` | Schema for the blocked secret handoff preflight. |
| `examples/agentic_service_harness_live_producer_secret_handoff_preflight.local.json` | Local fixture proving secret handoff remains `AwaitingEvidence` and contains no credential values. |

## Read Model Bindings

| Read model | Required refs | Forbidden fields |
| --- | --- | --- |
| `HarnessAccountReadModel` | `user_id`, `organization_memberships`, `default_role`, `identity_provider_ref` | access tokens, passwords, private keys, raw provider credentials |
| `HarnessProjectReadModel` | `project_id`, `organization_id`, `tenant_id`, `repository_connection_ids`, `agent_run_ids`, `receipt_refs`, `loop_status_ref` | raw repository credentials, unscoped receipt contents |
| `HarnessRepositoryReadModel` | `connection_id`, `project_id`, `provider`, `repository_slug`, `default_branch`, `permission_scope`, `credential_binding_ref` | secret values, installation tokens, webhook secrets |
| `HarnessRunReadModel` | `run_id`, `task_id`, `adapter_id`, `sandbox_id`, `mode`, `status`, `approval_gate_ids`, `receipt_id`, `evidence_bundle_id`, `result_summary_id` | executable command bodies that are not redacted or referenced |
| `HarnessApprovalReadModel` | `gate_id`, `run_id`, `action_class`, `risk_level`, `status`, `approver_role_required`, `evidence_refs` | self-approval, implicit approval, external-effect permission |
| `HarnessReceiptReadModel` | `receipt_id`, `run_id`, `task_request_ref`, `selected_agent_ref`, `files_changed`, `commands_run`, `tests_run`, `policy_result`, `risk_level`, `evidence_refs`, `next_action` | terminal closure claim, raw secret values, unredacted stdout or stderr |
| `HarnessEvidenceReadModel` | `bundle_id`, `run_id`, `command_log_refs`, `test_log_refs`, `diff_refs`, `policy_refs`, `redaction_policy` | inline secrets, raw credentials, unrestricted diff contents |

## State Machine

The first read-model lifecycle is bounded to non-mutating states:

```text
planned
-> ready_read_only
-> ready_dry_run
-> awaiting_approval
-> blocked
```

No state in this plan performs branch writes, opens pull requests, merges, deploys, mutates DNS, mutates secrets, sends email, moves money, or runs destructive operations.

## Authority Boundary

| Action class | Read model behavior | Authority result |
| --- | --- | --- |
| `read_only` | Display status and receipts. | Allowed as read projection. |
| `dry_run` | Display simulated plan, test intent, and blocked effects. | Allowed as read projection. |
| `write_to_branch` | Display approval requirement and blocked-until-approved state. | AwaitingEvidence. |
| `open_pr` | Display approval requirement and blocked-until-approved state. | AwaitingEvidence. |
| `blocked_high_risk` | Display denial and required evidence. | GovernanceBlocked. |

High-risk actions remain blocked by default:

```text
merge=false
deploy=false
dns_mutation=false
secret_mutation=false
destructive_operation=false
```

## Evidence And Receipt Binding

The harness read model must link to existing receipt classes instead of inventing hidden success paths:

```text
MessageReceipt
-> IdentityReceipt
-> TenantBindingReceipt
-> InterpretationReceipt
-> PlanReceipt
-> PolicyReceipt
-> BudgetReceipt
-> ApprovalRequestReceipt when required
-> ApprovalReceipt when approved or denied
-> WorkerReceipt only for admitted dry-run or later approved action
-> ClosureReceipt or DenialReceipt
-> FinalUserReceipt
```

`AgentRunReceipt` is not a terminal closure certificate. It is a non-terminal read projection that points to evidence refs and next action.

## Persistence Plan

The smallest acceptable persistence plan is append-friendly and read-first:

1. Store identity, organization, project, repository, task, run, approval, receipt, evidence, and result-summary records as explicit typed records.
2. Keep mutable lifecycle updates append-only through new receipt refs instead of overwriting prior causal evidence.
3. Store provider credentials only through redacted binding refs.
4. Store command output, test logs, and diffs as refs or hashes until a separate redaction policy is validated.
5. Require tenant and project scope on every read model.
6. Treat missing tenant, missing project, missing receipt, or stale evidence as `AwaitingEvidence`.

## Non-Goals

This plan does not create:

1. Dashboard UI.
2. Mutation endpoints.
3. GitHub branch creation.
4. Pull request creation.
5. Claude Code integration.
6. OpenClaw integration.
7. Email sending.
8. Deployment approval.
9. DNS mutation.
10. Secret mutation.
11. Billing.
12. Marketplace or multi-agent marketplace behavior.

## Smallest Next PR Sequence

| Order | PR | Scope | Validator target |
| --- | --- | --- | --- |
| 1 | `docs(harness): add read-model binding plan` | This planning artifact and validator only. | `scripts/validate_agentic_service_harness_read_model_binding_plan.py` |
| 2 | `feat(harness): add read-only harness read-model schemas` | JSON schemas for account, project, repository, run, approval, receipt, evidence, and result summary read models. No endpoints. | Closed by `scripts/validate_agentic_service_harness_read_models.py` |
| 3 | `feat(harness): add read-only harness fixture projections` | Examples that project existing contract examples into read-only read models. No persistence adapter. | Closed by projection and integrity validators |
| 4 | `feat(harness): add local read-only persistence rehearsal` | Local file or in-memory rehearsal only, with append-only receipt refs. No API routes. | Closed by `scripts/validate_agentic_service_harness_read_model_persistence.py` |
| 5 | `feat(harness): add read-only status route design` | Route design document only. No route implementation. | Closed by `scripts/validate_agentic_service_harness_read_only_status_route_design.py` |
| 6 | `feat(harness): implement static read-only status route` | `GET /api/v1/harness/status` only, sourced from validated foundation read model. No UI or mutation routes. | Closed by `scripts/validate_agentic_service_harness_read_only_status_route.py` |
| 7 | `feat(harness): bind status route runtime source` | Runtime-local read-model source object bound to the route, with foundation fixture fallback. No HTTP write route. | Closed by route validator and gateway route tests |
| 8 | `feat(harness): bind runtime-local read-model producer` | Runtime-local producer projects the read-only contract fixture into the bound status source. No live adapter, task mutation, UI, or HTTP write route. | Closed by route validator and gateway route tests |
| 9 | `docs(harness): define live task/run producer evidence` | Evidence contract for future live producer admission. No live producer implementation, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_task_run_producer_evidence.py` |
| 10 | `feat(harness): add local live-producer evidence fixture` | Schema and local JSON fixture for task/run producer evidence. No producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_task_run_producer_evidence.py` and schema validation |
| 11 | `feat(harness): add local producer rehearsal` | Local dry-run report projected from the validated evidence fixture. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_task_run_producer_rehearsal.py` |
| 12 | `feat(harness): project local rehearsal status` | Read-only status route includes a bounded `producer_rehearsal` projection. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_read_only_status_route.py` and gateway route tests |
| 13 | `feat(harness): add live producer admission gate` | Blocked admission gate projects local rehearsal evidence into explicit required live-authority witnesses. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_admission_gate.py` |
| 14 | `feat(harness): add live producer witness requirements` | Requirements packet records operator approval, effect receipt, adapter evidence, secret handoff, and rollback proof as missing witnesses. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_witness_requirements.py` |
| 15 | `feat(harness): add live producer operator approval request` | Request packet asks for the operator approval witness but keeps approval uncollected, authority denied, and remaining witnesses blocked. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_approval_request.py` |
| 16 | `feat(harness): add live producer operator response witness` | Response witness packet records that no explicit operator response has been collected and keeps approval unsatisfied. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_response_witness.py` |
| 17 | `feat(harness): add live producer operator decision evidence` | Decision evidence boundary records that generic continuation does not satisfy approval. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_decision_evidence.py` |
| 18 | `feat(harness): add live producer operator decision record` | Decision record intake envelope records that generic continuation creates no approval or rejection record. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_decision_record.py` |
| 19 | `feat(harness): add live producer operator decision value absence` | Value absence witness records that no explicit approval or rejection value is present. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_decision_value_absence.py` |
| 20 | `feat(harness): add live producer operator decision pending status` | Pending status projects value absence into a blocked platform-facing decision gate. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_decision_pending_status.py` |
| 21 | `feat(harness): add live producer operator decision value intake preflight` | Intake preflight defines the required explicit approval/rejection value contract without collecting a value or granting authority. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_decision_value_intake_preflight.py` |
| 22 | `feat(harness): add generic continuation rejection witness` | Rejection witness proves generic continuation is rejected as a non-decision input. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection.py` |
| 23 | `feat(harness): add operator decision value request` | Value request packet asks for explicit approval or rejection fields without collecting a value or granting authority. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_decision_value_request.py` |
| 24 | `feat(harness): add operator decision value templates` | Template packet provides approval and rejection shapes while keeping templates non-authorizing and non-values. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_decision_value_template.py` |
| 25 | `feat(harness): add operator decision value collection gate` | Collection gate blocks route admission and value capture until an actual explicit value exists. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_decision_value_collection_gate.py` |
| 26 | `feat(harness): add operator decision value record path` | Value-record path defines the future record contract while keeping record creation blocked until an actual explicit value exists. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_decision_value_record_path.py` |
| 27 | `feat(harness): add operator decision value record` | Explicit operator approval value record satisfies only the operator approval witness while leaving live execution blocked by effect receipt, external adapter evidence, secret handoff, and rollback proof. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_operator_decision_value_record.py` |
| 28 | `feat(harness): add effect receipt preflight` | Effect receipt preflight defines admitted-action, effect-hash, reconciliation, rollback-link, and redaction requirements while keeping actual effect receipt collection blocked. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter. | Closed by `scripts/validate_agentic_service_harness_live_producer_effect_receipt_preflight.py` |
| 29 | `feat(harness): add external adapter evidence preflight` | External adapter evidence preflight defines provider identity, adapter descriptor, capability scope, egress policy, redaction proof, and effect-receipt linkage requirements while keeping actual adapter evidence blocked. No live producer execution path, UI, mutation endpoint, branch write, pull-request creation, credential serialization, network egress, or external adapter integration. | Closed by `scripts/validate_agentic_service_harness_live_producer_external_adapter_evidence_preflight.py` |
| 30 | `feat(harness): add secret handoff preflight` | Secret handoff preflight defines authority-scope, storage-boundary, redaction, rotation-policy, audit-log, and external-adapter-evidence linkage requirements while keeping actual handoff blocked. No credential reading, printing, serialization, storage, live producer execution path, UI, mutation endpoint, branch write, pull-request creation, or external adapter integration. | Closed by `scripts/validate_agentic_service_harness_live_producer_secret_handoff_preflight.py` |

## Acceptance Gates

Before implementation starts, the following must be true:

| Gate | Required state |
| --- | --- |
| Contract validation | `python scripts/validate_agentic_service_harness_contract.py --strict` passes. |
| Binding plan validation | `python scripts/validate_agentic_service_harness_read_model_binding_plan.py` passes. |
| Read-model validation | `python scripts/validate_agentic_service_harness_read_models.py` passes. |
| Projection validation | `python scripts/validate_agentic_service_harness_read_model_projections.py` passes. |
| Integrity validation | `python scripts/validate_agentic_service_harness_read_model_integrity.py` passes. |
| Persistence rehearsal | `python scripts/validate_agentic_service_harness_read_model_persistence.py` passes. |
| Route design validation | `python scripts/validate_agentic_service_harness_read_only_status_route_design.py` passes. |
| Route implementation validation | `python scripts/validate_agentic_service_harness_read_only_status_route.py` passes. |
| Live producer evidence contract | `python scripts/validate_agentic_service_harness_live_task_run_producer_evidence.py` passes. |
| Live producer evidence fixture | `examples/agentic_service_harness_live_task_run_producer_evidence.local.json` validates against `schemas/agentic_service_harness_live_task_run_producer_evidence.schema.json`. |
| Local producer rehearsal | `python scripts/validate_agentic_service_harness_live_task_run_producer_rehearsal.py` passes. |
| Rehearsal status projection | `GET /api/v1/harness/status` returns a read-only `producer_rehearsal` projection. |
| Live producer admission gate | `python scripts/validate_agentic_service_harness_live_producer_admission_gate.py` passes and returns `admission_decision=blocked`. |
| Live producer witness requirements | `python scripts/validate_agentic_service_harness_live_producer_witness_requirements.py` passes and keeps all witnesses at `AwaitingEvidence`. |
| Operator approval request | `python scripts/validate_agentic_service_harness_live_producer_operator_approval_request.py` passes and keeps approval uncollected and non-authorizing. |
| Operator response witness | `python scripts/validate_agentic_service_harness_live_producer_operator_response_witness.py` passes and keeps explicit response evidence missing and non-authorizing. |
| Operator decision evidence | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_evidence.py` passes and proves generic continuation does not satisfy approval. |
| Operator decision record | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_record.py` passes and proves generic continuation records no decision. |
| Operator decision value absence | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_absence.py` passes and proves no explicit approval or rejection value is present. |
| Operator decision pending status | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_pending_status.py` passes and proves the decision gate remains blocked pending explicit operator value. |
| Operator decision value intake preflight | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_intake_preflight.py` passes and defines the future explicit value contract without collecting a value. |
| Generic continuation rejection witness | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_generic_continuation_rejection.py` passes and proves generic continuation is rejected as a non-decision input. |
| Operator decision value request | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_request.py` passes and asks for explicit approval or rejection without collecting a value. |
| Operator decision value template | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_template.py` passes and keeps approval/rejection templates non-authorizing and non-values. |
| Operator decision value collection gate | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_collection_gate.py` passes and blocks collection route admission until an actual explicit value exists. |
| Operator decision value record path | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_record_path.py` passes and keeps future value-record creation blocked until an actual explicit value exists. |
| Operator decision value record | `python scripts/validate_agentic_service_harness_live_producer_operator_decision_value_record.py` passes and grants no live authority after recording explicit approval. |
| Effect receipt preflight | `python scripts/validate_agentic_service_harness_live_producer_effect_receipt_preflight.py` passes and keeps the actual effect receipt at `AwaitingEvidence`. |
| External adapter evidence preflight | `python scripts/validate_agentic_service_harness_live_producer_external_adapter_evidence_preflight.py` passes and keeps actual adapter evidence, credential serialization, and network egress blocked. |
| Secret handoff preflight | `python scripts/validate_agentic_service_harness_live_producer_secret_handoff_preflight.py` passes and keeps actual handoff, credential reading, credential printing, and credential serialization blocked. |
| Governance preflight | Focused workspace governance checks pass. |
| Security boundary | Secret values are not serialized; high-risk authority flags remain false. |
| UI boundary | `ui_created=false`. |
| Mutation boundary | `mutation_endpoints_admitted=false`. |
| Adapter boundary | `external_adapter_integrated=false`. |

## Status

Outcome: `SolvedVerified` for read-model schema, projection, integrity, local persistence rehearsal, read-only status route design, static route implementation, runtime source binding, runtime-local producer binding, authority-transition validation, live task/run producer evidence contract, local evidence fixture, local producer rehearsal, read-only rehearsal status projection, blocked live producer admission gate, live producer witness requirements packet, operator approval request packet, operator response witness packet, operator decision evidence boundary, operator decision record intake boundary, operator decision value absence witness, operator decision pending status, operator decision value intake preflight, generic continuation rejection witness, operator decision value request packet, operator decision value template packet, operator decision value collection gate, operator decision value record path, explicit operator approval value record, effect receipt preflight, external adapter evidence preflight, and secret handoff preflight; `AwaitingEvidence` for live task/run producer implementation, actual effect receipt observation, actual external adapter evidence, actual secret handoff, and rollback proof.

Next action: collect rollback proof while keeping actual effect receipt observation, actual external adapter evidence, and actual secret handoff blocked until their named evidence packets exist.

STATUS:
  Completeness: 100% for secret handoff preflight
  Invariants verified: planning_only=true, local_rehearsal_only=true, route_implemented=true, route_read_only=true, producer_rehearsal_projected=true, admission_decision=blocked, decision_gate_state=blocked, path_status=ready_blocked_awaiting_explicit_operator_value, schema_ready=true, record_contract_ready=true, operator_value_record_created=true, actual_operator_decision_value_present=true, approval_status=Satisfied, approval_satisfied=true, approval_recorded=true, approval_value_present=true, effect_receipt_preflight_validated=true, effect_receipt_status=AwaitingEvidence, external_adapter_evidence_preflight_validated=true, external_adapter_evidence_status=AwaitingEvidence, secret_handoff_preflight_validated=true, secret_handoff_status=AwaitingEvidence, adapter_credentials_present=false, adapter_credentials_serialized=false, secret_values_present=false, secret_values_read=false, secret_values_serialized=false, secret_values_printed=false, live_effect_observed=false, effect_receipt_collected=false, remaining_live_witnesses_status=AwaitingEvidence, collection_route_admitted=false, record_path_admitted=false, collection_gate_satisfied=false, template_accepted_as_value=false, generic_continuation_rejected=true, generic_continuation_satisfies_approval=false, generic_continuation_records_decision=false, generic_continuation_accepted_as_decision=false, rejection_recorded=false, rejection_value_present=false, authority_granted=false, runtime_source_bound=true, runtime_local_producer_bound=true, live_task_run_producer_evidence_defined=true, live_producer_fixture_validated=true, local_producer_rehearsal_validated=true, live_producer_admission_gate_validated=true, live_producer_witness_requirements_validated=true, live_producer_operator_approval_request_validated=true, live_producer_operator_response_witness_validated=true, live_producer_operator_decision_evidence_validated=true, live_producer_operator_decision_record_validated=true, live_producer_operator_decision_value_absence_validated=true, live_producer_operator_decision_pending_status_validated=true, live_producer_operator_decision_value_intake_preflight_validated=true, live_producer_operator_decision_generic_continuation_rejection_validated=true, live_producer_operator_decision_value_request_validated=true, live_producer_operator_decision_value_template_validated=true, live_producer_operator_decision_value_collection_gate_validated=true, live_producer_operator_decision_value_record_path_validated=true, live_producer_operator_decision_value_record_validated=true, ui_created=false, mutation_endpoints_admitted=false, external_adapter_integrated=false, default_high_risk_authority=false, append-only local persistence rehearsal, read-only route design proof
  Open issues: live task/run producer implementation, actual effect receipt observation, actual external adapter evidence, actual secret handoff, rollback proof, dashboard UI, mutation endpoints, external adapter integration
  Next action: collect rollback proof before UI, mutation endpoint, or external adapter integration
