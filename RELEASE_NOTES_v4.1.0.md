# Mullu Platform v4.1.0 — MUSIA Runtime (Full Framework)

**Release date:** TBD
**Codename:** Confluence
**Migration required:** No (additive)

---

## What this release is

The full MUSIA framework. v4.0.0 shipped only the substrate (Mfidel grid +
Tier 1). v4.1.0 ships everything that follows: Tiers 2–5, the cascade
invalidation engine, the Φ_gov call contract, the Φ_agent 6-level filter,
the Mfidel implementations converged into a single source of truth, and the
anti-fabrication gate.

Soak-gate sequencing was overridden at user direction. The release ships
without the 4-week production soak originally planned between v3.13.1 and
v4.0.0. Risk acknowledgments are recorded below.

---

## What is new in v4.1.0

### Constructs — full 25

- **Tier 1 — Foundational**: State, Change, Causation, Constraint, Boundary (shipped in v4.0.0)
- **Tier 2 — Structural**: Pattern, Transformation, Composition, Conservation, Interaction
- **Tier 3 — Coordination**: Coupling, Synchronization, Resonance, Equilibrium, Emergence
- **Tier 4 — Governance**: Source, Binding, Validation, Evolution, Integrity
- **Tier 5 — Cognitive**: Observation, Inference, Decision, Execution, Learning

Each construct has exactly one irreducible responsibility. Cross-tier
disambiguation verifier runs at module load and asserts 25 distinct
responsibilities.

### Cascade invalidation engine

`mcoi_runtime/substrate/cascade.py` — when a construct changes, walks every
transitive dependent and classifies each as PRESERVED, AUTO_REPAIRED,
ESCALATED, or REJECTED.

- BFS traversal with depth bound (default 16)
- Cycle detection via visited set
- Auto-repair is opt-in per construct type (default refuses silent repair)
- Returns `CascadeResult` with full step-by-step record

### Φ_gov call contract

`mcoi_runtime/substrate/phi_gov.py` — implements the spec signature
`Φ_gov(𝕊, Δ, Ctx, auth) → ⟨𝕊′, 𝕁, Δ_reject⟩`.

- ProposedDelta (create | update | delete)
- 4-state ProofState: PASS, FAIL, UNKNOWN, BUDGET_UNKNOWN
- Φ_agent 6-level filter stack (L0 Physical/Logical → L5 Optimization)
- External validators slot: existing `core/governance_guard.py` plugs in here
- Judgment record carries cascade summaries and rejected deltas (no silent rejection)

### Mfidel convergence (Option 1b)

`core/mfidel_matrix.py` is now a **derived view** over
`substrate/mfidel/grid.py`. The substrate is the source of truth.

- Three known-empty positions (`f[20][8]`, `f[21][8]`, `f[24][8]`) are masked to zero in the 272-dim vectorizer
- `MfidelMatrix.lookup()` raises `EmptyFidelSlotError` on those coords
- Both modules now read the same atomic glyphs at every position
- Vector dimension unchanged (272) for backward compatibility with cached embeddings

### Anti-fabrication gate

`scripts/validate_doc_code_consistency.py` — the structural mechanism that
catches MUSIA_MODE-class fabrications before they ship.

Three checks:
- **FLAG**: every `*_MODE` flag in shell-style usage in docs must exist in code
- **PATH**: every Python module path referenced in docs must resolve
- **CONSTRUCT**: every 25-construct name in MUSIA docs must have a class definition

Pre-existing repo issues (3 stale path references) are deferred via
`scripts/doc_code_consistency_baseline.txt`. New fabrications fail CI.

### Action → construct mapping for v1→v2 proof migration

`mcoi/mcoi_runtime/migration/v1_to_v2_mapping.py` — concrete mapping table
that the bulk migration tool will use. Specified in v4.0.0 docs but shipped
as code in v4.1.0.

---

## Test counts

