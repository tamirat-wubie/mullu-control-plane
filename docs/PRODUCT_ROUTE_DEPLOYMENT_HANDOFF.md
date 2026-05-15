# Product Route Deployment Handoff

Purpose: record the deployment handoff for the Mullu private-beta product route.
Governance scope: source artifact, copied website target, live-route blocker, and post-deploy verification.
Dependencies: `site/mullu/index.html`, `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-07.md`.
Invariants: this handoff does not close `website_deployment_verification`; the route is not yet live until deployed and probed.

## Source And Target

| Field | Value |
| --- | --- |
| Governed source artifact | `site/mullu/index.html` |
| Website repo copy target | `../mullusi/mullu/index.html` |
| Intended live route | `https://mullusi.com/mullu` |
| Website main branch | `origin/main` |
| Initial merged PR carrying route | `https://github.com/tamirat-wubie/mullusi/pull/84` |
| Current merged PR carrying route boundary update | `https://github.com/tamirat-wubie/mullusi/pull/86` |
| Current main commit carrying route | `7965ae4e393457017611f6bd4e9b1f3e6dea4940` |
| Redundant route PR | `https://github.com/tamirat-wubie/mullusi/pull/85` closed after route appeared on `origin/main` |
| Live-route blocker issue | `https://github.com/tamirat-wubie/mullusi/issues/87` |
| DNS Pages target | `mullusi.github.io` |
| Pages source access | `https://github.com/mullusi/mullusi.github.io.git` returned repository not found from current session |
| Product first reference | `Mullu, by Mullusi` |
| Launch posture | private beta / request access |
| Live status | not yet live |

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

The earlier accidental product-route push to `ci/optimize-actions-minutes` was
removed with a lease-protected branch update before PR #84 was repaired and
merged.

## Remaining Deployment Work

1. Identify the repository or Pages source behind `mullusi.github.io`.
2. Copy or merge `mullu/index.html` into that live Pages source.
3. Re-run direct probes for `https://mullusi.com/mullu` after publish propagation.
4. Replace the failed `HTTP 404` evidence with passing `HTTP 200` evidence.
5. Keep `website_deployment_verification` open until the live route is verified.

Tracking issue: `https://github.com/tamirat-wubie/mullusi/issues/87`.
