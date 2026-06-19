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
   - Provides in-memory and JSONL-backed redacted result/receipt stores.
   - Backs console summaries without storing raw request text or private memory.

4. `mcoi_runtime.app.inceptadive_shadow_integration`
   - Invokes the bounded deep engine when deep mode is selected and enabled.
   - Records results and receipts through the selected store.
   - Preserves the explicit `DEEP_REQUIRED` fallback when the deep engine is disabled.

5. `mcoi_runtime.core.inceptadive_post_outcome_learning`
   - Emits governance-pending learning candidates from expected-versus-actual outcome comparison.
   - Does not write memory directly.

6. `mcoi_runtime.core.phi_inceptadive_solver_advisory`
   - Converts Phi/InceptaDive reports into compact solver-routing advisories.
   - Exposes proof gaps, hidden assumptions, fracture count, and suggested solver modes without approval authority.

## Runtime path

```text
request or candidate action
-> shadow gate
-> light, strict preflight, or bounded deep pass
-> deterministic result and receipt
-> optional redacted receipt store
-> console summary / solver advisory / governance repair path
```

## Authority invariants

- `execution_authority=false` on results, receipts, classifications, learning candidates, and solver advisories.
- Deep engine output is advisory only.
- Console state is redacted and count-oriented.
- Learning output stays `governance_pending` until a separate governed write path accepts it.
- Phi-GPS advisory output does not close proof obligations by itself.

## Deferred live route slice

Two route-level extensions were intentionally left for a follow-up PR because the current tool session blocked those file rewrites:

1. Attach redacted InceptaDive hook summaries directly to assistant planning route responses.
2. Add a dedicated redacted `POST /api/v1/shadow/inspect` route.

The core runtime now supports those surfaces through `InceptaDiveShadowRuntime.inspect_request`, `preflight_action`, `console_summary`, and `recent_activity`.

## Verification added

Focused tests cover:

- deep engine activation when the gate selects deep mode;
- explicit fallback when the deep engine is disabled;
- receipt-backed console summary counts;
- post-outcome learning candidates remaining governance-pending;
- Phi/InceptaDive solver advisory remaining non-executing.

## Status

Completeness: core runtime activation applied.

Constructive delta: InceptaDive now has a bounded deep engine, action taxonomy, receipt store, outcome-learning candidate path, Phi-GPS solver advisory, and focused tests.

Fracture delta: direct assistant-route response embedding and dedicated inspection route still need a separate route PR.
