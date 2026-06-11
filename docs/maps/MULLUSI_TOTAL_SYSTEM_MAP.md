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
| Ask / Goal Box UI | missing / unknown | no dedicated map evidence | Build web-only governed goal intake before external channel expansion. |
| Clarification engine | missing / partial | no dedicated map evidence | Add missing-slot detection and focused clarification questions. |
| Command ledger | implemented / partial | `gateway/command_spine.py` | Bind all user-visible task states to ledger states. |
| Approval router | implemented / partial | `gateway/approval.py`, `gateway/router.py` | Add user-facing Approval Center map and cross-channel approval rules. |
| Plan builder | implemented / partial | `gateway/plan.py`, `gateway/router.py` | Add UI binding, budget fields, and explicit execution approval path for plan previews. |
| Causal closure kernel | implemented / partial | `gateway/causal_closure_kernel.py` | Ensure every success response is certificate-backed. |
| Search layer | partial / unknown | `enterprise.knowledge_search` intent pattern | Add freshness, cache, source, budget, and receipt gates. |
| Worker layer | partial | `gateway/capability_worker.py`, worker-related docs | Define one contract per worker type. |
| Receipt viewer | missing / unknown | no dedicated map evidence | Build user-facing receipt display after receipt model is mapped. |
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
NO_SEARCH_NEEDED
CACHE_HIT
LOCAL_SEARCH
WEB_SEARCH_LIGHT
WEB_SEARCH_DEEP_APPROVAL_REQUIRED
SEARCH_BLOCKED_BY_BUDGET
SEARCH_FAILED_WITH_EXPLANATION
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
| Response delivery failure | separate execution status from delivery status. |
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
The current product map still needs a durable InterpretedRequest object,
interpretation receipts, a web Goal Intake UI, clarification handling,
search cost and freshness gates, production channel hardening,
receipt viewer UX, and explicit component status tracking.
```

Refinement:

```text
Build the Ask-to-Receipt spine first.
Add external channels and high-risk workers only after identity,
approval, receipt, budget, and state-machine evidence are mapped.
```
