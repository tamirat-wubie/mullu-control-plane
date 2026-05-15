# Mullu Name Clearance Preliminary

Purpose: record the initial non-legal clearance sweep for the `Mullu` flagship product name.
Governance scope: public name collision review, domain signal review, trademark search boundary, and launch-blocking evidence.
Dependencies: `docs/PRODUCT_IDENTITY.md`.
Invariants: this document is not legal advice; launch naming remains blocked until formal trademark and registrar checks are complete.

## Naming Candidate

| Field | Value |
| --- | --- |
| Candidate | Mullu |
| Owner brand | Mullusi |
| First-reference form | Mullu, by Mullusi |
| Product role | Flagship governed symbolic intelligence product |
| Technical architecture term | Mullu Platform |

## Preliminary Public Search Findings

| Finding | Surface | Relevance | Risk |
| --- | --- | --- | --- |
| `Mullu TV` | Online film and communication platform for original peoples of Abya Yala | Media/cultural platform, not software/SaaS governance | Medium review item |
| `The Last Mullu` | Indie game on Steam | Game title, not enterprise software/SaaS | Low to medium review item |
| `Thillu Mullu` | Tamil-language film title | Entertainment title, not software/SaaS | Low review item |
| Historical/cultural use of `mullu` | Book and cultural references around shell/material terms | Descriptive or cultural references outside software | Low review item |
| `mullu` in Estonian | Common adverb meaning "last year" | General-language meaning, not software/SaaS | Low review item |
| `mullu` in Kannada/Telugu transliteration | Word associated with "thorn" | General-language/cultural meaning, not software/SaaS | Low review item |
| Mullu Cafe / Mullu local stores | Restaurant, retail, or local commerce listings | Local commerce outside software/SaaS | Low review item |
| Mullus Boards.Clothing | German retail/skatewear shop using a nearby plural/possessive form | Retail apparel, not software/SaaS | Low to medium review item |
| `MULU` by MULU Corp. | Live/pending U.S. trademark records reported by public trademark mirrors in Class 9, Class 35, and Class 42-adjacent software/business/technical services | Similar spelling and similar software/service classes; not exact `MULLU`, but close enough for legal review | High review item |
| Prior `MULU` by Mulu, Inc. | Public trademark mirror reports an older U.S. Class 42 registration as dead/abandoned | Historic software/service-adjacent mark; may affect clearance history and search strategy | Medium review item |

No exact `MULLU` enterprise software, SaaS governance, browser extension,
developer-tool, or symbolic runtime product conflict surfaced in the preliminary
public search. However, the close `MULU` software/service filings require
qualified trademark review before any public paid launch decision.

## Mullusi.com Initial Website Signal

Public index mirrors reported `mullusi.com` as a GitHub Pages site-not-found
page in a prior crawl. Treat this as a website readiness issue, not a naming
clearance issue:

1. The company domain should not remain in a site-not-found state before public
   launch.
2. The earliest public page can live at `mullusi.com/mullu` if standalone
   product domains are unavailable.
3. Any homepage update must preserve the company/product split:
   `Mullu, by Mullusi`.

This signal requires direct deployment verification before launch because public
index mirrors can lag the live site.

## Public Web Update 2026-05-07

| Source surface | Result | Decision impact |
| --- | --- | --- |
| Public search for `mullusi.com` | Returned a domain-information mirror indicating GitHub Pages site-not-found content in an older crawl | Keep website deployment verification in launch blockers; see `docs/WEBSITE_RECHECK_LOG.md` |
| Direct route probe for `mullusi.com` | Root redirects to `https://www.mullusi.com/` and returns HTTP 200 with company-level Mullusi copy | Company homepage is live; product homepage update remains open |
| Direct route probe for `mullusi.com/mullu` | Redirects to `https://www.mullusi.com/mullu` and returns HTTP 404 | Product fallback route is not live |
| Direct DNS probe for `mullu.mullusi.com` | DNS name does not exist | Product subdomain is not live |
| Public search for `Mullu Mullusi` | No obvious indexed product/company collision surfaced | No new blocker |
| Public trademark mirrors for close variant `MULU` | Returned live/pending records connected to software, business consulting, and technical services | Escalate close-variant review from medium to high |
| USPTO TSDR official access path | USPTO FAQ confirms TSDR status lookup by serial number and an API-style status URL pattern | Add serial-specific official verification to the trademark runbook |

The `MULU` findings do not automatically reject `Mullu`, but they change the
clearance posture: official USPTO/TSDR review by serial number and attorney
confusion analysis are now mandatory before `public_paid_launch_allowed` can
become true.

## Public Web Update 2026-05-15

| Source surface | Result | Decision impact |
| --- | --- | --- |
| Direct route probe for `https://mullusi.com/mullu/` | Returns HTTP 200 with intentional `Mullu, by Mullusi` private-beta product content | Close `website_deployment_verification` for the fallback product route |
| Sitemap probe for `https://mullusi.com/sitemap.xml` | Returns HTTP 200 and includes `https://mullusi.com/mullu/` | Confirms product route is published in the public site map |
| Website source repository | `mullusi/mullusi-site` commit `ea4159d Add Mullu product route` | Confirms the live custom-domain Pages source |
| Pages deployment | `Validate Site` run `25919014515` and `pages-build-deployment` run `25919013720` completed successfully | Confirms deployment pipeline passed |

