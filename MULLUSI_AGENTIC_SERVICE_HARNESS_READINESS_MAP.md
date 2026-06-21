<!--
Purpose: map current repository readiness before the Mullusi Agentic Service Harness phase.
Governance scope: planning-only readiness classification for public API, tenant/project/run, agent harness, adapter, permission, sandbox, receipt, dashboard, and first-phase non-goal boundaries.
Dependencies: DEPLOYMENT_STATUS.md, docs/FOUNDATION_MODE.md, schemas/agentic_service_harness.schema.json, examples/agentic_service_harness*.json, gateway and MCOI read-model routes, receipt validators, sandbox validators, GitHub PR closure evidence, and live public API probes.
Invariants: no dashboard creation; no mutation endpoint admission; no Claude Code or OpenClaw integration; no unrestricted automation; no merge, deploy, DNS, secret, or destructive-operation authority.
-->

# Mullusi Agentic Service Harness Readiness Map

Date: 2026-06-21

Outcome: `AwaitingEvidence`

This is a readiness audit, not an implementation change. The repository is no longer blocked by the earlier architecture gap; it is in safety and hardening cleanup. The next harness phase must still close durable user, project, repository, run, approval, sandbox, and receipt foundations before any user-facing dashboard or live coding adapter is started.

Current `origin/main`: `7334ea159209406151f18343b93b30b5c77717af`

Open PRs after readiness-map refresh: `gh pr list --state open --limit 30 --json number,isDraft,headRefName,title` returned PR #2111 `openapi-export-artifact-witness` on 2026-06-21 after verifying `origin/main` at `7334ea159209406151f18343b93b30b5c77717af`; the queue remains live, may change after this task creation admission preflight closure, and remains outside this map-only closure.

## Closure Evidence

| Check | Verdict | Evidence |
| --- | --- | --- |
| Scheduler safety PR | READY | PR #1532 was closed earlier as a read-only scheduler history validation fix. Invalid limits are governed `422` errors; `limit=0` remains a valid empty read. |
| Receipt evidence PR | READY | PR #1865 merged at `2026-06-18T03:58:19Z`, merge commit `ddddcd91dd3c8ddfc9f21d95235e7104ce4ad1bd`. |
| Resilience rehearsal PR | READY | PR #1850 was marked ready after local and remote validation, then merged at `2026-06-18T04:01:50Z`, merge commit `b78592f97542cc3c6a9adf2b7c93cd104c029363`. |
| Active lease witness PR | READY | PR #1979 merged at `2026-06-19T16:06:08Z`, merge commit `b849663f9e5e4a2f0d0c6992bedad735e61fb6a8`. |
| Worker effect reconciliation witness PR | READY | PR #1983 merged at `2026-06-19T16:32:05Z`, merge commit `92c0bf83841253ca395cf3d35259bab82715b79d`. |
| AgentRun receipt dry-run PR | READY | PR #2025 merged at `5c77e4f7d43e9b7423b20f5f9fb965745b1c7d20` ancestry; it added the AgentRun receipt-emitter dry-run schema, fixture, validator, tests, manifest entry, and CI coverage without runtime receipt emission authority. |
| GitHub repo task intake PR | READY | PR #2059 merged at `ece356172950e2e3a8cd8ce7aa0c06803b9f0073`; it added the `agentic_service_harness_github_repo_task_intake` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It validates repository connection and read-only task scope while denying adapter execution, branch writes, PR creation, receipt append, mutation routes, secret serialization, and terminal closure. |
| Dashboard data contract PR | READY | Commit `1e94f9b786891f992bf195036fd344f0b26868a5` on `origin/main` added `agentic_service_harness_dashboard_data_contract` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It binds a read-only dashboard data contract with seven display-only widget contracts while dashboard UI creation remains blocked and route registration remains blocked. |
| Adapter registry contract PR | READY | This proof thread adds `agentic_service_harness_adapter_registry_contract` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It binds contract-only GitHub/Codex-style adapter entries, modes, authority classes, gate refs, and blocker refs while route registration, mutation endpoints, subprocess execution, connector calls, external model execution, branch writes, PR creation, receipt append, and terminal closure remain blocked. |
| EvidenceBundle projection PR | READY | This proof thread adds `agentic_service_harness_evidence_bundle_projection` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It groups command logs, test logs, diff refs, policy refs, receipt refs, and source read-model refs by AgentRun id while log ingestion, receipt-store append, adapter execution, connector calls, branch writes, PR creation, and terminal closure remain blocked. |
| Receipt/Evidence read models PR | READY | PR #2086 merged at `75af2a2e3`; it added `agentic_service_harness_receipt_evidence_read_models` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It binds Receipt and EvidenceBundle read models by AgentRun while receipt-store append, runtime writes, command/test execution, filesystem writes, branch creation, PR creation, external adapter execution, secret serialization, and terminal closure remain blocked. |
| Receipt projection PR | READY | This proof thread adds `agentic_service_harness_receipt_projection` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It projects existing receipt refs by AgentRun id from the EvidenceBundle projection while receipt-store append, inline receipt bodies, mutation endpoints, adapter execution, connector calls, branch writes, PR creation, and terminal closure remain blocked. |
| Task creation admission preflight PR | READY | This proof thread adds `agentic_service_harness_task_creation_admission_preflight` schema, fixture, validator, protocol manifest entry, workspace-preflight wiring, and CI coverage. It records prerequisite task-creation evidence while task creation admission remains blocked from mutation endpoints, runtime writes, adapter execution, branch workspace creation, receipt append, dashboard UI, secret serialization, and terminal closure remain blocked. |
| Remote CI | PARTIAL | `origin/main` advanced to `7334ea159209406151f18343b93b30b5c77717af` with work assistant dashboard OpenAPI refresh handoff merged; this task creation admission preflight branch still requires current PR CI before merge. |
| Public API probes | READY | `https://api.mullusi.com/health`, `/deployment/witness`, `/proof/verify`, and `/audit/verify` returned HTTP 200 on 2026-06-18. |
| Open PR queue | PARTIAL | `gh pr list --state open --limit 30 --json number,isDraft,headRefName,title` returned PR #2111 `openapi-export-artifact-witness` after verifying `origin/main` at `7334ea159209406151f18343b93b30b5c77717af`; the queue is live, may change after this task creation admission preflight closure, and does not grant harness execution authority. |

