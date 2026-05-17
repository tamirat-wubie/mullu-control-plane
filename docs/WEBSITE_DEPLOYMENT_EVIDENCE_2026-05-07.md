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

PR #89 added a static public proof boundary page at `/proof/` in
`tamirat-wubie/mullusi` and linked the Mullu product route to it. That
repository was later proven not to be the active Pages source for
`mullusi.com`, so the live route initially remained unpublished.

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
| `www.mullusi.com` | CNAME to `mullusi.github.io` | Live Pages source is under the `mullusi` GitHub organization |
| `gh api repos/mullusi/mullusi-site/pages` | HTTP 200, `status: built`, `source.branch: main`, `source.path: /`, `html_url: https://mullusi.com/` | Active Pages source identified |
| Active source repository | `https://github.com/mullusi/mullusi-site` | Live website source is not `tamirat-wubie/mullusi` |

The route file in `tamirat-wubie/mullusi` remains useful as prior source
history, but live publication is governed by `mullusi/mullusi-site`.

## 2026-05-15 Live Proof Boundary Route Closure

`mullusi/mullusi-site` PR #1 published the active `/proof/` route, linked the
live `/mullu/` product route to it, added `/proof/` to `sitemap.xml`, and made
`proof/index.html` a required static-site validation artifact.

| Check | Observed result | Decision |
| --- | --- | --- |
| `mullusi/mullusi-site` PR #1 | Merged after `validate` passed | Active Pages source updated |
| Active source commit | `c9badb0` | `/proof/index.html` present on active `main` |
| `https://mullusi.com/proof/` | HTTP 200 from current environment | Public proof boundary route is live |
| Body literal: `Public proof boundary` | Present | Route identity verified |
| Body literal: `AwaitingEvidence` | Present | Runtime witness boundary remains explicit |
| `https://mullusi.com/mullu/` | HTTP 200 and contains `/proof/` link | Product route now points to proof boundary |
| `https://mullusi.com/sitemap.xml` | HTTP 200 and contains `https://mullusi.com/proof/` | Search/discovery surface updated |
| Proof-route tracking issue | `https://github.com/tamirat-wubie/mullusi/issues/90` closed | Public proof-route publication closed |

This closes only the public website proof boundary route. Live runtime witness
closure still requires reachable gateway witness, runtime conformance, and
health endpoints.

## Homepage Copy Evidence

| Check | Result |
| --- | --- |
| Page title | `MULLUSI — Symbolic Intelligence` |
| Contains `Mullu, by Mullusi` first reference | No |
| Contains company-level Mullusi copy | Yes |
| Contains Mullu family references | Partial, including `Mullu Mathematics` |
| Product flagship route ready | Yes for `/mullu/`; homepage first-reference update remains separate |

## 2026-05-15 Homepage Boundary Closure

The Homepage Copy Evidence table above is superseded by this closure probe.
`mullusi/mullusi-site` PR #2 updated the active homepage so the first viewport
states Mullusi as the company umbrella and Mullu as the flagship governed
symbolic product. The route keeps public runtime readiness bounded as
`AwaitingEvidence` and routes users to `/mullu/` and `/proof/`.

| Check | Observed result | Decision |
| --- | --- | --- |
| `mullusi/mullusi-site` PR #2 | Merged after `validate` passed | Active Pages source updated |
| Active source commit | `4866b0a` | Homepage boundary copy present on active `main` |
| `https://mullusi.com/` | HTTP 200 from current environment | Company homepage is live |
| Body literal: `Mullusi builds governed symbolic products` | Present | First-viewport umbrella/product boundary verified |
| Body literal: `/mullu/` | Present | Homepage routes to flagship product |
| Body literal: `/proof/` | Present | Homepage routes to public proof boundary |
| Body literal: `AwaitingEvidence` | Present | Runtime witness boundary remains explicit |

## 2026-05-16 Production Claim Boundary Closure

`mullusi/mullusi-site` PR #3 added an explicit production-claim boundary to
the active homepage and `/mullu/` product route. The section states that
Mullusi is the umbrella company and governance authority, Mullu is the flagship
governed product, and live runtime publication remains `AwaitingEvidence`
until `/health`, `/gateway/witness`, and `/runtime/conformance` publish signed
evidence.

| Check | Observed result | Decision |
| --- | --- | --- |
| `mullusi/mullusi-site` PR #3 | Merged after `validate` passed | Active Pages source updated |
| Active source commit | `854a561bd002192846da056154ad355163c71b19` | Production-claim boundary copy present on active `main` |
| `https://mullusi.com/` | HTTP 200 from current environment | Company homepage is live |
| Homepage literal: `Production Claim Boundary` | Present | Public claim boundary visible |
| Homepage literal: `AwaitingEvidence` | Present | Runtime witness state remains explicit |
| Homepage literal: `/gateway/witness` | Present | Required live witness endpoint named |
| Homepage literal: `/runtime/conformance` | Present | Required runtime conformance endpoint named |
| `https://mullusi.com/mullu/` | HTTP 200 from current environment | Product route is live |
| Product literal: `Production Claim Boundary` | Present | Product page carries same claim boundary |
| Product literal: `AwaitingEvidence` | Present | Product page does not overclaim production runtime |

## Decision

The public company homepage, `/mullu/` product route, and `/proof/` public
proof boundary route are live and aligned around Mullusi as umbrella and Mullu
as flagship product. The homepage and product route now carry a visible
production-claim boundary. Paid public launch is still not ready because
runtime witness, legal/domain, and broader app-surface gates remain open.

The original 2026-05-07 and earlier 2026-05-15 probes kept
`website_deployment_verification` open because:

1. `https://mullu.mullusi.com` has no DNS record.
2. Live runtime witness closure is still AwaitingEvidence.
3. Paid public launch still needs legal/domain and app-surface clearance.

## Remaining Public Launch Work

1. Keep `Mullusi` as the company/governance authority.
2. Keep `/mullu` as the private-beta fallback route until standalone product DNS is intentionally configured.
3. Close `mullu.mullusi.com` only after DNS, HTTPS, and body probes pass.
4. Keep paid public launch blocked until trademark, legal, domain ownership, app-title, and SDK/API stability gates close.
