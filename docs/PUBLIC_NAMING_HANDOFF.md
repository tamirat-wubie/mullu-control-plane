# Public Naming Handoff

Purpose: summarize the Mullu public naming decision, current launch status, and verification commands for reviewers.
Governance scope: product identity, evidence artifacts, machine-readable witnesses, CI gates, tests, and open real-world clearance work.
Dependencies: `docs/PRODUCT_IDENTITY.md`, `docs/PUBLIC_NAMING_READINESS.md`, `docs/public-naming-readiness.json`, `scripts/validate_public_naming_readiness.py`.
Invariants: Mullu is the flagship product; Mullusi is the company and governance authority; paid public launch remains blocked until official clearance closes.

## Decision

| Boundary | Decision |
| --- | --- |
| Company / ecosystem | Mullusi |
| Flagship product | Mullu |
| First public reference | Mullu, by Mullusi |
| Developer / architecture term | Mullu Platform |
| Admin / governance / deployment surface | Mullu Control Plane |
| Public paid launch state | Blocked |

## Why This Name

Mullu preserves the existing product-family pattern and keeps the public product
distinct from the company brand. It supports shipped and future surfaces:

1. Mullu
2. Mullu Inspect
3. Mullu CLI
4. Mullu Code
5. Mullu Desk
6. Mullu Control Plane

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
| App title update | Use `Mullu` after authorization |
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
test_public_naming_readiness.py: passed
validate_schemas.py: passed
validate_release_status.py: passed
```

## Reviewer Rule

Do not approve a paid public launch PR if:

1. `public_paid_launch_allowed` is true while official searches remain open.
2. `final_decision` is `pending`.
3. No domain ownership record exists.
4. Legal review is missing.
5. Public copy uses blocked product names.

## Resolution

The naming system is structurally complete and governed. The remaining work is
external clearance evidence, not architecture or product naming.
