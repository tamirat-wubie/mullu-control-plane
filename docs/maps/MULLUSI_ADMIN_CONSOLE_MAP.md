# Mullusi Admin Console Map

Status: Foundation Mode
Scope: private admin-console map. This document does not claim admin UI implementation, customer support readiness, tenant readiness, legal readiness, or production operation.

## 1. Admin purpose

The admin console gives an operator governed visibility and control over users, tenants, policies, budgets, approvals, workers, connectors, and receipts.

```text
Admin session
-> role and tenant scope check
-> selected admin surface
-> governed read or governed mutation
-> receipt
```

## 2. Required admin screens

| Screen | Purpose | Allowed Actions | Forbidden Without Stronger Gate | Status | Next Step |
| --- | --- | --- | --- | --- | --- |
| Tenant Overview | view tenant status and boundaries | read tenant metadata | cross-tenant data inspection | missing / unknown | Define tenant scope fields. |
| User and Role Manager | manage actor roles | view and propose role changes | role mutation without approval | missing / unknown | Add role change receipt contract. |
| Policy Manager | view and edit policies | read policy, propose edit | policy write without governance | missing / unknown | Map policy edit approvals. |
| Budget Manager | view and set budgets | read budget, propose limit | spend or limit change without approval | missing / unknown | Add budget receipt fields. |
| Approval Center | inspect pending approvals | approve or deny within authority | approve expired or unbound requests | missing / partial | Bind request, actor, tenant, channel, and expiration. |
| Current Task Monitor | view active and blocked tasks | pause or cancel when allowed | force success or skip receipts | missing / unknown | Bind to command ledger states. |
| Worker Registry | view worker capabilities and limits | enable only after evidence | enable high-risk worker without approval | missing / unknown | Define worker contracts first. |
| Connector Settings | view connector posture | configure only through secure flow | store secrets in docs or receipts | missing / unknown | Keep real values outside repository. |
| Receipt and Audit Viewer | inspect receipt chain | read scoped receipts | cross-tenant receipt access | missing / unknown | Build read-only receipt viewer. |
| Deployment Readiness View | show deferred readiness gates | read-only evidence checklist | declare readiness from map alone | deferred | Use deployment readiness map. |

## 3. Admin gate rules

```text
Admin identity must be authenticated.
Admin actions must be tenant-scoped.
Role, policy, budget, worker, connector, and deployment changes are effect-bearing.
Effect-bearing admin actions require policy, budget when relevant, approval, and receipt.
Admin read access must not bypass tenant privacy.
```

## 4. Audit requirements

| Admin Action | Required Receipt |
| --- | --- |
| view tenant summary | AdminReadReceipt or AuditTrailEntry |
| change role | PolicyReceipt, ApprovalReceipt, AdminChangeReceipt |
| change budget | BudgetReceipt, ApprovalReceipt, AdminChangeReceipt |
| enable worker | PolicyReceipt, WorkerEnablementReceipt |
| configure connector | ConnectorReceipt with redacted secret refs |
| inspect receipt | AuditTrailEntry with tenant scope |
| mark readiness | readiness evidence receipt, not map-only claim |

## 5. Known gaps

```text
GAP-ADMIN-001: Tenant/user admin console missing.
GAP-ADMIN-002: Policy and budget manager missing.
GAP-EVIDENCE-003: Delivery failure must be separate from execution failure.
GAP-DEPLOY-001: Deployment readiness remains deferred.
```
