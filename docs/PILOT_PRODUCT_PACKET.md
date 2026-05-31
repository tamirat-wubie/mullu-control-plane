# Private Pilot Product Packet

Purpose: define a market-safe private pilot posture for Mullu Govern before public production health, legal clearance, or enterprise compliance claims are declared.
Governance scope: pilot positioning, allowed demos, blocked claims, buyer-facing proof surfaces, and next closure actions.
Dependencies: `docs/CURRENT_READINESS_SNAPSHOT.md`, `docs/EVIDENCE_CLASSIFICATION.md`, `DEPLOYMENT_STATUS.md`, `docs/PUBLIC_NAMING_READINESS.md`.
Invariants: the pilot packet may not claim public SaaS launch, production health, legal compliance, enterprise SLA, autonomous high-risk execution, or certification beyond named evidence.

## Pilot position

```text
Mullu Govern is governed symbolic execution for private pilot review: symbolic workflows can do bounded work only through approvals, budgets, policies, receipts, audit trails, and closure evidence.
```

## Pilot target users

| Segment | Good pilot fit | Avoid for first pilot |
| --- | --- | --- |
| Founder/operator teams | Approval-gated email, documents, reports, and invoice review | Fully autonomous payments |
| Finance/admin teams | Budget checks, invoice packets, duplicate-risk review, receipt exports | High-volume production payment rails |
| Developer/platform teams | Deployment witness review, GitHub checks, release-readiness packets | Unbounded production deploy automation |
| Compliance-sensitive teams | Audit-trail review, proof bundle demos, policy simulation | Formal compliance certification claims |

## Allowed pilot claims

1. Governed symbolic execution private pilot.
2. Approval-gated task review.
3. Budget-aware action checks.
4. Receipt and audit-trail demonstration.
5. Local, CI, staging, or pilot evidence when explicitly labeled.
6. Bounded simple-platform user path.
7. Controlled integrations only when connector credentials and evidence gates are configured.

## Blocked pilot claims

1. Public production SaaS.
2. Public production health declared.
3. Legal, SOC2, ISO27001, HIPAA, PCI, FedRAMP, or equivalent compliance certification.
4. Court-proof auditability.
5. Autonomous employee replacement.
6. Autonomous high-risk payment execution.
7. Production-certified marketplace.
8. Enterprise SLA.

## Pilot demo spine

A safe first pilot should demonstrate:

```text
request -> action check -> risk/evidence/budget decision -> approval need -> receipt -> audit view -> closure summary
```

Recommended demos:

| Demo | Shows | Required boundary |
| --- | --- | --- |
| Invoice approval packet | budget, evidence, approval, receipt export | no live payment unless separately approved |
| Email/calendar approval | capability boundary, approval, provider evidence | no raw token persistence |
| Document generation | bounded skill, PII scan, receipt | generated document clearly marked pilot |
| Deployment witness review | health/conformance gates and blocked publication | no public production claim |
| Policy simulation | what would pass/fail before execution | dry-run only |

## Buyer-facing surfaces to prioritize

1. Simple home/readiness surface.
2. Approval queue.
3. Budget view.
4. Receipt/proof viewer.
5. Evidence classification view.
6. Capability maturity view.
7. Deployment health boundary view.

## Pilot acceptance criteria

A pilot may be called `pilot-ready` only when:

1. scope and blocked claims are signed off;
2. evidence artifacts are classified;
3. demo actions have no silent execution path;
4. high-risk actions require approval or are blocked;
5. receipts are emitted for admitted/denied decisions;
6. external side effects, if any, have provider evidence and reconciliation notes;
7. operator can export a pilot evidence bundle;
8. deployment status still accurately reflects no public production health unless closed by real evidence.

## Pilot closeout packet

At the end of a pilot, produce:

1. pilot scope summary;
2. actions attempted;
3. allowed/denied/escalated counts;
4. approval events;
5. budget events;
6. receipt hashes;
7. evidence classifications;
8. known limitations;
9. customer feedback;
10. recommended next capability maturity changes.

## Next implementation targets

| Target | Reason |
| --- | --- |
| `GET /api/v1/simple/readiness` | lets apps show claim-safe readiness posture |
| `GET /api/v1/simple/proof-demo` | shows proof value without enabling side effects |
| Receipt viewer v1 | differentiates Mullu from generic dashboards |
| Capability runtime gate | enforces maturity and environment boundaries |
| Temporal scheduler v2 plan | moves from phrase parsing to safe delayed operations |
| Evidence classification validator | prevents fixture evidence from supporting public claims |
