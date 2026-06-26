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

Current `origin/main`: `32b784c6a52c307c690f5d42ee264446f7b65e06`

Open PRs after readiness-map refresh: the external PR queue remains outside this PR terminal closure readiness-map closure; the queue is live, may change after this branch, and does not grant harness execution authority.

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
| Task creation admission preflight PR | READY | This proof thread adds `agentic_service_harness_task_creation_admission_preflight` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It validates source task, read-model, approval, and evidence refs while task creation route, task record write, adapter execution, branch workspace creation, receipt append, mutation endpoints, secret serialization, and terminal closure remain blocked. |
| Approved branch workspace creation preflight PR | READY | This proof thread adds `agentic_service_harness_approved_branch_workspace_creation_preflight` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It binds task creation admission, temporary branch workspace, workspace sandbox, approval, UAO, cleanup, and next evidence refs while branch workspace creation, filesystem writes, adapter execution, connector calls, receipt append, secret serialization, and terminal closure remain blocked. |
| Dry-run test runner plan receipt PR | READY | This proof thread adds `agentic_service_harness_dry_run_test_runner_plan_receipt` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It records selected validator and pytest commands as plan-only evidence while command execution, subprocess execution, test result claims, coverage claims, filesystem writes, adapter execution, connector calls, receipt append, secret serialization, and terminal closure remain blocked. |
| Task record write UAO admission preflight PR | READY | This proof thread adds `agentic_service_harness_task_record_write_uao_admission_preflight` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It binds task creation admission, dry-run test runner plan, tenant/project identity, idempotency, rollback, receipt-store write-path, and next evidence refs while task record writes, runtime state writes, mutation routes, receipt append, adapter execution, filesystem writes, branch writes, secret serialization, and terminal closure remain blocked. |
| Receipt-store append preflight PR | READY | This proof thread adds `agentic_service_harness_receipt_store_append_preflight` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It binds task-record UAO admission, Universal Symbol receipt-store write-path and authority witnesses, append audit, writer registration, idempotency, durability replay, rollback, redaction, and next evidence refs while receipt-store append, runtime state writes, mutation routes, raw payloads, adapter execution, filesystem writes, branch writes, secret serialization, and terminal closure remain blocked. |
| Executed test receipt admission preflight PR | READY | This proof thread adds `agentic_service_harness_executed_test_receipt_admission_preflight` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It binds dry-run test runner plan, approved branch workspace preflight, receipt-store append preflight, operator approval, command timeout, subprocess redaction, exit-code, output-digest, and next evidence refs while executed test receipt, command execution, subprocess execution, test result claims, coverage claims, receipt-store append, runtime state writes, mutation routes, raw test output, secret serialization, and terminal closure remain blocked. |
| Non-empty diff receipt admission preflight PR | READY | This proof thread adds `agentic_service_harness_non_empty_diff_receipt_admission_preflight` schema, fixture, validator, manifest entry, workspace-preflight wiring, and tests. It binds the zero-diff actual diff collection receipt, branch/workspace authority, cleanup, redaction, UAO admission, receipt-store write-path, redacted diff bundle digest, and next evidence refs while non-empty diff receipt admission, raw diff bodies, raw file content, receipt-store append, runtime state writes, mutation routes, connector calls, secret serialization, and terminal closure remain blocked. |
| GitHub PR admission preflight PR | READY | Existing repository artifacts include `agentic_service_harness_github_pr_admission_preflight` schema, fixture, validator, manifest entry, workspace-preflight wiring, CI coverage, and receipt example coverage. It binds the GitHub task receipt-emitter dry-run, operator approval, branch-write authority, UAO admission, rollback, CI evidence, and effect-reconciliation blockers while PR admission is denied and branch writes, PR creation, repository writes, adapter execution, connector calls, mutation routes, secret material, and terminal closure fail closed. |
| GitHub PR CI gate before ready-for-review witness PR | READY | Existing repository artifacts include `agentic_service_harness_github_pr_ci_gate_before_ready_for_review_witness` schema, fixture, validator, manifest entry, workspace-preflight wiring, CI coverage, and receipt example coverage. It binds the repository effect rollback plan, requested CI evidence ref, required check result, and remaining effect_reconciliation witness while CI gate authority remains AwaitingEvidence and no branch, PR, ready-for-review, repository, connector, network, mutation-route, receipt-store, secret, destructive, or terminal authority is granted. |
| GitHub PR effect reconciliation witness PR | READY | Existing repository artifacts include `agentic_service_harness_github_pr_effect_reconciliation_witness` schema, fixture, validator, manifest entry, workspace-preflight wiring, CI coverage, and receipt example coverage. It binds to the GitHub PR CI gate before ready-for-review witness and records required effect reconciliation evidence before terminal closure while effect reconciliation remains AwaitingEvidence and no branch, PR, ready-for-review, merge, repository, connector, network, mutation-route, receipt-store, secret, destructive, or terminal authority is granted. |
| GitHub PR effect reconciliation evidence contract PR | READY | Existing repository artifacts include `agentic_service_harness_github_pr_effect_reconciliation_evidence_contract` schema, fixture, validator, manifest entry, workspace-preflight wiring, CI coverage, and receipt example coverage. It binds to the effect reconciliation witness and requires read-only GitHub PR state observation while live evidence remains AwaitingEvidence and no branch, PR, ready-for-review, merge, repository, connector, network, mutation-route, receipt-store, secret, destructive, or terminal authority is granted. |
| GitHub PR effect reconciliation live evidence PR | READY | Existing repository artifacts include `agentic_service_harness_github_pr_effect_reconciliation_live_evidence` schema, fixture, validator, manifest entry, workspace-preflight wiring, CI coverage, and receipt example coverage. It binds to the evidence contract and records read-only GitHub metadata observations for branch state, pull request state, required checks, merge state, and branch deletion state while granting no repository mutation, secret, destructive, or terminal closure authority. |
| GitHub PR terminal closure certificate witness PR | READY | Existing repository artifacts include `agentic_service_harness_github_pr_terminal_closure_certificate_witness` schema, fixture, validator, manifest entry, workspace-preflight wiring, CI coverage, and receipt example coverage. It binds to the effect reconciliation witness and requests `evidence://github-pr-terminal-closure-certificate` while terminal closure status remains AwaitingEvidence and no branch, PR, ready-for-review, merge, repository, connector, network, mutation-route, receipt-store, secret, destructive, or terminal authority is granted. |
| GitHub PR terminal closure certificate candidate PR | READY | Existing repository artifacts include `agentic_service_harness_github_pr_terminal_closure_certificate_candidate` schema, fixture, validator, manifest entry, workspace-preflight wiring, CI coverage, and receipt example coverage. It binds live effect reconciliation evidence into a terminal closure certificate candidate while certificate minting, operator approval, repository mutation, connector calls, receipt-store append, secret serialization, destructive operation, and terminal closure remain blocked. |
| GitHub PR terminal closure operator approval gate PR | READY | Existing repository artifacts include `agentic_service_harness_github_pr_terminal_closure_operator_approval_gate` schema, fixture, validator, manifest entry, workspace-preflight wiring, CI coverage, and receipt example coverage. It binds the terminal closure certificate candidate to `approval://github-pr-terminal-closure-certificate/operator-decision` while operator approval is required, not collected, and no terminal closure certificate or authority is granted. |
| GitHub PR terminal closure operator decision contract PR | READY | Existing repository artifacts include `agentic_service_harness_github_pr_terminal_closure_operator_decision_contract` schema, fixture, validator, manifest entry, workspace-preflight wiring, CI coverage, and receipt example coverage. It requires an explicit typed operator decision value of `approve_terminal_certificate` or `deny_terminal_certificate`; generic continuation remains rejected and no certificate minting or terminal closure authority is granted. |
| GitHub PR terminal closure generic continuation rejection PR | READY | Existing repository artifacts include `agentic_service_harness_github_pr_terminal_closure_generic_continuation_rejection` schema, fixture, validator, manifest entry, workspace-preflight wiring, CI coverage, and receipt example coverage. It proves generic continuation text is rejected as terminal approval, operator decision value remains absent, and no certificate minting, repository mutation, connector call, receipt-store append, secret serialization, destructive operation, or terminal closure authority is granted. |
| GitHub PR terminal closure operator decision value request PR | READY | This proof thread adds `agentic_service_harness_github_pr_terminal_closure_operator_decision_value_request` schema, fixture, validator, manifest entry, workspace-preflight wiring, and CI coverage. It requests exactly `approve_terminal_certificate` or `deny_terminal_certificate` after generic continuation rejection while recording no operator decision value, minting no certificate, and granting no repository mutation, connector call, receipt-store append, secret serialization, destructive operation, or terminal closure authority. |
| GitHub PR terminal closure operator decision value record PR | READY | This proof thread adds `agentic_service_harness_github_pr_terminal_closure_operator_decision_value_record` schema, fixture, validator, manifest entry, workspace-preflight wiring, and CI coverage. It records the explicit operator value `approve_terminal_certificate`, satisfies only the operator decision gate, and grants no certificate minting, repository mutation, connector call, receipt-store append, secret serialization, destructive operation, or terminal closure authority. |
| Remote CI | READY | `origin/main` is verified at `32b784c6a52c307c690f5d42ee264446f7b65e06`; this terminal closure readiness-map branch requires current PR CI before merge. |
| Public API probes | READY | `https://api.mullusi.com/health`, `/deployment/witness`, `/proof/verify`, and `/audit/verify` returned HTTP 200 on 2026-06-18. |
| Open PR queue | PARTIAL | External open PRs remain outside this PR terminal closure readiness-map closure; the queue is live, may change after this branch, and does not grant harness execution authority. |

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
| 4. First MVP adapter path | PARTIAL | GitHub/Codex-style planning receipts, dry-run boundaries, approved branch workspace preflight, dry-run test runner plan receipt, task-record write UAO admission, receipt-store append preflight, executed-test receipt admission preflight, non-empty diff receipt admission preflight, GitHub PR admission preflight, GitHub PR CI gate before ready-for-review witness, effect reconciliation evidence surfaces, and non-authorizing terminal closure certificate/gate/decision/rejection/request/record surfaces exist, but live adapter execution and terminal certificate minting remain blocked. |
| 5. Permission and authority model | READY | Roles, action classes, approval gates, and blocked high-risk actions are encoded as contract-only and validated. |
| 6. Sandbox/workspace safety | PARTIAL | Command/path/network/time/cleanup preflight is now contract-bound for a temporary branch workspace; actual branch workspace creation remains blocked until approval and cleanup evidence exist. |
| 7. Receipt and evidence model | PARTIAL | Required run receipt fields, read-only Receipt projection, AgentRun-indexed EvidenceBundle projection, receipt-store append preflight, executed-test receipt admission preflight, and non-empty diff receipt admission preflight exist; durable harness receipt emission and store append remain blocked. |
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
| WorkspaceSandbox | PARTIAL | Temporary branch workspace preflight, workspace sandbox preflight, and approved branch workspace creation preflight schemas, fixtures, validators, protocol manifest entries, workspace-preflight wiring, and tests bind command allowlist, path allowlist, timeout budget, network denial, cleanup receipt, approval blockers, UAO blockers, rollback refs, and branch-create denial. Actual branch workspace creation remains blocked. | Keep branch workspace creation blocked until approval, UAO, cleanup, rollback, and effect-reconciliation evidence exist. |
| AgentRunReceipt | PARTIAL | Dry-run AgentRun receipt-emitter contract, fixture, validator, manifest entry, and CI coverage exist; runtime emission and store binding are not complete. | Add harness receipt-store append preflight after workspace lifecycle is bound. |
| ApprovalGate | READY | Approval gates and high-risk denials are modeled and validated in harness examples. | None. |
| EvidenceBundle | READY | EvidenceBundle projection schema, fixture, validator, tests, protocol manifest entry, workspace-preflight wiring, receipt schema/example coverage, and CI shard group command logs, test logs, diff refs, policy refs, receipt refs, and source read-model refs by AgentRun id. It remains read-only, reference-only, redacted, non-appendable, and non-terminal. | None for read-only projection. |
| ResultSummary | PARTIAL | Result summaries are present in examples; no durable result summary route exists. | Add read-only ResultSummary projection after AgentRunReceipt is durable. |