| Suite                                    | v3.13.0 | v4.0.0  | v4.1.0  |
| ---------------------------------------- | ------- | ------- | ------- |
| MCOI Python tests (existing)             | 44,500+ | 44,500+ | 44,500+ |
| MAF Rust tests                           | 180     | 180     | 180     |
| Substrate metrics                        | n/a     | 15      | 15      |
| Tier 1 disambiguation                    | n/a     | embedded| embedded|
| Tier 2 structural                        | n/a     | n/a     | 29      |
| Tier 3 coordination                      | n/a     | n/a     | 22      |
| Tier 4 governance                        | n/a     | n/a     | 24      |
| Tier 5 cognitive                         | n/a     | n/a     | 20      |
| Cascade engine                           | n/a     | n/a     | 12      |
| Φ_gov contract                           | n/a     | n/a     | 16      |
| Mfidel convergence                       | n/a     | n/a     | 9       |

All MUSIA-specific suites pass. Doc/code consistency check passes (91 docs
scanned, 3 deferred via baseline).

---

## Compatibility

- v1 proof reads & writes: still supported
- v2 proof reads & writes: reserved (dual-write lands in v4.2.0)
- All v3.13.x endpoints: unchanged
- All v4.0.0 substrate code: unchanged (additive growth only)
- `MUSIA_MODE` flag: still not wired (no behavior to engage; all framework code is library-level for v4.1.0)

---

## What v4.1.0 still does NOT include

Honest deferral list:

- **15-step SCCCE cognitive cycle** — Tiers 1–5 are the building blocks; the cycle that *runs* on them is Phase 3 work
- **UCJA L0–L9 pipeline** — the execution orchestrator; Phase 3
- **Wired LLM-as-organ pattern** — the construct framework is reachable but no endpoint routes through it yet
- **Bulk proof migration tool** (`mcoi migrate-proofs`) — mapping table exists; runner does not
- **Rust-side USCL extensions** — Python-only for v4.1.0
- **Domain adapters beyond `software_dev`** — `business_process`, `scientific_research`, `manufacturing`, `healthcare`, `education` adapters arrive in v4.2–v4.4

---

## Acknowledged risks (skipped soak gate)

The original plan called for a 4-week production soak after v3.13.1 ships
the substrate-path telemetry, gating Mfidel convergence and Tier 2+ on soak
findings. The soak was skipped at user direction.

What we lose:
- No production-traffic evidence that the dual-Mfidel coexistence period was clean
- No data-driven pilot selection
- No callsite migration audit before convergence

What insulates us:
- Mfidel convergence is `is`-equal to substrate at the source (`FIDEL_GEBETA is MFIDEL_GRID`); no synthesis remains
- The three known-empty positions are explicit and tested
- Tier 2 references Tier 1 by UUID, not by Mfidel coordinate; substrate convergence outcome doesn't change construct shape
- Anti-fabrication gate runs before any release notes ship

What to watch in production:
- `EmptyFidelSlotError` from any caller that previously got a synthesized fidel at f[20][8], f[21][8], or f[24][8]
- The substrate metrics counters (still wired) — non-zero `requests_mixed` post-convergence indicates a caller still on the legacy path

If `EmptyFidelSlotError` fires in production, the caller depended on a
synthesized fidel and needs migration. The error message names the position
explicitly to make the migration obvious.

---

## Honest assessment

v4.1.0 is the first release where the MUSIA framework is structurally
complete. Every construct in the 25-construct framework has a class.
Governance has a contract. Cascade has an engine. Mfidel has one source of
truth. Documentation cannot reference unwired flags without failing CI.

What it is not: a working cognitive engine. The 15-step cycle and UCJA
pipeline that consume these constructs are Phase 3. v4.1.0 is library-level;
the runtime integration that turns these constructs into a live cognitive
loop is the next major piece of work.

**We recommend:**
- Upgrade in place. v4.1.0 is additive.
- Begin building cognitive cycles using the construct + cascade + Φ_gov primitives.
- Do not yet route production LLM calls through the framework — there is no `cycle.run()` to call.
- Use the doc/code consistency check on every PR going forward.

---

## Contributors

Same single architect, same Mullusi project. Soak discipline was traded for
implementation velocity at user direction; risks recorded above.
