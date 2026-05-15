# Public Naming Review Packet

Purpose: provide the reviewer-facing packet for deciding whether `Mullu` can move from internal alignment to public launch.
Governance scope: trademark evidence, domain evidence, website evidence, legal decision, launch-state mutation, and reviewer signoff.
Dependencies: `docs/public-naming-readiness.json`, `docs/mullu-name-clearance-draft.json`, `docs/TSDR_EVIDENCE_TEMPLATE.md`, `docs/WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md`, `docs/DOMAIN_OWNERSHIP_RECORD_TEMPLATE.md`.
Invariants: `Mullu` remains internally aligned only; paid public launch remains blocked until all open gates close with evidence.

## Current Decision

| Field | Value |
| --- | --- |
| Product name | Mullu |
| Company / governance authority | Mullusi |
| First public reference | Mullu, by Mullusi |
| Current state | internal_alignment_only |
| Paid public launch allowed | false |
| Final clearance decision | pending |

## Review Inputs

| Input | Required reviewer action |
| --- | --- |
| `docs/mullu-name-clearance-draft.json` | Fill official search outcomes, final legal decision, and launch effect |
| `docs/OFFICIAL_CLEARANCE_ACCESS_LOG_2026-05-15.md` | Review blocked official API/RDAP access attempts and required replacement evidence |
| `docs/TSDR_EVIDENCE_TEMPLATE.md` | Capture official USPTO/TSDR status for each required `MULU` serial |
| `docs/DOMAIN_OWNERSHIP_RECORD_TEMPLATE.md` | Record registrar, DNS, renewal, and security evidence |
| `docs/WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md` | Record live route, HTTPS, copy, and site-not-found checks |
| `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md` | Verify private-beta fallback route evidence already closed |
| `docs/PUBLIC_LAUNCH_COPY.md` | Confirm copy remains waitlist/private beta/request-access until clearance closes |
| `docs/public-naming-readiness.json` | Update only after evidence closes the matching gate |
| `docs/PUBLIC_NAMING_ARTIFACT_MANIFEST.md` | Confirm all naming package artifacts are present |

## Blocking Evidence Still Required

| Gate | Evidence required |
| --- | --- |
| `uspto_search` | Official USPTO exact/similar search evidence for required terms, classes, and serials |
| `wipo_search` | Official WIPO Global Brand Database evidence |
| `euipo_tmview_search` | Official EUIPO/TMview evidence |
| `close_variant_review` | Legal confusion analysis for required `MULU` records |
| `domain_ownership` | Registrar and DNS ownership evidence for selected product route |
| `legal_review` | Qualified legal/trademark conclusion |
| `app_title_update` | User-facing app title update after authorization |
| `sdk_api_stability_review` | Confirmation that technical `Mullu Platform` contracts remain intentional |

## Closed Website Evidence

| Gate | Evidence |
| --- | --- |
| `homepage_update` | Product landing page is live at `https://mullusi.com/mullu/` with private-beta/request-access copy |
| `website_deployment_verification` | `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md` records HTTP 200 product-route and sitemap checks |

## Required TSDR Serials

| Serial | Required action |
| --- | --- |
| `99518598` | Capture official TSDR status and legal risk |
| `99264214` | Capture official TSDR status and legal risk |
| `85772539` | Capture official TSDR status and history |
| `85494313` | Capture official TSDR status and history |
| `85222451` | Capture official TSDR status and history |

## Required Domain Candidates

| Priority | Domain | Launch meaning |
| ---: | --- | --- |
| 1 | `mullu.ai` | Preferred product domain |
| 2 | `mullu.app` | App-forwarding product domain |
| 3 | `mullu.dev` | Developer/product domain |
| 4 | `getmullu.com` | Marketing fallback |
| 5 | `mullu.mullusi.com` | Controlled DNS fallback |
| 6 | `mullusi.com/mullu` | Company-site fallback |

## Required Website Routes

| Route | Review requirement |
| --- | --- |
| `https://mullusi.com` | Company homepage must be intentional and live |
| `https://mullusi.com/mullu` | Product fallback must be intentional if used |
| `https://mullu.mullusi.com` | Controlled subdomain fallback must be intentional if used |
| `https://docs.mullusi.com` | Docs route must be live if linked |
| `https://dashboard.mullusi.com` | Control Plane route must be live if linked |
| `https://api.mullusi.com` | API route must be live if linked |

## Do Not Approve If

1. Any official search remains open.
2. Any required TSDR serial lacks official evidence.
3. Legal review is missing or concludes `hold` or `rename`.
4. Domain ownership or DNS control is missing for the selected route.
5. `mullusi.com` or the selected product route shows a site-not-found or parked-domain page.
6. Paid public launch copy appears before clearance closes.
7. `public_paid_launch_allowed` is changed without closing all open gates.

## Verification Commands

```powershell
python .\scripts\validate_public_naming_readiness.py
python .\scripts\report_public_naming_readiness.py
python .\scripts\plan_public_naming_transition.py
python -m pytest tests\test_public_naming_readiness.py -q
python .\scripts\validate_release_status.py
```

## Reviewer Decision

Choose one after evidence review:

1. `proceed`
2. `proceed_with_risk_controls`
3. `hold`
4. `rename`

Decision:

```text
pending
```
