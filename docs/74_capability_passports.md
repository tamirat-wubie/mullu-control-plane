# Capability Passports

Purpose: define the capability passport as the operator-facing identity card for every governed capability.
Governance scope: capability identity, family, C0-C7 evidence maturity, L0-L9 promotion level, allowed and blocked actions, gates, receipts, rollback status, and next unlock evidence.
Dependencies: `capabilities/*/capability_pack.json`, `schemas/capability_passports.schema.json`, `mcoi/mcoi_runtime/app/capability_passports.py`, and `scripts/validate_capability_passports.py`.
Invariants: capability passports are read models, not execution authority; evidence maturity is derived from evidence; promotion level is a boundary classification; every passport blocks terminal success overclaim without receipts.

## Architecture

Capability passports sit between the capability pack registry and operator read models.

| Layer | Role |
| --- | --- |
| Capability pack | Source of capability identity, family, policy, evidence, effects, isolation, cost, recovery, and certification state. |
| Maturity assessor | Derives the current C0-C7 evidence maturity from explicit evidence. |
| Promotion ladder | Classifies the capability into L0-L9 product authority boundaries. |
| Capability passport | Projects one dashboard-ready identity card per capability. |
| Validator | Proves the checked-in passport example matches runtime projection and schema. |

The maturity level says how much evidence exists. The promotion level says what kind of capability boundary the operator is looking at.

## Passport Fields

| Field | Meaning |
| --- | --- |
| `capability_id` | Stable governed capability identity. |
| `family` | Capability family or domain, such as communication, financial, browser, document, or software_dev. |
| `current_unlock_level` | Derived C0-C7 evidence maturity level. |
| `current_promotion_level` | L0-L9 promotion boundary: read-only, draft-only, proposal-only, sandbox-write, test-run, PR-preview, PR-create, merge-request, live connector read, or live connector write. |
| `promotion_required_gates` | Gates required by the promotion boundary. |
| `promotion_required_evidence` | Evidence required before claiming promotion closure. |
| `operator_status` | Simple read-model status: Ready, Prepare-only, Needs approval, Blocked, Evidence missing, or Live action disabled. |
| `allowed_actions` | Bounded actions this capability can prepare or perform under governance. |
| `blocked_actions` | Forbidden actions and overclaim guards. |
| `required_gates` | Canonical gates currently required before execution or promotion. |
| `required_receipts` | Evidence and receipt names required for closure. |
| `rollback_status` | Whether rollback, compensation, review-only handling, or no rollback is available. |
| `next_unlock_step` | The next evidence action required to advance the capability. |

## Algorithm

1. Load every `capabilities/*/capability_pack.json`.
2. Parse each capability through `CapabilityRegistryEntry`.
3. Derive governed read posture through `GovernedCapabilityRecord`.
4. Derive C0-C7 maturity through `CapabilityRegistryMaturityProjector`.
5. Derive the L0-L9 promotion level from capability effects, connector boundary, repository boundary, and approval policy.
6. Project gates, receipts, blocked actions, rollback status, promotion obligations, and operator status.
7. Validate the generated passport set against `schemas/capability_passports.schema.json`.
8. Reject drift if `examples/capability_passports.foundation.json` does not match runtime projection.

## Promotion Ladder

| Level | Boundary |
| --- | --- |
| L0 | read-only |
| L1 | draft-only |
| L2 | proposal-only |
| L3 | sandbox-write |
| L4 | test-run |
| L5 | PR-preview |
| L6 | PR-create with approval |
| L7 | merge-request with approval |
| L8 | live connector read |
| L9 | live connector write |

## Verification

Run:

```powershell
python scripts/validate_capability_passports.py
python -m pytest tests/test_validate_capability_passports.py -q
```

For broader schema integrity:

```powershell
python scripts/validate_schemas.py
```

## Next Additions

Capability passports are the first reusable surface. The next surfaces should build on them in order:

1. Gate Template Registry.
2. Capability Passport Dashboard / Read Model.
3. Evidence Passport.
4. Sandbox-to-Live Promotion Path.
5. Capability Debt Report.
