<!--
Purpose: pre-implementation readiness map for the Mullusi Agentic Service Harness phase.
Governance scope: planning-only harness readiness, public API evidence, tenant/project/run/approval/sandbox/receipt contracts, and non-goal enforcement.
Dependencies: DEPLOYMENT_STATUS.md, schemas/agentic_service_harness.schema.json, examples/agentic_service_harness.*.json, gateway agentic-service-harness read models, sandbox/code-worker contracts, and repository validators.
Invariants: no dashboard is created, no mutation endpoint is added, no live coding adapter is integrated, no branch/PR/deploy/DNS/secret/destructive authority is granted.
-->

# Mullusi Agentic Service Harness Readiness Map

Date: 2026-06-16

Outcome: `AwaitingEvidence`

This is a readiness audit, not an implementation plan. It maps the current control-plane foundation before any user-facing Agentic Service Harness build. The repository now has a strong planning and read-only contract surface, but the live harness should not start until the missing durable user/project/run/approval/sandbox/receipt foundations are closed in small PRs.

## Decision Summary

| Area | Status | Judgment |
| --- | --- | --- |
| 1. Public API foundation | READY | Live public API/evidence endpoints respond, and the live deployment witness now reports current `origin/main` commit `abf22a2d...`. |
| 2. User/project/tenant model | PARTIAL | Schema and read-model examples exist; durable harness-owned persistence and exact ApprovalRequest/LoopStatus bindings are incomplete. |
| 3. Agent service harness contract | PARTIAL | Contract schema, examples, read-only route, and blocked live-producer gates exist; live producer and adapter execution remain intentionally absent. |
| 4. First MVP adapter path | PARTIAL | GitHub/Codex-style concepts exist as no-effect planning projections and lower-level code-worker/sandbox pieces; no approved branch/PR execution path exists. |
| 5. Permission and authority model | READY | Roles, action classes, approval gates, and blocked high-risk actions are encoded and validated with no mutation authority. |
| 6. Sandbox/workspace safety | PARTIAL | Command/path/time/network safety foundations exist; harness-specific branch workspace binding and live cleanup receipts are missing. |
| 7. Receipt and evidence model | PARTIAL | Required receipt fields exist in contract examples; durable harness runtime receipt emission/store binding is not implemented. |
| 8. Dashboard/UI requirements | MISSING | No user-facing dashboard should be built yet; only read-only API/status evidence exists. |
| 9. Explicit non-goals | READY | First-phase non-goals are encoded in harness examples and validator expectations. |

## Evidence Snapshot

| Evidence | Observation |
| --- | --- |
| Current main | `origin/main = abf22a2d3cb0a39e8ed3e55759998c3621410110` |
| Latest mainline receipt merges | `#1806` added readiness waiver review packet evidence; `#1807` added Personal Assistant foundation evidence receipt; `#1810` aligned the Personal Assistant foundation evidence surface after that merge; `#1811` refreshed this harness readiness map. These are read-only governance/evidence surfaces and grant no harness execution authority. |
| Live health probe | `GET https://api.mullusi.com/health -> 200`, sample status `healthy` |
| Live deployment witness | `GET https://api.mullusi.com/deployment/witness -> 200`, deployed commit sample `abf22a2d3cb0a39e8ed3e55759998c3621410110` |
| Live capability evidence | `GET https://api.mullusi.com/capabilities/evidence -> 200`, sample capability count `81` |
| Live audit verify | `GET https://api.mullusi.com/audit/verify -> 200`, sample `valid=true` |
| Live proof verify | `GET https://api.mullusi.com/proof/verify -> 200`, sample `valid=true` |
| Harness route | `GET /api/v1/harness/status` exists in `gateway/server.py`; POST is tested as not admitted. |
| Harness contract | `schemas/agentic_service_harness.schema.json` plus five examples for read-only, dry-run, branch-write awaiting approval, open-PR awaiting approval, and blocked high-risk. |
| Live producer status | Local rehearsal and blocked admission gates exist; live producer implementation remains denied. |

## 1. Public API Foundation

Area status: READY

| Item | Status | Evidence | Smallest next PR when not READY |
| --- | --- | --- | --- |
| api.mullusi.com health | READY | Live unauthenticated `GET /health` returned `200` with `healthy` status on 2026-06-16. | - |
| deployment witness | READY | Live `GET /deployment/witness` returned `200`, and witness commit matches current `origin/main` `abf22a2d...`. | - |
| runtime conformance | READY | Live deployment witness includes passed `runtime_conformance` check and certificate `conf-290f78a0872d2bf5` for `abf22a2d...`. | - |
| proof verify | READY | Live `GET /proof/verify` returned `200` with `valid=true`. | - |
| audit verify | READY | Live `GET /audit/verify` returned `200` with `valid=true`. | - |
| loop read model | READY | `scripts/report_holistic_loop_read_model.py` and `scripts/validate_holistic_loop_read_model.py` exist, and harness read model examples reference `loop://holistic-loop-read-model`. | - |