This update resolves the website-route readiness issue for private-beta access
only. It does not clear trademark, domain ownership, legal review, app-title, or
SDK/API stability gates.

## Close-Variant Records To Verify

| Serial | Mark | Preliminary risk | Required action |
| --- | --- | --- | --- |
| `99518598` | `MULU` | High review item because public mirrors report software/service-adjacent classes | Verify official TSDR status and legal confusion risk |
| `99264214` | `MULU` | High review item because public mirrors report business/technical-service classes | Verify official TSDR status and legal confusion risk |
| `85772539` | `MULU` | Medium review item because public mirrors report an older live/registered record | Verify official TSDR status and scope |
| `85494313` | `MULU` | Medium review item because public mirrors report an older cancelled record | Verify official TSDR status and history |
| `85222451` | `MULU` | Medium review item because public mirrors report an older cancelled record | Verify official TSDR status and history |

## Domain Signal Review

Exact public search queries returned no indexed results for:

1. `mullu.ai`
2. `mullu.app`
3. `mullu.dev`
4. `getmullu.com`

Local DNS lookups in the current environment did not return records for these
domains. This is not a registrar availability check and must not be treated as
ownership clearance.

## Formal Clearance Required

Before public launch or paid-user rollout, complete:

1. USPTO search for `Mullu` in software/SaaS classes, including Class 9 and Class 42.
2. EUIPO eSearch plus and TMview searches for `Mullu` across EU and participating offices.
3. WIPO Global Brand Database search for `Mullu`.
4. Registrar availability checks for `mullu.ai`, `mullu.app`, `mullu.dev`, and `getmullu.com`.
5. Common-law search across GitHub, npm, PyPI, Chrome Web Store, Microsoft Edge Add-ons, Firefox Add-ons, Product Hunt, Crunchbase, LinkedIn, and major app stores.
6. Confusion analysis against `Mullu TV`, `The Last Mullu`, and close-variant `MULU` marks.
7. Direct deployment verification for new public routes or domains not covered by the 2026-05-15 fallback-route evidence.

## Official Search Tools

| Authority | Tool | Required query |
| --- | --- | --- |
| USPTO | `https://tmsearch.uspto.gov` | Exact `MULLU`, exact `MULLUSI`, contains `MULLU`, phonetic/similar variants |
| USPTO ID Manual | `https://idm-tmng.uspto.gov` | Goods/services language for software, SaaS, browser extension, governance, and enterprise workflow terms |
| WIPO | `https://branddb.wipo.int` | Exact `MULLU`, exact `MULLUSI`, Madrid and participating national/regional marks |
| EUIPO | `https://euipo.europa.eu/eSearch` | Exact `MULLU`, exact `MULLUSI`, owners, representatives, bulletins |
| TMview | `https://www.tmdn.org/tmview` | Participating national, international, and EU-level trade marks |
| TMclass | `https://tmclass.tmdn.org` | Classification language for software/SaaS descriptions |

## Class Review Matrix

| Class | Why it matters for Mullu |
| --- | --- |
| Nice Class 9 | Downloadable software, browser extensions, developer tools, CLI tooling, local runtime packages |
| Nice Class 35 | Business workflow operations, administrative process support, enterprise operations services |
| Nice Class 38 | Communication surfaces if Mullu routes messages, notifications, or collaboration channels |
| Nice Class 41 | Research, training, education, tutorials, certification, and operator learning surfaces |
| Nice Class 42 | SaaS, hosted software, cloud execution, developer platform, software design, technical governance tooling |
| Nice Class 45 | Compliance, audit, risk, and policy support if marketed as regulatory/governance assistance |

## Search Term Matrix

| Type | Terms |
| --- | --- |
| Exact | `MULLU`, `Mullu`, `mullu` |
| Owner pair | `MULLUSI`, `Mullusi`, `Mullu by Mullusi` |
| Surface family | `Mullu Inspect`, `Mullu CLI`, `Mullu Code`, `Mullu Desk`, `Mullu Control Plane` |
| Similar spelling | `Mulu`, `Mullu`, `Muluu`, `Mullus`, `Mullusi` |
| Sound-alike | `Moolu`, `Mulu`, `Mulu AI`, `Mullu AI` |

## Provisional Decision

Proceed internally with `Mullu` as the flagship product name while preserving
the unresolved legal and domain gates.

Do not announce paid public availability under `Mullu` until trademark and
registrar checks close.

## Resolution Status

| Gate | Status |
| --- | --- |
| Product architecture fit | Passed |
| Existing Mullu surface coherence | Passed |
| Preliminary public web collision scan | Passed with review items |
| Exact-domain indexed-result scan | No indexed blockers found |
| Close-variant `MULU` review | High review item |
| `mullusi.com/mullu` deployment signal | Passed for private-beta fallback route |
| DNS availability | Inconclusive |
| Registrar availability | Not checked |
| Trademark clearance | Not checked |
| Legal clearance | Not complete |
