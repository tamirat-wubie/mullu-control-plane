# InceptaDive Shadow Inspection Contract

Purpose: define the request, response, redaction, replay, and authority
contract for `POST /api/v1/shadow/inspect` and the external-effect advisory
projection route, plus the read-only console evidence view.

Governance scope: advisory-only symbolic intelligence inspection. The route can
classify request risk, emit redacted findings, and record a redacted receipt; it
cannot execute actions, approve actions, mutate memory, dispatch connectors, or
replace a governance verdict.

Dependencies: `mcoi_runtime.app.routers.shadow`,
`mcoi_runtime.app.inceptadive_shadow_integration`, InceptaDive shadow runtime
types, and the redacted shadow receipt store.

Invariants: request text may influence a bounded inspection, but raw request
text, raw evidence references, private memory, and execution authority must not
appear in the response envelope.

## Route

| Field | Value |
| --- | --- |
| Method | `POST` |
| Path | `/api/v1/shadow/inspect` |
| Authority | advisory-only |
| Runtime entry point | `InceptaDiveShadowRuntime.inspect_request` or `preflight_action` |
| Receipt behavior | redacted receipt metadata is returned when the runtime emits a receipt |
| Replay fixture | `mcoi/tests/fixtures/inceptadive_shadow_inspect_replay.json` |

External-effect advisory route:

| Field | Value |
| --- | --- |
| Method | `POST` |
| Path | `/api/v1/shadow/external-effect/advisory` |
| Authority | advisory-only |
| Runtime entry point | `InceptaDiveShadowRuntime.external_effect_advisory` |
| Receipt behavior | records redacted advisory history when the receipt store is enabled |
| Output status | `AwaitingEvidence`, `GovernanceBlocked`, or `SolvedUnverified` |

Console evidence route:

| Field | Value |
| --- | --- |
| Method | `GET` |
| Path | `/api/v1/console/shadow/evidence` |
| Authority | read-only |
| Runtime entry point | `InceptaDiveShadowRuntime.recent_activity` and `recent_external_effect_advisories` |
| Receipt behavior | reads recent redacted result, receipt, and advisory summaries only |
| Obligation history | available when the shadow receipt store is enabled |

## Request Body

| Field | Type | Meaning |
| --- | --- | --- |
| `request_id` | string | Optional caller id. If empty, the route derives a deterministic non-raw id. |
| `stage` | string | `interpretation`, `planning`, `preflight`, or another accepted `ShadowStage` value. |
| `user_input` | string | Raw request text for inspection only; never returned verbatim. |
| `normal_intent` | string | Normal-path intent summary. |
| `normal_plan` | array | Normal-path plan labels; each item is coerced to text. |
| `candidate_action` | string | Candidate action for risk and preflight checks. |
| `explicit_target` | string | Concrete target when known. |
| `scope` | string | Repository, tenant, environment, module, or project scope when known. |
| `risk_level` | string | Accepted `ShadowSeverity` value. |
| `external_side_effect` | boolean | Marks action as capable of changing external state. |
| `memory_contradiction` | boolean | Marks unresolved memory contradiction pressure. |
| `retrieval_receipt_ids` | array | Retrieval receipt references; response exposes only counts. |
| `required_evidence_refs` | array | Required evidence references for preflight; response exposes only counts. |
| `authority_receipt_refs` | array | External-effect advisory route only; response exposes only counts. |
| `created_at` | string | Optional deterministic timestamp; falls back to registered clock. |

Invalid `stage` or `risk_level` values fail closed with HTTP `400` and a bounded
`invalid_shadow_inspect_request` error detail.

## Response Body

Top-level response fields:

| Field | Contract |
| --- | --- |
| `governed` | Always `true`. |
| `registered` | Whether a registered runtime dependency served the request. |
| `result` | Redacted advisory result. |
| `receipt` | Redacted receipt metadata or `null`. |
| `recent_activity` | Result and receipt counts only. |
| `execution_authority` | Always `false`. |
| `raw_request_text_exposed` | Always `false`. |
| `private_memory_exposed` | Always `false`. |

The `result` object may include mode, stage, verdict, finding counts, redacted
finding summaries, repair flags, escalation flags, and snapshot hashes. It must
not include raw `user_input`, raw retrieval receipt ids, raw required evidence
refs, private memory, or any execution handle.

The `receipt` object may include receipt id, request id, mode, stage, context
hash, result id, finding ids, retrieval receipt count, shadow verdict,
governance verdict placeholder, created timestamp, and snapshot hash. It must
not include raw request text or raw evidence refs.

The external-effect `advisory` object may include action families, authority
obligations, evidence obligations, missing-obligation labels, reference counts,
the recommended outcome, and the recommended next action. It must not include
raw request text, raw evidence refs, raw authority refs, private memory, live
adapter handles, connector dispatch handles, or any execution authority flag.
The runtime records the same redacted advisory read model in the selected
shadow receipt store when available.

The console evidence response may include recent result ids, receipt ids,
request ids, modes, stages, verdicts, finding counts, repair counts,
escalation counts, block counts, receipt reference counts, redacted advisory
counts, missing-obligation counts, and non-authority flags. It must not include
raw request text, raw evidence refs, raw authority refs, finding summaries,
private memory, live adapter handles, connector dispatch handles, or any
execution authority flag. If the shadow receipt store is unavailable,
`obligation_history_available` is `false` and the unavailable reason is
`shadow_receipt_store_unavailable`.

## Runtime Fallbacks

1. If the runtime dependency is not registered, the route builds a bounded
   environment-derived fallback runtime and returns `registered=false`.
2. If the runtime is disabled, the route returns a disabled/off posture with
   `execution_authority=false`.
3. If the gate selects deep mode while the bounded deep engine is unavailable,
   the runtime returns the explicit deep-required advisory path rather than
   pretending deep inspection ran.
4. If strict preflight is selected, the route may return `stage=preflight` even
   when the caller submitted an earlier stage. This is a risk escalation signal,
   not execution approval.

## Replay Witness

The fixture `mcoi/tests/fixtures/inceptadive_shadow_inspect_replay.json`
anchors one deterministic high-risk request:

```text
raw ambiguous deploy request
-> bounded shadow inspection
-> strict preflight advisory
-> redacted result
-> redacted receipt metadata
-> recent activity counts
```

The fixture deliberately includes raw request text only under `request`. The
expected response stores redacted fields and absent-token checks. Tests must
prove that raw request text, secret-like tokens, raw retrieval ids, and raw
required evidence refs are absent from the actual route response.

## Authority Boundary

`POST /api/v1/shadow/inspect` is not:

1. a governance approval route;
2. an action execution route;
3. a memory write route;
4. a connector dispatch route;
5. a terminal closure route;
6. a proof-verdict replacement route.

Any future change that grants one of those powers must be a separate governed
capability-authority PR with new schemas, approval evidence, rollback evidence,
and route-family authority witnesses.

`POST /api/v1/shadow/external-effect/advisory` follows the same authority
boundary. It exposes external-effect obligations for operator visibility only;
it cannot satisfy those obligations by itself.

`GET /api/v1/console/shadow/evidence` follows the same authority boundary. It
can summarize stored evidence posture only; it cannot execute, approve, write
memory, dispatch connectors, replace governance verdicts, or manufacture
obligation history that the store does not hold.

STATUS:
  Completeness: route contract, replay witness, external-effect advisory projection, and console evidence view defined
  Invariants verified: advisory-only, read-only evidence posture, redacted response, receipt-count exposure, no execution authority, no connector dispatch authority
  Open issues: none
  Next action: keep replay fixture aligned with route response shape