## 2. User/Project/Tenant Model

Area status: PARTIAL

| Item | Status | Evidence | Smallest next PR when not READY |
| --- | --- | --- | --- |
| User | READY | `schemas/agentic_service_harness.schema.json` defines `user`; examples include `user.operator`. | - |
| Organization | READY | Harness schema defines `organization`; examples include `org.foundation`; organization kernel runtime also exists. | - |
| Project | READY | Harness schema defines `project` with tenant, repositories, runs, receipts, and loop status ref. | - |
| RepositoryConnection | PARTIAL | Harness schema defines GitHub repository connections, but examples are presence-only and write authority is false. | Add a durable `RepositoryConnection` store/read model with GitHub App installation ref, scopes, revocation path, and no secret serialization. |
| AgentRun | READY | Harness schema defines `agent_run`; read-model producer projects runs into status output. | - |
| ApprovalRequest | PARTIAL | Gateway has `ApprovalRequest`; harness schema uses `approval_gate`, but no harness-owned ApprovalRequest persistence/read model exists. | Add a harness ApprovalRequest binding that maps ApprovalGate to gateway approvals without creating mutation routes. |
| Receipt | PARTIAL | Harness agent-run receipt contract exists; runtime receipt-store write path is still witness-only. | Add a durable read-only harness receipt-store binding and append preflight; keep append disabled until approved. |
| LoopStatus | PARTIAL | Loop refs exist; no typed harness `LoopStatus` entity is in the harness schema. | Add a `LoopStatus` schema/read-model projection bound to holistic loop readiness reports. |

## 3. Agent Service Harness Contract

Area status: PARTIAL

| Item | Status | Evidence | Smallest next PR when not READY |
| --- | --- | --- | --- |
| AgentTask | READY | Defined by schema and all scenario examples. | - |
| AgentAdapter | PARTIAL | Schema supports `github_repo_task` and `codex_style_coding`, but `external_adapter_integrated=false`. | Add an adapter registry read model with contract-only GitHub/Codex-style entries and explicit blocker refs. |
| WorkspaceSandbox | PARTIAL | Schema defines sandbox contract; lower-level sandbox runner exists; harness-specific workspace allocation is not implemented. | Add harness workspace sandbox allocation plan/fixture with cleanup receipt refs, still no execution. |
| AgentRunReceipt | READY | Defined by schema with task request, selected agent, mode, files, commands, tests, policy, risk, evidence, and next action. | - |
| ApprovalGate | READY | Defined by schema; branch-write/open-PR examples require pending gates and block self approval. | - |
| EvidenceBundle | READY | Defined by schema with refs only, no secret values, and hash/reference redaction. | - |
| ResultSummary | READY | Defined by schema and read-model projection. | - |

## 4. First MVP Adapter Path

Area status: PARTIAL

| Item | Status | Evidence | Smallest next PR when not READY |
| --- | --- | --- | --- |
| GitHub repo task service | PARTIAL | Personal assistant GitHub/Codex projection exists as no-effect review planning; GitHub token/check-run helpers exist outside the harness. | Add read-only GitHub repository task service contract plus repo metadata probe receipt; no branch writes. |
| Codex-style coding adapter | PARTIAL | Harness schema admits `codex_style_coding`; code-worker/sandbox primitives exist; no adapter integration exists. | Add contract-only Codex-style adapter descriptor with required sandbox, receipt, and approval evidence. |
| temporary branch workspace | MISSING | No harness-owned temporary branch workspace allocator exists. | Add a branch workspace plan schema and local fixture; no branch creation yet. |
| test runner | PARTIAL | Code worker can admit exact `pytest`, `npm`, `cargo`, and validator commands under leases; no harness test-runner binding exists. | Add harness test runner binding fixture from workspace sandbox to command receipts. |
| diff collection | PARTIAL | Receipt schema supports diff refs; sandbox/code worker can witness changed-file refs; no harness diff collector exists. | Add hash/ref-only diff collection contract and validator. |
| PR creation after approval only | MISSING | Open-PR scenario is approval-gated but performs no PR creation. | Add PR creation admission preflight that requires approval, branch evidence, tests, diff summary, and receipt bundle; no PR creation endpoint. |

## 5. Permission and Authority Model

Area status: READY

