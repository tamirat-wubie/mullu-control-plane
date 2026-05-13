# Website Recheck Log

Purpose: record public website recheck signals for `mullusi.com` and Mullu launch-route readiness.
Governance scope: public index evidence, deployment readiness, launch blockers, and route verification boundaries.
Dependencies: `docs/WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md`, `docs/PUBLIC_NAMING_READINESS.md`.
Invariants: this log is non-authoritative; it cannot close `website_deployment_verification`; direct live-route verification remains required.

## Recheck 2026-05-07

| Field | Value |
| --- | --- |
| Recheck type | Public search and index mirror review |
| Source authority | non-authoritative |
| Checked route | `mullusi.com` |
| Observed signal | Public index result reported `GitHub Pages site-not-found` content from an older crawl |
| Product collision signal | No obvious indexed `Mullu, by Mullusi` product/company collision surfaced |
| Launch impact | Keep `homepage_update` and `website_deployment_verification` open |

## Decision

Direct route verification still required.

The public index signal is useful as a readiness warning, but it is not proof
of the current live deployment state. Before any public launch route is used,
record live evidence in `docs/WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md` showing
that the selected route returns intentional Mullu/Mullusi content, uses HTTPS,
and is not a GitHub Pages site-not-found or parked-domain page.

## Follow-Up Requirements

1. Verify `https://mullusi.com` directly from a browser or deployment monitor.
2. Verify `https://mullusi.com/mullu` if used as the product fallback route.
3. Verify `https://mullu.mullusi.com` if used as the product subdomain.
4. Capture timestamp, HTTP status, canonical URL, page title, and visible first-reference copy.
5. Keep paid public launch blocked until `website_deployment_verification` closes.
