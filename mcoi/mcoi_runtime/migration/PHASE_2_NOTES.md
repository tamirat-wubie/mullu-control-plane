# Phase 2 Notes — Anti-Fabrication Check (W12 Cascade Engine Scope)

## Background

During the v4.0.0 substrate rollout, a flag named `MUSIA_MODE` was written into the v4.0.0 release notes with documented values (`llm_only` and `full`) and described semantics ("preserves v3.13 behavior", "engages the framework"). A subsequent grep proved the flag was wired nowhere in code:

```
$ grep -rn "MUSIA_MODE\|musia_mode" mullu-control-plane/
RELEASE_NOTES_v4.0.0.md   (the only match — the docs themselves)
```

The flag was a fabrication. It existed only in documentation. Operators reading the release notes would have configured deployments around a flag that has no behavioral effect. The mechanism that prevented this from causing damage was an audit instinct surfacing the discrepancy, not the architecture.

Phase 2's Φ_gov implementation must make this kind of fabrication detectable structurally, not by audit instinct.

## W12 Scope Addition

In addition to the cascade invalidation engine and Φ_gov call contract that wraps the existing guard chain, W12 includes a **doc/code cross-reference pre-release check** with the following contract:

### Check 1 — Flag references must resolve

For every release-notes / RELEASE_*.md / *.md file under `docs/` and the repo root:

- Find every reference to an environment variable (matching `[A-Z_][A-Z0-9_]+_MODE` or any `[A-Z][A-Z0-9_]{2,}` followed by `=`).
- For each reference, prove that at least one Python or Rust source file under the repo references the same identifier.
- If no match is found in code, fail the check with: `unwired flag referenced in <doc>: <flag>`.

### Check 2 — Endpoint references must resolve

For every documented API endpoint of the form `/<noun>/<verb>` or `/<router>/<*>`:

- Prove that at least one router registration in `mcoi_runtime/app/` includes that path prefix.
- If no match, fail with: `unrouted endpoint referenced in <doc>: <path>`.

### Check 3 — Construct references must resolve

For every reference to a 25-construct name in docs (matching the names in `substrate/constructs/tier{1..5}_*.py`):

- Prove the construct is implemented in the corresponding tier file at the version the doc claims.
- If the doc claims a tier-N construct exists but tier-N is not yet implemented, fail with: `unimplemented construct referenced in <doc>: <name> (tier <N> ships in <version>)`.

### Check 4 — Module-path references must resolve

For every reference of the form `mcoi_runtime/<...>/<file>.py` in docs:

- Prove the file exists.
- If not, fail with: `nonexistent module referenced in <doc>: <path>`.

## Implementation Sketch

The check lives at `scripts/validate_doc_code_consistency.py` and runs in CI as part of the existing release-status gate (see `scripts/validate_release_status.py`).

It MUST run before any release notes are merged. A doc-only PR that introduces an unwired flag fails CI. This is the structural enforcement that the architecture is supposed to provide.

The check is itself a Φ_gov pre-release gate: a release that fabricates capability cannot be approved.

## Why this is Φ_gov and not just CI lint

Φ_gov's contract is `Φ_gov(𝕊, Δ, Ctx, auth) → ⟨𝕊′, 𝕁, Δ_reject⟩`. A release is a Δ on the system state. A release that promises capability the system does not have is a Δ that violates the integrity invariant. The natural Φ_gov rejection is `Δ_reject = doc_code_inconsistency(<flag>)`.

By framing the check as a Φ_gov rejection rather than a CI lint, we get:

- A formal `Δ_reject` record in the audit log.
- A structural justification for blocking the release (not "lint failed" but "integrity violation").
- A reusable mechanism that catches the same fabrication pattern in any future release.

## Recorded as a Phase 2 deliverable

This document supersedes the user's W12 scope and is recorded in:

- `mcoi/mcoi_runtime/migration/PHASE_2_NOTES.md` (this file)

When W12 begins, implementation of the four checks above is part of the cascade engine + Φ_gov work, not a separate workstream. The cascade engine and the doc/code consistency check share the same structural pattern: both refuse silent inconsistency, both record `Δ_reject`, both treat fabrication as a first-class governance violation.

## v3.13.1 deliberate trade — gauge vs counter

`substrate/metrics.py:export_to_prometheus` exposes cumulative totals as **gauges**, not counters. This is a deliberate trade-off, not a bug, and is documented here so it does not accumulate as silent debt.

### Why this matters

Prometheus's `rate()` function is calibrated for counters and behaves incorrectly on gauges. Soak-window dashboards that want a path-divergence rate (e.g., `rate(substrate_mfidel_lookups_total{path="legacy_matrix"}[5m])`) will need to use `deriv()` instead — non-obvious for an operator new to the dashboard.

### Why we shipped it anyway

The W4 soak gate is **binary** on `requests_mixed > 0`. Gauges answer that question correctly: the snapshot at any point in time tells you whether mixing has occurred. Rate precision is informational, not gating.

The cost of switching to true counters with delta tracking in v3.13.1 was 2 days of W0a engineering against a metric we don't actually need at gate-precision. The cost of documenting the `deriv()` workaround is one paragraph.

### W1–W2 operator note (to be added to PILOT_OPERATIONS_GUIDE)

> Substrate path metrics are exposed as gauges, not counters, in v3.13.1. To compute path-divergence rate, use `deriv(substrate_mfidel_lookups_total[5m])` rather than `rate(...)`. The W4 gate criterion `requests_mixed > 0` is unaffected by this and reads correctly from the gauge.

### Phase 2 fix

In v4.1.0, `substrate/metrics.py` switches to true counters with delta tracking against the prior export. This requires the registry to track per-export deltas, which is straightforward but was deliberately deferred to keep v3.13.1 pure-additive.

Tracked here (not in a separate ticket) because it is a structural decision, not a backlog item: **we deliberately chose snapshot-precision over rate-precision because the gate decision only needs snapshot-precision**.

---

## Lesson for the audit instinct

The audit instinct that caught `MUSIA_MODE` is not a permanent substitute for structural enforcement. Audit instinct degrades under load, time pressure, and large diff windows. A grep that runs in CI does not. The lesson worth preserving:

> When a doc references a capability, the system should be able to prove the capability exists. If it cannot prove this, the doc is fabrication regardless of authorial intent.

This is the structural rule. W12 is where it becomes enforced.