## Readiness Scale

| Status | Meaning |
| --- | --- |
| READY | Repository-backed contracts, validators, routes, or live evidence exist and can be referenced by the harness phase without adding authority. |
| PARTIAL | A usable primitive exists, but a harness-owned persistence, routing, approval, or evidence binding is incomplete. |
| MISSING | No explicit harness-ready contract, route, schema, validator, or evidence path was found. |

## Area Summary

| Area | Status | Decision |
| --- | --- | --- |
| 1. Public API foundation | READY | Public endpoints and repository witness surfaces exist. Harness-specific status aggregation can reuse them without mutation. |
| 2. User/project/tenant model | PARTIAL | Schema projections exist, but durable harness-owned persistence and exact run/approval/receipt bindings remain incomplete. |
| 3. Agent service harness contract | PARTIAL | Planning schemas, examples, read-only status routes, and live-producer denial gates exist. Live adapter execution remains intentionally absent. |
| 4. First MVP adapter path | PARTIAL | GitHub/Codex-style planning receipts and dry-run boundaries exist, but approved branch workspace, diff, test, and PR creation flow are not closed. |
| 5. Permission and authority model | READY | Roles, action classes, approval gates, and blocked high-risk actions are encoded as contract-only and validated. |
| 6. Sandbox/workspace safety | PARTIAL | Command/path/network/time/cleanup preflight is now contract-bound for a temporary branch workspace; actual branch workspace creation remains blocked until approval and cleanup evidence exist. |
| 7. Receipt and evidence model | PARTIAL | Required run receipt fields, read-only Receipt projection, and AgentRun-indexed EvidenceBundle projection exist; durable harness receipt emission and store append remain blocked. |
| 8. Dashboard/UI requirements | PARTIAL | The read-only dashboard data contract exists, but the dashboard must not be built yet. Required screens remain readiness inputs only. |
| 9. Explicit non-goals | READY | First-phase non-goals are explicit and align with Foundation Mode and high-risk-action blocking. |

## 1. Public API Foundation - READY

| Item | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| api.mullusi.com health | READY | `curl.exe` returned HTTP 200 for `https://api.mullusi.com/health` on 2026-06-18. | None. |
| deployment witness | READY | `curl.exe` returned HTTP 200 for `https://api.mullusi.com/deployment/witness`; deployment witness schemas and validators exist. | None for readiness. Later harness status can reference the witness read-only. |
| runtime conformance | READY | Runtime conformance schemas, deployment witness checks, and release validators are present. | None for readiness. |
| proof verify | READY | `curl.exe` returned HTTP 200 for `https://api.mullusi.com/proof/verify`; proof verification endpoint schemas exist. | None. |
| audit verify | READY | `curl.exe` returned HTTP 200 for `https://api.mullusi.com/audit/verify`; audit verification endpoint schemas exist. | None. |
| loop read model | READY | Holistic loop read-model schema, report, validators, and HTTP surface tests exist. | None. |

