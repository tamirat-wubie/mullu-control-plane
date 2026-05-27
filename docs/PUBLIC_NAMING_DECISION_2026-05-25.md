# Public Naming Decision 2026-05-25

Purpose: record the governed product rename from Mullu to Mullu Govern.
Governance scope: product name authority, suite boundary, technical-surface boundary, private-beta allowance, paid public launch block, and evidence closure requirements.
Dependencies: `docs/public-naming-readiness.json`, `docs/PRODUCT_BOUNDARY.md`, `docs/PRODUCT_IDENTITY.md`, `docs/PUBLIC_LAUNCH_COPY.md`, `docs/clearance-evidence/mullu/2026-05-15/capture-requirements.json`, `scripts/report_clearance_capture_readiness.py`.
Invariants: Mullu Govern is the public product; Mullu is the suite/family; Mullu Control Plane remains the internal/admin technical layer; Mullusi remains the company and governance authority; paid public launch remains blocked until external clearance evidence closes.

## Decision

Use `Mullu Govern` as the public product name.

Use `Mullu Govern, by Mullusi` on first public reference.

Keep `Mullu` as the suite/family name.

Keep `Mullusi` as the company, ecosystem, and governance authority.

Keep `Mullu Control Plane` as the internal/admin technical surface.

Keep `Mullu Platform` for developer, SDK, API, deployment, and architecture contexts where it identifies the platform layer.

Use `mullu-govern` as the public repository rename target after remotes, CI, deployment references, and release evidence paths are migrated together.

## Approved Scope

| Scope | Decision |
| --- | --- |
| Internal alignment | Approved |
| Private beta | Approved |
| Request-access product route | Approved |
| Research/product planning | Approved |
| Paid public launch | Blocked |
| Public paid advertising | Blocked |
| Domain-forwarded paid product traffic | Blocked until domain ownership evidence closes |

## Blockers

The paid public launch block remains because capture readiness still reports:

```text
Required files present: 6/40
Required files missing: 34
STATUS: blocked
```

The remaining open gates are:

1. `uspto_search`
2. `wipo_search`
3. `euipo_tmview_search`
4. `close_variant_review`
5. `domain_ownership`
6. `legal_review`

## Rejected Names

Do not use these as public product names:

1. `Mullusi Handler`
2. `Mullusi Work`
3. `Mullusi Operator`
4. `Mullu Generic`

## Next Mutation Rule

Do not set `public_paid_launch_allowed` to `true`.

Do not change status to `cleared_for_public_launch`.

Do not move any remaining gate from open to closed until the matching official evidence files are present and the required authority decision is recorded.

STATUS:
  Completeness: 100%
  Invariants verified: [Mullu Govern product name approved for internal/private beta, Mullu suite boundary preserved, Mullu Control Plane technical surface preserved, Mullusi company boundary preserved, paid public launch blocked, external evidence gates explicit]
  Open issues: [34 official evidence files missing, reviewer decisions pending, legal review pending, repository rename not executed]
  Next action: attach official evidence files and rerun capture-readiness with strict receipt output