| Item | Status | Evidence | Smallest next PR when not READY |
| --- | --- | --- | --- |
| viewer | READY | Required in harness permission model. | - |
| operator | READY | Required in harness permission model. | - |
| approver | READY | Required in harness permission model and approval gates. | - |
| admin | READY | Required in harness permission model. | - |
| read-only action | READY | `read_only` action class and read-only scenario exist. | - |
| dry-run action | READY | `dry_run` action class and scenario exist. | - |
| write-to-branch action | READY | `write_to_branch` action class exists and is approval-gated. | - |
| open-PR action | READY | `open_pr` action class exists and is approval-gated. | - |
| blocked high-risk actions: merge, deploy, DNS, secrets, destructive operations | READY | Validator requires all five blocked actions and false high-risk permission flags. | - |

## 6. Sandbox/Workspace Safety

Area status: PARTIAL

| Item | Status | Evidence | Smallest next PR when not READY |
| --- | --- | --- | --- |
| command allowlist | READY | Harness schema requires command allowlist; code worker enforces exact lease allowed commands and denied executables. | - |
| path allowlist | READY | Harness schema and code worker enforce path allowlists and repository-bound paths. | - |
| timeout budget | READY | Harness schema requires bounded timeout; sandbox runner and code worker enforce timeouts. | - |
| network/proxy policy | PARTIAL | Harness schema admits `none` and `proxy_allowlist`; current runner/code-worker default to no network. Proxy allowlist is not harness-bound. | Add proxy-allowlist policy schema and deny-by-default harness validation; do not enable network. |
| secret redaction | READY | Harness examples and validators reject secret serialization; sandbox projections require redaction. | - |
| no uncontrolled production mutation | READY | Contracts require `production_mutation_allowed=false`; live producer gates deny deployment, DNS, secrets, destructive operations, and runtime writes. | - |

## 7. Receipt and Evidence Model

Area status: PARTIAL

| Item | Status | Evidence | Smallest next PR when not READY |
| --- | --- | --- | --- |
| task request | READY | `task_request_ref` is required in `agent_run_receipt`. | - |
| selected agent | READY | `selected_agent_ref` is required in agent runs and receipts. | - |
| mode | READY | `mode` is required and constrained to read-only, dry-run, branch-write, open-PR. | - |
| files changed | READY | `files_changed` is required with count, changed refs, and diff refs. | - |
| commands run | READY | `commands_run` records command refs, status, stdout/stderr refs, and timeout. | - |
| tests run | READY | `tests_run` records test command refs, status, assertion count, and log ref. | - |
| policy result | READY | `policy_result` is constrained to allowed read-only, allowed dry-run, awaiting approval, or blocked high-risk. | - |
| risk level | READY | `risk_level` is constrained to low, medium, high, critical. | - |
| evidence refs | READY | Evidence refs are required on tasks, gates, receipts, and bundles. | - |
| next action | READY | `next_action` is required on contracts, receipts, summaries, and status projection. | - |
| durable harness receipt emission | PARTIAL | Existing read-only worker receipt-store path is witness-only; harness runtime receipt writes are not enabled. | Add harness receipt-emitter dry-run and durable store binding validator before any append path. |

## 8. Dashboard/UI Requirements

Area status: MISSING

| Item | Status | Evidence | Smallest next PR when not READY |
| --- | --- | --- | --- |
| login/account | MISSING | No harness user account UI exists. | Add auth/account read-model API contract and static fixture; no UI yet. |
| connect GitHub repo | MISSING | RepositoryConnection contract is presence-only; no connect flow exists. | Add GitHub repository connection intake contract and approval/secret handoff preflight. |
| create agent task | MISSING | AgentTask schema exists; no task creation route/UI exists. | Add task intake schema and read-only validation endpoint design; no mutation route. |
| run status | PARTIAL | `GET /api/v1/harness/status` exists and is read-only. | Add run-status read model for multiple runs backed by durable store fixtures. |
| evidence/receipt view | PARTIAL | Receipt/evidence projections exist; no harness view exists. | Add evidence/receipt read-model route design and validator. |
| approval screen | PARTIAL | Approval router and approval gates exist; no harness approval UI exists. | Add approval queue read-model contract and validator; approval mutation remains blocked. |
| loop/readiness dashboard | PARTIAL | Loop read-model scripts and harness status route exist; no dashboard exists. | Add dashboard information architecture/read-model map only; do not build UI. |

## 9. Explicit Non-Goals For First Harness Phase

Area status: READY

