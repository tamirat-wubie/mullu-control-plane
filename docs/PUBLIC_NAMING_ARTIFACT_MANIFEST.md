# Public Naming Artifact Manifest

Purpose: inventory the complete public naming package for review, release, and future drift checks.
Governance scope: product identity, public copy, clearance evidence, website/domain evidence, schemas, validators, reports, planners, and tests.
Dependencies: `docs/public-naming-readiness.json`, `scripts/validate_public_naming_readiness.py`, `scripts/report_clearance_capture_readiness.py`, `tests/test_public_naming_readiness.py`.
Invariants: every listed artifact must exist; paid public launch remains blocked until open clearance gates close.

## Documents

| Artifact | Role |
| --- | --- |
| `docs/PRODUCT_IDENTITY.md` | Canonical company/product/surface naming |
| `docs/PUBLIC_LAUNCH_COPY.md` | Draft public copy and blocked-name boundary |
| `docs/PUBLIC_NAMING_READINESS.md` | Readiness gate definition |
| `docs/NAMING_MIGRATION_PLAN.md` | Naming migration rules |
| `docs/NAME_CLEARANCE_PRELIMINARY.md` | Preliminary non-legal clearance sweep |
| `docs/APP_TITLE_UPDATE_EVIDENCE_2026-05-15.md` | User-facing app title update evidence |
| `docs/CLEARANCE_EVIDENCE_CAPTURE_PLAN_2026-05-15.md` | Remaining external-gate evidence capture plan |
| `docs/clearance-evidence/mullu/2026-05-15/README.md` | Root pending evidence scaffold instructions |
| `docs/clearance-evidence/mullu/2026-05-15/CAPTURE_INDEX.md` | Human-readable intake filename and mutation checklist |
| `docs/clearance-evidence/mullu/2026-05-15/capture-requirements.json` | Machine-readable intake requirements for remaining open gates |
| `docs/clearance-evidence/mullu/2026-05-15/01-uspto/README.md` | USPTO evidence capture instructions |
| `docs/clearance-evidence/mullu/2026-05-15/01-uspto/decision.md` | USPTO pending decision record |
| `docs/clearance-evidence/mullu/2026-05-15/02-wipo/README.md` | WIPO evidence capture instructions |
| `docs/clearance-evidence/mullu/2026-05-15/02-wipo/decision.md` | WIPO pending decision record |
| `docs/clearance-evidence/mullu/2026-05-15/03-euipo-tmview/README.md` | EUIPO/TMview evidence capture instructions |
| `docs/clearance-evidence/mullu/2026-05-15/03-euipo-tmview/decision.md` | EUIPO/TMview pending decision record |
| `docs/clearance-evidence/mullu/2026-05-15/04-close-variant-mulu/README.md` | Close-variant evidence capture instructions |
| `docs/clearance-evidence/mullu/2026-05-15/04-close-variant-mulu/decision.md` | Close-variant pending decision record |
| `docs/clearance-evidence/mullu/2026-05-15/05-domain-ownership/README.md` | Domain ownership evidence capture instructions |
| `docs/clearance-evidence/mullu/2026-05-15/05-domain-ownership/decision.md` | Domain ownership pending decision record |
| `docs/clearance-evidence/mullu/2026-05-15/06-legal-review/README.md` | Legal review evidence capture instructions |
| `docs/clearance-evidence/mullu/2026-05-15/06-legal-review/decision.md` | Legal review pending decision record |
| `docs/HOMEPAGE_UPDATE_EVIDENCE_2026-05-15.md` | Private-beta product landing page update evidence |
| `docs/OFFICIAL_CLEARANCE_ACCESS_LOG_2026-05-15.md` | Official trademark/domain access attempt log |
| `docs/SDK_API_STABILITY_REVIEW_2026-05-15.md` | SDK/API technical contract naming stability review |
| `docs/TRADEMARK_SEARCH_RUNBOOK.md` | Official trademark search procedure |
| `docs/TSDR_EVIDENCE_TEMPLATE.md` | USPTO/TSDR close-variant evidence template |
| `docs/DOMAIN_ACQUISITION_PLAN.md` | Domain candidate and routing plan |
| `docs/WEBSITE_UPDATE_CHECKLIST.md` | Public-site update requirements |
| `docs/WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md` | Live route verification template |
| `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-07.md` | Direct route probe evidence showing product routes still blocked |
| `docs/WEBSITE_DEPLOYMENT_EVIDENCE_2026-05-15.md` | Direct route probe evidence showing the private-beta product route is live |
| `docs/WEBSITE_LOCAL_BROWSER_VERIFICATION_2026-05-25.md` | Local browser verification for Mullu Govern static routes; not live launch evidence |
| `docs/WEBSITE_RECHECK_LOG.md` | Non-authoritative public index recheck log |
| `docs/PUBLIC_NAMING_STATE_TRANSITION.md` | Launch-state mutation rules |
| `docs/PUBLIC_NAMING_HANDOFF.md` | Reviewer handoff summary |
| `docs/PUBLIC_NAMING_PR_SUMMARY.md` | PR and release summary |
| `docs/PUBLIC_NAMING_REVIEW_PACKET.md` | Human review packet |
| `docs/PUBLIC_NAMING_ARTIFACT_MANIFEST.md` | Naming package inventory |
| `docs/PUBLIC_NAMING_DECISION_2026-05-20.md` | Current governed decision: Mullu approved internally/private beta, paid public launch blocked |
| `docs/public-naming-decision-2026-05-20.json` | Machine-readable naming decision witness |
| `docs/PUBLIC_NAMING_DECISION_2026-05-25.md` | Current governed decision: Mullu Govern approved internally/private beta, paid public launch blocked |
| `docs/public-naming-decision-2026-05-25.json` | Machine-readable Mullu Govern naming decision witness |
| `docs/CLEARANCE_PACKET_TEMPLATE.md` | Final clearance packet template |
| `docs/DOMAIN_OWNERSHIP_RECORD_TEMPLATE.md` | Domain ownership evidence template |
| `site/mullu/index.html` | Deploy-ready private-beta product route draft |
| `docs/PRODUCT_ROUTE_DEPLOYMENT_HANDOFF.md` | Copy target, post-deploy verification handoff, and current source-route first-reference boundary |

