# Evidence Classification

Purpose: prevent fixture, local, CI, staging, pilot, production, external, and historical artifacts from being used outside their evidence boundary.
Governance scope: public claims, release claims, deployment claims, pilot claims, validator examples, readiness examples, and market-facing language.
Dependencies: `README.md`, `STATUS.md`, `DEPLOYMENT_STATUS.md`, `docs/CURRENT_READINESS_SNAPSHOT.md`, `schemas/evidence_classification_manifest.schema.json`, `examples/evidence_classification_manifest.json`.
Invariants: example artifacts may not support public production claims; production claims require production-class evidence; legal/compliance claims require external review evidence.

## Evidence classes

| Class | Meaning | May support public production claim? |
| --- | --- | --- |
| `fixture` | Example data for tests, schemas, validators, docs, or demos | No |
| `local` | Developer-local command output or local runtime witness | No |
| `ci` | GitHub Actions or repository CI witness | No, except repository-validation claims |
| `staging` | Controlled non-production deployment witness | No |
| `pilot` | Controlled pilot evidence with bounded users/operators | Limited pilot claims only |
| `production` | Live production evidence from declared endpoints and operators | Yes, only for the named surface |
| `external` | Evidence from counsel, auditor, provider, DNS, domain, trademark, or compliance authority | Yes, only for the reviewed subject |
| `historical` | Prior evidence retained for continuity or audit | No new claims unless still current |

## Claim rule

```text
claim_allowed(claim, artifact) <=>
  artifact.class supports claim.scope
  and artifact.may_support_public_claim is true when claim is public
  and artifact.freshness_window is valid when freshness is required
  and artifact.blocked_claims does not contain claim.type
```

## Required manifest fields

Every evidence artifact used by a release, deployment, pilot, product, or market-facing claim should be listed with:

1. artifact path;
2. evidence class;
3. purpose;
4. allowed claims;
5. blocked claims;
6. whether it may support a public claim;
7. review owner;
8. freshness rule when applicable.

## High-risk examples

These files must be treated as `fixture` unless replaced by live collected evidence:

| Artifact pattern | Required class | Reason |
| --- | --- | --- |
| `*-example.json` | `fixture` | Validator/demo shape only |
| `docs/*production*example*.json` | `fixture` | Production-like wording can mislead readers |
| `docs/*readiness-example*.json` | `fixture` | Readiness fixture, not live readiness |
| `.change_assurance/*` in docs examples | `fixture` or `ci` | Must not imply live deployment unless collected from live endpoints |

## Blocked market claims without production/external evidence

Do not claim:

1. public production health;
2. public SaaS launch;
3. enterprise SLA;
4. SOC2, ISO27001, HIPAA, PCI, FedRAMP, or legal compliance;
5. court-proof auditability;
6. autonomous production execution;
7. production-certified capability marketplace.

## Operator checklist

Before using an artifact in a public or customer-facing claim, verify:

1. the artifact is listed in `examples/evidence_classification_manifest.json` or the production equivalent;
2. `may_support_public_claim` matches the intended claim;
3. `allowed_claims` includes the exact claim family;
4. `blocked_claims` does not include the claim family;
5. freshness is current;
6. reviewer/approver is recorded;
7. example fixtures are not presented as live deployment evidence.

## Next validator target

A future validator should read one or more evidence classification manifests and fail when:

1. a `*-example.json` artifact is marked as public-claim supporting;
2. a production-health claim cites non-production evidence;
3. a legal/compliance claim lacks an external evidence class;
4. a stale artifact is used for a freshness-bound claim;
5. an artifact has both allowed and blocked claims for the same claim family.
