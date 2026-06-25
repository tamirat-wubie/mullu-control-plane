# InceptaDive Shadow OpenAPI Witness

Purpose: bind the InceptaDive shadow inspection and external-effect advisory
routes to an exported OpenAPI witness surface.

Governance scope: API documentation and route contract evidence for
advisory-only InceptaDive shadow routes. This witness does not grant execution,
connector dispatch, memory write, external-effect, or governance verdict
authority.

Dependencies: `mcoi_runtime.app.routers.shadow`,
`docs/INCEPTADIVE_SHADOW_INSPECTION_CONTRACT.md`,
`docs/INCEPTADIVE_ASSISTANT_RESPONSE_EMBEDDING.md`,
`docs/INCEPTADIVE_EXTERNAL_EFFECT_ADAPTER_READINESS.md`,
`mcoi/tests/test_openapi_spec.py`, and
`mcoi/tests/test_inceptadive_shadow_routes.py`.

Invariants: route registration must remain explicit, response schemas must
expose non-authority and redaction fields, runtime responses must remain
redacted, and raw request text, private memory, raw evidence references, and
execution handles must not be exposed.

## Witness Surface

| Route | Method | OpenAPI witness | Runtime contract |
| --- | --- | --- | --- |
| `/api/v1/health/shadow` | `GET` | `ShadowHealthResponse` | Read-only health posture. |
| `/api/v1/shadow/inspect` | `POST` | `ShadowInspectResponse` | Redacted bounded shadow inspection. |
| `/api/v1/shadow/external-effect/advisory` | `POST` | `ShadowExternalEffectAdvisoryResponse` | Redacted external-effect obligation advisory. |
| `/api/v1/console/shadow` | `GET` | `ShadowConsoleResponse` | Read-only count-oriented console posture. |

## Required OpenAPI Fields

The exported OpenAPI schema must retain these fields:

| Schema | Required witness fields |
| --- | --- |
| `ShadowHealthResponse` | `execution_authority`, `raw_request_text_exposed`, `private_memory_exposed` |
| `ShadowInspectResponse` | `execution_authority`, `raw_request_text_exposed`, `private_memory_exposed`, `recent_activity` |
| `ShadowExternalEffectAdvisoryResponse` | `execution_authority`, `connector_dispatch_authority`, `memory_write_authority`, `governance_verdict_authority`, `raw_request_text_exposed`, `private_memory_exposed` |
| `ShadowConsoleResponse` | `execution_authority`, `raw_request_text_exposed`, `private_memory_exposed` |

## Authority Boundary

The OpenAPI witness proves only that the API surface exposes the advisory
boundary. It does not prove live external-effect readiness, adapter execution,
connector dispatch, memory writes, or production deployment.

The route family remains blocked from:

1. executing candidate actions;
2. approving plans;
3. dispatching connectors;
4. writing memory;
5. replacing a governance verdict;
6. exposing raw request text, raw evidence refs, private memory, or execution handles.

## Verification

OpenAPI witness:

```powershell
python -m pytest mcoi/tests/test_openapi_spec.py -q --tb=short
```

Behavioral redaction and authority witness:

```powershell
python -m pytest mcoi/tests/test_inceptadive_shadow_routes.py -q --tb=short
```

Assistant response embedding witness:

```powershell
python -m pytest mcoi/tests/test_inceptadive_assistant_response_embedding.py -q --tb=short
```

STATUS:
  Completeness: OpenAPI witness route surface defined
  Invariants verified: route registration, schema-visible non-authority flags, schema-visible redaction flags, advisory-only route family
  Open issues: live external-effect adapter readiness remains AwaitingEvidence
  Next action: keep OpenAPI witness tests aligned when shadow response envelopes change
