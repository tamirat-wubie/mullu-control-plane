<!--
Purpose: map current repository readiness before the Mullusi Agentic Service Harness phase.
Governance scope: planning-only readiness classification for public API, tenant/project/run, agent harness, adapter, permission, sandbox, receipt, dashboard, and first-phase non-goal boundaries.
Dependencies: DEPLOYMENT_STATUS.md, docs/FOUNDATION_MODE.md, schemas/agentic_service_harness.schema.json, examples/agentic_service_harness*.json, gateway and MCOI read-model routes, receipt validators, sandbox validators, GitHub PR closure evidence, and live public API probes.
Invariants: no dashboard creation; no mutation endpoint admission; no Claude Code or OpenClaw integration; no unrestricted automation; no merge, deploy, DNS, secret, or destructive-operation authority.
-->

# Mullusi Agentic Service Harness Readiness Map

Date: 2026-06-19

Outcome: `AwaitingEvidence`

This is a readiness audit, not an implementation change. The repository is no longer blocked by the earlier architecture gap; it is in safety and hardening cleanup. The next harness phase must still close durable user, project, repository, run, approval, sandbox, and receipt foundations before any user-facing dashboard or live coding adapter is started.

Current `origin/main`: `5c77e4f7d43e9b7423b20f5f9fb965745b1c7d20`

Open PRs after readiness-map refresh: the live open PR queue includes draft PR #2012 only; the queue remains live, may change after this map-only closure, and remains outside this map-only closure.

## Closure Evidence

| Check | Verdict | Evidence |
| --- | --- | --- |
| Scheduler safety PR | READY | PR #1532 was closed earlier as a read-only scheduler history validation fix. Invalid limits are governed `422` errors; `limit=0` remains a valid empty read. |
| Receipt evidence PR | READY | PR #1865 merged at `2026-06-18T03:58:19Z`, merge commit `ddddcd91dd3c8ddfc9f21d95235e7104ce4ad1bd`. |
| Resilience rehearsal PR | READY | PR #1850 was marked ready after local and remote validation, then merged at `2026-06-18T04:01:50Z`, merge commit `b78592f97542cc3c6a9adf2b7c93cd104c029363`. |
| Active lease witness PR | READY | PR #1979 merged at `2026-06-19T16:06:08Z`, merge commit `b849663f9e5e4a2f0d0c6992bedad735e61fb6a8`. |
| Worker effect reconciliation witness PR | READY | PR #1983 merged at `2026-06-19T16:32:05Z`, merge commit `92c0bf83841253ca395cf3d35259bab82715b79d`. |
| AgentRun receipt dry-run PR | READY | PR #2025 merged at `5c77e4f7d43e9b7423b20f5f9fb965745b1c7d20` ancestry; it added the AgentRun receipt-emitter dry-run schema, fixture, validator, tests, manifest entry, and CI coverage without runtime receipt emission authority. |
| Remote CI | READY | Build Verification, SDLC Governance Gate, Schema Validation, Gateway Closure and Witness Tests, Rust, TypeScript, Python compatibility, Python soak, MCOI shards, and GitHub App token boundary checks were green before merge. |
| Public API probes | READY | `https://api.mullusi.com/health`, `/deployment/witness`, `/proof/verify`, and `/audit/verify` returned HTTP 200 on 2026-06-18. |
| Open PR queue | PARTIAL | `gh pr list --state open --limit 8` returned draft PR #2012 after fetching `origin/main` at refresh time; PR #2025, PR #2023, PR #2024, and PR #2018 are merged through `5c77e4f7d43e9b7423b20f5f9fb965745b1c7d20`; the queue is live, may change after this map-only closure, and does not grant harness execution authority. |

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
| 6. Sandbox/workspace safety | PARTIAL | Command/path/network/time/receipt primitives exist; harness-specific branch workspace lifecycle is not complete. |
| 7. Receipt and evidence model | PARTIAL | Required run receipt fields exist in contracts and examples; durable harness receipt emission and store binding are not complete. |
| 8. Dashboard/UI requirements | MISSING | The dashboard must not be built yet. Required read models and screens are only readiness inputs. |
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
| Receipt | PARTIAL | Many receipt schemas exist and harness receipts are modeled, but durable harness receipt-store append remains witness-bound. | Add a harness Receipt projection and append preflight PR with append disabled until approval. |
| LoopStatus | PARTIAL | Loop refs and read models exist; no first-class harness LoopStatus projection is closed. | Add a small LoopStatus projection PR bound to holistic loop read-model output. |

## 3. Agent Service Harness Contract - PARTIAL

