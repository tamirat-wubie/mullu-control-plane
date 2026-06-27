# Capability Passports

Purpose: define the capability passport as the operator-facing identity card for every governed capability.
Governance scope: capability identity, family, C0-C7 unlock level, allowed and blocked actions, gates, receipts, rollback status, and next unlock evidence.
Dependencies: `capabilities/*/capability_pack.json`, `schemas/capability_passports.schema.json`, `mcoi/mcoi_runtime/app/capability_passports.py`, and `scripts/validate_capability_passports.py`.
Invariants: capability passports are read models, not execution authority; unlock level is derived from evidence; every passport blocks terminal success overclaim without receipts.

## Architecture

Capability passports sit between the capability pack registry and operator read models.

| Layer | Role |
| --- | --- |
| Capability pack | Source of capability identity, family, policy, evidence, effects, isolation, cost, recovery, and certification state. |
| Maturity assessor | Derives the current C0-C7 unlock level from explicit evidence. |
| Capability passport | Projects one dashboard-ready identity card per capability. |
| Validator | Proves the checked-in passport example matches runtime projection and schema. |

The unlock ladder says what maturity levels exist. The capability passport says where each capability currently stands.

## Passport Fields

| Field | Meaning |
| --- | --- |
| `capability_id` | Stable governed capability identity. |
| `family` | Capability family or domain, such as communication, financial, browser, document, or software_dev. |
| `current_unlock_level` | Derived C0-C7 maturity level. |
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
5. Project gates, receipts, blocked actions, rollback status, and operator status.
6. Validate the generated passport set against `schemas/capability_passports.schema.json`.
7. Reject drift if `examples/capability_passports.foundation.json` does not match runtime projection.

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
