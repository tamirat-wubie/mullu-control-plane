<!--
Purpose: define the read-only persistence and read-model binding plan that follows the Agentic Service Harness readiness map.
Governance scope: planning-only binding for tenant, project, repository, agent run, approval, sandbox, receipt, evidence, and loop status surfaces.
Dependencies: MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md, schemas/agentic_service_harness.schema.json, docs/maps/MULLUSI_ASK_TO_RECEIPT_FLOW_MAP.md, docs/maps/MULLUSI_EVIDENCE_RECEIPT_MAP.md, docs/FOUNDATION_MODE.md.
Invariants: planning_only=true; ui_created=false; mutation_endpoints_admitted=false; external_adapter_integrated=false; default_high_risk_authority=false.
-->

# Mullusi Agentic Service Harness Read Model Binding Plan

## Objective

Bind the merged Agentic Service Harness contract to a read-only persistence and read-model plan before any dashboard, mutation endpoint, external adapter, or live automation work begins.

Solver outcome: `AwaitingEvidence` for implementation and `SolvedVerified` for the planning boundary after validator passage.

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
| 2 | `feat(harness): add read-only harness read-model schemas` | JSON schemas for account, project, repository, run, approval, receipt, evidence, and result summary read models. No endpoints. | schema validation plus read-model fixture tests |
| 3 | `feat(harness): add read-only harness fixture projections` | Examples that project existing contract examples into read-only read models. No persistence adapter. | projection validator and no-secret checks |
| 4 | `feat(harness): add local read-only persistence rehearsal` | Local file or in-memory rehearsal only, with append-only receipt refs. No API routes. | persistence rehearsal validator |
| 5 | `feat(harness): add read-only status route design` | Route design document only. No route implementation. | route-design validator requiring read-only method and no mutation |

## Acceptance Gates

Before implementation starts, the following must be true:

| Gate | Required state |
| --- | --- |
| Contract validation | `python scripts/validate_agentic_service_harness_contract.py --strict` passes. |
| Binding plan validation | `python scripts/validate_agentic_service_harness_read_model_binding_plan.py` passes. |
| Governance preflight | Focused workspace governance checks pass. |
| Security boundary | Secret values are not serialized; high-risk authority flags remain false. |
| UI boundary | `ui_created=false`. |
| Mutation boundary | `mutation_endpoints_admitted=false`. |
| Adapter boundary | `external_adapter_integrated=false`. |

## Status

Outcome: `AwaitingEvidence` for implementation.

Next action: add read-only harness read-model schemas in a separate PR after this planning artifact is reviewed.

STATUS:
  Completeness: 100%
  Invariants verified: planning_only=true, ui_created=false, mutation_endpoints_admitted=false, external_adapter_integrated=false, default_high_risk_authority=false
  Open issues: read-only schema PR, fixture projection PR, local persistence rehearsal PR, route design PR
  Next action: validate this planning artifact, then open the read-only schema PR
