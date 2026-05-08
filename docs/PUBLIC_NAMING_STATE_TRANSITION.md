# Public Naming State Transition

Purpose: define the allowed transition from internal `Mullu` alignment to public paid launch.
Governance scope: readiness witness mutation, clearance packet closure, domain ownership evidence, legal review, and launch authorization.
Dependencies: `docs/public-naming-readiness.json`, `docs/mullu-name-clearance-draft.json`, `docs/PUBLIC_NAMING_READINESS.md`, `scripts/validate_public_naming_readiness.py`.
Invariants: `public_paid_launch_allowed` must not become `true` until all clearance, ownership, and legal gates close with retained evidence.

## Current State

```text
status: internal_alignment_only
public_paid_launch_allowed: false
final_decision: pending
```

## Allowed Next States

| State | Meaning | Public paid launch |
| --- | --- | --- |
| `internal_alignment_only` | Product naming is internally aligned but not externally cleared | Not allowed |
| `clearance_in_progress` | Official searches or domain acquisition are underway | Not allowed |
| `blocked` | A material conflict or legal blocker exists | Not allowed |
| `cleared_for_public_launch` | Clearance packet, domain evidence, and legal review are closed | Allowed only if decision permits |

## Required Evidence Before Launch

Before `public_paid_launch_allowed` may become `true`, all of the following must be recorded:

1. USPTO search results for exact and similar marks.
2. WIPO Global Brand Database search results.
3. EUIPO/TMview search results.
4. Common-law search notes for software, SaaS, developer tools, browser extensions, app stores, and enterprise workflow products.
5. Domain ownership record for the chosen product route.
6. DNS/security controls for the chosen route.
7. Legal/trademark reviewer decision.
8. Product owner decision.
9. Updated public launch copy.
10. Updated readiness witness.

## Mutation Rules

| File | Required mutation |
| --- | --- |
| `docs/mullu-name-clearance-draft.json` | Set official search statuses to complete, add evidence paths, set final decision |
| `docs/public-naming-readiness.json` | Move closed gates from open to closed, set status, set launch allowance only if permitted |
| `docs/PUBLIC_NAMING_READINESS.md` | Update gate table from Open to Closed with evidence references |
| `docs/CLEARANCE_PACKET_TEMPLATE.md` | Preserve as template; do not overwrite |
| `docs/DOMAIN_OWNERSHIP_RECORD_TEMPLATE.md` | Preserve as template; do not overwrite |

## Forbidden Transitions

1. `internal_alignment_only` -> `cleared_for_public_launch` without official search evidence.
2. `public_paid_launch_allowed: false` -> `true` while any official search remains `open`.
3. `final_decision: pending` -> `proceed` without legal review.
4. Domain route publication without registrar or DNS ownership evidence.
5. Public copy update that claims paid availability before launch allowance is true.

## Verification Required After Mutation

```powershell
python .\scripts\validate_public_naming_readiness.py
python .\scripts\report_public_naming_readiness.py
python -m pytest tests\test_public_naming_readiness.py -q
python .\scripts\validate_release_status.py
```

## Resolution

The current state remains blocked. The only authorized next action is evidence
collection and review closure, not launch-state mutation.
