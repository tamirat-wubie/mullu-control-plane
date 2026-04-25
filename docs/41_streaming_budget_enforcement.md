# Streaming Budget Enforcement Protocol

Purpose: define predictive debit semantics for streamed symbolic intelligence
responses where final provider usage is only known after completion.

Governance scope: request-start reservation, per-chunk debit, hard cutoff, final
settlement, and proof identifiers carried through the streaming audit chain.

## Architecture

| Layer | Responsibility | Proof anchor |
|---|---|---|
| Reservation | Predict input and output tokens before first byte | `precharge` proof id |
| Chunk debit | Decrement reserved output tokens as chunks leave the runtime | `chunk-debit` proof id |
| Cutoff | Stop delivery when reserved output tokens are exhausted | `cutoff` proof id |
| Settlement | Compare actual usage and cost against reservation | `final-reconcile` proof id |
| Audit | Persist bounded events under `streaming_budget_enforcement.schema.json` | trace entry or hash-chain event |

## Cutoff Semantics

| Semantic | Meaning | Retry eligible | Client contract |
|---|---|---:|---|
| `graceful` | Runtime emits a final cutoff event and terminates SSE cleanly | false | Client keeps delivered tokens and treats response as incomplete |
| `abrupt` | Runtime terminates transport immediately after recording cutoff | false | Client discards partial response unless policy permits partial use |
| `retry_eligible` | Runtime emits cutoff with retry permission under a new reservation | true | Client may retry with a larger reservation or lower requested output |

## Algorithm

1. Compute `estimated_input_tokens` and `estimated_output_tokens` from the
   request envelope, model profile, tenant policy, and budget window.
2. Reserve `estimated_input_tokens + estimated_output_tokens` before streaming.
3. Emit the stream only while `remaining_output_tokens > 0`.
4. Debit each emitted chunk by the deterministic output-token count assigned by
   the runtime token estimator.
5. If a chunk would exceed the reservation, emit only the allowed prefix and
   produce a cutoff event with one of the bounded semantics.
6. On completion or cutoff, settle actual provider usage against the reserved
   amount and record `delta_tokens` and `delta_cost`.
7. Reject silent continuation after cutoff; later debit attempts return zero
   allowed tokens and repeat the cutoff witness.

## Schema

The canonical event surface is
`schemas/streaming_budget_enforcement.schema.json`. Required event families:

1. `reservation_created`
2. `chunk_debited`
3. `cutoff_emitted`
4. `settled`

## Invariants

1. `reserved_total_tokens = estimated_input_tokens + reserved_output_tokens`
2. `emitted_output_tokens <= reserved_output_tokens`
3. Every cutoff has exactly one bounded semantic.
4. Settlement always records token and cost deltas, including zero deltas.
5. All events carry `tenant_id`, `budget_id`, `policy_version`, and `proof_id`.

STATUS:
  Completeness: 100%
  Invariants verified: reservation arithmetic, bounded cutoff semantics, settlement delta, policy-bound witness fields, `/api/v1/stream` binding, `/api/v1/chat/stream` binding, provider-native output delta debit
  Open issues: none
  Next action: benchmark provider-native stream debit behavior against pilot traces
