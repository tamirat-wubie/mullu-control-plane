# Mullu Platform v4.0.0 — MUSIA Runtime (Substrate Only)

**Release date:** TBD (gated on v3.13.1 telemetry patch + 4-week production soak)
**Codename:** Substrate
**Migration required:** No

---

## What this release is

This is the **substrate-only** first step of a multi-release pivot from "Governed AI Operating System" to "Universal Symbolic Causal Intelligence Runtime."

v4.0.0 ships **import-only code** for the Mfidel atomic grid, the 25-construct framework's Tier 1, the universal construct schema, the proof v1→v2 migration spec, and the first domain adapter (`software_dev`).

**Nothing else changes.** No runtime behavior is altered. No request path is modified. No new endpoints are exposed. No flags are added.

The substrate is reachable by import path (`from mcoi_runtime.substrate.mfidel import fidel_at`) but not yet integrated with the request lifecycle. Tiers 2–5, the SCCCE cognitive cycle, the UCJA pipeline, the Φ-operator wrappers, the cascade engine, and the Rust port are all deferred to v4.1+.

---

## What is new in v4.0.0

- **Mfidel atomic substrate** — `mcoi/mcoi_runtime/substrate/mfidel/`
  - 34×8 universal causal encoding grid (`grid.py`)
  - 269 non-empty atomic fidels (3 known-empty slots: `f[20][8]`, `f[21][8]`, `f[24][8]`)
  - Audio overlay rules including ሀ/ሐ/column-8 exceptions
  - Invariants verified at module load
  - **Coexists** with the existing `core/mfidel_matrix.py` (272-dim vectorizer). Convergence to a single source of truth is scheduled for v4.0 → v4.1 (Option 1b: spec is truth, vectorizer is derived view). See `mcoi/mcoi_runtime/substrate/mfidel/grid.py` and `core/mfidel_matrix.py`.
- **Tier 1 foundational constructs** — `mcoi/mcoi_runtime/substrate/constructs/`
  - State, Change, Causation, Constraint, Boundary
  - Each construct has exactly one irreducible responsibility
  - Disambiguation verified at module load
- **Universal construct schema** — `schemas/universal_construct.schema.json`
  - JSON Schema draft-07
  - All 25 construct types enumerated (Tier 1 implemented; Tiers 2–5 reserved as enum slots)
- **Proof v1 → v2 migration spec** — `mcoi/mcoi_runtime/migration/PROOF_V1_TO_V2.md`
  - 4-phase rollout (dual-write → dual-read → v2-primary → v1-frozen)
  - Hash chain continuity rules + rollback plan
  - Specification only; tooling lands in Phase 2
- **Software dev domain adapter** — `mcoi/mcoi_runtime/domain_adapters/software_dev.py`
  - First concrete domain adapter
  - Pattern reference for future adapters
  - Round-trip self-tested (request → universal → result → domain result)

---

## What is NOT in v4.0.0

The following are specified in the MUSIA v3.0 architecture but **not implemented**:

- Tiers 2–5 constructs (20 of 25)
- SCCCE 15-step cognitive cycle
- UCJA L0–L9 pipeline
- Φ_gov / Φ_agent / Φ_multi operator wrappers
- Cascade invalidation engine
- Bounded meta-cognition enforcement
- Rust-side USCL extensions
- Domain → Mfidel encoder (the static grid is complete; the encoder is not)
- Bulk migration tool binary (`mcoi migrate-proofs`)
- Any opt-in flag (e.g. `MUSIA_MODE`) to engage the framework — there is nothing to engage yet

These ship in v4.1.0 and are tracked as the Phase 2 scope.

---

## Runtime behavior change

**None.** v4.0.0 changes no runtime behavior versus v3.13.0.

The substrate code is reachable by import path but is not on any request path. Existing endpoints, governance flow, audit format, proof object format, agent workflows, and budget enforcement are all unchanged.

Performance delta vs v3.13.0: within ±1% (no hot-path code added).

---

## What changes (deferred — listed for transparency)

The following are **specified** by the MUSIA architecture and will introduce breaking changes in future releases. None are active in v4.0.0:

