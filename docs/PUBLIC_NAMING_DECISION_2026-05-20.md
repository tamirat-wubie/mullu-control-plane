# Public Naming Decision 2026-05-20

Purpose: record the current governed naming decision for Mullu public naming.
Governance scope: product name authority, company boundary, private-beta allowance, paid public launch block, and evidence closure requirements.
Dependencies: `docs/public-naming-readiness.json`, `docs/clearance-evidence/mullu/2026-05-15/capture-requirements.json`, `scripts/report_clearance_capture_readiness.py`.
Invariants: Mullu remains the product name; Mullusi remains the company and governance authority; paid public launch remains blocked until external clearance evidence closes.

## Decision

Use `Mullu` as the flagship product name.

Use `Mullu, by Mullusi` on first public reference.

Keep `Mullusi` as the company, ecosystem, and governance authority.

Keep `Mullu Platform` for developer, SDK, API, deployment, and architecture contexts where it identifies the platform layer.

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
Required files present: 6/32
Required files missing: 26
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
  Invariants verified: [Mullu product name approved for internal/private beta, Mullusi company boundary preserved, paid public launch blocked, external evidence gates explicit]
  Open issues: [26 official evidence files missing, reviewer decisions pending, legal review pending]
  Next action: attach official evidence files and rerun capture-readiness with strict receipt output
