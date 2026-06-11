# Mullusi Deployment Readiness Map

Status: Foundation Mode
Scope: deployment readiness deferral map. This document is not a deployment claim, public health claim, support claim, legal claim, customer-readiness claim, or production-readiness claim.

## 1. Readiness purpose

Deployment readiness is a future evidence promotion path. In Foundation Mode, public deployment, public health, DNS, secrets, customer access, and support readiness remain `AwaitingEvidence` unless proven by named witnesses.

```text
Local map
-> local evidence
-> governed readiness review
-> named witness receipts
-> promotion only when gates pass
```

## 2. Readiness categories

| Category | Required Evidence Before Promotion | Current Status | Foundation Mode Rule |
| --- | --- | --- | --- |
| Local docs | mapbook, gap register, Start Here link | partial | docs may map future readiness without claiming it. |
| Local tests | focused validators and preflight receipts | partial / unknown | tests prove local artifacts only. |
| Secrets | secure secret inventory and redaction proof | deferred | no real secret values in Git. |
| DNS | target binding, publication, and resolution receipts | deferred | no DNS publication claim. |
| Runtime | deploy target, health checks, and rollback evidence | deferred | no public runtime claim. |
| Monitoring | metrics, alert routing, incident flow | deferred | no operational readiness claim. |
| Rollback | rollback plan, recovery proof, replay evidence | deferred | no recovery readiness claim without receipts. |
| Support | support routing, SLA posture, incident triage | deferred | no customer support claim. |
| Privacy / legal | data handling, terms, review evidence | deferred | no legal or privacy readiness claim. |
| Customer access | auth, tenant isolation, onboarding, support | deferred | no pilot, beta, waitlist, or customer access claim. |

## 3. Deployment blocker rules

```text
Unknown public health -> block readiness claim.
Unknown DNS evidence -> block readiness claim.
Unknown secret posture -> block readiness claim.
Unknown rollback path -> block readiness claim.
Unknown support or legal posture -> block customer claim.
Mapbook existence alone -> not readiness evidence.
```

## 4. Future evidence receipt types

```text
DeploymentPlanReceipt
SecretPresenceReceipt
SecretRedactionReceipt
DNSBindingReceipt
DNSPublicationReceipt
DNSResolutionReceipt
EndpointReachabilityReceipt
PublicHealthDeclarationReceipt
RollbackReadinessReceipt
MonitoringReadinessReceipt
SupportReadinessReceipt
LegalReviewReceipt
CustomerAccessApprovalReceipt
```

## 5. Safe next step

```text
Keep deployment deferred.
Use this map only to name gates and blockers.
Do not run live deployment, DNS, customer, payment, or support actions from this mapbook task.
```