## 2. User/Project/Tenant Model - PARTIAL

| Item | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| User | READY | `schemas/agentic_service_harness.schema.json` defines `users`; scenario examples include operator users. | None. |
| Organization | READY | Harness schema defines organizations; organization kernel surfaces also exist. | None. |
| Project | READY | Harness schema defines projects with tenant, repositories, runs, receipts, and loop status refs. | None. |
| RepositoryConnection | READY | Harness contract, read-model schema, fixture projection, durable entity binding, validators, and tests require durable GitHub App installation ref/state, provider repository ref, repository id/name through owner/name and slug, read permission scopes, redacted credential bindings, revocation state/evidence, last verification timestamp, default branch, no secret serialization, false write authority, and read-only projection. | None. |
| AgentRun | READY | Harness contract, read-model schema, projection, validators, and tests define lifecycle state, created and updated timestamps, transition receipt refs, terminal-state flag, and read-only query ref while preserving no adapter execution, no branch creation, no pull-request creation, and no external-effect authority. | None. |
| ApprovalRequest | READY | Harness approval gates now bind explicit approval request id/ref, gateway approval ref, requested evidence ref, response-record requirement, no collected approval, and no granted authority. | None. |
| Receipt | READY | Harness Receipt projection schema, fixture, validator, protocol manifest entry, workspace-preflight wiring, receipt schema/example coverage, and CI coverage bind receipt refs by AgentRun while append, runtime writes, command execution, test execution, secrets, and terminal closure remain disabled. | None for read-only projection. Durable receipt-store append remains blocked until approval, UAO, cleanup, and redaction evidence exist. |
| LoopStatus | READY | Harness LoopStatus projection schema, fixture, validator, protocol manifest entry, workspace-preflight wiring, and CI coverage bind project loop status to the holistic loop read-model output while loop registration, status transition, runtime execution, dashboard UI, task creation routes, mutation endpoints, receipt append, secret serialization, and terminal closure remain denied. | None for read-only projection. |

## 3. Agent Service Harness Contract - PARTIAL

| Item | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| AgentTask | READY | Defined in `schemas/agentic_service_harness.schema.json` and scenario examples. | None. |
| AgentAdapter | READY | Contract-only adapter registry exists with GitHub/Codex-style entries, modes, authority class, gate refs, and blocker refs. External adapter integration, subprocess execution, connector calls, external model execution, branch writes, pull-request creation, receipt append, and terminal closure remain explicitly false. | None for contract-only registry. |
| WorkspaceSandbox | PARTIAL | Temporary branch workspace preflight schema, fixture, validator, protocol manifest entry, workspace-preflight wiring, and tests bind command allowlist, path allowlist, timeout budget, network denial, cleanup receipt, and branch-create denial. Actual branch workspace creation remains blocked. | Keep branch workspace creation blocked until approval and cleanup evidence exist. |
| AgentRunReceipt | PARTIAL | Dry-run AgentRun receipt-emitter contract, fixture, validator, manifest entry, and CI coverage exist; runtime emission and store binding are not complete. | Add harness receipt-store append preflight after workspace lifecycle is bound. |
| ApprovalGate | READY | Approval gates and high-risk denials are modeled and validated in harness examples. | None. |
| EvidenceBundle | READY | EvidenceBundle projection schema, fixture, validator, tests, protocol manifest entry, workspace-preflight wiring, receipt schema/example coverage, and CI shard group command logs, test logs, diff refs, policy refs, receipt refs, and source read-model refs by AgentRun id. It remains read-only, reference-only, redacted, non-appendable, and non-terminal. | None for read-only projection. |
| ResultSummary | PARTIAL | Result summaries are present in examples; no durable result summary route exists. | Add read-only ResultSummary projection after AgentRunReceipt is durable. |

## 4. First MVP Adapter Path - PARTIAL