| Change                                       | Active in        |
| -------------------------------------------- | ---------------- |
| Proof object schema v1 → v2 (dual-write)     | v3.14.0          |
| Proof object v2-preferred reads              | v3.15.0          |
| Guard verdict enum (pass/fail → ProofState)  | v3.14.0          |
| Audit log USCL H format                      | v3.14.0          |
| Agent 6-level Φ_agent filter stack           | v4.1.0           |
| Tiers 2–5 constructs                         | v4.1.0           |
| Cascade invalidation engine                  | v4.1.0           |
| Φ_gov call contract wrapping guard chain     | v4.1.0           |
| `MUSIA_MODE` opt-in flag                     | v4.1.0 (when there is a "full" mode to opt into) |

---

## Compatibility matrix

| Component                       | v3.13.x  | v4.0.0   | v4.1.0    | v5.0.0 (planned) |
| ------------------------------- | -------- | -------- | --------- | ---------------- |
| v1 proof reads                  | ✓        | ✓        | ✓         | ✗                |
| v1 proof writes                 | ✓        | ✓        | dual      | ✗                |
| v2 proof reads/writes           | ✗        | reserved | ✓         | ✓                |
| Mfidel substrate (Python)       | ✗        | ✓        | ✓         | ✓                |
| Tier 1 constructs (Python)      | ✗        | ✓        | ✓         | ✓                |
| Tiers 2–5 constructs            | ✗        | ✗        | ✓         | ✓                |
| Cognitive cycle / UCJA          | ✗        | ✗        | ✓         | ✓                |
| Φ-operators wired                | ✗        | ✗        | ✓         | ✓                |

---

## Test counts

| Suite                           | v3.13.0   | v4.0.0    |
| ------------------------------- | --------- | --------- |
| MCOI Python tests               | 44,500+   | 44,500+   |
| MAF Rust tests                  | 180       | 180       |
| Phase 1 substrate self-tests    | n/a       | embedded  |

Larger test additions land in v4.1.0 alongside Tiers 2–5.

---

## Release sequencing

v4.0.0 does not ship in isolation. It is gated on a telemetry-only patch and a production soak:

```
v3.13.0 → v3.13.1 (telemetry patch — substrate path counters, request flow detector)
       → 4-week production soak with both Mfidel paths instrumented
       → v4.0.0  (substrate code lands, runtime behavior unchanged)
       → v4.0.0 + 4-week soak gate
       → v4.0.x  (Mfidel convergence: Option 1b — spec is truth, vectorizer is derived view)
       → v4.1.0  (Tiers 2–5, cascade engine, Φ operators)
```

For installation:

```bash
# No data migration required — substrate is additive.
pip install -U mcoi-runtime==4.0.0
```

---

## Known limitations at v4.0.0

- **Dual Mfidel implementation.** `core/mfidel_matrix.py` (272-dim, dense grid) and `substrate/mfidel/grid.py` (269 atoms, three known-empty slots) coexist. The contract at `contracts/mfidel.py:39` rejects empty glyphs, so a single source of truth requires contract relaxation. Convergence is scheduled for the v4.0.x soak window.
- **Domain adapters.** Only `software_dev` ships. Other adapters (`business_process`, `scientific_research`, `manufacturing`, `healthcare`, `education`) arrive in v4.1–v4.4.
- **Mfidel encoder absent.** The static grid is complete; the `domain → Mfidel` encoder is not yet implemented. `MfidelSignature` objects accept manual coordinate assignments only.
- **Tier 1 is Python-only.** The Rust port lands in Phase 2.

---

## Honest assessment

v4.0.0 is a substrate-only release. It does **not** deliver the MUSIA experience. It establishes the foundation for v4.1 to build on, and it does so without disturbing the v3.13.0 runtime.

**We recommend:**
- Upgrade in place. v4.0.0 is a no-op for existing tenants.
- Optionally experiment with the `substrate` and `domain_adapters` Python packages.
- Wait for v4.1 before retrofitting any workflow.
- Wait for v4.0.x (Mfidel convergence) before grounding new code in the substrate grid.

---

## Contributors

Same single architect, same lack of institutional funding, same Mullusi project.
