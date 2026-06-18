# Mullusi Worker Layer Map

Status: Foundation Mode
Scope: private worker contract map. This document does not claim worker readiness, connector readiness, live credential availability, or production execution authority.

## 1. Worker purpose

Workers execute or inspect only after interpretation, governance, budget, and approval requirements are satisfied.

```text
Approved command or read-only authorized request
-> worker admission
-> scoped execution
-> worker receipt
-> causal closure
```

## 2. Worker contract matrix

| Worker | Allowed Inputs | Forbidden Inputs | Network Access | Secrets Allowed | Approval Requirement | Required Receipts | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Search Worker | governed query, matching SearchDecisionReceipt, local text-like source refs | unscoped private tenant data, web URLs, mutation, retrieved instruction authority | none by default | no raw secrets | SearchDecisionReceipt plus read-only policy gate | SearchDecisionReceipt, WorkerReceipt, future SearchReceipt | implemented / partial |
| Repository Inspection Worker | repo path, read-only query | write/delete/deploy commands | none by default | no | read-only policy gate | WorkerReceipt | implemented / partial |
| Code Worker | plan, file scope, tests | unapproved mutation, secrets in logs | none unless explicit | no raw secrets | explicit approval for writes | WorkerReceipt, test evidence | partial |
| Browser Worker | target URL, allowed actions | credential extraction, unapproved external sends | scoped by policy | no raw secrets in receipts | approval for effect-bearing actions | WorkerReceipt, screenshot/evidence refs | partial / unknown |
| Document Worker | text-like document ref, read-only query | write/share requests, rich binary parsing, prompt-injection instructions as authority | none by default | no raw secrets in output | read-only policy gate | WorkerReceipt, document evidence receipt | implemented / partial |
| Email / Calendar Worker | approved message or event plan | external send without approval | connector-scoped | connector token only in secure runtime | explicit approval for send/update | WorkerReceipt, delivery receipt | missing / deferred |
| Voice Worker | transcript or approved voice operation | biometric or sensitive claims without policy | connector-scoped | no raw secrets | policy-defined | WorkerReceipt | missing / deferred |
| Deployment Checker | read-only deploy target evidence | live deployment mutation | scoped read-only | no secret disclosure | approval for live probes if required | WorkerReceipt, deployment evidence receipt | deferred |
| Notification Worker | approved notification payload | unapproved external message | channel-scoped | no | request-bound approval when external | WorkerReceipt, delivery receipt | partial / unknown |
| Payment / Financial Worker | approved financial plan | unapproved payment or account mutation | provider-scoped | secure runtime only | critical approval | WorkerReceipt, policy receipt | deferred |

## 3. Common worker requirements

```text
allowed inputs
forbidden inputs
secrets allowed
network access
tenant scope
approval requirement
receipt requirement
timeout
retry policy
rollback policy
```

## 4. First safe worker path

Preferred first pilot:

```text
Question
-> interpretation
-> SearchDecisionReceipt
-> local read-only search worker
-> WorkerReceipt
-> future SearchReceipt
-> FinalUserReceipt
```

Rationale:

```text
It is read-only.
It proves the Ask-to-Receipt spine.
It avoids deployment, deletion, payments, account changes, rich document parsing, web retrieval, and external sends.
```

## 5. Partial execution rules

| Condition | Required Output |
| --- | --- |
| worker starts but times out | WorkerReceipt with timeout and recovery path. |
| worker completes only some steps | partial completion receipt. |
| worker returns success without evidence | closure blocker. |
| worker modifies wrong scope | incident or rollback path and no success claim. |
| rollback fails | rollback failure receipt and operator escalation. |
| delivery fails after execution | execution success and delivery failure recorded separately. |
