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

## Intake Validation Rule

Capture readiness is validated with:

```powershell
python .\scripts\report_clearance_capture_readiness.py --strict
```

The validator treats a file as ready only when:

1. Required `.pdf` evidence starts with a PDF header and contains a PDF EOF marker.
2. Required `.md` evidence is UTF-8, substantive, and free of placeholder/pending markers.
3. Gate-local `decision.md` includes every field listed for that gate in `capture-requirements.json`.

File presence alone is not sufficient. Placeholder decisions remain invalid
until the required authority records the reviewer, review date, evidence files,
decision, and launch impact.

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

1. `Mullu Govern`
2. `MULLU`
3. `MULLUSI`
4. `Mullu Govern by Mullusi`
5. `Mullu by Mullusi`
6. `Mullu Inspect`
7. `Mullu CLI`
8. `Mullu Code`
9. `Mullu Control Plane`
10. `MULU`

Required USPTO evidence files:

```text
uspto-search-mullu-govern.pdf
uspto-search-mullu.pdf
uspto-search-mullusi.pdf
uspto-search-mullu-govern-by-mullusi.pdf
uspto-search-mullu-by-mullusi.pdf
uspto-search-mullu-surfaces.pdf
uspto-search-mulu.pdf
```

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

1. `Mullu Govern`
2. `MULLU`
3. `MULLUSI`
4. `Mullu Govern by Mullusi`
5. `Mullu by Mullusi`

Required WIPO evidence files:

```text
wipo-search-mullu-govern.pdf
wipo-search-mullu.pdf
wipo-search-mullusi.pdf
wipo-search-mullu-govern-by-mullusi.pdf
wipo-search-mullu-by-mullusi.pdf
```

Record whether results appear in Madrid, Lisbon, 6ter, or participating office collections.

## EUIPO/TMview Capture Checklist

Capture EUIPO eSearch plus and TMview results for:

1. `Mullu Govern`
2. `MULLU`
3. `MULLUSI`
4. `Mullu Govern by Mullusi`
5. `Mullu by Mullusi`

Required EUIPO and TMview evidence files:

```text
euipo-search-mullu-govern.pdf
euipo-search-mullu.pdf
euipo-search-mullusi.pdf
euipo-search-mullu-govern-by-mullusi.pdf
euipo-search-mullu-by-mullusi.pdf
tmview-search-mullu-govern.pdf
tmview-search-mullu.pdf
tmview-search-mullusi.pdf
tmview-search-mullu-govern-by-mullusi.pdf
tmview-search-mullu-by-mullusi.pdf
```

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
  Invariants verified: [evidence paths defined, evidence directory scaffolds created, intake file validation defined, remaining gates stay open, authority requirements explicit, paid public launch remains blocked]
  Open issues: [official trademark records, domain ownership packet, legal decision]
  Next action: populate the evidence directories with official source captures and qualified reviewer decisions
