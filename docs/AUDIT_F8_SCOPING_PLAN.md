# Audit F8 — MAF Substrate Disconnect Scoping Plan

**Status:** scoping (not yet executing)
**Audit fracture:** F8 — "Rust MAF substrate is claimed to certify the Python control plane, but Python does not call into Rust; both sides implement the same protocol independently"
**Author:** autopilot loop after v4.43.0 (post-F7 closure)
**Decision required:** approval of phasing + build-tooling choice before any code lands

---

## TL;DR

**F8 is real.** The platform ships ~2,500 LoC of Rust in `maf/rust/crates/maf-kernel/` that defines `TransitionReceipt`, `ProofCapsule`, and `CausalLineage`. Python mirrors these in `mcoi_runtime/contracts/proof.py` etc. The two implementations produce **byte-identical hashes** (locked by `test_proof_hash_contract.py` against a hardcoded SHA-256 constant), but at runtime, Python uses its own `proof.py` — Rust never executes for a real request.

The audit's framing was honest: from `docs/MAF_RECEIPT_COVERAGE.md`:

> "The Rust MAF substrate certifies the Python control plane." **NOT a claim today.** Python does not call into Rust. Both sides implement the same protocol independently.

**Closing F8 means:** Python actually calls into Rust for canonical certification. The Rust kernel becomes the single source of truth; Python's `proof.py` becomes either a deprecated path or a verified mirror.

This is a 4-6 week effort with explicit design decisions that need human direction:
1. Build tooling (maturin vs setuptools-rust vs cargo-c)
2. FFI ABI — which functions cross the boundary, in what shape
3. Performance posture — sync vs async, blocking vs threadpool
4. Failure mode — what happens if the Rust binary is missing on a deployment
5. CI integration — how is the cross-language hash invariant maintained as Rust + Python evolve

This document scopes the work; **executing it requires those 5 decisions made by a human.**

---

## Survey: what's actually there

### Rust side (`maf/rust/`)

10 crates totaling roughly 6,000 LoC of Rust:

| Crate | LoC | Purpose |
|---|---:|---|
| `maf-kernel` | 2,558 | State machines, transition receipts, proof capsules, causal lineage |
| `maf-capability` | ~400 | Capability classification (effect, trust, descriptor) |
| `maf-event` | ~300 | Event spine, obligations |
| `maf-governance` | ~500 | Policy DSL, rules, bundles |
| `maf-agent` | ~200 | Agent abstractions |
| `maf-supervisor` | ~250 | Supervisor tick lifecycle |
| `maf-ops` | ~300 | Simulation, utility, benchmarks |
| `maf-orchestration` | ~600 | Jobs, workflows, goals, roles |
| `maf-learning` | ~300 | Decision learning, routing, meta-reasoning |
| `maf-cli` | ~150 | Standalone CLI for kernel testing |

**Currently used by:** the Rust CLI for testing + the cross-language hash test. **Not used at runtime by MCOI.**

### Python side (`mcoi/mcoi_runtime/`)

Mirrors live in:
- `mcoi_runtime/contracts/proof.py` — `TransitionReceipt`, `ProofCapsule` Python dataclasses
- `mcoi_runtime/contracts/integrity.py` — `HashChainEntry` (cross-language)
- `mcoi_runtime/contracts/access_runtime.py` — access decision contract
- ~10 other `contracts/*.py` files — domain-specific types

These are pure Python with `@dataclass(frozen=True, slots=True)`, JSON-serializable, and **the canonical thing every MCOI runtime path uses.**

The cross-language guarantee is in `mcoi/tests/test_proof_hash_contract.py`:

```python
def test_python_receipt_hash_matches_rust_constant():
    receipt = TransitionReceipt(...)
    assert receipt.hash() == "27bf13eff30cd9fd5fc334eff381e9b2349037bd0ef9dc88c2ca15d114a77fe5"
```

And the matching Rust test:

```rust
#[test]
fn receipt_hash_matches_python_sha256() {
    const EXPECTED: &str = "27bf13eff30cd9fd5fc334eff381e9b2349037bd0ef9dc88c2ca15d114a77fe5";
    assert_eq!(capsule.receipt.receipt_hash, EXPECTED);
}
```

Both pinned to the same constant. Drift in either direction is caught at CI.

---

## What F8 closure looks like

**F8 closed** means at least one of these holds:

### Option A — Python calls Rust (the strong form)

