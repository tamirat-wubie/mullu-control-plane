# Productization Focus Audit

Date: 2026-06-21
Scope: planning and product focus only. This audit is non-authorizing and does not enable live execution.

## Audit judgment

The repository has enough governance foundation to stop expanding sideways and focus on one understandable product flow.

The correct near-term product is:

**Governed Work Assistant Demo v0**

This is more accurate than "Team Assistant" at the current stage because the demo still mostly helps one operator manage work safely. It becomes a true team assistant only when shared ownership, handoff, reviewer/approver roles, and multi-person coordination are visible.

## What improved

- The no-effect governed assistant demo was merged.
- Mistaken old-thread refinement branches were closed unmerged.
- Stale stacked dashboard work was closed.
- A broad governance packet was closed because it needs splitting before any future admission.
- The product lane is now easier to explain: readiness, draft preview, approval preview, receipts, evidence, and blocked live actions.

## Primary weakness

The system still has a productization bottleneck:

- Many proof surfaces exist.
- The product story is not yet simple enough for a normal operator.
- Live connector and live effect authority remain intentionally blocked.
- Some governance work arrives as very large PRs and should be split into small, reviewable slices.

## Focus rules

1. Demo-first: no new conceptual engine work until the Governed Work Assistant demo is clear.
2. Small PRs only: split broad governance packets before review.
3. No old-thread application: old refinement threads must not write to GitHub unless explicitly requested.
4. No hidden authority: every new route must state whether it is read-only, preview-only, or effect-capable.
5. No effect without approval: live writes require identity, scope, expiry, revocation, replay protection, receipt append, and rollback.

## Near-term roadmap

### Phase 1: Clean demo

- Rename operator-facing language to Governed Work Assistant Demo v0.
- Show what the assistant can preview.
- Show what is blocked and why.
- Show receipt and evidence trail.
- Keep every action no-effect.

### Phase 2: Read-only live observation

- Add one live read-only connector observation.
- Preserve redaction and evidence receipts.
- No mutation, no sending, no repository writes.

### Phase 3: Signed approval lifecycle

- Define approval identity.
- Define approval scope.
- Define expiry and revocation.
- Define replay protection.
- Bind approval to receipt and rollback path.

### Phase 4: First reversible effect

- Pick one low-risk effect.
- Prefer draft creation over sending.
- Require explicit approval and receipt append.
- Verify outcome and rollback.

## Recommended open-branch policy

- Product/demo PRs may proceed when green and scoped.
- Conflicted planning PRs should be recreated from current main rather than force-merged.
- Stale stacked branches should be closed.
- Broad governance mega-branches should be split or closed.

## Current product stage

Strong internal alpha. No-effect demo has reached main. Private alpha requires a read-only live connector and signed approval lifecycle. Paid pilot requires one reversible approved action with reliable evidence and rollback.
