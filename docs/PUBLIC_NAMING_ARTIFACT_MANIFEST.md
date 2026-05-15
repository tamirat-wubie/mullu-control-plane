# Public Naming Artifact Manifest

Purpose: inventory the complete public naming package for review, release, and future drift checks.
Governance scope: product identity, public copy, clearance evidence, website/domain evidence, schemas, validators, reports, planners, and tests.
Dependencies: `docs/public-naming-readiness.json`, `scripts/validate_public_naming_readiness.py`, `tests/test_public_naming_readiness.py`.
Invariants: every listed artifact must exist; paid public launch remains blocked until open clearance gates close.

## Documents

| Artifact | Role |
| --- | --- |
| `docs/PRODUCT_IDENTITY.md` | Canonical company/product/surface naming |
| `docs/PUBLIC_LAUNCH_COPY.md` | Draft public copy and blocked-name boundary |
| `docs/PUBLIC_NAMING_READINESS.md` | Readiness gate definition |
| `docs/NAMING_MIGRATION_PLAN.md` | Naming migration rules |
| `docs/NAME_CLEARANCE_PRELIMINARY.md` | Preliminary non-legal clearance sweep |
| `docs/OFFICIAL_CLEARANCE_ACCESS_LOG_2026-05-15.md` | Official trademark/domain access attempt log |
| `docs/SDK_API_STABILITY_REVIEW_2026-05-15.md` | SDK/API technical contract naming stability review |
| `docs/TRADEMARK_SEARCH_RUNBOOK.md` | Official trademark search procedure |
| `docs/TSDR_EVIDENCE_TEMPLATE.md` | USPTO/TSDR close-variant evidence template |
| `docs/DOMAIN_ACQUISITION_PLAN.md` | Domain candidate and routing plan |
| `docs/WEBSITE_UPDATE_CHECKLIST.md` | Public-site update requirements |
| `docs/WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md` | Live route verification template |
| `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-07.md` | Direct route probe evidence showing product routes still blocked |
| `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md` | Direct route probe evidence showing the private-beta product route is live |
| `docs/WEBSITE_RECHECK_LOG.md` | Non-authoritative public index recheck log |
| `docs/PUBLIC_NAMING_STATE_TRANSITION.md` | Launch-state mutation rules |
| `docs/PUBLIC_NAMING_HANDOFF.md` | Reviewer handoff summary |
| `docs/PUBLIC_NAMING_PR_SUMMARY.md` | PR and release summary |
| `docs/PUBLIC_NAMING_REVIEW_PACKET.md` | Human review packet |
| `docs/PUBLIC_NAMING_ARTIFACT_MANIFEST.md` | Naming package inventory |
| `docs/CLEARANCE_PACKET_TEMPLATE.md` | Final clearance packet template |
| `docs/DOMAIN_OWNERSHIP_RECORD_TEMPLATE.md` | Domain ownership evidence template |
| `site/mullu/index.html` | Deploy-ready private-beta product route draft |
| `docs/PRODUCT_ROUTE_DEPLOYMENT_HANDOFF.md` | Copy target and post-deploy verification handoff |

## Machine-Readable Evidence

| Artifact | Role |
| --- | --- |
| `docs/public-naming-readiness.json` | Readiness witness |
| `docs/mullu-name-clearance-draft.json` | Draft name-clearance packet |
| `schemas/public_naming_readiness.schema.json` | Readiness witness schema |
| `schemas/mullu_name_clearance_draft.schema.json` | Clearance packet schema |

## Scripts And Tests

| Artifact | Role |
| --- | --- |
| `scripts/validate_public_naming_readiness.py` | Primary launch-gate validator |
| `scripts/report_public_naming_readiness.py` | Human-readable readiness report |
| `scripts/plan_public_naming_transition.py` | Remaining-action planner |
| `tests/test_public_naming_readiness.py` | Regression tests for naming gates |

## Verification

```powershell
python .\scripts\validate_public_naming_readiness.py
python .\scripts\report_public_naming_readiness.py
python .\scripts\plan_public_naming_transition.py
python -m pytest tests\test_public_naming_readiness.py -q
python .\scripts\validate_release_status.py
```
