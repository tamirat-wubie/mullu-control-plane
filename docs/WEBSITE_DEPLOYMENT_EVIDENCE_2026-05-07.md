# Website Deployment Evidence 2026-05-07

Purpose: record direct live-route evidence for Mullusi company and Mullu product launch routes.
Governance scope: homepage state, product route state, DNS state, HTTP status, launch blockers, and public naming readiness.
Dependencies: `docs/WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md`, `docs/PUBLIC_NAMING_READINESS.md`.
Invariants: this evidence closes `website_deployment_verification` only for the `/mullu` fallback route after the 2026-05-15 HTTP 200 probe; paid public launch remains blocked until the remaining public naming gates close.

## Probe Summary

| Field | Value |
| --- | --- |
| Probe date | 2026-05-07 |
| Probe method | `Resolve-DnsName`, `curl.exe -I -L`, and body fetch with `curl.exe -L` |
| Result | `website_deployment_verification` closed for `/mullu`; paid launch remains blocked |
| Homepage update | `homepage_update` remains open |
| Paid launch route | not cleared |

## DNS Evidence

| Route | Result |
| --- | --- |
| `mullusi.com` | Resolves to GitHub Pages A records `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153` and GitHub Pages IPv6 records |
| `www.mullusi.com` | CNAME resolves to `mullusi.github.io` |
| `mullu.mullusi.com` | DNS name does not exist |

## HTTP Evidence

| Route | Observed result | Decision |
| --- | --- | --- |
| `https://mullusi.com` | HTTP 301 to `https://www.mullusi.com/` | Company root route is live through redirect |
| `https://www.mullusi.com/` | HTTP 200 from GitHub Pages | Company homepage is live |
| `https://mullusi.com/mullu` | HTTP 301 to `https://www.mullusi.com/mullu`, then HTTP 404 | Product fallback route is not live |
| `https://mullu.mullusi.com` | Host could not resolve | Product subdomain is not live |

## Post-Main Probe

After `mullu/index.html` appeared on `origin/main` at website commit `39014fd`,
the direct route probe still returned:

| Route | Observed result | Decision |
| --- | --- | --- |
| `https://mullusi.com/mullu` | HTTP 301 to `https://www.mullusi.com/mullu`, then cached HTTP 404 | Keep `website_deployment_verification` open |

This means either GitHub Pages had not yet published the route, the cache had
not expired, or the live site is sourced from a different repository/branch than
`tamirat-wubie/mullusi` `origin/main`.

## 2026-05-15 Route Update Probe

PR #86 updated the product route on `tamirat-wubie/mullusi` `main` at commit
`7965ae4e393457017611f6bd4e9b1f3e6dea4940`. The route copy now makes the
Mullusi/Mullu boundary explicit and keeps repository-verified claims separate
from live deployment witness claims.

| Check | Observed result | Decision |
| --- | --- | --- |
| `tamirat-wubie/mullusi` PR #86 | Merged and `fast-check` passed | Website repo source updated |
| `gh api repos/tamirat-wubie/mullusi/pages` | HTTP 404 | This repository is not configured as the active Pages site |
| `https://mullusi.com/mullu` | HTTP 404 from current environment | Product route still not live |
| Live-route tracking issue | `https://github.com/tamirat-wubie/mullusi/issues/87` | Keep deployment verification open |

## 2026-05-15 Live Route Closure Probe

PR #88 restored the route literals required by the public naming readiness
witness and merged into `tamirat-wubie/mullusi` `main` at commit
`93b7a6de942241424564f686aebee023a469ecde`.

| Check | Observed result | Decision |
| --- | --- | --- |
| `tamirat-wubie/mullusi` PR #88 | Merged and `fast-check` passed | Website repo source aligned with governed artifact |
| `https://mullusi.com/mullu` | HTTP 200 from current environment | Product fallback route is live |
| Body literal: `Mullu, by Mullusi` | Present | First-reference product boundary verified |
| Body literal: `Mullu CLI` | Present | Public product-surface literal verified |
| Body literal: `Mullu Control Plane` | Present | Admin/product surface literal verified |
| `website_deployment_verification` | Closed for `/mullu` route | Paid public launch remains blocked by remaining gates |

## 2026-05-15 Proof Boundary Route Probe

PR #89 added a static public proof boundary page at `/proof/` and linked the
Mullu product route to it. The page separates verified route evidence, pending
runtime witness evidence, and paid-public-launch blockers.

| Check | Observed result | Decision |
| --- | --- | --- |
| `tamirat-wubie/mullusi` PR #89 | Merged and `fast-check` passed | Website repo source contains `/proof/index.html` |
| `https://mullusi.com/proof` | HTTP 404 from current environment | Proof route publication remains pending |
| `https://mullusi.com/proof/` | HTTP 404 from current environment | Proof route publication remains pending |
| `https://www.mullusi.com/proof/` | HTTP 404 from current environment | Proof route publication remains pending |
| Proof-route tracking issue | `https://github.com/tamirat-wubie/mullusi/issues/90` | Keep proof route verification open |

This does not reopen the already verified `/mullu` fallback route. It records a
separate publication gap for the new `/proof/` page.

## Pages Source Discovery

DNS now shows:

| Route | Observed result | Decision |
| --- | --- | --- |
| `www.mullusi.com` | CNAME to `mullusi.github.io` | Live Pages source is likely a `mullusi.github.io` user/org Pages source, not the checked-out `tamirat-wubie/mullusi` application repo |
| `https://github.com/mullusi/mullusi.github.io.git` | Repository not found from current session | Source repository is inaccessible, private, renamed, or controlled outside current GitHub access |

The route file is present on `tamirat-wubie/mullusi` `origin/main`, but that is
not sufficient to close the deployment gate until the Pages source that backs
`mullusi.github.io` is identified and updated.

## Homepage Copy Evidence

| Check | Result |
| --- | --- |
| Page title | `MULLUSI — Symbolic Intelligence` |
| Contains `Mullu, by Mullusi` first reference | No |
| Contains company-level Mullusi copy | Yes |
| Contains Mullu family references | Partial, including `Mullu Mathematics` |
| Product flagship route ready | No |

## Decision

The public company homepage is live, but the product launch route is not ready.

The original 2026-05-07 and earlier 2026-05-15 probes kept
`website_deployment_verification` open because:

1. `https://mullusi.com/mullu` returns HTTP 404 after redirect.
2. `https://mullu.mullusi.com` has no DNS record.
3. The live homepage does not yet present the first-reference product boundary: `Mullu, by Mullusi`.
4. The homepage remains company/ecosystem oriented rather than flagship product oriented.

## Remaining Public Launch Work

1. Keep `Mullusi` as the company/governance authority.
2. Keep `/mullu` as the private-beta fallback route until standalone product DNS is intentionally configured.
3. Close `mullu.mullusi.com` only after DNS, HTTPS, and body probes pass.
4. Keep paid public launch blocked until trademark, legal, domain ownership, app-title, and SDK/API stability gates close.