| Item | Status | Evidence | Smallest next PR when not READY |
| --- | --- | --- | --- |
| no unrestricted OpenClaw automation | READY | Harness validator requires `no_unrestricted_openclaw_automation`. | - |
| no email sending | READY | Harness validator requires `no_email_sending`. | - |
| no production deploy approval by default | READY | Harness validator requires `no_production_deploy_approval_by_default`; permission model blocks deploy. | - |
| no DNS mutation | READY | Harness validator requires `no_dns_mutation`; permission model blocks DNS mutation. | - |
| no secret mutation | READY | Harness validator requires `no_secret_mutation`; permission model blocks secret mutation. | - |
| no marketplace | READY | Harness validator requires `no_marketplace`. | - |
| no billing requirement yet | READY | Harness validator requires `no_billing_requirement`. | - |
| no multi-agent marketplace until first GitHub/Codex-style path is safe | READY | Harness validator requires `no_multi_agent_marketplace`. | - |

## Discipline Scan

| Discipline | Finding | Gap or pass | Fix |
| --- | --- | --- | --- |
| Strategy/Product | Harness should start with GitHub/Codex-style repo task path only. | Pass | Keep non-goals and first adapter path constrained. |
| Design/Research | Dashboard requirements are known but should not be built yet. | Gap | Define read models and approval/evidence screens before UI implementation. |
| Engineering | Contracts and read-only route exist; durable stores and execution bindings are incomplete. | Gap | Close user/project/run/approval/sandbox/receipt model PRs first. |
| Quality/Security | Validators cover contract safety, non-goals, status route denial, and high-risk blocking. | Pass | Extend validators when durable store and branch workspace contracts are added. |
| Operations | Public evidence endpoints are live, but latest main is not deployed/witnessed. | Gap | Refresh deployment/runtime witness for current main before public readiness claims. |
| Business/GTM | No marketplace, billing, or customer-facing launch requirement is admitted. | Pass | Keep first phase internal/foundation until safe GitHub path is closed. |

## Recommended PR Sequence

1. `audit(harness): bind durable user project run model`
   Add durable read-model/store contracts for User, Organization, Project, RepositoryConnection, AgentRun, ApprovalRequest, Receipt, and LoopStatus without mutation routes.

2. `audit(harness): add workspace sandbox allocation contract`
   Add branch workspace, cleanup receipt, command/test/diff collection contracts and validators; keep execution disabled.

3. `audit(harness): add github repo task read-only adapter contract`
   Add GitHub repo metadata probe receipt and Codex-style adapter descriptor; no branch write, no PR creation.

4. `audit(harness): add approval-gated branch and pr admission preflight`
   Add preflight validators for write-to-branch and open-PR after approval, tests, diff, and receipt bundle evidence; still no endpoint.

5. `audit(harness): map dashboard read models`
   Add dashboard information architecture and read-model contracts only after the previous foundations validate.

## Verification Results

| Check | Result |
| --- | --- |
| `python scripts/validate_agentic_service_harness_contract.py --strict` | PASS |
| `python scripts/validate_agentic_service_harness_read_only_status_route.py` | PASS |
| `python scripts/validate_agentic_service_harness_read_model_projections.py` | PASS |
| `python scripts/validate_agentic_service_harness_live_task_run_producer_evidence.py` | PASS |
| `python scripts/validate_agentic_service_harness_live_task_run_producer_rehearsal.py` | PASS |
| `python scripts/validate_agentic_service_harness_live_producer_admission_gate.py` | PASS |
| `python scripts/validate_release_status.py --strict` | PASS |
| `python scripts/validate_public_repository_surface.py` | PASS |
| `git diff --check` | PASS |
| `python scripts/run_workspace_governance_checks.py --json --receipt-path .tmp/workspace-governance-preflight-receipt-harness-readiness-map.json` | PASS, 176 checks |
| `python scripts/validate_workspace_governance_preflight_receipt.py --receipt .tmp/workspace-governance-preflight-receipt-harness-readiness-map.json` | PASS |

## Final Judgment

The repository is ready for the next foundation PRs, not ready for the user-facing harness UI or live coding adapter implementation.

Required ordering:

1. Close durable user/project/run/approval/sandbox/receipt models.
2. Close read-only GitHub repo task service evidence.
3. Close branch workspace/test/diff contracts.
4. Close approval-gated PR admission preflight.
5. Only then begin dashboard UI work.

STATUS:
  Completeness: 100%
  Invariants verified: no dashboard, no mutation endpoint, no live coding adapter, no branch/PR/deploy/DNS/secret/destructive authority, no secret serialization claim
  Open issues: durable harness model, branch workspace contract, GitHub read-only task service, PR admission preflight, dashboard read models
  Next action: implement the smallest durable user/project/run/approval/sandbox/receipt model PR
