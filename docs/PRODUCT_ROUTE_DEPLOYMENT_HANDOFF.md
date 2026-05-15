# Product Route Deployment Handoff

Purpose: record the deployment handoff for the Mullu private-beta product route.
Governance scope: source artifact, live website target, workflow validation, and post-deploy verification.
Dependencies: `site/mullu/index.html`, `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-07.md`, `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md`.
Invariants: this handoff closes `website_deployment_verification` only for the private-beta product route; paid public launch remains blocked until legal, trademark, domain, app-title, and SDK/API gates close.

## Source And Target

| Field | Value |
| --- | --- |
| Governed source artifact | `site/mullu/index.html` |
| Website repo copy target | `../mullusi_website/mullu/index.html` |
| Intended live route | `https://mullusi.com/mullu/` |
| Website main branch | `origin/main` |
| Live website repository | `https://github.com/mullusi/mullusi-site.git` |
| Current live commit carrying route | `ea4159d Add Mullu product route` |
| Site validation workflow | `Validate Site` run `25919014515` passed |
| Pages deployment workflow | `pages-build-deployment` run `25919013720` passed |
| Initial non-live route PR | `https://github.com/tamirat-wubie/mullusi/pull/84` |
| Non-live boundary update PR | `https://github.com/tamirat-wubie/mullusi/pull/86` |
| Non-live route commit | `7965ae4e393457017611f6bd4e9b1f3e6dea4940` |
| Redundant route PR | `https://github.com/tamirat-wubie/mullusi/pull/85` closed after route appeared on `origin/main` |
| Historical live-route blocker issue | `https://github.com/tamirat-wubie/mullusi/issues/87`; superseded by May 15 direct live-route evidence |
| DNS Pages target | `mullusi.github.io` |
| Product first reference | `Mullu, by Mullusi` |
| Launch posture | private beta / request access |
| Live status | HTTP 200 |

## Copy Result

The governed product route artifact was copied from:

```text
site/mullu/index.html
```

to the sibling website repository target:

```text
../mullusi_website/mullu/index.html
```

The initial route work first landed in the non-live repository
`tamirat-wubie/mullusi` through PR #84, while the focused route PR #85 was
closed as redundant after the route appeared on `origin/main` at commit
`39014fd`. PR #86 later clarified the Mullusi/Mullu boundary in that repository.
That history is retained as source-control lineage, but it was not the active
custom-domain Pages source.

```text
https://github.com/tamirat-wubie/mullusi/pull/84
https://github.com/tamirat-wubie/mullusi/pull/85
https://github.com/tamirat-wubie/mullusi/pull/86
```

The live custom-domain source was identified as:

```text
https://github.com/mullusi/mullusi-site.git
```

PR #86 later replaced the product route copy with a clearer Mullusi/Mullu
boundary: Mullusi is the company, research, governance, and trust umbrella;
Mullu is the flagship governed symbolic intelligence product. It also added
explicit public claim handling for repository-verified evidence versus live
deployment witness evidence. PR #86 passed `fast-check` and merged into
`tamirat-wubie/mullusi` `main` at `7965ae4e393457017611f6bd4e9b1f3e6dea4940`.

The earlier accidental product-route push to `ci/optimize-actions-minutes` was
removed with a lease-protected branch update before PR #84 was repaired and
merged.

The route and sitemap update were committed there as `ea4159d Add Mullu product
route`. The repository validation workflow and Pages deployment completed
successfully.

## Live Verification

1. `https://mullusi.com/mullu/` returns `HTTP 200`.
2. The page title includes `Mullu, by Mullusi`.
3. The page contains `private beta`, `Request access`, and `Mullu Control Plane`.
4. The page contains `Symbols are atomic. Meaning is relational. Traversal is governed. Judgment is earned.`
5. `https://mullusi.com/sitemap.xml` returns `HTTP 200` and includes `https://mullusi.com/mullu/`.

The authoritative evidence is recorded in:

```text
docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md
```

`website_deployment_verification` is closed for the private-beta route. Paid
public launch remains blocked by the remaining clearance gates.
