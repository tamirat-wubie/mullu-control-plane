# Product Boundary

Purpose: bind this repository to the Mullu flagship product naming system.
Governance scope: control-plane public wording, admin surface identity, developer metadata, and launch-readiness constraints.
Dependencies: `README.md`, `docs/00_platform_overview.md`.
Invariants: Mullu is the flagship product; Mullusi is the company and ecosystem brand; Mullu Control Plane is the admin/governance/deployment surface; Mullu Platform remains valid for SDK, API, schema, and architecture contexts.

## Boundary

| Name | Use in this repository |
| --- | --- |
| Mullu | Public product name |
| Mullusi | Company, governance authority, billing, research, and trust context |
| Mullu Control Plane | This repository's primary admin/governance/deployment surface |
| Mullu Platform | Developer, SDK, API, schema, deployment, and architecture context |
| MAF Core | Internal substrate |
| MCOI Runtime | Internal computer-operations runtime |

## Public Description

```text
Mullu is the flagship product by Mullusi: governed symbolic intelligence for
personal, team, enterprise, and deployment work.
```

```text
Mullu Control Plane provides gateway, approvals, status, traces, budgets,
lineage, and deployment controls.
```

## Allowed Existing Technical Uses

The following phrases may remain when the context is technical or historical:

1. `Mullu Platform`
2. `Mullu Platform Configuration`
3. `Mullu Platform MCOI Runtime`
4. `Mullu Platform` in historical release notes
5. `Mullu Platform` in OpenAPI titles and schema names

## Blocked Public Names

Do not introduce these as product names:

1. `Mullusi Handler`
2. `Mullusi Work`
3. `Mullusi Operator`
4. `Mullu AI`

## Launch Constraint

Public paid-user launch under `Mullu` remains blocked until trademark, domain,
and legal clearance close in the product identity package.