| Item | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| GitHub repo task service | READY | GitHub repo task service, read-only task intake, and contract-only GitHub repository adapter registry entry exist. The path validates repository connection and task scope without running code, connector calls, branch writes, pull-request creation, receipt append, or terminal closure. | None for read-only contract path. |
| Codex-style coding adapter | READY | Contract-only Codex-style planning adapter entry exists with read-only and awaiting-approval modes. No live coding adapter, subprocess, connector, external model execution, branch write, pull-request creation, receipt append, or terminal closure is integrated. | None for contract-only registry. |
| Temporary branch workspace | READY | Harness branch workspace preflight is bound to path allowlist, command allowlist, timeout, network denial, cleanup receipt, approval blocker, and no filesystem-write or branch-create authority. | None for preflight. Future creation remains blocked until approval and cleanup evidence exist. |
| Test runner | PARTIAL | Repository validators and test-run receipts exist; harness-selected test execution is not bound. | Add dry-run test runner plan receipt that records selected commands without execution authority. |
| Diff collection | PARTIAL | Diff and file-change receipts exist in lower-level surfaces; planned file-change collection preflight, actual file-change summary receipt, actual diff collection admission preflight, and actual diff collection receipt shape now exist. The receipt remains zero-diff and blocks raw diff content, receipt-store append, branch/workspace mutation, connector calls, and terminal closure until authority, cleanup, redaction, UAO admission, and receipt-store evidence are explicit. Actual non-empty diff collection remains unadmitted. | Add non-empty actual diff receipt only after branch-write authority, cleanup receipt, UAO admission, and receipt-store write path evidence are explicit. |
| PR creation after approval only | PARTIAL | Open-PR awaiting approval examples exist; no approved PR creation path is live. | Add a PR creation admission preflight that always blocks until ApprovalRequest and policy refs pass. |

## 5. Permission And Authority Model - READY

| Item | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| viewer | READY | Harness permission model supports read-only status and evidence views. | None. |
| operator | READY | Operator roles are represented in harness examples and approval surfaces. | None. |
| approver | READY | Approval gates and operator approval request schemas exist. | None. |
| admin | READY | Admin authority remains bounded by Foundation Mode and explicit approval gates. | None. |
| read-only action | READY | Read-only status and evidence routes are modeled and tested. | None. |
| dry-run action | READY | Dry-run task examples and validators exist. | None. |
| write-to-branch action | READY | Mode exists only as awaiting approval; default authority is blocked. | None. |
| open-PR action | READY | Mode exists only as awaiting approval; no default PR creation authority. | None. |
| blocked high-risk actions | READY | Merge, deploy, DNS, secrets, destructive operations, and unrestricted automation are represented as blocked high-risk paths. | None. |

## 6. Sandbox/Workspace Safety - PARTIAL

| Item | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| command allowlist | PARTIAL | Sandbox and code-change-loop validators include command constraints. | Add harness-specific command allowlist schema with per-mode command sets. |
| path allowlist | PARTIAL | Path confinement appears in sandbox and receipt validators. | Add workspace path policy bound to RepositoryConnection and AgentRun. |
| timeout budget | PARTIAL | Timeout concepts exist in sandbox/run validators. | Add per-task timeout budget fields and validator coverage. |
| network/proxy policy | PARTIAL | Foundation Mode blocks uncontrolled network effects; harness network policy is not first-class. | Add explicit harness network policy with default `disabled` and proxy-only future option. |
| secret redaction | PARTIAL | Secret serialization blocks exist across assistant and foundation validators. | Add harness redaction contract for command output, diffs, env names, and receipt fields. |
| no uncontrolled production mutation | READY | Foundation Mode, harness examples, and high-risk denials block production mutation. | None. |

## 7. Receipt And Evidence Model - PARTIAL

| Item | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| task request | READY | AgentTask contract covers request refs and task scope. | None. |
| selected agent | READY | Harness examples identify selected adapter/agent. | None. |
| mode | READY | Read-only, dry-run, branch-write-awaiting-approval, open-PR-awaiting-approval, and blocked high-risk modes exist. | None. |
| files changed | PARTIAL | AgentRunReceipt dry-run coverage keeps runtime state writes disabled and binds source read-model evidence; planned file-change collection is preflight-bound, actual file-change summary is zero-file gated, actual diff collection has an admission preflight, and actual diff collection receipt is now modeled as zero-diff. No non-empty actual file-change collection is admitted yet. | Add non-empty diff/file summary receipt only after workspace write authority, cleanup receipt emission, UAO admission, and receipt-store write path evidence are verified. |
| commands run | PARTIAL | Command receipt concepts exist; harness emission not durable. | Add commands-run field validator with redacted output refs. |
| tests run | PARTIAL | Test evidence exists in CI and validators; harness test-run receipt not durable. | Add tests-run receipt section with command, exit code, duration, and evidence refs. |
| policy result | READY | Policy result and approval gate fields exist in harness contracts. | None. |
| risk level | READY | Harness examples and policy surfaces include risk/high-risk blocking. | None. |
| evidence refs | READY | EvidenceBundle projection by AgentRun id groups command logs, test logs, diff refs, policy refs, receipt refs, and source read-model refs without inline logs, inline diffs, secret serialization, log ingestion, receipt append, adapter execution, branch writes, pull-request creation, or terminal closure. | None. |
| next action | READY | Harness contracts require next-action fields. | None. |

