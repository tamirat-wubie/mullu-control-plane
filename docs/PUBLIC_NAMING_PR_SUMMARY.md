# Public Naming PR Summary

Purpose: summarize the public naming changes for code review and release notes.
Governance scope: product identity, launch gating, verification commands, and remaining real-world clearance evidence.
Dependencies: `docs/PRODUCT_IDENTITY.md`, `docs/PUBLIC_NAMING_READINESS.md`, `docs/PUBLIC_NAMING_HANDOFF.md`, `docs/PUBLIC_NAMING_DECISION_2026-05-25.md`, `docs/public-naming-readiness.json`.
Invariants: `Mullu Govern` is the public product; `Mullu` is the suite/family; `Mullusi` is the company and governance authority; paid public launch remains blocked until clearance closes.

## Summary

This change aligns the repository around `Mullu Govern` as the public product
name, `Mullu` as the suite/family, and `Mullusi` as the company, ecosystem, and
governance authority.

It also adds a machine-readable naming readiness gate so the product name can be
used for internal alignment without accidentally authorizing paid public launch
before trademark, domain, and legal clearance are complete.

## Naming Decisions

| Boundary | Standard name |
| --- | --- |
| Company / ecosystem | Mullusi |
| Suite / family | Mullu |
| Public product | Mullu Govern |
| First public reference | Mullu Govern, by Mullusi |
| Developer / SDK / API term | Mullu Platform |
| Internal/admin governance/deployment surface | Mullu Control Plane |
| Public repository target | mullu-govern |

## Main Artifacts

| Artifact | Role |
| --- | --- |
| `docs/PRODUCT_IDENTITY.md` | Canonical company/product/surface boundary |
| `docs/PUBLIC_NAMING_READINESS.md` | Launch readiness gate |
| `docs/PUBLIC_NAMING_HANDOFF.md` | Reviewer handoff |
| `docs/PUBLIC_NAMING_REVIEW_PACKET.md` | Reviewer clearance packet |
| `docs/PUBLIC_LAUNCH_COPY.md` | Draft product copy |
| `docs/TRADEMARK_SEARCH_RUNBOOK.md` | Official search procedure |
| `docs/TSDR_EVIDENCE_TEMPLATE.md` | USPTO close-variant serial evidence template |
| `docs/DOMAIN_ACQUISITION_PLAN.md` | Domain and routing plan |
| `docs/WEBSITE_DEPLOYMENT_EVIDENCE_TEMPLATE.md` | Live-route deployment evidence template |
| `docs/mullu-name-clearance-draft.json` | Draft clearance packet |
| `docs/public-naming-readiness.json` | Machine-readable readiness witness |
| `docs/PUBLIC_NAMING_DECISION_2026-05-25.md` | Governed product rename decision |
| `docs/public-naming-decision-2026-05-25.json` | Machine-readable product rename decision witness |
| `docs/WEBSITE_LOCAL_BROWSER_VERIFICATION_2026-05-25.md` | Local static-route verification witness |
| `scripts/validate_public_naming_readiness.py` | Gate validator |
| `scripts/report_public_naming_readiness.py` | Human-readable readiness report |
| `scripts/plan_public_naming_transition.py` | Remaining transition planner |
| `tests/test_public_naming_readiness.py` | Focused regression tests |

## Compatibility Boundary

The worktree also contains OrgOS gateway routes and kernel tests. The public
naming change does not define those OrgOS contracts, but it updates the proof
coverage matrix so the new declared routes are classified instead of being left
as unproven gateway drift.

| Artifact | Role |
| --- | --- |
| `scripts/proof_coverage_matrix.py` | Adds `orgos_case_governance_lifecycle` route classification |
| `docs/40_proof_coverage_matrix.md` | Regenerated operator proof witness |
| `tests/fixtures/proof_coverage_matrix.json` | Regenerated machine proof witness |
| `tests/test_proof_coverage_matrix.py` | Regression assertions for the OrgOS route classification |

## Public Launch Status

```text
status: internal_alignment_only
public_paid_launch_allowed: false
final_decision: pending
```

The repository may use `Mullu Govern` for internal alignment, planning, and
technical preparation. Paid public launch remains blocked.

## Remaining Open Gates

| Gate | Required evidence |
| --- | --- |
| USPTO search | Official exact/similar search result |
| WIPO search | Official global brand search result |
| EUIPO/TMview search | Official EU and participating-office search result |
| Domain ownership | Registrar/DNS ownership record |
| Close-variant review | Official review of `MULU` software/service-adjacent records |
| Legal review | Qualified trademark/legal decision |
| Homepage update | Approved public copy applied after clearance or kept foundation-stage with no access invitation |
| Website deployment verification | `mullusi.com` and product routes verified live and not site-not-found |
| App title update | User-facing app title uses `Mullu Govern` only after authorization where the surface is product-facing |
| SDK/API stability review | Technical `Mullu Platform` contracts preserved intentionally |

## Verification

```powershell
python .\scripts\validate_public_naming_readiness.py
python .\scripts\report_public_naming_readiness.py
python .\scripts\plan_public_naming_transition.py
python -m pytest tests\test_public_naming_readiness.py -q
python .\scripts\validate_schemas.py
python .\scripts\validate_release_status.py
```

Current verification result:

```text
validate_public_naming_readiness.py: passed
proof_coverage_matrix.py --check: passed
test_proof_coverage_matrix.py: 113 passed
focused naming/release test lane: 270 passed
validate_release_status.py: passed
run_workspace_governance_checks.py: passed
git diff --check: passed with Windows line-ending warnings only
```

## Review Rule

Approve this as an internal naming alignment and readiness-gate change only.
Do not treat it as authorization for paid public launch until the open gates in
`docs/PUBLIC_NAMING_READINESS.md` are closed and the JSON witnesses are updated.
