# Current Readiness Snapshot

Purpose: give public readers, operators, and reviewers a compact claim boundary before they read deep architecture or release notes.
Governance scope: GitHub-visible product status, deployment status, evidence class, and market-facing launch posture.
Dependencies: `README.md`, `STATUS.md`, `DEPLOYMENT_STATUS.md`, `GITHUB_SURFACE.md`, `docs/PUBLIC_NAMING_READINESS.md`.
Invariants: this snapshot may not claim public production health, legal clearance, compliance certification, enterprise SLA, or autonomous execution beyond the named evidence.

## Snapshot

| Surface | Current posture | Claim boundary |
| --- | --- | --- |
| Repository | Active governed-runtime development | Public repository, proprietary use terms |
| Product name | `Mullu Govern` internally aligned | Paid public launch remains blocked by naming/legal/domain gates |
| Control surface | `Mullu Control Plane` | Internal/admin/deployment/governance surface |
| Latest tagged release | `v3.13.3` | GitHub release witness, not superseded by mainline notes |
| Mainline implementation | v4.x implementation and hardening records | Repository-mainline evidence only |
| Public production runtime | Not published from this repository | No production health claim |
| Public health endpoint | Not declared | Requires deployment witness and production evidence plane closure |
| Best current external posture | Private pilot / controlled staging review | Not public SaaS, not enterprise SLA |

## Allowed short description

```text
Mullu Govern is governed symbolic execution: symbolic workflows can do real work only through authority, policy, budget, evidence, temporal, capability, proof, audit, and closure controls.
```

## Blocked short descriptions

Do not use these until the corresponding evidence exists:

1. `production-certified autonomous operating system`
2. `legally safe autonomous worker`
3. `court-proof autonomous worker`
4. `SOC2-ready governance platform`
5. `public production SaaS`
6. `enterprise-compliant autonomous workforce`

## Reader routing

| Reader need | Start here |
| --- | --- |
| Plain explanation | `docs/explain/PLAIN_ENGLISH.md` |
| Product/name status | `docs/PUBLIC_NAMING_READINESS.md` |
| Repository claim boundary | `STATUS.md` |
| Deployment health boundary | `DEPLOYMENT_STATUS.md` |
| Pilot market packet | `docs/PILOT_PRODUCT_PACKET.md` |
| Evidence classification | `docs/EVIDENCE_CLASSIFICATION.md` |

## Update rule

This file should be updated only when one of these changes:

1. release witness changes;
2. deployment witness state changes;
3. public production health state changes;
4. product naming launch state changes;
5. pilot posture changes;
6. evidence classification policy changes.
