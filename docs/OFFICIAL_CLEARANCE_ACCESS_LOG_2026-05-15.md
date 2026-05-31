# Official Clearance Access Log 2026-05-15

Purpose: record the official trademark and domain-evidence access attempts for the Mullu public naming gate.
Governance scope: USPTO, WIPO, EUIPO/TMview, TSDR serial verification, RDAP/DNS domain evidence, and launch-state boundaries.
Dependencies: `docs/mullu-name-clearance-draft.json`, `docs/TSDR_EVIDENCE_TEMPLATE.md`, `docs/DOMAIN_OWNERSHIP_RECORD_TEMPLATE.md`.
Invariants: this log does not close official trademark, close-variant, domain ownership, or legal-review gates.

## Official Source Requirements

| Source | Required use | Gate impact |
| --- | --- | --- |
| USPTO Trademark Search | Search exact and similar marks for `MULLU`, `MULLUSI`, `Mullu by Mullusi`, product surfaces, and `MULU` | `uspto_search` remains open |
| USPTO TSDR | Check status and documents for required close-variant serials | `close_variant_review` remains open |
| WIPO Global Brand Database | Search international, Madrid, Lisbon, 6ter, and participating office collections | `wipo_search` remains open |
| EUIPO eSearch plus / TMview | Search EU and TMview participating office records | `euipo_tmview_search` remains open |
| Registrar/RDAP/DNS evidence | Verify ownership or availability of selected product domains | `domain_ownership` remains open |

## USPTO Evidence Attempt

Direct TSDR serial endpoints were attempted for:

1. `99518598`
2. `99264214`
3. `85772539`
4. `85494313`
5. `85222451`

Observed response from `https://tsdrapi.uspto.gov/ts/cd/casestatus/sn99518598/content.html`:

```text
Beginning October 2, you will need to register for an API key to download bulk data from TSDR APIs. Register for an API key at https://account.uspto.gov/api-manager/. Learn more about this requirement at https://developer.uspto.gov/api-catalog.
```

Decision: unauthenticated TSDR API access is insufficient to close the close-variant serial evidence. A USPTO.gov account/API key or browser-based TSDR status capture is required.

## Domain Evidence Attempt

RDAP checks were attempted for:

1. `mullu.ai`
2. `mullu.app`
3. `mullu.dev`
4. `getmullu.com`

Observed result: RDAP requests to `https://rdap.org/domain/...` timed out from the current environment.

DNS checks were attempted for:

1. `mullu.ai`
2. `mullu.app`
3. `mullu.dev`
4. `getmullu.com`
5. `mullu.mullusi.com`

Observed result: local DNS requests timed out from the current environment.

Decision: these timeouts are not registrar evidence. Domain ownership remains open until registrar screenshots/exports, DNS zone evidence, or a reliable RDAP/WHOIS response is recorded.

## Follow-Up Access Recheck 2026-05-31

This follow-up was run from the local Codex workspace on 2026-05-31. It records
source reachability and domain-resolution signals only. It does not attach the
required official search result exports, screenshots, registrar evidence, DNS
zone records, or reviewer decisions.

### Official Search Entry Reachability

| Source | URL | Observed result | Gate impact |
| --- | --- | --- | --- |
| USPTO Trademark Search | `https://tmsearch.uspto.gov/` | HTTP 200 | Does not close `uspto_search`; query result exports still required |
| USPTO trademark search instructions | `https://www.uspto.gov/trademarks/search` | HTTP 200 | Confirms search entry path only |
| WIPO Global Brand Database | `https://www.wipo.int/reference/en/branddb/` | HTTP 200 | Does not close `wipo_search`; official query exports still required |
| WIPO trademark tools portal | `https://ipportal.wipo.int/tools/trademarks` | HTTP 200 | Confirms search entry path only |
| EUIPO search tools | `https://www.euipo.europa.eu/en/search-ip` | HTTP 200 | Does not close `euipo_tmview_search`; official query exports still required |
| TMview portal | `https://www.tmdn.org/tmview/` | HTTP 200 | Does not close `euipo_tmview_search`; official query exports still required |

