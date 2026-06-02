# Product Boundary

Purpose: bind this repository to the Mullu Govern product naming system.
Governance scope: control-plane proprietary wording, admin surface identity, developer metadata, Foundation Mode, and launch-readiness constraints.
Dependencies: `README.md`, `docs/FOUNDATION_MODE.md`, `docs/00_platform_overview.md`.
Invariants: Foundation Mode is the current operating posture until promoted by witness; Mullu Govern is the public product; Mullu is the suite/family; Mullusi is the company and ecosystem brand; Mullu Control Plane is the admin/governance/deployment surface; Mullu Platform remains valid for SDK, API, schema, and architecture contexts.

## Boundary

Ownership: Mullu Govern is a proprietary invention of Tamirat Wubie, governed
for use under the Mullusi company boundary. Product naming, repository metadata,
package metadata, and launch copy must not imply free public use.

| Name | Use in this repository |
| --- | --- |
| Mullu Govern | Public governed-execution product name |
| Mullu | Proprietary Mullusi suite/family name |
| Mullusi | Company, governance authority, billing, research, and trust context |
| Mullu Control Plane | This repository's primary admin/governance/deployment surface |
| Mullu Platform | Developer, SDK, API, schema, deployment, and architecture context |
| MAF Core | Internal substrate |
| MCOI Runtime | Internal computer-operations runtime |

## Company Description

```text
Mullu Govern is the governed execution product by Mullusi for symbolic
workflows, approvals, budgets, audit trails, lineage, deployment controls, and
proof-backed actions.
```

```text
Mullu Control Plane is the internal/admin technical surface that provides
gateway, approvals, status, traces, budgets, lineage, and deployment controls.
```

## Allowed Existing Technical Uses

The following phrases may remain when the context is technical or historical:

1. `Mullu Platform`
2. `Mullu Platform Configuration`
3. `Mullu Platform MCOI Runtime`
4. `Mullu Platform` in historical release notes
5. `Mullu Platform` in OpenAPI titles and schema names
6. `Mullu Control Plane` for admin, runtime, deployment, observability, and repository-local technical surfaces

## Repository Rename Target

The public repository name target is:

```text
mullu-govern
```

The current `mullu-control-plane` repository and local directory may remain
until a separate migration updates remotes, deployment references, CI secrets,
and release evidence paths.

## Blocked Public Names

Do not introduce these as product names:

1. `Mullusi Handler`
2. `Mullusi Work`
3. `Mullusi Operator`
4. `Mullu Generic`

## Launch Constraint

External paid-user launch under `Mullu Govern` remains blocked until Foundation
Mode promotion, local proof-thread evidence, trademark, domain, legal
clearance, deployment witness, and public-health evidence close in the product
identity package.

## Foundation Scope Constraint

Foundation Mode product scope is bounded by
[`FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md`](FOUNDATION_PRODUCT_SCOPE_BOUNDARY.md).
The selected local learning lane is a proof lane only. It does not restrict the
long-term Mullu Govern platform, and it does not authorize pilot access,
customer access, market validation, paid launch, or deployment-readiness claims.

Foundation Mode secrets and credentials are bounded by
[`FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md`](FOUNDATION_SECRETS_CREDENTIALS_BOUNDARY.md).
Secrets/credentials planning may be drafted locally, but it does not store real
secrets, activate credentials, bind provider accounts, enable external calls,
commit environment files, or support deployment-readiness claims.

Foundation Mode cost and budget posture is bounded by
[`FOUNDATION_COST_BUDGET_BOUNDARY.md`](FOUNDATION_COST_BUDGET_BOUNDARY.md).
Cost/budget planning may be drafted locally, but it does not authorize
spending, paid infrastructure, provider billing, payment-method binding,
subscription creation, purchase approval, invoice payment, vendor commitment, or
deployment-readiness claims.

Foundation Mode runtime and environment posture is bounded by
[`FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md`](FOUNDATION_RUNTIME_ENVIRONMENT_BOUNDARY.md).
Runtime/environment planning may be drafted locally, but it does not verify
runtime readiness, activate databases, start containers, open endpoints, run
migrations, connect cloud runtimes, or support deployment-readiness claims.

Foundation Mode backup and export posture is bounded by
[`FOUNDATION_BACKUP_EXPORT_BOUNDARY.md`](FOUNDATION_BACKUP_EXPORT_BOUNDARY.md).
Backup/export planning may be drafted locally, but it does not run backups,
activate cloud sync, export files, publish archives, delete data, record
private paths, move secrets, move personal data, claim restore readiness, or
support deployment-readiness claims.

Foundation Mode support readiness is bounded by
[`FOUNDATION_SUPPORT_READINESS_BOUNDARY.md`](FOUNDATION_SUPPORT_READINESS_BOUNDARY.md).
Support planning may be drafted locally, but it does not open customer support,
support SLA, onboarding, paid support, incident-response readiness, or
deployment-readiness claims.

Foundation Mode intake and onboarding are bounded by
[`FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md`](FOUNDATION_INTAKE_ONBOARDING_BOUNDARY.md).
Intake planning may be drafted locally, but it does not publish forms, open
waitlists, accept pilot signups, collect personal data, import CRM records,
start outreach, onboard customers, enable paid access, or support deployment
claims.

Foundation Mode privacy and data retention are bounded by
[`FOUNDATION_PRIVACY_DATA_BOUNDARY.md`](FOUNDATION_PRIVACY_DATA_BOUNDARY.md).
Privacy/data planning may be drafted locally, but it does not collect or store
personal data, publish privacy notices, capture consent, enable tracking,
activate processors, claim legal clearance, open customer access, or support
deployment claims.
