# Mullu Govern Clearance Evidence 2026-05-15

Purpose: provide the controlled evidence root for Mullu Govern public product clearance artifacts while preserving Mullu as the suite/family name.
Governance scope: official trademark searches, close-variant serial review, domain ownership evidence, legal review, and launch-state mutation boundaries.
Dependencies: `docs/CLEARANCE_EVIDENCE_CAPTURE_PLAN_2026-05-15.md`, `docs/CLEARANCE_PACKET_TEMPLATE.md`, `docs/OFFICIAL_CLEARANCE_ACCESS_LOG_2026-05-15.md`.
Invariants: this directory structure does not close a clearance gate; paid public launch remains blocked until official evidence and authority decisions are recorded.

## Evidence Directories

| Directory | Gate | Required evidence |
| --- | --- | --- |
| `01-uspto/` | `uspto_search` | Official USPTO search screenshots or exports for required terms and classes |
| `02-wipo/` | `wipo_search` | WIPO Global Brand Database screenshots or exports |
| `03-euipo-tmview/` | `euipo_tmview_search` | EUIPO eSearch plus and TMview screenshots or exports |
| `04-close-variant-mulu/` | `close_variant_review` | USPTO TSDR serial status records and confusion analysis |
| `05-domain-ownership/` | `domain_ownership` | Registrar, DNS zone, HTTPS, renewal, MFA, lock, and ownership records |
| `06-legal-review/` | `legal_review` | Signed legal or trademark decision |

## Mutation Rule

Do not update `docs/public-naming-readiness.json` to close any remaining gate until:

1. The matching evidence directory contains official source records.
2. `decision.md` names the reviewer, date, decision, and evidence files.
3. The authority listed in the capture plan has approved the decision.
4. The final legal review explicitly allows paid public launch or records the remaining block.

The intake checklist is governed by:

```text
docs/clearance-evidence/mullu/2026-05-15/CAPTURE_INDEX.md
docs/clearance-evidence/mullu/2026-05-15/capture-requirements.json
```

Readiness is checked with:

```powershell
python .\scripts\report_clearance_capture_readiness.py --strict
```

The check requires valid capture files, not only filenames. Required `.pdf`
artifacts must have PDF file shape, required `.md` artifacts must be substantive
UTF-8, and each `decision.md` must contain the gate-specific decision fields
without placeholder or pending markers.

STATUS:
  Completeness: 100%
  Invariants verified: [evidence root exists, gate directories declared, capture requirements declared, capture file validation declared, paid public launch remains blocked]
  Open issues: [official source captures, reviewer decisions, legal decision]
  Next action: populate each gate directory with official source records and signed decisions
