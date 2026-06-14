# Mullusi Missing Component Gap Register

Status: Foundation Mode
Scope: local map of missing, partial, blocked, or deferred work. This register is not a roadmap commitment, delivery promise, launch claim, legal claim, support claim, customer-readiness claim, or deployment-readiness claim.

## 1. Purpose

This register tracks gaps discovered while mapping the Mullusi Govern ask-and-act system.

Each gap should answer:

```text
What is missing?
Why does it matter?
What risk does it create?
What evidence would close it?
What is the next safe local step?
```

Status vocabulary:

```text
missing
partial
implemented
tested
pilot-ready
production-ready
deferred
blocked
```

## 2. Gap register

| Gap ID | Name | Layer | Risk | Status | Why It Matters | Closure Evidence | Next Safe Step |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GAP-MAP-001 | Total mapbook not cross-linked from Start Here | Documentation | medium | implemented | The mapbook may be hard to discover from the main documentation entry path. | `docs/START_HERE.md` links to the mapbook without readiness claims. | Keep the link aligned as the mapbook evolves. |
| GAP-UI-001 | Governed Goal Intake UI missing | User Surface | high | missing / unknown | First-time users need a universal ask/goal entry before Current Task makes sense. | Web UI accepts user goal and emits `GatewayMessage`. | Design web-only Goal Intake. |
| GAP-UI-002 | Current Task state view missing | User Surface | medium | missing / unknown | Users need to see running, blocked, approved, denied, or completed task state. | UI state bound to command ledger and receipts. | Map Current Task states to command states. |
| GAP-UI-003 | Receipt Viewer missing | User Surface / Evidence | high | missing / unknown | Users need visible proof of what was interpreted, approved, executed, blocked, and evidenced. | Receipt viewer renders final and intermediate receipts. | Design read-only receipt screen. |
| GAP-COMM-001 | Production channel adapter hardening incomplete | Communication | high | partial | External channels can create identity, replay, approval, and delivery risks. | One channel has signature validation, deduplication, tenant binding, and request-ID approvals. | Harden one channel after web flow. |
| GAP-COMM-002 | Channel approval-strength rules missing | Communication / Governance | high | missing / partial | A casual message like `yes` should not approve high-risk actions without bound context. | Approval matrix by channel, action risk, tenant, actor, and request ID. | Draft channel trust policy. |
| GAP-COMM-003 | Cross-channel conversation binding incomplete | Communication | medium | missing / partial | A user may start in web and respond in Slack or WhatsApp; this can cause identity ambiguity. | Cross-channel binding rules and audit receipt. | Define allowed cross-channel handoff cases. |
| GAP-INTERP-001 | Durable InterpretedRequest object missing | Interpretation | high | implemented / partial | User text cannot safely become plans without an auditable interpretation object. | `gateway/interpretation.py` and `schemas/interpreted_request.schema.json` record intent, slots, confidence, risk, action/search need, and raw message hash. | Add UI readback when the product surface is built. |
| GAP-INTERP-002 | Interpretation receipt missing | Interpretation / Evidence | high | implemented / partial | The system needs proof of what it believed the user meant. | `InterpretationReceipt` is attached to command payloads and router response metadata; `schemas/interpretation_receipt.schema.json` validates the receipt shape. | Add persisted receipt viewer. |
| GAP-INTERP-003 | Clarification engine incomplete | Interpretation | high | implemented / partial | Vague goals must not trigger unsafe or wrong execution. | `ClarificationRequest` blocks ambiguous action-like input before command creation and returns one focused user question with safe default `no_execution`. | Expand slot requirements beyond the first vague action path. |
| GAP-INTERP-004 | LLM-assisted interpretation not bounded | Interpretation / LLM | medium | partial | LLMs can misclassify user intent or overstate available authority. | Deterministic rules run first; LLM output validated as proposal only. | Add LLM-assisted proposal lane behind deterministic interpretation. |
| GAP-GOV-001 | Ask-to-plan preview needs product binding | Governance / UI | high | implemented / partial | Users need to see risk, budget, tools, and approvals before action. | `CapabilityPlanPreview` exposes redacted read-only plan topology, risk, approval, and evidence obligations before execution authority. | Bind preview metadata to the future web Plan Review UI. |
| GAP-GOV-002 | Budget gate user display missing | Governance / UI | medium | missing / partial | Search and LLM usage can become expensive without visible limits. | Budget estimate and budget-used fields visible before approval. | Add budget fields to plan preview map. |
| GAP-GOV-003 | Policy denial explanation needs user-friendly composer | Governance / Response | medium | partial | Denials must be understandable without leaking internals. | Response composer produces safe, plain denial explanations. | Add denial response templates. |
| GAP-SEARCH-001 | Search need classifier missing | Search | medium | implemented / partial | Every chat message should not trigger search. | `SearchDecision` separates no-search, cache, local search, light web search, deep search, and blocked states before retrieval. | Add runtime classifier binding after Ask-to-Receipt UI binding. |
| GAP-SEARCH-002 | Freshness gate missing | Search | medium | implemented / partial | Current-info questions need freshness; stable facts may not. | `SearchDecision.freshness` records pre-retrieval freshness requirements; `SearchReceipt.freshness_result` records post-decision freshness status before current claims. | Bind freshness evidence to future read-only retrieval worker. |
| GAP-SEARCH-003 | Search cost gate missing | Search / Budget | high | implemented / partial | Search-backed chat can become expensive if unbounded. | `SearchDecision.budget_decision` blocks deep retrieval on BudgetUnknown or missing approval. | Bind budget policy to future Plan Review UI. |
| GAP-SEARCH-004 | Retrieval prompt-injection handling missing from map | Search / Safety | high | implemented / partial | Retrieved pages or docs may contain instructions that should not control the system. | `SearchDecision.retrieval_safety` classifies retrieved content as evidence only; `SearchReceipt.retrieval_safety_result` records source-instruction authority rejection and prompt-injection guard application. | Add worker-side enforcement receipt when retrieval worker exists. |
| GAP-WORKER-001 | Worker contract matrix incomplete | Worker | high | implemented / partial | Each worker needs allowed inputs, secrets, network scope, tenant scope, timeout, retry, and receipts. | `ReadOnlyWorkerBinding` defines the first worker contract matrix for local repo inspection, including denied network, secrets, writes, connector authority, terminal closure, and raw output retention. `ReadOnlyWorkerLeasePreflight` binds that path to temporal lease evidence. `ReadOnlyWorkerRehearsalReceipt` records local dry-run evidence while keeping dispatch and effects denied. The personal-assistant console receipt panel now projects that rehearsal receipt through a read-only viewer binding. | Design runtime receipt emission handoff before enabling any worker runtime. |
| GAP-WORKER-002 | Read-only first worker path not selected | Worker / Product | medium | implemented / partial | The first pilot path should prove the spine without mutation risk. | `read_only_repo_inspection` is selected as the first worker path and remains dispatch-blocked until lease evidence exists; rehearsal evidence is now contract-bound and visible in the console receipt panel without runtime dispatch. | Design runtime receipt emission handoff before enabling any worker runtime. |
| GAP-WORKER-003 | Partial execution recovery rules incomplete | Worker / Evidence | high | implemented / partial | Worker failures can leave unclear state. | `WorkerFailureReceipt` records failed steps, partial effects, unknown effects, rollback refs, recovery refs, and no-success/no-terminal-closure guards; `ReadOnlyWorkerBinding`, `ReadOnlyWorkerLeasePreflight`, `ReadOnlyWorkerRehearsalReceipt`, and the console receipt viewer binding make failure, lease, rehearsal, and operator-visible evidence explicit for the selected first worker path. | Design runtime receipt emission handoff before enabling any worker runtime. |
| GAP-EVIDENCE-001 | Receipt taxonomy not implemented end-to-end | Evidence | high | partial | Every stage needs evidence or a blocker. | Message, identity, interpretation, search decision, search receipt, worker failure, plan, approval, worker, closure, and final receipts linked by trace. | Continue from interpretation, search, and worker failure receipts to user-facing receipt viewer. |
| GAP-EVIDENCE-002 | Success-claim gate needs UI enforcement | Evidence / UI | high | missing / partial | The UI must not say work succeeded without terminal evidence. | UI reads terminal certificate or explicit blocker. | Add receipt-aware response state. |
| GAP-EVIDENCE-003 | Delivery failure separated from execution failure | Evidence / Channel | medium | missing / partial | A task can succeed while Slack/WhatsApp delivery fails. | Distinct execution status and delivery status in receipt. | Add delivery receipt field. |
| GAP-ADMIN-001 | Tenant/user admin console missing | Admin | high | missing / unknown | Operators need to manage users, tenants, roles, policies, budgets, and workers. | Admin UI with scoped controls and audit trail. | Map admin console components. |
| GAP-ADMIN-002 | Policy and budget manager missing | Admin / Governance | high | missing / unknown | Governance needs operator-controlled limits. | UI/API for policies, budgets, and approvals. | Draft policy/budget admin map. |
| GAP-DEPLOY-001 | Deployment readiness remains deferred | Deployment | high | deferred | Foundation Mode must not become accidental deployment claim. | Deployment evidence boundaries satisfied by future receipts. | Keep deployment work behind deferral docs. |
| GAP-LEGAL-001 | Legal/business/customer readiness remains deferred | Legal / Product | high | deferred | Product claims can create obligations before readiness. | Legal/business docs and approvals. | Keep public/customer claims out of mapbook. |

