# InceptaDive Assistant Response Embedding

Purpose: define the redacted metadata contract for InceptaDive advisory fields
attached to live assistant response envelopes and compatible streaming events.

Governance scope: advisory-only symbolic intelligence metadata for
`POST /api/v1/chat`, `POST /api/v1/chat/stream`, and
`POST /api/v1/chat/workflow`. The embedding can report shadow status, result
ids, receipt ids, bounded counts, and repair/escalation signals. It cannot
execute actions, dispatch connectors, mutate memory, approve plans, or replace
governance verdicts.

Dependencies: `mcoi_runtime.app.inceptadive_assistant_response_embedding`,
`mcoi_runtime.app.routers.llm.chat`, `InceptaDiveShadowRuntime`, and
non-executing shadow hook contracts.

Invariants: raw user input, assistant content, private memory, raw tenant ids,
raw model ids, raw evidence refs, and execution handles must not appear inside
the embedded advisory metadata.

## Applied Routes

| Route | Response field | Stage | Authority |
| --- | --- | --- | --- |
| `POST /api/v1/chat` | `inceptadive_shadow_advisory` | `workflow` | advisory-only |
| `POST /api/v1/chat/stream` | SSE event `inceptadive_shadow_advisory` | `workflow` | advisory-only |
| `POST /api/v1/chat/workflow` | `inceptadive_shadow_advisory` | `workflow` | advisory-only |

For streaming chat, the event is inserted after the existing `meta` event and
before terminal `done`. Existing `meta`, `token`, `done`, budget reservation,
and budget settlement event payloads are preserved.

## Embedded Field Contract

The embedded `inceptadive_shadow_advisory` object must include:

| Field | Contract |
| --- | --- |
| `embedding_surface` | Always `assistant_response`. |
| `route` | The route that emitted the response envelope. |
| `tenant_ref` | Stable deterministic public reference for the tenant boundary; never the raw tenant id. |
| `model_ref` | Stable deterministic public reference for the model or capability boundary; never the raw model id. |
| `tenant_identifier_exposed` | Always `false`. |
| `model_identifier_exposed` | Always `false`. |
| `execution_authority` | Always `false`. |
| `connector_dispatch_authority` | Always `false`. |
| `shadow_memory_write_authority` | Always `false`. |
| `governance_verdict_replaced` | Always `false`. |
| `raw_request_text_exposed` | Always `false`. |
| `assistant_content_exposed` | Always `false`. |
| `private_memory_exposed` | Always `false`. |

Normal route payloads keep their existing content fields. Streaming route
payloads keep their existing SSE events. The advisory is a side metadata block
or side metadata event and does not change generated content, workflow status,
conversation state, cost accounting, or governed dispatch eligibility.

## Failure Behavior

If the advisory path raises, the route still returns the normal assistant
response with a bounded advisory object:

```text
status = unavailable
error_code = inceptadive_assistant_response_advisory_unavailable
execution_authority = false
```

The raw exception message is not returned.

The unavailable fallback follows the same public-identifier policy as the normal
advisory path: it may expose `tenant_ref` and `model_ref`, but it must not expose
`tenant_id`, `model_name`, raw exception text, raw user input, or assistant
content.

## Verification

Focused tests:

```text
mcoi/tests/test_inceptadive_assistant_response_embedding.py
```

The tests prove that live chat, streaming chat, and chat-workflow responses
carry the advisory, that recent shadow activity is recorded, and that raw
request markers, raw tenant identifiers, raw model identifiers, and assistant
content are absent from the advisory.

STATUS:
  Completeness: live assistant response embedding defined for non-streaming and streaming chat surfaces
  Invariants verified: redacted advisory, public-safe tenant/model refs, no execution authority, no connector dispatch, no shadow memory write authority
  Open issues: none for assistant response embedding
  Next action: keep route docs and tests aligned when response envelopes change