| Item | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| AgentTask | READY | Defined in `schemas/agentic_service_harness.schema.json` and scenario examples. | None. |
| AgentAdapter | PARTIAL | Contract supports adapter concepts, but external adapter integration is explicitly false. | Add an adapter registry read-model PR with GitHub/Codex-style entries, modes, authority class, and blocker refs only. |
| WorkspaceSandbox | PARTIAL | Contract defines sandbox requirements and separate sandbox validators exist; branch workspace lifecycle is not harness-bound. | Add a `WorkspaceSandbox` lifecycle PR for temp branch workspace creation, cleanup receipt, and no production mutation. |
| AgentRunReceipt | PARTIAL | Dry-run AgentRun receipt-emitter contract, fixture, validator, manifest entry, and CI coverage exist; runtime emission and store binding are not complete. | Add harness receipt-store append preflight after workspace lifecycle is bound. |
| ApprovalGate | READY | Approval gates and high-risk denials are modeled and validated in harness examples. | None. |
| EvidenceBundle | PARTIAL | Evidence refs exist across harness and receipt surfaces; no harness evidence bundle aggregation is durable. | Add an EvidenceBundle read model that groups logs, diffs, tests, policies, and receipts by AgentRun. |
| ResultSummary | PARTIAL | Result summaries are present in examples; no durable result summary route exists. | Add read-only ResultSummary projection after AgentRunReceipt is durable. |

## 4. First MVP Adapter Path - PARTIAL

| Item | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| GitHub repo task service | PARTIAL | GitHub repo task service schemas, examples, and validators exist. | Add a read-only repository task intake PR that validates repo connection and task scope without running code. |
| Codex-style coding adapter | PARTIAL | Adapter concepts exist; no live coding adapter is integrated. | Add a contract-only adapter registry entry with no subprocess, connector, or external model execution. |
| Temporary branch workspace | PARTIAL | Sandbox and code-change loop primitives exist; harness branch workspace is not bound. | Add temp branch workspace preflight with path allowlist, cleanup receipt, and timeout budget. |
| Test runner | PARTIAL | Repository validators and test-run receipts exist; harness-selected test execution is not bound. | Add dry-run test runner plan receipt that records selected commands without execution authority. |
| Diff collection | PARTIAL | Diff and file-change receipts exist in lower-level surfaces; harness diff collection is not durable. | Add diff collection receipt schema with path allowlist and redaction guard. |
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
| files changed | PARTIAL | AgentRunReceipt dry-run coverage keeps runtime state writes disabled and binds source read-model evidence; no durable run emission exists yet. | Bind planned file-change collection after workspace preflight. |
| commands run | PARTIAL | Command receipt concepts exist; harness emission not durable. | Add commands-run field validator with redacted output refs. |
| tests run | PARTIAL | Test evidence exists in CI and validators; harness test-run receipt not durable. | Add tests-run receipt section with command, exit code, duration, and evidence refs. |
| policy result | READY | Policy result and approval gate fields exist in harness contracts. | None. |
| risk level | READY | Harness examples and policy surfaces include risk/high-risk blocking. | None. |
| evidence refs | PARTIAL | Evidence refs exist; aggregation by AgentRun remains missing. | Add EvidenceBundle projection by AgentRun id. |
| next action | READY | Harness contracts require next-action fields. | None. |

## 8. Dashboard/UI Requirements - MISSING

No dashboard should be created in the first readiness PR. The UI depends on durable read models that are not fully closed.

| Item | Status | Evidence | Smallest next PR |
| --- | --- | --- | --- |
| login/account | MISSING | No harness login/account screen or account persistence should be built yet. | Add account/user read model first; UI follows after persistence is validated. |
| connect GitHub repo | PARTIAL | RepositoryConnection read model and redacted GitHub installation binding are closed for read-only projection; no connect UI or provider mutation route is authorized. | Add task creation admission preflight and UI data contract only after AgentRun and approval read models are closed. |
| create agent task | MISSING | AgentTask exists as a contract; no user-facing task creation route. | Add task creation admission preflight before UI work. |
| run status | READY | AgentRun lifecycle read model exposes status, lifecycle state, transition receipt refs, terminal flag, and read-only query ref without execution authority. | None. |
| evidence/receipt view | PARTIAL | Receipt and evidence primitives exist; harness aggregation is incomplete. | Add EvidenceBundle and Receipt read models. |
| approval screen | MISSING | ApprovalRequest read-model binding exists; no harness approval UI is authorized yet. | Add dashboard approval screen only after receipt/evidence read models and UI data contract are closed. |
| loop/readiness dashboard | PARTIAL | Loop read models and readiness docs exist; no dashboard build is authorized. | Add read-only dashboard data contract after run and receipt read models. |

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

1. `harness(sandbox): bind temporary branch workspace preflight`
2. `harness(github): add read-only repo task intake`
3. `harness(ui-contract): add dashboard data contract`

## Governance Decision

Do not start the dashboard yet.

Do not add mutation endpoints yet.

Do not integrate Claude Code or OpenClaw yet.

Do not allow merge, deploy, DNS, secret, destructive operation, unrestricted automation, or email-send authority by default.

STATUS:
  Completeness: 100%
  Invariants verified: planning-only artifact; no dashboard; no mutation endpoint; no external adapter integration; no high-risk authority; open PR queue recorded without granting execution authority
  Open issues: durable Receipt store append, EvidenceBundle, WorkspaceSandbox, UI data contracts, and the current draft PR queue remain partial, missing, externally blocked, or outside this map-only closure
  Next action: start the smallest next PR sequence with temporary branch workspace preflight
