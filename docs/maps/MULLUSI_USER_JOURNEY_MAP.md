# Mullusi User Journey Map

Status: Foundation Mode
Scope: private product journey map. This document does not claim launch, customer access, support, commercial, legal, deployment, or production readiness.

## 1. Journey purpose

The user journey starts from a governed goal intake, not raw chat-to-tool execution.

```text
User arrives
-> states a question or goal
-> sees interpretation
-> clarifies or reviews a plan
-> approves only when needed
-> watches current task state
-> reviews evidence receipt
```

## 2. Required screens

| Screen | Purpose | Required State | Current Status | Next Step |
| --- | --- | --- | --- | --- |
| Governed Goal Intake | accept a question or goal | RECEIVED | missing / unknown | Build web-only intake before external channels. |
| Current Task | show active, blocked, approved, executing, or closed task | QUEUED to CLOSED | missing / unknown | Bind display states to command ledger states. |
| Plan Review | show plan, tools, risk, budget, and approval need | PLAN_DRAFTED | missing / partial | Map `GovernedPlan` to user-facing preview. |
| Approval Center | approve, deny, expire, or re-request approval | APPROVAL_PENDING | missing / partial | Bind approvals to request ID, actor, tenant, and risk tier. |
| Execution Status | show worker progress and blockers | EXECUTING | missing / unknown | Display worker receipts and partial completion status. |
| Evidence Receipt Viewer | show interpreted, planned, approved, executed, denied, or blocked evidence | RECEIPT_FINALIZED | missing / unknown | Render receipt chain and terminal certificate. |
| Search / Answer Viewer | show answer, citations, freshness, and uncertainty | ANSWER_DRAFTED | missing / partial | Display SearchReceipt and evidence freshness. |
| Connectors | show configured and deferred connectors | AUTHENTICATED | missing / unknown | Keep credentials out of public docs and receipts. |
| Worker Status | show worker capability, limits, and last receipt | QUEUED / EXECUTING | missing / unknown | Start with one read-only worker. |
| Policy / Budget Settings | show limits and approval requirements | POLICY_EVALUATED / BUDGET_EVALUATED | missing / unknown | Map policy and budget fields before UI work. |
| Admin Console | manage users, tenants, roles, policies, and receipts | authenticated admin | missing / unknown | Use the admin map before implementation. |

## 3. Primary journeys

### 3.1 Question journey

```text
Goal Intake
-> Interpretation Preview
-> Search / Answer Viewer when evidence is needed
-> Evidence Receipt Viewer
```

Required controls:

```text
Do not create an execution plan for a pure question.
Do not search if local or cached evidence is sufficient.
Show freshness and uncertainty when evidence is stale or conflicting.
```

### 3.2 Vague action journey

```text
Goal Intake
-> Interpretation Preview
-> Clarification Question
-> wait for user response
```

Required controls:

```text
Ask the fewest questions needed for the next safe step.
Allow read-only diagnosis as a safe default only when policy permits it.
Do not mutate files, accounts, DNS, deployment state, or external channels.
```

### 3.3 Approved action journey

```text
Goal Intake
-> Interpretation Preview
-> Plan Review
-> Policy and Budget Gate
-> Approval Center
-> Current Task
-> Evidence Receipt Viewer
```

Required controls:

```text
Approval must bind to request_id, tenant_id, actor_id, channel, risk tier, and expiration.
Casual messages like yes are invalid unless bound to an active approval request.
Success is visible only after terminal evidence exists.
```

### 3.4 Cancellation or correction journey

```text
Current Task
-> user correction or cancellation
-> pause, cancel, deny, or re-plan
-> receipt update
```

Required controls:

```text
Correction creates a new interpretation or plan receipt.
Cancellation is best-effort once execution has started.
Partial completion is reported as partial completion, not success.
```

## 4. UI status rules

```text
Every task has exactly one visible state.
Every visible state maps to a gateway, ledger, worker, or receipt state.
Every failure has a blocker, denial, or recovery path.
No UI string may claim production readiness from this mapbook alone.
```