## 8. Dashboard/UI Requirements - PARTIAL

No dashboard should be created in the first readiness PR. The UI depends on durable read models that are not fully closed; the current closure only defines a read-only data contract.

| Item | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| login/account | MISSING | No harness login/account screen or account persistence should be built yet. | Add account/user read model first; UI follows after persistence is validated. |
| connect GitHub repo | PARTIAL | RepositoryConnection read model, redacted GitHub installation binding, GitHub repo task intake, dashboard data contract, contract-only adapter registry, Receipt/EvidenceBundle projections, LoopStatus projection, and task creation admission preflight are closed for read-only projection; no connect UI or provider mutation route is authorized. | Add approved branch workspace creation preflight before any connect UI or provider mutation route. |
| create agent task | PARTIAL | AgentTask exists as a contract, read-only repo task intake validates RepositoryConnection and task scope without execution authority, and the task creation admission preflight records required evidence; dashboard data contract exposes this as display-only; no user-facing task creation route, runtime state write, adapter execution, receipt append, or terminal closure is authorized. | Add approved branch workspace creation preflight before any task route admission. |
| run status | READY | AgentRun lifecycle read model exposes status, lifecycle state, transition receipt refs, terminal flag, and read-only query ref without execution authority. | None. |
| evidence/receipt view | READY | Receipt and EvidenceBundle projections are closed for display-only dashboard data, with append, runtime writes, commands, tests, secrets, and terminal closure denied. | None for read-only projection. |
| approval screen | MISSING | ApprovalRequest read-model binding exists; no harness approval UI is authorized yet. | Add dashboard approval screen only after receipt/evidence read models and UI data contract are closed. |
| loop/readiness dashboard | READY | Loop read models, readiness docs, read-only dashboard data contract, contract-only adapter registry, Receipt/EvidenceBundle projections, and LoopStatus projection exist; no dashboard build, route, mutation control, receipt append, status transition, loop registration, or adapter execution is authorized. | None for read-only projection. |

## 9. Explicit Non-Goals For The First Harness Phase - READY

| Non-goal | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| no unrestricted OpenClaw automation | READY | External adapter integration remains false and unrestricted automation is blocked. | None. |
| no email sending | READY | TeamOps/Gmail surfaces keep send authority separately gated. | None. |
| no production deploy approval by default | READY | Foundation Mode and high-risk blocking deny default deployment authority. | None. |
| no DNS mutation | READY | DNS mutation remains blocked by foundation boundary validators. | None. |
| no secret mutation | READY | Secret serialization and mutation remain blocked by foundation and assistant validators. | None. |
| no marketplace | READY | Marketplace is not part of the first harness path. | None. |
| no billing requirement yet | READY | Billing is not required for this foundation phase. | None. |
| no multi-agent marketplace until the first GitHub/Codex-style path is safe | READY | Multi-agent marketplace is outside the first MVP adapter path. | None. |

## Smallest Next PR Sequence

1. `harness(workspace): add approved branch workspace creation preflight`
2. `harness(tasks): add task creation route design with runtime writes denied`

## Governance Decision

Do not start the dashboard yet.

Do not add mutation endpoints yet.

Do not integrate Claude Code or OpenClaw yet.

Do not allow merge, deploy, DNS, secret, destructive operation, unrestricted automation, or email-send authority by default.

STATUS:
  Completeness: 100%
  Invariants verified: planning-only artifact; no dashboard; no mutation endpoint; no external adapter integration; no high-risk authority; open PR queue recorded without granting execution authority; read-only GitHub repository task intake bound without execution authority; read-only dashboard data contract bound without UI or route authority; contract-only adapter registry bound without subprocess, connector, external model, branch write, PR creation, receipt append, or terminal closure authority; EvidenceBundle projection by AgentRun id bound without log ingestion, inline logs, inline diffs, receipt append, adapter execution, branch write, PR creation, secret serialization, or terminal closure authority; Receipt projection bound without append, runtime writes, command execution, test execution, secret serialization, or terminal closure authority; LoopStatus projection bound without loop registration, status transition, runtime execution, dashboard UI, task creation route, mutation endpoint, receipt append, secret serialization, or terminal closure authority; task creation admission preflight bound without user-facing route, runtime state write, task persistence, adapter execution, branch workspace creation, receipt append, dashboard UI, secret serialization, or terminal closure authority
  Open issues: durable Receipt store append, branch workspace creation authority, dashboard UI, task creation route implementation, approved branch workspace creation preflight, and live adapter integration remain partial, missing, externally blocked, or outside this closure
  Next action: start the smallest next PR sequence with approved branch workspace creation preflight
