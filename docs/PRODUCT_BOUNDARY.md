# Product Boundary

Purpose: bind this repository to the Mullu Govern product naming system.
Governance scope: control-plane proprietary wording, admin surface identity, developer metadata, and launch-readiness constraints.
Dependencies: `README.md`, `docs/00_platform_overview.md`.
Invariants: Mullu Govern is the public product; Mullu is the suite/family; Mullusi is the company and ecosystem brand; Mullu Control Plane is the admin/governance/deployment surface; Mullu Platform remains valid for SDK, API, schema, and architecture contexts.

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

External paid-user launch under `Mullu Govern` remains blocked until trademark,
domain, and legal clearance close in the product identity package.
