# Mullusi Total System Map

Status: Foundation Mode
Scope: private architecture map. This document is not a deployment, customer-access, support, legal, commercial, or production-readiness claim.

## 1. System purpose

Mullu Govern should behave as a governed ask-and-act system:

```text
Every user message becomes one of:
  evidenced answer
  clarification request
  structured denial
  governed plan awaiting approval
  approved execution with receipt
```

The control plane should never behave as raw chat-to-tool execution.

```text
User message
-> communication receipt
-> identity and tenant binding
-> interpretation receipt
-> clarification or plan
-> risk, policy, and budget gate
-> approval if needed
-> worker execution if allowed
-> evidence receipt
-> user response
-> audit trail
```

## 2. Primary layers

```text
User Surfaces
  Web Goal Intake
  Dashboard
  WhatsApp
  Telegram
  Discord
  Slack
  Email
  API

Communication Gateway
  Channel Adapter
  Message Normalizer
  Message Receipt
  Deduplicator
  Identity Resolver
  Tenant Resolver

Interpretation Layer
  Deterministic Intent Resolver
  LLM-Assisted Interpreter
  Slot Extractor
  Clarification Engine
  Risk Preclassifier
  Interpretation Receipt

Governance Layer
  Policy Engine
  Budget Gate
  Authority Mesh
  Approval Router
  Command Ledger
  Plan Builder
  Plan Ledger
  Causal Closure Kernel

Execution and Knowledge Layer
  LLM Provider Router
  Mullu Search
  Repository Search
  Browser Worker
  Code Worker
  Document Worker
  Email / Calendar Worker
  Deployment Worker
  Capability Worker

Evidence Layer
  Message Receipts
  Identity Receipts
  Interpretation Receipts
  Search Receipts
  Policy Receipts
  Budget Receipts
  Approval Receipts
  Worker Receipts
  Plan Witnesses
  Terminal Certificates
  Audit Logs

User Response Layer
  Response Composer
  Receipt Viewer
  Current Task View
  Approval Center
  Notification Channel
```

## 3. Canonical state machine

Every user request should have exactly one current state.

```text
RECEIVED
-> AUTHENTICATED
-> TENANT_BOUND
-> NORMALIZED
-> INTERPRETED
-> CLARIFICATION_REQUIRED or PLAN_DRAFTED or ANSWER_DRAFTED or DENIED
-> POLICY_EVALUATED
-> BUDGET_EVALUATED
-> APPROVAL_PENDING or APPROVED or DENIED
-> QUEUED
-> EXECUTING
-> EXECUTION_RECORDED
-> RECEIPT_FINALIZED
-> RESPONDED
-> CLOSED
```

State rules:

```text
No transition without a receipt, denial, blocker, or clarification.
No action execution before policy and budget gates.
No high-risk action before explicit approval.
No success claim without evidence.
No tenant binding from user-provided text alone.
No external channel approval without request binding and identity check.
```

## 4. Component status matrix