### TSDR API Recheck

| Serial | URL | Observed result | Gate impact |
| --- | --- | --- | --- |
| `99518598` | `https://tsdrapi.uspto.gov/ts/cd/casestatus/sn99518598/info.json` | HTTP 401 Unauthorized | Does not close `close_variant_review`; authorized API or browser capture still required |
| `99264214` | `https://tsdrapi.uspto.gov/ts/cd/casestatus/sn99264214/info.json` | HTTP 401 Unauthorized | Does not close `close_variant_review`; authorized API or browser capture still required |

The prior API-key blocker remains active. No official TSDR serial status packet
is attached by this follow-up.

### Domain Signal Recheck

| Target | Check | Observed result | Gate impact |
| --- | --- | --- | --- |
| `mullu.ai` | DNS A lookup | DNS name does not exist | Not ownership evidence |
| `mullu.app` | DNS A lookup | DNS name does not exist | Not ownership evidence |
| `mullu.dev` | DNS A lookup | DNS name does not exist | Not ownership evidence |
| `getmullu.com` | DNS A lookup | DNS name does not exist | Not ownership evidence |
| `mullu.mullusi.com` | `nslookup` | no host A/AAAA answer; authoritative SOA returned for `mullusi.com` | Not route publication or ownership evidence |
| `mullusi.com` | DNS A lookup | resolves to Cloudflare addresses `104.21.82.46` and `172.67.153.104` | Confirms root domain resolution only |
| `mullusi.com` | DNS NS lookup | `harleigh.ns.cloudflare.com`, `leonard.ns.cloudflare.com` | Confirms public nameserver signal only |
| `mullu.ai` | RDAP via `https://rdap.org/domain/mullu.ai` | timed out | Not registrar evidence |
| `mullu.app` | RDAP via `https://rdap.org/domain/mullu.app` | HTTP 404 Not Found | Not registrar availability or ownership evidence |
| `mullu.dev` | RDAP via `https://rdap.org/domain/mullu.dev` | HTTP 404 Not Found | Not registrar availability or ownership evidence |
| `getmullu.com` | RDAP via `https://rdap.org/domain/getmullu.com` | timed out | Not registrar evidence |

Decision: the follow-up improves the access trail but does not satisfy any
remaining closure requirement. Domain ownership remains blocked until registrar,
DNS-zone, HTTPS, renewal, MFA, and lock evidence is captured for the selected
route.

## Required Evidence Still Missing

| Gate | Missing evidence |
| --- | --- |
| `uspto_search` | Official USPTO search results for required terms and classes |
| `wipo_search` | WIPO Global Brand Database result captures |
| `euipo_tmview_search` | EUIPO/TMview result captures |
| `close_variant_review` | Official TSDR serial status and legal confusion analysis |
| `domain_ownership` | Registrar/DNS ownership or controlled selected-route evidence |
| `legal_review` | Qualified legal/trademark decision |

## Gate Decision

No clearance gate is closed by this log.

This log converts an unknown access state into a bounded evidence requirement:

1. Acquire USPTO API access or capture browser-based official TSDR records.
2. Run official USPTO, WIPO, and EUIPO/TMview searches.
3. Record registrar or DNS-zone evidence for the selected route.
4. Submit the evidence to qualified trademark/legal review.

STATUS:
  Completeness: 100%
  Invariants verified: [official-source boundary recorded, API-key blocker recorded, domain timeout not treated as clearance, 2026-05-31 follow-up does not close gates, paid public launch remains blocked]
  Open issues: [official trademark searches, TSDR status evidence, domain ownership evidence, legal review]
  Next action: capture official USPTO/WIPO/EUIPO search screenshots or exports and registrar/DNS ownership evidence

