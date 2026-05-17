# Product Route Deployment Handoff

Purpose: record the deployment handoff for the Mullu private-beta product route.
Governance scope: source artifact, copied website target, live-route publication, and post-deploy verification.
Dependencies: `site/mullu/index.html`, `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-07.md`, `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md`.
Invariants: this handoff closes `website_deployment_verification` only for the private-beta `/mullu` fallback route; paid public launch remains blocked until the remaining public naming gates close.

## Source And Target

| Field | Value |
| --- | --- |
| Governed source artifact | `site/mullu/index.html` |
| Website repo copy target | `../mullusi_website/mullu/index.html`, `../mullusi/mullu/index.html`, and active source `mullusi/mullusi-site` |
| Intended live route | `https://mullusi.com/mullu/` |
| Website main branch | `origin/main` |
| Live website repository | `https://github.com/mullusi/mullusi-site.git` |
| Current live commit carrying route | `ea4159d Add Mullu product route` |
| Site validation workflow | `Validate Site` run `25919014515` passed |
| Pages deployment workflow | `pages-build-deployment` run `25919013720` passed |
| Initial merged PR carrying route | `https://github.com/tamirat-wubie/mullusi/pull/84` |
| Current merged PR carrying route boundary update | `https://github.com/tamirat-wubie/mullusi/pull/86` |
| Current merged PR carrying launch literals | `https://github.com/tamirat-wubie/mullusi/pull/88` |
| Current merged PR carrying active proof route | `https://github.com/mullusi/mullusi-site/pull/1` |
| Current merged PR carrying active homepage boundary | `https://github.com/mullusi/mullusi-site/pull/2` |
| Current merged PR carrying production-claim boundary | `https://github.com/mullusi/mullusi-site/pull/3` |
| Current main commit carrying route | `93b7a6de942241424564f686aebee023a469ecde` |
| Active Pages source commit carrying proof route | `c9badb0` |
| Active Pages source commit carrying homepage boundary | `4866b0a` |
| Active Pages source commit carrying production-claim boundary | `854a561bd002192846da056154ad355163c71b19` |
| Redundant route PR | `https://github.com/tamirat-wubie/mullusi/pull/85` closed after route appeared on `origin/main` |
| Live-route blocker issue | `https://github.com/tamirat-wubie/mullusi/issues/87` resolved by PR #88 live probe |
| DNS Pages target | `mullusi.github.io` |
| Pages source access | `gh api repos/mullusi/mullusi-site/pages` returns active Pages config for `https://mullusi.com/` from `main` path `/` |
| Product first reference | `Mullu, by Mullusi` |
| Launch posture | private beta / request access |
| Live status | live route verified for `/`, `/mullu/`, and `/proof/`; HTTP 200 |

## Copy Result

The governed product route artifact was copied from:

```text
site/mullu/index.html
```

to the sibling website repository target:

```text
../mullusi_website/mullu/index.html
```

Earlier non-live route lineage referenced:

```text
../mullusi/mullu/index.html
```

That path is retained only as source-control history. It was not the active
custom-domain Pages source. A prior attempt to access
`https://github.com/mullusi/mullusi.github.io.git` returned repository not found
from the current session, which is why the live source was later identified as
`mullusi/mullusi-site`.

The copied file was byte-equivalent by line comparison during the handoff check.

The route was split onto a focused website branch:

```text
product/mullu-route
```

and opened as:

```text
https://github.com/tamirat-wubie/mullusi/pull/85
```

PR #85 was green, but the repository branch policy required the newer
`fast-check` status introduced by PR #84. PR #84 was updated with the same
strict-typing fixes, passed `fast-check`, and merged first. After PR #84 merged,
`mullu/index.html` was already present on `origin/main` at commit `39014fd`, so
PR #85 was closed as redundant.