## Machine-Readable Evidence

| Artifact | Role |
| --- | --- |
| `docs/public-naming-readiness.json` | Readiness witness |
| `docs/mullu-name-clearance-draft.json` | Draft name-clearance packet |
| `schemas/public_naming_readiness.schema.json` | Readiness witness schema |
| `schemas/public_naming_decision.schema.json` | Public naming decision schema |
| `schemas/mullu_name_clearance_draft.schema.json` | Clearance packet schema |
| `schemas/mullu_clearance_capture_requirements.schema.json` | Capture requirements schema |
| `schemas/mullu_clearance_capture_readiness_report.schema.json` | Capture-readiness report schema |

## Scripts And Tests

| Artifact | Role |
| --- | --- |
| `scripts/validate_public_naming_readiness.py` | Primary launch-gate validator |
| `scripts/report_clearance_capture_readiness.py` | Read-only required-file intake report for remaining clearance gates |
| `scripts/report_public_naming_readiness.py` | Human-readable readiness report |
| `scripts/plan_public_naming_transition.py` | Remaining-action planner |
| `tests/test_public_naming_readiness.py` | Regression tests for naming gates |

## Verification

```powershell
python .\scripts\validate_public_naming_readiness.py
python .\scripts\report_clearance_capture_readiness.py
python .\scripts\report_public_naming_readiness.py
python .\scripts\plan_public_naming_transition.py
python -m pytest tests\test_public_naming_readiness.py -q
python .\scripts\validate_release_status.py
```
