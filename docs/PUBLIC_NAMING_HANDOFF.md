# Public Naming Handoff

Purpose: summarize the Mullu Govern public naming decision, current launch status, and verification commands for reviewers.
Governance scope: product identity, evidence artifacts, machine-readable witnesses, CI gates, tests, and open real-world clearance work.
Dependencies: `docs/PRODUCT_IDENTITY.md`, `docs/PUBLIC_NAMING_READINESS.md`, `docs/public-naming-readiness.json`, `scripts/validate_public_naming_readiness.py`.
Invariants: Mullu Govern is the public product; Mullu is the suite/family; Mullusi is the company and governance authority; paid public launch remains blocked until official clearance closes.

## Decision

| Boundary | Decision |
| --- | --- |
| Company / ecosystem | Mullusi |
| Suite / family | Mullu |
| Public product | Mullu Govern |
| First public reference | Mullu Govern, by Mullusi |
| Developer / architecture term | Mullu Platform |
| Internal/admin governance/deployment surface | Mullu Control Plane |
| Public repository target | mullu-govern |
| Public paid launch state | Blocked |

## Why This Name

Mullu Govern names the repo's real value: governed execution through approvals,
budgets, traces, audit, lineage, deployment controls, policy enforcement, skill
boundaries, and proof-backed actions. It keeps the public product distinct from
the company brand and the internal/admin control surface. The Mullu family
supports shipped and future surfaces:

1. Mullu Govern
2. Mullu Proof
3. Mullu Ledger
4. Mullu Inspect
5. Mullu CLI
6. Mullu Code
7. Mullu Desk
8. Mullu Control Plane

## Current State

```text
status: internal_alignment_only
public_paid_launch_allowed: false
final_decision: pending
```

The name is approved for internal alignment and product planning only.

## Closed Artifacts

| Artifact | Status |
| --- | --- |
| Product identity docs | Closed |
| Public launch copy draft | Closed |
| Preliminary search memo | Closed with review items |
| Trademark search runbook | Closed |
| TSDR evidence template | Closed |
| Domain acquisition plan | Closed |
| Website update checklist | Closed |
| Website deployment evidence template | Closed |
| PR summary | Closed |
| Review packet | Closed |
| Clearance packet template | Closed |
| Domain ownership template | Closed |
| Draft clearance packet | Closed |
| JSON readiness witness | Closed |
| JSON schemas | Closed |
| Validator script | Closed |
| Report script | Closed |
| Transition planner | Closed |
| Focused tests | Closed |
| CI/release gate wiring | Closed |

## Open Gates

| Gate | Required action |
| --- | --- |
| USPTO search | Run official exact/similar searches and attach evidence |
| WIPO search | Run official global brand search and attach evidence |
| EUIPO/TMview search | Run official EU and participating-office searches and attach evidence |
| Domain ownership | Acquire or verify product domain/subdomain and DNS ownership |
| Legal review | Record qualified trademark/legal decision |
| Homepage update | Apply approved copy only after clearance or mark private beta/waitlist |
| App title update | Use `Mullu Govern` after authorization where the surface is product-facing |
| SDK/API stability review | Preserve `Mullu Platform` where technical contracts require it |

## Verification Commands

```powershell
python .\scripts\validate_public_naming_readiness.py
python .\scripts\report_public_naming_readiness.py
python .\scripts\plan_public_naming_transition.py
python -m pytest tests\test_public_naming_readiness.py -q
python .\scripts\validate_schemas.py
python .\scripts\validate_release_status.py
```

## Current Verification Result

```text
validate_public_naming_readiness.py: passed
proof_coverage_matrix.py --check: passed
test_proof_coverage_matrix.py: 113 passed
focused naming/release test lane: 270 passed
validate_release_status.py: passed
run_workspace_governance_checks.py: passed
git diff --check: passed with Windows line-ending warnings only
```

## Review Boundary

The OrgOS gateway and kernel files are a separate worktree boundary. This
handoff only depends on the proof-matrix compatibility update that classifies
the declared OrgOS routes under `orgos_case_governance_lifecycle`; it does not
make an independent product-name decision for OrgOS.

## Reviewer Rule

Do not approve a paid public launch PR if:

1. `public_paid_launch_allowed` is true while official searches remain open.
2. `final_decision` is `pending`.
3. No domain ownership record exists.
4. Legal review is missing.
5. Public copy uses blocked product names.

## Resolution

The naming system is structurally complete and governed around `Mullu Govern`.
The remaining work is external clearance evidence, not architecture or product
naming.