PR #86 later replaced the product route copy with a clearer Mullusi/Mullu
boundary: Mullusi is the company, research, governance, and trust umbrella;
Mullu is the flagship governed symbolic intelligence product. It also added
explicit public claim handling for repository-verified evidence versus the
unpublished live deployment witness. PR #86 passed `fast-check` and merged into
`tamirat-wubie/mullusi` `main` at `7965ae4e393457017611f6bd4e9b1f3e6dea4940`.

PR #88 restored the public naming readiness literals required by the governed
route witness: `private beta`, `Request access`, `Mullu CLI`, `Mullu Code`,
`Mullu Desk`, and `Mullu Control Plane`. PR #88 passed `fast-check` and merged
into `tamirat-wubie/mullusi` `main` at
`93b7a6de942241424564f686aebee023a469ecde`.

The earlier accidental product-route push to `ci/optimize-actions-minutes` was
removed with a lease-protected branch update before PR #84 was repaired and
merged.

During the first Pages-source investigation,
`https://github.com/mullusi/mullusi.github.io.git` returned repository not found
from the current session. The active source was later identified through the
GitHub Pages API as `mullusi/mullusi-site`.

## Live Route Verification

On 2026-05-15, a direct probe of `https://mullusi.com/mullu` returned HTTP 200
from the current environment. The fetched body contained:

```text
Mullu, by Mullusi
Mullu CLI
Mullu Control Plane
```

That closes `website_deployment_verification` for the `/mullu` fallback route.
It does not close paid public launch, standalone subdomain publication, legal
clearance, domain ownership, homepage update, app title update, or SDK/API
stability review.

Tracking issue: `https://github.com/tamirat-wubie/mullusi/issues/87`.

## Live Proof Boundary Verification

On 2026-05-15, the active GitHub Pages source was identified as
`mullusi/mullusi-site`. PR #1 in that repository published `/proof/`, linked
`/mullu/` to the proof boundary, and added `/proof/` to the live sitemap.

Direct probes from the current environment returned:

```text
https://mullusi.com/proof/      HTTP 200, contains Public proof boundary and AwaitingEvidence
https://mullusi.com/mullu/      HTTP 200, contains /proof/ and Review proof boundary
https://mullusi.com/sitemap.xml HTTP 200, contains https://mullusi.com/proof/
```

Tracking issue `https://github.com/tamirat-wubie/mullusi/issues/90` is closed.
This closes the public proof boundary route only; live runtime witness closure
remains pending until gateway witness, runtime conformance, and health endpoints
are reachable and validated.

## Live Homepage Boundary Verification

On 2026-05-15, `mullusi/mullusi-site` PR #2 updated the active homepage to make
the public product hierarchy explicit: Mullusi is the company umbrella and
Mullu is the flagship governed symbolic product.

Direct probes from the current environment returned:

```text
https://mullusi.com/ HTTP 200, contains Mullusi builds governed symbolic products
https://mullusi.com/ contains /mullu/, /proof/, and AwaitingEvidence
```

This closes the homepage product-boundary copy gap. It does not close live
runtime witness closure, standalone `mullu.mullusi.com` publication, legal
clearance, paid launch readiness, or SDK/API stability review.

## Production Claim Boundary Verification

On 2026-05-16, `mullusi/mullusi-site` PR #3 was verified after merge. The
active homepage and `/mullu/` product route both expose a production-claim
boundary that separates company identity, product identity, and live runtime
witness status.

Direct probes from the current environment returned:

```text
https://mullusi.com/       HTTP 200, contains Production Claim Boundary and AwaitingEvidence
https://mullusi.com/mullu/ HTTP 200, contains Production Claim Boundary and AwaitingEvidence
```

The active site validator now requires the production boundary section and the
terms `Mullusi`, `Mullu`, `AwaitingEvidence`, `/health`, `/gateway/witness`,
`/runtime/conformance`, and `/proof/` on both public pages.

This closes the public website claim-boundary copy gap. It does not close live
runtime witness closure, because the gateway endpoints remain unpublished.
