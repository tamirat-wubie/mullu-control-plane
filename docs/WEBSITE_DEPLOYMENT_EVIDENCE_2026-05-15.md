# Website Deployment Evidence 2026-05-15

Purpose: record the direct live-route evidence for the Mullu private-beta product page.
Governance scope: public route availability, source repository, workflow result, page copy, sitemap inclusion, and launch-state boundary.
Dependencies: `docs/WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md`, `docs/PUBLIC_NAMING_READINESS.md`, live repository `mullusi/mullusi-site`.
Invariants: `website_deployment_verification` and `homepage_update` are closed for private-beta product routing only; paid public launch remains blocked until trademark, legal, domain ownership, app title, and SDK/API gates close.

## Deployment Summary

| Field | Value |
| --- | --- |
| Evidence date | 2026-05-15 |
| Product route | `https://mullusi.com/mullu/` |
| Source repository | `mullusi/mullusi-site` |
| Source remote | `https://github.com/mullusi/mullusi-site.git` |
| Local source path | `C:\Users\tmrtl\Projects\mullusi_website\mullu\index.html` |
| Commit | `ea4159d Add Mullu product route` |
| Workflow validation | `Validate Site` run `25919014515` completed successfully |
| Pages deployment | `pages-build-deployment` run `25919013720` completed successfully |
| Launch posture | private beta / request access |
| Gate effect | `website_deployment_verification` closed |
| Page-copy effect | `homepage_update` closed because the product landing page is live with private-beta copy |

## Pre-Publish Local Checks

| Check | Result |
| --- | --- |
| `node --check assets/app.js` | Passed |
| `node scripts\validate-site.mjs` | Passed with `site validation passed` |

## Live Route Probes

| Probe | Result | Decision impact |
| --- | --- | --- |
| `curl.exe -I -L https://mullusi.com/mullu/` | `HTTP 200`; `Last-Modified: Fri, 15 May 2026 12:57:44 GMT` | Product fallback route is live |
| `curl.exe -L https://mullusi.com/mullu/` | Contains `Mullu, by Mullusi`, `private beta`, `Request access`, `Mullu Control Plane` | Page copy is intentional product content |
| `curl.exe -L https://mullusi.com/mullu/` | Contains `Symbols are atomic. Meaning is relational. Traversal is governed. Judgment is earned.` | Canonical law is present |
| `curl.exe -I -L https://mullusi.com/sitemap.xml` | `HTTP 200` | Sitemap is reachable |
| `curl.exe -L https://mullusi.com/sitemap.xml` | Contains `https://mullusi.com/mullu/` | Product route is included in sitemap |

## Copy Boundary

The live page uses:

```text
Mullu, by Mullusi
```

The live page is explicitly private beta / request access and does not claim paid public availability.

## Gate Decision

`website_deployment_verification` is closed for the selected fallback product route:

```text
https://mullusi.com/mullu/
```

`homepage_update` is closed under the documented requirement "`mullusi.com` or product landing page updated" because the product landing page is live with intentional private-beta copy.

Paid public launch remains blocked. This evidence does not close:

1. `uspto_search`
2. `wipo_search`
3. `euipo_tmview_search`
4. `close_variant_review`
5. `domain_ownership`
6. `legal_review`
7. `app_title_update`
8. `sdk_api_stability_review`

STATUS:
  Completeness: 100%
  Invariants verified: [product route live, sitemap includes product route, private-beta copy preserved, paid public launch remains blocked]
  Open issues: [trademark search, close-variant review, domain ownership, legal review, app title update, SDK/API stability review]
  Next action: complete official trademark/domain/legal clearance before paid public launch
