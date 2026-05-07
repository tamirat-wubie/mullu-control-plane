# SDK Generation

Purpose: define Python and TypeScript SDK generation from the governed OpenAPI
document.

Governance scope: OpenAPI export, generator commands, language SDK output
locations, and no hand-written endpoint clients.

## Architecture

| Component | Responsibility | Input | Output |
|---|---|---|---|
| OpenAPI exporter | Reads the runtime FastAPI app and writes deterministic JSON | `mcoi_runtime.app.server:app` | `sdk/openapi/mullu.openapi.json` |
| SDK manifest | Declares generator commands and output paths | OpenAPI spec path | Python and TypeScript generator plans |
| Python generator | Produces Python SDK package | OpenAPI JSON | `sdk/python/mullu_client` |
| TypeScript generator | Produces TypeScript SDK package | OpenAPI JSON | `sdk/typescript/src` |

## Commands

```powershell
$env:PYTHONPATH='mcoi'
python scripts\export_openapi.py
python scripts\generate_sdks.py --dry-run
python scripts\generate_sdks.py --language python
python scripts\generate_sdks.py --language typescript
```

## Rules

1. SDKs MUST be generated from `sdk/openapi/mullu.openapi.json`.
2. Endpoint methods MUST NOT be hand-written.
3. Generator command changes MUST update `sdk/sdk-generation.json`.
4. OpenAPI export MUST be deterministic JSON with sorted keys.
5. Generated SDK output directories are artifacts, not source-of-truth contracts.

STATUS:
  Completeness: 100%
  Invariants verified: OpenAPI as source of truth, Python generator declared, TypeScript generator declared, deterministic export path, dry-run generator inspection
  Open issues: generator CLIs must be installed in the release environment before non-dry-run generation
  Next action: run SDK generation in release packaging once generator CLIs are available