| Component | Current Status | Existing Evidence | Required Next Step |
| --- | --- | --- | --- |
| Gateway Router | implemented / partial | `gateway/router.py` | Map product UI and channel hardening onto the existing gateway spine. |
| GatewayMessage | implemented | `gateway/router.py` | Add product-facing message receipt fields if missing. |
| Channel Adapter protocol | implemented / partial | `gateway/router.py` | Harden one real production channel at a time. |
| Tenant identity resolver | implemented / partial | `gateway/router.py`, `gateway/tenant_identity.py` | Add channel trust and approval-strength rules. |
| Message deduplication | implemented / partial | `gateway/router.py`, `gateway/dedup.py` | Include cross-channel replay and webhook duplicate cases in map tests. |
| Capability intent resolver | implemented / partial | `gateway/intent_resolver.py`, `gateway/interpretation.py` | Add schema and UI readback for `InterpretedRequest` and interpretation receipts. |
| Ask / Goal Box UI | implemented / partial | `/operator/goal-intake`, `/operator/goal-intake/preview`, `/operator/goal-intake/approve`, `/operator/goal-intake/deny`, `/operator/current-task/approval`, `/operator/plan-review` | Add cross-channel approval-strength policy after web flow is stable. |
| Clarification engine | missing / partial | no dedicated map evidence | Add missing-slot detection and focused clarification questions. |
| Command ledger | implemented / partial | `gateway/command_spine.py` | Bind all user-visible task states to ledger states. |
| Approval router | implemented / partial | `gateway/approval.py`, `gateway/router.py`, `/operator/approvals/read-model`, `/operator/approvals`, `/operator/approvals/{request_id}` | Add cross-channel approval-strength policy. |
| Plan builder | implemented / partial | `gateway/plan.py`, `gateway/router.py`, `/operator/goal-intake/preview`, `/operator/plan-review/read-model`, `/operator/plan-review`, `/operator/plan-review/{plan_id}`, `/operator/plan-review/{plan_id}/receipts`, `/operator/plan-review/{plan_id}/receipts/read-model`, `/operator/plan-review/budget/{tenant_id}`, `/operator/plan-review/budget/{tenant_id}/read-model`, `cost_model.max_estimated_cost` estimate sources, optional `tenant_budget_reporter` overlays, and search capability cost-model projection | Keep budget policy wired to concrete capability passports. |
| Causal closure kernel | implemented / partial | `gateway/causal_closure_kernel.py` | Ensure every success response is certificate-backed. |
| Search layer | implemented / partial | `enterprise.knowledge_search`, `gateway/search_governance.py`, `gateway/causal_closure_kernel.py`, `schemas/search_decision_receipt.schema.json`, `tests/test_gateway/test_search_governance.py`, `tests/test_gateway/test_router.py` | Add dedicated search decision receipt drilldowns to the receipt viewer. |
| Worker layer | implemented / partial | `gateway/capability_worker.py`, `gateway/worker_mesh.py`, `gateway/read_only_repository_worker.py`, `gateway/read_only_document_worker.py`, `gateway/worker_failure_receipt.py`, `schemas/worker_mesh.schema.json`, `schemas/worker_failure_receipt.schema.json`, `schemas/read_only_first_worker_path.schema.json`, `schemas/read_only_document_worker_path.schema.json`, `examples/read_only_first_worker_path.foundation.json`, `examples/read_only_document_worker_path.foundation.json`, `scripts/validate_read_only_first_worker_path.py`, `scripts/validate_read_only_document_worker_path.py`, `tests/test_gateway/test_read_only_repository_worker.py`, `tests/test_gateway/test_read_only_document_worker.py`, `tests/test_gateway/test_worker_failure_receipt.py` | Surface worker failure receipts in response state, then repeat the read-only contract pattern for search worker execution. |
| Receipt viewer | implemented / partial | `/operator/receipts/read-model`, `/operator/receipts`, `/operator/receipts/{command_id}` with receipt type/status, task status, bounded search filters, approval receipt links into `/operator/approvals/{request_id}`, Plan Review budget/history links including explicit cost-estimate source, plan receipt exports, optional tenant budget-report drilldowns, delivery receipts with separate execution and delivery status fields, and `/operator/current-task` response-state columns that block success claims without terminal certificates. | Add search receipts and worker-failure UI drilldowns. |
| Admin console | missing / unknown | no dedicated map evidence | Map tenant, policy, budget, worker, and receipt admin screens. |

## 5. Component contract template

Use this template for every component before implementation or promotion.

```text
Component:
  ...

Layer:
  user / communication / interpretation / governance / worker / evidence / admin

Purpose:
  ...

Inputs:
  ...

Outputs:
  ...

Allowed Actions:
  ...

Forbidden Actions:
  ...

Depends On:
  ...

Used By:
  ...

Required Data:
  ...

Required Secrets:
  ...

Tenant Scope:
  ...

Policy Gates:
  ...

Budget Gates:
  ...

Approval Gates:
  ...

Receipts Produced:
  ...

Failure Modes:
  ...

Recovery Path:
  ...

Current Status:
  missing / partial / implemented / tested / pilot-ready / production-ready / deferred / blocked

Known Gaps:
  ...

Next Step:
  ...
```