## 3. Highest-priority local build order

```text
1. Review mapbook for Foundation Mode language.
2. Add persisted receipt viewer for InterpretedRequest and InterpretationReceipt.
3. Design web-only Governed Goal Intake.
4. Add budget and tool display fields to Plan Preview before UI binding.
5. Design runtime receipt emission handoff for the selected read-only first worker path.
6. Build Receipt Viewer for interpretation, plan, approval, execution, and denial receipts.
7. Add one external channel only after web identity and approval work.
```

## 4. Edge-case backlog

```text
EDGE-001: Vague request such as `fix it`.
EDGE-002: Mixed question and action in one message.
EDGE-003: Casual `yes` approval without request ID.
EDGE-004: Duplicate webhook replay.
EDGE-005: Cross-channel approval from a different identity.
EDGE-006: Expired approval response.
EDGE-007: Search API failure.
EDGE-008: Search result conflict.
EDGE-009: Prompt injection in retrieved content.
EDGE-010: Worker timeout after partial execution.
EDGE-011: Execution success but response delivery failure.
EDGE-012: Tenant mismatch.
EDGE-013: Memory leakage across users or tenants.
EDGE-014: User cancels after queue but before execution.
EDGE-015: Policy changes while task is waiting for approval.
```

## 5. Audit result

Constructive delta:

```text
The register converts curiosity-level architecture discussion into trackable local gaps with IDs, risks, closure evidence, and next safe steps.
```

Fracture delta:

```text
The register confirms that product UI, durable interpretation, search cost controls, runtime receipt emission, and channel hardening are still not closed.
```

Refinement:

```text
Do not build every channel or worker first.
Close the web Ask-to-Receipt spine first, then expand one safe capability at a time.
```
