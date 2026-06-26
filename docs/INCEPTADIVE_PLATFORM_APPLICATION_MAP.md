# InceptaDive Platform Application Map

Purpose: record the applied InceptaDive platform surfaces for governed deep-shadow activation.

Governance boundary: InceptaDive may inspect, classify, score, summarize, and recommend repair. It does not approve actions, mutate state, send external messages, write memory, promote truth, or bypass Mullu governance.

## Applied surfaces

1. `mcoi_runtime.core.inceptadive_action_taxonomy`
   - Classifies request and candidate-action text into bounded governance action families.
   - Emits `execution_authority=false`.

2. `mcoi_runtime.core.inceptadive_deep_engine`
   - Runs repository-local deep shadow interrogation when the gate selects deep mode.
   - Builds projection-only Concept Boxes, runs axis traversal, and returns redacted `ShadowPassResult` objects.
   - Keeps all results advisory.

3. `mcoi_runtime.core.inceptadive_shadow_receipt_store`
   - Provides in-memory and JSONL-backed redacted result, receipt, and
     external-effect advisory stores.
   - Hydrates bounded recent JSONL history on runtime startup and fails closed
     on corrupt replay records.
   - Backs console summaries without storing raw request text, raw evidence
     refs, raw authority refs, or private memory.

4. `mcoi_runtime.app.inceptadive_shadow_integration`
   - Invokes the bounded deep engine when deep mode is selected and enabled.
   - Adds bounded deep advisory findings to strict preflight for external-effect
     candidates when the deep engine is explicitly enabled.
   - Records results and receipts through the selected store.
   - Records redacted external-effect advisory history through the selected store.
   - Preserves the explicit `DEEP_REQUIRED` fallback when the deep engine is disabled.

5. `mcoi_runtime.core.inceptadive_post_outcome_learning`
   - Emits governance-pending learning candidates from expected-versus-actual outcome comparison.
   - Does not write memory directly.

6. `mcoi_runtime.core.phi_inceptadive_solver_advisory`
   - Converts Phi/InceptaDive reports into compact solver-routing advisories.
   - Exposes proof gaps, hidden assumptions, fracture count, and suggested solver modes without approval authority.

7. `mcoi_runtime.core.inceptadive_external_effect_boundary`
   - Derives redacted authority and evidence obligations for effect-bearing candidates.
   - Returns `AwaitingEvidence`, `GovernanceBlocked`, or `SolvedUnverified` advisory status without execution authority.
   - Does not dispatch connectors, write memory, approve actions, or replace governance verdicts.

8. `mcoi_runtime.app.routers.shadow`
   - Exposes `POST /api/v1/shadow/inspect` for bounded, redacted, non-executing shadow inspection.
   - Exposes `POST /api/v1/shadow/external-effect/advisory` for read-only external-effect obligation projection.
   - Exposes `GET /api/v1/console/shadow/evidence` for read-only recent result and receipt evidence posture.
   - Returns result, receipt, and redacted advisory metadata without raw request
     text, raw evidence refs, raw authority refs, private memory, or execution
     authority.
   - Route contract: `docs/INCEPTADIVE_SHADOW_INSPECTION_CONTRACT.md`.
   - OpenAPI witness: `docs/INCEPTADIVE_SHADOW_OPENAPI_WITNESS.md`.
   - Replay fixture: `mcoi/tests/fixtures/inceptadive_shadow_inspect_replay.json`.

9. `mcoi_runtime.app.routers.assistant`
   - Embeds compact `inceptadive_shadow_advisory` metadata in assistant preview and assistant planning responses.
   - Keeps the advisory separate from the plan outcome, operator queue state, consent gate, and dispatch authority.

10. `mcoi_runtime.app.inceptadive_assistant_response_embedding`
   - Embeds redacted `inceptadive_shadow_advisory` metadata in live assistant response envelopes.
   - Covers `POST /api/v1/chat`, `POST /api/v1/chat/stream`, and `POST /api/v1/chat/workflow`.
   - Streaming chat emits a side SSE event named `inceptadive_shadow_advisory` without changing existing `meta`, `token`, or `done` events.
   - Route contract: `docs/INCEPTADIVE_ASSISTANT_RESPONSE_EMBEDDING.md`.

