# InceptaDive Assistant Response Embedding

Purpose: define the redacted metadata contract for InceptaDive advisory fields
attached to live non-streaming assistant response envelopes.

Governance scope: advisory-only symbolic intelligence metadata for
`POST /api/v1/chat` and `POST /api/v1/chat/workflow`. The embedding can report
shadow status, result ids, receipt ids, bounded counts, and repair/escalation
signals. It cannot execute actions, dispatch connectors, mutate memory, approve
plans, or replace governance verdicts.

Dependencies: `mcoi_runtime.app.inceptadive_assistant_response_embedding`,
`mcoi_runtime.app.routers.llm.chat`, `InceptaDiveShadowRuntime`, and
non-executing shadow hook contracts.

Invariants: raw user input, assistant content, private memory, raw evidence refs,
and execution handles must not appear inside the embedded advisory metadata.

## Applied Routes

| Route | Response field | Stage | Authority |
| --- | --- | --- | --- |
| `POST /api/v1/chat` | `inceptadive_shadow_advisory` | `workflow` | advisory-only |
| `POST /api/v1/chat/workflow` | `inceptadive_shadow_advisory` | `workflow` | advisory-only |

Streaming routes remain intentionally outside this slice because SSE event
envelopes have a different compatibility surface.

## Embedded Field Contract

The embedded `inceptadive_shadow_advisory` object must include:

| Field | Contract |
| --- | --- |
| `embedding_surface` | Always `assistant_response`. |
| `route` | The route that emitted the response envelope. |
| `execution_authority` | Always `false`. |
| `connector_dispatch_authority` | Always `false`. |
| `shadow_memory_write_authority` | Always `false`. |
| `governance_verdict_replaced` | Always `false`. |
| `raw_request_text_exposed` | Always `false`. |
| `assistant_content_exposed` | Always `false`. |
| `private_memory_exposed` | Always `false`. |

Normal route payloads keep their existing content fields. The advisory is a
side metadata block and does not change generated content, workflow status,
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

## Verification

Focused tests:

```text
mcoi/tests/test_inceptadive_assistant_response_embedding.py
```

The tests prove that live chat and chat-workflow responses carry the advisory,
that recent shadow activity is recorded, and that raw request markers and
assistant content are absent from the advisory.

STATUS:
  Completeness: live non-streaming assistant response embedding defined
  Invariants verified: redacted advisory, no execution authority, no connector dispatch, no shadow memory write authority
  Open issues: streaming response embedding remains outside this slice
  Next action: keep route docs and tests aligned when streaming envelopes are governed
