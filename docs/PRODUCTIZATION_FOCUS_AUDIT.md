# Productization Focus Audit

Date: 2026-06-20

Purpose: inspect platform maturity, separate constructive progress from fracture risk, and define the smallest next productization sequence.

Governance scope: planning and documentation only. No runtime, connector, worker, repository-write, deployment, receipt-append, or terminal-closure authority is granted.

## Audit judgment

The platform has a strong governance foundation and a growing internal-alpha runtime surface. The main weakness is no longer missing architecture. It is fragmentation between many proof lanes and the absence of one simple, operator-visible, end-to-end product demonstration.

## Constructive deltas

- Personal Assistant readiness, skill catalog, dry-run packet, closure packet, and source integrity checks are coherent.
- Governed Team Assistant Pilot packaging creates a clear product lane.
- Agentic Service Harness now has repository intake, workspace preflight, file-change preflight, receipt dry runs, and dashboard data contracts.
- InceptaDive is integrated as a redacted advisory layer without replacing governance decisions.
- Worker runtime authority remains denied by explicit gates rather than accidental incompleteness.

## Fracture and weakness findings

1. **Product surface gap:** data contracts exist, but the operator experience remains fragmented.
2. **Positive approval gap:** the system proves what is not approval more strongly than it implements signed approval identity, expiry, revocation, and replay protection.
3. **Execution gap:** live effects remain correctly denied, but there is no single controlled path from approved request to reconciled effect and terminal closure.
4. **Status drift risk:** merged, open, superseded, and closed-unmerged PR lineages can be confused without one current-state ledger.
5. **Breadth risk:** new research lanes can consume attention before the primary assistant pilot demonstrates user value.
6. **Preflight cost:** large unsharded governance runs frequently exceed local execution windows, increasing reliance on focused checks and remote CI.

## Applied decisions

- The primary product lane is `Governed Team Assistant Demo v0`.
- New unrelated capability expansion is temporarily subordinate to product-demo closure.
- Security, integrity, correctness, and release-blocking fixes remain allowed at any time.
- Generic continuation, CI success, and historical PR evidence remain non-authorizing.
- Read-only observation precedes any write-capable connector or worker action.

## Ordered development focus

### Level 1 — Status and approval closure

- Maintain `CURRENT_PLATFORM_STATE.md`.
- Complete review of the signed-approval continuation rejection boundary.
- Remove or clearly mark superseded PR lineages.

### Level 2 — Read-only product face

- Project the existing dashboard data contract into one operator-facing read-only view.
- Show readiness, skills, blocked actions, approvals, receipts, and next evidence.
- Keep all action controls absent or disabled.

### Level 3 — Coherent no-effect demo

- Replay one fixture-backed request through readiness, planning, draft, approval preview, dry-run receipt, and closure evidence.
- Present plain-language explanations beside governance evidence.

### Level 4 — Positive signed approval

- Bind operator identity.
- Verify an explicit signature or equivalent governed decision.
- Enforce expiry, revocation, scope, and replay protection.

### Level 5 — Real read-only observation

- Add one live read-only connector observation with redaction, provenance, and receipts.
- Do not add provider mutation in the same change.

### Level 6 — First reversible effect

- Admit one reversible action only after rollback, receipt append, effect reconciliation, trusted time, and terminal closure evidence exist.

## Exit criteria

The current stage is complete when a non-developer can open one read-only demo, understand what Mullu can and cannot do, trace one dry-run workflow, see why an action is blocked, and identify the exact evidence required for promotion.
