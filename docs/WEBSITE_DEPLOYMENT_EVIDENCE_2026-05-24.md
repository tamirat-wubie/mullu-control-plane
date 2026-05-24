# Website Deployment Evidence 2026-05-24

Purpose: record current live-route evidence for the Mullusi company umbrella and Mullu product route.
Governance scope: public website routing, product/company naming boundary, production-claim boundary, and runtime-witness separation.
Dependencies: `docs/WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md`, `docs/WEBSITE_UPDATE_CHECKLIST.md`, `docs/PUBLIC_NAMING_READINESS.md`, `DEPLOYMENT_STATUS.md`.
Invariants: Mullusi remains the company and governance authority; Mullu remains the flagship product route; website publication does not imply API, gateway, or production-runtime publication.

## Evidence Summary

| Field | Value |
| --- | --- |
| Evidence date | 2026-05-24 |
| Company route | `https://mullusi.com/` |
| Product route | `https://mullusi.com/mullu/` |
| Proof route | `https://mullusi.com/proof/` |
| Launch posture | private beta / request access |
| Runtime claim posture | not a production-runtime claim |
| Blocking runtime issue | GitHub issue `#330`, deployment witness runtime inputs and reachable gateway endpoints |

## Live Route Probes

| Probe | Observed result | Decision impact |
| --- | --- | --- |
| `curl.exe -I -L https://mullusi.com/` | HTTP 200 | Company homepage is reachable |
| `curl.exe -I -L https://mullusi.com/mullu/` | HTTP 200 | Product fallback route is reachable |
| `curl.exe -I -L https://mullusi.com/proof/` | HTTP 200 | Public proof route is reachable |
| `curl.exe -L https://mullusi.com/mullu/` | Contains `Mullu, by Mullusi` | Product/company first-reference boundary is present |
| `curl.exe -L https://mullusi.com/mullu/` | Contains `private beta` and `Request access` | Paid public launch is not claimed |
| `curl.exe -L https://mullusi.com/mullu/` | Contains `Production Claim Boundary` | Runtime claim boundary is visible |
| `curl.exe -L https://mullusi.com/mullu/` | Contains `Mullu Control Plane` | Product surface naming is present |

## Runtime Separation

Website route publication is closed for the public-company and private-beta
product surfaces. It does not close deployment witness publication.

The current runtime boundary remains:

1. `api.mullusi.com` does not yet have a valid gateway DNS resolution receipt.
2. `/health` is not reachable from the deployment witness preflight.
3. `/gateway/witness` is not reachable and cannot provide the required signed runtime witness fields.
4. `/runtime/conformance` is not reachable and cannot provide the required conformance certificate fields.
5. `DEPLOYMENT_STATUS.md` remains the authority for production-runtime claim state.

## Design Decision

Mullusi should continue to serve as the umbrella company and governance
authority. Mullu should remain the product family and flagship symbolic work
surface. The public website can describe product intent, private beta access,
architecture, proof boundaries, and control-plane surfaces now. It must not
claim published production runtime health until issue `#330` is closed by
signed deployment witness evidence.

STATUS:
  Completeness: 100%
  Invariants verified: [company route live, product route live, proof route live, product/company boundary present, private-beta boundary present, production-runtime claim withheld]
  Open issues: [api.mullusi.com DNS and runtime witness closure remain blocked under issue #330]
  Next action: publish gateway DNS and runtime endpoints, then rerun deployment witness preflight before changing production claim copy
