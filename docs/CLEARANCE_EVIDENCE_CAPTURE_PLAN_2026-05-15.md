# Clearance Evidence Capture Plan 2026-05-15

Purpose: define the concrete artifact layout and capture checklist for the remaining Mullu public naming clearance gates.
Governance scope: official trademark searches, close-variant serial review, domain ownership evidence, legal review evidence, and launch-state mutation boundaries.
Dependencies: `docs/mullu-name-clearance-draft.json`, `docs/OFFICIAL_CLEARANCE_ACCESS_LOG_2026-05-15.md`, `docs/CLEARANCE_PACKET_TEMPLATE.md`, `docs/DOMAIN_OWNERSHIP_RECORD_TEMPLATE.md`.
Invariants: this plan does not close any remaining gate; it defines required evidence paths and authority checks before a gate may close.

## Evidence Root

Store captured records under:

```text
docs/clearance-evidence/mullu/2026-05-15/
```

Required subdirectories:

```text
01-uspto/
02-wipo/
03-euipo-tmview/
04-close-variant-mulu/
05-domain-ownership/
06-legal-review/
```

Required root files:

```text
README.md
CAPTURE_INDEX.md
capture-requirements.json
```

`CAPTURE_INDEX.md` must list every evidence directory, its pending/closed state,
the required source authority, and the rule that paid public launch remains
blocked until the matching official source captures and reviewer decisions are
present.

`capture-requirements.json` is the machine-readable counterpart validated by
`schemas/mullu_clearance_capture_requirements.schema.json`.

Each subdirectory must include:

1. `README.md` describing source, date, reviewer, query terms, and decision.
2. Raw screenshot/export files from the official source.
3. A short `decision.md` summarizing whether the evidence is clear, risky, blocked, or inconclusive.

## Gate Capture Matrix

| Gate | Evidence path | Required source | Authority |
| --- | --- | --- | --- |
| `uspto_search` | `01-uspto/` | USPTO Trademark Search and TSDR | product owner plus qualified trademark reviewer |
| `wipo_search` | `02-wipo/` | WIPO Global Brand Database | product owner plus qualified trademark reviewer |
| `euipo_tmview_search` | `03-euipo-tmview/` | EUIPO eSearch plus and TMview | product owner plus qualified trademark reviewer |
| `close_variant_review` | `04-close-variant-mulu/` | USPTO TSDR serial evidence and legal confusion analysis | qualified trademark reviewer |
| `domain_ownership` | `05-domain-ownership/` | registrar, DNS zone, HTTPS, renewal, MFA, lock evidence | domain/DNS owner plus launch owner |
| `legal_review` | `06-legal-review/` | signed trademark/legal decision | qualified legal/trademark reviewer |

## USPTO Capture Checklist

Capture official USPTO evidence for:

1. `MULLU`
2. `MULLUSI`
3. `Mullu by Mullusi`
4. `Mullu Inspect`
5. `Mullu CLI`
6. `Mullu Code`
7. `Mullu Control Plane`
8. `MULU`

Required classes:

```text
9, 35, 38, 41, 42, 45
```

Required serial status records:

```text
99518598
99264214
85772539
85494313
85222451
```

## WIPO Capture Checklist

Capture WIPO Global Brand Database results for:

1. `MULLU`
2. `MULLUSI`
3. `Mullu by Mullusi`

Record whether results appear in Madrid, Lisbon, 6ter, or participating office collections.

## EUIPO/TMview Capture Checklist

Capture EUIPO eSearch plus and TMview results for:

1. `MULLU`
2. `MULLUSI`
3. `Mullu by Mullusi`

Record owner, jurisdiction, classes, status, and goods/services for any similar result.

## Domain Ownership Checklist

For the selected launch route or domain, capture:

1. Registrar account ownership.
2. Registered owner or organization account.
3. Renewal owner and renewal date.
4. Auto-renew status.
5. Registrar lock status.
6. MFA status.
7. DNS provider and zone control.
8. HTTPS certificate status.
9. DNSSEC/HSTS status if enabled.
10. TXT ownership verification if available.

## Legal Review Checklist

The legal review packet must include:

1. Reviewer name and role.
2. Review date.
3. Reviewed evidence paths.
4. Decision: `proceed`, `proceed_with_risk_controls`, `hold`, or `rename`.
5. Risk controls if `proceed_with_risk_controls` is selected.
6. Explicit statement that paid public launch is allowed or remains blocked.

## Mutation Rule

Do not update `docs/public-naming-readiness.json` to close any of the remaining six gates until the matching evidence path exists and contains the required source records and authority decision.

STATUS:
  Completeness: 100%
  Invariants verified: [evidence paths defined, evidence directory scaffolds created, remaining gates stay open, authority requirements explicit, paid public launch remains blocked]
  Open issues: [official trademark records, domain ownership packet, legal decision]
  Next action: populate the evidence directories with official source captures and qualified reviewer decisions
