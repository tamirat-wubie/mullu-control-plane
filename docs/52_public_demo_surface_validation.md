# Public Demo Surface Validation

Purpose: define the local readiness gate for evaluator-facing demo surfaces.

Governance scope: sandbox read models, federation read model, replay
determinism, OpenAPI SDK source, gateway benchmark witness, compliance
alignment, and proof coverage.

## Command

```powershell
$env:PYTHONPATH='mcoi'
python scripts\validate_public_demo_surfaces.py --output .change_assurance\public_demo_surface_validation.json
```

## Checked Surfaces

| Check | Evidence |
|---|---|
| `http_demo_routes` | FastAPI TestClient over sandbox, federation, and replay routes |
| `openapi_source` | `sdk/openapi/mullu.openapi.json` contains required public demo paths |
| `sdk_manifest` | SDK generators are bound to the checked-in OpenAPI source |
| `proof_coverage` | Proof matrix includes demo route surfaces and declared routes |
| `benchmark_witness` | Offline gateway benchmark emits deterministic proof tradeoff |
| `compliance_alignment` | Alignment matrix stays evidence-backed and non-certifying |

STATUS:
  Completeness: 100%
  Invariants verified: local-only validation, bounded check ids, deterministic report hash, sandbox route coverage, federation route coverage, replay route coverage, SDK source alignment, compliance boundary
  Open issues: none
  Next action: run the validator before publishing sandbox or dashboard demos
