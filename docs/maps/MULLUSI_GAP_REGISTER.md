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
| GAP-UI-001 | Governed Goal Intake UI missing | User Surface | high | implemented / partial | First-time users need a universal ask/goal entry before Current Task makes sense. | `/operator/goal-intake` renders a web-only operator goal form; `/operator/goal-intake/preview` stores a bounded pending preview and renders redacted `CapabilityPlanPreview`; `/operator/goal-intake/approve` submits an explicit internal handoff into the governed router; `/operator/goal-intake/deny` consumes the preview without command writes; Current Task exposes approved handoff state by preview id, goal hash, plan id, step id, and approval request id; `/operator/plan-review` surfaces preview history without raw-goal echo. | Add cross-channel approval-strength policy after web flow is stable. |
| GAP-UI-002 | Current Task state view missing | User Surface | medium | implemented / partial | Users need to see running, blocked, approved, denied, or completed task state. | `/operator/current-task/read-model` and `/operator/current-task` classify command states into received, active, waiting, review, blocked, and completed task states; approved Goal Intake handoffs project `goal_intake_preview_id`, `goal_hash`, `plan_id`, `plan_step_id`, and `approval_request_id`; `/operator/current-task/approval` resolves request-bound approvals and resumes waiting plans when closure evidence is available; operator navigation links Current Task, Approval History, Plan Review, and Receipt Viewer. | Add richer Current Task filters after worker path selection. |
| GAP-UI-003 | Receipt Viewer missing | User Surface / Evidence | high | implemented / partial | Users need visible proof of what was interpreted, approved, executed, blocked, and evidenced. | `/operator/receipts/read-model`, `/operator/receipts`, and `/operator/receipts/{command_id}` render bounded command receipt groups, detail drilldowns, and filters for receipt type, receipt status, task status, and bounded search without raw payload text. `/operator/approvals/read-model`, `/operator/approvals`, and `/operator/approvals/{request_id}` reconstruct approval history from command transition witnesses and link approval receipts back to approval detail and current task recovery surfaces. `/operator/plan-review/read-model`, `/operator/plan-review`, `/operator/plan-review/{plan_id}`, `/operator/plan-review/{plan_id}/receipts`, and `/operator/plan-review/{plan_id}/receipts/read-model` expose redacted plan, recovery, budget evidence, explicit plan-cost estimate sources, plan evidence bundles when certified, and step command receipt groups without raw-goal echo. `/operator/plan-review/budget/{tenant_id}` and `/operator/plan-review/budget/{tenant_id}/read-model` provide read-only tenant budget drilldowns. Receipt classes include interpretation, search-decision, plan-step, approval, denial, worker/capability, delivery-observation, command-event, terminal-certificate, and proof refs. | Add worker-failure receipt ids to future worker UI drilldowns. |
| GAP-COMM-001 | Production channel adapter hardening incomplete | Communication | high | partial | External channels can create identity, replay, approval, and delivery risks. | One channel has signature validation, deduplication, tenant binding, and request-ID approvals. | Harden one channel after web flow. |
| GAP-COMM-002 | Channel approval-strength rules missing | Communication / Governance | high | missing / partial | A casual message like `yes` should not approve high-risk actions without bound context. | Approval matrix by channel, action risk, tenant, actor, and request ID. | Draft channel trust policy. |
| GAP-COMM-003 | Cross-channel conversation binding incomplete | Communication | medium | missing / partial | A user may start in web and respond in Slack or WhatsApp; this can cause identity ambiguity. | Cross-channel binding rules and audit receipt. | Define allowed cross-channel handoff cases. |
| GAP-INTERP-001 | Durable InterpretedRequest object missing | Interpretation | high | implemented / partial | User text cannot safely become plans without an auditable interpretation object. | `gateway/interpretation.py` and `schemas/interpreted_request.schema.json` record intent, slots, confidence, risk, action/search need, and raw message hash. | Add UI readback when the product surface is built. |
| GAP-INTERP-002 | Interpretation receipt missing | Interpretation / Evidence | high | implemented / partial | The system needs proof of what it believed the user meant. | `InterpretationReceipt` is attached to command payloads and router response metadata; `schemas/interpretation_receipt.schema.json` validates the receipt shape. | Add persisted receipt viewer. |
| GAP-INTERP-003 | Clarification engine incomplete | Interpretation | high | implemented / partial | Vague goals must not trigger unsafe or wrong execution. | `ClarificationRequest` blocks ambiguous action-like input before command creation and returns one focused user question with safe default `no_execution`. | Expand slot requirements beyond the first vague action path. |
| GAP-INTERP-004 | LLM-assisted interpretation not bounded | Interpretation / LLM | medium | partial | LLMs can misclassify user intent or overstate available authority. | Deterministic rules run first; LLM output validated as proposal only. | Add LLM-assisted proposal lane behind deterministic interpretation. |
| GAP-GOV-001 | Ask-to-plan preview needs product binding | Governance / UI | high | implemented / partial | Users need to see risk, budget, tools, and approvals before action. | `CapabilityPlanPreview` exposes redacted read-only plan topology, risk, approval, evidence obligations, budget display state, and tool requirements; Goal Intake approve/deny forms route by preview id only; approved previews use an internal `operator_goal_intake` channel for governed command creation; Current Task exposes the approval request and recovery controls without raw-goal echo; Plan Review records preview, failed, certified, and recovered plan rows. | Add cross-channel approval-strength policy. |
| GAP-GOV-002 | Budget gate user display missing | Governance / UI | medium | implemented | Search and LLM usage can become expensive without visible limits. | `CapabilityPlanPreview` exposes budget estimate state, estimate source, used-cost state, required budget-gate steps, tool-level estimated cost, and tool requirements before approval without execution authority; registry-backed passports carry `cost_model.max_estimated_cost` into preview `capability_cost_model` estimates while unpriced capabilities remain explicit `not_calculated`. `/operator/plan-review` shows `budget_required`, `budget_gate`, estimate state/source, used/limit/remaining cost fields, required budget steps, budget report drilldown links, and budget evidence source from previews, failed plan witnesses, or optional `tenant_budget_report` overlays. Reporter failures surface as `tenant_budget_report_error` instead of silent omission. | Keep search-specific budget policy separate under GAP-SEARCH-003. |
| GAP-GOV-003 | Policy denial explanation needs user-friendly composer | Governance / Response | medium | partial | Denials must be understandable without leaking internals. | Response composer produces safe, plain denial explanations. | Add denial response templates. |
| GAP-SEARCH-001 | Search need classifier missing | Search | medium | implemented / partial | Every chat message should not trigger search. | `SearchDecision` and `SearchDecisionReceipt` separate no-search, cache, local search, light web search, deep search, and blocked states before retrieval; `gateway/causal_closure_kernel.py` attaches and durably records search decision receipts for live `enterprise.knowledge_search` execution before proof validation; `gateway/operator_receipt_viewer.py` exposes `search_decision_receipt` with query-hash, freshness, budget, and retrieval-authority drilldowns while tests verify raw query text is not exposed. | Repeat the read-only worker contract pattern for search worker execution. |
| GAP-SEARCH-002 | Freshness gate missing | Search | medium | implemented / partial | Current-info questions need freshness; stable facts may not. | `SearchDecision.freshness`, `SearchDecisionReceipt.freshness_state`, and `SearchReceipt.freshness_result` record pre-decision and post-decision freshness status; `enterprise.knowledge_search` requires `search_freshness_checked`. | Bind source-level freshness evidence to future search result receipts. |
| GAP-SEARCH-003 | Search cost gate missing | Search / Budget | high | implemented / partial | Search-backed chat can become expensive if unbounded. | Search decision contracts record estimated cost, budget limit, budget state, and blocked reasons; deep retrieval is blocked on BudgetUnknown or missing approval, and `enterprise.knowledge_search` requires `budget_reserved` and `search_budget_checked`. | Connect tenant-specific budget policy to search decision request construction. |
| GAP-SEARCH-004 | Retrieval prompt-injection handling missing from map | Search / Safety | high | implemented / partial | Retrieved pages or docs may contain instructions that should not control the system. | `SearchDecision.retrieval_safety`, `SearchDecisionReceipt.retrieval_authority=evidence_only`, and `SearchReceipt.retrieval_safety_result` reject source-instruction authority and preserve retrieved material as evidence only. | Preserve evidence-only authority in answer synthesis and citation receipts. |
| GAP-WORKER-001 | Worker contract matrix incomplete | Worker | high | implemented / partial | Each worker needs allowed inputs, secrets, network scope, tenant scope, timeout, retry, and receipts. | `repository.inspect_read_only` and `document.inspect_read_only` are implemented with worker mesh leases and receipts, path containment, scan bounds, deterministic traversal, secret redaction, zero network allowlist, zero spend, failure receipts, and focused tests; runtime receipt witness obligations remain non-authoritative until activation evidence exists. | Define the live runtime receipt schema-binding activation witness before enabling any worker runtime, then repeat the contract pattern for search worker execution. |
| GAP-WORKER-002 | Read-only first worker path not selected | Worker / Product | medium | implemented / partial | The first pilot path should prove the spine without mutation risk. | `repository.inspect_read_only` is selected and validated by the first worker path contract; `document.inspect_read_only` repeats the local read-only pattern for text-like documents through `schemas/read_only_document_worker_path.schema.json`, `examples/read_only_document_worker_path.foundation.json`, `scripts/validate_read_only_document_worker_path.py`, and `gateway/read_only_document_worker.py`, while mutation, network, secrets, external tenant resources, rich parsing, and spend remain blocked. | Keep live dispatch blocked until runner registration, dispatch endpoint, emitter registration, schema binding, live receipt-store write path, active lease, UAO, `Phi_gov`, effect reconciliation, and failure-receipt evidence exist. |
| GAP-WORKER-003 | Partial execution recovery rules incomplete | Worker / Evidence | high | implemented / partial | Worker failures can leave unclear state. | `WorkerFailureReceipt`, `schemas/worker_failure_receipt.schema.json`, and `gateway/worker_failure_receipt.py` classify failed steps, partial effects, unknown effects, rollback refs, recovery refs, safe-halt recovery, source receipt hashes, no-success guards, and no-terminal-closure discipline; Current Task response state exposes blocker states instead of success claims. | Thread worker-failure receipt ids into future worker UI drilldowns. |
| GAP-EVIDENCE-001 | Receipt taxonomy not implemented end-to-end | Evidence | high | implemented / partial | Every stage needs evidence or a blocker. | Message, identity, interpretation, search-decision, search receipt, plan, approval, worker, worker-failure, denial, delivery-observation, closure, and final receipts are linked by trace; approval history, Plan Review exports, budget evidence, receipt groups, Current Task response state, terminal-certificate gates, separated delivery status, and search-decision drilldowns are read-model visible without raw-query exposure. | Add worker-failure receipt ids to future worker UI drilldowns. |
| GAP-EVIDENCE-002 | Success-claim gate needs UI enforcement | Evidence / UI | high | implemented | The UI must not say work succeeded without terminal evidence. | `schemas/current_task_read_model.schema.json` requires response state, terminal certificate, and blocker fields; `gateway/operator_receipt_viewer.py` only allows verified completion when terminal certificate evidence exists. | Keep future response surfaces bound to the same response-state contract. |
| GAP-EVIDENCE-003 | Delivery failure separated from execution failure | Evidence / Channel | medium | implemented / partial | A task can succeed while Slack/WhatsApp delivery fails. | `gateway/router.py` records post-response delivery observations as `RESPONSE_EVIDENCE_CLOSED` command events only after `RESPONDED`; receipt viewer fields separate execution status, delivery status, delivery error type, delivery success, delivery attempt, and execution-delivery separation. | Extend the same delivery witness pattern to future external channel adapters. |
| GAP-ADMIN-001 | Tenant/user admin console missing | Admin | high | missing / unknown | Operators need to manage users, tenants, roles, policies, budgets, and workers. | Admin UI with scoped controls and audit trail. | Map admin console components. |
| GAP-ADMIN-002 | Policy and budget manager missing | Admin / Governance | high | missing / unknown | Governance needs operator-controlled limits. | UI/API for policies, budgets, and approvals. | Draft policy/budget admin map. |
| GAP-DEPLOY-001 | Deployment readiness remains deferred | Deployment | high | deferred | Foundation Mode must not become accidental deployment claim. | Deployment evidence boundaries satisfied by future receipts. | Keep deployment work behind deferral docs. |
| GAP-LEGAL-001 | Legal/business/customer readiness remains deferred | Legal / Product | high | deferred | Product claims can create obligations before readiness. | Legal/business docs and approvals. | Keep public/customer claims out of mapbook. |

## 3. Highest-priority local build order

```text
1. Review mapbook for Foundation Mode language.
2. Harden persisted receipt viewer coverage for InterpretedRequest, InterpretationReceipt, Plan Review, approval history, receipt exports, search receipts, and worker-failure receipts.
3. Stabilize web-only Governed Goal Intake and Current Task recovery links.
4. Keep budget, tool, freshness, and search safety controls visible in Plan Preview and Plan Review.
5. Define the live runtime receipt schema-binding activation witness for the selected read-only worker paths.
6. Repeat the read-only worker contract pattern for search worker execution.
7. Draft channel trust and approval-strength policy before adding one external channel.
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
The register confirms that product UI hardening, durable interpretation readback, search receipt drilldowns, Plan Review receipt export hardening, live runtime receipt schema-binding activation, live receipt-store write path, search worker contract repetition, worker-failure UI drilldowns, channel hardening, and channel approval-strength policy are still not fully closed.
```

Refinement:

```text
Do not build every channel or worker first.
Close the web Ask-to-Receipt spine first, then expand one safe capability at a time.
```
