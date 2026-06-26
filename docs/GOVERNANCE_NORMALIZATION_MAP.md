<!--
Purpose: map repository governance doctrine to canonical local source, validator, and test artifacts without creating a readiness claim.
Governance scope: AGENTS policy, Foundation Mode, Phi platform law, UAO, Mfidel atomicity, SDLC, workspace preflight, documentation drift control.
Dependencies: AGENTS.md, docs/FOUNDATION_MODE.md, docs/PHI_CANONICAL_SPEC.md, docs/UNIVERSAL_ACTION_ORCHESTRATION.md, docs/85_mfidel_substrate_conformance_receipt_contract.md, docs/SDLC.md, scripts/validate_governance_normalization_map.py.
Invariants: this map is a navigation and drift-control artifact only; it does not replace canonical doctrine, grant runtime authority, prove documentation completeness, promote deployment readiness, or publish external claims.
-->

# Governance Normalization Map

Status: Foundation Mode

This map names the repository-local source-of-truth surfaces for the governance
instructions that are repeated across operator prompts, docs, schemas, examples,
validators, and tests. It is a routing map, not a doctrine replacement.

## Architecture

The normalization chain is:

```text
operator instruction -> AGENTS.md -> canonical doctrine docs
canonical doctrine docs -> schemas/examples/runtime contracts
schemas/examples/runtime contracts -> validators/tests
validators/tests -> workspace governance preflight
```

The purpose is to prevent repeated governance text from becoming multiple
competing sources. When duplicate wording appears, the source below controls.

| Surface | Canonical source | Validator | Proof lane |
| --- | --- | --- | --- |
| `agents_policy` | `AGENTS.md` | `scripts/validate_agents_governance.py` | `tests/test_validate_agents_governance.py` |
| `foundation_mode` | `docs/FOUNDATION_MODE.md` | `scripts/validate_foundation_mode.py` | `tests/test_validate_foundation_mode.py` |
| `phi_platform` | `docs/PHI_CANONICAL_SPEC.md` | `scripts/validate_phi_gps_v3_platform_spec.py` | `tests/test_validate_phi_gps_v3_platform_spec.py` |
| `universal_action_orchestration` | `docs/UNIVERSAL_ACTION_ORCHESTRATION.md` | `scripts/validate_universal_action_orchestration.py` | `tests/test_validate_universal_action_orchestration.py` |
| `mfidel_substrate` | `docs/85_mfidel_substrate_conformance_receipt_contract.md` | `scripts/validate_mfidel_substrate_conformance_receipt.py` | `tests/test_validate_mfidel_substrate_conformance_receipt.py` |
| `software_delivery` | `docs/SDLC.md` | `scripts/validate_sdlc_artifact.py` | `tests/test_validate_sdlc_artifact.py` |
| `workspace_preflight` | `docs/workspace-governance-witness.json` | `scripts/run_workspace_governance_checks.py` | `tests/test_run_workspace_governance_checks.py` |

## Algorithm

1. Treat `AGENTS.md` as the active local operating contract.
2. Route foundational posture claims to `docs/FOUNDATION_MODE.md`.
3. Route Phi, ProofState, solver outcome, and platform-overlay claims to
   `docs/PHI_CANONICAL_SPEC.md`.
4. Route effect-bearing action admission claims to
   `docs/UNIVERSAL_ACTION_ORCHESTRATION.md`.
5. Route Amharic, Ge'ez, Ethiopic, or Mfidel processing claims to
   `docs/85_mfidel_substrate_conformance_receipt_contract.md` and its receipt
   schema.
6. Route software-change lifecycle claims to `docs/SDLC.md`.
7. Route closure claims through the workspace governance preflight runner.

## Drift Rules

1. Do not edit repeated governance wording in isolation when the table names a
   canonical source.
2. Any new canonical source must have a read-only validator and a test file.
3. Any new validator that gates governance closure must be reachable from
   `scripts/run_workspace_governance_checks.py`.
4. Any new governance artifact must be listed in
   `docs/workspace-governance-witness.json`.
5. Mfidel text handling remains exact-preservation only: no Unicode
   normalization, decomposition, recomposition, root-letter model, or
   consonant-vowel split is admitted.
6. Foundation Mode remains the default status until promoted by a named witness.

## Verification

Run:

```powershell
python scripts/validate_governance_normalization_map.py
python -m pytest tests/test_validate_governance_normalization_map.py -q
python scripts/run_workspace_governance_checks.py --check governance_normalization_map
```

For inventory closure after editing this map, also run:

```powershell
python scripts/report_workspace_governance_inventory.py
python scripts/validate_workspace_governance_witness.py
```

STATUS:
  Completeness: 100%
  Invariants verified: source map is local-only, Foundation Mode remains active, Mfidel atomicity preserved, UAO remains non-bypassable, workspace preflight remains the closure gate
  Open issues: none
  Next action: keep this map synchronized when a governance source, validator, or test lane changes
