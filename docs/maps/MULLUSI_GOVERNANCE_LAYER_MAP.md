# Mullusi Governance Layer Map

Status: Foundation Mode
Scope: private governance map for policy, budget, approval, command, plan, and causal closure. This document does not claim runtime completeness or deployment readiness.

## 1. Governance purpose

Governance decides whether an interpreted request may become an answer, clarification, denial, plan, approval request, or execution.

```text
InterpretedRequest
-> policy gate
-> budget gate
-> authority check
-> approval route when needed
-> command ledger
-> plan ledger
-> causal closure
```

Decision rule:

```text
LLM proposes.
Governance disposes.
Receipts prove.
```

## 2. Governance components

| Component | Purpose | Inputs | Outputs | Status | Next Step |
| --- | --- | --- | --- | --- | --- |
| Policy Engine | allow, deny, constrain, or require approval | InterpretedRequest, plan, actor, tenant | PolicyReceipt | implemented / partial | Map user-friendly denial explanations. |
| Budget Gate | decide whether search, LLM, worker, or execution cost is allowed | estimate, tenant budget, task class | BudgetReceipt | implemented | Plan Review exposes redacted preview, witness, explicit `capability_cost_model` estimates, and optional tenant budget-report evidence with read-only drilldowns. |
| Authority Mesh | check actor, role, channel, tenant, and action authority | actor, tenant, channel, risk | authority decision | partial | Bind `ChannelApprovalStrengthResult` into channel-native adapters and cross-channel handoff receipts. |
| Approval Router | request, record, expire, or deny approval | governed plan, actor, channel | ApprovalReceipt | implemented / partial | Extend approval-strength witnesses from HTTP callbacks into channel-native adapters and admin policy surfaces. |
| Command Ledger | hold command state and idempotency | approved command | ledger record | implemented / partial | Add richer Current Task filters after worker path selection. |
| Plan Builder | create actionable plan preview | action intent and slots | CapabilityPlanPreview | implemented / partial | Budget/tool display is exposed in preview and Plan Review with explicit plan-cost estimate sources and optional tenant budget-report overlays. |
| Plan Ledger | retain plan versions and changes | plan, correction, approval | plan trace | partial | Record re-plan on scope change. |
| Causal Closure Kernel | validate final evidence | worker receipts, plan, policy | ClosureReceipt or blocker | implemented / partial | Block success without terminal certificate. |

## 3. Decision paths

```text
question
-> policy check
-> budget check if search or provider use is needed
-> answer receipt

action_request
-> plan draft
-> policy check
-> budget check
-> authority check
-> approval if required
-> execution if approved
-> closure receipt

blocked_request
-> structured denial
-> denial receipt
```

## 4. Approval strength matrix

| Risk Tier | Example | Minimum Approval |
| --- | --- | --- |
| low | search docs, inspect repository | contextual approval with tenant and actor binding |
| medium | inspect private tenant data or schedule low-risk work | request-bound approval with tenant, actor, request ID, and freshness |
| high | deploy, delete, send external message | operator-bound approval with actor authority and operator session |
| critical | payment, account change, tenant boundary change | dual-control approval with operator-bound authority |

## 5. No-bypass rules

```text
No execution before policy and budget gates.
No action approval from unbound casual text.
No external send without approval when the action represents the user.
No deployment, deletion, account change, payment, or tenant change without explicit approval.
No success response without closure evidence.
No private or secret values in user-facing denial, receipt, or logs.
```

## 6. Failure outputs

| Failure | Required Output |
| --- | --- |
| policy deny | PolicyReceipt and DenialReceipt |
| budget deny | BudgetReceipt and DenialReceipt |
| approval expired | ApprovalReceipt with expired decision |
| actor lacks authority | DenialReceipt with safe explanation |
| plan missing evidence | blocker and PlanReceipt |
| closure evidence incomplete | ClosureReceipt with missing evidence blocker |