Every governance certification path in MCOI calls into the Rust kernel via PyO3. The Python `proof.py` is removed (or kept as a fallback documented as deprecated). Receipts emitted by MCOI are produced by the Rust kernel; cross-language hash equality is now a runtime guarantee, not a test-time invariant.

### Option B — Mutual verification (the medium form)

MCOI keeps its Python `proof.py` for runtime emit, but every emitted receipt is **also verified** by a Rust-side check (in-process via PyO3 or out-of-process via subprocess). A mismatch is treated as a hard error, surfaced as `ProofVerificationError`.

### Option C — Cross-replay verification (the weak form)

Python emits as today. A separate Rust verification job (CLI invoked from CI or a cron) replays a sample of recent receipts through the Rust kernel and asserts hash equality. No runtime change.

**The audit framing implies Option A is the eventual goal.** But Option B is a defensible intermediate; Option C is what we have today plus automation.

---

## The five decisions blocking execution

Before any code lands, a human needs to decide:

### Decision 1: Build tooling

| Tool | Pros | Cons |
|---|---|---|
| **maturin** | Most popular, simple `pip install`, handles Mac/Linux/Windows wheel builds | Adds Rust toolchain to dev setup; CI matrix grows |
| **setuptools-rust** | Integrates with existing setuptools workflow | More config; less standard for new projects |
| **cargo-c** + ctypes | No Python-side dependency; just a `.so`/`.dll` | No Python-native types; manual marshalling |

**Recommendation if asked:** maturin. The project already has a Rust toolchain in CI for the `maf-kernel` tests; maturin formalizes that and produces installable wheels.

### Decision 2: FFI ABI shape

What crosses the boundary?

- **Coarse:** `verify_receipt(receipt_json: str) -> bool`. One function, one string-in / bool-out. Simple ABI; no Python-side type complexity.
- **Medium:** `compute_receipt_hash(state_machine_id: str, transition: str, before: str, after: str, ...) -> str`. Several primitive args; structured output. Matches the current Rust API.
- **Fine:** Expose the full Rust types (`TransitionReceipt`, `ProofCapsule`, `CausalLineage`) as PyO3 classes. Python code uses them as if native; behavior matches Rust exactly.

**Recommendation:** start coarse. `verify_receipt(json) -> bool` is enough for Option B (mutual verification) and adds zero complexity to Python's call sites. Refactor toward Medium/Fine in a follow-up if it earns its weight.

### Decision 3: Performance posture

A Rust call from Python's async event loop blocks unless dispatched to a threadpool:

- **Synchronous:** call returns when Rust returns. Simple. Blocks the event loop on every audit append.
- **Threadpool:** `loop.run_in_executor(...)`. Adds latency (context switch) but doesn't block.
- **Async-native:** PyO3-async (rust 1.78+ + crate `pyo3-async-runtimes`). Most complex; best perf if the path is hot.

**Recommendation:** synchronous for first cut. Receipt verification is microseconds; threadpool overhead exceeds the saving. Revisit if profiling shows blocking.

### Decision 4: Failure mode

What if the deployment doesn't have the Rust binary loaded?

- **Hard fail:** ship the Rust wheel as a required dependency; if it's missing, the platform refuses to start.
- **Soft fail:** log CRITICAL, fall back to pure-Python `proof.py`. Operators can opt in to strict mode via env var.
- **Rollout flag:** `MULLU_PROOF_BACKEND=rust|python` env var; pure-Python by default for now, opt-in to Rust per deployment.

**Recommendation:** rollout flag. Defaults to `python` (current behavior); operators opt into `rust`. After bake, flip default. Same shape as the v4.35 `MULLU_ENV_REQUIRED` rollout.

### Decision 5: CI integration

The cross-language hash invariant is currently a unit test on each side. Post-F8 it becomes a runtime invariant. CI must:

- Build the Rust wheel on every PR (already done for the kernel tests)
- Run the full mcoi suite with the Rust backend selected (new — needs `MULLU_PROOF_BACKEND=rust` in the test environment)
- Run a stress test that exercises the FFI under contention (new — pairs with the v4.45 stress test harness for connection pools)

The CI matrix grows by ~1 dimension. If any Python platform doesn't have a Rust wheel, that platform is excluded — explicit decision needed.

---

## Proposed phasing (4 phases, ~4-6 weeks)

If decisions land as recommended (maturin + coarse ABI + sync + rollout flag + new CI dimension):

### Phase 1 — Build infrastructure (1 week)

