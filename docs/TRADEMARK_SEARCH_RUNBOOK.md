# Trademark Search Runbook

Purpose: define the exact search procedure for clearing `Mullu` as the public product name.
Governance scope: trademark search evidence, search variants, Nice classes, owner records, conflict notes, and launch-blocking decisions.
Dependencies: `docs/PRODUCT_IDENTITY.md`, `docs/NAME_CLEARANCE_PRELIMINARY.md`, `docs/PUBLIC_NAMING_READINESS.md`.
Invariants: this runbook is not legal advice; public paid launch remains blocked until qualified legal review closes.

## Candidate

| Field | Value |
| --- | --- |
| Product name | Mullu |
| Company / owner brand | Mullusi |
| First public reference | Mullu, by Mullusi |
| Product category | Governed symbolic intelligence for personal, enterprise, developer, and deployment work |

## Official Search Sources

| Source | URL | Purpose |
| --- | --- | --- |
| USPTO Trademark Search | `https://tmsearch.uspto.gov` | U.S. federal marks |
| USPTO TSDR | `https://tsdr.uspto.gov` | Official application and registration status by serial or registration number |
| USPTO ID Manual | `https://idm-tmng.uspto.gov` | Goods and services wording |
| WIPO Global Brand Database | `https://branddb.wipo.int` | Madrid and participating office marks |
| EUIPO eSearch plus | `https://euipo.europa.eu/eSearch` | EU trade marks, designs, owners, representatives, bulletins |
| TMview | `https://www.tmdn.org/tmview` | Participating national, international, and EU-level marks |
| TMclass | `https://tmclass.tmdn.org` | Classification wording |

## Search Terms

Run each term as exact mark, contains, and similar/phonetic where the tool supports it.

| Group | Terms |
| --- | --- |
| Exact product | `MULLU`, `Mullu`, `mullu` |
| Owner brand | `MULLUSI`, `Mullusi`, `mullusi` |
| Product pair | `Mullu by Mullusi`, `MULLU BY MULLUSI` |
| Surface family | `Mullu Inspect`, `Mullu CLI`, `Mullu Code`, `Mullu Desk`, `Mullu Control Plane` |
| Similar spelling | `Mulu`, `Muluu`, `Moolu`, `Mullus`, `Mullusi` |
| Risky generic pair | `Mullu AI`, `Mulu AI`, `Mullu Agent`, `Mullu Copilot` |

## Nice Class Targets

| Class | Search reason |
| --- | --- |
| 9 | Downloadable software, browser extension, CLI, local runtime, developer tools |
| 35 | Business workflow, operational support, enterprise process services |
| 38 | Communications, notifications, messaging and collaboration surfaces |
| 41 | Training, education, research publications, certification, tutorials |
| 42 | SaaS, cloud execution, developer platform, software design, governance tooling |
| 45 | Compliance, audit, policy support, regulatory workflow assistance |

## Evidence Record

For every search, record:

1. Date and timezone.
2. Search source.
3. Exact query.
4. Filters/classes used.
5. Number of results.
6. Result names.
7. Owner names.
8. Classes.
9. Goods/services text.
10. Status: live, pending, abandoned, expired, cancelled, registered.
11. Conflict rating: none, low, medium, high, blocking.
12. Screenshot or exported result link.

## TSDR Serial Review

The preliminary public web scan surfaced close-variant `MULU` records. Verify
these directly in USPTO TSDR before any launch decision:

| Serial | Mark | Preliminary surface | Required official check |
| --- | --- | --- | --- |
| `99518598` | `MULU` | Close-variant software, business consulting, and technical services record reported by public mirrors | Confirm TSDR status, classes, owner, goods/services, prosecution history, and current location |
| `99264214` | `MULU` | Close-variant business consulting and technical services record reported by public mirrors | Confirm TSDR status, classes, owner, goods/services, prosecution history, and current location |
| `85772539` | `MULU` | Older live/registered record reported by public mirrors | Confirm live/dead status, registration scope, owner, and whether the goods/services create confusion risk |
| `85494313` | `MULU` | Older cancelled record reported by public mirrors | Confirm cancellation status and goods/services history |
| `85222451` | `MULU` | Older cancelled record reported by public mirrors | Confirm cancellation status and goods/services history |

USPTO FAQ documents the API-style status URL pattern:

```text
https://tsdrapi.uspto.gov/ts/cd/casestatus/sn<SERIAL_NUMBER>/content.html
```

Use TSDR or the API-style status page for evidence collection, then attach the
exported status page or screenshot to the clearance packet. Third-party mirrors
may guide the search, but they do not close the official search gate.

## Conflict Rating

| Rating | Meaning | Action |
| --- | --- | --- |
| None | No relevant results | Proceed to next source |
| Low | Unrelated class or historical/dead mark | Record and proceed |
| Medium | Similar term or adjacent class | Legal review required |
| High | Similar software/SaaS/developer/enterprise mark | Do not launch until reviewed |
| Blocking | Same or confusingly similar live mark in target class | Rename or get legal strategy |

## Output Artifact

Create a signed clearance packet with:

1. Completed search table.
2. Screenshot/export bundle.
3. Conflict notes.
4. Domain ownership evidence.
5. Legal review conclusion.
6. Final decision: proceed, proceed with risk, hold, or rename.

## Stop Conditions

Halt public launch if any official source shows:

1. A live `MULLU` mark in Class 9 or 42 for software/SaaS/developer tools.
2. A live confusingly similar mark in enterprise workflow/governance software.
3. A close-variant `MULU` record that legal review rates as likely confusion.
4. A live `MULLU AI` or similar product mark in software classes.
5. Any legal reviewer marks the name high-risk.
