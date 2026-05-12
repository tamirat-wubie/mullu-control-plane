# Website Deployment Evidence Template

Purpose: provide the deployment verification format for `mullusi.com` and Mullu public product routes.
Governance scope: live website state, route ownership, copy correctness, HTTPS, DNS, launch gating, and site-not-found prevention.
Dependencies: `docs/WEBSITE_UPDATE_CHECKLIST.md`, `docs/DOMAIN_OWNERSHIP_RECORD_TEMPLATE.md`, `docs/PUBLIC_NAMING_READINESS.md`, `docs/DOMAIN_ACQUISITION_PLAN.md`.
Invariants: website deployment evidence does not clear trademark or legal gates; no paid public launch route is valid until domain ownership and deployment verification are both recorded.

## Capture Rules

For each public route, capture:

1. URL.
2. HTTP status.
3. Final redirected URL.
4. Page title.
5. Visible product/company naming.
6. HTTPS certificate status.
7. Evidence screenshot or exported HTML path.
8. Date, time, timezone, and reviewer.
9. Decision: pass, private_beta_only, blocked, or not_deployed.

This evidence must be collected from the live public route, not from local
preview output alone.

## Required Routes

| Route | Purpose | Required before paid public launch |
| --- | --- | --- |
| `https://mullusi.com` | Company homepage | Yes |
| `https://mullusi.com/mullu` | Company-site product fallback | Yes if standalone product domain is not controlled |
| `https://mullu.mullusi.com` | Controlled product subdomain fallback | Yes if used as app/product route |
| `https://docs.mullusi.com` | Documentation landing | Yes if referenced by launch copy |
| `https://dashboard.mullusi.com` | Control Plane/admin route | Yes if referenced by enterprise copy |
| `https://api.mullusi.com` | API route | Yes if referenced by developer copy |

## Route Evidence Table

| Field | Required value |
| --- | --- |
| Route | Public URL |
| Surface | company_homepage, product_landing, app, docs, dashboard, api, or fallback |
| Expected owner | Mullusi |
| Expected product reference | `Mullu, by Mullusi` where product-facing |
| HTTP status | 200, 3xx, 4xx, 5xx, or blocked |
| Final URL | Final URL after redirects |
| Page title | Browser/document title |
| HTTPS valid | yes/no |
| Not site-not-found | yes/no |
| Blocked old names absent | yes/no |
| Paid launch claims absent before clearance | yes/no |
| Screenshot/artifact | Path or storage reference |
| Captured by | Reviewer name or system identity |
| Captured at | Date, time, timezone |
| Decision | pass, private_beta_only, blocked, or not_deployed |
| Notes | Review notes |

## Copy Verification

| Requirement | Evidence |
| --- | --- |
| First product reference is `Mullu, by Mullusi` |  |
| Company reference uses `Mullusi` |  |
| Product name uses `Mullu` |  |
| Technical architecture uses `Mullu Platform` only where appropriate |  |
| Admin surface uses `Mullu Control Plane` |  |
| Blocked names are absent: `Mullusi Handler`, `Mullusi Work`, `Mullusi Operator`, `Mullu AI` |  |
| Page is private beta, waitlist, or request-access until clearance closes |  |
| No paid production availability claim appears before clearance |  |

## DNS And Security Verification

| Control | Evidence |
| --- | --- |
| DNS points to expected host/provider |  |
| HTTPS certificate is valid for hostname |  |
| Redirects preserve expected trust domain |  |
| HSTS configured where appropriate |  |
| No mixed-content warnings |  |
| No exposed staging/debug banner |  |
| No GitHub Pages site-not-found page |  |
| No generic parked-domain page |  |

## Per-Route Worksheet

### `https://mullusi.com`

```text
surface:
http_status:
final_url:
page_title:
https_valid:
not_site_not_found:
blocked_old_names_absent:
paid_launch_claims_absent_before_clearance:
screenshot_artifact:
captured_by:
captured_at:
decision:
notes:
```

### `https://mullusi.com/mullu`

```text
surface:
http_status:
final_url:
page_title:
https_valid:
not_site_not_found:
blocked_old_names_absent:
paid_launch_claims_absent_before_clearance:
screenshot_artifact:
captured_by:
captured_at:
decision:
notes:
```

### `https://mullu.mullusi.com`

```text
surface:
http_status:
final_url:
page_title:
https_valid:
not_site_not_found:
blocked_old_names_absent:
paid_launch_claims_absent_before_clearance:
screenshot_artifact:
captured_by:
captured_at:
decision:
notes:
```

## Closure Rule

The `website_deployment_verification` gate may close only when:

1. The selected launch route returns an intentional page, not a site-not-found or parked-domain page.
2. The selected route uses valid HTTPS.
3. The selected route preserves the `Mullu, by Mullusi` boundary.
4. Blocked public names are absent.
5. Any page visible before legal clearance is clearly waitlist, request-access, or private beta.
6. Domain ownership evidence exists for the selected route.
7. The readiness witness is updated in the same change that closes the gate.
