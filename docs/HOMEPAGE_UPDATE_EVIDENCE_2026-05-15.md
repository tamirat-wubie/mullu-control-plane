# Homepage Update Evidence 2026-05-15

Purpose: record that the public product landing page requirement is satisfied through the live Mullu private-beta route.
Governance scope: homepage/product-page naming copy, private-beta launch posture, public first-reference form, and paid-launch boundary.
Dependencies: `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md`, `docs/PUBLIC_LAUNCH_COPY.md`, `site/mullu/index.html`.
Invariants: this evidence closes `homepage_update` only for private-beta product-page readiness; paid public launch remains blocked until official clearance gates close.

## Decision

`homepage_update` is closed.

The readiness requirement is:

```text
`mullusi.com` or product landing page updated
```

The selected product landing page is:

```text
https://mullusi.com/mullu/
```

## Evidence

| Evidence | Result |
| --- | --- |
| Live product route | `https://mullusi.com/mullu/` returns HTTP 200 |
| Product first reference | Page contains `Mullu, by Mullusi` |
| Launch posture | Page contains private beta / request access copy |
| Canonical law | Page contains `Symbols are atomic. Meaning is relational. Traversal is governed. Judgment is earned.` |
| Product family | Page names `Mullu CLI`, `Mullu Code`, `Mullu Desk`, and `Mullu Control Plane` |
| Sitemap | `https://mullusi.com/sitemap.xml` includes `https://mullusi.com/mullu/` |

## Boundary

This is not a paid launch homepage.

The public page may remain private beta until these gates close:

1. `uspto_search`
2. `wipo_search`
3. `euipo_tmview_search`
4. `close_variant_review`
5. `domain_ownership`
6. `legal_review`
7. `app_title_update`

## Gate Decision

`homepage_update` is closed because the product landing page is live, intentional, and private-beta bounded.

STATUS:
  Completeness: 100%
  Invariants verified: [product landing page live, first-reference copy present, private-beta posture preserved, paid public launch remains blocked]
  Open issues: [official trademark searches, close-variant review, domain ownership evidence, legal review, app title update]
  Next action: complete legal/domain clearance before publishing paid public launch copy
