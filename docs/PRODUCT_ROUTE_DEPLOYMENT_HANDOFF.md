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
| Merged PR carrying route | `https://github.com/tamirat-wubie/mullusi/pull/84` |
| Main commit carrying route | `39014fd` |
| Redundant route PR | `https://github.com/tamirat-wubie/mullusi/pull/85` closed after route appeared on `origin/main` |
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

The earlier accidental product-route push to `ci/optimize-actions-minutes` was
removed with a lease-protected branch update before PR #84 was repaired and
merged.

## Remaining Deployment Work

1. Identify the repository or Pages source behind `mullusi.github.io`.
2. Copy or merge `mullu/index.html` into that live Pages source.
3. Re-run direct probes for `https://mullusi.com/mullu` after publish propagation.
4. Replace the failed `HTTP 404` evidence with passing `HTTP 200` evidence.
5. Keep `website_deployment_verification` open until the live route is verified.