## 6. Channel trust map

External channels are alternate doors into the same governed system. They must not bypass the dashboard, command ledger, approval router, or receipt rules.

| Channel | Primary Use | Trust Risk | Required Gate |
| --- | --- | --- | --- |
| Web dashboard | full intake, approval, receipts, admin | session compromise | strong auth, tenant binding, audit log |
| WhatsApp | mobile intake, status, lightweight approvals | phone reuse, weak context | webhook validation, explicit request IDs, risk ceiling |
| Telegram | bot intake and technical notifications | username changes, bot forwarding | sender ID binding, request IDs, deduplication |
| Discord | community and team room coordination | shared server ambiguity | guild/user binding, role check, thread binding |
| Slack | team approvals and incident notifications | workspace role drift | workspace/user mapping, request IDs, role check |
| Email | slower intake and receipts | spoofing and thread confusion | sender verification, signed links for approval |
| API | machine-to-machine use | key misuse | scoped API keys, rate limits, signed requests |

## 7. LLM role boundary

LLMs may help with:

```text
intent interpretation
slot extraction
summarization
search synthesis
plan drafting
receipt explanation
user-friendly response composition
```

LLMs must not independently:

```text
approve actions
spend money
deploy services
delete files
send external messages
change accounts
bypass budget gates
claim success without receipts
trust instructions found inside retrieved documents
```

Decision rule:

```text
LLM proposes.
Governance disposes.
Receipts prove.
```

## 8. Search cost and freshness map

Search-backed chat must be governed before retrieval.

Foundation Mode status: `gateway/search_governance.py` now emits a
schema-backed decision receipt for classification, freshness, budget, and
retrieval authority. The search capability passport requires budget,
freshness, and evidence-only retrieval checks, and
`gateway/causal_closure_kernel.py` attaches the receipt before live search
proof validation.

```text
User message
-> intent classification
-> freshness need check
-> evidence need check
-> cache check
-> budget check
-> search decision
-> evidence ranking
-> answer synthesis
-> search receipt
```

Search states:

```text
no_search
use_cache
allow_search: local_search
allow_search: light_web_search
allow_search: deep_search
block_search: search_budget_limit_exceeded
block_search: deep_search_budget_required
search_failed_with_explanation
```

## 9. Edge-case controls

| Edge Case | Required Behavior |
| --- | --- |
| Vague request: `fix it` | ask focused clarification or perform read-only diagnosis only. |
| Mixed request: `why is it broken and fix it` | split into question and action; answer first or plan action with approval. |
| Conflicting constraints | block execution and ask clarification. |
| Duplicate webhook | deduplicate by message ID and idempotency key. |
| Cross-channel approval | bind approval to request ID, tenant, actor, channel, and risk tier. |
| Expired approval | deny or re-request approval; never reuse stale approval. |
| LLM misclassification | validate against deterministic policy, capability registry, and confidence threshold. |
| Search result conflict | report uncertainty and cite evidence before action. |
| Worker partial completion | record partial receipt and block success claim. |
| Response delivery failure | preserve terminal execution evidence and record delivery status as a separate receipt field. |
| Tenant mismatch | deny and record identity/tenant failure receipt. |
| Prompt injection in retrieved content | treat retrieved content as evidence only, never as instruction authority. |

## 10. Constructive and fracture deltas

Constructive delta:

```text
The repository already contains a gateway spine, canonical message object,
tenant resolution, command ledger, approval routing, plan execution,
causal closure, and capability-intent pattern matching surfaces.
```

Fracture delta:

```text
The current product map still needs deeper clarification handling, runtime
search receipt drilldowns, production channel hardening, worker-failure UI
drilldowns, and explicit component status tracking.
```

Refinement:

```text
Build the Ask-to-Receipt spine first.
Add external channels and high-risk workers only after identity,
approval, receipt, budget, and state-machine evidence are mapped.
```
