# Mullusi Evidence Receipt Map

Status: Foundation Mode
Scope: private receipt and audit map. This document does not claim that all receipts are implemented end-to-end or production-retained.

## 1. Evidence purpose

Every meaningful transition must produce one of:

```text
receipt
denial
blocker
clarification request
```

No stage may silently succeed or silently fail.

## 2. Receipt taxonomy

| Receipt | Produced By | Proves | Missing State Risk |
| --- | --- | --- | --- |
| MessageReceipt | Gateway | a message entered the system | inbound event cannot be audited |
| IdentityReceipt | Identity Resolver | actor was authenticated or rejected | actor ambiguity |
| TenantBindingReceipt | Tenant Resolver | tenant was bound or blocked | cross-tenant leakage |
| NormalizationReceipt | Gateway Router | channel message became canonical | channel confusion |
| InterpretationReceipt | Interpretation Layer | what the system believed the user meant | misunderstood intent |
| ClarificationReceipt | Clarification Engine | missing details were requested | vague execution |
| SearchReceipt | Search Layer | search decision, freshness, cost, evidence | stale or unbounded retrieval |
| KnowledgeReceipt | Knowledge Layer | local answer evidence | unsupported answer |
| PlanReceipt | Plan Builder | proposed action plan | hidden execution plan |
| PolicyReceipt | Policy Engine | allow, deny, constrain, or approval decision | policy bypass |
| BudgetReceipt | Budget Gate | budget estimate and decision | cost overrun |
| ApprovalRequestReceipt | Approval Router | approval was requested | unbound approval |
| ApprovalReceipt | Approval Router | approval, denial, expiration, or revocation | casual approval misuse |
| QueueReceipt | Command Ledger | command entered queue | duplicate or lost task |
| WorkerReceipt | Worker | execution or inspection result | unverifiable worker result |
| ClosureReceipt | Causal Closure Kernel | evidence was validated or blocked | false success |
| TerminalCertificate | Evidence Layer | final closure is complete | incomplete completion claim |
| FinalUserReceipt | Response Composer | user response was delivered or delivery failed | response ambiguity |
| ErrorReceipt | Any layer | explicit failure with context | silent failure |
| DenialReceipt | Governance / Gateway | structured refusal or block | unexplained denial |
| AuditTrailEntry | Audit Store | trace was retained | missing lineage |

## 3. Receipt chain

```text
MessageReceipt
-> IdentityReceipt
-> TenantBindingReceipt
-> NormalizationReceipt
-> InterpretationReceipt
-> SearchReceipt or PlanReceipt or ClarificationReceipt or DenialReceipt
-> PolicyReceipt
-> BudgetReceipt
-> ApprovalReceipt when needed
-> WorkerReceipt when executed
-> ClosureReceipt
-> TerminalCertificate
-> FinalUserReceipt
-> AuditTrailEntry
```

Question-only paths may skip execution receipts, but they still need answer evidence and final response evidence.

## 4. Redaction rules

```text
Do not expose secrets in logs, receipts, errors, docs, or user responses.
Store raw message hashes when raw content retention is not required.
Redact credentials from URLs, proxy strings, connector errors, and provider messages.
Separate internal evidence refs from user-safe explanation text.
```

## 5. Terminal closure rules

| Condition | Terminal Status |
| --- | --- |
| all required receipts exist | closed with TerminalCertificate |
| missing interpretation evidence | blocker |
| missing policy or budget evidence | blocker |
| missing approval for risky action | blocker |
| worker result lacks evidence | blocker |
| execution succeeded but delivery failed | execution closed, delivery failed |
| user canceled before execution | canceled with receipt |
