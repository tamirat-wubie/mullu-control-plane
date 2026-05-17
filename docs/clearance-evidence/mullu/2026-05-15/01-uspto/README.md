# USPTO Evidence

Purpose: store official USPTO Trademark Search evidence for the Mullu public naming gate.
Governance scope: exact and similar mark searches, required Nice classes, reviewer decision, and source retention.
Dependencies: `docs/TRADEMARK_SEARCH_RUNBOOK.md`, `docs/CLEARANCE_EVIDENCE_CAPTURE_PLAN_2026-05-15.md`.
Invariants: no USPTO gate is closed by this placeholder; official screenshots or exports are required.

## Required Queries

| Query | Required classes | Status |
| --- | --- | --- |
| `MULLU` | 9, 35, 38, 41, 42, 45 | Pending capture |
| `MULLUSI` | 9, 35, 38, 41, 42, 45 | Pending capture |
| `Mullu by Mullusi` | 9, 35, 38, 41, 42, 45 | Pending capture |
| `Mullu Inspect` | 9, 35, 38, 41, 42, 45 | Pending capture |
| `Mullu CLI` | 9, 35, 38, 41, 42, 45 | Pending capture |
| `Mullu Code` | 9, 35, 38, 41, 42, 45 | Pending capture |
| `Mullu Control Plane` | 9, 35, 38, 41, 42, 45 | Pending capture |
| `MULU` | 9, 35, 38, 41, 42, 45 | Pending capture |

## Required Files

1. Official USPTO screenshots or exports.
2. Search timestamp and reviewer identity.
3. `decision.md` with conflict rating and launch impact.

STATUS:
  Completeness: 20%
  Invariants verified: [query scope declared, classes declared, gate remains pending]
  Open issues: [official USPTO captures, reviewer decision]
  Next action: capture USPTO records and update `decision.md`