- Add `pyproject.toml` build-system entry for maturin
- Create `mcoi_runtime/_maf_kernel/` Python module that wraps the FFI
- Add a single `verify_receipt(json: str) -> bool` PyO3 binding to `maf-kernel`
- CI builds the wheel on Linux, macOS, Windows (×3 Python versions = 9 wheels)
- One round-trip test: Python serializes a receipt → Rust verifies → asserts True
- Docs: `docs/MAF_FFI.md` covers the build, the ABI, the failure mode

**Risk:** medium. Build infrastructure across 3 OSes is real work. Manylinux/macOS/Windows each have wheel-format quirks. Plan for 2-3 days of CI debugging.

### Phase 2 — Mutual verification path (1-2 weeks)

- Wire `MULLU_PROOF_BACKEND=rust` env var into proof_bridge construction
- When `rust` is selected: every receipt MCOI emits is also verified by Rust before being persisted
- New error class `ProofVerificationError` for mismatches
- Operator-visible: `proof_bridge_rust_verification_failures` Prometheus metric
- Tests: full mcoi suite must pass with `MULLU_PROOF_BACKEND=rust` set

**Risk:** medium-low. The Python and Rust hashes agree today (locked by the SHA-256 constant test). If they diverge under the new path, the divergence is a real bug — fix it.

### Phase 3 — Hot path migration (1-2 weeks)

- Identify the 3-5 most-traveled audit paths (audit append, governance decision certify, capability invoke)
- Convert each from Python `proof.py.compute_*()` to the Rust binding
- Benchmark before/after; ensure no regression
- Keep the Python implementation for the rollout flag path

**Risk:** low if Phase 2 stable. The semantic guarantee is already proven; this is just routing.

### Phase 4 — Default flip + Python deprecation (1 week)

- Flip `MULLU_PROOF_BACKEND` default from `python` to `rust`
- Deprecate `proof.py` Python implementation (keep behind env var for 1-2 releases)
- After deprecation period: remove Python implementation
- Update `MAF_RECEIPT_COVERAGE.md` to claim the strong form: "Rust certifies"

**Risk:** depends on Phase 2 + 3 bake time. Recommend at least 4 weeks of `MULLU_PROOF_BACKEND=rust` in production before flipping default.

---

## What can land WITHOUT the 5 decisions

If decisions take time, these pieces of F8-adjacent work are still useful:

1. **Tighten the cross-language hash test.** Today it pins one constant. Could pin many — every receipt shape that exists in the codebase. Catches drift earlier.
2. **Build a Rust verification CLI** invoked from CI on exported audit logs. This is Option C from above — the weakest form of F8 closure, but doable in a week without any FFI work.
3. **Document the boundary more strictly.** `MAF_BOUNDARY.md` exists but doesn't enumerate every type that crosses. A complete index makes the FFI ABI design easier later.

Items 1-3 don't require human decisions on tooling/ABI. They're worth doing before Phase 1 if calendar time slips.

---

## Why F8 wasn't closed earlier

The autopilot loop closed 16 of 17 audit fractures because each one fit a "one PR, one fracture" shape: small, contained, mechanically verifiable. F8 doesn't fit:

- It needs **build-tooling decisions** that are downstream of project conventions, not derivable from code
- It needs **FFI ABI design** that affects every future Rust↔Python boundary, not just this one
- It needs **a deprecation period** (Phases 2-4) that can't be compressed below several weeks
- It needs **CI matrix expansion** that has cost across every other PR

These are project-level decisions. The autopilot loop's "one PR, one fracture" pattern doesn't shop for them; a human does.

---

## Recommendation

**Pause F8 until the 5 decisions land.** When they do, this plan executes in 4-6 weeks of focused work. Without those decisions, attempting F8 is guessing at tooling preferences and creating churn that the next contributor will rewrite.

In the meantime, items 1-3 from "What can land without the 5 decisions" are useful warm-up work. Item 1 (tighten the cross-language hash test) is the highest-leverage single piece — it strengthens the existing F8-adjacent guarantee without requiring any FFI work.

After Phase 4 lands, **F8 closes** and the audit-roadmap section in `MAF_RECEIPT_COVERAGE.md` updates from "NOT a claim today" to "Verified — Rust certifies."

---

## Audit roadmap status (post-v4.43.0)

```
✅ F2/F3/F4/F5/F6/F7/F9/F10/F11/F12/F15/F16 + JWT hardening + F15 follow-up
⏳ F8 — MAF substrate disconnect — this plan
```

F8 is the last open audit fracture. After it closes, the audit-fracture taxonomy is feature-complete. Future audits will identify new fractures; the existing 17 will all be covered.