## 4. First MVP Adapter Path - PARTIAL

| Item | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| GitHub repo task service | READY | GitHub repo task service, read-only task intake, and contract-only GitHub repository adapter registry entry exist. The path validates repository connection and task scope without running code, connector calls, branch writes, pull-request creation, receipt append, or terminal closure. | None for read-only contract path. |
| Codex-style coding adapter | READY | Contract-only Codex-style planning adapter entry exists with read-only and awaiting-approval modes. No live coding adapter, subprocess, connector, external model execution, branch write, pull-request creation, receipt append, or terminal closure is integrated. | None for contract-only registry. |
| Temporary branch workspace | READY | Harness temporary branch workspace, workspace sandbox, and approved branch workspace creation preflights are bound to path allowlist, command allowlist, timeout, network denial, cleanup receipt, approval blocker, UAO blocker, rollback refs, and no filesystem-write or branch-create authority. | None for preflight. Future creation remains blocked until approval, UAO, cleanup, rollback, and effect-reconciliation evidence exist. |
| Test runner | READY | `agentic_service_harness_dry_run_test_runner_plan_receipt` records selected validator and pytest commands as plan-only evidence, and `agentic_service_harness_executed_test_receipt_admission_preflight` blocks executed-test receipt admission until operator approval, approved workspace, command timeout, subprocess redaction, exit-code, output-digest, receipt-store append admission, and audit evidence exist. Command execution, subprocess execution, test result claims, coverage claims, receipt append, secret serialization, raw test output, and terminal closure remain blocked. | None for plan-only command selection or admission preflight. Live command execution remains blocked until approved workspace, timeout, redaction, result, append, and audit evidence exist. |
| Diff collection | READY | Diff and file-change receipts exist in lower-level surfaces; planned file-change collection preflight, actual file-change summary receipt, actual diff collection admission preflight, actual diff collection receipt shape, and non-empty diff receipt admission preflight now exist. The admission preflight binds zero-diff source receipt evidence, branch/workspace authority, cleanup, redaction, UAO admission, receipt-store write-path, and redacted diff bundle digest refs while non-empty diff receipt, raw diff bodies, raw file content, receipt-store append, branch/workspace mutation, connector calls, and terminal closure remain blocked. | None for admission preflight. Actual non-empty diff receipt remains blocked until branch-write authority, cleanup receipt, UAO admission, redaction evidence, redacted diff bundle digest, and receipt-store write path evidence are explicit. |
| PR creation after approval only | READY | Open-PR awaiting approval examples, GitHub PR admission preflight, GitHub PR CI gate before ready-for-review witness, effect reconciliation evidence surfaces, and non-authorizing terminal closure certificate/gate/decision/rejection/request/record surfaces exist. They keep PR admission denied unless operator approval, branch-write authority, UAO admission, rollback, CI evidence, effect reconciliation evidence, explicit terminal decision value, and terminal certificate evidence exist, and they grant no branch, PR, ready-for-review, repository, connector, network, mutation-route, receipt-store, secret, destructive, or terminal authority. | None for admission, CI-gate witness, effect reconciliation evidence, decision-value record, or non-authorizing terminal closure request chain. Live PR creation remains blocked until a terminal closure certificate is minted through a governed path. |

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
| files changed | PARTIAL | AgentRunReceipt dry-run coverage keeps runtime state writes disabled and binds source read-model evidence; planned file-change collection is preflight-bound, actual file-change summary is zero-file gated, actual diff collection has an admission preflight, actual diff collection receipt is modeled as zero-diff, and non-empty diff receipt admission is preflight-bound without serializing raw file or diff content. No non-empty actual file-change collection is admitted yet. | Add non-empty diff/file summary receipt only after workspace write authority, cleanup receipt emission, UAO admission, redaction evidence, redacted diff bundle digest, and receipt-store write path evidence are verified. |
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
| connect GitHub repo | PARTIAL | RepositoryConnection read model, redacted GitHub installation binding, GitHub repo task intake, dashboard data contract, contract-only adapter registry, Receipt/EvidenceBundle projections, LoopStatus projection, task creation admission preflight, approved branch workspace creation preflight, dry-run test runner plan receipt, task record write UAO admission preflight, receipt-store append preflight, executed test receipt admission preflight, non-empty diff receipt admission preflight, GitHub PR admission preflight, GitHub PR CI gate before ready-for-review witness, effect reconciliation evidence surfaces, and non-authorizing terminal closure certificate/gate/decision/rejection/request/record surfaces are closed for read-only/admission-only/plan-only projection; no connect UI or provider mutation route is authorized. | Add certificate minting evidence before any connect UI or provider mutation route. |
| create agent task | READY | AgentTask exists as a contract, read-only repo task intake validates RepositoryConnection and task scope without execution authority, dashboard data contract exposes this as display-only, and task creation admission preflight records required approval/evidence refs while denying user-facing task route admission and task writes. | None for admission preflight. User-facing task creation route remains blocked until approval, UAO, rollback, and route-registration evidence exist. |
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

