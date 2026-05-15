# Product Route Deployment Handoff

Purpose: record the deployment handoff for the Mullu private-beta product route.
Governance scope: source artifact, copied website target, live-route publication, and post-deploy verification.
Dependencies: `site/mullu/index.html`, `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-07.md`.
Invariants: this handoff closes `website_deployment_verification` only for the `/mullu` fallback route; paid public launch remains blocked until the remaining public naming gates close.

## Source And Target

| Field | Value |
| --- | --- |
| Governed source artifact | `site/mullu/index.html` |
| Website repo copy target | `../mullusi/mullu/index.html` |
| Intended live route | `https://mullusi.com/mullu` |
| Website main branch | `origin/main` |
| Initial merged PR carrying route | `https://github.com/tamirat-wubie/mullusi/pull/84` |
| Current merged PR carrying route boundary update | `https://github.com/tamirat-wubie/mullusi/pull/86` |
| Current merged PR carrying launch literals | `https://github.com/tamirat-wubie/mullusi/pull/88` |
| Current main commit carrying route | `93b7a6de942241424564f686aebee023a469ecde` |
| Redundant route PR | `https://github.com/tamirat-wubie/mullusi/pull/85` closed after route appeared on `origin/main` |
| Live-route blocker issue | `https://github.com/tamirat-wubie/mullusi/issues/87` resolved by PR #88 live probe |
| DNS Pages target | `mullusi.github.io` |
| Pages source access | `https://github.com/mullusi/mullusi.github.io.git` returned repository not found from current session |
| Product first reference | `Mullu, by Mullusi` |
| Launch posture | private beta / request access |
| Live status | live route verified; HTTP 200 |

## Copy Result

The governed product route artifact was copied from:

```text
site/mullu/index.html
```

to the sibling website repository target:

```text
../mullusi/mullu/index.html
```

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
