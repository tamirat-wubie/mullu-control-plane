# Gate Template Registry

Purpose: define reusable gate templates once so every capability family can reference the same approval, evidence, rollback, connector, workspace, external-send, receipt, admission, and promotion gates.
Governance scope: canonical gate IDs, required inputs, required receipts, block conditions, failure modes, operator statuses, and validator refs.
Dependencies: `mcoi/mcoi_runtime/app/gate_template_registry.py`, `schemas/gate_template_registry.schema.json`, `examples/gate_template_registry.foundation.json`, and `scripts/validate_gate_template_registry.py`.
Invariants: gate templates are read-only policy metadata, not execution authority; every capability passport `required_gates` entry must resolve to one template; no unused templates are admitted.

## Architecture

The registry is the shared gate vocabulary for capability passports and later evidence surfaces.

| Layer | Role |
| --- | --- |
| Gate template registry | Canonical gate definitions and IDs. |
| Capability passport | References gate IDs required by a capability. |
| Validator | Proves every passport gate resolves and no template is unused. |
| Future dashboard | Groups capability state by gate category and operator status. |

## Canonical Gates

| Gate | Category | Missing-state outcome |
| --- | --- | --- |
| `gate.uao.admission` | admission | Blocked |
| `gate.capability.registry` | admission | Blocked |
| `gate.evidence.intake` | evidence | Evidence missing |
| `gate.evidence.verification` | evidence | Evidence missing |
| `gate.receipt.append` | receipt | Blocked |
| `gate.approval.required` | approval | Needs approval |
| `gate.sandbox.required` | isolation | Live action disabled |
| `gate.connector.lease` | isolation | Evidence missing |
| `gate.rollback.required` | recovery | Prepare-only |
| `gate.external.send` | external_effect | Needs approval |
| `gate.workspace.write` | local_effect | Prepare-only |
| `gate.production.evidence` | promotion | Live action disabled |

## Algorithm

1. Build deterministic gate templates from `GATE_TEMPLATES`.
2. Validate schema shape and required validator refs.
3. Load capability passports and collect all `required_gates`.
4. Reject any passport gate without a template.
5. Reject any template not referenced by capability passports.
6. Reject authority overclaims such as registry execution authority or missing block conditions.

## Verification

Run:

```powershell
python scripts/validate_gate_template_registry.py
python -m pytest tests/test_validate_gate_template_registry.py -q
```

For passport cross-check:

```powershell
python scripts/validate_capability_passports.py
```

## Next Additions

With passports and gate templates in place, the next reusable surface is the Capability Passport Dashboard / Read Model.