1. `harness(pr): mint PR terminal closure certificate after approved decision value`

## Governance Decision

Do not start the dashboard yet.

Do not add mutation endpoints yet.

Do not integrate Claude Code or OpenClaw yet.

Do not allow merge, deploy, DNS, secret, destructive operation, unrestricted automation, or email-send authority by default.

STATUS:
  Completeness: 100%
  Invariants verified: planning-only artifact; no dashboard; no mutation endpoint; no external adapter integration; no high-risk authority; open PR queue recorded without granting execution authority; read-only GitHub repository task intake bound without execution authority; read-only dashboard data contract bound without UI or route authority; contract-only adapter registry bound without subprocess, connector, external model, branch write, PR creation, receipt append, or terminal closure authority; EvidenceBundle projection by AgentRun id bound without log ingestion, inline logs, inline diffs, receipt append, adapter execution, branch write, PR creation, secret serialization, or terminal closure authority; Receipt projection bound without append, runtime writes, command execution, test execution, secret serialization, or terminal closure authority; LoopStatus projection bound without loop registration, status transition, runtime execution, dashboard UI, task creation route, mutation endpoint, receipt append, secret serialization, or terminal closure authority; task creation admission preflight bound without route admission, task writes, adapter execution, branch workspace creation, receipt append, mutation endpoint, secret serialization, or terminal closure authority; approved branch workspace creation preflight bound without workspace creation, filesystem writes, adapter execution, connector calls, receipt append, secret serialization, or terminal closure authority; dry-run test runner plan receipt bound without command execution, subprocess execution, test result claims, coverage claims, filesystem writes, adapter execution, connector calls, receipt append, secret serialization, or terminal closure authority; task record write UAO admission preflight bound without task persistence, runtime state writes, mutation routes, receipt append, adapter execution, filesystem writes, branch writes, secret serialization, or terminal closure authority; receipt-store append preflight bound without append authority, runtime state writes, mutation routes, raw payloads, adapter execution, filesystem writes, branch writes, secret serialization, or terminal closure authority; executed test receipt admission preflight bound without executed test receipt admission, command execution, subprocess execution, test result claims, coverage claims, receipt-store append, runtime state writes, mutation routes, raw test output, secret serialization, or terminal closure authority; non-empty diff receipt admission preflight bound without non-empty diff receipt admission, raw diff bodies, raw file content, receipt-store append, runtime state writes, mutation routes, connector calls, secret serialization, or terminal closure authority; GitHub PR admission preflight bound without operator approval, branch-write authority, PR creation, repository writes, adapter execution, connector calls, mutation routes, secret material, or terminal closure authority; GitHub PR CI gate before ready-for-review witness bound without branch, PR, ready-for-review, repository, connector, network, mutation-route, receipt-store, secret, destructive, or terminal authority; GitHub PR effect reconciliation witness and evidence contract bound without branch, PR, ready-for-review, merge, repository, connector, network, mutation-route, receipt-store, secret, destructive, or terminal authority; GitHub PR effect reconciliation live evidence bound to read-only GitHub metadata without repository mutation, secret, destructive, or terminal closure authority; GitHub PR terminal closure certificate witness, candidate, approval gate, decision contract, generic continuation rejection, decision value request, and decision value record bound without certificate minting, generic approval, repository mutation, connector call, receipt-store append, secret serialization, destructive operation, or terminal closure authority
  Open issues: terminal certificate minting, branch workspace creation authority, dashboard UI, and live adapter integration remain partial, missing, externally blocked, or outside this closure
  Next action: mint PR terminal closure certificate after approved decision value
