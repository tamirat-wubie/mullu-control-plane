# Mullu Clearance Evidence Capture Index

Purpose: define the exact intake files required before any remaining Mullu naming clearance gate may close.
Governance scope: evidence naming, reviewer authority, source traceability, and paid launch mutation boundaries.
Dependencies: `docs/CLEARANCE_EVIDENCE_CAPTURE_PLAN_2026-05-15.md`, `docs/public-naming-readiness.json`, and gate-local `decision.md` files.
Invariants: this index does not close any gate; paid public launch remains blocked until official evidence and authority decisions are attached.

## Required Intake Files

| Gate | Directory | Required files before review decision may change |
| --- | --- | --- |
| `uspto_search` | `01-uspto/` | `uspto-search-mullu.pdf`, `uspto-search-mullusi.pdf`, `uspto-search-mullu-by-mullusi.pdf`, `uspto-search-mullu-surfaces.pdf`, `uspto-search-mulu.pdf`, `decision.md` |
| `wipo_search` | `02-wipo/` | `wipo-search-mullu.pdf`, `wipo-search-mullusi.pdf`, `wipo-search-mullu-by-mullusi.pdf`, `decision.md` |
| `euipo_tmview_search` | `03-euipo-tmview/` | `euipo-search-mullu.pdf`, `euipo-search-mullusi.pdf`, `euipo-search-mullu-by-mullusi.pdf`, `tmview-search-mullu.pdf`, `tmview-search-mullusi.pdf`, `tmview-search-mullu-by-mullusi.pdf`, `decision.md` |
| `close_variant_review` | `04-close-variant-mulu/` | `tsdr-99518598.pdf`, `tsdr-99264214.pdf`, `tsdr-85772539.pdf`, `tsdr-85494313.pdf`, `tsdr-85222451.pdf`, `mulu-confusion-analysis.md`, `decision.md` |
| `domain_ownership` | `05-domain-ownership/` | `registrar-ownership.pdf`, `dns-zone-control.pdf`, `https-certificate.pdf`, `renewal-and-lock-controls.pdf`, `decision.md` |
| `legal_review` | `06-legal-review/` | `legal-review-decision.pdf`, `reviewed-evidence-list.md`, `decision.md` |

## Decision Mutation Rule

Before changing any gate from `Pending`, the gate-local `decision.md` must include:

1. Reviewer name and role.
2. Review date.
3. Evidence file list matching this index or an explicit reason for substitution.
4. Result count or status summary.
5. Highest conflict rating.
6. Decision value: `clear`, `risky`, `blocked`, or `inconclusive`.
7. Launch impact statement.

Do not update `docs/public-naming-readiness.json` until the matching decision
is evidence-backed and the required authority in the capture plan has approved
the change.

STATUS:
  Completeness: 100%
  Invariants verified: [intake filenames declared, decision mutation blocked, paid public launch remains blocked]
  Open issues: [official source files, reviewer decisions, legal decision]
  Next action: attach official evidence files in the matching gate directories
