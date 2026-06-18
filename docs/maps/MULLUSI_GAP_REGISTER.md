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
| GAP-UI-001 | Governed Goal Intake UI missing | User Surface | high | implemented / partial | First-time users need a universal ask/goal entry before Current Task makes sense. | `/operator/goal-intake` renders a web-only operator goal form; `/operator/goal-intake/preview` stores a bounded pending preview and renders redacted `CapabilityPlanPreview`; `/operator/goal-intake/approve` submits an explicit internal handoff into the governed router; `/operator/goal-intake/deny` consumes the preview without command writes; Current Task exposes approved handoff state by preview id, goal hash, plan id, step id, and approval request id; `/operator/plan-review` surfaces preview history without raw-goal echo; `channel_approval_strength_policy.foundation` defines request-bound and cross-channel approval strength; `/webhook/approve/{request_id}` now blocks high-risk external callback approval without an operator-bound session witness; `/operator/approvals/read-model` and `/operator/approvals/{request_id}` expose approval-strength decision, observed strength, required strength, policy, and controls. | Extend approval-strength enforcement to channel-native adapter approval flows. |
| GAP-UI-002 | Current Task state view missing | User Surface | medium | implemented / partial | Users need to see running, blocked, approved, denied, or completed task state. | `/operator/current-task/read-model` and `/operator/current-task` classify command states into received, active, waiting, review, blocked, and completed task states; approved Goal Intake handoffs project `goal_intake_preview_id`, `goal_hash`, `plan_id`, `plan_step_id`, and `approval_request_id`; `/operator/current-task/approval` resolves request-bound approvals and resumes waiting plans when closure evidence is available; operator navigation links Current Task, Approval History, Plan Review, and Receipt Viewer. | Add richer Current Task filters after worker path selection. |
| GAP-UI-003 | Receipt Viewer missing | User Surface / Evidence | high | implemented / partial | Users need visible proof of what was interpreted, approved, executed, blocked, and evidenced. | `/operator/receipts/read-model`, `/operator/receipts`, and `/operator/receipts/{command_id}` render bounded command receipt groups, detail drilldowns, and filters for receipt type, receipt status, task status, and bounded search without raw payload text. `/operator/approvals/read-model`, `/operator/approvals`, and `/operator/approvals/{request_id}` reconstruct approval history from command transition witnesses, surface approval-strength witness fields when present, and link approval receipts back to approval detail and current task recovery surfaces. `/operator/plan-review/read-model`, `/operator/plan-review`, `/operator/plan-review/{plan_id}/receipts`, and `/operator/plan-review/{plan_id}/receipts/read-model` expose redacted plan, recovery, budget evidence, explicit plan-cost estimate sources, plan evidence bundles when certified, and step command receipt groups without raw-goal echo. `/operator/plan-review/budget/{tenant_id}` and `/operator/plan-review/budget/{tenant_id}/read-model` provide read-only tenant budget drilldowns. Receipt classes include interpretation, search-decision, search-evidence, plan-step, approval, denial, worker/capability, worker-failure, delivery-observation, command-event, terminal-certificate, and proof refs. | Extend worker, search, and external adapter drilldowns without exposing raw payload text. |
| GAP-COMM-001 | Production channel adapter hardening incomplete | Communication | high | partial | External channels can create identity, replay, approval, and delivery risks. | One channel has signature validation, deduplication, tenant binding, and request-ID approvals. | Harden one channel after web flow. |
| GAP-COMM-002 | Channel approval-strength policy partially wired | Communication / Governance | high | implemented / partial | A casual message like `yes` should not approve high-risk actions without bound context. | `gateway/channel_approval_strength.py`, `schemas/channel_approval_strength_policy.schema.json`, `examples/channel_approval_strength_policy.foundation.json`, and `scripts/validate_channel_approval_strength_policy.py` define default-block channel trust, request-bound medium approvals, operator-bound high-risk approvals, dual-control critical approvals, expired approval blockers, and cross-channel binding witnesses. `GatewayRouter.handle_external_approval_callback` now evaluates `ChannelApprovalStrengthResult` before resolving HTTP approval callbacks, leaves under-strength approvals pending, returns denial metadata, and stamps successful approval command events with the strength witness. | Extend the same strength gate to channel-native adapter approvals and explicit cross-channel binding receipts. |
| GAP-COMM-003 | Cross-channel conversation binding incomplete | Communication | medium | missing / partial | A user may start in web and respond in Slack or WhatsApp; this can cause identity ambiguity. | Cross-channel binding rules and audit receipt. | Define allowed cross-channel handoff cases. |
| GAP-INTERP-001 | Durable InterpretedRequest object missing | Interpretation | high | implemented / partial | User text cannot safely become plans without an auditable interpretation object. | `gateway/interpretation.py` and `schemas/interpreted_request.schema.json` record intent, slots, confidence, risk, action/search need, and raw message hash. | Add UI readback when the product surface is built. |
| GAP-INTERP-002 | Interpretation receipt missing | Interpretation / Evidence | high | implemented / partial | The system needs proof of what it believed the user meant. | `InterpretationReceipt` is attached to command payloads and router response metadata; `schemas/interpretation_receipt.schema.json` validates the receipt shape. | Add persisted receipt viewer. |
| GAP-INTERP-003 | Clarification engine incomplete | Interpretation | high | implemented / partial | Vague goals must not trigger unsafe or wrong execution. | `ClarificationRequest` blocks ambiguous action-like input before command creation and returns one focused user question with safe default `no_execution`. | Expand slot requirements beyond the first vague action path. |
| GAP-INTERP-004 | LLM-assisted interpretation not bounded | Interpretation / LLM | medium | partial | LLMs can misclassify user intent or overstate available authority. | Deterministic rules run first; LLM output validated as proposal only. | Add LLM-assisted proposal lane behind deterministic interpretation. |
| GAP-GOV-001 | Ask-to-plan preview needs product binding | Governance / UI | high | implemented / partial | Users need to see risk, budget, tools, and approvals before action. | `CapabilityPlanPreview` exposes redacted read-only plan topology, risk, approval, evidence obligations, budget display state, and tool requirements; Goal Intake approve/deny forms route by preview id only; approved previews use an internal `operator_goal_intake` channel for governed command creation; Current Task exposes the approval request and recovery controls without raw-goal echo; Plan Review records preview, failed, certified, and recovered plan rows; `channel_approval_strength_policy.foundation` defines the approval-strength contract; `/webhook/approve/{request_id}` records approval-strength metadata during external callback resolution; operator approval history and detail read models expose that strength evidence. | Bind approval-strength policy controls into channel-native adapters and future admin screens. |
| GAP-GOV-002 | Budget gate user display missing | Governance / UI | medium | implemented | Search and LLM usage can become expensive without visible limits. | `CapabilityPlanPreview` exposes budget estimate state, estimate source, used-cost state, required budget-gate steps, tool-level estimated cost, and tool requirements before approval without execution authority; registry-backed passports carry `cost_model.max_estimated_cost` into preview `capability_cost_model` estimates while unpriced capabilities remain explicit `not_calculated`. `/operator/plan-review` shows `budget_required`, `budget_gate`, estimate state/source, used/limit/remaining cost fields, required budget steps, budget report drilldown links, and budget evidence source from previews, failed plan witnesses, or optional `tenant_budget_report` overlays. Reporter failures surface as `tenant_budget_report_error` instead of silent omission. | Keep search-specific budget policy separate under GAP-SEARCH-003. |
| GAP-GOV-003 | Policy denial explanation needs user-friendly composer | Governance / Response | medium | partial | Denials must be understandable without leaking internals. | Response composer produces safe, plain denial explanations. | Add denial response templates. |
| GAP-SEARCH-001 | Search need classifier missing | Search | medium | implemented / partial | Every chat message should not trigger search. | `gateway/search_governance.py` classifies no-search, cache, local search, light web search, and deep search; `schemas/search_decision_receipt.schema.json` and `tests/test_gateway/test_search_governance.py` validate the decision receipt; `gateway/causal_closure_kernel.py` attaches and durably records search decision receipts for live `enterprise.knowledge_search` execution before proof validation; `gateway/operator_receipt_viewer.py` exposes `search_decision_receipt` and `search_receipt` as dedicated receipt types with query-hash, freshness, budget, retrieval-authority, citation, conflict, and safety drilldowns while tests verify raw query text and source bodies are not exposed; `gateway/read_only_search_worker.py` repeats the pattern for local text-like evidence-only search behind matching SearchDecisionReceipt and WorkerReceipt-bound SearchReceipt metadata. | Keep future external retrieval adapters behind the same evidence-only source-instruction denial contract. |
| GAP-SEARCH-002 | Freshness gate missing | Search | medium | implemented / partial | Current-info questions need freshness; stable facts may not. | `SearchDecisionReceipt.freshness_state` records `not_required`, `cache_fresh`, or `source_required`; `SearchReceipt.freshness_result` records post-decision freshness status before current claims; `enterprise.knowledge_search` requires `search_freshness_checked`; the closure kernel attaches the decision receipt to live search execution. | Bind tenant-specific source freshness policy into future external retrieval adapters. |
| GAP-SEARCH-003 | Search cost gate missing | Search / Budget | high | implemented / partial | Search-backed chat can become expensive if unbounded. | Search decision receipts record estimated cost, budget limit, budget state, and blocked reasons; `SearchDecision.budget_decision` blocks deep retrieval on BudgetUnknown or missing approval; `enterprise.knowledge_search` requires `budget_reserved` and `search_budget_checked` and carries a `cost_model.max_estimated_cost` for plan preview; live search execution receives a receipt before proof validation. | Connect tenant-specific budget policy to search decision request construction. |
| GAP-SEARCH-004 | Retrieval prompt-injection handling missing from map | Search / Safety | high | implemented / partial | Retrieved pages or docs may contain instructions that should not control the system. | Search decision receipts enforce `retrieval_authority=evidence_only` and `retrieval_instruction_authority_allowed=false`; `enterprise.knowledge_search` requires `retrieval_evidence_only`; local read-only search worker results mark source instruction markers; `SearchReceipt.retrieval_safety_result` records prompt-injection detection, source-instruction authority denial, `instruction_authority_rejected` retrieval errors, and bounded local polarity conflicts without storing retrieved content bodies. | Preserve evidence-only authority in answer synthesis, citation receipts, and external retrieval adapters. |
| GAP-WORKER-001 | Worker contract matrix incomplete | Worker | high | implemented / partial | Each worker needs allowed inputs, secrets, network scope, tenant scope, timeout, retry, and receipts. | `repository.inspect_read_only`, `document.inspect_read_only`, and local `enterprise.knowledge_search` are implemented with worker mesh leases and receipts, path containment, scan bounds, deterministic traversal, secret redaction, zero network allowlist, zero spend, failure receipts, and focused tests in `tests/test_gateway/test_read_only_repository_worker.py`, `tests/test_gateway/test_read_only_document_worker.py`, `tests/test_gateway/test_read_only_search_worker.py`, and `tests/test_gateway/test_worker_failure_receipt.py`. Runtime receipt handoff, dry-run, runner binding, receipt candidate, schema-binding witness, receipt-store write-path, runner registration, dispatch endpoint registration, emitter registration, schema-binding activation, receipt-store activation, and runtime receipt emission admission witnesses remain contract-bound without runtime dispatch. | Define the runtime dispatch admission witness before enabling any worker runtime. |
| GAP-WORKER-002 | Read-only first worker path not selected | Worker / Product | medium | implemented / partial | The first pilot path should prove the spine without mutation risk. | `repository.inspect_read_only` is selected in `examples/read_only_first_worker_path.foundation.json`, validated by `schemas/read_only_first_worker_path.schema.json`, `scripts/validate_read_only_first_worker_path.py`, and `tests/test_validate_read_only_first_worker_path.py`, and implemented by `gateway/read_only_repository_worker.py`; `document.inspect_read_only` and local `enterprise.knowledge_search` repeat the read-only pattern through their selection schemas, examples, validators, and workers. Runtime dispatch remains blocked until live runner registration, dispatch endpoint, emitter registration, schema-binding activation, receipt-store activation, runtime receipt emission admission, runtime dispatch admission, active lease, UAO, `Phi_gov`, effect reconciliation, and failure-receipt evidence exist. | Keep mutation, network, secrets, external tenant resources, rich parsing, web retrieval, and spend blocked while extending worker drilldowns. |
| GAP-WORKER-003 | Partial execution recovery rules incomplete | Worker / Evidence | high | implemented / partial | Worker failures can leave unclear state. | `schemas/worker_failure_receipt.schema.json` and `gateway/worker_failure_receipt.py` classify rejected-before-handler, failed-after-handler, failed-during-handler, partial-completion, and unknown failure states; failure receipts preserve source worker receipt hashes, recovery refs, evidence refs, safe-halt recovery for partial completion, and non-terminal closure discipline. Current Task response state now exposes blocker states instead of success claims, while runtime witness artifacts make failure, lease, rehearsal, handoff, dry-run emitter, runner-binding, schema-binding, runtime receipt candidate, receipt-store write-path, runner registration, dispatch endpoint registration, runtime receipt emitter registration, schema-binding activation, receipt-store activation, runtime receipt emission admission, and operator-visible evidence explicit for the selected first worker path. | Thread worker-failure receipt ids into future worker UI drilldowns and close runtime dispatch admission before dispatch. |
| GAP-EVIDENCE-001 | Receipt taxonomy not implemented end-to-end | Evidence | high | implemented / partial | Every stage needs evidence or a blocker. | Message, identity, interpretation, search-decision, search-evidence, plan, approval, worker, worker-failure, denial, delivery-observation, closure, and final receipts linked by trace; approval history is reconstructed from persisted command witnesses and cross-linked from approval receipts; Plan Review reconstructs preview, failure, recovery, certificate, explicit cost-estimate source, optional tenant budget-report evidence, plan evidence bundle exports, and step command receipt groups with redacted budget fields and tenant budget drilldowns; Current Task exposes receipt-aware response state and terminal-certificate success gates; delivery receipts expose execution status and delivery status as separate fields; operator receipts expose search-decision and search-evidence drilldowns by receipt type/status without raw-query or source-body exposure. | Add worker-failure receipt ids to future worker UI drilldowns. |
| GAP-EVIDENCE-002 | Success-claim gate needs UI enforcement | Evidence / UI | high | implemented | The UI must not say work succeeded without terminal evidence. | Current Task exposes `response_state`, `response_evidence_state`, `response_claim_allowed`, `response_terminal_certificate_id`, `response_evidence_refs`, and `response_blocker`; completed responses without a terminal certificate remain `awaiting_terminal_evidence` with claim authority denied, verified completions require a terminal-certificate ref, and blocked tasks surface explicit blocker receipt refs when available. `gateway/operator_receipt_viewer.py` only allows `completed_verified` when a terminal certificate exists and marks late lifecycle rows without certificates as `awaiting_terminal_evidence`. | Keep future response composers bound to `response_claim_allowed` and terminal or blocker evidence refs. |
| GAP-EVIDENCE-003 | Delivery failure separated from execution failure | Evidence / Channel | medium | implemented / partial | A task can succeed while Slack/WhatsApp delivery fails. | `gateway/router.py` records post-response delivery observations as `RESPONSE_EVIDENCE_CLOSED` command events only after `RESPONDED`; `gateway/operator_receipt_viewer.py` exposes `execution_status`, `delivery_status`, `delivery_error_type`, `delivery_succeeded`, `delivery_attempted`, and `execution_delivery_separated`; tests cover successful delivery and adapter failure without collapsing execution closure into delivery status. | Extend the same delivery witness pattern to future external channel adapters. |
| GAP-ADMIN-001 | Tenant/user admin console missing | Admin | high | missing / unknown | Operators need to manage users, tenants, roles, policies, budgets, and workers. | Admin UI with scoped controls and audit trail. | Map admin console components. |
| GAP-ADMIN-002 | Policy and budget manager missing | Admin / Governance | high | missing / unknown | Governance needs operator-controlled limits. | UI/API for policies, budgets, and approvals. | Draft policy/budget admin map. |
| GAP-DEPLOY-001 | Deployment readiness remains deferred | Deployment | high | deferred | Foundation Mode must not become accidental deployment claim. | Deployment evidence boundaries satisfied by future receipts. | Keep deployment work behind deferral docs. |
| GAP-LEGAL-001 | Legal/business/customer readiness remains deferred | Legal / Product | high | deferred | Product claims can create obligations before readiness. | Legal/business docs and approvals. | Keep public/customer claims out of mapbook. |

## 3. Highest-priority local build order

```text
1. Review mapbook for Foundation Mode language.
2. Add one external channel only after web identity and approval work.
3. Extend channel approval-strength policy from HTTP callbacks to channel-native adapters.
4. Bind source-level freshness evidence to future search result receipts.
5. Harden persisted receipt viewer coverage for InterpretedRequest, InterpretationReceipt, Plan Review, approval history, worker, search, and receipt exports.
6. Keep budget, tool, freshness, and search safety controls visible in Plan Preview and Plan Review.
7. Define the runtime dispatch admission witness for the selected read-only first worker path.
8. Map tenant, policy, budget, worker, and receipt admin screens.
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
The register confirms that channel hardening, source-level search freshness evidence, channel-native approval-strength enforcement, runtime dispatch admission, live receipt-store write path, durable interpretation readback, Plan Review receipt export hardening, and admin surfaces are still not fully closed.
```

Refinement:

```text
Do not build every channel or worker first.
Close the web Ask-to-Receipt spine first, then expand one safe capability at a time.
```
