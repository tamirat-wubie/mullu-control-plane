# App Title Update Evidence 2026-05-15

Purpose: record that user-facing application title surfaces use `Mullu` and do not use blocked generic product names.
Governance scope: HTML/operator console titles, product route title, app-facing title boundary, and technical title exclusions.
Dependencies: `site/mullu/index.html`, `gateway/server.py`, `gateway/operator_capability_console.py`, `docs/SDK_API_STABILITY_REVIEW_2026-05-15.md`.
Invariants: user-facing app titles use `Mullu`; `Mullu Platform` remains allowed only for SDK/API/runtime technical contracts.

## Decision

`app_title_update` is closed.

## User-Facing Title Evidence

| Surface | Observed title | Decision |
| --- | --- | --- |
| Product landing page | `<title>Mullu, by Mullusi - Governed Symbolic Systems</title>` | Product-facing title uses `Mullu` |
| Authority operator console | `<title>Mullu Authority Operator Console</title>` | App-facing title uses `Mullu` |
| Physical promotion receipts | `<title>Mullu Physical Promotion Receipts</title>` | App-facing title uses `Mullu` |
| Universal action proofs | `<title>Mullu Universal Action Proofs</title>` | App-facing title uses `Mullu` |
| Operator capabilities | `<title>Mullu Operator Capabilities</title>` | App-facing title uses `Mullu` |

## Blocked Names

The following names must not appear as user-facing app titles:

1. `Mullusi Handler`
2. `Mullusi Work`
3. `Mullusi Operator`
4. `Mullu Generic`

## Technical Exclusion

The following are not user-facing app title blockers because they are SDK/API/runtime contract titles already covered by `docs/SDK_API_STABILITY_REVIEW_2026-05-15.md`:

1. OpenAPI `title="Mullu Platform"`
2. Generated SDK test expectations for `Mullu Platform`
3. Runtime package name `Mullu Platform MCOI Runtime`
4. Historical release-note headings

## Gate Decision

`app_title_update` is closed because active app-facing HTML/product titles use `Mullu`, while remaining `Mullu Platform` titles are intentional technical contracts.

This evidence does not close:

1. `uspto_search`
2. `wipo_search`
3. `euipo_tmview_search`
4. `close_variant_review`
5. `domain_ownership`
6. `legal_review`

STATUS:
  Completeness: 100%
  Invariants verified: [user-facing app titles use Mullu, blocked generic names absent from title evidence, technical Mullu Platform boundary preserved, paid public launch remains blocked]
  Open issues: [official trademark searches, close-variant review, domain ownership evidence, legal review]
  Next action: complete official trademark/domain/legal clearance before paid public launch
