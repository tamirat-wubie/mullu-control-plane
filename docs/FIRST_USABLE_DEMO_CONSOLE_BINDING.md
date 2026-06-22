# First Usable Demo Console Binding

Purpose: bind the static First Usable Demo operator read model into the existing Personal Assistant console read model without changing live routes or opening runtime authority.

Governance scope: read-only console composition, no-effect authority preservation, product-compression visibility, and customer-readiness claim separation.

Dependencies:
- `examples/first_usable_demo_packet.json`
- `scripts/render_first_usable_demo_operator_page.py`
- `scripts/build_first_usable_demo_console_binding.py`
- `mcoi/mcoi_runtime/personal_assistant/console.py`

Invariants:
- The binding does not execute skills, call connectors, dispatch workers, create provider drafts, send email, move money, write memory, mutate deployments, or append live receipts.
- The existing console read model remains the source of assistant readiness, lane status, pilot package, skill registry, approvals, receipts, and memory panels.
- The first usable demo read model is attached as a read-only section named `first_usable_demo`.
- The binding includes `first_usable_demo_binding.execution_allowed=false` and preserves all live-effect false fields.
- Customer-readiness and public-launch claims remain blocked.

## Command

```bash
python scripts/build_first_usable_demo_console_binding.py \
  --generated-at 2026-06-22T00:00:00Z \
  --output .change_assurance/first_usable_demo_console_binding.json \
  --json
```

## Operator-visible result

The composed read model answers:

1. What is the current Personal Assistant console state?
2. What is the first usable demo packet?
3. What did the first usable demo explicitly not do?
4. Which authority fields remain false?
5. Which evidence references support the bound read model?
6. What is the next safe action before any route or live connector promotion?

## Boundary

This is not a live route promotion. It is a static read-model composition step used to prepare a later bounded route integration. The next route-level promotion still requires separate tests and must preserve the same no-effect authority boundary.

## Status

Judgment: `SolvedReviewable`.

Reason: the binding closes the gap between the static first usable demo page and the existing Personal Assistant console while preserving Foundation Mode and no-effect authority.
