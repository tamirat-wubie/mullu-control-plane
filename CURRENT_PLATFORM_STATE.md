# Current Platform State

Date: 2026-06-21
Scope: productization ledger only. This document does not grant runtime, connector, worker, repository-write, receipt-append, deployment, customer, or production authority.

## Current position

Mullu Control Plane is in a strong internal-alpha / no-effect demo stage.

The governed assistant demo path is now the main product lane. The accidental old-thread refinement branches have been closed and were not merged. The broad split-required governance branch and stale stacked dashboard branch have also been closed.

## What is now admitted to main

- Governed assistant pilot read model.
- Read-only assistant demo surface.
- Operator presentation for readiness, draft preview, approval preview, dry-run receipt trail, closure evidence, and blocked-action reasons.
- Deterministic fixture-backed replay.
- InceptaDive advisory panel as redacted advisory context only.
- Explicit next-phase signed-approval requirements.

## What remains blocked

- Live connector execution.
- External sends.
- Repository writes from the assistant demo.
- Worker dispatch.
- Live receipt append.
- Production or customer-readiness claims.
- Autonomous action without explicit approval, evidence, scope, expiry, and rollback.

## Active product priority

Rename the near-term product lane from "Team Assistant" to the more accurate "Governed Work Assistant Demo v0" unless and until true multi-person team coordination is visible.

The product ladder is:

1. Governed Personal Assistant.
2. Governed Work Assistant.
3. Governed Team Assistant.
4. Governed Organization Assistant.
5. Governed Work OS.

Current implementation is between level 1 and level 2.

## Branch hygiene status

Closed / not product lane:

- PR #2068: mistaken old-thread refinement branch, closed unmerged.
- PR #2069: mistaken old-thread refinement branch, closed unmerged.
- PR #2077: stale stacked dashboard contract, closed unmerged.
- PR #2094: broad split-required governance packet, closed unmerged.

Merged product milestone:

- PR #2089: governed assistant demo closure, merged.

Conflicted / superseded planning branch:

- PR #2066: productization focus audit, conflicted after main advanced; this clean ledger replaces its core purpose.

## Next ordered milestones

1. Keep CI green after the demo merge.
2. Rename and present the current demo as Governed Work Assistant Demo v0.
3. Add a small read-only dashboard route or page that exposes the merged demo state clearly.
4. Add signed approval identity, scope, expiry, revocation, and replay protection.
5. Add one read-only live connector observation.
6. Add one reversible, approved, receipt-backed live action only after the above gates close.

## Product rule

Do not merge broad conceptual or old-thread refinement branches into this repository unless the request explicitly says to apply that specific change to `tamirat-wubie/mullu-control-plane` and the change advances the governed assistant product lane.