## Runtime path

```text
request or candidate action
-> shadow gate
-> light, strict preflight, or bounded deep pass
-> deterministic result and receipt
-> optional external-effect boundary advisory
-> optional redacted receipt store
-> console summary / inspect route / assistant advisory / solver advisory / governance repair path
```

## Authority invariants

- `execution_authority=false` on results, receipts, classifications, learning candidates, and solver advisories.
- Deep engine output is advisory only.
- Console state is redacted and count-oriented.
- Learning output stays `governance_pending` until a separate governed write path accepts it.
- Phi-GPS advisory output does not close proof obligations by itself.
- Assistant response embedding is metadata-only and does not change assistant plan outcomes.
- Live assistant response embedding is metadata-only and does not change content,
  conversation state, workflow status, streaming token events, cost accounting,
  connector dispatch, or governance verdicts.
- `POST /api/v1/shadow/inspect` is advisory-only and cannot execute candidate actions.
- `POST /api/v1/shadow/external-effect/advisory` is advisory-only and cannot execute candidate actions.
- `GET /api/v1/console/shadow/evidence` is read-only and cannot expose raw
  request text, private memory, raw evidence refs, connector handles, memory
  write handles, or governance verdict authority.
- External-effect preflight deep advisories supplement strict preflight findings
  only; they do not grant execution, connector dispatch, memory write, approval,
  or governance verdict authority.
- External-effect boundary advisories expose obligation status only; they do not
  call live adapters or close Mullu governance.
- External-effect advisory history stores redacted obligation posture only; it
  does not store raw request text, raw evidence refs, raw authority refs,
  connector handles, memory handles, or execution handles.
- JSONL-backed shadow history replay validates persisted snapshots before
  serving console summaries; malformed replay records are explicit invariant
  errors.

## Route slice closure

The previously deferred route-level extensions are now applied:

1. Redacted InceptaDive hook summaries are attached directly to assistant route responses.
2. A dedicated redacted `POST /api/v1/shadow/inspect` route is available.

Both surfaces continue to use `InceptaDiveShadowRuntime.inspect_request`,
`preflight_action`, `console_summary`, `recent_activity`, and
`recent_external_effect_advisories`.

## Verification added

Focused tests cover:

- deep engine activation when the gate selects deep mode;
- explicit fallback when the deep engine is disabled;
- receipt-backed console summary counts;
- post-outcome learning candidates remaining governance-pending;
- Phi/InceptaDive solver advisory remaining non-executing.
- redacted inspection route execution without raw request text exposure;
- inspection route replay fixture alignment with redacted response and receipt counts;
- assistant response advisory embedding without execution authority.
- live chat and chat-workflow response embedding without raw request or assistant content exposure.
- streaming chat advisory SSE event insertion without raw request or assistant content exposure.
- external-effect strict preflight receiving bounded deep advisory findings only
  when the deep engine is explicitly enabled.
- external-effect boundary advisory exposing missing and satisfied
  authority/evidence obligations without raw receipt refs or authority flags.
- external-effect advisory route exposing the same obligation surface without
  connector dispatch, memory write, approval, or raw reference exposure.
- OpenAPI export retaining explicit shadow route response models and
  non-authority/redaction fields.
- console evidence route exposing recent result and receipt summaries without
  raw request text, raw evidence refs, private memory, or authority flags.
- JSONL-backed shadow store replaying recent result, receipt, and advisory
  evidence after runtime restart and rejecting corrupt replay records.

## Status

Completeness: core runtime activation and route-level embedding applied.

Constructive delta: InceptaDive now has a bounded deep engine, action taxonomy, replay-capable receipt store, outcome-learning candidate path, Phi-GPS solver advisory, assistant advisory embedding, a dedicated inspection route, external-effect preflight deep advisory supplementation, external-effect boundary advisory, external-effect advisory route projection, and focused tests.

Fracture delta: live execution authority, memory write authority, connector dispatch authority, and governance verdict replacement remain intentionally absent.
